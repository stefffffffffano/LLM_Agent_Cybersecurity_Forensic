from multi_agent.tshark_expert.tools.pcap import commandExecutor_func
from multi_agent.tshark_expert.tools.tshark_manual import manualSearch_func
from multi_agent.common.tshark_expert_state import State
from multi_agent.common.configuration import Configuration
from multi_agent.tshark_expert.tools.browser import web_quick_search_func
from multi_agent.common.utils import split_model_and_provider

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

def tools(state: State, config: RunnableConfig) -> dict:
    """
    Executes the tools called by the LLM.
    """

    tool_calls = state.messages[-1].tool_calls
    
    if not tool_calls:
        raise ValueError("No tool calls found.")

    results = []
    
    # Handle web_quick_search (only one allowed)
    web_calls = [tc for tc in tool_calls if tc["name"] == "web_quick_search"]
    if web_calls:
        first_web_call = web_calls[0]
        configurable = Configuration.from_runnable_config(config)
        llm = init_chat_model(**split_model_and_provider(configurable.model))
        query_used = first_web_call["args"].get("query", "unknown")
        
        response = web_quick_search_func(**first_web_call["args"], llm_model=llm)
        response_with_query = (
            f"Search result for query: '{query_used}'\n{response}"
        )
        
        results.append({
            "role": "tool",
            "content": response_with_query,
            "tool_call_id": first_web_call["id"],
        })

        if len(web_calls) > 1:
            skipped_calls = len(web_calls) - 1
            skipped_calls_content = '\n'.join([text["args"].get("query","unknown") for text in web_calls[1:]])
            results.append({
                "role": "tool",
                "content": f"Only one web_quick_search is allowed per step. "
                           f"{skipped_calls} additional call(s) were skipped.\n"
                           f"Skipped call(s): {skipped_calls_content}",
                "tool_call_id": web_calls[1]["id"]  
            })


    # Handles manual search -> the LLM passes one single argument: searchString
    manual_search_calls = [tc for tc in tool_calls if tc["name"] == "manual_search"]

    if manual_search_calls:
        manual_content = [
            manualSearch_func(**tc["args"])
            for tc in manual_search_calls
        ]
        results.extend([
            {
                "role": "tool",
                "content": f"{content}",
                "tool_call_id": tc["id"],
            }
            for tc, content in zip(manual_search_calls, manual_content)
        ])

    # Handles command execution -> the LLM passes one single argument: tshark_command
    command_executor_calls = [tc for tc in tool_calls if tc["name"] == "command_executor"]

    if command_executor_calls:
        command_content = [
            commandExecutor_func(**tc["args"], pcap_file=state.pcap_path)
            for tc in command_executor_calls
        ]
        results.extend([
            {
                "role": "tool",
                "content": f"\nResult of command {tc['args']}:  {content}",
                "tool_call_id": tc["id"],
            }
            for tc, content in zip(command_executor_calls, command_content)
        ])

    
    return {
        "messages": results,
        "steps": state.steps - 1,
    }


__all__ = ["tools"]