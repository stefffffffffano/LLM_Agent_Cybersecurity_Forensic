import asyncio

from langgraph.store.base import BaseStore
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from multi_agent.common.utils import split_model_and_provider
from multi_agent.main_agent.tools.memory import upsert_memory_func
from multi_agent.main_agent.tools.browser import web_quick_search_func
from multi_agent.main_agent.tools.report import finalAnswerFormatter_func
from multi_agent.main_agent.tools.tshark_expert_tool import tshark_expert_func
from multi_agent.common.main_agent_state import State
from multi_agent.common.configuration import Configuration



async def tools(state: State, config: RunnableConfig, *, store: BaseStore):
    """
    Executes the tools called by the LLM.
    Allows multiple tool calls, but only one `web_quick_search` per step.
    If more than one `web_quick_search` is requested, only the first is executed,
    and an informative message is returned.
    """
    tool_calls = state.messages[-1].tool_calls
    done = False

    if not tool_calls:
        raise ValueError("No tool calls found.")

    results = []

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
            result_content = tshark_expert_func(task=task_input, pcap_path=state.pcap_path)
            results.append({
                "role": "tool",
                "content": result_content,
                "tool_call_id": first_tshark_call["id"],
            })
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
    
    
        
    return {
        "messages": results,
        "steps": state.steps - 1,
        "done": done
    }


__all__ = ["tools"]