from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """
    Base interface for all language model providers.
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
        Generate an answer using the supplied prompts.
        """
        ...