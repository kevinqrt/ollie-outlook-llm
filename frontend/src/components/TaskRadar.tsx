import { useCallback, useEffect, useState } from 'react';
import { getEmailActionSummary } from '../api/generated';
import type { EmailActionResponseSchema } from '../api/generated';
import { useNotification } from '../context/NotificationContext';
import {
  fetchUnreadMessages,
  type UnreadMessage,
} from '../services/graphService';
import './TaskRadar.css';

interface RadarItem {
  id: string;
  subject: string;
  from: string;
  webLink: string;
  category: EmailActionResponseSchema['category'];
  actionType: EmailActionResponseSchema['actionType'];
  actionSummary: string | null;
  link: string | null;
  meeting: EmailActionResponseSchema['meeting'];
  done: boolean;
}

const STORAGE_KEY = 'ollie_task_radar';

function loadStoredItems(): RadarItem[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? (JSON.parse(saved) as RadarItem[]) : [];
  } catch (_e) {
    return [];
  }
}

function toRadarItem(
  msg: UnreadMessage,
  data: EmailActionResponseSchema
): RadarItem {
  const linkIndex = data.linkIndex;
  return {
    id: msg.id,
    subject: msg.subject,
    from: msg.from,
    webLink: msg.webLink,
    category: data.category,
    actionType: data.actionType ?? null,
    actionSummary: data.actionSummary ?? null,
    link: linkIndex != null ? (msg.links[linkIndex] ?? null) : null,
    meeting: data.meeting ?? null,
    done: false,
  };
}

function openMail(item: RadarItem) {
  if (item.webLink) {
    window.open(item.webLink, '_blank', 'noopener');
  }
}

function createAppointment(item: RadarItem) {
  if (typeof Office === 'undefined') return;
  const proposedTime = item.meeting?.proposedTime;
  const bodyLines = [
    item.actionSummary,
    proposedTime ? `Vorschlag laut Mail: ${proposedTime}` : null,
  ].filter(Boolean);

  Office.context.mailbox.displayNewAppointmentForm({
    subject: item.meeting?.subject || item.subject,
    body: bodyLines.join('\n'),
    ...(item.meeting?.attendees?.length
      ? { requiredAttendees: item.meeting.attendees }
      : {}),
  });
}

function ActionButton({ item }: { item: RadarItem }) {
  switch (item.actionType) {
    case 'meeting':
      return (
        <button
          type="button"
          className="radar-action-btn"
          onClick={() => createAppointment(item)}
        >
          Termin anlegen
        </button>
      );
    case 'confirm_link':
      if (!item.link) return null;
      return (
        <a
          className="radar-action-btn"
          href={item.link}
          target="_blank"
          rel="noopener noreferrer"
        >
          Link öffnen
        </a>
      );
    case 'reply_needed':
      return (
        <button
          type="button"
          className="radar-action-btn"
          onClick={() => openMail(item)}
        >
          Antwort verfassen
        </button>
      );
    case 'document':
      return (
        <button
          type="button"
          className="radar-action-btn"
          onClick={() => openMail(item)}
        >
          Dokument öffnen
        </button>
      );
    default:
      return (
        <button
          type="button"
          className="radar-action-btn"
          onClick={() => openMail(item)}
        >
          Mail öffnen
        </button>
      );
  }
}

function RadarCard({
  item,
  onToggleDone,
}: {
  item: RadarItem;
  onToggleDone: (id: string) => void;
}) {
  return (
    <div className={`radar-card ${item.category} ${item.done ? 'done' : ''}`}>
      <label className="radar-done">
        <input
          type="checkbox"
          checked={item.done}
          onChange={() => onToggleDone(item.id)}
        />
      </label>
      <div className="radar-card-body">
        <p className="radar-summary">{item.actionSummary || item.subject}</p>
        <p className="radar-meta">
          {item.from} · {item.subject}
        </p>
      </div>
      <div className="radar-card-actions">
        {item.category === 'action' && !item.done && (
          <ActionButton item={item} />
        )}
        <button
          type="button"
          className="radar-link-btn"
          onClick={() => openMail(item)}
        >
          Mail öffnen
        </button>
      </div>
    </div>
  );
}

export function TaskRadar() {
  const [items, setItems] = useState<RadarItem[]>(loadStoredItems);
  const [isScanning, setIsScanning] = useState(false);
  const [progress, setProgress] = useState<{
    done: number;
    total: number;
  } | null>(null);
  const { notify } = useNotification();

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      console.error('Failed to save task radar', e);
    }
  }, [items]);

  const handleScan = useCallback(async () => {
    setIsScanning(true);
    setProgress(null);
    try {
      const messages = await fetchUnreadMessages();
      const existingIds = new Set(items.map((i) => i.id));
      const newMessages = messages.filter((m) => !existingIds.has(m.id));
      setProgress({ done: 0, total: newMessages.length });

      const results: RadarItem[] = [];
      for (const msg of newMessages) {
        try {
          const { data } = await getEmailActionSummary({
            body: {
              emailContent: msg.bodyText || '(kein Textinhalt)',
              emailLinks: msg.links,
              sender: msg.from,
              subject: msg.subject,
            },
          });
          if (data) {
            results.push(toRadarItem(msg, data));
          }
        } catch (err) {
          console.error('Klassifikation fehlgeschlagen für Mail', msg.id, err);
        } finally {
          setProgress((p) => (p ? { ...p, done: p.done + 1 } : p));
        }
      }

      setItems((prev) => [...results, ...prev]);
      notify(
        `${messages.length} ungelesene Mails gescannt, ${results.length} neu eingeordnet.`,
        'success'
      );
    } catch (error) {
      console.error('Scan error:', error);
      notify(
        error instanceof Error
          ? `Fehler: ${error.message}`
          : 'Scan fehlgeschlagen.',
        'error'
      );
    } finally {
      setIsScanning(false);
      setProgress(null);
    }
  }, [items, notify]);

  const toggleDone = (id: string) => {
    setItems((prev) =>
      prev.map((i) => (i.id === id ? { ...i, done: !i.done } : i))
    );
  };

  const actionItems = items.filter((i) => i.category === 'action' && !i.done);
  const restItems = items.filter((i) => i.category !== 'action' || i.done);

  return (
    <div className="task-radar">
      <button
        type="button"
        className="primary-button"
        onClick={handleScan}
        disabled={isScanning}
      >
        {isScanning
          ? progress
            ? `Scanne ${progress.done}/${progress.total}...`
            : 'Postfach wird gelesen...'
          : 'Postfach scannen'}
      </button>

      {actionItems.length === 0 && !isScanning && (
        <p className="description">
          Keine offenen Handlungen. Klicke auf „Postfach scannen", um ungelesene
          Mails einzuordnen.
        </p>
      )}

      <div className="radar-list">
        {actionItems.map((item) => (
          <RadarCard key={item.id} item={item} onToggleDone={toggleDone} />
        ))}
      </div>

      {restItems.length > 0 && (
        <details className="radar-rest">
          <summary>Zum Überfliegen ({restItems.length})</summary>
          <div className="radar-list">
            {restItems.map((item) => (
              <RadarCard key={item.id} item={item} onToggleDone={toggleDone} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
