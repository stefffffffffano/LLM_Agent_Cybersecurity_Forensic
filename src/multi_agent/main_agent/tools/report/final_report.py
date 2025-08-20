from pydantic import BaseModel

from langchain_core.tools import Tool

class FinalAnswerArgs(BaseModel):
    detailed_report: str
    cve_identifier: str
    affected_service: str
    successfull_attack: bool
    is_vulnerable: bool

def finalAnswerFormatter_func(
    detailed_report: str,
    cve_identifier: str,
    affected_service: str,
    successfull_attack: bool,
    is_vulnerable: bool
) -> str:
    """Format the final answer."""
    final_report = f'FINAL REPORT:\n'
    final_report += detailed_report
    final_report += f'\nREPORT SUMMARY:\n'
    final_report += f'Identified CVE: {cve_identifier}\n'
    final_report += f'Affected Service: {affected_service}\n'
    final_report += f'Is Service Vulnerable: {is_vulnerable}\n'
    final_report += f'Attack succeeded: {successfull_attack}\n'
    return final_report

finalAnswerFormatter = Tool(
    name="final_answer_formatter",
    description="""Format the final answer when you want to provide it as a solution to the proposed question.
    Return one single cve and affected service (without the version,just the name).
    Args: 
        detailed_report: summarize the requests sent by the attacker, the attack type and all relevant evidence collected about the attack exploitation/success.
        cve_identifier: The CVE identifier of the vulnerability.
        affected_service: The service that was affected by the attack.
        successfull_attack: Whether the attack was successful or not.
        is_vulnerable: Whether the service is vulnerable or not.
    Returns:
        The final report of the attack to be returned before ending
    """,
    args_schema=FinalAnswerArgs,
    func=finalAnswerFormatter_func,
)

__all__ = ["finalAnswerFormatter", "finalAnswerFormatter_func"]