# To-Do List

## Setup & Infrastructure
- [x] **Automated OpenAPI Sync**: Create a command (e.g., in `justfile`) that automatically fetches the `openapi.json` from the running FastAPI backend and updates the frontend's generated TypeScript types.

## Features

- [ ] **Generate Reply Button**: Add a generate reply button which automatically generates a reply for the focused email based on the `getEmailSuggestion` method.

- [ ] **Vector Store Integration für PDF/Website Scanner**
  - **Ziel:** E-Mail-Antworten vor dem Senden an den RAG-Service mit zusätzlichem Wissen aus PDFs anreichern.

  - **Backend-Aufgaben:**
    - **Technologie-Stack:** PyMuPDF (`pymupdf`), ChromaDB (`langchain-chroma`), LangChain.
    - **Teilaufgaben:**
      - [ ] `backend/pyproject.toml` um LangChain, Chroma, HuggingFace Embeddings und PyMuPDF erweitern.
      - [ ] Konfiguration (`app/core/config.py`) um `vector_store_path` und `embedding_model` erweitern.
      - [ ] `VectorStoreService` (`app/services/vector_store_service.py`) erstellen (Methoden: `ingest_pdf`, `search`, `list_documents`, `delete_document`).
      - [ ] API-Endpunkte in `app/api/router.py` hinzufügen:
        - `POST /knowledge/pdf` (Upload)
        - `GET /knowledge/search` (Test-Suche)
        - `GET /knowledge/documents` (Liste aller PDFs)
        - `DELETE /knowledge/documents/{doc_id}` (Löschen eines PDFs)
      - [ ] `LlmService.generate_suggestion` anpassen, um vor dem Aufruf der RAG-Pipeline den Vector Store abzufragen und das Wissen an den E-Mail-Kontext anzuhängen.

  - **Frontend-Aufgaben:**
    - **Ziel:** UI für die Verwaltung der Wissensbasis bereitstellen.
    - **Teilaufgaben:**
      - [ ] OpenAPI-Client aktualisieren (`just sync-openapi`), um die neuen Backend-Endpunkte im Frontend verfügbar zu haben.
      - [ ] Neuen Reiter/Tab "Wissensbasis" in der UI hinzufügen.
      - [ ] Upload-Komponente für PDF-Dateien implementieren (Aufruf von `POST /knowledge/pdf`).
      - [ ] Listen-Ansicht der hochgeladenen Dokumente anzeigen (Aufruf von `GET /knowledge/documents`).
      - [ ] Löschen-Funktion (Papierkorb-Icon) pro Dokument implementieren (Aufruf von `DELETE /knowledge/documents/{doc_id}`).
