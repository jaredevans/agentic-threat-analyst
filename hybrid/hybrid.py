# hybrid/hybrid.py
from typing import Set, List, Tuple, Dict, Optional
import re

from core.ingest import load_and_normalize
from core.rules import RuleDetector
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from chains.chains import build_langchain_llm

# -------------------- Helpers: entity guards --------------------

def _allowed_users_and_ips(evts) -> tuple[Set[str], Set[str]]:
    users = {e.get("user") for e in evts if e.get("user")}
    ips = {e.get("ip") for e in evts if e.get("ip")}
    return users, ips


def _strip_unknown_entities(text: str, users: Set[str], ips: Set[str]) -> str:
    """
    Drop lines that mention emails/IPs we didn't observe in the current log window.
    Conservative guardrail against hallucinated principals.
    """
    if not text:
        return text
    lines = []
    for ln in text.splitlines():
        bad = False
        tokens = [t.strip(",.:;()[]") for t in ln.split()]
        for t in tokens:
            # email-ish
            if "@" in t and users and (t not in users):
                bad = True
                break
            # ip-ish (very rough)
            if t.count(".") == 3 and any(ch.isdigit() for ch in t):
                if ips and (t not in ips):
                    bad = True
                    break
        if not bad:
            lines.append(ln)
    return "\n".join(lines)

# -------------------- Risk tagging & email extraction --------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def _tag_risks(analysis_text: str) -> List[Tuple[str, str]]:
    """
    Extract bullet risks from the analysis and tag them R1, R2, ...
    Returns list of (rid, text).
    """
    risks: List[str] = []
    for ln in analysis_text.splitlines():
        s = ln.strip()
        if s.startswith("-"):
            body = s.lstrip("-").strip()
            if body:
                risks.append(body)
    return [(f"R{i+1}", r) for i, r in enumerate(risks)]

def _extract_risk_email_map(risk_items: List[Tuple[str, str]]) -> Dict[str, Optional[str]]:
    """
    Build {rid -> email or None} by regexing each risk text.
    """
    out: Dict[str, Optional[str]] = {}
    for rid, txt in risk_items:
        m = _EMAIL_RE.search(txt)
        out[rid] = m.group(0) if m else None
    return out

# -------------------- Executor post-processing --------------------

def _infer_command(item_line: str, user_hint: Optional[str]) -> str:
    """
    Heuristically infer a jq command from an '- Item:' line.
    Falls back to 'No data' if we can't safely infer.
    Uses only fields present in the sample logs.
    Prefers explicit email in the item; otherwise uses user_hint from the risk.
    """
    # Prefer email in the item text, else hint from the risk
    m = _EMAIL_RE.search(item_line)
    user = m.group(0) if m else (user_hint if user_hint else None)

    lo = item_line.lower()

    # TIMELINE (time, result, ip, country)
    if "timeline" in lo and user:
        return (
            "jq -r 'select(.actor.alternateId==\"%s\") | "
            "[.published, .outcome.result, "
            "(.request.ipChain[0].ip // .client.ipAddress), "
            "(.request.ipChain[0].geographicalContext.country // .client.geographicalContext.country)] "
            "| @tsv' okta-logs.txt | sort" % user
        )

    # COUNT failed login attempts for a user
    if user and ("failed" in lo or "failures" in lo) and ("count" in lo or "number" in lo):
        return (
            "jq -r 'select(.actor.alternateId==\"%s\" and .outcome.result==\"FAILURE\") "
            "| .actor.alternateId' okta-logs.txt | wc -l" % user
        )

    # LIST IPs of failed attempts for a user
    if user and "ip" in lo and ("failed" in lo or "fail" in lo):
        return (
            "jq -r 'select(.actor.alternateId==\"%s\" and .outcome.result==\"FAILURE\") | "
            "(.request.ipChain[0].ip // .client.ipAddress)' okta-logs.txt "
            "| sort | uniq -c | sort -nr" % user
        )

    # DISTINCT countries for a user
    if user and "country" in lo:
        return (
            "jq -r 'select(.actor.alternateId==\"%s\") | "
            "(.request.ipChain[0].geographicalContext.country // .client.geographicalContext.country)' "
            "okta-logs.txt | sort | uniq -c | sort -nr" % user
        )

    # JAPAN-origin attempts (timestamps)
    if user and ("japan" in lo or " jp" in lo or lo.endswith("(jp)")):
        return (
            "jq -r 'select(.actor.alternateId==\"%s\" and "
            "((.request.ipChain[0].geographicalContext.country // .client.geographicalContext.country)==\"JP\")) "
            "| .published' okta-logs.txt | sort" % user
        )

    # GENERIC: failed timeline table (no user)
    if "failed" in lo and ("timeline" in lo or "table" in lo):
        return (
            "jq -r 'select(.outcome.result==\"FAILURE\") | "
            "[.published, .actor.alternateId, "
            "(.request.ipChain[0].ip // .client.ipAddress), "
            "(.request.ipChain[0].geographicalContext.country // .client.geographicalContext.country)] "
            "| @tsv' okta-logs.txt | column -t"
        )

    return "No data"

