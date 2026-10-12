"""Structured data exchanged by coach components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class JobAnalysis(BaseModel):
    skills: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    priority_topics: list[str] = Field(default_factory=list)
    experience_expectations: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    interview_concepts: list[str] = Field(default_factory=list)


class InterviewQuestion(BaseModel):
    question: str
    topic: str
    difficulty: str
    expected_key_concepts: list[str] = Field(default_factory=list)
    rationale: str = ""


class Evaluation(BaseModel):
    score: float = Field(ge=0, le=10)
    strengths: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    incorrect_points: list[str] = Field(default_factory=list)
    feedback: str
    weak_topics: list[str] = Field(default_factory=list)


@dataclass
class TopicStats:
    attempts: int = 0
    total_score: float = 0.0
    importance: int = 1

    @property
    def average_score(self) -> float | None:
        return round(self.total_score / self.attempts, 2) if self.attempts else None

    @property
    def weakness_level(self) -> float:
        """0 is strong; 10 is most in need of practice."""
        return round(10.0 - (self.average_score if self.average_score is not None else 5.0), 2)


@dataclass
class Attempt:
    question: InterviewQuestion
    answer: str
    evaluation: Evaluation
    response_seconds: float
    asked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OperationMetric:
    count: int = 0
    total_latency_ms: float = 0.0
    last_latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    token_usage_available: bool = False

    def record(
        self,
        latency_ms: float,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        self.count += 1
        self.total_latency_ms += latency_ms
        self.last_latency_ms = latency_ms
        if any(value is not None for value in (input_tokens, output_tokens, total_tokens)):
            self.token_usage_available = True
            self.input_tokens += input_tokens or 0
            self.output_tokens += output_tokens or 0
            self.total_tokens += total_tokens or 0

    def as_dict(self) -> dict[str, float | int | bool | None]:
        return {
            "count": self.count,
            "average_latency_ms": round(self.total_latency_ms / self.count, 2) if self.count else None,
            "last_latency_ms": round(self.last_latency_ms, 2),
            "input_tokens": self.input_tokens if self.token_usage_available else None,
            "output_tokens": self.output_tokens if self.token_usage_available else None,
            "total_tokens": self.total_tokens if self.token_usage_available else None,
        }


@dataclass
class SessionState:
    job_description: str
    analysis: JobAnalysis
    current_difficulty: str
    max_questions: int
    attempts: list[Attempt] = field(default_factory=list)
    operation_metrics: dict[str, OperationMetric] = field(default_factory=dict)
    ended: bool = False

    @property
    def asked_questions(self) -> list[str]:
        return [attempt.question.question for attempt in self.attempts]

    @property
    def is_complete(self) -> bool:
        return self.ended or len(self.attempts) >= self.max_questions

    def record_operation(
        self,
        operation: str,
        latency_ms: float,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        metric = self.operation_metrics.setdefault(operation, OperationMetric())
        metric.record(latency_ms, input_tokens, output_tokens, total_tokens)
