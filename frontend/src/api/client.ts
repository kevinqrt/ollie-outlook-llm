import { client } from './generated/client.gen';

const runtimeOrigin =
  typeof window !== 'undefined' ? window.location.origin : '';

// In the packaged desktop host, frontend and backend share one HTTPS origin.
// Use the runtime origin in production so we never keep a stale dev API URL
// like http://127.0.0.1:8000 baked into the bundle.
export const OLLIE_API_BASE_URL = import.meta.env.PROD
  ? runtimeOrigin
  : import.meta.env.VITE_BASE_API_URL || '';

// Initial configuration of the base client
client.setConfig({
  baseUrl: OLLIE_API_BASE_URL,
});

export { client as backendApiClient };
