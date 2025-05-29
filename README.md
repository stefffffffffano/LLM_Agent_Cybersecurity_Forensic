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
# Piano di lavoro 28/05/2025

- Rifare tutti i grafici seguendo i consigli -> token_count e steps mostrano le 3 esecuzioni, failing events alla fine della heat map e colonne riordinate; <- done
- Gestire context length in pcap_flow_analyzer e browser; <-done
- Cambiare browser in modo che non usi embeddings, tornare singolo risultato; <- done
- Gestire tutti i file in cui si prendono i prompt, bisogna dividere in system e user !!!!; <-done
  - Bisogna rivedere main_agent, pcap_flow_analyzer,log_reporter e llm_as_a_judge <-done
- Rivedere tutti i prompt -> riprendi slide consigli dall'ultima riunione; <- done
- Valutare come integrare Ollama <- done  
  
  
- Valutare la possibilità che l'agente non risponda solo true/false, ma anche un don't know per attack success (?);
- Strutturare il report dell'agente (?) -> la parte in formato str in cui descrive che cosa è successo;



 

