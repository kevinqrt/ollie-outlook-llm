import { useEffect, useRef, useState, useTransition } from 'react';
import type {
  MeetingProposalSchema,
  ModelOptionSchema,
  PipelineSettingsSchema,
} from './api/generated';
import type {
  ClarificationNeededEvent,
  PipelineEvent,
} from './api/pipelineEvents';
import { ChatAssistant } from './components/ChatAssistant';
import { KnowledgeBase } from './components/KnowledgeBase';
import { PromptLibrary } from './components/PromptLibrary';
import { StyleRules } from './components/StyleRules';
import { useNotification } from './context/NotificationContext';
import {
  createCalendarEventFromProposal,
  getCalendarConnection,
  openCalendarComposeWindow,
} from './services/calendarWorkflow';
import { officeService } from './services/officeService';
import {
  fetchPipelineSettings,
  listModelOptions,
  savePipelineSettings,
} from './services/pipelineSettingsWorkflow';
import { reviseReply, runReplyWorkflow } from './services/replyWorkflow';
import { submitCorrection } from './services/styleRulesWorkflow';
import { summarizeThread } from './services/summaryWorkflow';
import './App.css';

type Tab = 'assistant' | 'chat' | 'knowledge';
type AssistantView = 'main' | 'settings' | 'library' | 'rules';
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

type ToneOption = NonNullable<PipelineSettingsSchema['tone']>;

