import { useEffect, useRef, useState, useTransition } from 'react';
import type { MeetingProposalSchema } from './api/generated';
import type {
  ClarificationNeededEvent,
  PipelineEvent,
} from './api/pipelineEvents';
import { ChatAssistant } from './components/ChatAssistant';
import { KnowledgeBase } from './components/KnowledgeBase';
import { PromptLibrary } from './components/PromptLibrary';
import { useNotification } from './context/NotificationContext';
import { openCalendarComposeWindow } from './services/calendarWorkflow';
import { officeService } from './services/officeService';
import {
  fetchPipelineSettings,
  savePipelineSettings,
} from './services/pipelineSettingsWorkflow';
import { runReplyWorkflow } from './services/replyWorkflow';
import { summarizeThread } from './services/summaryWorkflow';
import './App.css';

type Tab = 'assistant' | 'chat' | 'knowledge';
type AssistantView = 'main' | 'settings' | 'library';
type StepStatus = 'pending' | 'running' | 'done';

type PipelineStep = {
  index: number;
  label: string;
  status: StepStatus;
};

const STEP_ICON: Record<StepStatus, string> = {
  pending: '○',
  running: '◐',
  done: '✓',
};

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('assistant');
  const [isCompose, setIsCompose] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [meetingProposal, setMeetingProposal] =
    useState<MeetingProposalSchema | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [clarification, setClarification] =
    useState<ClarificationNeededEvent | null>(null);
  const [clarificationCustomAnswer, setClarificationCustomAnswer] =
    useState('');
  const [assistantView, setAssistantView] = useState<AssistantView>('main');
  const [promptDraft, setPromptDraft] = useState('');
  const [allowClarifyingQuestions, setAllowClarifyingQuestions] =
    useState(false);
  const [savingPipelineSettings, setSavingPipelineSettings] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const { notify, removeNotification } = useNotification();
  const loadingNotificationId = useRef<string | null>(null);

  useEffect(() => {
    if (typeof Office !== 'undefined') {
      Office.onReady(() => {
        setIsCompose(officeService.isComposeMode());
      });
    } else {
      console.warn('Office JS not found, running in browser mode.');
    }
  }, []);

  useEffect(() => {
    fetchPipelineSettings()
      .then((s) => {
        setPromptDraft(s.prompt);
        setAllowClarifyingQuestions(s.allowClarifyingQuestions ?? false);
      })
      .catch((error) => {
        console.error(
          'Pipeline-Einstellungen konnten nicht geladen werden:',
          error
        );
      });
  }, []);

  async function handleSavePipelineSettings() {
    if (!promptDraft.trim()) return;
    setSavingPipelineSettings(true);
    try {
      const saved = await savePipelineSettings(
        promptDraft,
        allowClarifyingQuestions
      );
      setPromptDraft(saved.prompt);
      setAllowClarifyingQuestions(saved.allowClarifyingQuestions ?? false);
      setAssistantView('main');
      notify('Einstellungen gespeichert.', 'success');
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : 'Einstellungen konnten nicht gespeichert werden.';
      notify(msg, 'error');
      console.error('Save pipeline settings error:', error);
    } finally {
      setSavingPipelineSettings(false);
    }
  }

  function handleOpenAppointment(proposal: MeetingProposalSchema) {
    try {
      openCalendarComposeWindow(proposal);
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : 'Kalenderfenster konnte nicht geöffnet werden.';
      notify(msg, 'error');
      console.error('Open calendar compose window error:', error);
    }
  }

  function handleProgress(event: PipelineEvent) {
    switch (event.type) {
      case 'plan_ready':
        setIsPlanning(false);
        setSteps(
          event.steps.map((label, index) => ({
            index,
            label,
            status: 'pending' as const,
          }))
        );
        break;
      case 'step_started':
        setSteps((prev) =>
          prev.map((step) =>
            step.index === event.index ? { ...step, status: 'running' } : step
          )
        );
        break;
      case 'step_completed':
        setSteps((prev) =>
          prev.map((step) =>
            step.index === event.index ? { ...step, status: 'done' } : step
          )
        );
        break;
      default:
        break;
    }
  }

  function handleAction(clarificationAnswer?: string) {
    setSteps([]);
    setIsPlanning(true);
    setMeetingProposal(null);
    setClarification(null);

    startTransition(async () => {
      if (loadingNotificationId.current) {
        removeNotification(loadingNotificationId.current);
      }

      loadingNotificationId.current = notify(
        'KI generiert eine Antwort...',
        'info',
        0
      );

      try {
        const result = await runReplyWorkflow(
          handleProgress,
          clarificationAnswer
        );

        if (loadingNotificationId.current) {
          removeNotification(loadingNotificationId.current);
          loadingNotificationId.current = null;
        }

        if (result.clarification) {
          setClarification(result.clarification);
          return;
        }

        setMeetingProposal(result.meetingProposal ?? null);
        notify('Vorschlag erfolgreich eingefügt!', 'success');
      } catch (error) {
        console.error('Workflow error:', error);
        setMeetingProposal(null);

        if (loadingNotificationId.current) {
          removeNotification(loadingNotificationId.current);
          loadingNotificationId.current = null;
        }

        let finalMessage = 'Ein Fehler ist aufgetreten.';
        if (error instanceof Error) {
          try {
            const parsed = JSON.parse(error.message);
            finalMessage = parsed.detail || error.message;
          } catch {
            finalMessage = error.message;
          }
        }
        notify(`Fehler: ${finalMessage}`, 'error');
      } finally {
        setIsPlanning(false);
      }
    });
  }

  function handleClarificationAnswer(answer: string) {
    if (!answer.trim() || isPending) return;
    setClarificationCustomAnswer('');
    handleAction(answer.trim());
  }

  function handleSelectSavedPrompt(text: string) {
    setPromptDraft(text);
    setAssistantView('settings');
  }

  async function handleSummarize() {
    setIsSummarizing(true);
    setSummary(null);
    try {
      const result = await summarizeThread();
      setSummary(result);
    } catch (error) {
      console.error('Summarize error:', error);
      const msg =
        error instanceof Error
          ? error.message
          : 'Zusammenfassung fehlgeschlagen.';
      notify(`Fehler: ${msg}`, 'error');
    } finally {
      setIsSummarizing(false);
    }
  }

  return (
    <main className="taskpane-minimal">
      <header className="branding">
        <div className="logo-container">
          <img
            src="/icon-80.png"
            alt="Ollie Logo"
            className="logo"
            data-loading={isPending}
          />
        </div>
        <h1>Ollie KI</h1>
      </header>

      <nav className="tab-navigation">
        <button
          type="button"
          className={`tab-button ${activeTab === 'assistant' ? 'active' : ''}`}
          onClick={() => setActiveTab('assistant')}
        >
          E-Mail Assistent
        </button>
        <button
          type="button"
          className={`tab-button ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </button>
        <button
          type="button"
          className={`tab-button ${activeTab === 'knowledge' ? 'active' : ''}`}
          onClick={() => setActiveTab('knowledge')}
        >
          Wissensbasis
        </button>
      </nav>

      <section className="content-area">
        {activeTab === 'assistant' && assistantView === 'main' && (
          <>
            <div className="assistant-toolbar">
              <button
                type="button"
                className="icon-button"
                aria-label="Pipeline-Einstellungen"
                onClick={() => setAssistantView('settings')}
              >
                ⚙️
              </button>
            </div>

            {isCompose ? (
              <div className="action-card">
                <p className="description">
                  Bereit für eine intelligente Antwort.
                </p>
                <button
                  className="primary-button"
                  type="button"
                  disabled={isPending}
                  onClick={() => handleAction()}
                >
                  {isPending ? 'Generiere...' : 'Antwort einfügen'}
                </button>

                {meetingProposal && (
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => handleOpenAppointment(meetingProposal)}
                  >
                    📅 Termin im Kalender öffnen
                  </button>
                )}

                {clarification && (
                  <div className="clarification-block">
                    <p className="clarification-question">
                      {clarification.question}
                    </p>
                    {clarification.options.length > 0 && (
                      <div className="clarification-options">
                        {clarification.options.map((option) => (
                          <button
                            key={option}
                            type="button"
                            className="clarification-option-button"
                            disabled={isPending}
                            onClick={() => handleClarificationAnswer(option)}
                          >
                            {option}
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="clarification-custom-row">
                      <input
                        type="text"
                        placeholder="Sonstiges..."
                        value={clarificationCustomAnswer}
                        onChange={(e) =>
                          setClarificationCustomAnswer(e.target.value)
                        }
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleClarificationAnswer(
                              clarificationCustomAnswer
                            );
                          }
                        }}
                      />
                      <button
                        type="button"
                        className="text-button"
                        disabled={
                          isPending || !clarificationCustomAnswer.trim()
                        }
                        onClick={() =>
                          handleClarificationAnswer(clarificationCustomAnswer)
                        }
                      >
                        Senden
                      </button>
                    </div>
                  </div>
                )}

                {isPending && isPlanning && (
                  <p className="description">Plane Vorgehen...</p>
                )}

                {steps.length > 0 && (
                  <ul className="pipeline-steps">
                    {steps.map((step) => (
                      <li
                        key={step.index}
                        className="pipeline-step"
                        data-status={step.status}
                      >
                        <span className="pipeline-step-icon">
                          {STEP_ICON[step.status]}
                        </span>
                        <span>{step.label}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <div className="info-card">
                <div className="icon-info">ℹ</div>
                <p>
                  Um die KI zu nutzen, klicken Sie bitte erst auf{' '}
                  <strong>Antworten</strong>.
                </p>
              </div>
            )}

            <div className="action-card">
              <button
                className="secondary-button"
                type="button"
                disabled={isSummarizing}
                onClick={handleSummarize}
              >
                {isSummarizing
                  ? 'Fasse zusammen...'
                  : '🧵 Thread zusammenfassen'}
              </button>

              {summary && <p className="summary-panel">{summary}</p>}
            </div>
          </>
        )}

        {activeTab === 'assistant' && assistantView === 'settings' && (
          <div className="pipeline-settings-panel">
            <div className="pipeline-settings-header">
              <button
                type="button"
                className="text-button"
                onClick={() => setAssistantView('main')}
              >
                ← Zurück
              </button>
            </div>
            <label
              className="pipeline-settings-field-label"
              htmlFor="pipeline-prompt"
            >
              Prompt:
            </label>
            <textarea
              id="pipeline-prompt"
              className="pipeline-settings-textarea"
              rows={10}
              value={promptDraft}
              onChange={(e) => setPromptDraft(e.target.value)}
            />
            <label className="pipeline-settings-toggle-row">
              <input
                type="checkbox"
                checked={allowClarifyingQuestions}
                onChange={(e) => setAllowClarifyingQuestions(e.target.checked)}
              />
              Rückfragen erlauben
            </label>
            <button
              type="button"
              className="secondary-button"
              onClick={() => setAssistantView('library')}
            >
              Prompts verwalten
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={handleSavePipelineSettings}
              disabled={savingPipelineSettings || !promptDraft.trim()}
            >
              {savingPipelineSettings ? 'Speichere...' : 'Speichern'}
            </button>
          </div>
        )}

        {activeTab === 'assistant' && assistantView === 'library' && (
          <PromptLibrary
            onSelect={handleSelectSavedPrompt}
            onBack={() => setAssistantView('settings')}
          />
        )}

        {activeTab === 'chat' && <ChatAssistant />}

        {activeTab === 'knowledge' && <KnowledgeBase />}
      </section>
    </main>
  );
}

export default App;
