from typing import Any
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline as hf_pipeline


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
    # Avoid flash-attn paths and disable KV cache to steer away from DynamicCache issues
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        attn_implementation="eager",
        dtype="auto",
    )
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
    """Always call the HF pipeline deterministically and return text only."""
    def _invoke(prompt_or_dict: Any) -> str:
        value = _as_str(prompt_or_dict)
        out = textgen(
            value,
            do_sample=False,
            return_full_text=False,
        )
        return out[0]["generated_text"]
    return RunnableLambda(_invoke)


def build_langchain_llm(model_name: str, max_new_tokens: int = 256, temp: float = 0.0):
    # temperature ignored when do_sample=False; keep for config parity
    tok = _build_tokenizer(model_name)
    model = _build_model(model_name)

    textgen = hf_pipeline(
        task="text-generation",
        model=model,
        tokenizer=tok,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        top_p=None,
        temperature=0.0,
        repetition_penalty=1.05,
        no_repeat_ngram_size=3,
        eos_token_id=tok.eos_token_id,
        trust_remote_code=True,
    )
    return _wrap_as_runnable(textgen)


# ——— tightly-scoped prompts ———

_TRIAGE_TMPL = (
    "<s><|user|>\n"
    "You are a security threat analyst.\n"
    "Use ONLY the signal text given. Do not invent users, IPs, or events. "
    "If needed information is missing, answer 'No data'.\n\n"
    "Summarize risk and next steps in 3 short bullets.\n\n"
    "Signal:\n{signal}\n"
    "<|end|>\n<|assistant|>\n"
)

_PLAN_TMPL = (
    "<s><|user|>\n"
    "Use ONLY the goal text. No outside assumptions. If info is missing, say 'No data'.\n"
    "Return EXACTLY 3 numbered steps (each ≤2 lines).\n\n"
    "Goal:\n{goal}\n"
    "<|end|>\n<|assistant|>\n"
)

_STEP_TMPL = (
    "<s><|user|>\n"
    "Use ONLY the step text. Produce 3–6 actionable items with concrete, read-only shell commands "
    "(prefer `jq`, `grep`, `awk`) that operate on okta-logs.txt. "
    "Do NOT reference other files. If unknown, say 'No data'.\n\n"
    "Output format:\n"
    "- Item: <what>\n  Command: <shell>\n\n"
    "Step:\n{step}\n"
    "<|end|>\n<|assistant|>\n"
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
