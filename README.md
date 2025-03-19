# LLM_Agent_Cybersecurity_Forensic
AI agent leveraging on LLM models in order to perform cybersecurity forensic.

Using [templates](https://langchain-ai.github.io/langgraph/concepts/template_applications/) we can define agents with different responsibilities. With [multi-agent supervision](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/) provided by LangChain, we can create a Multi-agent systems composed by 3 main components:
1. Memory Agent (Orchestrator) -> ReAct agent that coordinates everything and mantain the context;
2. Retrieval Agent -> search for more information online;


The orchestrator is prompted as a supervisor tasked with managing conversation between a list of workers. Then, given a request, it responds with the worker to act next passing what is necessary for that worker. Each worker can interact with different tools, allowing for better modularization and separation of concerns.  

How to manage the context?  
1. Immediate Context: Use a sliding window for the most recent and relevant conversation bits; 
2. Deep Memory: Store older context as vectors to retrieve only what’s necessary. 


With LangChain, we have the possibility to limit the (long term/scratchpad) memory buffer based on a predefined number of tokens (let's say, 4000):

```python
from langchain.memory import ConversationTokenBufferMemory
from langchain.chat_models import ChatOpenAI

# limit the memory to 4000 tokes
memory = ConversationTokenBufferMemory(llm=ChatOpenAI(model_name="gpt-4-turbo"), max_token_limit=4000)

# Save info, only the last 4000 tokens will be mantained
memory.save_context(...info)

# Recover the context
print(memory.load_memory_variables({}))
```

At each steps, append both the prompt and the observation obtained to the Scratchpad. At each new step, if the number of tokens (counted with tiktokens) is equal to the maximum allowed for the Scratchpad, retrieve from the db the informations that are more 'aligned' with the elements appended in the previous iteration.   

How to store in the db for future retrieval? We can keep track of what is dynamically removed from the sliding context window and save what would be lost in a database. Then, using the strategy explained before, we try to retrieve what is more relevant. A summary of older information and all details for more recent information could be more beneficial than ReAct + summary-> In forensic it could be better to mantain every detail of the last 2/3 steps and have a general idea of what has been done before. If you summarize everything, the risk is to lose relevant details of the previous steps.