const TONE_LABELS: Record<ToneOption, string> = {
  friendly: 'Freundlich',
  formal: 'Formell',
  casual: 'Locker',
  custom: 'Benutzerdefiniert',
};

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('assistant');
  const [isCompose, setIsCompose] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [meetingProposal, setMeetingProposal] =
    useState<MeetingProposalSchema | null>(null);
  const [graphCalendarConnected, setGraphCalendarConnected] = useState(false);
  const [creatingEvent, setCreatingEvent] = useState(false);
  const [createdEventFor, setCreatedEventFor] =
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
  const [tone, setTone] = useState<ToneOption>('friendly');
  const [customToneText, setCustomToneText] = useState('');
  const [modelId, setModelId] = useState('');
  const [modelOptions, setModelOptions] = useState<ModelOptionSchema[]>([]);
  const [savingPipelineSettings, setSavingPipelineSettings] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [lastReply, setLastReply] = useState<string | null>(null);
  const [lastEmailContent, setLastEmailContent] = useState<string | null>(null);
  const [revising, setRevising] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
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
        setTone(s.tone ?? 'friendly');
        setCustomToneText(s.customToneText ?? '');
        setModelId(s.model ?? '');
      })
      .catch((error) => {
        console.error(
          'Pipeline-Einstellungen konnten nicht geladen werden:',
          error
        );
      });
    listModelOptions()
      .then(setModelOptions)
      .catch((error) => {
        console.error('Modell-Liste konnte nicht geladen werden:', error);
      });
  }, []);

  async function handleSavePipelineSettings() {
    if (!promptDraft.trim()) return;
    if (tone === 'custom' && !customToneText.trim()) return;
    setSavingPipelineSettings(true);
    try {
      const saved = await savePipelineSettings(
        promptDraft,
        allowClarifyingQuestions,
        tone,
        tone === 'custom' ? customToneText.trim() : null,
        modelId
      );
      setPromptDraft(saved.prompt);
      setAllowClarifyingQuestions(saved.allowClarifyingQuestions ?? false);
      setTone(saved.tone ?? 'friendly');
      setCustomToneText(saved.customToneText ?? '');
      setModelId(saved.model ?? '');
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

  useEffect(() => {
    // Checked per proposal rather than once on mount: the user may have
    // connected the calendar in the chat tab in the meantime.
    if (!meetingProposal) return;
    getCalendarConnection()
      .then((connection) =>
        setGraphCalendarConnected(
          connection.backend === 'graph' && connection.authenticated
        )
      )
      .catch(() => setGraphCalendarConnected(false));
  }, [meetingProposal]);

  async function handleCreateEvent(proposal: MeetingProposalSchema) {
    setCreatingEvent(true);
    try {
      await createCalendarEventFromProposal(proposal);
      setCreatedEventFor(proposal);
      notify('Termin im Kalender eingetragen.', 'success');
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : 'Termin konnte nicht eingetragen werden.';
      notify(msg, 'error');
      console.error('Create calendar event error:', error);
    } finally {
      setCreatingEvent(false);
    }
  }

  async function handleOpenAppointment(proposal: MeetingProposalSchema) {
    try {
      await openCalendarComposeWindow(proposal);
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
    const previousReply = lastReply ?? undefined;
    setSteps([]);
    setIsPlanning(true);
    setMeetingProposal(null);
    setClarification(null);
    setLastReply(null);
    setLastEmailContent(null);
    setFeedbackText('');

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
          clarificationAnswer,
          previousReply
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
        setLastReply(result.finalReply ?? null);
        setLastEmailContent(result.emailContent ?? null);
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

  async function handleRevise() {
    if (!lastReply || !lastEmailContent || revising) return;
    if (!feedbackText.trim()) return;
    setRevising(true);
    try {
      const result = await reviseReply(
        lastEmailContent,
        lastReply,
        feedbackText.trim()
      );
      setLastReply(result.reply);
      setFeedbackText('');
      if (result.placement === 'replaced') {
        notify('Antwort überarbeitet.', 'success');
      } else {
        notify(
          'Ersetzen fehlgeschlagen, Antwort wurde am Cursor eingefügt.',
          'error'
        );
      }
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : 'Antwort konnte nicht überarbeitet werden.';
      notify(`Fehler: ${msg}`, 'error');
      console.error('Revise reply error:', error);
    } finally {
      setRevising(false);
    }
  }

  async function handleSubmitFeedback() {
    if (!lastReply || submittingFeedback) return;
    if (!feedbackText.trim()) return;
    setSubmittingFeedback(true);
    try {
      const result = await submitCorrection(lastReply, feedbackText, '');
      if (result.learned && result.rule) {
        notify(`Gemerkt: ${result.rule.text}`, 'success');
      } else {
        notify(
          'Keine neue Stilregel erkannt (nur der Inhalt wurde geändert oder die Regel ist schon bekannt).',
          'info'
        );
      }
      setFeedbackText('');
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : 'Feedback konnte nicht gespeichert werden.';
      notify(`Fehler: ${msg}`, 'error');
      console.error('Submit correction error:', error);
    } finally {
      setSubmittingFeedback(false);
    }
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

                {meetingProposal && graphCalendarConnected && (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={
                      creatingEvent || createdEventFor === meetingProposal
                    }
                    onClick={() => handleCreateEvent(meetingProposal)}
                  >
                    {createdEventFor === meetingProposal
                      ? '✓ Im Kalender eingetragen'
                      : creatingEvent
                        ? 'Trage ein...'
                        : meetingProposal.attendees?.length
                          ? '📅 Direkt eintragen & Einladung senden'
                          : '📅 Direkt im Kalender eintragen'}
                  </button>
                )}

                {meetingProposal && (
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => handleOpenAppointment(meetingProposal)}
                  >
                    {graphCalendarConnected
                      ? 'In Outlook bearbeiten'
                      : '📅 Termin im Kalender öffnen'}
                  </button>
                )}

                {lastReply && !isPending && (
                  <div className="feedback-block">
                    <label
                      className="pipeline-settings-field-label"
                      htmlFor="reply-feedback"
                    >
                      Was soll Ollie künftig anders machen?
                    </label>
                    <div className="feedback-row">
                      <input
                        id="reply-feedback"
                        type="text"
                        placeholder="z. B. kürzer, immer duzen"
                        value={feedbackText}
                        onChange={(e) => setFeedbackText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleRevise();
                          }
                        }}
                      />
                    </div>
                    <div className="feedback-actions">
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={
                          revising || !lastEmailContent || !feedbackText.trim()
                        }
                        onClick={handleRevise}
                      >
                        {revising ? 'Überarbeite...' : 'Neu generieren'}
                      </button>
                      <button
                        type="button"
                        className="text-button"
                        disabled={submittingFeedback || !feedbackText.trim()}
                        onClick={handleSubmitFeedback}
                      >
                        {submittingFeedback
                          ? 'Merke...'
                          : 'Für die Zukunft merken'}
                      </button>
                    </div>
                  </div>
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
            <label
              className="pipeline-settings-field-label"
              htmlFor="pipeline-tone"
            >
              Tonalität:
            </label>
            <select
              id="pipeline-tone"
              className="pipeline-settings-tone-select"
              value={tone}
              onChange={(e) => setTone(e.target.value as ToneOption)}
            >
              {(Object.keys(TONE_LABELS) as ToneOption[]).map((option) => (
                <option key={option} value={option}>
                  {TONE_LABELS[option]}
                </option>
              ))}
            </select>
            {tone === 'custom' && (
              <input
                type="text"
                className="pipeline-settings-tone-custom-input"
                placeholder="z. B. sehr knapp und direkt"
                value={customToneText}
                onChange={(e) => setCustomToneText(e.target.value)}
              />
            )}
            <label
              className="pipeline-settings-field-label"
              htmlFor="pipeline-model"
            >
              KI-Modell:
            </label>
            <select
              id="pipeline-model"
              className="pipeline-settings-tone-select"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              {modelOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
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
              onClick={() => setAssistantView('rules')}
            >
              Gelernte Stilregeln
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={handleSavePipelineSettings}
              disabled={
                savingPipelineSettings ||
                !promptDraft.trim() ||
                (tone === 'custom' && !customToneText.trim())
              }
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

        {activeTab === 'assistant' && assistantView === 'rules' && (
          <StyleRules onBack={() => setAssistantView('settings')} />
        )}

        {activeTab === 'chat' && <ChatAssistant />}

        {activeTab === 'knowledge' && <KnowledgeBase />}
      </section>
    </main>
  );
}

export default App;
