import { streamEmailSuggestion } from '../api';
import { isPipelineEvent, type PipelineEvent } from '../api/pipelineEvents';
import { officeService } from './officeService';

export type PipelineProgressHandler = (event: PipelineEvent) => void;

/**
 * Der zentrale KI-Antwort-Workflow.
 *
 * Streamt die Pipeline-Schritte (Planung, Teilschritte, Ergebnis) live über
 * SSE, damit der Aufrufer (z. B. die Taskpane-UI) den Fortschritt anzeigen
 * kann, statt nur auf das Endergebnis zu warten.
 */
export async function runReplyWorkflow(onProgress?: PipelineProgressHandler) {
  try {
    officeService.showNotification('Anfrage wird bearbeitet...');

    const content = await officeService.getBodyText();

    const { stream } = await streamEmailSuggestion({
      body: { emailContent: content },
    });

    let finalReply: string | undefined;

    for await (const raw of stream) {
      if (!isPipelineEvent(raw)) {
        continue;
      }

      onProgress?.(raw);

      if (raw.type === 'error') {
        throw new Error(raw.detail);
      }
      if (raw.type === 'done') {
        finalReply = raw.finalReply;
      }
    }

    if (!finalReply) {
      throw new Error('Kein Vorschlag generiert');
    }

    if (officeService.isComposeMode()) {
      await officeService.insertText(finalReply);
    } else {
      officeService.displayReply(finalReply);
    }

    officeService.showNotification('Abgeschlossen');
  } catch (error) {
    officeService.showNotification('Fehler aufgetreten');
    throw error;
  }
}
