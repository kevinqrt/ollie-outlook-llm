import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createCalendarEvent,
  deleteCalendarIcsKnown,
  getCalendarAuthStatus,
  getCalendarIcsKnown,
  getCalendarIcsStatus,
  postCalendarIcsKnown,
  postCalendarIcsSelf,
} from '../api/generated';
import {
  addKnownCalendar,
  buildCalendarComposeUrl,
  checkIcsCalendarStatus,
  connectGraphCalendar,
  createCalendarEventFromProposal,
  getCalendarConnection,
  listKnownCalendars,
  openCalendarComposeWindow,
  removeKnownCalendar,
  setSelfIcsUrl,
} from './calendarWorkflow';
import { officeService } from './officeService';

const PROPOSAL = {
  subject: 'Termin',
  body: 'Kurze Beschreibung.',
  start: '2026-08-06T16:30:00Z',
  end: '2026-08-06T17:00:00Z',
  attendees: ['alice@example.com'],
};

vi.mock('../api/generated', () => ({
  createCalendarEvent: vi.fn(),
  getCalendarAuthStatus: vi.fn(),
  deleteCalendarIcsKnown: vi.fn(),
  getCalendarIcsKnown: vi.fn(),
  getCalendarIcsStatus: vi.fn(),
  postCalendarIcsKnown: vi.fn(),
  postCalendarIcsSelf: vi.fn(),
}));

vi.mock('./officeService', () => ({
  officeService: {
    openUrl: vi.fn(),
    getMeetingContext: vi.fn(),
  },
}));

