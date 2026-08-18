import { getEmailSuggestion } from '../api';
import type { MeetingProposalSchema } from '../api/generated';
import { officeService } from './officeService';

export interface ReplyWorkflowResult {
  meetingProposal?: MeetingProposalSchema | null;
}

/**
 * Der zentrale KI-Antwort-Workflow.
 */
export async function runReplyWorkflow(): Promise<ReplyWorkflowResult> {
  try {
    officeService.showNotification('Anfrage wird bearbeitet...');

    // 1. Kontext lesen
    const content = await officeService.getBodyText();
    const attendees = await officeService.getRecipients();

    // 2. KI-Vorschlag holen
    const { data, error } = await getEmailSuggestion({
      body: { emailContent: content, attendees },
    });

    if (error || !data?.suggestedReply) {
      throw new Error(
        error ? JSON.stringify(error) : 'Kein Vorschlag generiert'
      );
    }

    const { suggestedReply, meetingProposal } = data;

    // 3. Aktion ausführen
    if (officeService.isComposeMode()) {
      await officeService.insertText(suggestedReply);
    } else {
      officeService.displayReply(suggestedReply);
    }

    officeService.showNotification('Abgeschlossen');
    return { meetingProposal };
  } catch (error) {
    officeService.showNotification('Fehler aufgetreten');
    throw error;
  }
}
