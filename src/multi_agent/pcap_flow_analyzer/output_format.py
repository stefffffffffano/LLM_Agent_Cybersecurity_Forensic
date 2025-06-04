from typing import Optional

from typing_extensions import Annotated, TypedDict


# TypedDict
class  Pcap_flow_output(TypedDict):
    """Structure of the output for the PCAP flow analyzer (report for each tcp flow)"""

    service: Annotated[str, ..., "The service involved (a list if more than one) and, if possible, the version of the service"]
    relevant_events: Annotated[str, ..., "What are the IP addresses involved doing in this tcp flow? Report relevant events and their meaning. \
                               If needed, direct quotations can be added"]
    malicious_activities: Annotated[Optional[str], None, "Malicious/suspicious activities found in the flow and the service they involve"]
    attack_success: Annotated[Optional[str], None, "Report wheter an attack in this flow (or in a previous flow) was successful or not. \
                              Report relevant details related to the attack."]
    

def format_pcap_flow_output(output: Pcap_flow_output) -> str:
    """Format the output of the PCAP flow analyzer as a string"""
    formatted_output = []
    formatted_output.append(f"Service: {output['service']}")
    
    formatted_output.append(f"Relevant Events: {output['relevant_events']}")

    if output['malicious_activities']:
        formatted_output.append(f"Malicious Activities: {output['malicious_activities']}")
    
    if output['attack_success']:
        formatted_output.append(f"Attack Success: {output['attack_success']}")
    
    return "\n".join(formatted_output)
    
__all__ = ["Pcap_flow_output","format_pcap_flow_output"]