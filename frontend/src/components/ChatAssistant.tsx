import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  KnownCalendarSchema,
  MeetingProposalSchema,
} from '../api/generated';
import { useNotification } from '../context/NotificationContext';
import {
  addKnownCalendar,
  checkIcsCalendarStatus,
  listKnownCalendars,
  openCalendarComposeWindow,
  removeKnownCalendar,
  setSelfIcsUrl,
} from '../services/calendarWorkflow';
import { sendChatMessage } from '../services/chatWorkflow';
import './ChatAssistant.css';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  meetingProposal?: MeetingProposalSchema | null;
}

const STORAGE_KEY = 'ollie_chat_history';

export function ChatAssistant() {
  const [messages, setMessages] = useState<Message[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      const parsed: Message[] = saved ? JSON.parse(saved) : [];
      return parsed.filter((m) => m.role !== 'error');
    } catch (_e) {
      return [];
    }
  });
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [icsConfigured, setIcsConfigured] = useState<boolean | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selfUrlInput, setSelfUrlInput] = useState('');
  const [savingSelfUrl, setSavingSelfUrl] = useState(false);
  const [knownCalendars, setKnownCalendars] = useState<KnownCalendarSchema[]>(
    []
  );
  const [newKnownEmail, setNewKnownEmail] = useState('');
  const [newKnownUrl, setNewKnownUrl] = useState('');
  const [savingKnown, setSavingKnown] = useState(false);
  const { notify } = useNotification();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch (e) {
      console.error('Failed to save chat history', e);
    }
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    checkIcsCalendarStatus()
      .then((configured) => {
        setIcsConfigured(configured);
        if (!configured) setSettingsOpen(true);
      })
      .catch(() => {
        setIcsConfigured(false);
        setSettingsOpen(true);
      });
    listKnownCalendars()
      .then(setKnownCalendars)
      .catch(() => setKnownCalendars([]));
  }, []);

  const handleClearChat = () => {
    localStorage.removeItem(STORAGE_KEY);
    setMessages(() => []);
  };

  const handleSaveSelfUrl = useCallback(async () => {
    if (!selfUrlInput.trim()) return;
    setSavingSelfUrl(true);
    try {
      await setSelfIcsUrl(selfUrlInput.trim());
      setIcsConfigured(true);
      setSelfUrlInput('');
      notify('Kalender-Link gespeichert.', 'success');
    } catch (error) {
      const msg =
        error instanceof Error ? error.message : 'Kalender-Link ungültig.';
      notify(msg, 'error');
      console.error('Set self ICS URL error:', error);
    } finally {
      setSavingSelfUrl(false);
    }
  }, [selfUrlInput, notify]);

  const handleAddKnownCalendar = useCallback(async () => {
    if (!newKnownEmail.trim() || !newKnownUrl.trim()) return;
    setSavingKnown(true);
    try {
      const updated = await addKnownCalendar(
        newKnownEmail.trim(),
        newKnownUrl.trim()
      );
      setKnownCalendars(updated);
      setNewKnownEmail('');
      setNewKnownUrl('');
      notify('Kalender hinzugefügt.', 'success');
    } catch (error) {
      const msg =
        error instanceof Error ? error.message : 'Kalender-Link ungültig.';
      notify(msg, 'error');
      console.error('Add known calendar error:', error);
    } finally {
      setSavingKnown(false);
    }
  }, [newKnownEmail, newKnownUrl, notify]);

  const handleRemoveKnownCalendar = useCallback(
    async (email: string) => {
      try {
        const updated = await removeKnownCalendar(email);
        setKnownCalendars(updated);
      } catch (error) {
        const msg =
          error instanceof Error ? error.message : 'Entfernen fehlgeschlagen.';
        notify(msg, 'error');
        console.error('Remove known calendar error:', error);
      }
    },
    [notify]
  );

  const handleOpenAppointment = useCallback(
    (proposal: MeetingProposalSchema) => {
      try {
        openCalendarComposeWindow(proposal);
      } catch (error) {
        const msg =
          error instanceof Error
            ? error.message
            : 'Kalenderfenster konnte nicht geöffnet werden.';
        notify(msg, 'error');
        console.error('Open calendar compose window error:', error);
      }
    },
    [notify]
  );

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input,
    };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    try {
      const { reply, meetingProposal } = await sendChatMessage(
        newMessages.map(({ role, content }) => ({ role, content }))
      );
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: reply,
          meetingProposal,
        },
      ]);
    } catch (error) {
      console.error('Chat error:', error);
      const msg =
        error instanceof Error
          ? error.message
          : 'Verbindung zum Server fehlgeschlagen.';
      notify(`Fehler: ${msg}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-assistant">
      <div className="calendar-status-bar">
        {icsConfigured === null ? (
          <span className="calendar-status-text">
            Kalender-Status wird geprüft...
          </span>
        ) : icsConfigured ? (
          <span className="calendar-status-text">📅 Kalender verbunden</span>
        ) : (
          <span className="calendar-status-text">
            📅 Kein Kalender-Link hinterlegt
          </span>
        )}
        <button
          type="button"
          className="text-button"
          onClick={() => setSettingsOpen((open) => !open)}
        >
          {settingsOpen ? 'Schließen' : 'Kalender-Einstellungen'}
        </button>
      </div>

      {settingsOpen && (
        <div className="calendar-settings-panel">
          <p className="calendar-settings-hint">
            Kalender-Link findest du in Outlook im Web unter Einstellungen →
            Kalender → Geteilte Kalender → „Kalender veröffentlichen" (ICS-Link
            kopieren). Hinweis: veröffentlichte Kalender können bis zu mehreren
            Stunden verzögert sein (Microsoft-seitige Aktualisierung) – für
            Wochenplanung ausreichend, nicht für minutengenaue Prüfungen.
          </p>

          <div className="calendar-settings-row">
            <input
              type="url"
              placeholder="Meine Kalender-URL (ICS)"
              value={selfUrlInput}
              onChange={(e) => setSelfUrlInput(e.target.value)}
            />
            <button
              type="button"
              className="text-button"
              onClick={handleSaveSelfUrl}
              disabled={savingSelfUrl || !selfUrlInput.trim()}
            >
              {savingSelfUrl ? 'Speichere...' : 'Speichern'}
            </button>
          </div>

          <p className="calendar-settings-subheading">
            Bekannte Kalender anderer Personen
          </p>
          <ul className="known-calendar-list">
            {knownCalendars.map((entry) => (
              <li key={entry.email}>
                <span title={entry.url}>{entry.email}</span>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => handleRemoveKnownCalendar(entry.email)}
                >
                  Entfernen
                </button>
              </li>
            ))}
            {knownCalendars.length === 0 && (
              <li className="known-calendar-empty">
                Noch keine bekannten Kalender.
              </li>
            )}
          </ul>
          <div className="calendar-settings-row">
            <input
              type="email"
              placeholder="E-Mail-Adresse"
              value={newKnownEmail}
              onChange={(e) => setNewKnownEmail(e.target.value)}
            />
            <input
              type="url"
              placeholder="Kalender-URL (ICS)"
              value={newKnownUrl}
              onChange={(e) => setNewKnownUrl(e.target.value)}
            />
            <button
              type="button"
              className="text-button"
              onClick={handleAddKnownCalendar}
              disabled={
                savingKnown || !newKnownEmail.trim() || !newKnownUrl.trim()
              }
            >
              {savingKnown ? 'Speichere...' : 'Hinzufügen'}
            </button>
          </div>
        </div>
      )}

      <div className="chat-header-actions">
        <button
          type="button"
          className="text-button"
          onClick={handleClearChat}
          disabled={messages.length === 0}
        >
          Verlauf löschen
        </button>
      </div>
      <div className="message-list">
        {messages.map((msg) => (
          <div key={msg.id} className={`message-bubble ${msg.role}`}>
            <div className="message-content">{msg.content}</div>
            {msg.meetingProposal && (
              <button
                type="button"
                className="meeting-proposal-button"
                onClick={() =>
                  handleOpenAppointment(
                    msg.meetingProposal as MeetingProposalSchema
                  )
                }
              >
                📅 Termin im Kalender öffnen
              </button>
            )}
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          rows={1}
          placeholder="Nachricht an Ollie..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <button
          type="button"
          className="send-button"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
        >
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="currentColor"
            role="img"
            aria-label="Senden"
          >
            <title>Senden</title>
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
