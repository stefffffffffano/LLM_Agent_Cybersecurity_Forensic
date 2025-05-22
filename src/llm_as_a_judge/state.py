from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated


@dataclass(kw_only=True)
class State:
    """Main graph state."""
    messages: Annotated[list[AnyMessage], add_messages] #messages in the conversation
    steps: int #Maximum number of steps for the autonomous agent
    ground_truth: str #Ground truth for the event, contains the report, CVE, service etc.
    report: str #Report provided by the agent, it contains the CVE, service etc.
    done: bool = False #Flag to indicate if the agent has finished its task providing an answer
    event_id: int #Event ID for the task
    inputTokens: int = 0 #counter for the input tokens
    outputTokens: int = 0 #counter for the output tokens