from typing import Protocol


class LanguageModelProvider(Protocol):
    model_name: str

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate a text response from the supplied prompts."""
        ...