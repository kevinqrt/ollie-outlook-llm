import { useEffect, useState } from 'react';
import type { SavedPromptSchema } from '../api/generated';
import { useNotification } from '../context/NotificationContext';
import {
  createSavedPrompt,
  deleteSavedPrompt,
  listSavedPrompts,
  updateSavedPrompt,
} from '../services/pipelineSettingsWorkflow';
import './PromptLibrary.css';

interface Draft {
  localId: string;
  text: string;
}

interface PromptLibraryProps {
  onSelect: (text: string) => void;
  onBack: () => void;
}

/**
 * Dritte Ebene der Pipeline-Einstellungen: eine kleine Bibliothek
 * wiederverwendbarer Prompt-Vorlagen. Ein Klick auf eine gespeicherte
 * Vorlage übernimmt sie in das Prompt-Feld der Einstellungsebene und kehrt
 * dorthin zurück; der Stift-Button daneben schaltet nur die Bearbeitung
 * dieser einen Vorlage frei, ohne sie auszuwählen.
 */
export function PromptLibrary({ onSelect, onBack }: PromptLibraryProps) {
  const [prompts, setPrompts] = useState<SavedPromptSchema[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState('');
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(
    null
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const { notify } = useNotification();

  function loadPrompts() {
    setLoading(true);
    setLoadError(null);
    listSavedPrompts()
      .then(setPrompts)
      .catch((error) => {
        const msg =
          error instanceof Error
            ? error.message
            : 'Prompts konnten nicht geladen werden.';
        setLoadError(msg);
        notify(`Prompts konnten nicht geladen werden: ${msg}`, 'error');
        console.error('Load prompts error:', error);
      })
      .finally(() => setLoading(false));
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: loadPrompts only reads stable setters
  useEffect(() => {
    loadPrompts();
  }, []);

  function handleAddDraft() {
    const localId = crypto.randomUUID();
    setDrafts((prev) => [...prev, { localId, text: '' }]);
    setEditingId(localId);
    setEditingText('');
  }

  function handleDiscardDraft(localId: string) {
    setDrafts((prev) => prev.filter((d) => d.localId !== localId));
    if (editingId === localId) {
      setEditingId(null);
      setEditingText('');
    }
  }

  function handleStartEdit(id: string, currentText: string) {
    setEditingId(id);
    setEditingText(currentText);
  }

  async function handleSaveEdit(id: string, isDraft: boolean) {
    const text = editingText.trim();
    if (!text || saving) return;
    setSaving(true);
    try {
      if (isDraft) {
        const created = await createSavedPrompt(text);
        setPrompts((prev) => [...prev, created]);
        setDrafts((prev) => prev.filter((d) => d.localId !== id));
      } else {
        const updated = await updateSavedPrompt(id, text);
        setPrompts((prev) => prev.map((p) => (p.id === id ? updated : p)));
      }
      setEditingId(null);
      setEditingText('');
    } catch (error) {
      const msg =
        error instanceof Error ? error.message : 'Speichern fehlgeschlagen.';
      notify(msg, 'error');
      console.error('Save prompt error:', error);
    } finally {
      setSaving(false);
    }
  }

  function handleRequestDelete(id: string) {
    if (editingId === id) {
      setEditingId(null);
      setEditingText('');
    }
    setConfirmingDeleteId(id);
  }

  function handleCancelDelete() {
    setConfirmingDeleteId(null);
  }

  async function handleConfirmDelete(id: string) {
    if (deletingId) return;
    setDeletingId(id);
    try {
      await deleteSavedPrompt(id);
      setPrompts((prev) => prev.filter((p) => p.id !== id));
      setConfirmingDeleteId(null);
    } catch (error) {
      const msg =
        error instanceof Error ? error.message : 'Löschen fehlgeschlagen.';
      notify(msg, 'error');
      console.error('Delete prompt error:', error);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="prompt-library">
      <div className="prompt-library-header">
        <button type="button" className="text-button" onClick={onBack}>
          ← Zurück
        </button>
        <button
          type="button"
          className="icon-button"
          aria-label="Prompt hinzufügen"
          onClick={handleAddDraft}
        >
          +
        </button>
      </div>

      {loading && <p className="description">Lade Prompts...</p>}

      {!loading && loadError && (
        <div className="prompt-library-error">
          <p>Prompts konnten nicht geladen werden: {loadError}</p>
          <button
            type="button"
            className="secondary-button"
            onClick={loadPrompts}
          >
            Erneut versuchen
          </button>
        </div>
      )}

      <div className="prompt-library-list">
        {prompts.map((p) => {
          const isEditing = editingId === p.id;
          const isConfirmingDelete = confirmingDeleteId === p.id;
          return (
            <div key={p.id} className="prompt-entry">
              {p.isDefault ? (
                <span className="prompt-entry-badge">Standard</span>
              ) : (
                <>
                  <button
                    type="button"
                    className="prompt-entry-delete-button"
                    aria-label="Prompt löschen"
                    title="Prompt löschen"
                    disabled={deletingId !== null}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRequestDelete(p.id);
                    }}
                  >
                    🗑
                  </button>
                  <button
                    type="button"
                    className={`prompt-entry-edit-button ${isEditing ? 'is-saving' : ''}`}
                    aria-label={isEditing ? 'Speichern' : 'Bearbeiten'}
                    title={isEditing ? 'Speichern' : 'Bearbeiten'}
                    disabled={saving && !isEditing}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isEditing) {
                        handleSaveEdit(p.id, false);
                      } else {
                        handleStartEdit(p.id, p.text);
                      }
                    }}
                  >
                    {isEditing ? '✓' : '✎'}
                  </button>
                </>
              )}
              {isConfirmingDelete ? (
                <div className="prompt-entry-confirm">
                  <span>Diesen Prompt wirklich für immer löschen?</span>
                  <div className="prompt-entry-confirm-actions">
                    <button
                      type="button"
                      className="prompt-entry-confirm-delete-button"
                      disabled={deletingId !== null}
                      onClick={() => handleConfirmDelete(p.id)}
                    >
                      {deletingId === p.id ? 'Lösche...' : 'Löschen'}
                    </button>
                    <button
                      type="button"
                      className="text-button"
                      disabled={deletingId !== null}
                      onClick={handleCancelDelete}
                    >
                      Abbrechen
                    </button>
                  </div>
                </div>
              ) : (
                <textarea
                  className="prompt-entry-textarea"
                  readOnly={!isEditing}
                  value={isEditing ? editingText : p.text}
                  onChange={(e) => isEditing && setEditingText(e.target.value)}
                  onClick={() => {
                    if (!isEditing) onSelect(p.text);
                  }}
                />
              )}
            </div>
          );
        })}

        {drafts.map((d) => (
          <div key={d.localId} className="prompt-entry">
            <button
              type="button"
              className="prompt-entry-delete-button"
              aria-label="Entwurf verwerfen"
              title="Entwurf verwerfen"
              disabled={saving}
              onClick={(e) => {
                e.stopPropagation();
                handleDiscardDraft(d.localId);
              }}
            >
              🗑
            </button>
            <button
              type="button"
              className="prompt-entry-edit-button is-saving"
              aria-label="Speichern"
              title="Speichern"
              disabled={saving}
              onClick={(e) => {
                e.stopPropagation();
                handleSaveEdit(d.localId, true);
              }}
            >
              ✓
            </button>
            <textarea
              className="prompt-entry-textarea"
              value={editingId === d.localId ? editingText : d.text}
              placeholder="Neuer Prompt..."
              onChange={(e) => setEditingText(e.target.value)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