describe('calendarWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('checkIcsCalendarStatus', () => {
    it('returns true when configured', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getCalendarIcsStatus).mockResolvedValue({
        data: { configured: true },
        error: null,
      });

      await expect(checkIcsCalendarStatus()).resolves.toBe(true);
    });

    it('returns false when no data is returned', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getCalendarIcsStatus).mockResolvedValue({
        data: undefined,
        error: null,
      });

      await expect(checkIcsCalendarStatus()).resolves.toBe(false);
    });
  });

  describe('setSelfIcsUrl', () => {
    it('resolves when the backend accepts the URL', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postCalendarIcsSelf).mockResolvedValue({
        data: { configured: true },
        error: null,
      });

      await expect(
        setSelfIcsUrl('https://example.com/me.ics')
      ).resolves.toBeUndefined();
      expect(postCalendarIcsSelf).toHaveBeenCalledWith({
        body: { url: 'https://example.com/me.ics' },
      });
    });

    it('throws a readable error when the URL is rejected', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postCalendarIcsSelf).mockResolvedValue({
        data: undefined,
        error: { detail: 'Kalender-Link nicht erreichbar.' },
      });

      await expect(
        setSelfIcsUrl('https://example.com/broken.ics')
      ).rejects.toThrow('Kalender-Link nicht erreichbar.');
    });
  });

  describe('listKnownCalendars', () => {
    it('returns the saved calendars', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getCalendarIcsKnown).mockResolvedValue({
        data: {
          calendars: [
            {
              email: 'alice@example.com',
              url: 'https://example.com/alice.ics',
            },
          ],
        },
        error: null,
      });

      await expect(listKnownCalendars()).resolves.toEqual([
        { email: 'alice@example.com', url: 'https://example.com/alice.ics' },
      ]);
    });
  });

  describe('addKnownCalendar', () => {
    it('sends email and url and returns the updated list', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postCalendarIcsKnown).mockResolvedValue({
        data: {
          calendars: [
            {
              email: 'alice@example.com',
              url: 'https://example.com/alice.ics',
            },
          ],
        },
        error: null,
      });

      const result = await addKnownCalendar(
        'alice@example.com',
        'https://example.com/alice.ics'
      );

      expect(postCalendarIcsKnown).toHaveBeenCalledWith({
        body: {
          email: 'alice@example.com',
          url: 'https://example.com/alice.ics',
        },
      });
      expect(result).toEqual([
        { email: 'alice@example.com', url: 'https://example.com/alice.ics' },
      ]);
    });

    it('throws a readable error when the URL is rejected', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postCalendarIcsKnown).mockResolvedValue({
        data: undefined,
        error: { detail: 'Kalender-Feed konnte nicht gelesen werden.' },
      });

      await expect(
        addKnownCalendar('bob@example.com', 'https://example.com/broken.ics')
      ).rejects.toThrow('Kalender-Feed konnte nicht gelesen werden.');
    });
  });

  describe('removeKnownCalendar', () => {
    it('deletes by email and returns the updated list', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(deleteCalendarIcsKnown).mockResolvedValue({
        data: { calendars: [] },
        error: null,
      });

      const result = await removeKnownCalendar('alice@example.com');

      expect(deleteCalendarIcsKnown).toHaveBeenCalledWith({
        path: { email: 'alice@example.com' },
      });
      expect(result).toEqual([]);
    });
  });

  describe('buildCalendarComposeUrl', () => {
    it('includes only start/end when no details are given', () => {
      const url = buildCalendarComposeUrl(
        new Date('2026-08-06T16:30:00Z'),
        new Date('2026-08-06T17:00:00Z')
      );
      const parsed = new URL(url);

      // The origin depends on VITE_OUTLOOK_WEB_URL (outlook.office.com or
      // outlook.live.com), the path doesn't.
      expect(parsed.pathname).toBe('/calendar/0/deeplink/compose');
      expect(parsed.searchParams.get('path')).toBe('/calendar/action/compose');
      expect(parsed.searchParams.get('rru')).toBe('addevent');
      expect(parsed.searchParams.get('startdt')).toBe(
        '2026-08-06T16:30:00.000Z'
      );
      expect(parsed.searchParams.get('enddt')).toBe('2026-08-06T17:00:00.000Z');
      expect(parsed.searchParams.has('subject')).toBe(false);
      expect(parsed.searchParams.has('body')).toBe(false);
      expect(parsed.searchParams.has('to')).toBe(false);
    });

    it('adds subject, body and comma-separated attendees when given', () => {
      const parsed = new URL(
        buildCalendarComposeUrl(
          new Date('2026-08-06T16:30:00Z'),
          new Date('2026-08-06T17:00:00Z'),
          {
            subject: 'Projektbesprechung',
            body: 'Agenda folgt.',
            attendees: ['soeren@example.com', 'alice@example.com'],
          }
        )
      );

      expect(parsed.searchParams.get('subject')).toBe('Projektbesprechung');
      expect(parsed.searchParams.get('body')).toBe('Agenda folgt.');
      expect(parsed.searchParams.get('to')).toBe(
        'soeren@example.com,alice@example.com'
      );
    });
  });

  describe('openCalendarComposeWindow', () => {
    const openedParams = () =>
      new URL(vi.mocked(officeService.openUrl).mock.calls[0][0]).searchParams;

    it('titles it "Termin mit <Vorname>" and adds the mail participants when the proposal has only the default subject', async () => {
      vi.mocked(officeService.getMeetingContext).mockResolvedValue({
        counterpartName: 'Sören',
        participants: ['soeren@example.com', 'alice@example.com'],
      });

      await openCalendarComposeWindow(PROPOSAL);

      const params = openedParams();
      expect(params.get('startdt')).toBe('2026-08-06T16:30:00.000Z');
      expect(params.get('enddt')).toBe('2026-08-06T17:00:00.000Z');
      expect(params.get('subject')).toBe('Termin mit Sören');
      expect(params.get('body')).toBe(
        'Termin mit Sören, vereinbart per E-Mail.'
      );
      expect(params.get('to')).toBe('alice@example.com,soeren@example.com');
    });

    it('prefers a topic the backend extracted over "Termin mit <Vorname>"', async () => {
      vi.mocked(officeService.getMeetingContext).mockResolvedValue({
        counterpartName: 'Sören',
        participants: [],
      });

      await openCalendarComposeWindow({ ...PROPOSAL, subject: 'Kickoff' });

      expect(openedParams().get('subject')).toBe('Kickoff');
    });

    it('falls back to the proposal alone when the mail context is unavailable', async () => {
      vi.mocked(officeService.getMeetingContext).mockRejectedValue(
        new Error('Kein Element ausgewählt.')
      );

      await openCalendarComposeWindow(PROPOSAL);

      const params = openedParams();
      expect(params.get('subject')).toBe('Termin');
      expect(params.has('body')).toBe(false);
      expect(params.get('to')).toBe('alice@example.com');
    });
  });

  describe('getCalendarConnection', () => {
    it('returns the backend and login state', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getCalendarAuthStatus).mockResolvedValue({
        data: { authenticated: true, backend: 'graph' },
        error: null,
      });

      await expect(getCalendarConnection()).resolves.toEqual({
        backend: 'graph',
        authenticated: true,
      });
    });

    it('falls back to ICS when no data is returned', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getCalendarAuthStatus).mockResolvedValue({
        data: undefined,
        error: null,
      });

      await expect(getCalendarConnection()).resolves.toEqual({
        backend: 'ics',
        authenticated: false,
      });
    });
  });

  describe('createCalendarEventFromProposal', () => {
    it('sends the proposal to the backend and returns the event', async () => {
      const event = {
        id: 'event-1',
        subject: 'Termin',
        start: PROPOSAL.start,
        end: PROPOSAL.end,
        webLink: 'https://outlook.live.com/calendar/item/event-1',
      };
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(createCalendarEvent).mockResolvedValue({
        data: event,
        error: null,
      });

      await expect(createCalendarEventFromProposal(PROPOSAL)).resolves.toEqual(
        event
      );
      expect(createCalendarEvent).toHaveBeenCalledWith({
        body: {
          subject: 'Termin',
          body: 'Kurze Beschreibung.',
          start: PROPOSAL.start,
          end: PROPOSAL.end,
          attendees: ['alice@example.com'],
        },
      });
    });

    it('throws the backend error message', async () => {
      vi.mocked(createCalendarEvent).mockResolvedValue({
        data: undefined,
        error: { detail: 'Direktes Anlegen nicht unterstuetzt.' },
        response: { status: 503 },
      } as never);

      await expect(createCalendarEventFromProposal(PROPOSAL)).rejects.toThrow(
        'Direktes Anlegen nicht unterstuetzt.'
      );
    });
  });

  describe('connectGraphCalendar', () => {
    type Handler = (arg: { message: string } | { error: number }) => void;

    function mockOfficeDialog() {
      const handlers: Record<string, Handler> = {};
      const dialog = {
        close: vi.fn(),
        addEventHandler: vi.fn((type: string, handler: Handler) => {
          handlers[type] = handler;
        }),
      };
      const displayDialogAsync = vi.fn(
        (
          _url: string,
          _options: unknown,
          callback: (result: unknown) => void
        ) => callback({ status: 'succeeded', value: dialog })
      );
      vi.stubGlobal('window', {
        location: { origin: 'https://localhost:3000' },
      });
      vi.stubGlobal('Office', {
        AsyncResultStatus: { Succeeded: 'succeeded' },
        EventType: {
          DialogMessageReceived: 'message',
          DialogEventReceived: 'event',
        },
        context: { ui: { displayDialogAsync } },
      });
      return { handlers, dialog, displayDialogAsync };
    }

    it('opens auth-start.html and resolves with the login result', async () => {
      const { handlers, dialog, displayDialogAsync } = mockOfficeDialog();

      const promise = connectGraphCalendar();
      handlers.message({ message: JSON.stringify({ success: true }) });

      await expect(promise).resolves.toBe(true);
      expect(displayDialogAsync.mock.calls[0][0]).toBe(
        'https://localhost:3000/auth-start.html'
      );
      expect(dialog.close).toHaveBeenCalled();
      vi.unstubAllGlobals();
    });

    it('resolves false when the user closes the dialog', async () => {
      const { handlers } = mockOfficeDialog();

      const promise = connectGraphCalendar();
      handlers.event({ error: 12006 });

      await expect(promise).resolves.toBe(false);
      vi.unstubAllGlobals();
    });
  });
});
