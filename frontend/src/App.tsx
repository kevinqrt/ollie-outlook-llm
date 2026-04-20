import { useState } from 'react'
import { ApiError, getEmailSuggestion } from './api'
import './App.css'

type RequestState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; suggestedReply: string }
  | { status: 'error'; message: string }

function App() {
  const [emailContent, setEmailContent] = useState(
    'Test Email Content'
  )
  const [requestState, setRequestState] = useState<RequestState>({
    status: 'idle',
  })

  const isLoading = requestState.status === 'loading'

  async function requestSuggestion() {
    setRequestState({ status: 'loading' })

    try {
      const { suggestedReply } = await getEmailSuggestion(emailContent)
      setRequestState({ status: 'success', suggestedReply })
    } catch (error) {
      setRequestState({
        status: 'error',
        message: getErrorMessage(error),
      })
    }
  }

  return (
    <main className="taskpane">
      <textarea
        className="email-input"
        value={emailContent}
        onChange={(e) => setEmailContent(e.target.value)}
        placeholder="E-Mail Inhalt hier einfuegen..."
        disabled={isLoading}
      />
      <button
        className="suggestion-button"
        disabled={isLoading}
        type="button"
        onClick={requestSuggestion}
      >
        {isLoading ? 'Wird gesendet...' : 'Antwortvorschlag anfordern'}
      </button>

      {requestState.status === 'loading' && (
        <p className="status" aria-live="polite">
          Anfrage laeuft.
        </p>
      )}

      {requestState.status === 'success' && (
        <p className="result" aria-live="polite">
          {requestState.suggestedReply}
        </p>
      )}

      {requestState.status === 'error' && (
        <p className="error" role="alert">
          {requestState.message}
        </p>
      )}
    </main>
  )
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `Anfrage fehlgeschlagen (${error.status}).`
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Anfrage fehlgeschlagen.'
}

export default App
