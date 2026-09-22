import {
  type ChatMessageSchema,
  type MeetingProposalSchema,
  postChat,
  type ValidationError,
} from '../api/generated';

function extractErrorMessage(
  error: { detail?: string | ValidationError[] } | null | undefined,
  status?: number
): string {
  if (error) {
    if (typeof error.detail === 'string') return error.detail;
    if (Array.isArray(error.detail)) {
      return error.detail.map((d: ValidationError) => d.msg).join(', ');
    }
    // A network/fetch failure (backend unreachable, CORS, ...) surfaces here as
    // a raw Error instance rather than a parsed API error body.
    if (error instanceof Error) return error.message;
    // DOMException (e.g. AbortError) and similar browser error objects don't
    // extend Error but still carry a readable `message`.
    const message = (error as { message?: unknown }).message;
    if (typeof message === 'string' && message) return message;
    // A non-2xx response with an empty body (e.g. the dev proxy answering for
    // an unreachable backend) is normalized by the SDK into a plain "{}" - not
    // useful on its own, so fall through to the status-based message below
    // instead of showing that literal "{}" to the user.
    const stringified = JSON.stringify(error);
    if (stringified && stringified !== '{}') return stringified;
  }
  return status
    ? `Server nicht erreichbar oder Fehler (HTTP ${status}). Läuft das Backend?`
    : 'Server nicht erreichbar. Läuft das Backend?';
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
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }

  return {
    reply: response.data?.reply ?? '',
    meetingProposal: response.data?.meetingProposal,
  };
}
