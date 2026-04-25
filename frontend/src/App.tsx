import { useEffect, useState } from 'react';
import { officeService } from './services/officeService';
import { runReplyWorkflow } from './services/replyWorkflow';
import './App.css';

type RequestStatus = 'idle' | 'loading' | 'success' | 'error';

function App() {
  const [isCompose, setIsCompose] = useState(false);
  const [status, setStatus] = useState<RequestStatus>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    Office.onReady(() => {
      setIsCompose(officeService.isComposeMode());
    });
  }, []);

  async function handleAction() {
    setStatus('loading');
    setErrorMessage('');

    try {
      await runReplyWorkflow();
      setStatus('success');
    } catch (error) {
      setStatus('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Fehler aufgetreten'
      );
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
