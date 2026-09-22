import { postReplyRevision, streamEmailSuggestion } from '../api';
import type { MeetingProposalSchema, ValidationError } from '../api/generated';
import {
  type ClarificationNeededEvent,
  isPipelineEvent,
  type PipelineEvent,
} from '../api/pipelineEvents';
import { officeService } from './officeService';
import { extractErrorMessage } from './pipelineSettingsWorkflow';

export interface ReplyWorkflowResult {
  meetingProposal?: MeetingProposalSchema | null;
  /**
   * Der eingefügte Antworttext. Der Aufrufer braucht ihn, damit der Nutzer
   * dazu Feedback geben kann, aus dem Ollie künftige Vorschläge verbessert.
   */
  finalReply?: string;
  /**
   * Der Text der E-Mail, auf die geantwortet wird. Nach dem Einfügen steht die
   * Antwort selbst im Entwurf, ein erneutes Lesen würde sie also mitschicken;
   * die Überarbeitung braucht deshalb den Text vom ersten Lauf.
   */
  emailContent?: string;
  /**
   * Gesetzt, wenn die Pipeline vor der eigentlichen Antwort eine Rückfrage an
   * den Nutzer stellt (nur wenn die Einstellung dafür aktiviert ist). Der
   * Aufrufer zeigt die Frage/Optionen an und ruft den Workflow danach mit der
   * Antwort in `clarificationAnswer` erneut auf.
   */
  clarification?: ClarificationNeededEvent | null;
}

export type PipelineProgressHandler = (event: PipelineEvent) => void;

/**
 * Der zentrale KI-Antwort-Workflow.
 *
 * Streamt die Pipeline-Schritte (Planung, Teilschritte, Ergebnis) live über
 * SSE, damit der Aufrufer (z. B. die Taskpane-UI) den Fortschritt anzeigen
 * kann, statt nur auf das Endergebnis zu warten.
 */
export async function runReplyWorkflow(
  onProgress?: PipelineProgressHandler,
  clarificationAnswer?: string,
  previousReply?: string
): Promise<ReplyWorkflowResult> {
  try {
    officeService.showNotification('Anfrage wird bearbeitet...');

    const content = await officeService.getBodyText();
    const attendees = await officeService.getRecipients();

    const { stream } = await streamEmailSuggestion({
      body: { emailContent: content, attendees, clarificationAnswer },
    });

    let finalReply: string | undefined;
    let meetingProposal: MeetingProposalSchema | null | undefined;
    let clarification: ClarificationNeededEvent | null = null;

    for await (const raw of stream) {
      if (!isPipelineEvent(raw)) {
        continue;
      }

      onProgress?.(raw);

      if (raw.type === 'error') {
        throw new Error(raw.detail);
      }
      if (raw.type === 'clarification_needed') {
        clarification = raw;
      }
      if (raw.type === 'done') {
        finalReply = raw.finalReply;
        meetingProposal = raw.meetingProposal;
      }
    }

    if (clarification) {
      return { clarification };
    }

    if (!finalReply) {
      throw new Error('Kein Vorschlag generiert');
    }

    if (officeService.isComposeMode()) {
      if (previousReply) {
        await officeService.replaceInsertedText(finalReply);
      } else {
        await officeService.insertText(finalReply);
      }
    } else {
      officeService.displayReply(finalReply);
    }

    officeService.showNotification('Abgeschlossen');
    return { meetingProposal, finalReply, emailContent: content };
  } catch (error) {
    officeService.showNotification('Fehler aufgetreten');
    throw error;
  }
}

export interface ReviseReplyResult {
  reply: string;
  /**
   * `'inserted'`: das vollständige Ersetzen des Entwurfs ist fehlgeschlagen
   * (seltener Office.js-Fehlerfall), die Antwort wurde stattdessen nur am
   * Cursor eingefügt.
   */
  placement: 'replaced' | 'inserted';
}

/**
 * Überarbeitet die zuvor eingefügte Antwort nach Nutzerfeedback und ersetzt sie
 * im Entwurf. Das Feedback gilt nur für diese eine Antwort und wird nicht gelernt.
 */
export async function reviseReply(
  emailContent: string,
  previousReply: string,
  feedback: string
): Promise<ReviseReplyResult> {
  try {
    officeService.showNotification('Antwort wird überarbeitet...');

    const response = await postReplyRevision({
      body: { emailContent, previousReply, feedback },
    });
    if (response.error || !response.data) {
      throw new Error(
        extractErrorMessage(
          response.error as { detail?: string | ValidationError[] },
          response.response?.status
        )
      );
    }

    const reply = response.data.finalReply;
    const placement = await officeService.replaceInsertedText(reply);
    officeService.showNotification('Abgeschlossen');
    return { reply, placement };
  } catch (error) {
    officeService.showNotification('Fehler aufgetreten');
    throw error;
  }
}
