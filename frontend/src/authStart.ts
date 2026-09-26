import { getCalendarAuthLogin } from './api';

/**
 * First page of the Office login dialog: Office only opens dialogs on the
 * add-in's own domain, so this page fetches the Microsoft login URL from the
 * backend and redirects there. Microsoft then redirects to auth-callback.html.
 */
async function redirectToLogin(): Promise<void> {
  const { data, error } = await getCalendarAuthLogin();
  if (error || !data) {
    const status = document.getElementById('status');
    if (status) {
      status.textContent =
        'Anmeldung nicht möglich - ist Microsoft Graph in der .env konfiguriert?';
    }
    if (typeof Office !== 'undefined') {
      Office.onReady(() => {
        Office.context.ui.messageParent(JSON.stringify({ success: false }));
      });
    }
    return;
  }
  window.location.href = data.authUrl;
}

redirectToLogin();
