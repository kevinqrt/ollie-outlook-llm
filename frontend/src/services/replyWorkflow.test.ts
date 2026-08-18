import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getEmailSuggestion } from '../api';
import { officeService } from './officeService';
import { runReplyWorkflow } from './replyWorkflow';

// Mocks
vi.mock('./officeService', () => ({
  officeService: {
    showNotification: vi.fn(),
    getBodyText: vi.fn(),
    getRecipients: vi.fn().mockResolvedValue([]),
    insertText: vi.fn(),
    displayReply: vi.fn(),
    isComposeMode: vi.fn(),
  },
}));

vi.mock('../api', () => ({
  getEmailSuggestion: vi.fn(),
}));

describe('replyWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should successfully generate and insert a suggestion in compose mode', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(true);
    // @ts-expect-error - mocked response omits the SDK's request/response metadata
    vi.mocked(getEmailSuggestion).mockResolvedValue({
      data: { suggestedReply: 'Suggested reply' },
      error: null,
    });

    // WHEN
    await runReplyWorkflow();

    // THEN
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Anfrage wird bearbeitet...'
    );
    expect(officeService.insertText).toHaveBeenCalledWith('Suggested reply');
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Abgeschlossen'
    );
  });

  it('returns the meeting proposal when present', async () => {
    // GIVEN
    const meetingProposal = {
      subject: 'Termin',
      body: '',
      start: '2026-08-03T09:00:00Z',
      end: '2026-08-03T09:30:00Z',
      attendees: [],
    };
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(true);
    // @ts-expect-error - mocked response omits the SDK's request/response metadata
    vi.mocked(getEmailSuggestion).mockResolvedValue({
      data: { suggestedReply: 'Suggested reply', meetingProposal },
      error: null,
    });

    // WHEN
    const result = await runReplyWorkflow();

    // THEN
    expect(result.meetingProposal).toEqual(meetingProposal);
  });

  it('should successfully generate and display a suggestion in read mode', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(false);
    // @ts-expect-error - mocked response omits the SDK's request/response metadata
    vi.mocked(getEmailSuggestion).mockResolvedValue({
      data: { suggestedReply: 'Suggested reply' },
      error: null,
    });

    // WHEN
    await runReplyWorkflow();

    // THEN
    expect(officeService.displayReply).toHaveBeenCalledWith('Suggested reply');
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Abgeschlossen'
    );
  });

  it('should handle API errors correctly', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    // @ts-expect-error - mocked response omits the SDK's request/response metadata
    vi.mocked(getEmailSuggestion).mockResolvedValue({
      data: undefined,
      error: { detail: 'Service Unavailable' },
    });

    // WHEN / THEN
    await expect(runReplyWorkflow()).rejects.toThrow();
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Fehler aufgetreten'
    );
  });

  it('should handle missing suggestion correctly', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    // @ts-expect-error - mocked response omits the SDK's request/response metadata
    vi.mocked(getEmailSuggestion).mockResolvedValue({
      data: { suggestedReply: '' },
      error: null,
    });

    // WHEN / THEN
    await expect(runReplyWorkflow()).rejects.toThrow(
      'Kein Vorschlag generiert'
    );
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Fehler aufgetreten'
    );
  });
});
