from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from multi_agent.common.utils import split_model_and_provider
from browser import web_quick_search_func
from llm_as_a_judge.tools.report import judgeEvaluationFormatter_func

from llm_as_a_judge.state import State
from configuration import Configuration


async def tools(state: State, config: RunnableConfig):
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

    # Handle web_quick_search (only one allowed)
    web_calls = [tc for tc in tool_calls if tc["name"] == "web_quick_search"]
    if web_calls:
        first_web_call = web_calls[0]
        configurable = Configuration.from_runnable_config(config)
        llm = init_chat_model(**split_model_and_provider(configurable.model),timeout=100)
        query_used = first_web_call["args"].get("query", "unknown")
        
        # In this case we consider only LLM summary as strategy, chunking not considered
        (response,inCount,outCount) = web_quick_search_func(**first_web_call["args"], llm_model=llm, research="judge",context_window_size= configurable.context_window_size)
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
            judgeEvaluationFormatter_func(**tc["args"])
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
        
    return {
        "messages": results,
        "steps": state.steps - 1,
        "done": done,
        "inputTokens": input_tokens_count,
        "outputTokens": output_tokens_count,
    }


__all__ = ["tools"]