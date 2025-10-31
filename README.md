# 🛡️ Agentic Threat Analyst

**Deterministic rules + LangChain reasoning + lightweight agents. 100% local, openai-compatible LM Studio endpoint.**

---

## Overview

This project demonstrates how to build an **Agentic AI Threat Analyst** system that ingests logs, identifies suspicious activity, and produces human-readable triage reports — all **offline and privacy-preserving**.

This project ingests **Okta System Logs** (`okta-logs.txt`), detects anomalies with a **deterministic rule engine**, and layers **LLM reasoning** and **agentic planning/execution** on top—while staying **local** by talking to an **OpenAI‑compatible LM Studio** endpoint.

This project was inspired by the [*MarkTechPost* tutorial](https://www.marktechpost.com/2025/10/21/how-i-built-an-intelligent-multi-agent-systems-with-autogen-langchain-and-hugging-face-to-demonstrate-practical-agentic-ai-workflows/) — _“How I Built an Intelligent Multi-Agent System with AutoGen, LangChain, and Hugging Face” (Oct 2025)_  — but adapts it for a **cybersecurity use case**: analyzing authentication and identity events from Okta.

**Key parts:**

- `core/ingest.py` — Normalizes raw Okta events (JSONL or `key=value`) into a consistent schema.
- `core/rules.py` — Deterministic `RuleDetector` (failed-login bursts, impossible travel).
- `chains/chains.py` — Builds an OpenAI‑compatible LangChain LLM and defines LCEL chains (triage, plan, step).
- `agents/simple_agent.py` — Tiny role‑based agent wrapper for LangChain chat LLMs.
- `hybrid/hybrid.py` — Flagship pipeline: rules → reasoning → planner → executor with guardrails.
- `autogen_sim/conversation.py` — Conceptual AutoGen‑style multi‑agent layout (no API calls).
- `core/report.py` — Tabular CLI output helper.
- `main.py` — Demo driver.
- `demos/run_all.py` — Runs all demos in sequence.
- `config.yaml` — Model + rule configuration (LM Studio base URL, model name, thresholds).
- `requirements.txt` — LangChain v0.3+ stack (`langchain-openai`) + utilities.

---

## Quick Start

### 1) Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

> Prefer `uv`?
> 
> ```bash
> uv venv && source .venv/bin/activate
> uv pip install -r requirements.txt
> ```

### 2) Point to LM Studio (OpenAI‑compatible)
Update `config.yaml` (already set to a safe default) **or** use env vars:

- **Default in `config.yaml`:**

```yaml
model:
    provider: openai_compat
    model_name: openai/gpt-oss-20b
    base_url: http://192.168.1.226:1234/v1
    max_new_tokens: 768
    temperature: 0.0
```
  
- **Environment variables (override if needed):**

  ```bash
  export OPENAI_BASE_URL=http://<lm-studio-ip>:1234/v1   # or LM_STUDIO_BASE_URL
  export OPENAI_API_KEY=lm-studio                        # any non-empty string
  ```

### 3) Add Logs
Place your Okta export at the repo root.

```
okta-logs.txt
```
- JSONL preferred (one event per line).  
- `key=value` lines supported (e.g., `actor.alternateId=alice@example.edu outcome=FAILURE ...`).

---

## Demos

Run:

```bash
python main.py --demo <mode> --input okta-logs.txt
```

Modes:

1. **`rules`** — Deterministic engine only (no LLM).

   ```bash
   python main.py --demo rules
   ```
   Prints `SEV | RULE | DETAILS` for findings.

2. **`langchain1`** — Triage chain (summary of a synthetic signal).

   ```bash
   python main.py --demo langchain1
   ```

3. **`langchain2`** — Plan + step‑to‑commands.

   ```bash
   python main.py --demo langchain2
   ```

4. **`simple_agents`** — Three lightweight agents over rule findings (Loader → Analyst → Responder).

   ```bash
   python main.py --demo simple_agents
   ```

5. **`autogen`** — **Conceptual** AutoGen‑style config printed as JSON (no inference).

   ```bash
   python main.py --demo autogen
   ```

6. **`hybrid`** — **Flagship** pipeline: rules → reasoning → planner → executor.

   ```bash
   python main.py --demo hybrid
   ```
   - Entity guardrails drop lines mentioning **unknown** emails/IPs.
   - Executor prompt enforces **jq‑only** (with safe pipes) and real Okta JSON keys.
   - Post‑processor ensures every `- Item:` is followed by a `Command:`.

> Batch showcase:

> ```bash
> python demos/run_all.py
> ```

---

## How It Works

1. **Ingest/Normalize** (`core/ingest.py`)  
   - Accepts JSONL or `key=value` lines.  
   - Coerces timestamps to **ISO‑8601 UTC**.  
   - Canonical fields: `timestamp`, `event_type`, `message`, `user`, `ip`, `country`, `outcome`, `raw`.

2. **Deterministic Rules** (`core/rules.py`)  
   - Sliding‑window counters for **failed logins per user/IP**.  
   - **Impossible travel** detection by country variance within a time window.  
   - Configurable via `config.yaml` (`failed_*`, `impossible_travel_window`).

3. **LLM Reasoning & Chains** (`chains/chains.py`)  
   - `build_langchain_llm` wraps `ChatOpenAI` with **LM Studio base_url**.  
   - Chains: `triage_chain`, `plan_chain`, `step_chain` (LCEL).

4. **Agents** (`agents/simple_agent.py`)  
   - Minimal role‑based wrapper over the shared LLM.

5. **Hybrid Pipeline** (`hybrid/hybrid.py`)  
   - **Risk analysis prompt** → bullet list.  
   - **Guardrails**: `_strip_unknown_entities` removes lines with unseen principals.  
   - **Planner prompt** groups actions by `[R#]`.  
   - **Executor prompt** outputs **jq** commands against `okta-logs.txt` only.  
   - **Repair**: `_ensure_item_commands` fills missing `Command:` lines, using risk‑to‑email hints.

---

## Sample Run

```
== Prioritized risks (LangChain) ==
- **High** – *Impossible travel* (alice@company.com: US → JP in a short time)
  • Indicates potential credential compromise or account hijacking.

- **Medium** – *Excessive failed logins* (charlie@company.com, 8–11 failures)
  • Brute‑force attempt; account may be under attack.

- **Medium** – *Excessive failed logins* (eve@company.com, 8–11 failures)
  • Same risk as above; multiple attempts suggest targeted probing.

- **Medium** – *Excessive failed logins* (frank@company.com, 8–11 failures)
  • Indicates possible credential guessing or compromised credentials.

== Risk IDs ==
R1: **High** – *Impossible travel* (alice@company.com: US → JP in a short time)
R2: **Medium** – *Excessive failed logins* (charlie@company.com, 8–11 failures)
R3: **Medium** – *Excessive failed logins* (eve@company.com, 8–11 failures)
R4: **Medium** – *Excessive failed logins* (frank@company.com, 8–11 failures)

== Planner ==
[R1] Impossible travel (alice@company.com: US → JP in a short time)
- Verify travel itinerary and timestamps with HR.
- Temporarily lock the account until verification completes.
- Enable MFA for all future logins.

[R2] Excessive failed logins (charlie@company.com, 8–11 failures)
- Lock the account and require password reset.
- Review login logs for suspicious IPs.
- Enforce MFA on next successful login.

[R3] Excessive failed logins (eve@company.com, 8–11 failures)
- Lock the account and require password reset.
- Check for brute‑force patterns in logs.
- Enable MFA on next successful login.

[R4] Excessive failed logins (frank@company.com, 8–11 failures)
- Lock the account and require password reset.
- Investigate login attempts for unusual IPs.
- Enable MFA on next successful login.

== Executor ==
[R1]
- Item: Alice – timeline (time, result, IP, country)

  Command: jq -r 'select(.actor.alternateId=="alice@company.com") | [.published, .outcome.result, (.request.ipChain[0].ip // .client.ipAddress), (.request.ipChain[0].geographicalContext.country // .client.geographicalContext.country)] | @tsv' okta-logs.txt | sort
[R2]
- Item: Charlie – count of failed login attempts

  Command: jq -r 'select(.actor.alternateId=="charlie@company.com" and .outcome.result=="FAILURE") | .actor.alternateId' okta-logs.txt | wc -l
[R3]
- Item: Eve – count of failed login attempts

  Command: jq -r 'select(.actor.alternateId=="eve@company.com" and .outcome.result=="FAILURE") | .actor.alternateId' okta-logs.txt | wc -l
[R4]
- Item: Frank – count of failed login attempts
  Command: jq -r 'select(.actor.alternateId=="frank@company.com" and .outcome.result=="FAILURE") | .actor.alternateId' okta-logs.txt | wc -l

✓ Hybrid pipeline complete

```

----

## Repository Layout

```
agentic-threat-analyst-okta/
├─ README.md
├─ config.yaml
├─ requirements.txt
├─ okta-logs.txt
├─ run.sh
├─ main.py
│
├─ core/
│  ├─ ingest.py
│  ├─ rules.py
│  └─ report.py
│
├─ agents/
│  └─ simple_agent.py
│
├─ chains/
│  └─ chains.py
│
├─ hybrid/
│  └─ hybrid.py
│
├─ autogen_sim/
│  └─ conversation.py
│
└─ demos/
   └─ run_all.py
```

---

## Configuration Reference (`config.yaml`)

```yaml
model:
  provider: openai_compat
  model_name: openai/gpt-oss-20b
  base_url: http://192.168.1.226:1234/v1
  max_new_tokens: 768
  temperature: 0.0

rules:
  failed_login_window_min: 60
  failed_per_user: 8
  failed_per_ip: 20
  impossible_travel_window: 90
```

> You can override at runtime via environment variables:
> `OPENAI_BASE_URL`, `OPENAI_API_KEY` (or `LM_STUDIO_BASE_URL`, `LM_STUDIO_API_KEY`).

---

## Requirements

- Python 3.10+
- LM Studio running an OpenAI‑compatible chat model (e.g., `openai/gpt-oss-20b`).
- `jq` in your shell for executor commands (hybrid demo).

Install Python deps:

```bash
pip install -r requirements.txt
# or
uv pip install -r requirements.txt
```

---

## Privacy & Local‑First

- No external API calls are required; LM Studio runs locally on your network.
- Suitable for environments with FERPA/GLBA constraints (no telemetry from this repo).

---

## Troubleshooting

- **LLM calls fail / 404:** Verify `OPENAI_BASE_URL` matches LM Studio (e.g., `http://<ip>:1234/v1`).
- **Model not loaded in LM Studio:** Start a chat model and ensure it supports the OpenAI Chat API.
- **Empty/Weird jq results:** Confirm your `okta-logs.txt` uses Okta’s JSON keys referenced in prompts.
- **Performance (Apple Silicon):** LM Studio model choice matters; try a smaller chat model for quick tests.

---

## License

MIT — see `LICENSE` (or include one).

**Keywords:** Okta, cybersecurity, LM Studio, LangChain, LCEL, ChatOpenAI, jq, agentic AI, deterministic rules, incident response


---

## 🔧 What Happens During a Hybrid Run (`--demo hybrid`)

The **hybrid** pipeline is the flagship end‑to‑end path that combines deterministic signals with tightly‑scoped LLM reasoning and post‑processing guardrails. Here’s the exact sequence, mapped to source files and important functions.

### 1) Ingest & Normalize ( `core/ingest.py` )
1. `load_and_normalize(log_path)`
   - Reads `okta-logs.txt` as **JSONL** (preferred) or **key=value** lines.
   - Parses key/value lines with `parse_kv_line` (supports dotted keys like `client.ipAddress` and quoted values).
   - Timestamps are coerced to **ISO‑8601 UTC** by `_to_iso` (epoch ms/s, or ISO with/without `Z` → always UTC).
   - Each raw event is normalized to a canonical dict:
     - `timestamp`, `event_type`, `message`, `user`, `ip`, `country`, `outcome`, `raw`
   - Output is chronologically **sorted** by `timestamp`.

### 2) Deterministic Rule Signals ( `core/rules.py` )
2. `RuleDetector().evaluate(evt)` across events:
   - **Failed login bursts**: sliding windows for per‑user and per‑IP failures using `deque`s.
   - **Impossible travel**: country changes within a short time window.
   - Thresholds from `config.yaml` → `rules.*` (e.g., `failed_per_user: 8`, `failed_per_ip: 20`, `impossible_travel_window: 90` minutes).
   - Emits tuples `(rule_name, severity, details)`, e.g.:
     - `("excessive_failed_logins_user", "medium", "user alice@example.edu failures=9")`
     - `("excessive_failed_logins_ip", "high", "ip 198.51.100.23 failures=24")`
     - `("impossible_travel", "high", "alice@example.edu: US -> JP quickly")`
3. The first ~15 findings are joined into a **signals** string for the LLM.

### 3) Build One Shared LLM ( `chains/chains.py` )
4. `llm = build_langchain_llm(model_name, max_new_tokens, temp)`
   - Wraps `langchain_openai.ChatOpenAI` pointed at an **OpenAI‑compatible** LM Studio endpoint.
   - Endpoint resolution (in priority order): `OPENAI_BASE_URL` → `LM_STUDIO_BASE_URL` → default in `config.yaml`.
   - API key: `OPENAI_API_KEY` → `LM_STUDIO_API_KEY` → default `"lm-studio"` (LM Studio ignores the value but requires non‑empty).  
   - Returns a **Runnable** that takes a string and returns `.content` text.

### 4) Risk Reasoning (LangChain Prompt)
5. A structured **reasoning prompt** is run through the LLM to turn signals into a short prioritized list:
   - Guardrails in the prompt: *“Use ONLY the signals given; do not invent users/IPs; if missing, say ‘No data’.”*
   - Output: bullet list of risks with terse justifications.

### 5) Anti‑Hallucination Guardrail
6. `_allowed_users_and_ips(evts)` collects the **actual** users/IPs seen in the current log window.
7. `_strip_unknown_entities(text, allowed_users, allowed_ips)` removes any lines that mention **unseen** principals.

### 6) Risk Numbering & Email Hints
8. `_tag_risks(analysis_text)` extracts bullets and labels them `R1`, `R2`, … (keeps original order).
9. `_extract_risk_email_map(risk_items)` builds `{R#: email_or_None}` to help the executor infer user‑scoped commands later.
   - Example: `{ "R1": "alice@example.edu", "R2": None, ... }`

### 7) Planner (Grouped, Concise Actions)
10. **Planner prompt** (LangChain) consumes the labeled risks and emits **grouped actions**:
    ```
    [R1] <one‑line risk>
    - <action 1>
    - <action 2>
    - <action 3>
    ```
    - Prompt forbids invented users/IPs.  
    - Output is again sanitized with `_strip_unknown_entities(...)`.

### 8) Executor (jq‑only, Strict Schema)
11. **Executor prompt** generates command blocks **per risk** using **only** allowed Okta JSON keys:
    - Keys permitted in the prompt:
      - `.actor.alternateId`
      - `.outcome.result`
      - `.request.ipChain[0].ip`, `.client.ipAddress`
      - `.request.ipChain[0].geographicalContext.country`, `.client.geographicalContext.country`
      - `.published`
    - **Constraints**:
      - Read‑only commands against **`okta-logs.txt`** (no `$FILE` indirection).
      - Allowed pipes: `sort | uniq -c | sort -nr | head | wc -l | column -t`.
      - If a valid jq can’t be formed → **`Command: No data`**.
    - **Required format** per risk:
      ```
      [R#]
      - Item: <what>
        Command: <jq ... okta-logs.txt>
      - Item: ...
        Command: ...
      ```
12. Post‑processing: `_ensure_item_commands(text, risk_email_map)` guarantees **every** `- Item:` line is immediately followed by a `Command:` line.
    - Uses `_infer_command(item_line, user_hint)`:
      - Detects an email in the item text or falls back to the risk’s email hint.
      - Emits safe jq patterns (timeline, failed counts, IP aggregation, country list, JP‑origin timestamps, etc.).
      - If inference is unsafe/insufficient → `Command: No data`.

### 9) Output Sections
13. The pipeline prints three blocks to the console:
    - `== Prioritized risks (LangChain) ==`  
      *Guardrailed bullets from the reasoning step.*
    - `== Risk IDs ==`  
      *`R#:` lines mapping IDs to the bullet text (also powering email hints).*  
    - `== Executor ==`  
      *Per‑risk itemized jq commands against `okta-logs.txt` (fully grounded).*

### 10) Completion
14. Prints `✓ Hybrid pipeline complete` to confirm the end of run.

---

### Dataflow Recap

```text
okta-logs.txt
    │
    ▼
load_and_normalize ──► events (UTC timestamps, canonical fields)
    │
    ▼
RuleDetector.evaluate ──► findings (signals string)
    │
    ▼
LLM (reasoning prompt) ──► prioritized risks (bullets)
    │
    ▼   (filter by known users/IPs)
_strip_unknown_entities
    │
    ├─► _tag_risks / _extract_risk_email_map ──► R# labels + hints
    │
    ▼
LLM (planner prompt) ──► grouped actions by [R#]
    │
    ▼
LLM (executor prompt) ──► jq commands per [R#] (okta-logs.txt only)
    │
    ▼   (repair)
_ensure_item_commands ──► guaranteed Command lines
    │
    ▼
Console output (3 sections) ──► Done
```

---

### Why This Design?
- **Grounded**: Every LLM step is fenced to the provided signals and real Okta keys.
- **Explainable**: Deterministic rules produce auditable seeds for the LLM.
- **Safe**: Guardrails delete lines with unknown users/IPs; executor is jq‑only, read‑only.
- **Practical**: Post‑processor fills in missing commands so the output is always actionable.


---

## 🧠 Agent Roles, Purpose, and Configuration

The **Agentic Threat Analyst** uses lightweight, role-based agents to simulate a security operations (SOC) workflow.  
Each agent shares the same **LLM instance** (from `build_langchain_llm`) for consistency but maintains its **own memory log** of interactions.

### 1️⃣ Agent Design ( `agents/simple_agent.py` )
Each agent is an instance of the `SimpleAgent` class:

```python
class SimpleAgent:
    def __init__(self, name: str, role: str, llm, *, max_input_chars: int = 8000):
        self.name = name
        self.role = role
        self.llm = llm
        self.memory = []
```
- **`name`** — human-readable identifier (e.g., `"ThreatAnalyst"`).  
- **`role`** — description injected into the system prompt (e.g., `"Okta security analyst"`).  
- **`llm`** — the shared LangChain LLM (OpenAI-compatible LM Studio endpoint).  
- **`memory`** — stores `{user, agent}` message pairs for that specific agent (local-only, not fed back).  
- **`max_input_chars`** — clips long messages to prevent token overflows.  

Each `SimpleAgent` builds a reusable chain:

```python
self._prompt = ChatPromptTemplate.from_messages([
    ("system", "You are {name}: {role}. Follow instructions exactly. "
               "Do not invent users, IPs, devices, or events. "
               "If needed info is missing, say 'No data'."),
    ("user", "{message}")
])
self._chain = self._prompt | self.llm | StrOutputParser()
```

**Behavior:**  
- Each time you call `.say(message)`, the agent composes a message using that fixed prompt and returns a one-shot reply.  
- No multi-turn context is carried forward (but the history is logged in `.memory` if needed for debugging or analytics).  

---

### 2️⃣ Agents in Use ( `main.py --demo simple_agents` )
In the **Simple Agents demo**, three agents are instantiated and run sequentially over the same shared LLM:

| Agent | Role | Purpose |
|--------|------|----------|
| 🧾 **LogLoader** | "log ingestion specialist" | Receives findings from the deterministic rule engine and formats them as text. |
| 🧠 **ThreatAnalyst** | "Okta security analyst" | Summarizes risks and patterns from rule-based findings using concise, data-grounded language. |
| 🛡️ **Responder** | "incident responder" | Suggests immediate containment or remediation actions based on the analyst’s output. |

**Pipeline flow:**  
1. `LogLoader` prints the normalized list of anomalies (e.g., excessive failed logins, impossible travel).  
2. `ThreatAnalyst.say()` summarizes risk implications from those anomalies.  
3. `Responder.say()` proposes incident response steps given the analysis.

Example run:

```text
[LogLoader]
excessive_failed_logins_user | medium | user alice@example.edu failures=9

[ThreatAnalyst]
- Repeated failed logins suggest possible credential stuffing.
- Investigate source IPs and geolocation anomalies.

[Responder]
- Lock the affected account temporarily.
- Require MFA reset.
- Block IPs showing repeated failures.
```

---

### 3️⃣ Agents in Hybrid Mode
During the **hybrid run** (`--demo hybrid`):

- Agents are not explicitly constructed, but **their logic is embedded** into the multi-prompt flow:
  - The **LLM reasoning prompt** plays the role of the **ThreatAnalyst**.
  - The **Planner prompt** acts as the **Responder**, suggesting actions.
  - The **Executor prompt** simulates a **Command Engineer** role that converts each plan step into concrete jq commands.
- These roles are implicit, but they mirror the same chain-of-responsibility structure as the explicit agents demo.

---

### 4️⃣ Configuring Agents or Adding New Ones

To add or adjust an agent:

1. **Define the role and tone** — edit or expand the system message in `SimpleAgent`.
2. **Adjust memory behavior** — if you want conversational persistence, include prior turns in the next `.say()` prompt (or use `RunnableWithMessageHistory`).
3. **Add a new stage** — for example:

```python
   reviewer = SimpleAgent("Reviewer", "validates responder actions for compliance", llm)
   review = reviewer.say(f"Evaluate these response actions:
{response}")
   print("[Reviewer]\n" + review)
```

4. **Parallelize** — you can run multiple agents concurrently with asyncio or threads since they all share a read-only LLM client.

---

### 5️⃣ Why Agents?

| Advantage | Description |
|------------|-------------|
| **Transparency** | Each agent produces its own output block, so reasoning steps are human-auditable. |
| **Reusability** | The same `SimpleAgent` class can represent any role just by changing its prompt. |
| **Scalability** | New roles (e.g., *Forensic Examiner*, *Compliance Reviewer*) can be dropped in without changing the architecture. |
| **Performance** | Reuses one shared LLM connection; avoids redundant model re-initialization. |

---

### 6️⃣ Future Extensions
- Add **real memory replay** using LangChain’s `ConversationBufferMemory` or `RunnableWithMessageHistory`.
- Connect a **vector store** (e.g., FAISS or Chroma) to let agents recall prior investigations.
- Introduce **coordination logic** (a lightweight “Orchestrator”) to decide which agent should act next.
- Extend roles to **MFA enforcement**, **privilege escalation detection**, or **user behavior baselining**.

---
