# log_reporter_agent.py
from openai import BadRequestError
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from multi_agent.common.main_agent_state import State
from multi_agent.common.configuration import Configuration
from multi_agent.log_reporter.concatenate_logs import concatenate_logs
from multi_agent.common.utils import split_model_and_provider
from multi_agent.log_reporter.prompts import (
    LOG_REPORTER_SYSTEM_PROMPT_NO_TASK,
    LOG_REPORTER_USER_PROMPT,
)


async def log_reporter(state: State, config: RunnableConfig) -> dict:
    """
    Log reporter agent that generates a report based on the logs provided.
    The report is then used by the main_agent in the following steps of the analysis.

    Here there's no check on the context window size, as the agent cannot work on partial logs.
    If the agent fails because logs are too long, then log_reporter is useless in that case (an error will always be returned).
    """

    configurable = Configuration.from_runnable_config(config)

    log_content = concatenate_logs(state.log_dir)

    system_prompt = LOG_REPORTER_SYSTEM_PROMPT_NO_TASK.strip()
    user_prompt = LOG_REPORTER_USER_PROMPT.format(
        log_content=log_content
    )

    llm = init_chat_model(
        **split_model_and_provider(configurable.model),
        temperature=0.0,
        timeout=200
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        msg = await llm.ainvoke(messages)
    except BadRequestError:
        final_msg = "Logs are too long, a report cannot be generated."
        return {
            "messages": [{"role": "system", "content": final_msg}],
            "steps": state.steps,
            "event_id": state.event_id
        }
    except Exception as e:
        final_msg = f"An unexpected error occurred: {str(e)}"
        return {
            "messages": [{"role": "system", "content": final_msg}],
            "steps": state.steps,
            "event_id": state.event_id
        }

    input_token_count = msg.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
    output_token_count = msg.response_metadata.get("token_usage", {}).get("completion_tokens", 0)

    return {
        "messages": [msg],
        "steps": state.steps,
        "event_id": state.event_id,
        "inputTokens": input_token_count,
        "outputTokens": output_token_count,
    }


__all__ = ["log_reporter"]
