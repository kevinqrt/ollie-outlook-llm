import {
  deleteSavedPrompt as deleteSavedPromptApi,
  getPipelineSettings,
  getSavedPrompts,
  type PipelineSettingsSchema,
  postSavedPrompt,
  putPipelineSettings,
  putSavedPrompt,
  type SavedPromptSchema,
  type ValidationError,
} from '../api/generated';

export function extractErrorMessage(
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

/** Lädt den aktuellen (ggf. angepassten) Pipeline-Prompt und die Rückfrage-Einstellung. */
export async function fetchPipelineSettings(): Promise<PipelineSettingsSchema> {
  const response = await getPipelineSettings();
  if (response.error || !response.data) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
  return response.data;
}

export async function savePipelineSettings(
  prompt: string,
  allowClarifyingQuestions: boolean,
  tone: PipelineSettingsSchema['tone'],
  customToneText: string | null
): Promise<PipelineSettingsSchema> {
  const response = await putPipelineSettings({
    body: { prompt, allowClarifyingQuestions, tone, customToneText },
  });
  if (response.error || !response.data) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
  return response.data;
}

/** Lädt die Bibliothek gespeicherter Prompt-Vorlagen. */
export async function listSavedPrompts(): Promise<SavedPromptSchema[]> {
  const response = await getSavedPrompts();
  if (response.error || !response.data) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
  return response.data.prompts;
}

export async function createSavedPrompt(
  text: string
): Promise<SavedPromptSchema> {
  const response = await postSavedPrompt({ body: { text } });
  if (response.error || !response.data) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
  return response.data;
}

export async function updateSavedPrompt(
  id: string,
  text: string
): Promise<SavedPromptSchema> {
  const response = await putSavedPrompt({
    path: { prompt_id: id },
    body: { text },
  });
  if (response.error || !response.data) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
  return response.data;
}

export async function deleteSavedPrompt(id: string): Promise<void> {
  const response = await deleteSavedPromptApi({ path: { prompt_id: id } });
  if (response.error) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
}
