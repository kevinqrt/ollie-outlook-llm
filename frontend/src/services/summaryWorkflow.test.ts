import { beforeEach, describe, expect, it, vi } from 'vitest';
import { summarizeEmailThread } from '../api';
import { officeService } from './officeService';
import { summarizeThread } from './summaryWorkflow';

vi.mock('./officeService', () => ({
  officeService: {
    getBodyText: vi.fn(),
    getThreadHeader: vi.fn().mockReturnValue(''),
  },
}));

vi.mock('../api', () => ({
  summarizeEmailThread: vi.fn(),
}));

describe('summaryWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reads the mail body and returns the summary', async () => {
    vi.mocked(officeService.getBodyText).mockResolvedValue('Thread text');
    vi.mocked(summarizeEmailThread).mockResolvedValue({
      data: { summary: 'Kurze Zusammenfassung.' },
      error: null,
    } as never);

    const result = await summarizeThread();

    expect(summarizeEmailThread).toHaveBeenCalledWith({
      body: { threadText: 'Thread text' },
    });
    expect(result).toBe('Kurze Zusammenfassung.');
  });

  it('prepends the sender/recipient header when present', async () => {
    vi.mocked(officeService.getBodyText).mockResolvedValue('Thread text');
    vi.mocked(officeService.getThreadHeader).mockReturnValue(
      'Betreff: Test\nVon: Alice <alice@example.com>\n\n'
    );
    vi.mocked(summarizeEmailThread).mockResolvedValue({
      data: { summary: 'Kurze Zusammenfassung.' },
      error: null,
    } as never);

    await summarizeThread();

    expect(summarizeEmailThread).toHaveBeenCalledWith({
      body: {
        threadText:
          'Betreff: Test\nVon: Alice <alice@example.com>\n\nThread text',
      },
    });
  });

  it('throws with the backend error detail on failure', async () => {
    vi.mocked(officeService.getBodyText).mockResolvedValue('Thread text');
    vi.mocked(summarizeEmailThread).mockResolvedValue({
      data: undefined,
      error: { detail: 'Service Unavailable' },
    } as never);

    await expect(summarizeThread()).rejects.toThrow('Service Unavailable');
  });
});
