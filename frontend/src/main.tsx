import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { NotificationContainer } from './context/NotificationContainer';
import { NotificationProvider } from './context/NotificationContext';
import './index.css';
import App from './App.tsx';

const container = document.getElementById('root');
if (container) {
  createRoot(container).render(
    <StrictMode>
      <NotificationProvider>
        <App />
        <NotificationContainer />
      </NotificationProvider>
    </StrictMode>
  );
}
