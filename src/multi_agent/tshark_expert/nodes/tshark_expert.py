from typing import Any
from openai import BadRequestError 

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import BaseCallbackHandler

from multi_agent.common.tshark_expert_state import State
from multi_agent.common.configuration import Configuration
from multi_agent.common.utils import split_model_and_provider
from multi_agent.tshark_expert.tools.pcap import commandExecutor
from multi_agent.tshark_expert.tools.tshark_manual import manualSearch
from multi_agent.tshark_expert.tools.browser import web_quick_search

class PromptDebugHandler(BaseCallbackHandler):
    """
    For debug only: print the full prompt sent to the LLM.
    """
    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> None:
        print("\n================== FULL PROMPT SENT TO LLM ==================\n")
        for i, prompt in enumerate(prompts):
            print(f"--- Prompt {i+1} ---\n{prompt}\n")
        print("=============================================================\n")



def tshark_expert(state: State, config: RunnableConfig) -> dict:
    """Extract the user's state from the conversation and update the memory."""
    configurable = Configuration.from_runnable_config(config)

    # Prepare the system prompt with user memories and current time
    # This helps the model understand the context and temporal relevance
    steps = '\n'.join([f" {m.content}\n" for  m in state.messages])
    sys = configurable.tshark_expert_template.format(
        task=state.task,
        steps=steps
    )
    if state.steps == 1 or state.steps == 2:
        sys += "\nWARNING: You are not allowed to explore the PCAP anymore, you have to provide the answer with the information you gathered so far."
    message =  [{"role": "system", "content": sys}]
    debug_config = RunnableConfig(callbacks=[PromptDebugHandler()])
    #Define the LLM with the model and the provider, temperature=0 to reduce randomness
    llm = init_chat_model(**split_model_and_provider(configurable.model),temperature=0.0)
    #Add the tools to the LLM
    llm = llm.bind_tools([commandExecutor, manualSearch]) #,web_quick_search
    #Invoke the LLM with the prepared prompt (and debug config to observe the prompt)
    length_exceeded = False
    done = False
    try:
        msg = llm.invoke(
            message,
            config=debug_config,
        )
        if 'task completed' in msg.content.lower():
            done = True
    except BadRequestError as e:
        length_exceeded = True
        print(f"Error: {e}")
        msg = {"role": "assistant", "content": f"Error: {e}"}

    return {"messages": [msg],
            "steps": state.steps-1,
            "error": length_exceeded,
            "done": done,
            }