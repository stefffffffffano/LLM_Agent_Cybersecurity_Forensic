from langgraph.graph import END
from langchain_core.messages import AIMessage

from llm_as_a_judge.state import State


def route_message(state: State):
    """Determine the next step based on the presence of tool calls."""
    if len(state.messages) == 0:
        #return the initial node if there are no messages
        return "judge"
    msg = state.messages[-1]
    if state.done or state.steps <= 0:
        return END
    if isinstance(msg, AIMessage) and msg.tool_calls:
        return "tools"

    return "judge" 