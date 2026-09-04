import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  deleteCalendarIcsKnown,
  getCalendarIcsKnown,
  getCalendarIcsStatus,
  postCalendarIcsKnown,
  postCalendarIcsSelf,
} from '../api/generated';
import {
  addKnownCalendar,
  buildCalendarComposeUrl,
  checkIcsCalendarStatus,
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
  deleteCalendarIcsKnown: vi.fn(),
  getCalendarIcsKnown: vi.fn(),
  getCalendarIcsStatus: vi.fn(),
  postCalendarIcsKnown: vi.fn(),
  postCalendarIcsSelf: vi.fn(),
}));

vi.mock('./officeService', () => ({
  officeService: {
    openUrl: vi.fn(),
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
    it('includes only start/end, no subject/location/attendees', () => {
      const url = buildCalendarComposeUrl(
        new Date('2026-08-06T16:30:00Z'),
        new Date('2026-08-06T17:00:00Z')
      );
      const parsed = new URL(url);

      expect(parsed.origin + parsed.pathname).toBe(
        'https://outlook.office.com/calendar/0/deeplink/compose'
      );
      expect(parsed.searchParams.get('path')).toBe('/calendar/action/compose');
      expect(parsed.searchParams.get('rru')).toBe('addevent');
      expect(parsed.searchParams.get('startdt')).toBe(
        '2026-08-06T16:30:00.000Z'
      );
      expect(parsed.searchParams.get('enddt')).toBe('2026-08-06T17:00:00.000Z');
      expect(parsed.searchParams.has('subject')).toBe(false);
      expect(parsed.searchParams.has('location')).toBe(false);
      expect(parsed.searchParams.has('body')).toBe(false);
      expect(parsed.searchParams.has('attendees')).toBe(false);
    });
  });

  describe('openCalendarComposeWindow', () => {
    it('opens the compose URL built from the proposal start/end', () => {
      openCalendarComposeWindow(PROPOSAL);

      expect(officeService.openUrl).toHaveBeenCalledWith(
        buildCalendarComposeUrl(
          new Date('2026-08-06T16:30:00Z'),
          new Date('2026-08-06T17:00:00Z')
        )
      );
    });
  });
});
