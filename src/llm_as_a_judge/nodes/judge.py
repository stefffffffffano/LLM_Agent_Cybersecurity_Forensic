from typing import Any
from openai import BadRequestError 


from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import BaseCallbackHandler


from multi_agent.common.browser import web_quick_search
from llm_as_a_judge.tools.report import judgeEvaluationFormatter


from llm_as_a_judge.state import State
from llm_as_a_judge.prompts import LLM_JUDGE_TEMPLATE
from multi_agent.common.configuration import Configuration
from multi_agent.common.utils import count_tokens, split_model_and_provider


class PromptDebugHandler(BaseCallbackHandler):
    """
    For debug only: print the full prompt sent to the LLM.
    """
    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> None:
        print("\n================== FULL PROMPT SENT TO LLM ==================\n")
        for i, prompt in enumerate(prompts):
            print(f"--- Prompt {i+1} ---\n{prompt}\n")
        print("=============================================================\n")



async def judge(state: State, config: RunnableConfig) -> dict:
    """
    Main graph node: calls the LLM with the current state. It manages the context window to ensure not overcoming it.
     
    Based on the context, the LLM may decide to call tools or not.
    Description of tools is provided when they are bounded to the LLM itself in json format.
    """

    configurable = Configuration.from_runnable_config(config)
    MAX_TOKENS = configurable.max_fifo_tokens + configurable.max_working_context_tokens

    token_counter = 0
    messages_to_be_included = 0
    for m in reversed(state.messages):  # reversed to collect latest messages
        tok = count_tokens(m)
        if token_counter + tok < MAX_TOKENS:
            token_counter += tok
            messages_to_be_included += 1
        else:
            break

    fifo_messages = state.messages[-messages_to_be_included:]
    
    # FIFO as string->messages are counted to give a context of the flow to the LLM 
    queue_lines = [f"Message number {i+1}: {m.content}" for i, m in enumerate(fifo_messages)]
    queue_str = "\n".join(queue_lines)

    # Final prompt
    system_prompt = LLM_JUDGE_TEMPLATE.format(
        queue=queue_str
    )

    llm = init_chat_model(**split_model_and_provider(configurable.model),temperature=0.0,timeout=200)
    debug_config = RunnableConfig(callbacks=[PromptDebugHandler()])
    llm_with_tools = llm.bind_tools([web_quick_search,judgeEvaluationFormatter])
    #When it's the last iteration, concatenate a message saying that it has to provide an 
    #answer
    if state.steps == 2 or state.steps==3: #1 step this iteration, 1 for tools: 2 in total
        system_prompt += "\nWARNING: You are not allowed to reason anymore, you have to provide the report with the information you gathered so far."
    messages = [{"role": "system", "content": system_prompt}]
    length_exceeded = False
    
    try:
        msg = await llm_with_tools.ainvoke(messages, config=debug_config)
    except BadRequestError as e:
        #The input prompt is too long->specific for gpt
        length_exceeded = True
        print(f"Error: {e}")
        msg = {"role": "assistant", "content": f"Error: {e}"}
    except Exception as e:
        #general exception for other errors or models
        final_msg = f"An unexpected error occurred: {str(e)}"
        return {"messages": [{"role": "system", "content": final_msg}],
            "length_exceeded": length_exceeded,
            "steps": state.steps,
            "event_id": state.event_id,
        }

    if not length_exceeded:
        input_token_count = state.inputTokens + msg.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
        output_token_count = state.outputTokens + msg.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
    else:
        input_token_count = 0
        output_token_count = 0

    return {"messages": [msg],
            "steps": state.steps - 1,
            "done": length_exceeded,
            "inputTokens": input_token_count,
            "outputTokens": output_token_count
    }

__all__ = ["judge"]