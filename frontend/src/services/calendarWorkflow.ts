import {
  deleteCalendarIcsKnown,
  getCalendarIcsKnown,
  getCalendarIcsStatus,
  type KnownCalendarSchema,
  type MeetingProposalSchema,
  postCalendarIcsKnown,
  postCalendarIcsSelf,
  type ValidationError,
} from '../api/generated';
import { officeService } from './officeService';

const OWA_COMPOSE_BASE_URL =
  'https://outlook.office.com/calendar/0/deeplink/compose';

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
