import argparse
import json
import os
import re
import sys
from typing import List

if not os.environ.get("USER_AGENT"):
    # TODO: replace with proper version.
    os.environ["USER_AGENT"] = "HAIstings/0.0.1"

from enum import Enum

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, MessagesState, StateGraph

from haistings import prompts
from haistings.k8sreport import ReportResult, gatherVulns
from haistings.memory import memory_factory
from haistings.repo_ingest import ingest, retrieve_relevant_files
from haistings.vector_db import build_query_from_report_result

rt = None


class ContinueConversation(Enum):
    YES = "yes"
    NO = "no"
    UNSURE = "unsure"


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
    # ingested_repo is the infra repository that was ingested.
    ingested_repo: str
    answer: str
    continue_conversation: ContinueConversation = ContinueConversation.UNSURE


class HAIstingsRuntime:

    def __init__(
        self,
        top: int,
        model: str,
        model_provider: str,
        api_key: str,
        base_url: str,
        repo_url: str = None,
        repo_subdir: str = None,
        gh_token: str = None,
        use_vectordb: bool = True,
        max_relevant_files: int = 5,
    ):
        # This is not dynamic anymore as we want to access
        # The history of the conversation via the checkpointer.
        tid = "haistings-bot-thread"
        self.rtconfig = {
            "configurable": {
                "thread_id": tid,
                "checkpoint_ns": "",
            },
        }
        # Store the top value for use in the retrieve function
        self.top = top
        self.repo_url = repo_url
        self.use_vectordb = use_vectordb
        self.max_relevant_files = max_relevant_files

        ## TODO: Make this configurable
        self.report = lambda: gatherVulns()
        self.ingest_repo = lambda: ingest(gh_token, repo_url, repo_subdir, use_vectordb=use_vectordb)
        self.llm = init_chat_model(
            # We're using CodeGate's Muxing feature. No need to select a model here.
            model,
            model_provider=model_provider,
            # We're using CodeGate, no need to get an API Key here.
            api_key=api_key,
            # CodeGate Muxing API URL
            base_url=base_url,
        )

        # Define prompt
        self.kickoff_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", prompts.ASSISTANT_PROMPT),
                # Kicks off the conversation
                ("user", prompts.KICKOFF_USER_QUESTION),
            ],
        )

    def llm_invoke_with_streaming_print(self, messages: List[BaseMessage]) -> AIMessage:
        msgid: str = ""
        fullmsg: str = ""
        thinking: bool = False

        for chunk in self.llm.stream(messages, config=rt.rtconfig):
            if not msgid:
                # All messages from the stream are part of the same run.
                msgid = chunk.id
            # We store the raw message content for the response.
            fullmsg += chunk.content

            printable = preprocess_token(chunk.content, thinking)
            if printable.thinking_token_in_stream == ThinkingTokenInStream.BEGIN:
                print("* Thinking...")
                thinking = True
            elif printable.thinking_token_in_stream == ThinkingTokenInStream.END:
                print("* ...Done")
                print(text_separator())
                thinking = False

            if not thinking:
                print(printable.output_token, end="")

        return AIMessage(id=msgid, content=fullmsg)


# Define application steps
def retrieve(state: State):
    if len(state["messages"]) > 0:
        return {}

    report_result = rt.report()
    report = report_result.buildreport(rt.top)  # Using the top value from HAIstingsRuntime

    # Get repository context if configured in runtime
    ingested_repo = ""

    try:
        summary, tree, content = rt.ingest_repo()

        if rt.use_vectordb and rt.repo_url:
            # Use vector database to retrieve relevant files
            ingested_repo = get_relevant_files_for_report(report_result, rt.repo_url, rt.max_relevant_files)
        else:
            # Use traditional approach
            ingested_repo = f"""Repository Context:
    Summary: {summary}
    Structure: {tree}
    Content: {content}"""

        print("Ingested repository successfully.")
    except Exception as e:
        print(f"Warning: Failed to ingest repository: {e}", file=sys.stderr)

    return {"infrareport": report, "ingested_repo": ingested_repo}


