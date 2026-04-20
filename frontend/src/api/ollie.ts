import { ollieApiClient } from './client'

export interface RequestOptions {
  signal?: AbortSignal
}

export interface HealthResponse {
  status: string
}

export interface EmailSuggestionResponse {
  suggestedReply: string
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown
  readonly response: Response

  constructor(response: Response, error: unknown) {
    super(formatApiErrorMessage(response, error))
    this.name = 'ApiError'
    this.status = response.status
    this.detail = getErrorDetail(error)
    this.response = response
  }
}

export async function getHealth(
  options: RequestOptions = {},
): Promise<HealthResponse> {
  const { data, error, response } = await ollieApiClient.GET('/health', {
    signal: options.signal,
  })

  if (error !== undefined) {
    throw new ApiError(response, error)
  }

  return { status: data.status }
}

export async function getEmailSuggestion(
  emailContent: string,
  options: RequestOptions = {},
): Promise<EmailSuggestionResponse> {
  const { data, error, response } = await ollieApiClient.POST(
    '/email/suggestion',
    {
      body: { email_content: emailContent },
      signal: options.signal,
    },
  )

  if (error !== undefined) {
    throw new ApiError(response, error)
  }

  return { suggestedReply: data.suggested_reply }
}

function formatApiErrorMessage(response: Response, error: unknown): string {
  const detail = getErrorDetail(error)

  if (typeof detail === 'string' && detail.length > 0) {
    return detail
  }

  return `API request failed with status ${response.status}`
}

function getErrorDetail(error: unknown): unknown {
  if (isRecord(error) && 'detail' in error) {
    return error.detail
  }

  return error
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
