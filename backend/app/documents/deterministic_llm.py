from app.documents.llm_provider import BaseLLMProvider


class DeterministicLLMProvider(BaseLLMProvider):
    """
    Development-only LLM.

    Useful until a real model is connected.
    """

    @property
    def model_name(self) -> str:
        return "deterministic-llm"

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return (
            "This is a deterministic placeholder response.\n\n"
            + user_prompt
        )