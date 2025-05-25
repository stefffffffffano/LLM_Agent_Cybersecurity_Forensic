import asyncio

from langgraph.store.base import BaseStore
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from multi_agent.common.utils import split_model_and_provider
from multi_agent.main_agent.tools.memory import upsert_memory_func
from browser import web_quick_search_func
from multi_agent.main_agent.tools.report import finalAnswerFormatter_func
from multi_agent.main_agent.tools.tshark_expert_tool import tshark_expert_func
from multi_agent.common.global_state import State_global
from configuration import Configuration



async def tools(state: State_global, config: RunnableConfig, *, store: BaseStore):
    """
    Executes the tools called by the LLM.
    Allows multiple tool calls, but only one `web_quick_search` per step.
    If more than one `web_quick_search` is requested, only the first is executed,
    and an informative message is returned. 
    In case a web call is made together with a tshark_expert call, the web call is skipped.
    """
    tool_calls = state.messages[-1].tool_calls
    done = False

    if not tool_calls:
        raise ValueError("No tool calls found.")

    results = []

    input_tokens_count = state.inputTokens
    output_tokens_count = state.outputTokens

    # Handle upsert_memory
    upsert_calls = [tc for tc in tool_calls if tc["name"] == "upsert_memory"]
    if upsert_calls:
        saved_memories = await asyncio.gather(
            *[upsert_memory_func(**tc["args"], store=store) for tc in upsert_calls]
        )
        results.extend([
            {
                "role": "tool",
                "content": mem,
                "tool_call_id": tc["id"],
            }
            for tc, mem in zip(upsert_calls, saved_memories)
        ])

    # Handle web_quick_search (only one allowed)
    web_calls = [tc for tc in tool_calls if tc["name"] == "web_quick_search"]
    tshark_calls = [tc for tc in tool_calls if tc["name"] == "tshark_expert"]
    if web_calls and not tshark_calls:
        first_web_call = web_calls[0]
        configurable = Configuration.from_runnable_config(config)
        llm = init_chat_model(**split_model_and_provider(configurable.model),timeout=100)
        query_used = first_web_call["args"].get("query", "unknown")
        
        (response,inCount,outCount) = web_quick_search_func(**first_web_call["args"], llm_model=llm, strategy=state.strategy)
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

    #Handles formatting of the final answer
    final_answer_calls = [tc for tc in tool_calls if tc["name"] == "final_answer_formatter"]
    if len(final_answer_calls) > 1:
        raise(ValueError('Final answer formatting called more than once'))
    if final_answer_calls:
        formatted_answers = [
            finalAnswerFormatter_func(**tc["args"])
            for tc in final_answer_calls
        ]
        done = True # Set the done flag to True, the multi_agent.main_agent has finished its task
        results.extend([
            {
                "role": "tool",
                "content": f"{content}",
                "tool_call_id": tc["id"],
            }
            for tc, content in zip(final_answer_calls, formatted_answers)
        ])

    # Handle tshark_expert tool
    
    if tshark_calls:
        #Just consider the first call to the tshark expert, and skip the others
        first_tshark_call = tshark_calls[0]
        # If there are multiple calls, inform the agent that you have skipped the others
        task_input = first_tshark_call["args"].get("task", "")
        if not state.pcap_path:
                result_content = "Error: No PCAP file available for Tshark Expert analysis."
        else:
            (result_content,inTokens,outTokens) = tshark_expert_func(task=task_input, pcap_path=state.pcap_path,event_id=state.event_id, call_number=state.call_number,strategy=state.strategy)
            results.append({
                "role": "tool",
                "content": result_content,
                "tool_call_id": first_tshark_call["id"],
            })
            #counting tokens generated (in and out) by the subagent 
            input_tokens_count += inTokens
            output_tokens_count += outTokens
        if(len(tshark_calls) > 1):
            skipped_calls = len(tshark_calls) - 1
            skipped_calls_content = '\n'.join([text["args"].get("task","unknown") for text in tshark_calls[1:]])
            results.append({
                "role": "tool",
                "content": f"Only one tshark_expert call is allowed per step. "
                        f"{skipped_calls} additional call(s) were skipped.\n"
                        f"Skipped call(s): {skipped_calls_content}",
                "tool_call_id": tshark_calls[1]["id"]  
            })
        if(web_calls and tshark_calls):
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


    #Handles log_analyzer calls, where the task is specified in the args 
    log_analyzer_calls = [tc for tc in tool_calls if tc["name"] == "log_analyzer"]
    if log_analyzer_calls:
        if len(log_analyzer_calls) > 1:
            raise ValueError("log_analyzer tool called more than once in the same step.")
        task = log_analyzer_calls[0]["args"].get("task", "")
        
        return {
            "steps": state.steps - 1, #Counting already decremented here
            "next_step": "log_reporter", #Next step is log_reporter
            "task": task, #Task to be executed by the log_reporter
        }


    return {
        "messages": results,
        "steps": state.steps - 1,
        "done": done,
        "inputTokens": input_tokens_count,
        "outputTokens": output_tokens_count,
        "call_number": state.call_number if not tshark_calls else state.call_number + 1, #Increment the call number only if the tshark_expert is called
    }


__all__ = ["tools"]