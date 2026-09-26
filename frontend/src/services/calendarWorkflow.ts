import {
  type CalendarEventSchema,
  createCalendarEvent,
  deleteCalendarIcsKnown,
  getCalendarAuthStatus,
  getCalendarIcsKnown,
  getCalendarIcsStatus,
  type KnownCalendarSchema,
  type MeetingProposalSchema,
  postCalendarIcsKnown,
  postCalendarIcsSelf,
  type ValidationError,
} from '../api/generated';
import { officeService } from './officeService';

// Private Microsoft accounts use Outlook on outlook.live.com instead of
// outlook.office.com - configurable via VITE_OUTLOOK_WEB_URL in the root .env.
const OUTLOOK_WEB_URL = (
  import.meta.env.VITE_OUTLOOK_WEB_URL || 'https://outlook.office.com'
).replace(/\/$/, '');
const OWA_COMPOSE_BASE_URL = `${OUTLOOK_WEB_URL}/calendar/0/deeplink/compose`;

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

export type CalendarBackend = 'ics' | 'graph';

export interface CalendarConnection {
  backend: CalendarBackend;
  /** Whether the Microsoft login was completed (always false for ICS). */
  authenticated: boolean;
}

/** Which calendar backend is active and whether Microsoft Graph is connected. */
export async function getCalendarConnection(): Promise<CalendarConnection> {
  const response = await getCalendarAuthStatus();
  return {
    backend: response.data?.backend ?? 'ics',
    authenticated: response.data?.authenticated ?? false,
  };
}

/**
 * Runs the Microsoft login in an Office dialog. The dialog has to start on the
 * add-in's own domain, so it opens auth-start.html, which redirects to the
 * Microsoft login; after consent Microsoft redirects to auth-callback.html,
 * which hands the code to the backend and reports back via messageParent.
 * Resolves with whether the calendar is connected afterwards.
 */
export function connectGraphCalendar(): Promise<boolean> {
  const startUrl = `${window.location.origin}/auth-start.html`;
  return new Promise((resolve, reject) => {
    Office.context.ui.displayDialogAsync(
      startUrl,
      { height: 60, width: 30, promptBeforeOpen: false },
      (result) => {
        if (result.status !== Office.AsyncResultStatus.Succeeded) {
          reject(
            new Error(
              `Anmeldefenster konnte nicht geöffnet werden: ${result.error.message}`
            )
          );
          return;
        }
        const dialog = result.value;
        dialog.addEventHandler(
          Office.EventType.DialogMessageReceived,
          (arg) => {
            dialog.close();
            try {
              const message = JSON.parse(
                'message' in arg ? arg.message : '{}'
              ) as { success?: boolean };
              resolve(message.success === true);
            } catch {
              resolve(false);
            }
          }
        );
        dialog.addEventHandler(Office.EventType.DialogEventReceived, () => {
          // Closed by the user (or navigation error) before finishing.
          resolve(false);
        });
      }
    );
  });
}

/**
 * Creates the proposed meeting directly in the user's calendar via Microsoft
 * Graph. Only call this after the user explicitly confirmed it - attendees
 * receive a real invitation.
 */
