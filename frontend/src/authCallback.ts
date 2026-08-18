import { postCalendarAuthCallback } from './api';

function setStatus(message: string): void {
  const el = document.getElementById('status');
  if (el) el.textContent = message;
}

async function completeAuth(): Promise<boolean> {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const errorDescription =
    params.get('error_description') || params.get('error');

  if (errorDescription) {
    setStatus(`Anmeldung fehlgeschlagen: ${errorDescription}`);
    return false;
  }

  if (!code) {
    setStatus('Kein Autorisierungscode erhalten.');
    return false;
  }

  try {
    const { error } = await postCalendarAuthCallback({ body: { code } });
    if (error) {
      setStatus('Verbindung fehlgeschlagen. Bitte erneut versuchen.');
      return false;
    }
    setStatus(
      'Kalender erfolgreich verbunden. Dieses Fenster kann geschlossen werden.'
    );
    return true;
  } catch {
    setStatus('Verbindung zum Server fehlgeschlagen.');
    return false;
  }
}

completeAuth().then((success) => {
  if (typeof Office === 'undefined') return;
  Office.onReady(() => {
    Office.context.ui.messageParent(JSON.stringify({ success }));
  });
});
