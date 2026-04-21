import createClient from 'openapi-fetch';

import type { paths } from './generated/schema';

// Vite picks up VITE_BASE_API_URL from .env in root
export const OLLIE_API_BASE_URL = import.meta.env.VITE_BASE_API_URL;
export const ollieApiClient = createClient<paths>({
  baseUrl: OLLIE_API_BASE_URL,
});
