import { beforeEach, describe, expect, it, vi } from 'vitest';
import { postChat } from '../api/generated';
import { sendChatMessage } from './chatWorkflow';

vi.mock('../api/generated', () => ({
  postChat: vi.fn(),
}));

describe('chatWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('sendChatMessage', () => {
    it('returns the reply without a meeting proposal', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postChat).mockResolvedValue({
        data: { reply: 'Hallo!' },
        error: null,
      });

      await expect(
        sendChatMessage([{ role: 'user', content: 'Hi' }])
      ).resolves.toEqual({ reply: 'Hallo!', meetingProposal: undefined });
    });

    it('returns the meeting proposal when present', async () => {
      const meetingProposal = {
        subject: 'Termin',
        body: '',
        start: '2026-08-03T09:00:00Z',
        end: '2026-08-03T09:30:00Z',
        attendees: [],
      };
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postChat).mockResolvedValue({
        data: { reply: 'Wie waere 09:00?', meetingProposal },
        error: null,
      });

      await expect(
        sendChatMessage([{ role: 'user', content: 'Termin?' }])
      ).resolves.toEqual({ reply: 'Wie waere 09:00?', meetingProposal });
    });

    it('throws a readable error when the request fails', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postChat).mockResolvedValue({
        data: undefined,
        error: { detail: 'RAG Service unavailable' },
      });

      await expect(
        sendChatMessage([{ role: 'user', content: 'Hi' }])
      ).rejects.toThrow('RAG Service unavailable');
    });
  });
});
