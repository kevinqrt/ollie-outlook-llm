import logging
import tempfile
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.api.schemas.knowledge_schema import KnowledgeDocumentSchema, KnowledgeSearchResultSchema
from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(self) -> None:
        logger.info("Initializing VectorStoreService (this should only happen once)")
        self.embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
        self.vector_store = Chroma(
            persist_directory=settings.vector_store_path,
            embedding_function=self.embeddings,
            collection_name="knowledge_base",
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )

    async def ingest_documents(self, documents: list[Document], source_name: str) -> str:
        """Process documents and add their content to the vector store.

        This method handles splitting and storage, decoupled from the source format.
        """
        # Check if document with this name already exists
        existing = self.vector_store.get(where={"source": source_name})
        if existing and existing.get("ids"):
            logger.warning("Attempted to upload duplicate document: %s", source_name)
            raise ValueError(f"Document '{source_name}' already exists in the knowledge base.")

        for doc in documents:
            doc.metadata["source"] = source_name

        chunks = self.text_splitter.split_documents(documents)

        # Filter out chunks that are empty or only whitespace
        valid_chunks = [c for c in chunks if c.page_content and c.page_content.strip()]

        if not valid_chunks:
            logger.warning("No valid text chunks found for source: %s", source_name)
            raise ValueError(f"No readable text found in '{source_name}'.")

        logger.info(
            "Adding %d valid chunks to vector store for source: %s", len(valid_chunks), source_name
        )
        self.vector_store.add_documents(valid_chunks)
        logger.info("Successfully ingested source: %s", source_name)
        return source_name

    async def ingest_pdf(self, file_content: bytes, filename: str) -> str:
        """Parse a PDF file and delegate to ingest_documents."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name

        try:
            loader = PyMuPDFLoader(tmp_path)
            documents = loader.load()
            return await self.ingest_documents(documents, filename)
        finally:
            p = Path(tmp_path)
            if p.exists():
                p.unlink()

    async def search(self, query: str, k: int = 3) -> list[KnowledgeSearchResultSchema]:
        """Search for relevant context in the vector store."""
        results = self.vector_store.similarity_search(query, k=k)
        return [
            KnowledgeSearchResultSchema(content=doc.page_content, metadata=doc.metadata)
            for doc in results
        ]

    async def list_documents(self) -> list[KnowledgeDocumentSchema]:
        """List all unique documents in the vector store."""
        all_data = self.vector_store.get()
        if not all_data or "metadatas" not in all_data:
            return []

        unique_docs = set()
        for metadata in all_data["metadatas"]:
            source = metadata.get("source", "unknown")
            unique_docs.add(source)

        return [KnowledgeDocumentSchema(source=source) for source in sorted(unique_docs)]

    async def delete_document(self, filename: str) -> bool:
        """Delete a document and its chunks from the vector store."""
        try:
            # First, find all IDs associated with this source
            data = self.vector_store.get(where={"source": filename})
            ids = data.get("ids", [])

            if not ids:
                logger.warning("No documents found in vector store for filename: %s", filename)
                return False

            # Perform deletion
            self.vector_store.delete(ids=ids)
            logger.info("Successfully deleted %d chunks for document: %s", len(ids), filename)
            return True
        except Exception as e:
            logger.error("Error deleting document %s: %s", filename, e)
            return False
