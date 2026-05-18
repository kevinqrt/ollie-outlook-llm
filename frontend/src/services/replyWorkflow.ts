import { getEmailSuggestion } from '../api';
import { officeService } from './officeService';

function describeRequestError(error: unknown): string {
  if (!error) {
    return 'Unbekannter Fehler beim Abruf der Antwort.';
  }

  if (typeof error === 'string') {
    return error;
  }

  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'object') {
    const maybeError = error as {
      detail?: unknown;
      message?: unknown;
      error?: unknown;
      response?: { status?: number; statusText?: string };
    };

    if (typeof maybeError.detail === 'string') {
      return maybeError.detail;
    }
    if (typeof maybeError.message === 'string') {
      return maybeError.message;
    }
    if (typeof maybeError.error === 'string') {
      return maybeError.error;
    }
    if (maybeError.response?.status) {
      const statusText = maybeError.response.statusText
        ? ` ${maybeError.response.statusText}`
        : '';
      return `HTTP ${maybeError.response.status}${statusText}`.trim();
    }
  }

  return 'Unbekannter Fehler beim Abruf der Antwort.';
}

/**
 * Der zentrale KI-Antwort-Workflow.
 */
export async function runReplyWorkflow() {
  try {
    officeService.showNotification('Anfrage wird bearbeitet...');

    // 1. Kontext lesen
    const content = await officeService.getBodyText();

    // 2. KI-Vorschlag holen
    const { data, error } = await getEmailSuggestion({
      body: { emailContent: content },
    });

    if (error || !data?.suggestedReply) {
      throw new Error(error ? describeRequestError(error) : 'Kein Vorschlag generiert');
    }

    const { suggestedReply } = data;

    // 3. Aktion ausführen
    if (officeService.isComposeMode()) {
      await officeService.insertText(suggestedReply);
    } else {
      officeService.displayReply(suggestedReply);
    }

    officeService.showNotification('Abgeschlossen');
  } catch (error) {
    officeService.showNotification('Fehler aufgetreten');
    throw error;
  }
}
