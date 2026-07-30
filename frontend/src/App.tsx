import { useEffect, useState } from 'react';
import type { PipelineEvent } from './api/pipelineEvents';
import { officeService } from './services/officeService';
import { runReplyWorkflow } from './services/replyWorkflow';
import './App.css';

type RequestStatus = 'idle' | 'loading' | 'success' | 'error';
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
  const [isCompose, setIsCompose] = useState(false);
  const [status, setStatus] = useState<RequestStatus>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [isPlanning, setIsPlanning] = useState(false);
  const [steps, setSteps] = useState<PipelineStep[]>([]);

  useEffect(() => {
    Office.onReady(() => {
      setIsCompose(officeService.isComposeMode());
    });
  }, []);

  function handleProgress(event: PipelineEvent) {
    switch (event.type) {
      case 'plan_ready':
        setIsPlanning(false);
        setSteps(
          event.steps.map((label, index) => ({ index, label, status: 'pending' as const }))
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
          prev.map((step) => (step.index === event.index ? { ...step, status: 'done' } : step))
        );
        break;
      default:
        break;
    }
  }

  async function handleAction() {
    setStatus('loading');
    setErrorMessage('');
    setSteps([]);
    setIsPlanning(true);

    try {
      await runReplyWorkflow(handleProgress);
      setStatus('success');
    } catch (error) {
      setStatus('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Fehler aufgetreten'
      );
    } finally {
      setIsPlanning(false);
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
            data-loading={status === 'loading'}
          />
        </div>
        <h1>Ollie KI</h1>
      </header>

      <section className="content-area">
        {isCompose ? (
          <div className="action-card">
            <p className="description">Bereit für eine intelligente Antwort.</p>
            <button
              className="primary-button"
              type="button"
              disabled={status === 'loading'}
              onClick={handleAction}
            >
              {status === 'loading' ? 'Generiere...' : 'Antwort einfügen'}
            </button>

            {status === 'loading' && isPlanning && (
              <p className="description">Plane Vorgehen...</p>
            )}

            {steps.length > 0 && (
              <ul className="pipeline-steps">
                {steps.map((step) => (
                  <li key={step.index} className="pipeline-step" data-status={step.status}>
                    <span className="pipeline-step-icon">{STEP_ICON[step.status]}</span>
                    <span>{step.label}</span>
                  </li>
                ))}
              </ul>
            )}

            {status === 'success' && (
              <p className="status-label success">✓ Fertig eingefügt</p>
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

        {status === 'error' && (
          <div className="status-label error">{errorMessage}</div>
        )}
      </section>
    </main>
  );
}

export default App;
