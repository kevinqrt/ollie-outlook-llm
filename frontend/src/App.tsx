import { useEffect, useRef, useState, useTransition } from 'react';
import type { PipelineEvent } from './api/pipelineEvents';
import { ChatAssistant } from './components/ChatAssistant';
import { KnowledgeBase } from './components/KnowledgeBase';
import { useNotification } from './context/NotificationContext';
import { officeService } from './services/officeService';
import { runReplyWorkflow } from './services/replyWorkflow';
import './App.css';

type Tab = 'assistant' | 'chat' | 'knowledge';
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
  const [isPlanning, setIsPlanning] = useState(false);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
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

  function handleAction() {
    setSteps([]);
    setIsPlanning(true);

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
        await runReplyWorkflow(handleProgress);
        if (loadingNotificationId.current) {
          removeNotification(loadingNotificationId.current);
          loadingNotificationId.current = null;
        }
        notify('Vorschlag erfolgreich eingefügt!', 'success');
      } catch (error) {
        console.error('Workflow error:', error);

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
        {activeTab === 'assistant' &&
          (isCompose ? (
            <div className="action-card">
              <p className="description">
                Bereit für eine intelligente Antwort.
              </p>
              <button
                className="primary-button"
                type="button"
                disabled={isPending}
                onClick={handleAction}
              >
                {isPending ? 'Generiere...' : 'Antwort einfügen'}
              </button>

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
          ))}

        {activeTab === 'chat' && <ChatAssistant />}

        {activeTab === 'knowledge' && <KnowledgeBase />}
      </section>
    </main>
  );
}

export default App;