def get_relevant_files_for_report(report_result: ReportResult, repo_url: str, max_files: int = 5) -> str:
    """Get relevant files for the report using the vector database.

    Args:
        report_result: The ReportResult object
        repo_url: URL of the repository
        max_files: Maximum number of files to include per component

    Returns:
        A string containing the relevant files
    """
    if not report_result or not report_result.images_with_vulns:
        return ""

    # Get the top vulnerable images
    top_images = sorted(report_result.images_with_vulns, reverse=True)[:10]

    all_relevant_files = []

    # For each image, retrieve relevant files
    for img in top_images:
        # Extract component name from image
        component_name = img.img.split("/")[-1]

        # Build query from the image
        query = build_query_from_report_result(report_result, component_name)

        # Retrieve relevant files
        relevant_files = retrieve_relevant_files(repo_url, query, k=max_files)

        if relevant_files:
            all_relevant_files.append({"component": component_name, "files": relevant_files})

    # Format the output
    if not all_relevant_files:
        return ""

    output = "Repository Context:\n"
    output += f"Summary: Retrieved {sum(len(comp['files']) for comp in all_relevant_files)} relevant files for {len(all_relevant_files)} components\n\n"

    for component_data in all_relevant_files:
        component = component_data["component"]
        files = component_data["files"]

        output += f"Component: {component}\n"

        for file in files:
            output += f"  File: {file['path']}\n"
            output += (
                f"  Content:\n```\n{file['content'][:1000]}{'...' if len(file['content']) > 1000 else ''}\n```\n\n"
            )

    return output


def generate_initial(state: State):
    # Revisit the previous conversation
    if len(state["messages"]) > 0:
        messages = state["messages"] + [HumanMessage(prompts.CONTINUE_FROM_CHECKPOINT)]
    else:
        if state["ingested_repo"]:
            file_context = prompts.DEPLOYMENT_FILE_CONTEXT.format(ingested_repo=state["ingested_repo"])
        else:
            file_context = ""
        messages = rt.kickoff_prompt.invoke(
            {
                "context": state["infrareport"],
                "question": state["question"],
                "usercontext": state["usercontext"],
                "deployment_file_context": file_context,
            }
        ).to_messages()

    response = rt.llm_invoke_with_streaming_print(messages)

    return {
        "messages": messages + [response],
        "answer": response.content,
    }


def extra_userinput(state: State):
    """Based on the user input, the assistant will provide a response."""
    messages = state["messages"]
    inputmsg = (
        text_separator()
        + """
Is there more information needed? Note that more information will help the assistant provide a better response.

> """
    )
    extra = input(inputmsg)

    print(text_separator())

    try:
        response = rt.llm.invoke(prompts.USER_RESPONSE_CATEGORIZATION % extra, config=rt.rtconfig)
        processed = strip_code_markdown(preprocess_response(response.content))
        resp = json.loads(processed)
        continue_conversation = ContinueConversation(resp["continue_conversation"])
    except Exception:
        continue_conversation = continue_conversation = ContinueConversation.YES

    exp = resp["explanation"]
    print(f"* {exp}")

    if continue_conversation == ContinueConversation.NO:
        print("* Finishing the conversation...\n\n* Cheers!")
        return {
            "messages": messages,
            "answer": exp,
            "continue_conversation": continue_conversation,
        }
    elif continue_conversation == ContinueConversation.UNSURE:
        print(
            "The idea is to add more context on the given infrastructure to "
            "help the assistant provide a better response.\n\n"
            "You can also provide more context on the vulnerabilities "
            "as well as override the priorization based on the new context."
        )
        return {
            "messages": messages,
            "answer": "The user is unsure about continuing the conversation.",
            "continue_conversation": continue_conversation,
        }

    prompt = ChatPromptTemplate.from_messages(
        [
            ("user", prompts.PROVIDE_EXTRA_CONTEXT),
        ]
    )

    prompt_msg = prompt.invoke({"extra": extra})
    messages = messages + prompt_msg.to_messages()

    response = rt.llm_invoke_with_streaming_print(messages)

    return {
        "messages": prompt_msg.to_messages() + [response],
        "answer": response.content,
        "continue_conversation": continue_conversation,
    }


def needs_more_info(state: State):
    if state["continue_conversation"] == ContinueConversation.NO:
        return END
    return "extra_userinput"


def text_separator() -> str:
    return "\n" + "=" * 120


class ThinkingTokenInStream(Enum):
    BEGIN = 1
    END = 2
    NONE = 3


