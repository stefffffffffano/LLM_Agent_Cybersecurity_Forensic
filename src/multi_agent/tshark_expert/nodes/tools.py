from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from multi_agent.tshark_expert.tools.pcap import commandExecutor_func
from multi_agent.common.tshark_expert_state import State_tshark_expert
from multi_agent.tshark_expert.tools.report import finalAnswerFormatter_func
from multi_agent.common.utils import split_model_and_provider
from multi_agent.common.browser import web_quick_search_func
from multi_agent.common.configuration import Configuration

def tools(state: State_tshark_expert,config: RunnableConfig,) -> dict:
    """
    Executes the tools called by the LLM.
    Allows multiple tool calls, but only one `web_quick_search` per step.
    If more than one `web_quick_search` is requested, only the first is executed.
    In case a web call is made together with a tshark_expert call, the web call is skipped.
    """

    input_tokens_count = state.inputTokens
    output_tokens_count = state.outputTokens

    tool_calls = state.messages[-1].tool_calls
    
    if not tool_calls:
        raise ValueError("No tool calls found.")

    results = []
    # Handle web_quick_search (only one allowed)
    web_calls = [tc for tc in tool_calls if tc["name"] == "web_quick_search"]
    command_executor_calls = [tc for tc in tool_calls if tc["name"] == "command_executor"]

    if web_calls and not command_executor_calls:
        first_web_call = web_calls[0]
        configurable = Configuration.from_runnable_config(config)
        llm = init_chat_model(**split_model_and_provider(configurable.model),timeout=100)
        query_used = first_web_call["args"].get("query", "unknown")
        
        (response,inCount,outCount) = web_quick_search_func(**first_web_call["args"], llm_model=llm, research="tshark", strategy=state.strategy)
        input_tokens_count += inCount
        output_tokens_count += outCount 
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

    # Handles command execution -> the LLM passes one single argument: tshark_command
    if command_executor_calls:
        first_call = command_executor_calls[0]
        content = commandExecutor_func(**first_call["args"], pcap_file=state.pcap_path)
        results.append({
            "role": "tool",
            "content": f"\nResult of command {first_call['args']}:  {content}",
            "tool_call_id": first_call["id"],
        })

        if(len(command_executor_calls) > 1):
            skipped_calls = len(command_executor_calls) - 1
            skipped_calls_content = '\n'.join([text["args"].get("task","unknown") for text in command_executor_calls[1:]])
            results.append({
                "role": "tool",
                "content": f"Only one command executor call is allowed per step. "
                        f"{skipped_calls} additional call(s) were skipped.\n"
                        f"Skipped call(s): {skipped_calls_content}",
                "tool_call_id": command_executor_calls[1]["id"]  
            })
        if(web_calls and command_executor_calls):
            #web search calls skipped, advise the agent
            skipped_calls = len(web_calls) 
            skipped_calls_content = '\n'.join([text["args"].get("query","unknown") for text in web_calls])
            results.append({
                "role": "tool",
                "content": f"You cannot call web_quick_search and tshark_expert in the same step. "
                        f"{skipped_calls} call(s) were skipped.\n"
                        f"Skipped call(s): {skipped_calls_content}",
                "tool_call_id": web_calls[0]["id"]  
            })


    #Handles final answer formatter
    final_answer_calls = [tc for tc in tool_calls if tc["name"] == "final_answer_formatter"]
    if(len(final_answer_calls) > 1):
        raise ValueError("Only one final answer formatter call is allowed.")
    final_answer_call = final_answer_calls[0] if final_answer_calls else None
    if final_answer_calls:
        final_answer_content = finalAnswerFormatter_func(**final_answer_call["args"],pcap_file=state.pcap_path)
        
        results.extend([
            {
                "role": "tool",
                "content": f"{final_answer_content}",
                "tool_call_id": final_answer_call["id"],
            }
        ])
        return {
            "messages": results,
            "steps": state.steps - 1,
            "done": True,
        }
    
    return {
        "messages": results,
        "steps": state.steps - 1,
        "inputTokens": input_tokens_count,
        "outputTokens": output_tokens_count,
    }


__all__ = ["tools"]