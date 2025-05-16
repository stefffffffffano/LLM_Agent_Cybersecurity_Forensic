from openai import BadRequestError 
from typing import Tuple

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig


from multi_agent.pcap_flow_analyzer.prompts import PCAP_FLOW_ANALYZER_PROMPT
from multi_agent.common.configuration import Configuration
from multi_agent.pcap_flow_analyzer.flow_extractor import get_flow
from multi_agent.common.utils import split_model_and_provider


async def pcap_flow_analyzer(config: RunnableConfig,pcap_path:str,stream_number:int) -> Tuple[str, int, int]:
    """
    This function gets all the chuncks from the tcp flow of a stram of a pcap file and produces a report
    using an LLM that iteratively refines the report with each chunk if the output of the tshark command
    is too long.
    The command used is:
    tshark -r <pcap_file> -q -z follow,tcp,ascii,<stream_number>
    """

    input_token_count = 0
    output_token_count = 0
    configurable = Configuration.from_runnable_config(config)
    llm = init_chat_model(**split_model_and_provider(configurable.model),temperature=0.0,timeout=200)
    chuncks = get_flow(pcap_path,stream_number)
    
    for i, chunk in enumerate(chuncks):
        if i == 0:
            prompt = PCAP_FLOW_ANALYZER_PROMPT.format(previous_report="", chunk=f"Current chunk: {chunk}\n\n")
        else:
            previous = f"Previous report: {report_text}\n\n"
            prompt = PCAP_FLOW_ANALYZER_PROMPT.format(previous_report=previous, chunk=f"Current chunk: {chunk}\n\n")
        
        message = [{"role": "system", "content": prompt}]
        
        try:
            response = await llm.ainvoke(message)
        except BadRequestError:
            return ("Error: report of this flow couldn't be generated.", 0, 0)
        except Exception as e:
            return (f"Error: an unexpected error occurred", 0, 0)
        
        # Token usage tracking
        input_token_count += response.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
        output_token_count += response.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
    
        # Extract actual response content
        report_text = response.content

    
    return (report_text, input_token_count, output_token_count)



__all__ = ["pcap_flow_analyzer"]