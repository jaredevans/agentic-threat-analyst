# 🛡️ Agentic Threat Analyst — Okta System Logs

### AutoGen + LangChain + Hugging Face + Deterministic Rules  
**An end-to-end local, explainable multi-agent system for Okta security log triage**

---

## 🔍 Overview

This project demonstrates how to build an **Agentic AI Threat Analyst** system that ingests **Okta System Logs** (`okta-logs.txt`), identifies suspicious activity, and produces human-readable triage reports — all **offline and privacy-preserving**.

This project was inspired by the *MarkTechPost* tutorial —  
_“How I Built an Intelligent Multi-Agent System with AutoGen, LangChain, and Hugging Face” (Oct 2025)_ —  
but adapts it for a **cybersecurity use case**: analyzing authentication and identity events from Okta.

The framework incrementally combines:

1. **Rule-based detection** (deterministic, explainable)
2. **LLM summarization and planning** (LangChain LCEL)
3. **Multi-agent collaboration** (AutoGen-inspired)
4. **Hybrid symbolic + neural reasoning** with guardrails

---

## 🧠 Key Concepts

| Component | Purpose | Framework |
|------------|----------|------------|
| **LangChain** | Builds reasoning and planning chains for triage and investigation | `langchain`, `langchain-community` |
| **AutoGen (simulated)** | Demonstrates conceptual multi-agent orchestration | `autogen` (conceptual only, no API calls) |
| **Hugging Face Transformers** | Provides local LLM backbone (`microsoft/Phi-3-mini-4k-instruct`) | `transformers`, `accelerate` |
| **Rule Engine** | Deterministic detection of anomalies (failed logins, impossible travel) | Native Python |
| **Simple Agents** | Lightweight Hugging Face pipeline wrappers for role-based reasoning | `agents/simple_agent.py` |

---

## ⚙️ Architecture Overview

```
okta-logs.txt
│
▼
[core/ingest.py]
└── Normalizes raw JSONL or key=value Okta events
↓
[core/rules.py]
└── Deterministic threat detector (login bursts, impossible travel)
↓
[chains/chains.py]
└── LangChain reasoning chains (triage, planning, execution)
↓
[agents/simple_agent.py]
└── Role-based agents powered by Hugging Face (no API)
↓
[autogen_sim/conversation.py]
└── Conceptual AutoGen workflow simulation
↓
[hybrid/hybrid.py]
└── Combines rules + reasoning + agents
↓
Reports + Console Output
```

---

## 🧰 Setup Instructions

### 1️⃣ Environment Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Apple Silicon (M-series) users:**  
PyTorch with MPS acceleration is supported.  
If missing, install manually:

```bash
pip install torch torchvision torchaudio
```

If you encounter backend issues:

```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

### 2️⃣ Add Your Okta Logs

Place your Okta export at the project root:
```
okta-logs.txt
```

- JSONL format preferred (one event per line)
- `key=value` lines also supported

### 3️⃣ Configure Your Model

Edit `config.yaml` as needed:

```
model:
  hf_model: microsoft/Phi-3-mini-4k-instruct
  max_new_tokens: 384
  temperature: 0.0
rules:
  failed_login_window_min: 60
  failed_per_user: 8
  failed_per_ip: 20
  impossible_travel_window: 90
