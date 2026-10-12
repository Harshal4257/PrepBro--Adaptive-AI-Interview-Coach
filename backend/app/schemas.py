"""Pydantic schemas for the thin HTTP layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class StartInterviewRequest(BaseModel):
    job_description: str = Field(min_length=20, max_length=12_000)
    difficulty: str = "Medium"
    num_questions: int = Field(default=10, ge=1, le=20)

    @field_validator("difficulty")
    @classmethod
    def normalize_difficulty(cls, value: str) -> str:
        normalized = value.strip().title()
        if normalized not in {"Easy", "Medium", "Hard"}:
            raise ValueError("difficulty must be Easy, Medium, or Hard")
        return normalized


class AnswerRequest(BaseModel):
    answer: str


class JobSummaryResponse(BaseModel):
    skills: list[str]
    priority_topics: list[str]
    topics: list[str]


class QuestionResponse(BaseModel):
    id: str
    text: str
    topic: str
    difficulty: str
    question_number: int


class ProgressResponse(BaseModel):
    current: int
    total: int


class EvaluationResponse(BaseModel):
    score: float
    strengths: list[str]
    missing_points: list[str]
    incorrect_points: list[str]
    feedback: str
    weak_topics: list[str]


class HistoryItemResponse(BaseModel):
    question_number: int
    question: str
    topic: str
    score: float


class StartInterviewResponse(BaseModel):
    session_id: str
    job_summary: JobSummaryResponse
    question: QuestionResponse
    progress: ProgressResponse


class AnswerResponse(BaseModel):
    evaluation: EvaluationResponse
    next_question: QuestionResponse | None
    progress: ProgressResponse
    topic_scores: dict[str, float | None]
    weak_topics: list[str]
    strong_topics: list[str]
    final_summary: "FinalSummaryResponse | None" = None


class SessionResponse(BaseModel):
    session_id: str
    status: Literal["active", "completed", "ended"]
    current_question: QuestionResponse | None
    progress: ProgressResponse
    average_score: float
    topic_scores: dict[str, float | None]
    weak_topics: list[str]
    strong_topics: list[str]
    question_history: list[HistoryItemResponse]
    job_summary: JobSummaryResponse


class FinalSummaryResponse(BaseModel):
    overall_score: float
    average_score: float
    strongest_topics: list[str]
    weakest_topics: list[str]
    topic_scores: dict[str, float | None]
    recommended_revision_areas: list[str]
    improvement_suggestions: list[str]
    questions_attempted: int
    highest_score: float | None
    lowest_score: float | None


class ResetResponse(BaseModel):
    session_id: str
    status: Literal["ended"]


class HealthResponse(BaseModel):
    status: Literal["healthy"]
    service: Literal["adaptive-ai-interview-coach"]
    configuration: Literal["loaded"]
    session_store: Literal["ready"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    service: Literal["adaptive-ai-interview-coach"]
    configuration: Literal["validated"]
