from typing import Any
import os
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI


def _as_str(x: Any) -> str:
    if isinstance(x, str):
        return x
    to_string = getattr(x, "to_string", None)
    if callable(to_string):
        return to_string()
    if isinstance(x, dict):
        return "\n".join(f"{k}: {v}" for k, v in x.items())
    return str(x)


def _wrap_as_runnable_chat(llm: ChatOpenAI):
    def _invoke(prompt_or_dict: Any) -> str:
        value = _as_str(prompt_or_dict)
        msg = llm.invoke(value)
        return getattr(msg, "content", str(msg))
    return RunnableLambda(_invoke)


def build_langchain_llm(model_name: str, max_new_tokens: int = 256, temp: float = 0.0):
    base_url = os.getenv("OPENAI_BASE_URL", os.getenv("LM_STUDIO_BASE_URL", "http://192.168.1.226:1234/v1"))
    api_key = os.getenv("OPENAI_API_KEY", os.getenv("LM_STUDIO_API_KEY", "lm-studio"))
    llm = ChatOpenAI(
        model=model_name,
        base_url=base_url,
        api_key=api_key,
        temperature=float(temp),
        max_tokens=int(max_new_tokens),
    )
    return _wrap_as_runnable_chat(llm)


_TRIAGE_TMPL = (
    "You are a security threat analyst.\n"
    "Use ONLY the signal text given. Do not invent users, IPs, or events. "
    "If needed information is missing, answer 'No data'.\n\n"
    "Summarize risk and next steps in 3 short bullets.\n\n"
    "Signal:\n{signal}\n"
)

_PLAN_TMPL = (
    "Use ONLY the goal text. No outside assumptions. If info is missing, say 'No data'.\n"
    "Return EXACTLY 3 numbered steps (each ≤2 lines).\n\n"
    "Goal:\n{goal}\n"
)

_STEP_TMPL = (
    "Use ONLY the step text. Produce 3–6 actionable items with concrete, read-only shell commands "
    "that operate on okta-logs.txt. Prefer `jq`; you may pipe to `sort|uniq -c|sort -nr|head`. "
    "Allowed keys: .actor.alternateId, .outcome.result, .request.ipChain[0].ip, "
    ".request.ipChain[0].geographicalContext.country, .client.ipAddress, "
    ".client.geographicalContext.country, .published. "
    "Do NOT search for plain words (e.g., 'lock', 'session', 'MFA enabled'); access real JSON keys only. "
    "If unknown, say 'No data'.\n\n"
    "Output format:\n"
    "- Item: <what>\n  Command: <shell>\n\n"
    "Step:\n{step}\n"
)


def triage_chain(llm):
    prompt = PromptTemplate(input_variables=["signal"], template=_TRIAGE_TMPL)
    return prompt | llm | StrOutputParser()


def plan_chain(llm):
    prompt = PromptTemplate(input_variables=["goal"], template=_PLAN_TMPL)
    return prompt | llm | StrOutputParser()


def step_chain(llm):
    prompt = PromptTemplate(input_variables=["step"], template=_STEP_TMPL)
    return prompt | llm | StrOutputParser()
