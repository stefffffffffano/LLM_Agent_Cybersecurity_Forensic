from typing import Any
from openai import BadRequestError 

from langgraph.store.base import BaseStore
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import BaseCallbackHandler

from multi_agent.main_agent.tools.memory import upsert_memory
from multi_agent.main_agent.tools.browser import web_quick_search
from multi_agent.main_agent.tools.pcap import generate_summary 
from multi_agent.main_agent.tools.report import finalAnswerFormatter
from multi_agent.main_agent.tools.tshark_expert_tool import tshark_expert
from multi_agent.common.global_state import State_global
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



async def main_agent(state: State_global, config: RunnableConfig,*,store:BaseStore) -> dict:
    """
    Main graph node: calls the LLM with the current state. It manages the context window and the memory.
    Context window is divided into three sections following MEMGPT approach: system messages, working
    context (memories) and FIFO queue of messages. Dimensions are checked by counting tokens. 

    Based on the context, the LLM may decide to call tools or not.
    Description of tools is provided when they are bounded to the LLM itself in json format.
    """

    configurable = Configuration.from_runnable_config(config)
    MAX_FIFO_TOKENS = configurable.max_fifo_tokens
    MAX_WORKING_CONTEXT_TOKENS = configurable.max_working_context_tokens

    assert store is not None, "Store not injected!"

    # FIFO messages (limited by token budget)
    pcap_content = generate_summary(state.pcap_path)
    #pcap_content = ListFrames().run(state.pcap_path)
    MAX_FIFO_TOKENS -= count_tokens(pcap_content) #Subtract the tokens used by the pcap content
    fifo_token_counter = 0
    fifo_messages_to_be_included = 0
    for m in reversed(state.messages):  # reversed to collect latest messages
        tok = count_tokens(m)
        if fifo_token_counter + tok < MAX_FIFO_TOKENS:
            fifo_token_counter += tok
            fifo_messages_to_be_included += 1
        else:
            break

    fifo_messages = state.messages[-fifo_messages_to_be_included:]

    # Semantic memory (working context)
    recent_messages = state.messages[-3:]
    search_query = " ".join([m.content for m in recent_messages if hasattr(m, "content")])
    results = await store.asearch("memories", query=search_query, limit=10)

    working_context_token_counter = 0
    working_context = []
    for mem in results:
        content = mem.value.get("content", "")
        context = mem.value.get("context", "")
        mem_str = f"{content} ({context})"
        tok = count_tokens(mem_str)
        if working_context_token_counter + tok < MAX_WORKING_CONTEXT_TOKENS:
            working_context.append(f"{mem.key.upper()}: {mem_str}, score={mem.score:.2f}")
            working_context_token_counter += tok
        else:
            break
    newline='\n'
    if working_context:
        memories_str = f"""
        You are provided with contextual memories retrieved from past interactions.
        Use them if they are relevant. Their relevance with respect to the current context is given by the score.

        <memories>
        {newline.join(working_context)}
        </memories>
        """
    else:
        memories_str = ""
    
    # FIFO as string->messages are counted to give a context of the flow to the LLM 
    queue_lines = [f"Message number {i+1}: {m.content}" for i, m in enumerate(fifo_messages)]
    queue_str = "\n".join(queue_lines)

    # Final prompt
    system_prompt = configurable.react_template.format(
        pcap_content=pcap_content,
        memories=memories_str,
        queue=queue_str
    )

    llm = init_chat_model(**split_model_and_provider(configurable.model),temperature=0.0,timeout=200)
    debug_config = RunnableConfig(callbacks=[PromptDebugHandler()])
    llm_with_tools = llm.bind_tools([upsert_memory, web_quick_search,tshark_expert,finalAnswerFormatter])#,file_reader,frameDataExtractor])
    #When it's the last iteration, concatenate a message saying that it has to provide an 
    #answer
    if state.steps == 2 or state.steps==3: #1 step this iteration, 1 for tools: 2 in total
        system_prompt += "\nWARNING: You are not allowed to explore the PCAP anymore, you have to provide the report with the information you gathered so far."
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