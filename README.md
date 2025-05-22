# LLM_Agent_Cybersecurity_Forensic

### LLM-as-a-Judge: Evaluation Protocol

The goal of this module is to evaluate whether the findings reported by the agent are coherent with the ground truth about a specific event. Due to the nature of technical reports, it is possible that different terminology is used or that partially different evidence is highlighted, even if the underlying events or vulnerabilities are the same.

To support this evaluation, an LLM is asked to act as a judge and compare two reports:

- The **agent report**, which contains the information extracted or inferred by an autonomous agent.
- The **ground truth report**, which is the expected or validated reference for the event.

The agent will be provided not only with the reports, but also with the entire output produced (including CVE, vulnerability type, attack success, and affected service).

The LLM should return three outputs:

1. **differences_summary**  
   A brief textual explanation highlighting the most relevant differences (or notable similarities) between the two reports. This helps explain the rationale behind the final classification.

2. **similarity_scale**  
   A discrete classification indicating how closely the two reports refer to the same core concepts and technical findings.

3. **cve_similarity_note** *(optional)*  
   If the reports refer to **different CVEs**, this field should assess whether the two CVEs may describe similar or related vulnerabilities (e.g., variants, incomplete patches, or shared root causes).  
   The model may simulate a brief web search to verify whether the confusion is understandable or justified.

---

### Similarity Scale

| Class | Interpretation |
|-------|----------------|
| **Strongly agree** | The two reports describe the exact same event, possibly using different wording or structure. Full semantic overlap. |
| **Agree** | The reports refer to the same core issue, with some differences in technical details, scope, or emphasis (e.g., same attack but different outcome, or different CVEs). |
| **Disagree** | Some thematic overlap (e.g., same attack class), but the reports describe different events or vulnerabilities with limited shared details. |
| **Strongly disagree** | The reports describe completely unrelated issues, with no meaningful semantic alignment. Likely a misclassification or confusion. |


# TODO: 
# Web search to be modified: we need a prompt for this agent (for the summarization) and a modified description.
# Write the run_judge function to call the graph, check the entire code
# Verify that everything adapts to the context length that you can set through the .env file
# Adjust character limit that is set in the web search file