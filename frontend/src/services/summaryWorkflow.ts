import { summarizeEmailThread } from '../api';
import type { ValidationError } from '../api/generated';
import { officeService } from './officeService';

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

/**
 * Liest den aktuell geöffneten Mail-Body (inkl. zitiertem Verlauf) und lässt
 * ihn von Ollie zusammenfassen. Fügt das Ergebnis nicht in die Mail ein - der
 * Aufrufer zeigt es an.
 */
export async function summarizeThread(): Promise<string> {
  const header = officeService.getThreadHeader();
  const bodyText = await officeService.getBodyText();

  const response = await summarizeEmailThread({
    body: { threadText: header + bodyText },
  });

  if (response.error) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] }
      )
    );
  }

  return response.data?.summary ?? '';
}
