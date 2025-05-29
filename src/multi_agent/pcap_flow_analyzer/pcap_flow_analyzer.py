from openai import BadRequestError 
from typing import Tuple

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from configuration import Configuration
from multi_agent.pcap_flow_analyzer.flow_extractor import get_flow
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
    context_window_size: int
) -> Tuple[str, int, int]:
    """
    Analyze a TCP flow from a PCAP stream and produce a structured report,
    possibly refining it iteratively if the stream is chunked.
    """

    input_token_count = 0
    output_token_count = 0
    configurable = Configuration.from_runnable_config(config)
    llm = init_chat_model(
        **split_model_and_provider(configurable.model),
        temperature=0.0,
        timeout=200
    ).with_structured_output(Pcap_flow_output)

    chunks = get_flow(pcap_path, stream_number, context_window_size)

    for i, chunk in enumerate(chunks):
        previous = f"Previous report: {report_text}\n\n" if i > 0 else ""
        user_prompt = PCAP_FLOW_ANALYZER_USER_PROMPT.format(
            previous_tcp_traffic=previous_tcp_traffic, #tcp traffic of the previous flows
            current_stream=current_stream, #stream header of the current flow
            previous_report=previous, #report produced on the current flow on the previous chunks
            chunk=chunk #current chunk of the TCP flow to be analyzed
        )

        messages = [
            {"role": "system", "content": PCAP_FLOW_ANALYZER_SYSTEM_PROMPT.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ]

        try:
            response = await llm.ainvoke(messages)
        except BadRequestError:
            return ("Error: report of this flow couldn't be generated.", 0, 0)
        except Exception as e:
            return ("Error: an unexpected error occurred", 0, 0)

        report_text = format_pcap_flow_output(response)

        input_token_count += count_tokens(user_prompt)
        output_token_count += count_tokens(report_text)

    return (report_text, input_token_count, output_token_count)


__all__ = ["pcap_flow_analyzer"]
