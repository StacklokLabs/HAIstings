import argparse
import os
import sys
import tempfile
import git

from uuid import uuid4

if not os.environ.get("USER_AGENT"):
    # TODO: replace with proper version.
    os.environ["USER_AGENT"] = "HAIstings/0.0.1"

from gitingest import ingest
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph, MessagesState

from haistings.k8sreport import buildVulnerabilityReport

rt = None

class State(MessagesState):
    """State of the conversation."""

    # The user's question
    question: str
    # infrareport is the report of the infrastructure vulnerabilities.
    infrareport: str
    # usercontext is the context provided by the user. It helps enhance
    # the quality of the response by providing information about the
    # different components of the infrastructure.
    usercontext: str
    answer: str


class HAIstingsRuntime:

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

    def __init__(self, top: int, model: str, api_key: str, base_url: str):
        tid = "haistings-" + str(uuid4())
        self.rtconfig = {"configurable": {"thread_id": tid}}
        ## TODO: Make this configurable
        self.report = lambda: buildVulnerabilityReport(top)
        self.llm = init_chat_model(
            # We're using CodeGate's Muxing feature. No need to select a model here.
            model,
            model_provider="openai",
            # We're using CodeGate, no need to get an API Key here.
            api_key=api_key,
            # CodeGate Muxing API URL
            base_url=base_url)

        # Define prompt
        self.kickoff_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.assistant_text),
                # Kicks off the conversation
                ("user", "{question} Do the priorization based on the following context:\n\n{context}\n\n"
                         "The system administrator also provided the following context which is "
                         "important for the prioritization:\n\n{usercontext}"),
            ],
        )


    def run(self):
        do(self.top, self.model, self.api_key, self.base_url, self.debug)


# Define application steps
def retrieve(state: State):
    report = rt.report()
    return {"infrareport": report}


def generate_initial(state: State):
    messages = rt.kickoff_prompt.invoke({
        "context": state["infrareport"],
        "question": state["question"],
        "usercontext": state["usercontext"]
    })
    response = rt.llm.invoke(messages)
    print(response.content)

    return {
        "messages": response,
        "answer": response.content,
    }


def extra_userinput(state: State):
    """Based on the user input, the assistant will provide a response."""
    messages = state["messages"]
    extra = input("Please provide more information to help the assistant provide a better response: ")

    prompt = ChatPromptTemplate.from_messages([
        ("user", "Here's extra context to help with the prioritization: {extra}. "
                 "Given this new information, can you provide a better response?"),
    ])

    prompt_msg = prompt.invoke({"extra": extra})

    messages = messages + prompt_msg.to_messages()

    response = rt.llm.invoke(messages)
    print(response.content)
    return {
        "messages": response,
        "answer": response.content,
    }


def needs_more_info(state: State):
    print("Is there more information needed? Note that more information "
          "will help the assistant provide a better response.")
    should_continue = input("Type 'yes' or 'no': ").lower() == "yes"
    if should_continue:
        return "extra_userinput"
    return END


def ingest_repo(token: str, repo_url: str, subdir: str):
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
                return ingest(os.path.join(temp_dir, subdir))
            except Exception as e:
                print(f"Error cloning repository: {e}")
    elif subdir:
        return ingest(subdir)
    else:
        raise ValueError("Both repo_url and subdir cannot be empty")


def do(top: int, model: str, api_key: str, base_url: str, notes: str):
    global rt

    rt = HAIstingsRuntime(top, model, api_key, base_url)

    # Add memory
    memory = MemorySaver()

    graph_builder = StateGraph(State)
    # Nodes
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("generate_initial", generate_initial)
    graph_builder.add_node("extra_userinput", extra_userinput)

    # Edges
    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "generate_initial")

    # potentially finish execution after initial report.
    graph_builder.add_conditional_edges(
        "generate_initial",
        needs_more_info,
        ["extra_userinput", END])

    # allow for finishing execution after extra user input.
    graph_builder.add_conditional_edges(
        "extra_userinput",
        needs_more_info,
        ["extra_userinput", END]
    )

    # Compile the graph
    graph = graph_builder.compile(checkpointer=memory)

    kickoff_question = "What are the top vulnerabilities in the infrastructure?"

    # Start the conversation
    graph.invoke( {
        "question": kickoff_question,
        "usercontext": notes,
    }, config=rt.rtconfig)


def main():
    parser = argparse.ArgumentParser(description="Prioritize container image updates based on vulnerabilities")
    parser.add_argument("--top", type=int, default=25, help="Number of images to list")
    parser.add_argument("--model", type=str, default="this-makes-no-difference-to-codegate",
                        help="Model to use. Note that if you're using CodeGate with Muxing, this parameter is ignored.")
    parser.add_argument("--api-key", type=str, default="fake-api-key",
                        help="API Key to use. Note that if you're using CodeGate with Muxing, this parameter is ignored.")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8989/v1/mux",
                        help="Base URL to use. Points to CodeGate Muxing endpoint by default.")
    # Pass notes as a file
    parser.add_argument("--notes", type=str, help="Path to a file containing notes")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--infra-repo", type=str, help="URL to your infrastructure repository")
    parser.add_argument("--infra-repo-subdir", type=str, help="Subdirectory in the repository to ingest")
    parser.add_argument("--gh-token", type=str, default="", help="GitHub PAT for the repository")
    args = parser.parse_args()

    # Read notes from file
    if args.notes:
        with open(args.notes) as f:
            notes = f.read()
    else:
        notes = ""

    do(args.top, args.model, args.api_key, args.base_url, notes)


if __name__ == "__main__":
    main()