import { client } from './generated/client.gen';

export const OLLIE_API_BASE_URL = import.meta.env.VITE_BASE_API_URL;

// Initial configuration of the base client
client.setConfig({
  baseUrl: OLLIE_API_BASE_URL,
});

export { client as backendApiClient };
