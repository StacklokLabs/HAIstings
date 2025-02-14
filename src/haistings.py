import os

if not os.environ.get("USER_AGENT"):
    # TODO: replace with proper version.
    os.environ["USER_AGENT"] = "HAIstings/0.0.1"

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate

from .k8sreport import buildVulnerabilityReport

def main():
    llm = init_chat_model("this-makes-no-difference-to-codegate",
                        model_provider="openai",
                        # CodeGate Muxing API URL
                        base_url="http://127.0.0.1:8989/v1/mux")

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

    End the report with a closing statement that also sounds like something
    Hastings would say.
    """

    # Define prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", assistant_text),
            ("user", "What container images should be updated first? Do the priorization based on the following context:\n\n{context}"),
        ],
    )

    report = buildVulnerabilityReport(5)

    for tok in llm.stream(
        prompt.invoke({"context": report}),
    ):
        print(tok, end="")

if __name__ == "__main__":
    main()