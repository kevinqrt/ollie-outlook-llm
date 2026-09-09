import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getPipelineSettings, getSavedPrompts } from '../api/generated';
import {
  fetchPipelineSettings,
  listSavedPrompts,
} from './pipelineSettingsWorkflow';

vi.mock('../api/generated', () => ({
  getPipelineSettings: vi.fn(),
  getSavedPrompts: vi.fn(),
  postSavedPrompt: vi.fn(),
  putPipelineSettings: vi.fn(),
  putSavedPrompt: vi.fn(),
  deleteSavedPrompt: vi.fn(),
}));

describe('pipelineSettingsWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchPipelineSettings', () => {
    it('returns the settings on success', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getPipelineSettings).mockResolvedValue({
        data: { prompt: 'Custom prompt', allowClarifyingQuestions: true },
        error: null,
      });

      await expect(fetchPipelineSettings()).resolves.toEqual({
        prompt: 'Custom prompt',
        allowClarifyingQuestions: true,
      });
    });

    it('throws a readable error for an API error response', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getPipelineSettings).mockResolvedValue({
        data: undefined,
        error: { detail: 'Settings service unavailable' },
      });

      await expect(fetchPipelineSettings()).rejects.toThrow(
        'Settings service unavailable'
      );
    });
  });

  describe('listSavedPrompts', () => {
    it('returns the prompt list on success', async () => {
      const prompts = [
        { id: 'default', text: 'Standard-Prompt', isDefault: true },
      ];
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getSavedPrompts).mockResolvedValue({
        data: { prompts },
        error: null,
      });

      await expect(listSavedPrompts()).resolves.toEqual(prompts);
    });

    it('surfaces the underlying message for a network/fetch failure', async () => {
      // A network failure (backend unreachable, CORS, ...) resolves with a raw
      // Error instance as `error`, not a parsed {detail} API error body -
      // regression test for the case where this used to throw a useless "{}".
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getSavedPrompts).mockResolvedValue({
        data: undefined,
        error: new TypeError('Failed to fetch'),
      });

      await expect(listSavedPrompts()).rejects.toThrow('Failed to fetch');
    });

    it('surfaces the HTTP status for a non-2xx response with an empty body', async () => {
      // The generated SDK normalizes an empty error body into a plain "{}"
      // object (e.g. the dev proxy answering with an empty 502 for an
      // unreachable backend) - regression test for the case where this used
      // to throw a useless "{}" instead of anything actionable.
      // @ts-expect-error - mocked response omits the SDK's request metadata
      vi.mocked(getSavedPrompts).mockResolvedValue({
        data: undefined,
        error: {},
        response: { status: 502 } as Response,
      });

      await expect(listSavedPrompts()).rejects.toThrow('HTTP 502');
    });

    it('falls back to a generic message with no status and no usable error', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getSavedPrompts).mockResolvedValue({
        data: undefined,
        error: {},
      });

      await expect(listSavedPrompts()).rejects.toThrow(
        'Server nicht erreichbar'
      );
    });
  });
});
