import {
  createContext,
  type ReactNode,
  use,
  useCallback,
  useRef,
  useState,
} from 'react';

export type NotificationType = 'success' | 'error' | 'info';

export interface Notification {
  id: string;
  message: string;
  type: NotificationType;
  duration?: number;
}

interface NotificationContextType {
  notify: (
    message: string,
    type?: NotificationType,
    duration?: number
  ) => string;
  removeNotification: (id: string) => void;
  notifications: Notification[];
}

const NotificationContext = createContext<NotificationContextType | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const timersRef = useRef<Record<string, number>>({});

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    if (timersRef.current[id]) {
      window.clearTimeout(timersRef.current[id]);
      delete timersRef.current[id];
    }
  }, []);

  const notify = useCallback(
    (message: string, type: NotificationType = 'info', duration = 5000) => {
      const id =
        typeof crypto !== 'undefined' && crypto.randomUUID
          ? crypto.randomUUID()
          : Math.random().toString(36).substring(2, 9);

      setNotifications((prev) => {
        if (duration === 0) {
          const exists = prev.find(
            (n) => n.message === message && n.type === 'info'
          );
          if (exists) return prev;
        }
        return [...prev, { id, message, type, duration }];
      });

      if (duration > 0) {
        timersRef.current[id] = window.setTimeout(() => {
          removeNotification(id);
        }, duration);
      }

      return id;
    },
    [removeNotification]
  );

  return (
    <NotificationContext.Provider
      value={{ notify, removeNotification, notifications }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const context = use(NotificationContext);
  if (!context) {
    throw new Error(
      'useNotification must be used within a NotificationProvider'
    );
  }
  return context;
}