def _ensure_item_commands(text: str, risk_email_map: Dict[str, Optional[str]]) -> str:
    """
    Ensure that every '- Item:' is followed by a 'Command:' line.
    Uses the current [R#] section's email (if any) as a hint.
    """
    out_lines: List[str] = []
    lines = text.splitlines()
    i = 0
    current_rid: Optional[str] = None

    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()
        # Track current [R#]
        if stripped.startswith("[R") and stripped.endswith("]"):
            current_rid = stripped.strip("[]").upper()
        out_lines.append(ln)

        if stripped.startswith("- Item:"):
            # Find next non-empty; if not Command:, inject one
            j = i + 1
            buffer_blank = []
            while j < len(lines) and lines[j].strip() == "":
                buffer_blank.append(lines[j])
                j += 1
            if j >= len(lines) or not lines[j].lstrip().startswith("Command:"):
                # Determine user hint from current risk
                user_hint = risk_email_map.get(current_rid, None) if current_rid else None
                cmd = _infer_command(ln, user_hint)
                out_lines.extend(buffer_blank)
                out_lines.append(f"  Command: {cmd}")
                i = j
                continue
            else:
                # There is a Command: line; emit buffered blanks and continue
                out_lines.extend(buffer_blank)
        i += 1
    return "\n".join(out_lines)

# -------------------- Main pipeline --------------------

