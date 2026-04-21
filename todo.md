# To-Do List

## Setup & Infrastructure
- [ ] **Environment-based API URL**: Move `OLLIE_API_BASE_URL` in `frontend/src/api/client.ts` to use `import.meta.env.VITE_API_BASE_URL` from environment variables.
- [ ] **Automated OpenAPI Sync**: Create a command (e.g., in `justfile`) that automatically fetches the `openapi.json` from the running FastAPI backend and updates the frontend's generated TypeScript types.

## Features
- [ ] **Generate Reply Button**: Add a generate reply button which automatically generates a reply for the focused email based on the `getEmailSuggestion` method.
