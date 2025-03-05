#!/usr/bin/env python3
"""
Test script for the RAG functionality in HAIstings.

This script demonstrates how to use the vector database to store and retrieve
relevant files for a Kubernetes deployment.
"""

import os
import tempfile

from haistings.repo_ingest import ingest_to_vectordb, retrieve_relevant_files
from haistings.vector_db import VectorDatabase


def test_ingest_and_retrieve():
    """Test ingesting a repository and retrieving relevant files."""
    # Create a temporary directory for the test
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample Kubernetes deployment file
        os.makedirs(os.path.join(temp_dir, "kubernetes"), exist_ok=True)

        # Create a sample deployment file
        with open(os.path.join(temp_dir, "kubernetes", "deployment.yaml"), "w") as f:
            f.write(
                """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example-service
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: example-service
  template:
    metadata:
      labels:
        app: example-service
    spec:
      containers:
      - name: example-service
        image: example/service:latest
        ports:
        - containerPort: 8080
"""
            )

        # Create another sample file
        with open(os.path.join(temp_dir, "kubernetes", "service.yaml"), "w") as f:
            f.write(
                """
apiVersion: v1
kind: Service
metadata:
  name: example-service
  namespace: default
spec:
  selector:
    app: example-service
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
"""
            )

        # Ingest the repository
        print("Ingesting repository...")
        summary, tree, content_preview = ingest_to_vectordb("test-repo", temp_dir)

        print(f"Summary: {summary}")
        print(f"Tree: {tree}")
        print(f"Content Preview: {content_preview}")

        # Retrieve relevant files
        print("\nRetrieving relevant files for 'example-service'...")
        query = "kubernetes deployment example-service in namespace default"
        relevant_files = retrieve_relevant_files("test-repo", query, k=2)

        print(f"Found {len(relevant_files)} relevant files:")
        for file in relevant_files:
            print(f"- {file['path']} (is_kubernetes: {file['is_kubernetes']})")
            print(f"  Content snippet: {file['content'][:100]}...")

        # Clean up
        print("\nCleaning up...")
        vector_db = VectorDatabase()
        vector_db.clear()
        print("Done!")


if __name__ == "__main__":
    test_ingest_and_retrieve()
