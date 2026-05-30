import type React from 'react';
import { useEffect } from 'react';
import './StatusPopup.css';

export type StatusType = 'success' | 'error' | 'info';

interface StatusPopupProps {
  message: string;
  type: StatusType;
  duration?: number;
  onClose: () => void;
}

export const StatusPopup: React.FC<StatusPopupProps> = ({
  message,
  type,
  duration = 5000,
  onClose,
}) => {
  useEffect(() => {
    // Only set timer if duration is greater than 0
    if (duration > 0) {
      const timer = setTimeout(() => {
        onClose();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'info':
        return '⏳';
      default:
        return 'ℹ️';
    }
  };

  return (
    <div className={`status-popup-container ${type}`} role="alert">
      <span className="status-popup-icon">{getIcon()}</span>
      <span className="status-popup-message">{message}</span>
      <button
        type="button"
        className="status-popup-close"
        onClick={onClose}
        aria-label="Schließen"
      >
        ✕
      </button>
    </div>
  );
};
