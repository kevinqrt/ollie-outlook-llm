import {
  type ChangeEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  deleteDocumentKnowledgeDocumentsFilenameDelete as deleteDocument,
  type KnowledgeDocumentSchema,
  listDocumentsKnowledgeDocumentsGet as listDocuments,
  uploadPdfKnowledgePdfPost as uploadPdf,
  type ValidationError,
} from '../api/generated';
import { useNotification } from '../context/NotificationContext';
import './KnowledgeBase.css';

/**
 * Utility to extract a readable error message from API error responses.
 */
const extractErrorMessage = (
  error: { detail?: string | ValidationError[] } | null | undefined
): string => {
  if (!error) return 'Ein unbekannter Fehler ist aufgetreten.';
  if (typeof error.detail === 'string') return error.detail;
  if (Array.isArray(error.detail)) {
    return error.detail.map((d: ValidationError) => d.msg).join(', ');
  }
  return JSON.stringify(error);
};

export function KnowledgeBase() {
  const [documents, setDocuments] = useState<KnowledgeDocumentSchema[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingFiles, setDeletingFiles] = useState<Set<string>>(new Set());
  const { notify, removeNotification } = useNotification();
  const uploadNotificationId = useRef<string | null>(null);

  const fetchDocuments = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const response = await listDocuments();
        if (response.error) {
          throw new Error(
            extractErrorMessage(
              response.error as { detail?: string | ValidationError[] }
            )
          );
        }
        setDocuments(response.data?.documents ?? []);
      } catch (err) {
        const msg =
          err instanceof Error
            ? err.message
            : 'Fehler beim Laden der Dokumente.';
        notify(msg, 'error');
        console.error('Fetch error:', err);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [notify]
  );

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleFileUpload = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;

      setUploading(true);

      if (uploadNotificationId.current) {
        removeNotification(uploadNotificationId.current);
      }

      uploadNotificationId.current = notify(
        `PDF "${file.name}" wird verarbeitet...`,
        'info',
        0
      );

      try {
        const response = await uploadPdf({
          body: {
            file: file,
          },
        });

        if (response.error) {
          throw new Error(
            extractErrorMessage(
              response.error as { detail?: string | ValidationError[] }
            )
          );
        }

        if (uploadNotificationId.current) {
          removeNotification(uploadNotificationId.current);
          uploadNotificationId.current = null;
        }

        notify(`"${file.name}" erfolgreich hinzugefügt.`, 'success');
        await fetchDocuments(true);
        event.target.value = '';
      } catch (err) {
        if (uploadNotificationId.current) {
          removeNotification(uploadNotificationId.current);
          uploadNotificationId.current = null;
        }
        const errorMsg =
          err instanceof Error ? err.message : 'Upload fehlgeschlagen';
        notify(errorMsg, 'error');
        console.error('Upload error:', err);
      } finally {
        setUploading(false);
      }
    },
    [fetchDocuments, notify, removeNotification]
  );

  const handleDelete = useCallback(
    async (filename: string) => {
      setDeletingFiles((prev) => {
        const next = new Set(prev);
        next.add(filename);
        return next;
      });

      try {
        const response = await deleteDocument({
          path: { filename },
        });

        if (response.error) {
          throw new Error(
            extractErrorMessage(
              response.error as { detail?: string | ValidationError[] }
            )
          );
        }

        notify(`"${filename}" gelöscht.`, 'success');
        await fetchDocuments(true);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unbekannter Fehler';
        notify(`Fehler: ${msg}`, 'error');
        console.error('Delete error:', err);
      } finally {
        setDeletingFiles((prev) => {
          const next = new Set(prev);
          next.delete(filename);
          return next;
        });
      }
    },
    [fetchDocuments, notify]
  );

  return (
    <div className="knowledge-base">
      <section className="upload-section">
        <h3>PDF hinzufügen</h3>
        <label
          className={`file-upload-label ${uploading ? 'disabled' : ''}`}
          title={uploading ? 'Upload läuft...' : 'Klicken um PDF hochzuladen'}
        >
          {uploading ? 'Wird verarbeitet...' : 'PDF auswählen'}
          <input
            type="file"
            accept=".pdf"
            disabled={uploading}
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />
        </label>
      </section>

      <section className="document-list-section">
        <h3>Wissensbasis Dokumente</h3>
        {loading ? (
          <p className="loading-state">Lade Dokumente...</p>
        ) : documents.length === 0 ? (
          <p className="empty-state">Noch keine PDF-Dokumente vorhanden.</p>
        ) : (
          <ul className="document-list">
            {documents.map((doc) => {
              const isDeleting = deletingFiles.has(doc.source);
              return (
                <li
                  key={doc.source}
                  className={`document-item ${isDeleting ? 'deleting' : ''}`}
                >
                  <span className="document-name" title={doc.source}>
                    {doc.source}
                  </span>
                  <button
                    type="button"
                    className="delete-button"
                    onClick={() => handleDelete(doc.source)}
                    disabled={isDeleting}
                    aria-label={`Dokument ${doc.source} löschen`}
                  >
                    {isDeleting ? '...' : '🗑️'}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
