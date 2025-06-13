import json
from langchain_core.messages import HumanMessage
from typing import Dict, Optional, Tuple

from browser.prompts import CVE_SUMMARY_PROMPT,JUDGE_SUMMARY_PROMPT,TSHARK_SUMMARY_PROMPT,FINAL_CVE_AGGREGATION_PROMPT,FINAL_JUDGE_AGGREGATION_PROMPT


class SummarizationHandler:
    def __init__(self, llm, research: str = "CVE", verbose=False,context_window_size=8192):
        self.llm = llm
        self.research = research
        self.verbose = verbose
        self.context_window_size = context_window_size

    def summarize(self, content: str, query: str, character_limit=800,max_chars = 20000 ) -> Tuple[Optional[str], int, int]:
        #Adjust max_chars based on context_window_size
        max_chars=int((80000*(128000/self.context_window_size))) 
        if self.research == "CVE":
            prompt = CVE_SUMMARY_PROMPT.format(query=query, character_limit=character_limit)
        elif self.research == "judge":
            prompt = JUDGE_SUMMARY_PROMPT.format(query=query, character_limit=character_limit)
        else:
            prompt = TSHARK_SUMMARY_PROMPT.format(query=query, character_limit=character_limit)

        try:
            messages = [
                HumanMessage(role="system", content=prompt),
                HumanMessage(role="user", content=content[:max_chars])
            ]
            response = self.llm.invoke(messages)
            usage = response.response_metadata.get("token_usage", {})
            return (response.content.strip(), usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        except Exception as e:
            if self.verbose:
                print(f"[LLM SUMMARY ERROR] {e}")
            return (None, 0, 0)

    def aggregate(self, summaries: Dict[str, str], query: str) -> Tuple[str, int, int]:
        if self.research == "CVE":
            prompt = FINAL_CVE_AGGREGATION_PROMPT.format(query=query)
        else:
            prompt = FINAL_JUDGE_AGGREGATION_PROMPT.format(query=query)

        try:
            messages = [
                HumanMessage(role="system", content=prompt),
                HumanMessage(role="user", content=json.dumps(summaries))
            ]
            response = self.llm.invoke(messages)
            usage = response.response_metadata.get("token_usage", {})
            return (response.content.strip(), usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        except Exception as e:
            if self.verbose:
                print(f"[FINAL SUMMARY ERROR] {e}")
            return ("An error occurred during final summarization.", 0, 0)