def run_hybrid(log_path: str, model_name: str, max_new_tokens: int = 256, temp: float = 0.0):
    # 1) Deterministic rules → signals (ground truth)
    evts = load_and_normalize(log_path)
    rd = RuleDetector()
    findings = []
    for e in evts:
        findings.extend(rd.evaluate(e))

    signals = "\n".join([f"{f[0]} | {f[1]} | {f[2]}" for f in findings[:15]]) or "No anomalies."

    # 2) Build the LLM once (OpenAI-compatible LM Studio via build_langchain_llm)
    llm = build_langchain_llm(model_name, max_new_tokens=max_new_tokens, temp=temp)

    # 3) Reasoning: prioritized risks (grounded prompt)
    reasoning_prompt = PromptTemplate(
        input_variables=["signals"],
        template=(
            "You are a senior security analyst.\n"
            "Use ONLY the signals given below. Do not invent users, IPs, devices, or events. "
            "If information is missing, answer 'No data'.\n\n"
            "Return a prioritized bullet list of risks with very short justifications.\n\n"
            "Signals:\n{signals}\n"
        ),
    )
    analysis_raw = (reasoning_prompt | llm | StrOutputParser()).invoke({"signals": signals})

    # 4) Minimal guardrail against unknown principals
    allow_users, allow_ips = _allowed_users_and_ips(evts)
    analysis = _strip_unknown_entities(analysis_raw, allow_users, allow_ips)

    print("== Prioritized risks (LangChain) ==")
    print(analysis, "\n")

    # 5) Number risks and extract per-risk email hints
    risk_items = _tag_risks(analysis)
    if not risk_items:
        risk_items = [("R1", "No data")]
    risk_list_text = "\n".join(f"{rid}: {txt}" for rid, txt in risk_items)
    risk_email_map = _extract_risk_email_map(risk_items)  # e.g., {"R1": "alice@...", "R2": "charlie@...", ...}

    print("== Risk IDs ==")
    print(risk_list_text, "\n")

    # 6) Planner: actions grouped by risk ID
    planner_prompt = PromptTemplate(
        input_variables=["risk_list_text"],
        template=(
            "You are planning containment/validation actions for the following risks.\n"
            "Each risk has an ID like R1, R2, etc. Return actions grouped by each risk ID, "
            "and keep them short, actionable, and specific. No invented users/IPs.\n\n"
            "FORMAT STRICTLY:\n"
            "[R#] <one-line risk title>\n"
            "- <concise action 1>\n"
            "- <concise action 2>\n"
            "- <concise action 3>\n\n"
            "Risks:\n{risk_list_text}\n"
        ),
    )
    plan_raw = (planner_prompt | llm | StrOutputParser()).invoke({"risk_list_text": risk_list_text})
    plan = _strip_unknown_entities(plan_raw, allow_users, allow_ips)

    print("== Planner ==")
    print(plan, "\n")

    # 7) Executor: jq-only, grouped by risk ID (explicit okta-logs.txt)
    executor_prompt = PromptTemplate(
        input_variables=["risk_list_text", "plan"],
        template=(
            "Environment:\n"
            "  Use direct path: okta-logs.txt\n"
            "Constraints:\n"
            "  - OUTPUT ONLY read-only jq commands operating on okta-logs.txt.\n"
            "  - You may pipe to sort|uniq -c|sort -nr|head|wc -l|column -t.\n"
            "  - Do NOT use grep for plain words (e.g., 'lock', 'session', 'MFA').\n"
            "  - Use only real JSON keys present in Okta logs.\n"
            "  - Allowed keys: .actor.alternateId, .outcome.result, .request.ipChain[0].ip, "
            ".request.ipChain[0].geographicalContext.country, .client.ipAddress, "
            ".client.geographicalContext.country, .published\n\n"
            "FORMAT STRICTLY (every Item MUST be immediately followed by a Command line):\n"
            "[R#]\n"
            "- Item: <what>\n"
            "  Command: <jq command using okta-logs.txt>\n"
            "- Item: <what>\n"
            "  Command: <jq command using okta-logs.txt>\n\n"
            "EXAMPLE SHAPE (do not output $FILE):\n"
            "[R1]\n"
            "- Item: Alice – timeline (time, result, IP, country)\n"
            "  Command: jq -r 'select(.actor.alternateId==\"alice@company.com\") | "
            "[.published, .outcome.result, (.request.ipChain[0].ip // .client.ipAddress), "
            "(.request.ipChain[0].geographicalContext.country // .client.geographicalContext.country)] "
            "| @tsv' okta-logs.txt | sort\n\n"
            "If you cannot produce a valid jq command for an item, write exactly:\n"
            "  Command: No data\n\n"
            "Risks:\n{risk_list_text}\n\n"
            "Plan (for reference):\n{plan}\n"
        ),
    )
    act_raw = (executor_prompt | llm | StrOutputParser()).invoke(
        {"risk_list_text": risk_list_text, "plan": plan}
    )
    act = _strip_unknown_entities(act_raw, allow_users, allow_ips)

    # 8) Repair: guarantee each '- Item:' has a 'Command:' using rid→email hints
    act = _ensure_item_commands(act, risk_email_map)

    print("== Executor ==")
    print(act, "\n")

    print("✓ Hybrid pipeline complete")
