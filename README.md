# HAIstings

HAIstings is an AI-powered companion designed to help you assess and prioritize Common Vulnerabilities and Exposures (CVEs) within your components. Drawing inspiration from Agatha Christie's legendary character Hastings, the crime-solving partner of Hercule Poirot, HAIstings partners with you to ensure robust security measures in your Kubernetes environments.

## Features

- **Intelligent CVE Evaluation**: Analyze and interpret a list of CVEs affecting your components to assess potential risks accurately.
- **Prioritization**: Automatically prioritize CVEs based on severity and reachability, helping you address the most critical vulnerabilities first.
- **Kubernetes Manifest Analysis**: Directly ingest Kubernetes manifests to tailor security assessments in context with your specific configurations.
- **Context Awareness**: HAIstings learns from your environment to provide bespoke security recommendations.

## How It Works

1. **Input**: Provide HAIstings with the Kubernetes manifest of your component and the list of associated CVEs.
2. **Analyze**: HAIstings examines the CVEs in detail, considering their impact and how they integrate with your component's configuration.
3. **Prioritize**: Using intelligent algorithms, HAIstings ranks the CVEs by their severity and the likelihood of exploitation.
4. **Output**: Receive a prioritized list of CVEs, along with contextual advice to mitigate potential risks.

## Getting Started

### Prerequisites

- Python 3.12
- [Docker](https://docs.docker.com/get-docker/)
- Kubernetes environment (e.g., Minikube, GKE)

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/HAIstings.git
   cd HAIstings
   ```

2. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

### Usage

1. Prepare your Kubernetes manifest file of the component.
2. Gather the list of CVEs affecting your component.
3. Run HAIstings with the manifest and CVE list as input:

   ```bash
   python haistings.py --manifest /path/to/manifest.yaml --cves /path/to/cves.json
   ```

4. Review the output for the prioritized list of CVEs and corresponding mitigation advice.

## Example

Here's an example command and what you can expect from HAIstings:

```bash
python haistings.py --manifest example-app.yaml --cves example-cves.json
```

### Example Output

TODO

## Contributing

Contributions are welcome! Please submit a pull request or open an issue to discuss any changes or enhancements.

---

With HAIstings, make your Kubernetes environment more secure and gain the peace of mind that your components are well-guarded against vulnerabilities.