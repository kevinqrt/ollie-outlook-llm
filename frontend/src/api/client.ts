import createClient from 'openapi-fetch';

import type { paths } from './generated/schema';

export const OLLIE_API_BASE_URL = import.meta.env.VITE_BASE_API_URL;
export const ollieApiClient = createClient<paths>({
  baseUrl: OLLIE_API_BASE_URL,
});