class TokenStreamProcessing:
    def __init__(self, output_token, ThinkingTokenInStream):
        self.output_token = output_token
        self.thinking_token_in_stream = ThinkingTokenInStream


def preprocess_token(response: str, processing_thinking: bool) -> TokenStreamProcessing:
    """Preprocess single-token response coming from an LLM.

    In this case, it'll search for thinking tokens and remove them."""
    if "<think>" in response:
        return TokenStreamProcessing("", ThinkingTokenInStream.BEGIN)
    elif "</think>" in response:
        return TokenStreamProcessing("", ThinkingTokenInStream.END)
    elif processing_thinking:
        return TokenStreamProcessing("", ThinkingTokenInStream.NONE)
    else:
        return TokenStreamProcessing(response, ThinkingTokenInStream.NONE)


def preprocess_response(response: str) -> str:
    """Preprocesses the response coming from an LLM.

    In this case, it'll only search for thinking tokens and remove them."""

    # Remove thinking tokens. These are all the characters between the <think> and </think> tags
    # Note that we have to match multiline strings
    # DOTALL makes '.' match newlines as well
    pattern = r"<think>.*?</think>"
    return re.sub(pattern, "", response, flags=re.DOTALL)


def strip_code_markdown(text: str) -> str:
    """Strips code markdown tags from a text."""
    return re.sub(r"```\w+?\n(.*?)```", r"\1", text, flags=re.DOTALL)


def do(
    top: int,
    model: str,
    model_provider: str,
    api_key: str,
    base_url: str,
    notes: str,
    checkpointer_driver: str,
    repo_url: str = None,
    repo_subdir: str = None,
    gh_token: str = None,
    use_vectordb: bool = True,
    max_relevant_files: int = 5,
):
    global rt

    rt = HAIstingsRuntime(
        top, model, model_provider, api_key, base_url, repo_url, repo_subdir, gh_token, use_vectordb, max_relevant_files
    )

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
    graph_builder.add_conditional_edges("extra_userinput", needs_more_info, ["extra_userinput", END])

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
    for chunk in graph.stream(
        {
            "question": kickoff_question,
            "usercontext": notes,
        },
        config=rt.rtconfig,
        stream_mode="messages",
    ):
        pass


def main():
    parser = argparse.ArgumentParser(description="Prioritize container image updates based on vulnerabilities")
    parser.add_argument("--top", type=int, default=25, help="Number of images to list")
    parser.add_argument(
        "--model",
        type=str,
        default="this-makes-no-difference-to-codegate",
        help="Model to use. Note that if you're using CodeGate with Muxing, this parameter is ignored.",
    )
    parser.add_argument(
        "--model-provider",
        type=str,
        default="openai",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="fake-api-key",
        help="API Key to use. Note that if you're using CodeGate with Muxing, this parameter is ignored.",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8989/v1/mux",
        help="Base URL to use. Points to CodeGate Muxing endpoint by default.",
    )
    # Pass notes as a file
    parser.add_argument("--notes", type=str, help="Path to a file containing notes")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--infra-repo", type=str, help="URL to your infrastructure repository")
    parser.add_argument("--infra-repo-subdir", type=str, help="Subdirectory in the repository to ingest")
    parser.add_argument("--gh-token", type=str, default="", help="GitHub PAT for the repository")

    # Persistence
    parser.add_argument(
        "--checkpoint-saver-driver",
        type=str,
        default="memory",
        choices=["memory", "sqlite"],
        help="Checkpoint saver driver to use",
    )

    # Vector database options
    parser.add_argument(
        "--use-vectordb",
        action="store_true",
        default=True,
        help="Use vector database for repository ingestion (default: True)",
    )
    parser.add_argument(
        "--max-relevant-files",
        type=int,
        default=5,
        help="Maximum number of relevant files to include per component (default: 5)",
    )

    args = parser.parse_args()

    # Read notes from file
    if args.notes:
        with open(args.notes) as f:
            notes = f.read()
    else:
        notes = ""

    do(
        args.top,
        args.model,
        args.model_provider,
        args.api_key,
        args.base_url,
        notes,
        args.checkpoint_saver_driver,
        args.infra_repo,
        args.infra_repo_subdir,
        args.gh_token,
        args.use_vectordb,
        args.max_relevant_files,
    )


if __name__ == "__main__":
    main()
