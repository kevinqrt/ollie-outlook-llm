import createClient from 'openapi-fetch'

import type { paths } from './generated/schema'

export const OLLIE_API_BASE_URL = 'http://127.0.0.1:8000'

export const ollieApiClient = createClient<paths>({
  baseUrl: OLLIE_API_BASE_URL,
})
