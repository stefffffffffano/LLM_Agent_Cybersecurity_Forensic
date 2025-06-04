from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal

from langchain_core.tools import Tool


class ThreeStateBool(str, Enum):
    true = "true"
    false = "false"
    unknown = "unknown"


class FinalAnswerArgs(BaseModel): 
    detailed_report: str = Field(..., description="The detailed report of the attack.")
    cve_identifier: str = Field("unknown", description="The CVE identifier, or 'unknown' if you are not confident about the answer.")
    affected_service: str = Field("unknown", description="The name of the affected service, or 'unknown' if you are not confident about the answer.")
    successfull_attack: ThreeStateBool = Field(..., description="Whether the attack was successful: true, false, or unknown.")
    is_vulnerable: ThreeStateBool = Field(..., description="Whether the service is vulnerable: true, false, or unknown.")


def finalAnswerFormatter_func(
    detailed_report: str,
    cve_identifier: str,
    affected_service: str,
    successfull_attack: ThreeStateBool,
    is_vulnerable: ThreeStateBool
) -> str:
    """Format the final answer."""
    final_report = f"FINAL REPORT:\n{detailed_report}\n\nREPORT SUMMARY:\n"
    final_report += f"Identified CVE: {cve_identifier}\n"
    final_report += f"Affected Service: {affected_service}\n"
    final_report += f"Is Service Vulnerable: {is_vulnerable}\n"
    final_report += f"Attack Succeeded: {successfull_attack}\n"
    return final_report


finalAnswerFormatter = Tool(
    name="final_answer_formatter",
    description="""Format the final answer when you want to provide it as a solution to the proposed question.
    Return one single CVE and affected service (without the version, just the name).
    If any of the fields is unknown or cannot be confidently determined, use 'unknown'.

    Args:
        detailed_report: summarize the requests sent by the attacker, the attack type and all relevant evidence collected about the attack exploitation/success. 
        cve_identifier: The CVE identifier (or 'unknown').
        affected_service: The affected service name (or 'unknown').
        successfull_attack: Whether the attack was successful: true, false or unknown.
        is_vulnerable: Whether the service is vulnerable: true, false or unknown.

    Returns:
        The formatted final report to be returned before ending.
    """,
    args_schema=FinalAnswerArgs,
    func=finalAnswerFormatter_func,
)

__all__ = ["finalAnswerFormatter", "finalAnswerFormatter_func"]
