import { getEmailSuggestion } from '../api';
import { officeService } from './officeService';

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
      throw new Error(
        error ? JSON.stringify(error) : 'Kein Vorschlag generiert'
      );
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
