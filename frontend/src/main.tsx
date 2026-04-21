import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';

/* global Office */

Office.onReady(() => {
  const container = document.getElementById('root');
  if (container) {
    createRoot(container).render(
      <StrictMode>
        <App />
      </StrictMode>
    );
  }
});
