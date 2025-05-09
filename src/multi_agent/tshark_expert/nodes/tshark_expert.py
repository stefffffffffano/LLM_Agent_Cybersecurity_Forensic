from typing import Any
from openai import BadRequestError

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import BaseCallbackHandler

from multi_agent.common.tshark_expert_state import State_tshark_expert
from multi_agent.common.utils import count_tokens
from multi_agent.common.configuration import Configuration
from multi_agent.common.utils import split_model_and_provider
from multi_agent.tshark_expert.tools.pcap import commandExecutor
from multi_agent.tshark_expert.tools.tshark_manual import manualSearch
from multi_agent.tshark_expert.tools.report import finalAnswerFormatter
from multi_agent.main_agent.tools.pcap import generate_summary

MAX_TOKENS = 120000
 

class PromptDebugHandler(BaseCallbackHandler):
    """
    For debug only: print the full prompt sent to the LLM.
    """
    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> None:
        print("\n================== FULL PROMPT SENT TO LLM ==================\n")
        for i, prompt in enumerate(prompts):
            print(f"--- Prompt {i+1} ---\n{prompt}\n")
        print("=============================================================\n")



def tshark_expert(state: State_tshark_expert, config: RunnableConfig) -> dict:
    """Extract the user's state from the conversation and update the memory."""
    configurable = Configuration.from_runnable_config(config)

    #Count how many messages you can include, in order not to overcome the context window
    fifo_token_counter = 0
    fifo_messages_to_be_included = 0
    for m in reversed(state.messages):  # reversed to collect latest messages
        tok = count_tokens(m)
        if fifo_token_counter + tok < MAX_TOKENS:
            fifo_token_counter += tok
            fifo_messages_to_be_included += 1
        else:
            break

    fifo_messages = state.messages[-fifo_messages_to_be_included:]   
    queue_lines = [f"Message number {i+1}: {m.content}" for i, m in enumerate(fifo_messages)]
    queue_str = "\n".join(queue_lines)

    sys = configurable.tshark_expert_template.format(
        pcap_content=generate_summary(state.pcap_path),
        task=state.task,
        steps=queue_str
    )
    if state.steps == 2 or state.steps == 3:
        sys += "\nWARNING: You are not allowed to explore the PCAP anymore, you have to provide the answer with the information you gathered so far."
    message =  [{"role": "system", "content": sys}]
    debug_config = RunnableConfig(callbacks=[PromptDebugHandler()])
    #Define the LLM with the model and the provider, temperature=0 to reduce randomness
    llm = init_chat_model(**split_model_and_provider(configurable.model),temperature=0.0,request_timeout=30)
    #Add the tools to the LLM
    llm = llm.bind_tools([commandExecutor, manualSearch,finalAnswerFormatter]) 
    #Invoke the LLM with the prepared prompt (and debug config to observe the prompt)
    length_exceeded = False
    try:
        msg = llm.invoke(message, config=debug_config)
    except BadRequestError as e:
        length_exceeded = True
        print(f"Error: {e}")
        msg = {"role": "assistant", "content": f"Error: {e}"}
    except Exception as e:
        print(f"Error: {e}")
        print("TimeoutError: subagent's LLM call took too long!")
        return {"messages": [], #Empty message to avoid confusion
                "steps": state.steps, #Step is not counted
                }
    if not length_exceeded:
        input_token_count = state.inputTokens + msg.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
        output_token_count = state.outputTokens + msg.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
    else:
        input_token_count = 0
        output_token_count = 0
    return {"messages": [msg],
            "steps": state.steps-1,
            "error": length_exceeded,
            "inputTokens" : input_token_count,
            "outputTokens": output_token_count
            }