export async function createCalendarEventFromProposal(
  proposal: MeetingProposalSchema
): Promise<CalendarEventSchema> {
  const response = await createCalendarEvent({
    body: {
      subject: proposal.subject || DEFAULT_PROPOSAL_SUBJECT,
      body: proposal.body ?? '',
      start: proposal.start,
      end: proposal.end,
      attendees: proposal.attendees ?? [],
    },
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

/** Whether the signed-in user has set their own ICS calendar link. */
export async function checkIcsCalendarStatus(): Promise<boolean> {
  const response = await getCalendarIcsStatus();
  return response.data?.configured ?? false;
}

/**
 * Sets the user's own published-calendar ICS link. The backend fetches and
 * parses it immediately to validate it before saving, so a bad/unreachable
 * link is rejected here rather than failing silently later.
 */
export async function setSelfIcsUrl(url: string): Promise<void> {
  const response = await postCalendarIcsSelf({ body: { url } });
  if (response.error) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
}

export async function listKnownCalendars(): Promise<KnownCalendarSchema[]> {
  const response = await getCalendarIcsKnown();
  return response.data?.calendars ?? [];
}

export async function addKnownCalendar(
  email: string,
  url: string
): Promise<KnownCalendarSchema[]> {
  const response = await postCalendarIcsKnown({ body: { email, url } });
  if (response.error) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
  return response.data?.calendars ?? [];
}

export async function removeKnownCalendar(
  email: string
): Promise<KnownCalendarSchema[]> {
  const response = await deleteCalendarIcsKnown({ path: { email } });
  if (response.error) {
    throw new Error(
      extractErrorMessage(
        response.error as { detail?: string | ValidationError[] },
        response.response?.status
      )
    );
  }
  return response.data?.calendars ?? [];
}

/** Default subject the backend uses when none was found in the text. */
const DEFAULT_PROPOSAL_SUBJECT = 'Termin';

export interface CalendarComposeDetails {
  subject?: string;
  body?: string;
  attendees?: string[];
}

/**
 * Builds an Outlook Web deep link that opens the calendar's "new event"
 * compose page pre-filled with start/end and - if given - subject, body and
 * attendees. It's a real, editable Outlook form, not an auto-created event,
 * and it works regardless of the add-in's Read/Compose mode since it just
 * opens a browser window rather than touching the mailbox item.
 */
export function buildCalendarComposeUrl(
  start: Date,
  end: Date,
  details: CalendarComposeDetails = {}
): string {
  const params = new URLSearchParams({
    path: '/calendar/action/compose',
    rru: 'addevent',
    startdt: start.toISOString(),
    enddt: end.toISOString(),
  });
  if (details.subject) params.set('subject', details.subject);
  if (details.body) params.set('body', details.body);
  if (details.attendees?.length) params.set('to', details.attendees.join(','));
  return `${OWA_COMPOSE_BASE_URL}?${params.toString()}`;
}

/**
 * Opens the calendar compose window for a meeting proposal, pre-filled with a
 * title and the people from the open mail. The title is the topic the backend
 * extracted if it found one, otherwise "Termin mit <Vorname>"; the attendees
 * are the proposal's plus the mail's sender and recipients. The proposal's
 * LLM-written `body` is deliberately not used as description - the small
 * model's text was often not even a full sentence - a fixed sentence naming
 * the counterpart is used instead.
 */
export async function openCalendarComposeWindow(
  proposal: MeetingProposalSchema
): Promise<void> {
  let counterpartName = '';
  let participants: string[] = [];
  try {
    ({ counterpartName, participants } =
      await officeService.getMeetingContext());
  } catch (error) {
    // No mail context (e.g. no item open) - fall back to the proposal alone.
    console.warn('Could not read meeting context from mail:', error);
  }

  const proposalSubject =
    proposal.subject && proposal.subject !== DEFAULT_PROPOSAL_SUBJECT
      ? proposal.subject
      : '';
  const fallbackSubject = counterpartName
    ? `${DEFAULT_PROPOSAL_SUBJECT} mit ${counterpartName}`
    : DEFAULT_PROPOSAL_SUBJECT;
  const attendees = [
    ...new Set(
      [...(proposal.attendees ?? []), ...participants].map((a) =>
        a.toLowerCase()
      )
    ),
  ];

  const url = buildCalendarComposeUrl(
    new Date(proposal.start),
    new Date(proposal.end),
    {
      subject: proposalSubject || fallbackSubject,
      body: counterpartName
        ? `${DEFAULT_PROPOSAL_SUBJECT} mit ${counterpartName}, vereinbart per E-Mail.`
        : '',
      attendees,
    }
  );
  officeService.openUrl(url);
}
