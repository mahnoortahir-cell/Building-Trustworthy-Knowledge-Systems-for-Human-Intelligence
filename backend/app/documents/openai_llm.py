import os
from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from app.documents.llm_provider import BaseLLMProvider


class OpenAILLMProvider(BaseLLMProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not resolved_api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not configured"
            )

        self._model_name = (
            model_name
            or os.getenv("OPENAI_LLM_MODEL")
            or "gpt-5-mini"
        )

        self.client = OpenAI(api_key=resolved_api_key)

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        response = self.client.responses.create(
            model=self.model_name,
            instructions=system_prompt,
            input=user_prompt,
        )

        output_text = response.output_text

        if not output_text or not output_text.strip():
            raise RuntimeError(
                "OpenAI returned an empty response"
            )

        return output_text.strip()

    def stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> Iterator[str]:
        """
        Stream text deltas from the OpenAI Responses API.

        Empty provider events are ignored. An exception is raised if the
        provider finishes without emitting usable text.
        """

        emitted_text = False

        with self.client.responses.stream(
            model=self.model_name,
            instructions=system_prompt,
            input=user_prompt,
        ) as stream:
            for event in stream:
                event_type = getattr(event, "type", None)

                if event_type != "response.output_text.delta":
                    continue

                delta = self._extract_text_delta(event)

                if not delta:
                    continue

                emitted_text = True
                yield delta

            # Ensure provider-side errors are surfaced after stream completion.
            stream.get_final_response()

        if not emitted_text:
            raise RuntimeError(
                "OpenAI returned an empty streamed response"
            )

    @staticmethod
    def _extract_text_delta(
        event: Any,
    ) -> str:
        delta = getattr(event, "delta", None)

        if isinstance(delta, str):
            return delta

        return ""
