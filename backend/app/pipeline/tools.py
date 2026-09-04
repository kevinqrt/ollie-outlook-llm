from langchain_core.tools import BaseTool, tool
from rag_service_api import Client

from app.pipeline import rag_client


def build_search_tool(client: Client, session_id: str) -> BaseTool:
    """Baut ein Tool, mit dem der Agent den Inhalt der aktuellen E-Mail (RAG-Session) abfragen kann.

    Ohne dieses Tool hat das LLM keine Möglichkeit, Aussagen wie "ist der Termin frei?"
    oder "wurden die Unterlagen schon versendet?" zu verifizieren - es würde raten statt
    nachzuschlagen.
    """

    @tool
    async def search_email_context(query: str) -> str:
        """Durchsucht den Inhalt der aktuell bearbeiteten E-Mail nach einer Antwort auf `query`.

        Nutze dieses Tool, um Fakten aus der E-Mail zu verifizieren, statt zu raten.
        """
        try:
            return await rag_client.query_rag_session(client, session_id, query)
        except Exception as exc:  # Grenze zum RAG-Service: Fehler als Beobachtung zurückgeben
            return f"Suche fehlgeschlagen: {exc}"

    return search_email_context
