from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated


@dataclass(kw_only=True)
class State:
    """Main graph state."""
    messages: Annotated[list[AnyMessage], add_messages]
    """The messages in the conversation."""
    steps: int #Maximum number of steps for the autonomous agent
    pcap_path: str #Path to the pcap file
    log_path: str #Path to the log file
    done: bool = False #Flag to indicate if the agent has finished its task providing an answer
    