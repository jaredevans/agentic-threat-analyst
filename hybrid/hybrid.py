from typing import Any, Set
from core.ingest import load_and_normalize
from core.rules import RuleDetector
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline as hf_pipeline
from agents.simple_agent import SimpleAgent


def _build_tokenizer(model_name: str):
    tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = (
            getattr(tok, "eos_token", None)
            or tok.special_tokens_map.get("eos_token")
            or tok.unk_token
        )
    tok.truncation_side = "left"
    tok.model_max_length = 4096
    return tok


def _build_model(model_name: str):
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        attn_implementation="eager",
        dtype="auto",
    )
    # Avoid DynamicCache.seen_tokens paths
    model.config.use_cache = False
    if hasattr(model, "generation_config"):
        try:
            model.generation_config.use_cache = False
        except Exception:
            pass
    return model


def _as_str(x: Any) -> str:
    if isinstance(x, str):
        return x
    to_string = getattr(x, "to_string", None)
    if callable(to_string):
        return to_string()
    if isinstance(x, dict):
        return "\n".join(f"{k}: {v}" for k, v in x.items())
    return str(x)


def _wrap_as_runnable(textgen):
    def _invoke(prompt_or_dict):
        value = _as_str(prompt_or_dict)
        out = textgen(value, do_sample=False, return_full_text=False)
        return out[0]["generated_text"]
    return RunnableLambda(_invoke)


def _allowed_users_and_ips(evts) -> tuple[Set[str], Set[str]]:
    users = {e.get("user") for e in evts if e.get("user")}
    ips = {e.get("ip") for e in evts if e.get("ip")}
    return users, ips


def _strip_unknown_entities(text: str, users: Set[str], ips: Set[str]) -> str:
    """
    Drop lines that mention emails/IPs we didn't observe in the current log window.
    A tiny, conservative guardrail against hallucinated principals.
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


def run_hybrid(log_path: str, model_name: str, max_new_tokens: int = 256, temp: float = 0.0):
    # 1) Deterministic rules → signals (ground truth)
    evts = load_and_normalize(log_path)
    rd = RuleDetector()
    findings = []
    for e in evts:
        findings.extend(rd.evaluate(e))

    # Keep a small, readable slice
    signals = "\n".join([f"{f[0]} | {f[1]} | {f[2]}" for f in findings[:15]]) or "No anomalies."

    # 2) Build the textgen once (deterministic decoding)
    tok = _build_tokenizer(model_name)
    model = _build_model(model_name)
    textgen = hf_pipeline(
        "text-generation",
        model=model,
        tokenizer=tok,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        top_p=None,
        temperature=0.0,           # ignored when do_sample=False; kept for clarity
        eos_token_id=tok.eos_token_id,
        trust_remote_code=True,
    )
    llm = _wrap_as_runnable(textgen)

    # 3) Reasoning: strictly grounded prompt
    reasoning_prompt = PromptTemplate(
        input_variables=["signals"],
        template=(
            "<s><|user|>\n"
            "You are a senior security analyst.\n"
            "Use ONLY the signals given below. Do not invent users, IPs, devices, or events. "
            "If information is missing, answer 'No data'.\n\n"
            "Return a prioritized bullet list of risks with very short justifications.\n\n"
            "Signals:\n{signals}\n"
            "<|end|>\n<|assistant|>\n"
        ),
    )
    reasoning_chain = reasoning_prompt | llm | StrOutputParser()
    analysis_raw = reasoning_chain.invoke({"signals": signals})

    # 4) Minimal guardrail: strip lines that cite unknown principals
    allow_users, allow_ips = _allowed_users_and_ips(evts)
    analysis = _strip_unknown_entities(analysis_raw, allow_users, allow_ips)

    print("== Prioritized risks (LangChain) ==")
    print(analysis, "\n")

    # 5) Planner & Executor agents reuse the same pipeline
    planner = SimpleAgent(
        "Planner",
        "IR playbook planner — use ONLY the analysis text provided; no invented users/IPs; if missing, say 'No data'.",
        textgen,
    )
    executor = SimpleAgent(
        "Executor",
        "ops executor (dry-run) — output only read-only shell using jq/grep/awk on $FILE; if unknown, say 'No data'.",
        textgen,
    )

    plan = planner.say(
        "Create 3–5 short, numbered containment/validation actions tailored to this analysis:\n"
        f"{analysis}"
    )
    plan = _strip_unknown_entities(plan, allow_users, allow_ips)
    print("== Planner ==")
    print(plan, "\n")

    # 6) Executor phase — always use $FILE and never hardcode filenames
    act = executor.say(
        "Environment:\n"
        "  FILE=okta-logs.txt\n"
        "All commands MUST operate only on $FILE (never hardcode filenames).\n"
        "Use jq, grep, or awk only — read-only, safe commands.\n\n"
        "Format each item exactly as:\n"
        "- Item: <what>\n"
        "  Command: <shell using $FILE>\n\n"
        f"Plan:\n{plan}"
    )
    act = _strip_unknown_entities(act, allow_users, allow_ips)
    print("== Executor ==")
    print(act, "\n")

    print("✓ Hybrid pipeline complete")
