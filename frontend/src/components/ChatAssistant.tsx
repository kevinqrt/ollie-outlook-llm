import { useCallback, useEffect, useRef, useState } from 'react';
import { postChat, type ValidationError } from '../api/generated';
import { useNotification } from '../context/NotificationContext';
import './ChatAssistant.css';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
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

  const handleClearChat = () => {
    localStorage.removeItem(STORAGE_KEY);
    setMessages(() => []);
  };

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
      const response = await postChat({
        body: {
          messages: newMessages.map(({ role, content }) => ({ role, content })),
        },
      });

      if (response.error) {
        let errorDetail = 'Ein unbekannter Fehler ist aufgetreten.';
        const err = response.error as { detail?: string | ValidationError[] };

        if (typeof err.detail === 'string') {
          errorDetail = err.detail;
        } else if (Array.isArray(err.detail)) {
          errorDetail = err.detail
            .map((d: ValidationError) => d.msg)
            .join(', ');
        }

        notify(`Fehler: ${errorDetail}`, 'error');
      } else if (response.data) {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: response.data?.reply || '',
          },
        ]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      notify(
        'Verbindung zum Server fehlgeschlagen. Bitte prüfe, ob das Backend läuft.',
        'error'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-assistant">
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
