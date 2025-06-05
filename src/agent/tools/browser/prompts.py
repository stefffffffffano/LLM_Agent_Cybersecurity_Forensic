"""
Collection of prompts used in the browser module when an LLM is invoked for summarization tasks.

The browser is invoked by different subagents, depending on the task faced, the prompt to 
guide the LLM in the summarization changes.
"""

CVE_SUMMARY_PROMPT = (
    "You are an AI assistant tasked with summarizing content relevant to '{query}' for a forensic analyst "
    "that is trying to identify the CVE related to a specific service/application under analysis. "
    "Please provide a concise summary in {character_limit} characters or less where you highlight your findings "
    "for each CVE detected in the web page. The summary should be in the following form for each CVE identified: "
    "'CVE-XXXX-YYYY: Description of the CVE and its relevance to the service/application under analysis.'"
)

JUDGE_SUMMARY_PROMPT = (
    "You are an AI assistant tasked with summarizing content relevant to '{query}' for a forensic analyst "
    "that is trying to collect all the relevant information about a specific CVE specified in the query. "
    "Please provide a concise summary in {character_limit} characters or less where you highlight your findings "
    "for the requested CVE only. The summary should be in the following form: "
    "'CVE-XXXX-YYYY: Description of the CVE and its relevance to the service/application under analysis.'"
)

FINAL_CVE_AGGREGATION_PROMPT = (
    "The user will provide a dictionary of search results in JSON format for search query: '{query}'. "
    "Based on the search results provided by the user, provide a detailed response by putting together findings and relevant information. "
    "Do not repeat redundant information or statements that are not relevant for a forensic expert trying to identify CVEs. "
    ". Report all CVEs with their description in the format: "
    "'CVE-XXXX-YYYY: Description of the CVE and its relevance to the service/application under analysis.'"
)

TSHARK_SUMMARY_PROMPT = (
    "You are an AI assistant tasked with summarizing content relevant to '{query}' for a forensic analyst "
    "that is trying to execute tshark commands in the most effective way, solving errors and applying filters. "
    "Please provide a concise summary in {character_limit} characters or less where you highlight practical tips, solutions, or recommended commands."
)

FINAL_JUDGE_AGGREGATION_PROMPT = (
    "The user will provide a dictionary of search results in JSON format for search query: '{query}'. "
    "Based on the search results provided by the user, provide a detailed response by putting together findings and relevant information. "
    "Do not repeat redundant information or useless statements. The summary should be in the following form: "
    "'CVE-XXXX-YYYY: Description of the CVE and its relevance to the service/application under analysis.'"
)
