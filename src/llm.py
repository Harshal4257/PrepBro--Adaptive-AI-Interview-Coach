"""Small LangChain model boundary, with an offline deterministic mode for demos/tests."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from src.config import Settings
from src.models import Evaluation, InterviewQuestion, JobAnalysis
from src.utils import ModelServiceError

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(frozen=True)
class InvocationMetrics:
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class StructuredLLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        self.last_invocation = InvocationMetrics(latency_ms=0.0)
        if settings.llm_provider == "gemini":
            if not os.getenv("GOOGLE_API_KEY"):
                raise ModelServiceError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini. Create one in Google AI Studio, or use LLM_PROVIDER=mock for an offline demo.")
            self._model = ChatGoogleGenerativeAI(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.max_output_tokens,
                request_timeout=settings.llm_timeout_seconds,
                retries=settings.llm_max_retries,
            )
        elif settings.llm_provider != "mock":
            raise ModelServiceError("Unsupported LLM_PROVIDER. Supported values are: gemini, mock.")

    def invoke_structured(self, prompt: Any, schema: type[SchemaT]) -> SchemaT:
        if self.settings.llm_provider == "mock":
            self.last_invocation = InvocationMetrics(latency_ms=0.0)
            return self._mock_response(schema)
        started = time.perf_counter()
        try:
            response = self._model.with_structured_output(schema, include_raw=True).invoke(prompt)
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            if isinstance(response, dict):
                parsed = response.get("parsed")
                if parsed is None:
                    raise ModelServiceError("The model returned an invalid structured response.")
                self.last_invocation = self._metrics_from_raw(response.get("raw"), latency_ms)
                return parsed
            self.last_invocation = InvocationMetrics(latency_ms=latency_ms)
            return response
        except ModelServiceError:
            raise
        except Exception as exc:  # provider/network errors are translated at one boundary
            raise ModelServiceError(
                "The model request failed. Check the model name, API quota, network connection, and retry shortly."
            ) from exc

    @staticmethod
    def _metrics_from_raw(raw: Any, latency_ms: float) -> InvocationMetrics:
        """Capture provider-reported token counts only; never estimate them."""
        usage = getattr(raw, "usage_metadata", None)
        if usage is None and isinstance(raw, dict):
            usage = raw.get("usage_metadata") or raw.get("usage")
        if usage is None:
            usage = getattr(raw, "response_metadata", {}).get("usage_metadata") if raw is not None else None
        if not isinstance(usage, dict):
            return InvocationMetrics(latency_ms=latency_ms)
        return InvocationMetrics(
            latency_ms=latency_ms,
            input_tokens=usage.get("input_tokens") or usage.get("prompt_token_count"),
            output_tokens=usage.get("output_tokens") or usage.get("candidates_token_count"),
            total_tokens=usage.get("total_tokens") or usage.get("total_token_count"),
        )

    @staticmethod
    def _mock_response(schema: type[SchemaT]) -> SchemaT:
        if schema is JobAnalysis:
            return schema(skills=["Python", "LLMs", "Model Evaluation"], topics=["LLM Fundamentals", "Prompt Engineering", "Model Evaluation"], priority_topics=["LLM Fundamentals", "Model Evaluation"], technologies=["Python", "LangChain"], experience_expectations=["Hands-on AI/ML development"], interview_concepts=["Prompting", "Evaluation", "Reliability"])
        if schema is InterviewQuestion:
            return schema(question="How would you evaluate whether an LLM application gives useful, reliable answers?", topic="LLM Evaluation", difficulty="Medium", expected_key_concepts=["quality metrics", "grounded answers", "evaluation dataset"], rationale="Tests practical LLM evaluation.")
        if schema is Evaluation:
            return schema(score=7.0, strengths=["Provided a relevant technical explanation"], missing_points=["Add concrete evaluation metrics"], incorrect_points=[], feedback="A solid foundation. Add measurable evaluation and reliability metrics.", weak_topics=["LLM Evaluation"])
        raise ModelServiceError("Mock mode does not support this output schema.")
