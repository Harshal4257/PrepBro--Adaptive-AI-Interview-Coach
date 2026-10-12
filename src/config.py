"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when local or deployed configuration is not usable."""


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str
    max_questions: int
    initial_difficulty: str
    minimum_score_threshold: float
    max_query_length: int
    max_answer_length: int
    max_output_tokens: int
    llm_temperature: float = 0.3
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 1
    logging_level: str = "INFO"
    app_environment: str = "development"
    allowed_origins: tuple[str, ...] = ("http://localhost:8501", "http://127.0.0.1:8501")

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        try:
            return cls(
                llm_provider=os.getenv("LLM_PROVIDER", "gemini").strip().lower(),
                llm_model=os.getenv("LLM_MODEL", "gemini-3.1-flash-lite").strip(),
                max_questions=int(os.getenv("MAX_QUESTIONS", "8")),
                initial_difficulty=os.getenv("INITIAL_DIFFICULTY", "Easy").title(),
                minimum_score_threshold=float(os.getenv("MINIMUM_SCORE_THRESHOLD", "6.0")),
                max_query_length=int(os.getenv("MAX_QUERY_LENGTH", "12000")),
                max_answer_length=int(os.getenv("MAX_ANSWER_LENGTH", "6000")),
                max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", "700")),
                llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
                llm_timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
                llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
                logging_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
                app_environment=os.getenv("APP_ENV", "development").strip().lower(),
                allowed_origins=tuple(
                    origin.strip()
                    for origin in os.getenv(
                        "ALLOWED_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501"
                    ).split(",")
                    if origin.strip()
                ),
            )
        except ValueError as exc:
            raise ConfigurationError("A numeric environment setting has an invalid value.") from exc

    def validate_runtime(self) -> None:
        """Validate local configuration without making a network/model request."""
        if self.llm_provider not in {"gemini", "mock"}:
            raise ConfigurationError("LLM_PROVIDER must be either 'gemini' or 'mock'.")
        if not self.llm_model:
            raise ConfigurationError("LLM_MODEL cannot be empty.")
        if self.initial_difficulty not in {"Easy", "Medium", "Hard"}:
            raise ConfigurationError("INITIAL_DIFFICULTY must be Easy, Medium, or Hard.")
        if not 1 <= self.max_questions <= 20:
            raise ConfigurationError("MAX_QUESTIONS must be between 1 and 20.")
        if not 0 <= self.minimum_score_threshold <= 10:
            raise ConfigurationError("MINIMUM_SCORE_THRESHOLD must be between 0 and 10.")
        if self.max_query_length < 20 or self.max_answer_length < 1:
            raise ConfigurationError("MAX_QUERY_LENGTH and MAX_ANSWER_LENGTH must be positive, safe limits.")
        if not 0 <= self.llm_temperature <= 1:
            raise ConfigurationError("LLM_TEMPERATURE must be between 0 and 1.")
        if self.max_output_tokens < 64 or self.llm_timeout_seconds < 1 or self.llm_max_retries not in {0, 1, 2}:
            raise ConfigurationError("Model output, timeout, or retry settings are outside supported limits.")
        if self.logging_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ConfigurationError("LOG_LEVEL must be DEBUG, INFO, WARNING, or ERROR.")
        if not self.allowed_origins:
            raise ConfigurationError("ALLOWED_ORIGINS must contain at least one frontend origin.")
        if self.llm_provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
            raise ConfigurationError(
                "GOOGLE_API_KEY is required when LLM_PROVIDER=gemini. "
                "Use LLM_PROVIDER=mock for an offline demo."
            )
