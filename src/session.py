"""High-level adaptive interview session orchestration."""

from __future__ import annotations

import logging
import time

from src.config import Settings
from src.evaluator import AnswerEvaluator
from src.jd_analyzer import JobDescriptionAnalyzer
from src.llm import StructuredLLM
from src.models import Attempt, InterviewQuestion, SessionState
from src.question_generator import QuestionGenerator
from src.question_selector import NextQuestionSelector
from src.utils import InputValidationError, validate_text
from src.weakness_tracker import WeaknessTracker


class InterviewCoach:
    def __init__(self, settings: Settings, logger: logging.Logger | None = None):
        self.settings = settings
        self.logger = logger or logging.getLogger("interview_coach")
        settings.validate_runtime()
        self.llm = StructuredLLM(settings)
        self.analyzer = JobDescriptionAnalyzer(self.llm)
        self.generator = QuestionGenerator(self.llm)
        self.evaluator = AnswerEvaluator(self.llm)
        self.selector = NextQuestionSelector()
        self.state: SessionState | None = None
        self.tracker: WeaknessTracker | None = None
        self.current_question: InterviewQuestion | None = None

    def start(
        self,
        job_description: str,
        difficulty: str | None = None,
        max_questions: int | None = None,
    ) -> SessionState:
        job_description = validate_text(job_description, "Job description", self.settings.max_query_length)
        selected_difficulty = (difficulty or self.settings.initial_difficulty).title()
        if selected_difficulty not in {"Easy", "Medium", "Hard"}:
            raise InputValidationError("Difficulty must be Easy, Medium, or Hard.")
        selected_max_questions = max_questions or self.settings.max_questions
        if selected_max_questions < 1:
            raise InputValidationError("The interview must contain at least one question.")
        started = time.perf_counter()
        analysis = self.analyzer.analyze(job_description)
        if not analysis.topics:
            analysis.topics = ["General AI/ML Fundamentals"]
        self.state = SessionState(
            job_description=job_description,
            analysis=analysis,
            current_difficulty=selected_difficulty,
            max_questions=selected_max_questions,
        )
        self.tracker = WeaknessTracker(analysis.priority_topics or analysis.topics)
        self._record_operation("jd_analysis", started)
        self.logger.info(
            "Job description analyzed",
            extra={"event": "jd_analyzed", "operation": "jd_analysis", "latency_ms": self.llm.last_invocation.latency_ms},
        )
        return self.state

    def next_question(self) -> InterviewQuestion | None:
        self._require_started()
        if self.state.is_complete:
            return None
        if self.current_question is not None:
            return self.current_question
        topic = self.selector.select_topic(self.state.analysis, self.tracker)
        difficulty = self.selector.select_difficulty(
            self.tracker, self.settings.minimum_score_threshold, self.state.current_difficulty
        )
        started = time.perf_counter()
        self.current_question = self.generator.generate(
            analysis=self.state.analysis,
            selected_topic=topic,
            difficulty=difficulty,
            history=self.state.asked_questions,
        )
        self._record_operation("question_generation", started)
        self.state.current_difficulty = difficulty
        self.logger.info(
            "Question generated",
            extra={"event": "question_generated", "topic": topic, "operation": "question_generation", "latency_ms": self.llm.last_invocation.latency_ms},
        )
        return self.current_question

    def submit_answer(self, answer: str, response_seconds: float | None = None) -> Attempt:
        self._require_started()
        if self.current_question is None:
            raise InputValidationError("There is no active question to answer.")
        answer = validate_text(answer, "Answer", self.settings.max_answer_length)
        started = time.perf_counter()
        evaluation = self.evaluator.evaluate(self.current_question, answer)
        self._record_operation("answer_evaluation", started)
        latency = response_seconds if response_seconds is not None else time.perf_counter() - started
        attempt = Attempt(
            question=self.current_question,
            answer=answer,
            evaluation=evaluation,
            response_seconds=round(latency, 2),
        )
        self.state.attempts.append(attempt)
        self.tracker.record(attempt.question.topic, evaluation)
        self.logger.info(
            "Answer evaluated",
            extra={
                "event": "answer_evaluated",
                "topic": attempt.question.topic,
                "score": evaluation.score,
                "operation": "answer_evaluation",
                "latency_ms": self.llm.last_invocation.latency_ms,
                "input_tokens": self.llm.last_invocation.input_tokens,
                "output_tokens": self.llm.last_invocation.output_tokens,
                "total_tokens": self.llm.last_invocation.total_tokens,
            },
        )
        self.current_question = None
        return attempt

    def end(self) -> None:
        self._require_started()
        self.state.ended = True
        self.current_question = None

    def summary(self) -> dict[str, object]:
        self._require_started()
        scores = [attempt.evaluation.score for attempt in self.state.attempts]
        weakest = self.tracker.weakest()
        strongest = self.tracker.strongest()
        return {
            "questions_answered": len(self.state.attempts),
            "average_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "strongest_topics": [topic for topic, _ in strongest],
            "weakest_topics": [topic for topic, _ in weakest],
            "recommended_revision_topics": [topic for topic, _ in weakest],
            "topic_scores": {topic: stats.average_score for topic, stats in self.tracker.stats().items() if stats.attempts},
            "operation_metrics": {name: metric.as_dict() for name, metric in self.state.operation_metrics.items()},
        }

    def _record_operation(self, operation: str, started: float) -> None:
        assert self.state is not None
        metrics = self.llm.last_invocation
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self.state.record_operation(
            operation,
            elapsed_ms,
            metrics.input_tokens,
            metrics.output_tokens,
            metrics.total_tokens,
        )

    def _require_started(self) -> None:
        if self.state is None or self.tracker is None:
            raise RuntimeError("Call start(job_description) before using the session.")
