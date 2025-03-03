# HAIstings

HAIstings is an AI-powered companion designed to help you assess and prioritize Common Vulnerabilities and Exposures (CVEs) within your Kubernetes infrastructure. Drawing inspiration from Agatha Christie's legendary character Arthur Hastings, the crime-solving partner of Hercule Poirot, HAIstings partners with you to ensure robust security measures in your Kubernetes environments.

## Overview

HAIstings analyzes vulnerability reports from tools like trivy-operator, generates prioritized reports, and engages in an interactive conversation to refine its recommendations based on your specific context and requirements.

## Features

- **Vulnerability Prioritization**: Automatically prioritizes vulnerabilities based on severity, impact, and context
- **Interactive Refinement**: Engages in a conversation to gather more context and refine prioritization
- **Infrastructure Context**: Ingests infrastructure repository information to provide more relevant recommendations
- **Persistent Memory**: Maintains conversation history across sessions using checkpoints
- **Customizable Output**: Adjusts recommendations based on user-provided context

## Installation

### Prerequisites

- Python 3.12
- Kubernetes cluster with trivy-operator installed
- Properly configured kubeconfig file

### Using Poetry

```bash
# Clone the repository
git clone https://github.com/stacklok/HAIstings.git
cd HAIstings

# Install dependencies
poetry install
```

### Using pip

```bash
pip install haistings
```

## Usage

### Basic Usage

Generate a vulnerability report showing the top 25 most critical vulnerabilities:

```bash
haistings
```

### Customizing Output

Specify the number of vulnerabilities to show:

```bash
haistings --top 30
```

### Providing Context

Provide additional context to improve prioritization:

```bash
haistings --notes usercontext.txt
```

Where `usercontext.txt` contains information about your infrastructure, such as:

```
example-service is a very critical service that is internet-facing. We should assign more priority to it.

Flux is critical to our infrastructure, so if it has a vulnerability on anything related to how it processes git requests, then we should assign it very high priority.
```

### Ingesting Infrastructure Repository

Provide your infrastructure repository for additional context:

```bash
haistings --infra-repo https://github.com/yourusername/infra-repo --gh-token YOUR_GITHUB_TOKEN
```

For a specific subdirectory:

```bash
haistings --infra-repo https://github.com/yourusername/infra-repo --infra-repo-subdir kubernetes --gh-token YOUR_GITHUB_TOKEN
```

### Persistent Conversations

Use SQLite to persist conversation history:

```bash
haistings --checkpoint-saver-driver sqlite
```

### Full Example

```bash
haistings --top 30 --notes usercontext.txt --infra-repo https://github.com/yourusername/infra-repo --checkpoint-saver-driver sqlite
```

## How It Works

1. **Vulnerability Collection**: HAIstings connects to your Kubernetes cluster and collects vulnerability reports from trivy-operator.
2. **Prioritization**: Vulnerabilities are prioritized based on severity (critical vulnerabilities are weighted 10x more than high vulnerabilities).
3. **Context Integration**: User-provided context and infrastructure repository information are integrated into the analysis.
4. **Report Generation**: A prioritized report is generated in a conversational style inspired by Arthur Hastings.
5. **Interactive Refinement**: HAIstings engages in a conversation to gather more context and refine its recommendations.

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--top` | Number of vulnerabilities to show | 25 |
| `--notes` | Path to a file containing additional context | None |
| `--infra-repo` | URL to your infrastructure repository | None |
| `--infra-repo-subdir` | Subdirectory in the repository to ingest | None |
| `--gh-token` | GitHub Personal Access Token for private repositories | None |
| `--checkpoint-saver-driver` | Memory persistence driver (`memory` or `sqlite`) | `memory` |
| `--debug` | Enable debug mode | False |
| `--model` | LLM model to use (when not using CodeGate) | `this-makes-no-difference-to-codegate` |
| `--model-provider` | Model provider | `openai` |
| `--api-key` | API key for the model provider (when not using CodeGate) | `fake-api-key` |
| `--base-url` | Base URL for the model provider | `http://127.0.0.1:8989/v1/mux` |

## Example Output

```markdown
# HAIsting's Security Report

## Introduction

Good day! Arthur Hastings at your service. I've meticulously examined the vulnerability reports from your Kubernetes infrastructure and prepared a prioritized assessment of the security concerns that require your immediate attention.

## Summary

After careful analysis, I've identified several critical vulnerabilities that demand prompt remediation:

1. **example-service (internet-facing service)**
   - Critical vulnerabilities: 3
   - High vulnerabilities: 7
   - Most concerning: CVE-2023-1234 (Remote code execution)
   
   This service is particularly concerning due to its internet-facing nature, as mentioned in your notes. I recommend addressing these vulnerabilities with the utmost urgency.

2. **Flux (GitOps controller)**
   - Critical vulnerabilities: 2
   - High vulnerabilities: 5
   - Most concerning: CVE-2023-5678 (Git request processing vulnerability)
   
   As you've noted, Flux is critical to your infrastructure, and this Git request processing vulnerability aligns with your specific concerns.

[Additional entries...]

## Conclusion

I say, these vulnerabilities require prompt attention, particularly the ones affecting your internet-facing services and deployment controllers. I recommend addressing the critical vulnerabilities in example-service and Flux as your top priorities. Should you require any further assistance or have additional context to share, I remain at your service.
```

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/stacklok/HAIstings.git
cd HAIstings

# Install dependencies including development dependencies
poetry install

# Run tests
poetry run pytest
```

### Code Style

This project uses:
- Black for code formatting
- isort for import sorting
- mypy for type checking
- flake8 for linting

```bash
# Format code
poetry run black .
poetry run isort .

# Type check
poetry run mypy .

# Lint
poetry run flake8
```

## Future Improvements / TODO

- **RAG for Infrastructure Files**: Implement Retrieval-Augmented Generation to selectively include only relevant infrastructure files in the context, reducing overall context size and improving performance.
- **Custom Vulnerability Scoring**: Add support for custom vulnerability scoring based on user-defined criteria beyond just severity.
- **Integration with More Scanners**: Extend beyond trivy-operator to support other vulnerability scanners.
- **Visualization Dashboard**: Create a web interface to visualize vulnerability reports and trends over time.
- **Automated Remediation Suggestions**: Provide specific remediation steps for common vulnerabilities.
- **Multi-Cluster Support**: Add support for analyzing vulnerabilities across multiple Kubernetes clusters.

## License

Apache-2.0
