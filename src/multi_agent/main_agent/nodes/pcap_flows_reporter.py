from langchain_core.runnables import RunnableConfig
from typing import List, Tuple
import numpy as np
import os

from multi_agent.common.global_state import State_global
from multi_agent.main_agent.tools.pcap import generate_summary
from multi_agent.pcap_flow_analyzer import pcap_flow_analyzer
from multi_agent.main_agent.tools.pcap.tls_streams import get_tls_streams
from configuration import Configuration
from multi_agent.common.utils import count_tokens, count_flows,get_flow,get_flow_web_browsing


def sqrt_token_allocation(flows, budget):
    tokens_array = np.array(flows)
    sqrt_tokens = np.sqrt(tokens_array)
    weights = sqrt_tokens / sqrt_tokens.sum()
    raw_allocations = weights * budget
    bounded_allocations = np.minimum(tokens_array, raw_allocations)

    def redistribute_residual(tokens, current_alloc, total_budget):
        remaining = total_budget - current_alloc.sum()
        while remaining > 1:
            eligible = tokens > current_alloc
            if not eligible.any():
                break
            #It mantains the allocation proportional to the square root of the tokens
            extra = np.sqrt(tokens[eligible] - current_alloc[eligible])
            extra_weights = extra / extra.sum()
            redistribution = np.minimum(tokens[eligible] - current_alloc[eligible], extra_weights * remaining)
            current_alloc[eligible] += redistribution
            remaining = total_budget - current_alloc.sum()
        return np.round(current_alloc).astype(int)

    return redistribute_residual(tokens_array, bounded_allocations.copy(), budget)

def tokens_budget_vector(pcap_path:str,tokens_budget:int,discarded_flows:set,browsing:bool)->Tuple[List[int],List[int]]:
    """
    This function takes the pcap path and tokens budget as input and returns a vector of 
    floats representing the tokens budget (input prompt) for each tcp flow analyzed.
    Discarded flows is used to skip tcp flows containing tls traffic.
    """
    number_of_flows = count_flows(pcap_path)
    flows = []
    for j in range(number_of_flows):
        if j not in discarded_flows:
            if not browsing:
                flow = get_flow(pcap_path, j)
            else:
                flow = get_flow_web_browsing(pcap_path,j)
            flow_tokens = count_tokens(flow) if flow is not None else 0
            flows.append(flow_tokens)
        else:
            flows.append(0)
    total = sum(flows)
    if(total > tokens_budget):
        allocations = sqrt_token_allocation(flows, tokens_budget).tolist()
    else:
        allocations = flows
    return (allocations,flows)


async def pcap_flows_reporter(state: State_global, config: RunnableConfig) -> dict:
    """
    This function executes the command tshark -r <pcap_path> -q -z conv,tcp and,
    for each tcp flow (that does not containt tls traffic), calls the tcp flow analyzer 
    to get a report of the flow.
    Finally, it returns a report for each flow concatenating results.

    If we are analysing traffic related to normal web browsing, we still consider tls traffic
    """
    input_token_count = state.inputTokens
    output_token_count = state.outputTokens
    final_report = ""

    browsing = os.getenv("DATASET", "").strip().lower() == "web_browsing_events"
    # This is the full tshark output, already formatted
    tshark_output = generate_summary(state.pcap_path)
    tshark_lines = tshark_output.strip().splitlines()
    # Get a set containing the tcp streams that contain tls traffic
    if not browsing: 
        tls_streams = get_tls_streams(state.pcap_path)
    else:
        tls_streams = set()
    #retrieve context window size from the configuration
    configurable = Configuration.from_runnable_config(config)
    tokens_budget = configurable.tokens_budget

    allocations,flows = tokens_budget_vector(
        pcap_path=state.pcap_path,
        tokens_budget=tokens_budget,
        discarded_flows=tls_streams,
        browsing = browsing
    )
    
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
                previous_tcp_traffic=final_report,
                current_stream=line,
                context_window_size= context_window_size,
                allocation_size = allocations[stream_number] if stream_number < len(allocations) else 0,
                total_size = flows[stream_number] if stream_number < len(flows) else 0,
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
