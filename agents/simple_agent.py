# agents/simple_agent.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class SimpleAgent:
    def __init__(self, name: str, role: str, llm, *, max_input_chars: int = 8000):
        """`llm` is a LangChain-chat-compatible Runnable (e.g., ChatOpenAI)."""
        self.name = name
        self.role = role
        self.llm = llm
        self.memory = []
        self.max_input_chars = max_input_chars

        self._prompt = ChatPromptTemplate.from_messages([
            ("system", "You are {name}: {role}. Follow instructions exactly. "
                        "Do not invent users, IPs, devices, or events. "
                        "If needed info is missing, say 'No data'."),
            ("user", "{message}")
        ])
        self._chain = self._prompt | self.llm | StrOutputParser()

    def _clip(self, s: str) -> str:
        # keep tail (latest context) if too long
        return s if len(s) <= self.max_input_chars else s[-self.max_input_chars:]

    def say(self, message: str) -> str:
        message = self._clip(message)
        out = self._chain.invoke({"name": self.name, "role": self.role, "message": message})
        self.memory.append({"user": message, "agent": out})
        return out
