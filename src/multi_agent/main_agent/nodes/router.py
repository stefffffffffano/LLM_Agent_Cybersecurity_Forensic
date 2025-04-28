from langgraph.graph import END
from langchain_core.messages import AIMessage

from multi_agent.common.main_agent_state import State


def route_message(state: State):
    msg = state.messages[-1]
    if state.done or state.steps <= 0:
        return END
    if isinstance(msg, AIMessage) and msg.tool_calls:
        return "tools"

    return "call_model" 
