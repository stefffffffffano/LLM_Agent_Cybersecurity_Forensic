from langchain_core.runnables import RunnableConfig

from multi_agent.common.global_state import State_global
from multi_agent.main_agent.tools.pcap import generate_summary
from multi_agent.pcap_flow_analyzer import pcap_flow_analyzer
from multi_agent.main_agent.tools.pcap.tls_streams import get_tls_streams
from configuration import Configuration

async def pcap_flows_reporter(state: State_global, config: RunnableConfig) -> dict:
    """
    This function executes the command tshark -r <pcap_file> -q -z conv,tcp and,
    for each tcp flow (that does not containt tls traffic), calls the tcp flow analyzer 
    to get a report of the flow.
    Finally, it returns a report for each flow concatenating results.
    """
    input_token_count = state.inputTokens
    output_token_count = state.outputTokens
    final_report = ""

    # This is the full tshark output, already formatted
    tshark_output = generate_summary(state.pcap_path)
    tshark_lines = tshark_output.strip().splitlines()
    # Get a set containing the tcp streams that contain tls traffic
    tls_streams = get_tls_streams(state.pcap_path)

    #retrieve context window size from the configuration
    configurable = Configuration.from_runnable_config(config)
    context_window_size = configurable.context_window_size
    # Identify the lines that contain flow rows (i.e., between header and footer)
    flow_lines = []
    for line in tshark_lines:
        if line.startswith("==="):
            continue
        if "<->" in line:
            flow_lines.append(line)
        elif flow_lines and not line.strip():
            # End of the flow table (blank line or footer)
            break

    # Rebuild report: copy line-by-line and interleave analysis after flow rows
    stream_number = 0
    
    for i, line in enumerate(tshark_lines):
        final_report += line + "\n"
        if(line in flow_lines):
            #Call the flow analyzer in this case
            if(stream_number in tls_streams):
                stream_number += 1
                continue 
            (report,input_tokens,output_tokens) = await pcap_flow_analyzer(
                config=config,
                pcap_path=state.pcap_path,
                stream_number=stream_number,
                current_report=final_report,
                current_stream=line,
                cotext_window_size= context_window_size
            )
            stream_number += 1
            tcp_report = f"Report from the tcp stream analyzer:\n{report}\n"
            input_token_count += input_tokens
            output_token_count += output_tokens
            final_report += tcp_report

    return {
        "messages": [{"role": "system", "content": final_report}],
        "steps": state.steps,
        "event_id": state.event_id,
        "inputTokens": input_token_count,
        "outputTokens": output_token_count,
    }


__all__ = ["pcap_flows_reporter"]