```

---

## 🚀 Demos and Test Runs

Run via:

```bash
python main.py --demo <mode>
```

Each mode builds progressively from deterministic rules → AI reasoning → multi-agent collaboration.

---

### 1⃣ Deterministic Rules

```bash
python main.py --demo rules
```

**Input:**  
- `okta-logs.txt` — a local file containing Okta System Logs (JSONL or key=value lines).  
- No model or LLM involved.

**Process:**  
- Parsed and normalized by `core/ingest.py`.  
- Evaluated by `core/rules.py` (`RuleDetector`) for:  
  - Excessive failed logins per user/IP  
  - Impossible travel between countries  

**Output:**  
- Printed list of rule-based findings:  

  ```
  == Rule-based findings ==
  MEDIUM  excessive_failed_logins_user     user alice@gallaudet.edu failures=8
  HIGH    excessive_failed_logins_ip       ip 198.51.100.23 failures=20
  HIGH    impossible_travel                alice@gallaudet.edu: US -> DE quickly
  ```
- Output is **deterministic, explainable, and text-only**.

---

### 2⃣ LangChain: Threat Triage Chain

```bash
python main.py --demo langchain1
```

**Input:**  
- A **synthetic test signal** (string):  

  ```
  "Multiple login failures for alice@gallaudet.edu from 198.51.100.23 over 10 minutes."
  ```
- Uses `triage_chain` in `chains/chains.py`.

**Process:**  
- Builds a local Hugging Face text-generation pipeline (`Phi-3-mini-4k-instruct`).  
- Passes the signal through a structured prompt to produce a concise triage summary.

**Output:**  
- A **3-bullet summary** of risks and recommended actions, for example:

  ```
  - High likelihood of brute-force attempt.
  - User account alice@gallaudet.edu may be compromised.
  - Recommend temporary lockout and MFA enforcement.
  ```

---

### 3⃣ LangChain: Multi-Step Plan + Execution

```bash
python main.py --demo langchain2
```

**Input:**  
- Goal text (string):  

  ```
  "Investigate burst of failed Okta logins and possible account takeover"
  ```
- Uses two LCEL chains:  
  - `plan_chain` → creates 3 numbered steps.  
  - `step_chain` → converts one step into actionable shell commands.

**Process:**  
- The model generates a procedural plan, then expands one step with concrete `jq`, `grep`, or `awk` commands referencing `okta-logs.txt`.

**Output:**  

```
Plan:
1. Identify top failing users.
2. Extract source IPs and geolocations.
3. Verify login patterns.

Execution detail:
- Item: Top failing users
  Command: jq '. | select(.outcome=="FAILURE") | .actor.alternateId' okta-logs.txt | sort | uniq -c
```

**Output Type:**  
- Text printed to console; partially generated by LLM.

---

### 4⃣ Simple Multi-Agent Workflow

```bash
python main.py --demo simple_agents
```

**Input:**  
- `okta-logs.txt` — the same as in Demo 1.  
- Findings from the rule engine are summarized and fed to agents.

**Process:**  
- Three lightweight agents (`SimpleAgent` objects):

  1. **LogLoader:** Prints structured rule findings.  
  2. **ThreatAnalyst:** Summarizes risks based on findings.  
  3. **Responder:** Suggests containment or remediation actions.
  
- All agents use the same HF model pipeline, passing messages sequentially.

**Output:**  
- Textual conversation printed in order:

  ```
  [LogLoader]
  excessive_failed_logins_user | medium | user alice@gallaudet.edu failures=8

  [ThreatAnalyst]
  - Multiple login failures may indicate credential stuffing.
  - Investigate repeated IP addresses.
  - Consider temporary user lockout.

  [Responder]
  - Disable affected accounts.
  - Enforce password reset.
  - Block offending IP ranges at firewall.
  ```

---

### 5⃣ AutoGen Conceptual Demo

```bash
python main.py --demo autogen
```

**Input:**  
- None (no logs or model required).

**Process:**  
- Prints a conceptual configuration for a multi-agent system inspired by Microsoft AutoGen.  
- Defines agent roles (UserProxy, ThreatAnalyst, Responder, Executor) and workflow sequence.

**Output:**  
- JSON-formatted structure showing how such a system would coordinate:

  ```json
  {
    "agents": [
      {"name": "UserProxy", "type": "user_proxy", "role": "Receives/Supervises task"},
      {"name": "ThreatAnalyst", "type": "assistant", "role": "Summarizes Okta anomalies"},
      {"name": "Responder", "type": "assistant", "role": "Proposes containment/validation"},
      {"name": "Executor", "type": "executor", "role": "Dry-run commands/tools"}
    ]
  }
  ```
- Conceptual only — no inference.

---

### 6⃣ Hybrid Reasoning Pipeline (Flagship Demo)

```bash
python main.py --demo hybrid
```

**Input:**  
- `okta-logs.txt` — primary log dataset.  
- Model configuration from `config.yaml`.

**Process:**

1. Rule-based engine produces **signals** (deterministic anomalies).  
2. LangChain reasoning chain summarizes and prioritizes risks.  
3. **Planner Agent:** Generates numbered containment/validation plan.  
4. **Executor Agent:** Produces safe, read-only shell commands using `$FILE` variable.  
5. `_strip_unknown_entities()` ensures model output mentions only real users/IPs from logs.

**Output:**  
- Three structured sections printed to console:

  ```
  == Prioritized risks (LangChain) ==
  - High: Burst of login failures for alice@gallaudet.edu
  - Medium: Impossible travel from US -> DE

  == Planner ==
  1. Temporarily suspend user account.
  2. Require MFA reset.
  3. Block suspicious IP addresses.

  == Executor ==
  - Item: Find failed logins for Alice
    Command: grep 'alice@gallaudet.edu' $FILE | grep '"result":"FAILURE"'
  - Item: Count unique IPs
    Command: jq '.client.ipAddress' $FILE | sort | uniq -c
  ```

**Output Type:**  
- Structured text (console).  
- Grounded, non-hallucinated reasoning pipeline result.

## 🔄 Integration Flow

Here’s what happens when `--demo hybrid` runs:

```
1️⃣ RuleDetector → extracts signals from Okta logs.
2️⃣ Reasoning Chain → summarizes into a prioritized risk list.
3️⃣ Planner Agent → converts that list into 3–5 short containment steps.
4️⃣ Executor Agent → translates steps into jq/awk/grep commands.
```

### Dataflow Diagram

```
Okta JSONL Logs
   │
   ▼
