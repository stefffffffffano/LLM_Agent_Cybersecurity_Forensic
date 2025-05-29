from openai import BadRequestError 
from typing import Tuple

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig


from multi_agent.pcap_flow_analyzer.prompts import PCAP_FLOW_ANALYZER_PROMPT
from configuration import Configuration
from multi_agent.pcap_flow_analyzer.flow_extractor import get_flow
from multi_agent.common.utils import split_model_and_provider,count_tokens
from multi_agent.pcap_flow_analyzer.output_format import Pcap_flow_output,format_pcap_flow_output



async def pcap_flow_analyzer(config: RunnableConfig,pcap_path:str,stream_number:int,current_report:str,current_stream:str,context_window_size:int) -> Tuple[str, int, int]:
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
    llm = init_chat_model(**split_model_and_provider(configurable.model),temperature=0.0,timeout=200).with_structured_output(Pcap_flow_output)
    chuncks = get_flow(pcap_path,stream_number,context_window_size)
    
    for i, chunk in enumerate(chuncks):
        if i == 0:
            prompt = PCAP_FLOW_ANALYZER_PROMPT.format(current_stream=current_stream,current_report=current_report,previous_report="", chunk=f"Current chunk: {chunk}\n\n")
        else:
            previous = f"Previous report: {report_text}\n\n"
            prompt = PCAP_FLOW_ANALYZER_PROMPT.format(current_stream=current_stream,current_report=current_report,previous_report=previous, chunk=f"Current chunk: {chunk}\n\n")
        
        message = [{"role": "system", "content": prompt}]
        try:
            response = await llm.ainvoke(message)
        except BadRequestError:
            return ("Error: report of this flow couldn't be generated.", 0, 0)
        except Exception as e:
            return (f"Error: an unexpected error occurred", 0, 0)
        
        #Format the report from the response
        report_text = format_pcap_flow_output(response)

        # Token usage tracking
        input_token_count += count_tokens(prompt)
        output_token_count += count_tokens(report_text)
    
    
    return (report_text, input_token_count, output_token_count)



__all__ = ["pcap_flow_analyzer"]