from dataclasses import dataclass
from typing import Literal


ConversationRole = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True)
class ConversationHistoryMessage:
    """
    Read-only message supplied to the RAG and LLM layers.

    This type deliberately does not expose SQLAlchemy models outside the
    persistence layer.
    """

    role: ConversationRole
    content: str