RuleDetector ───► Signals
   │
   ▼
Reasoning Chain (LCEL)
   │        —> structured, concise risk summary
   ▼
Planner Agent (SimpleAgent)
   │        —> converts summary into actionable steps
   ▼
Executor Agent (SimpleAgent)
   │        —> converts steps into jq/awk/grep shell commands ($FILE=okta-logs.txt)
   ▼
Operator Output (dry-run script)
```



---

### 7⃣ Run All Demos Sequentially

```bash
python demos/run_all.py
```

**Input:**  
- Uses `okta-logs.txt` and built-in test strings.  
- Executes each of the previous demos in sequence.

**Output:**  
- Composite printed log showing all modes, in order:  

  ```
  === DEMO: rules ===
  ...
  === DEMO: langchain1 ===
  ...
  === DEMO: hybrid ===
  ✓ Hybrid pipeline complete
  ```

**Purpose:**  
- Full showcase of system evolution — ideal for **training**, **presentations**, and **evaluation**.

## 🔐 Privacy & Offline Operation

- 100% local execution — **no external API calls or telemetry**  
- Suitable for regulated environments (FERPA / GLBA compliant)  
- Works on CPU, GPU, or Apple Metal (MPS)

---

## 📁 Repository Structure

```
agentic-threat-analyst-okta/
├─ README.md
├─ config.yaml
├─ requirements.txt
├─ okta-logs.txt
├─ main.py
│
├─ core/
│  ├─ ingest.py      # Parses & normalizes Okta logs
│  ├─ rules.py       # Deterministic anomaly detection
│  └─ report.py      # CLI tabular reporting
│
├─ agents/
│  └─ simple_agent.py
│
├─ autogen_sim/
│  └─ conversation.py # Conceptual AutoGen workflow
│
├─ chains/
│  └─ chains.py       # LangChain reasoning templates
│
├─ hybrid/
│  └─ hybrid.py       # Hybrid symbolic + neural reasoning
│
└─ demos/
   └─ run_all.py
```

---

## 🧩 Future Enhancements

- Add Okta System Log API ingestion for live analysis  
- Expand rule catalog (MFA bypass, privilege escalation)  
- Add correlation visualization and risk scoring  
- Evaluate LLM reasoning accuracy metrics  

---

## 🧾 License

Open-sourced under **MIT**.  
All AI reasoning components run locally — no data leaves your machine.

---

**Keywords:** Okta, cybersecurity, LangChain, Hugging Face, AutoGen, agentic AI, rule-based detection, explainable AI
