#!/usr/bin/env python3
"""
main.py — Agentic Threat Analyst (Okta Logs)

Demos:
  --demo rules          : deterministic rule detections only
  --demo langchain1     : single-step triage summary (LCEL)
  --demo langchain2     : multi-step plan + execution details (LCEL)
  --demo simple_agents  : three-role agent chain using HF pipeline directly
  --demo autogen        : conceptual AutoGen-style workflow (no inference)
  --demo hybrid         : rules + LCEL reasoning + agentic planning/execution
"""

import argparse
import yaml

from core.ingest import load_and_normalize
from core.rules import RuleDetector

# LCEL chains (prompt | llm | StrOutputParser):
from chains.chains import build_langchain_llm, triage_chain, plan_chain, step_chain

from agents.simple_agent import SimpleAgent
from autogen_sim.conversation import demo_autogen_concept
from hybrid.hybrid import run_hybrid


def load_cfg():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


def run_rules_only(log_path: str):
    evts = load_and_normalize(log_path)
    rd = RuleDetector()
    findings = []
    for e in evts:
        findings.extend(rd.evaluate(e))
    return findings


def main():
    ap = argparse.ArgumentParser(description="Agentic Threat Analyst — Okta Logs")
    ap.add_argument("--input", default="okta-logs.txt", help="Path to Okta logs (JSONL preferred)")
    ap.add_argument(
        "--demo",
        choices=["langchain1", "langchain2", "simple_agents", "autogen", "hybrid", "rules"],
        default="hybrid",
        help="Which demo to run",
    )
    args = ap.parse_args()

    cfg = load_cfg()
    model_name = cfg["model"]["hf_model"]
    max_new = cfg["model"]["max_new_tokens"]
    temperature = cfg["model"]["temperature"]

    # ---- rules-only (no LLM build) ----
    if args.demo == "rules":
        findings = run_rules_only(args.input)
        print("== Rule-based findings ==")
        for r, severity, desc in findings[:50]:
            print(f"{severity.upper():<6}  {r:<30}  {desc}")
        return

    # ---- langchain1 (build LLM here only when needed) ----
    if args.demo == "langchain1":
        llm = build_langchain_llm(model_name, max_new_tokens=max_new, temp=temperature)
        chain = triage_chain(llm)
        signal = "Multiple login failures for alice@gallaudet.edu from 198.51.100.23 over 10 minutes."
        out = chain.invoke({"signal": signal})
        print(out)
        return

    # ---- langchain2 (build LLM here only when needed) ----
    if args.demo == "langchain2":
        llm = build_langchain_llm(model_name, max_new_tokens=max_new, temp=temperature)
        planner = plan_chain(llm)
        executor = step_chain(llm)
        goal = "Investigate burst of failed Okta logins and possible account takeover"
        plan_text = planner.invoke({"goal": goal})
        print("Plan:\n", plan_text, "\n")
        detail = executor.invoke({"step": "Extract top failing users and IPs in last 60 minutes from okta-logs.txt"})
        print("Execution detail:\n", detail)
        return

    # ---- simple_agents (direct HF pipeline inside this block; no LangChain build here) ----
    if args.demo == "simple_agents":
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline as hfpipe

        evts = load_and_normalize(args.input)
        rd = RuleDetector()
        findings = []
        for e in evts:
            findings.extend(rd.evaluate(e))

        summary = "\n".join([f"{f[0]} | {f[1]} | {f[2]}" for f in findings[:20]]) or "No anomalies"

        tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        if tok.pad_token is None:
            tok.pad_token = (
                getattr(tok, "eos_token", None)
                or tok.special_tokens_map.get("eos_token")
                or tok.unk_token
            )

        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            attn_implementation="eager",
            torch_dtype="auto",
        )
        model.config.use_cache = False

        pipe = hfpipe(
            "text-generation",
            model=model,
            tokenizer=tok,
            max_new_tokens=max_new,
            temperature=temperature,
            top_p=0.9,
            eos_token_id=tok.eos_token_id,
            return_full_text=False,
            trust_remote_code=True,
        )

        loader = SimpleAgent("LogLoader", "log ingestion specialist", pipe)
        analyst = SimpleAgent("ThreatAnalyst", "Okta security analyst", pipe)
        responder = SimpleAgent("Responder", "incident responder", pipe)

        print(f"[{loader.name}]\n{summary}\n")
        analysis = analyst.say("Summarize risks from:\n" + summary)
        print(f"[{analyst.name}]\n{analysis}\n")
        response = responder.say(f"Given this analysis:\n{analysis}\n\nPropose immediate containment steps.")
        print(f"[{responder.name}]\n{response}\n")
        return

    # ---- autogen (no LLM build) ----
    if args.demo == "autogen":
        demo_autogen_concept()
        return

    # ---- hybrid (no LangChain LLM build here; run_hybrid builds its own once) ----
    if args.demo == "hybrid":
        run_hybrid(
            args.input,
            model_name,
            max_new_tokens=max_new,
            temp=temperature,
        )
        return


if __name__ == "__main__":
    main()
