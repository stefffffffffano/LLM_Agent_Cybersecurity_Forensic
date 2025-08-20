from openai import BadRequestError
import time 
from typing import Tuple

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from configuration import Configuration
from multi_agent.common.utils import get_flow,truncate_flow
from multi_agent.common.utils import split_model_and_provider, count_tokens
from multi_agent.pcap_flow_analyzer.output_format import Pcap_flow_output, format_pcap_flow_output
from multi_agent.pcap_flow_analyzer.prompts import (
    PCAP_FLOW_ANALYZER_SYSTEM_PROMPT,
    PCAP_FLOW_ANALYZER_USER_PROMPT
)


async def pcap_flow_analyzer(
    config: RunnableConfig,
    pcap_path: str,
    stream_number: int,
    previous_tcp_traffic: str,
    current_stream: str,
    context_window_size: int,
    allocation_size: int,
    total_size: int,
) -> Tuple[str, int, int]:
    """
    Analyze a TCP flow from a PCAP stream and produce a structured report
    If the tcp flow is too long, it discards part of it in the middle to fit
    an allocation size constraint.
    """

    input_token_count = 0
    output_token_count = 0
    configurable = Configuration.from_runnable_config(config)
    llm = init_chat_model(
        **split_model_and_provider(configurable.model),
        #temperature=0.0,
        timeout=200
    )

    flow_text = get_flow(pcap_path, stream_number)

    if total_size > allocation_size  or total_size > context_window_size:
        chunk = truncate_flow(flow_text, allocation_size, context_window_size)
    else:
        chunk = flow_text
        
    user_prompt = PCAP_FLOW_ANALYZER_USER_PROMPT.format(
        previous_tcp_traffic=previous_tcp_traffic, #tcp traffic of the previous flows
        current_stream=current_stream, #stream header of the current flow
        chunk=chunk #current chunk of the TCP flow to be analyzed
    )

    messages = [
        {"role": "system", "content": PCAP_FLOW_ANALYZER_SYSTEM_PROMPT.strip()},
        {"role": "user", "content": user_prompt.strip()}
    ]

    try:
        response = await llm.ainvoke(messages)
    except BadRequestError as e:
        print("❌ BadRequestError:", e)
        return ("Error: report of this flow couldn't be generated.", 0, 0)
    except Exception as e:
        return ("Error: an unexpected error occurred", 0, 0)
    #report_text = format_pcap_flow_output(response)

    input_token_count += count_tokens(user_prompt)
    output_token_count += count_tokens(response.content)

    return (response.content, input_token_count, output_token_count)


__all__ = ["pcap_flow_analyzer"]
