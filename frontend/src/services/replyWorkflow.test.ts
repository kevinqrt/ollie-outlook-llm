import { beforeEach, describe, expect, it, vi } from 'vitest';
import { postReplyRevision, streamEmailSuggestion } from '../api';
import { officeService } from './officeService';
import { reviseReply, runReplyWorkflow } from './replyWorkflow';

// Mocks
vi.mock('./officeService', () => ({
  officeService: {
    showNotification: vi.fn(),
    getBodyText: vi.fn(),
    getRecipients: vi.fn().mockResolvedValue([]),
    insertText: vi.fn(),
    replaceInsertedText: vi.fn(),
    displayReply: vi.fn(),
    isComposeMode: vi.fn(),
  },
}));

vi.mock('../api', () => ({
  streamEmailSuggestion: vi.fn(),
  postReplyRevision: vi.fn(),
}));

async function* asyncStream<T>(events: T[]): AsyncGenerator<T> {
  for (const event of events) {
    yield event;
  }
}

describe('replyWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should successfully generate and insert a suggestion in compose mode', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(true);
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([{ type: 'done', finalReply: 'Suggested reply' }]),
    } as never);

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

  it('returns the inserted reply text so the user can give feedback on it', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(true);
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([{ type: 'done', finalReply: 'Suggested reply' }]),
    } as never);

    // WHEN
    const result = await runReplyWorkflow();

    // THEN
    expect(result.finalReply).toBe('Suggested reply');
  });

  it('returns the email content so the reply can be revised later', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(true);
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([{ type: 'done', finalReply: 'Suggested reply' }]),
    } as never);

    // WHEN
    const result = await runReplyWorkflow();

    // THEN
    expect(result.emailContent).toBe('Email content');
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
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([
        { type: 'done', finalReply: 'Suggested reply', meetingProposal },
      ]),
    } as never);

    // WHEN
    const result = await runReplyWorkflow();

    // THEN
    expect(result.meetingProposal).toEqual(meetingProposal);
  });

  it('should successfully generate and display a suggestion in read mode', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(false);
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([{ type: 'done', finalReply: 'Suggested reply' }]),
    } as never);

    // WHEN
    await runReplyWorkflow();

    // THEN
    expect(officeService.displayReply).toHaveBeenCalledWith('Suggested reply');
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Abgeschlossen'
    );
  });

  it('replaces the previous reply instead of inserting again when one is passed', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(true);
    vi.mocked(officeService.replaceInsertedText).mockResolvedValue('replaced');
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([{ type: 'done', finalReply: 'Neue Antwort' }]),
    } as never);

    // WHEN
    await runReplyWorkflow(undefined, undefined, 'Alte Antwort');

    // THEN
    expect(officeService.replaceInsertedText).toHaveBeenCalledWith(
      'Neue Antwort'
    );
    expect(officeService.insertText).not.toHaveBeenCalled();
  });

  it('reports progress events to the onProgress callback', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(officeService.isComposeMode).mockReturnValue(true);
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([
        { type: 'plan_ready', steps: ['Schritt 1'] },
        { type: 'step_started', index: 0, label: 'Schritt 1' },
        { type: 'step_completed', index: 0, label: 'Schritt 1', result: 'ok' },
        { type: 'done', finalReply: 'Suggested reply' },
      ]),
    } as never);
    const onProgress = vi.fn();

    // WHEN
    await runReplyWorkflow(onProgress);

    // THEN
    expect(onProgress).toHaveBeenCalledTimes(4);
  });

  it('should handle a pipeline error event correctly', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([{ type: 'error', detail: 'Service Unavailable' }]),
    } as never);

    // WHEN / THEN
    await expect(runReplyWorkflow()).rejects.toThrow('Service Unavailable');
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Fehler aufgetreten'
    );
  });

  it('should handle missing suggestion correctly', async () => {
    // GIVEN
    vi.mocked(officeService.getBodyText).mockResolvedValue('Email content');
    vi.mocked(streamEmailSuggestion).mockResolvedValue({
      stream: asyncStream([]),
    } as never);

    // WHEN / THEN
    await expect(runReplyWorkflow()).rejects.toThrow(
      'Kein Vorschlag generiert'
    );
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Fehler aufgetreten'
    );
  });
});

describe('reviseReply', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends mail, previous reply and feedback and replaces the reply in the draft', async () => {
    // GIVEN
    vi.mocked(postReplyRevision).mockResolvedValue({
      data: { finalReply: 'Kurze Antwort' },
      error: undefined,
    } as never);
    vi.mocked(officeService.replaceInsertedText).mockResolvedValue('replaced');

    // WHEN
    const result = await reviseReply('Mail', 'Lange Antwort', 'kürzer');

    // THEN
    expect(postReplyRevision).toHaveBeenCalledWith({
      body: {
        emailContent: 'Mail',
        previousReply: 'Lange Antwort',
        feedback: 'kürzer',
      },
    });
    expect(officeService.replaceInsertedText).toHaveBeenCalledWith(
      'Kurze Antwort'
    );
    expect(result).toEqual({ reply: 'Kurze Antwort', placement: 'replaced' });
  });

  it('reports when the old reply could not be replaced', async () => {
    // GIVEN
    vi.mocked(postReplyRevision).mockResolvedValue({
      data: { finalReply: 'Kurze Antwort' },
      error: undefined,
    } as never);
    vi.mocked(officeService.replaceInsertedText).mockResolvedValue('inserted');

    // WHEN
    const result = await reviseReply('Mail', 'Lange Antwort', 'kürzer');

    // THEN
    expect(result.placement).toBe('inserted');
  });

  it('surfaces the backend error and leaves the draft untouched', async () => {
    // GIVEN
    vi.mocked(postReplyRevision).mockResolvedValue({
      data: undefined,
      error: { detail: 'DGX-Anfrage fehlgeschlagen' },
    } as never);

    // WHEN / THEN
    await expect(reviseReply('Mail', 'Antwort', 'kürzer')).rejects.toThrow(
      'DGX-Anfrage fehlgeschlagen'
    );
    expect(officeService.replaceInsertedText).not.toHaveBeenCalled();
    expect(officeService.showNotification).toHaveBeenCalledWith(
      'Fehler aufgetreten'
    );
  });
});
