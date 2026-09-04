import {
  type ChatMessageSchema,
  type MeetingProposalSchema,
  postChat,
  type ValidationError,
} from '../api/generated';

function extractErrorMessage(
  error: { detail?: string | ValidationError[] } | null | undefined
): string {
  if (!error) return 'Ein unbekannter Fehler ist aufgetreten.';
  if (typeof error.detail === 'string') return error.detail;
  if (Array.isArray(error.detail)) {
    return error.detail.map((d: ValidationError) => d.msg).join(', ');
  }
  return JSON.stringify(error);
}

export interface ChatResult {
  reply: string;
  meetingProposal?: MeetingProposalSchema | null;
}

/**
 * Sends the conversation history to Ollie and returns the reply, plus a
 * concrete meeting proposal if the message contained a meeting request.
 */
export async function sendChatMessage(
  messages: ChatMessageSchema[]
): Promise<ChatResult> {
  const response = await postChat({ body: { messages } });

  if (response.error) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] }
      )
    );
  }

  return {
    reply: response.data?.reply ?? '',
    meetingProposal: response.data?.meetingProposal,
  };
}
