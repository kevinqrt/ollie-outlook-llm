import { createPortal } from 'react-dom';
import { StatusPopup } from '../components/StatusPopup';
import { useNotification } from './NotificationContext';

export function NotificationContainer() {
  const { notifications, removeNotification } = useNotification();

  if (notifications.length === 0) return null;

  return createPortal(
    <div className="notification-container-fixed">
      {notifications.map((notification) => (
        <StatusPopup
          key={notification.id}
          message={notification.message}
          type={notification.type}
          duration={0} // Managed by the context
          onClose={() => removeNotification(notification.id)}
        />
      ))}
    </div>,
    document.body
  );
}
