import os
import tempfile

import git
from gitingest import ingest as repo_ingest


def ingest(token: str, repo_url: str, subdir: str):
    """Ingest a repository and return a report.
    Returns its summary, tree, and content."""
    # Clone the repository, if provided. Otherwise, ingest the directory.
    if repo_url:
        # Add token to the repo URL if provided
        if token:
            repo_url = f"https://{token}@{repo_url.replace("https://", "")}"
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                git.Repo.clone_from(repo_url, temp_dir)
                return repo_ingest(os.path.join(temp_dir, subdir))
            except Exception as e:
                print(f"Error cloning repository: {e}")
    elif subdir:
        try:
            return repo_ingest(subdir)
        except Exception as e:
            print(f"Error ingesting local repository: {e}")
    else:
        raise ValueError("Both repo_url and subdir cannot be empty")
