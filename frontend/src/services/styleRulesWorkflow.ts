import {
  type CorrectionResponseSchema,
  deleteAllStyleRules,
  deleteStyleRule as deleteStyleRuleApi,
  getStyleRules,
  postCorrection,
  putStyleRulesSettings,
  type StyleRulesSchema,
  type ValidationError,
} from '../api/generated';
import { extractErrorMessage } from './pipelineSettingsWorkflow';

type ApiError = { detail?: string | ValidationError[] };

/** Lädt die gelernten Stilregeln und ob das Lernen aus Korrekturen aktiv ist. */
export async function fetchStyleRules(): Promise<StyleRulesSchema> {
  const response = await getStyleRules();
  if (response.error || !response.data) {
    throw new Error(
      extractErrorMessage(response.error as ApiError, response.response?.status)
    );
  }
  return response.data;
}

export async function setStyleLearningEnabled(
  enabled: boolean
): Promise<StyleRulesSchema> {
  const response = await putStyleRulesSettings({ body: { enabled } });
  if (response.error || !response.data) {
    throw new Error(
      extractErrorMessage(response.error as ApiError, response.response?.status)
    );
  }
  return response.data;
}

/**
 * Schickt eine Nutzerkorrektur an das Backend, das daraus eine allgemeine
 * Stilregel ableitet. `feedback` ist eine Anweisung (z. B. "kürzer"),
 * `correctedReply` optional die korrigierte Fassung; mindestens eines von
 * beiden muss gesetzt sein.
 */
export async function submitCorrection(
  originalReply: string,
  feedback: string,
  correctedReply: string
): Promise<CorrectionResponseSchema> {
  const response = await postCorrection({
    body: {
      originalReply,
      feedback: feedback.trim() || null,
      correctedReply: correctedReply.trim() || null,
    },
  });
  if (response.error || !response.data) {
    throw new Error(
      extractErrorMessage(response.error as ApiError, response.response?.status)
    );
  }
  return response.data;
}

export async function deleteStyleRule(id: string): Promise<void> {
  const response = await deleteStyleRuleApi({ path: { rule_id: id } });
  if (response.error) {
    throw new Error(
      extractErrorMessage(response.error as ApiError, response.response?.status)
    );
  }
}

export async function clearStyleRules(): Promise<void> {
  const response = await deleteAllStyleRules();
  if (response.error) {
    throw new Error(
      extractErrorMessage(response.error as ApiError, response.response?.status)
    );
  }
}
