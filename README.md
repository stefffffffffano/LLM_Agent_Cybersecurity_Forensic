# LLM-based Cybersecurity Forensics Agent

This project implements a LangGraph-based AI agent capable of performing autonomous forensic analysis on network events captured in `.pcap` files.  
Given a benchmark dataset, the agent detects vulnerabilities (e.g., CVEs), identifies affected services, and produces structured reports. 

The current version represent the ***Flow reporter*** that does not include log analysis in the flow of execution. The system first analyses each tcp flow through a PCAP_flows_analyzer, then instantiates an agent to loop on findings, make research online and provide a final report with all findings related to the forensic task. 

---

##  Repository Structure

```
project-root/
├── data/                                # Dataset folder
│   ├── CFA-benchmark/                   # CFA dataset
│   │   ├── raw/                         # Raw PCAPs and logs
│   │   │   └── eventID_<n>/             # One folder per forensic challenge
│   │   └── tasks/                       # Tasks metadata
│   │       └── data.json                # JSON file containing all tasks
│   │
│   ├── TestSet_benchmark/              # Test set for evaluation
│   │   ├── raw/                         # Raw PCAPs and logs
│   │   │   └── eventID_<n>/             # One folder per forensic challenge
│   │   └── tasks/                       # Tasks metadata
│   │       └── data.json                # JSON file containing all tasks
│   │
│   └── web_browsing_traffic/           # Non-malicious traffic samples
│       ├── raw/                         # Raw PCAPs
│       │   └── eventID_<n>/             # Events related to non malicious traffic, no ground truth required
│
├── src/                                 # Source code
│   ├── run_agent.py                     # Entry point to execute the agent
│   ├── configuration.py                 # Reads environment variables and agent settings
│   ├── multi_agent/                     # Contains the code for all the agents
│   ├── browser/                         # Code related to the web search tool
│   └── .env_example                     # Example of environmental variables file
│
├── requirements.txt                     # Python dependencies
├── results/                             # Results folder containing logs and reports for each rn (for each execution on the benchmark)
└── README.md                            # Instructions on how to execute the agent

```

---

## How to Run the Agent

Follow these steps to install dependencies, configure the environment, and execute the agent.


### 1. Set Up the Python Environment

Create and activate a virtual environment:

```bash
python -m venv venv
venv\scripts\activate.ps1  
```

Then install the required packages:

```bash
pip install -r requirements.txt
```

---

##  Wireshark / TShark Dependency

This project requires the command-line tool **TShark** to analyze `.pcap` files.

TShark is part of the [Wireshark](https://www.wireshark.org/) network analysis suite and must be **installed and accessible via the system `PATH`**.

###  Installation Instructions

1. **Download Wireshark** from the official site:  
  https://www.wireshark.org/download.html

2. During installation:
   -  **Enable the option to install `TShark`**
   -  **Select the option to add Wireshark to the system `PATH` or do it manually once it has been installed**

---


### 2. Configure Environment Variables

From the `src/` folder:

```bash
cd src
cp .env_example .env
```

Edit `.env` and fill in the necessary variables:
- LLM provider and model name. There is a specific section in the following detailing how to provide model and provider
- API keys (e.g., OpenAI, Google Custom Search, etc.). Remind that the OpenAI Key is always required, even if another LLM is used, because It is used to produce embeddings
- Context window (default 128K), depends on the LLM used 
- Dataset: CFA or test. By specifying the former, CFA-bench with its 20 events is executed, otherwise it is executed the more recent set of 10 events created as test set. The latter contains only events related to vulnerabilities discovered in 2025
- Number of executions: specify how many iterations on the benchmark

Save the file before proceeding.

---

### 3. Run the Agent

Run the following command from the `src/` directory:

#### Executing one of the two benchmarks (CFA or test set):

```bash
python run_agent.py
```

The script will:

- Iterate through all events in `tasks/data.json`
- For each event:
  - Instantiate a new LangGraph agent
  - Run the analysis on the corresponding `.pcap` file
  - Log the step-by-step reasoning into `results/run[n]/log_steps`
  - Append results to `results/run[n]/result.txt`

At the end, it prints performance metrics (e.g., accuracy) to `stdout` and to the file `results/run[n]/result.txt` for each execution.

#### Testing the agent on non-malicious traffic

The folder `data/web_browsing_traffic` contains data from normal web browsing, with no malicious activity involved. Although the agent is prompted with a bias toward detecting malicious behavior (as defined in the benchmark), we also evaluated it on this benign scenario.

To run the test, simply execute:

```bash
python run_agent_web_events.py
```

The final output will be the same reported before without perfornance metrics, as there is no ground truth in this case, since there is no malicious activity. In the file in `data/web_browsing_traffic/gt.txt` there is, for each event, the corresponding event that we were browsing when collecting data. Because the traffic is TLS-encrypted, the corresponding decryption key is also provided for each event, enabling the agent to analyze the content in an automatic manner.


---

## Output Artifacts

- `results/run[n]/log_steps/`: One file per event, detailing internal reasoning and tool calls
- `results/run[n]/result.txt`: Final report for each event (e.g., predicted CVE, vulnerable status)

---

##  Structure of the Benchmark

The benchmark is designed to evaluate the agent’s ability to perform forensic analysis on malicious network traffic (there is always an attempted attack against a web service). Thus, for each event, it is assumed that an attack has occurred. The goal of the agent is to:

- **Determine the affected service**
- **Detect the correct CVE ID**, if applicable
- **Assess whether the service is vulnerable**
- **Assess whether the attack was successful**
- **Generate a concise report**
---
## How to specify model and provider

To configure the model and provider, set the appropriate variable in your `.env` file.

### Official providers (e.g., OpenAI)

Use the provider name followed by a `/` and the model identifier. Examples:

- openai/gpt-4o
- openai/o3
- openai/gpt-5
  

### Third-party providers (e.g., Together AI)

Specify the provider name first, then append the model identifier in the same format as before. Example:
 -together/meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8

---