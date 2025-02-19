import argparse
import os
import sys
import tempfile


if not os.environ.get("USER_AGENT"):
    # TODO: replace with proper version.
    os.environ["USER_AGENT"] = "HAIstings/0.0.1"

from gitingest import ingest
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import START, END, StateGraph, MessagesState
from pydantic import BaseModel, Field
from enum import Enum
from uuid import uuid4
import git

from haistings.k8sreport import buildVulnerabilityReport
from haistings.memory import memory_factory

rt = None


class ContinueConversation(Enum):
    YES = "yes"
    NO = "no"
    UNSURE = "unsure"


class ExtraInfoOrStop(BaseModel):
    """Extra information or stop the conversation."""
    explanation: str = Field(
        description="The agent's explanation for the decision")
    continue_conversation: ContinueConversation = Field(
        description="Indicates if the user wants to provider more context, "
        "conversation or get more guidance")


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
    continue_conversation: ContinueConversation = ContinueConversation.UNSURE


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

    def __init__(self, top: int, model: str, model_provider: str, api_key: str, base_url: str):
        # This is not dynamic anymore as we want to access
        # The history of the conversation via the checkpointer.
        tid = "haistings-bot-thread"
        self.rtconfig = {
            "configurable": {
                "thread_id": tid,
                "checkpoint_ns": "",
            },
        }
        ## TODO: Make this configurable
        self.report = lambda: buildVulnerabilityReport(top)
        self.llm = init_chat_model(
            # We're using CodeGate's Muxing feature. No need to select a model here.
            model,
            model_provider=model_provider,
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


# Define application steps
def retrieve(state: State):
    if len(state["messages"]) > 0:
        return {}

    report = rt.report()
    return {"infrareport": report}


def generate_initial(state: State):
    # Revisit the previous conversation
    if len(state["messages"]) > 0:
        messages = state["messages"] + \
           [HumanMessage("Given all the context available, especially the extra "
                         "context provided by the system administrator, "
                         "Can you generate another prioritized report?")]
    else:
        messages = rt.kickoff_prompt.invoke({
            "context": state["infrareport"],
            "question": state["question"],
            "usercontext": state["usercontext"]
        }).to_messages()
    response = rt.llm.invoke(messages, config=rt.rtconfig)
    print(response.content)

    return {
        "messages": messages + [response],
        "answer": response.content,
    }


def extra_userinput(state: State):
    """Based on the user input, the assistant will provide a response."""
    messages = state["messages"]
    inputmsg = text_separator() + """
Is there more information needed? Note that more information will help the assistant provide a better response.

> """
    extra = input(inputmsg)

    print(text_separator())

    structured_llm = rt.llm.with_structured_output(ExtraInfoOrStop)
    try:
        eios = structured_llm.invoke("""
    Based on the following text: \"{extra}\"
    Does the user want to provide more information or stop the conversation?

    Before this, the user was given a priority list of components and their vulnerabilities,
    and this tool is meant to help you prioritize.

    statements such as \"no\" or \"exit\" would indicate that 
    the user wants to end the conversation.

    If the user asks a question or indicates they're not sure, then it means
    they're unsure. Note that this is explicitly only when they ask
    questions about this tool, and not a software component.

    If the user talks about some infrastructure component, changes in priorization
    or provides more context, then it means they want to provide more information
    and want to continue the conversation. The user might also want to stop
    showing a component from the list, that would also mean they want to
    continue the conversation.
    """.format(extra=extra),
            config=rt.rtconfig)
    except Exception:
        eios = ExtraInfoOrStop(
            explanation="Overriding this to continue due to LLM error",
            continue_conversation=ContinueConversation.YES,
        )

    if eios.continue_conversation == ContinueConversation.NO:
        return {
            "messages": messages,
            "answer": "The user has decided to stop the conversation.",
            "continue_conversation": eios.continue_conversation,
        }
    elif eios.continue_conversation == ContinueConversation.UNSURE:
        print("The idea is to add more context on the given infrastructure to "
              "help the assistant provide a better response.\n\n"
              "You can also provide more context on the vulnerabilities "
              "as well as override the priorization based on the new context.")
        return {
            "messages": messages,
            "answer": "The user is unsure about continuing the conversation.",
            "continue_conversation": eios.continue_conversation,
        }

    prompt = ChatPromptTemplate.from_messages([
        ("user", "Here's extra context to help with the prioritization by the system administrator:\n\n"
                 "{extra}.\n\n"
                 "Given this new information, can you provide a better response?"),
    ])

    prompt_msg = prompt.invoke({"extra": extra})
    messages = messages + prompt_msg.to_messages()

    response = rt.llm.invoke(messages, config=rt.rtconfig)
    print(response.content)
    return {
        "messages": prompt_msg.to_messages() + [response],
        "answer": response.content,
        "continue_conversation": eios.continue_conversation
    }


def needs_more_info(state: State):
    if state["continue_conversation"] == ContinueConversation.NO:
        return END
    return "extra_userinput"


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


def text_separator() -> str:
    return "\n\n" + "=" * 120


def do(top: int, model: str, model_provider: str, api_key: str, base_url: str, notes: str, checkpointer_driver: str):
    global rt

    rt = HAIstingsRuntime(top, model, model_provider, api_key, base_url)

    # Add memory
    memory = memory_factory(checkpointer_driver)

    graph_builder = StateGraph(State)
    # Nodes
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("generate_initial", generate_initial)
    graph_builder.add_node("extra_userinput", extra_userinput)

    # Edges
    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "generate_initial")
    graph_builder.add_edge("generate_initial", "extra_userinput")

    # allow for finishing execution after extra user input.
    graph_builder.add_conditional_edges(
        "extra_userinput",
        needs_more_info,
        ["extra_userinput", END]
    )

    # Compile the graph
    graph = graph_builder.compile(checkpointer=memory)

    # Determine if we can continue from a previous state
    all_states = [s for s in graph.get_state_history(rt.rtconfig)]

    if len(all_states) >= 1:
        # Override the configuration with the last state
        rt.rtconfig = all_states[0].config
        print("Starting from checkpoint: {}".format(rt.rtconfig["configurable"]["checkpoint_id"]))

    kickoff_question = "What are the top vulnerabilities in the infrastructure?"

    # Start the conversation
    for chunk in graph.stream({
        "question": kickoff_question,
        "usercontext": notes,
    }, config=rt.rtconfig, stream_mode="messages"):
        pass


def main():
    parser = argparse.ArgumentParser(description="Prioritize container image updates based on vulnerabilities")
    parser.add_argument("--top", type=int, default=25, help="Number of images to list")
    parser.add_argument("--model", type=str, default="this-makes-no-difference-to-codegate",
                        help="Model to use. Note that if you're using CodeGate with Muxing, this parameter is ignored.")
    parser.add_argument("--model-provider", type=str, default="openai",)
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

    # Persistence
    parser.add_argument("--checkpoint-saver-driver", type=str, default="memory",
                        choices=["memory", "sqlite"],
                        help="Checkpoint saver driver to use")
    args = parser.parse_args()

    # Read notes from file
    if args.notes:
        with open(args.notes) as f:
            notes = f.read()
    else:
        notes = ""

    do(args.top, args.model, args.model_provider, args.api_key, args.base_url, notes, args.checkpoint_saver_driver)


if __name__ == "__main__":
    main()