import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  deleteAllStyleRules,
  deleteStyleRule as deleteStyleRuleApi,
  getStyleRules,
  postCorrection,
  putStyleRulesSettings,
} from '../api/generated';
import {
  clearStyleRules,
  deleteStyleRule,
  fetchStyleRules,
  setStyleLearningEnabled,
  submitCorrection,
} from './styleRulesWorkflow';

vi.mock('../api/generated', () => ({
  getStyleRules: vi.fn(),
  putStyleRulesSettings: vi.fn(),
  postCorrection: vi.fn(),
  deleteStyleRule: vi.fn(),
  deleteAllStyleRules: vi.fn(),
}));

describe('styleRulesWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchStyleRules', () => {
    it('returns the rules and the enabled flag on success', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getStyleRules).mockResolvedValue({
        data: {
          enabled: true,
          rules: [{ id: '1', text: 'Duze den Empfänger.' }],
        },
        error: null,
      });

      await expect(fetchStyleRules()).resolves.toEqual({
        enabled: true,
        rules: [{ id: '1', text: 'Duze den Empfänger.' }],
      });
    });

    it('throws a readable error for an API error response', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(getStyleRules).mockResolvedValue({
        data: undefined,
        error: { detail: 'Store kaputt' },
      });

      await expect(fetchStyleRules()).rejects.toThrow('Store kaputt');
    });
  });

  describe('setStyleLearningEnabled', () => {
    it('sends the flag and returns the updated state', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(putStyleRulesSettings).mockResolvedValue({
        data: { enabled: false, rules: [] },
        error: null,
      });

      const result = await setStyleLearningEnabled(false);

      expect(putStyleRulesSettings).toHaveBeenCalledWith({
        body: { enabled: false },
      });
      expect(result.enabled).toBe(false);
    });
  });

  describe('submitCorrection', () => {
    it('sends trimmed inputs and turns empty ones into null', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postCorrection).mockResolvedValue({
        data: { learned: true, rule: { id: '1', text: 'Halte dich kurz.' } },
        error: null,
      });

      const result = await submitCorrection('Antwort', '  kürzer ', '   ');

      expect(postCorrection).toHaveBeenCalledWith({
        body: {
          originalReply: 'Antwort',
          feedback: 'kürzer',
          correctedReply: null,
        },
      });
      expect(result.learned).toBe(true);
    });

    it('surfaces the backend error detail, e.g. when the LLM is unavailable', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(postCorrection).mockResolvedValue({
        data: undefined,
        error: { detail: 'DGX-Anfrage fehlgeschlagen' },
      });

      await expect(submitCorrection('Antwort', 'kürzer', '')).rejects.toThrow(
        'DGX-Anfrage fehlgeschlagen'
      );
    });
  });

  describe('deleteStyleRule', () => {
    it('calls the API with the rule id', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(deleteStyleRuleApi).mockResolvedValue({ error: undefined });

      await deleteStyleRule('abc');

      expect(deleteStyleRuleApi).toHaveBeenCalledWith({
        path: { rule_id: 'abc' },
      });
    });

    it('throws when the rule is not found', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(deleteStyleRuleApi).mockResolvedValue({
        error: { detail: 'Regel nicht gefunden.' },
      });

      await expect(deleteStyleRule('abc')).rejects.toThrow(
        'Regel nicht gefunden.'
      );
    });
  });

  describe('clearStyleRules', () => {
    it('calls the delete-all endpoint', async () => {
      // @ts-expect-error - mocked response omits the SDK's request/response metadata
      vi.mocked(deleteAllStyleRules).mockResolvedValue({ error: undefined });

      await expect(clearStyleRules()).resolves.toBeUndefined();
      expect(deleteAllStyleRules).toHaveBeenCalled();
    });
  });
});
