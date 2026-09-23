import { useEffect, useState } from 'react';
import type { StyleRuleSchema } from '../api/generated';
import { useNotification } from '../context/NotificationContext';
import {
  clearStyleRules,
  deleteStyleRule,
  fetchStyleRules,
  setStyleLearningEnabled,
} from '../services/styleRulesWorkflow';
import './StyleRules.css';

interface StyleRulesProps {
  onBack: () => void;
}

/**
 * Übersicht der aus Nutzerkorrekturen gelernten Stilregeln: einzeln löschbar,
 * komplett löschbar und das Lernen lässt sich ganz abschalten. So behält der
 * Nutzer die Kontrolle darüber, was Ollie sich merkt.
 */
export function StyleRules({ onBack }: StyleRulesProps) {
  const [rules, setRules] = useState<StyleRuleSchema[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmingClear, setConfirmingClear] = useState(false);
  const { notify } = useNotification();

  function loadRules() {
    setLoading(true);
    setLoadError(null);
    fetchStyleRules()
      .then((data) => {
        setRules(data.rules);
        setEnabled(data.enabled);
      })
      .catch((error) => {
        const msg =
          error instanceof Error
            ? error.message
            : 'Stilregeln konnten nicht geladen werden.';
        setLoadError(msg);
        console.error('Load style rules error:', error);
      })
      .finally(() => setLoading(false));
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: loadRules only reads stable setters
  useEffect(() => {
    loadRules();
  }, []);

  async function run(action: () => Promise<void>, fallbackMessage: string) {
    if (busy) return;
    setBusy(true);
    try {
      await action();
    } catch (error) {
      const msg = error instanceof Error ? error.message : fallbackMessage;
      notify(msg, 'error');
      console.error('Style rules error:', error);
    } finally {
      setBusy(false);
    }
  }

  function handleToggle(next: boolean) {
    run(async () => {
      const updated = await setStyleLearningEnabled(next);
      setEnabled(updated.enabled);
    }, 'Einstellung konnte nicht gespeichert werden.');
  }

  function handleDelete(id: string) {
    run(async () => {
      await deleteStyleRule(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
    }, 'Löschen fehlgeschlagen.');
  }

  function handleClear() {
    run(async () => {
      await clearStyleRules();
      setRules([]);
      setConfirmingClear(false);
    }, 'Löschen fehlgeschlagen.');
  }

  return (
    <div className="style-rules">
      <div className="style-rules-header">
        <button type="button" className="text-button" onClick={onBack}>
          ← Zurück
        </button>
      </div>

      <label className="pipeline-settings-toggle-row">
        <input
          type="checkbox"
          checked={enabled}
          disabled={busy || loading || loadError !== null}
          onChange={(e) => handleToggle(e.target.checked)}
        />
        Aus Korrekturen lernen
      </label>
      <p className="description">
        Ollie merkt sich nur kurze Stilregeln, nie den Text deiner E-Mails oder
        Antworten.
      </p>

      {loading && <p className="description">Lade Stilregeln...</p>}

      {!loading && loadError && (
        <div className="style-rules-error">
          <p>Stilregeln konnten nicht geladen werden: {loadError}</p>
          <button
            type="button"
            className="secondary-button"
            onClick={loadRules}
          >
            Erneut versuchen
          </button>
        </div>
      )}

      {!loading && !loadError && rules.length === 0 && (
        <p className="description">Noch keine Stilregeln gelernt.</p>
      )}

      <ul className="style-rules-list">
        {rules.map((rule) => (
          <li key={rule.id} className="style-rule" data-inactive={!enabled}>
            <span className="style-rule-text">{rule.text}</span>
            <button
              type="button"
              className="style-rule-delete-button"
              aria-label="Regel löschen"
              disabled={busy}
              onClick={() => handleDelete(rule.id)}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>

      {rules.length > 0 &&
        (confirmingClear ? (
          <div className="style-rules-confirm">
            <span>Alle gelernten Regeln wirklich für immer löschen?</span>
            <div className="style-rules-confirm-actions">
              <button
                type="button"
                className="style-rules-confirm-delete-button"
                disabled={busy}
                onClick={handleClear}
              >
                {busy ? 'Lösche...' : 'Alle löschen'}
              </button>
              <button
                type="button"
                className="text-button"
                disabled={busy}
                onClick={() => setConfirmingClear(false)}
              >
                Abbrechen
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => setConfirmingClear(true)}
          >
            Alle Regeln löschen
          </button>
        ))}
    </div>
  );
}
