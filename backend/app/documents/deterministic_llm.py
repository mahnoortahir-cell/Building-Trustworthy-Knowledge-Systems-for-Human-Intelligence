from collections.abc import Iterator

from app.documents.llm_provider import BaseLLMProvider


class DeterministicLLMProvider(BaseLLMProvider):
    """
    Development-only deterministic language model.

    It supports both complete-response and chunked-response execution so local
    development and automated tests do not require an external provider.
    """

    STREAM_CHUNK_SIZE = 32

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

    def stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> Iterator[str]:
        response = self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        for start in range(0, len(response), self.STREAM_CHUNK_SIZE):
            yield response[
                start : start + self.STREAM_CHUNK_SIZE
            ]
