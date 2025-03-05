import os
import tempfile
from typing import Dict, List, Tuple

import git
from gitingest import ingest as repo_ingest

from haistings.vector_db import VectorDatabase, is_kubernetes_file


def ingest(token: str, repo_url: str, subdir: str, use_vectordb: bool = True) -> Tuple[str, str, str]:
    """Ingest a repository and return a report.
    Returns its summary, tree, and content."""
    # Clone the repository, if provided. Otherwise, ingest the directory.
    if repo_url:
        # Add token to the repo URL if provided
        if token:
            repo_url = f"https://{token}@{repo_url.replace('https://', '')}"
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                git.Repo.clone_from(repo_url, temp_dir)
                if use_vectordb:
                    return ingest_to_vectordb(repo_url, os.path.join(temp_dir, subdir))
                else:
                    return repo_ingest(os.path.join(temp_dir, subdir))
            except Exception as e:
                print(f"Error cloning repository: {e}")
    elif subdir:
        try:
            if use_vectordb:
                return ingest_to_vectordb("local", subdir)
            else:
                return repo_ingest(subdir)
        except Exception as e:
            print(f"Error ingesting local repository: {e}")
    else:
        raise ValueError("Both repo_url and subdir cannot be empty")


def ingest_to_vectordb(repo_url: str, repo_path: str) -> Tuple[str, str, str]:
    """Ingest a repository to the vector database.

    Args:
        repo_url: URL of the repository (or "local" for local repositories)
        repo_path: Path to the repository

    Returns:
        A tuple of (summary, tree, content_preview)
    """
    # Get repository summary and tree using gitingest
    summary, tree, _ = repo_ingest(repo_path)

    # Initialize vector database
    vector_db = VectorDatabase()

    # Walk through the repository and add files to the vector database
    file_count = 0
    k8s_file_count = 0

    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_path)

            # Skip hidden files and directories
            if any(part.startswith(".") for part in rel_path.split(os.sep)):
                continue

            try:
                # Read file content
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check if it's a Kubernetes file
                is_k8s = is_kubernetes_file(file_path)

                # Add to vector database
                vector_db.add_document(
                    repo_url=repo_url,
                    path=rel_path,
                    content=content,
                    metadata={
                        "is_kubernetes": is_k8s,
                        "file_type": os.path.splitext(file_path)[1],
                    },
                )

                file_count += 1
                if is_k8s:
                    k8s_file_count += 1

            except Exception as e:
                print(f"Error processing file {file_path}: {e}")

    # Generate a content preview
    content_preview = (
        f"Ingested {file_count} files into vector database, including {k8s_file_count} Kubernetes manifests."
    )

    return summary, tree, content_preview


def retrieve_relevant_files(repo_url: str, query: str, k: int = 5) -> List[Dict]:
    """Retrieve relevant files from the vector database based on a query.

    Args:
        repo_url: URL of the repository (or "local" for local repositories)
        query: Query string
        k: Number of results to return

    Returns:
        List of relevant files with their content and metadata
    """
    vector_db = VectorDatabase()
    documents = vector_db.similarity_search(query, k=k)

    results = []
    for doc in documents:
        results.append(
            {
                "path": doc.metadata["path"],
                "content": doc.page_content,
                "is_kubernetes": doc.metadata.get("is_kubernetes", False),
            }
        )

    return results
