import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  KnownCalendarSchema,
  MeetingProposalSchema,
} from '../api/generated';
import { useNotification } from '../context/NotificationContext';
import {
  addKnownCalendar,
  type CalendarConnection,
  checkIcsCalendarStatus,
  connectGraphCalendar,
  createCalendarEventFromProposal,
  getCalendarConnection,
  listKnownCalendars,
  openCalendarComposeWindow,
  removeKnownCalendar,
  setSelfIcsUrl,
} from '../services/calendarWorkflow';
import { sendChatMessage } from '../services/chatWorkflow';
import { officeService } from '../services/officeService';
import './ChatAssistant.css';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  meetingProposal?: MeetingProposalSchema | null;
  /** Set once the proposal was created in the calendar (Graph only). */
  createdEvent?: { webLink?: string | null } | null;
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
  const [calendarConnection, setCalendarConnection] =
    useState<CalendarConnection | null>(null);
  const [connectingCalendar, setConnectingCalendar] = useState(false);
  const [creatingEventFor, setCreatingEventFor] = useState<string | null>(null);
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
    const loadIcsSettings = () => {
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
    };
    getCalendarConnection()
      .then((connection) => {
        setCalendarConnection(connection);
        if (connection.backend === 'ics') loadIcsSettings();
      })
      .catch(() => {
        setCalendarConnection({ backend: 'ics', authenticated: false });
        loadIcsSettings();
      });
  }, []);

  const isGraphCalendar = calendarConnection?.backend === 'graph';

  const handleConnectCalendar = useCallback(async () => {
    setConnectingCalendar(true);
    try {
      await connectGraphCalendar();
      const connection = await getCalendarConnection();
      setCalendarConnection(connection);
      notify(
        connection.authenticated
          ? 'Outlook-Kalender verbunden.'
          : 'Kalender wurde nicht verbunden.',
        connection.authenticated ? 'success' : 'error'
      );
    } catch (error) {
      const msg =
        error instanceof Error ? error.message : 'Verbinden fehlgeschlagen.';
      notify(msg, 'error');
      console.error('Connect calendar error:', error);
    } finally {
      setConnectingCalendar(false);
    }
  }, [notify]);

  const handleCreateEvent = useCallback(
    async (messageId: string, proposal: MeetingProposalSchema) => {
      setCreatingEventFor(messageId);
      try {
        const event = await createCalendarEventFromProposal(proposal);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId
              ? { ...m, createdEvent: { webLink: event.webLink } }
              : m
          )
        );
        notify('Termin im Kalender eingetragen.', 'success');
      } catch (error) {
        const msg =
          error instanceof Error
            ? error.message
            : 'Termin konnte nicht eingetragen werden.';
        notify(msg, 'error');
        console.error('Create calendar event error:', error);
      } finally {
        setCreatingEventFor(null);
      }
    },
    [notify]
  );

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
    async (proposal: MeetingProposalSchema) => {
      try {
        await openCalendarComposeWindow(proposal);
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
      {isGraphCalendar ? (
        <div className="calendar-status-bar">
          {calendarConnection?.authenticated ? (
            <span className="calendar-status-text">
              📅✉️ Outlook verbunden (Kalender & Mails)
            </span>
          ) : (
            <>
              <span className="calendar-status-text">
                📅✉️ Outlook nicht verbunden
              </span>
              <button
                type="button"
                className="text-button"
                onClick={handleConnectCalendar}
                disabled={connectingCalendar}
              >
                {connectingCalendar ? 'Verbinde...' : 'Verbinden'}
              </button>
            </>
          )}
        </div>
      ) : (
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
      )}

      {!isGraphCalendar && settingsOpen && (
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
            {msg.meetingProposal && isGraphCalendar && (
              <MeetingProposalActions
                proposal={msg.meetingProposal}
                createdEvent={msg.createdEvent}
                creating={creatingEventFor === msg.id}
                onCreate={() =>
                  handleCreateEvent(
                    msg.id,
                    msg.meetingProposal as MeetingProposalSchema
                  )
                }
                onOpen={() =>
                  handleOpenAppointment(
                    msg.meetingProposal as MeetingProposalSchema
                  )
                }
              />
            )}
            {msg.meetingProposal && !isGraphCalendar && (
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

interface MeetingProposalActionsProps {
  proposal: MeetingProposalSchema;
  createdEvent?: { webLink?: string | null } | null;
  creating: boolean;
  onCreate: () => void;
  onOpen: () => void;
}

/**
 * Confirm-before-create actions for a proposal on the Graph backend: the
 * event is only created on an explicit click, and the label says when
 * attendees will get a real invitation.
 */
function MeetingProposalActions({
  proposal,
  createdEvent,
  creating,
  onCreate,
  onOpen,
}: MeetingProposalActionsProps) {
  if (createdEvent) {
    const { webLink } = createdEvent;
    return (
      <div className="meeting-proposal-actions">
        <span className="meeting-proposal-done">✓ Im Kalender eingetragen</span>
        {webLink && (
          <button
            type="button"
            className="text-button"
            onClick={() => officeService.openUrl(webLink)}
          >
            In Outlook öffnen
          </button>
        )}
      </div>
    );
  }

  const attendees = proposal.attendees ?? [];
  const createLabel = attendees.length
    ? `📅 Eintragen & Einladung an ${attendees.join(', ')} senden`
    : '📅 Im Kalender eintragen';
  return (
    <div className="meeting-proposal-actions">
      <button
        type="button"
        className="meeting-proposal-button"
        onClick={onCreate}
        disabled={creating}
      >
        {creating ? 'Trage ein...' : createLabel}
      </button>
      <button type="button" className="text-button" onClick={onOpen}>
        Vorher bearbeiten
      </button>
    </div>
  );
}
