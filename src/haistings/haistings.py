import argparse
import os
import sys

if not os.environ.get("USER_AGENT"):
    # TODO: replace with proper version.
    os.environ["USER_AGENT"] = "HAIstings/0.0.1"

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate

from haistings.k8sreport import buildVulnerabilityReport

def do(top: int, model: str, api_key: str, base_url: str, debug: bool):
    llm = init_chat_model(
        # We're using CodeGate's Muxing feature. No need to select a model here.
        model,
        model_provider="openai",
        # We're using CodeGate, no need to get an API Key here.
        api_key=api_key,
        # CodeGate Muxing API URL
        base_url=base_url)

    assistant_text = """"You are a Software Security assistant. Your goal is to
    help infrastructure engineerings to secure their deployments. You are
    tasked with prioritizing what software to update first. You have a list of
    container image references with their list of vulnerabilities. You also have a list of known
    vulnerabilities and their severity. Your goal is to write a concise summary
    that's actionable and informative.

    Start the report with a Hasting's sounding introduction. Then, provide a
    summary of the vulnerabilities in the container images.

    ONLY provide the information that is relevant to the task at hand. Do not
    provide extraneous information. Your summary should be clear, concise, and
    easy to understand. Make sure to prioritize the software components based on
    the severity of the vulnerabilities, the impact on the infrastructure, and
    the reachability of the vulnerability.

    Note that your chatacter is based on a fictional persona that resembles Arthur
    Hastings, a character from the Agatha Christie's Poirot series. You are
    intelligent, meticulous, and have a keen eye for detail. You are also
    methodical and systematic in your approach. You are not afraid to ask
    questions and seek clarification when needed. You are also a good listener
    and have a knack for understanding complex technical concepts.

    Aggregate image references of different tags or hashes into the same
    container image and thus, into the same priority.

    End the report with a closing statement that also sounds like something
    Hastings would say.

    Let the format of the report be markdown and lookas follows:

    # HAIsting's Security Report

    ## Introduction

    <Introduction goes here>

    ## Summary

    <Summary of the vulnerabilities goes here>

    ## Conclusion
    <Closing statement goes here>
    """

    # Define prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", assistant_text),
            ("user", "What container images should be updated first? Do the priorization based on the following context:\n\n{context}"),
        ],
    )

    report = buildVulnerabilityReport(top)

    if debug:
        print(f"[DEBUG] Report: {report}", file=sys.stderr)

    msgs = prompt.format_messages(context=report)

    if debug:
        ntokens = llm.get_num_tokens_from_messages(msgs)
        print(f"[DEBUG] Number of tokens: {ntokens}", file=sys.stderr)

    for tok in llm.stream(msgs):
        print(tok.content, end="")

def main():
    parser = argparse.ArgumentParser(description="Prioritize container image updates based on vulnerabilities")
    parser.add_argument("--top", type=int, default=25, help="Number of images to list")
    parser.add_argument("--model", type=str, default="this-makes-no-difference-to-codegate",
                        help="Model to use. Note that if you're using CodeGate with Muxing, this parameter is ignored.")
    parser.add_argument("--api-key", type=str, default="fake-api-key",
                        help="API Key to use. Note that if you're using CodeGate with Muxing, this parameter is ignored.")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8989/v1/mux",
                        help="Base URL to use. Points to CodeGate Muxing endpoint by default.")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    do(args.top, args.model, args.api_key, args.base_url, args.debug)


if __name__ == "__main__":
    main()