from pydantic import BaseModel
from typing import Optional
from langchain_core.tools import Tool

class JudgeEvaluationArgs(BaseModel):
    differences_summary: str
    similarity_scale: str  # One of: "Strongly agree", "Agree", "Disagree", "Strongly disagree"
    cve_similarity_note: Optional[str] = None  # Optional field if CVEs differ

def judgeEvaluationFormatter_func(
    differences_summary: str,
    similarity_scale: str,
    cve_similarity_note: Optional[str] = None
) -> str:
    """Format the evaluation report from the LLM-as-a-judge."""
    report = "LLM EVALUATION REPORT:\n"
    report += f"Similarity Scale: {similarity_scale}\n"
    report += f"\nDifferences Summary:\n{differences_summary}\n"
    if cve_similarity_note:
        report += f"\nCVE Similarity Note:\n{cve_similarity_note}\n"
    else:
        report += "\nThe 2 CVEs are the same.\n"
    return report

judgeEvaluationFormatter = Tool(
    name="judge_evaluation_formatter",
    description="""
        Format the final evaluation report after comparing the agent's findings with the ground truth.

        Arguments:
        - differences_summary: A concise but informative explanation of the main differences or similarities between the agent's report and the ground truth.
        - similarity_scale: A discrete label describing the level of semantic alignment between the two reports. Must be one of the following:
            - "Strongly agree": the reports describe the exact same event with full semantic overlap.
            - "Agree": they describe the same issue with minor differences (e.g., same attack, different CVE or different outcome).
            - "Disagree": some topical overlap but distinct events or vulnerabilities.
            - "Strongly disagree": completely unrelated reports with no meaningful similarity.
        - cve_similarity_note (optional): If the CVEs are different, this optional field explains what are the differences between the two CVEs. If the CVEs are the same, this field is not needed.

        Returns:
        A formatted string summarizing the LLM’s judgment on the quality and accuracy of the agent’s findings.
    """,
    args_schema=JudgeEvaluationArgs,
    func=judgeEvaluationFormatter_func,
)

__all__ = ["judgeEvaluationFormatter", "judgeEvaluationFormatter_func"]
