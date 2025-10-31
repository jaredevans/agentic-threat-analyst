# 🛡️ Agentic Threat Analyst — Okta System Logs (LM Studio / OpenAI‑compatible)

**Deterministic rules + LangChain reasoning + lightweight agents. 100% local, LM Studio endpoint.**

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
   - Minimal role‑based wrapper over the shared LLM (memory of exchanges per agent).

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
