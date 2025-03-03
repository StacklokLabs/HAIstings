import sqlite3

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver


def memory_factory(memory_type: str) -> BaseCheckpointSaver:
    if memory_type == "memory":
        return MemorySaver()
    elif memory_type == "sqlite":
        return sqlite_saver()
    else:
        raise ValueError("Invalid memory type")


def sqlite_saver() -> BaseCheckpointSaver:
    # `check_same_thread` is set to false because the connection is shared across threads.
    # This came from https://github.com/langchain-ai/langgraph/issues/1274#issuecomment-2309549811
    conn = sqlite3.connect(".haistings-checkpoints.db", check_same_thread=False)
    return SqliteSaver(conn)
