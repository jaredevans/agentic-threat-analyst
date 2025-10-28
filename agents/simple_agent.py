# agents/simple_agent.py
class SimpleAgent:
    def __init__(self, name: str, role: str, pipe, *, max_input_chars: int = 8000):
        self.name = name
        self.role = role
        self.pipe = pipe
        self.memory = []
        self.max_input_chars = max_input_chars

    def _clip(self, s: str) -> str:
        # keep tail (latest context) if too long
        return s if len(s) <= self.max_input_chars else s[-self.max_input_chars:]

    def say(self, message: str) -> str:
        message = self._clip(message)
        prompt = (
            "<s><|user|>\n"
            f"You are {self.name}: {self.role}\n"
            "Follow instructions exactly. Do not invent users, IPs, devices, or events. "
            "If needed info is missing, say 'No data'.\n\n"
            f"{message}\n"
            "<|end|>\n<|assistant|>\n"
        )
        # Deterministic, cache-safe call with light anti-repetition
        out = self.pipe(
            prompt,
            do_sample=False,
            top_p=None,
            temperature=0.0,
            repetition_penalty=1.05,
            no_repeat_ngram_size=3,
            return_full_text=False,
        )[0]["generated_text"]
        self.memory.append({"user": message, "agent": out})
        return out
