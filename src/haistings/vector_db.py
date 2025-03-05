import json
import os
import sqlite3
from typing import Dict, List, Optional

import numpy as np
from langchain.embeddings import CacheBackedEmbeddings
from langchain.embeddings.base import Embeddings
from langchain.storage import LocalFileStore
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


class VectorDatabase:
    """A simple vector database using SQLite for storing and retrieving documents."""

    def __init__(self, db_path: str = ".haistings-vectordb.db", embedding_model: Optional[Embeddings] = None):
        """Initialize the vector database.

        Args:
            db_path: Path to the SQLite database file
            embedding_model: Embedding model to use for vectorizing documents
        """
        self.db_path = db_path

        # Initialize embedding model if not provided
        if embedding_model is None:
            # Use a small, efficient model for embeddings
            base_embeddings = HuggingFaceEmbeddings(
                model_name="BAAI/bge-small-en-v1.5",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )

            # Use cache to avoid recomputing embeddings
            cache_dir = os.path.join(os.path.dirname(db_path), ".embeddings_cache")
            store = LocalFileStore(cache_dir)
            self.embedding_model = CacheBackedEmbeddings.from_bytes_store(
                base_embeddings, store, namespace=base_embeddings.model_name
            )
        else:
            self.embedding_model = embedding_model

        # Initialize the database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create documents table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT,
            path TEXT,
            content TEXT,
            metadata TEXT,
            UNIQUE(repo_url, path)
        )
        """
        )

        # Create embeddings table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS embeddings (
            document_id INTEGER,
            embedding BLOB,
            FOREIGN KEY (document_id) REFERENCES documents (id),
            UNIQUE(document_id)
        )
        """
        )

        conn.commit()
        conn.close()

    def add_document(self, repo_url: str, path: str, content: str, metadata: Dict = None) -> int:
        """Add a document to the database.

        Args:
            repo_url: URL of the repository
            path: Path to the file within the repository
            content: Content of the file
            metadata: Additional metadata about the file

        Returns:
            The ID of the inserted document
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Insert or replace document
        # Serialize metadata to JSON instead of using str() for security and reliability
        metadata_json = json.dumps(metadata or {})
        cursor.execute(
            "INSERT OR REPLACE INTO documents (repo_url, path, content, metadata) VALUES (?, ?, ?, ?)",
            (repo_url, path, content, metadata_json),
        )

        # Get the document ID
        document_id = cursor.lastrowid

        # Create a Document object with content and metadata
        doc = Document(page_content=content, metadata={"repo_url": repo_url, "path": path, **(metadata or {})})

        # Generate embedding using the document's content
        # Note: Some embedding models can work directly with Document objects,
        # but for maximum compatibility, we're using the content string
        embedding = self.embedding_model.embed_documents([doc.page_content])[0]

        # Store embedding as binary blob
        embedding_blob = self._vector_to_blob(embedding)
        cursor.execute(
            "INSERT OR REPLACE INTO embeddings (document_id, embedding) VALUES (?, ?)", (document_id, embedding_blob)
        )

        conn.commit()
        conn.close()

        return document_id

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """Search for documents similar to the query.

        Args:
            query: The query string
            k: Number of results to return

        Returns:
            List of documents sorted by similarity
        """
        # Generate query embedding
        # Note: Some embedding models can work directly with Document objects,
        # but for maximum compatibility, we're using the content string
        query_embedding = self.embedding_model.embed_query(query)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all documents and embeddings
        cursor.execute(
            """
        SELECT d.id, d.repo_url, d.path, d.content, d.metadata, e.embedding
        FROM documents d
        JOIN embeddings e ON d.id = e.document_id
        """
        )

        results = []
        for row in cursor.fetchall():
            doc_id, repo_url, path, content, metadata_str, embedding_blob = row
            embedding = self._blob_to_vector(embedding_blob)

            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_embedding, embedding)

            # Parse metadata from JSON instead of using eval() for security
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                metadata = {}

            results.append(
                (
                    similarity,
                    Document(
                        page_content=content, metadata={"id": doc_id, "repo_url": repo_url, "path": path, **metadata}
                    ),
                )
            )

        conn.close()

        # Sort by similarity (highest first) and return top k
        results.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in results[:k]]

    def get_document_by_path(self, repo_url: str, path: str) -> Optional[Document]:
        """Get a document by its repository URL and path.

        Args:
            repo_url: URL of the repository
            path: Path to the file within the repository

        Returns:
            The document if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, content, metadata FROM documents WHERE repo_url = ? AND path = ?", (repo_url, path))

        row = cursor.fetchone()
        conn.close()

        if row:
            doc_id, content, metadata_str = row
            # Parse metadata from JSON instead of using eval() for security
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                metadata = {}

            return Document(
                page_content=content, metadata={"id": doc_id, "repo_url": repo_url, "path": path, **metadata}
            )

        return None

    def get_all_documents(self, repo_url: Optional[str] = None) -> List[Document]:
        """Get all documents, optionally filtered by repository URL.

        Args:
            repo_url: Optional URL of the repository to filter by

        Returns:
            List of all documents
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if repo_url:
            cursor.execute(
                "SELECT id, repo_url, path, content, metadata FROM documents WHERE repo_url = ?", (repo_url,)
            )
        else:
            cursor.execute("SELECT id, repo_url, path, content, metadata FROM documents")

        results = []
        for row in cursor.fetchall():
            doc_id, repo_url, path, content, metadata_str = row
            # Parse metadata from JSON instead of using eval() for security
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                metadata = {}

            results.append(
                Document(page_content=content, metadata={"id": doc_id, "repo_url": repo_url, "path": path, **metadata})
            )

        conn.close()
        return results

    def clear(self) -> None:
        """Clear all documents and embeddings from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM embeddings")
        cursor.execute("DELETE FROM documents")

        conn.commit()
        conn.close()

    def _vector_to_blob(self, vector: List[float]) -> bytes:
        """Convert a vector to a binary blob for storage."""
        return np.array(vector, dtype=np.float32).tobytes()

    def _blob_to_vector(self, blob: bytes) -> List[float]:
        """Convert a binary blob to a vector."""
        return np.frombuffer(blob, dtype=np.float32).tolist()

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0

        return dot_product / (norm1 * norm2)


def is_kubernetes_file(file_path: str) -> bool:
    """Check if a file is a Kubernetes manifest file.

    Args:
        file_path: Path to the file

    Returns:
        True if the file is a Kubernetes manifest file, False otherwise
    """
    # Check file extension
    if file_path.endswith((".yaml", ".yml", ".json")):
        # Additional checks could be added here, such as checking for common
        # Kubernetes fields in the file content
        return True

    return False


def build_query_from_report_result(report_result, component_name: str) -> str:
    """Build a query from a ReportResult object for a specific component.

    Args:
        report_result: The ReportResult object
        component_name: The name of the component to build a query for

    Returns:
        A query string
    """
    # Find the component in the report
    component = None
    for img in report_result.images_with_vulns:
        if component_name in img.img:
            component = img
            break

    if not component:
        return f"kubernetes deployment {component_name}"

    # Build a query based on the component and its vulnerabilities
    query = f"kubernetes deployment {component_name} "

    # Add namespace
    if component.namespace:
        query += f"in namespace {component.namespace} "

    # Add vulnerability information
    if component.vulns:
        query += "with vulnerabilities "
        vuln_ids = [v.id for v in component.vulns[:3]]  # Limit to first 3 vulnerabilities
        query += ", ".join(vuln_ids)

    return query
