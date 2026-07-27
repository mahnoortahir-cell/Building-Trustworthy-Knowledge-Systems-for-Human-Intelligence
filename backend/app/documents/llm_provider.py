from abc import ABC, abstractmethod
from collections.abc import Iterator


class BaseLLMProvider(ABC):
    """
    Base interface for all language-model providers.

    Providers must implement synchronous complete-text generation.

    Streaming has a backward-compatible default implementation that yields the
    complete generated response as one chunk. Providers with native streaming
    support may override stream().
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Generate and return a complete textual response.
        """
        ...

    def stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> Iterator[str]:
        """
        Stream textual response chunks.

        The default implementation preserves compatibility with providers that
        only support complete-response generation.
        """

        response = self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        if not isinstance(response, str):
            raise TypeError(
                "The language-model provider returned a non-text response."
            )

        if not response:
            raise ValueError(
                "The language-model provider returned an empty response."
            )

        yield response
