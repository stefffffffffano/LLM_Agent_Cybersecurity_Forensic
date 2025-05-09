from openai import BadRequestError 

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig


from multi_agent.common.global_state import State_global
from multi_agent.log_reporter.prompts import LOG_REPORTER_PROMPT
from multi_agent.common.configuration import Configuration
from multi_agent.log_reporter.concatenate_logs import concatenate_logs
from multi_agent.common.utils import split_model_and_provider


async def log_reporter(state: State_global, config: RunnableConfig) -> dict:
    """
    Log reporter agent that generates a report based on the logs provided.
    The report is then used by the main_agent in the following steps of the analysis.
    """

    configurable = Configuration.from_runnable_config(config)

    log_content = concatenate_logs(state.log_dir) #content of the logs
    # Final prompt for the log reporter
    system_prompt = LOG_REPORTER_PROMPT.format(
        log_content = log_content)


    llm = init_chat_model(**split_model_and_provider(configurable.model),temperature=0.0,timeout=600)

    messages = [{"role": "system", "content": system_prompt}]
    
    try:
        msg = await llm.ainvoke(messages)
    except BadRequestError as e: 
        # The input prompt is too long->specific for gpt
        final_msg = "Logs are too long, a report cannot be generated."
        return {"messages": [{"role": "system", "content": final_msg}],
            "steps": state.steps,
            "event_id": state.event_id,
            }
    except Exception as e:
        #general exception for other errors or models
        final_msg = f"An unexpected error occurred: {str(e)}"
        return {"messages": [{"role": "system", "content": final_msg}],
            "steps": state.steps,
            "event_id": state.event_id,
        }
    

    input_token_count =  msg.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
    output_token_count =  msg.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
    
    return {"messages": [msg],
            "steps": state.steps,
            "event_id": state.event_id,
            "inputTokens": input_token_count,
            "outputTokens": output_token_count,
    }


__all__ = ["log_reporter"]