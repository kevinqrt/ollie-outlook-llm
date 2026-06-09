import { client } from './generated/client.gen';

/**
 * Die API-URL wird aus der .env Datei (VITE_BASE_API_URL) gelesen.
 * Falls keine Variable gesetzt ist, wird standardmäßig der relative Pfad '/api' genutzt.
 */
export const OLLIE_API_BASE_URL = import.meta.env.VITE_BASE_API_URL || '/api';

// Initial configuration of the base client
client.setConfig({
  baseUrl: OLLIE_API_BASE_URL,
});

export { client as backendApiClient };
