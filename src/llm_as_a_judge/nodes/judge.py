from typing import Any
from openai import BadRequestError

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import BaseCallbackHandler

from browser import web_quick_search
from llm_as_a_judge.tools.report import judgeEvaluationFormatter
from llm_as_a_judge.state import State
from llm_as_a_judge.prompts import LLM_JUDGE_SYSTEM_PROMPT, LLM_JUDGE_USER_PROMPT_TEMPLATE
from configuration import Configuration
from multi_agent.common.utils import count_tokens, split_model_and_provider


class PromptDebugHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> None:
        print("\n================== FULL PROMPT SENT TO LLM ==================\n")
        for i, prompt in enumerate(prompts):
            print(f"--- Prompt {i+1} ---\n{prompt}\n")
        print("=============================================================\n")


async def judge_agent(state: State, config: RunnableConfig) -> dict:
    """
    Calls the LLM to evaluate the quality of a report from an autonomous agent
    against a ground truth, acting as a cybersecurity judge.
    """

    configurable = Configuration.from_runnable_config(config)
    MAX_TOKENS = configurable.max_fifo_tokens + configurable.max_working_context_tokens

    # Context window management (FIFO)
    token_counter = 0
    messages_to_be_included = 0
    for m in reversed(state.messages):
        tok = count_tokens(m)
        if token_counter + tok < MAX_TOKENS:
            token_counter += tok
            messages_to_be_included += 1
        else:
            break

    fifo_messages = state.messages[-messages_to_be_included:]
    queue_lines = [f"Message number {i+1}: {m.content}" for i, m in enumerate(fifo_messages)]
    queue_str = "\n".join(queue_lines)

    # Construct user prompt with reports
    user_prompt = LLM_JUDGE_USER_PROMPT_TEMPLATE.format(
        agent_report=state.agent_report,
        ground_truth=state.ground_truth,
        queue=queue_str
    )

    # Optional forced response at last step
    system_prompt = LLM_JUDGE_SYSTEM_PROMPT.strip()
    if state.steps in (2, 3):
        system_prompt += "\n\nWARNING: You are not allowed to reason anymore. Provide your final evaluation now based on the information available."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    llm = init_chat_model(**split_model_and_provider(configurable.model), temperature=0.0, timeout=200)
    llm_with_tools = llm.bind_tools([web_quick_search, judgeEvaluationFormatter])
    debug_config = RunnableConfig(callbacks=[PromptDebugHandler()])

    length_exceeded = False

    try:
        msg = await llm_with_tools.ainvoke(messages, config=debug_config)
    except BadRequestError as e:
        length_exceeded = True
        print(f"Error: {e}")
        msg = {"role": "assistant", "content": f"Error: {e}"}
    except Exception as e:
        final_msg = f"An unexpected error occurred: {str(e)}"
        return {
            "messages": [{"role": "system", "content": final_msg}],
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

    return {
        "messages": [msg],
        "steps": state.steps - 1,
        "done": length_exceeded,
        "inputTokens": input_token_count,
        "outputTokens": output_token_count
    }


__all__ = ["judge_agent"]
