"""Session registry that delegates all interview behavior to Phase 1."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
from threading import RLock
from uuid import uuid4

from src.config import Settings
from src.models import Attempt, InterviewQuestion
from src.session import InterviewCoach
from src.utils import InputValidationError, ModelServiceError

from backend.app.schemas import (
    AnswerResponse,
    EvaluationResponse,
    FinalSummaryResponse,
    HistoryItemResponse,
    JobSummaryResponse,
    ProgressResponse,
    QuestionResponse,
    SessionResponse,
    StartInterviewRequest,
    StartInterviewResponse,
)


class APIProblem(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class ManagedSession:
    coach: InterviewCoach
    lock: RLock = field(default_factory=RLock)


class InterviewSessionService:
    """In-memory, multi-session facade around one Phase 1 coach per interview."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.logger = logging.getLogger("interview_coach")
        self._sessions: dict[str, ManagedSession] = {}
        self._registry_lock = RLock()

    def start(self, request: StartInterviewRequest) -> StartInterviewResponse:
        started = time.perf_counter()
        try:
            coach = InterviewCoach(self.settings)
            state = coach.start(request.job_description, request.difficulty, request.num_questions)
            question = coach.next_question()
        except InputValidationError as exc:
            raise APIProblem(400, "INVALID_JOB_DESCRIPTION", str(exc)) from exc
        except ModelServiceError as exc:
            raise APIProblem(502, "MODEL_FAILURE", str(exc)) from exc

        if question is None:
            raise APIProblem(500, "SESSION_START_FAILED", "The interview did not produce an initial question.")
        session_id = str(uuid4())
        with self._registry_lock:
            self._sessions[session_id] = ManagedSession(coach=coach)
        self.logger.info(
            "Interview session created",
            extra={"event": "session_created", "session_id": session_id, "latency_ms": round((time.perf_counter() - started) * 1000, 2)},
        )
        return StartInterviewResponse(
            session_id=session_id,
            job_summary=self._job_summary(coach),
            question=self._question(session_id, question, 1),
            progress=ProgressResponse(current=1, total=state.max_questions),
        )

    def answer(self, session_id: str, answer: str) -> AnswerResponse:
        started = time.perf_counter()
        managed = self._get(session_id)
        with managed.lock:
            coach = managed.coach
            if coach.state is None or coach.state.is_complete:
                raise APIProblem(409, "SESSION_COMPLETED", "This interview session has already ended.")
            try:
                attempt = coach.submit_answer(answer)
                next_question = coach.next_question()
            except InputValidationError as exc:
                raise APIProblem(400, "INVALID_ANSWER", str(exc)) from exc
            except ModelServiceError as exc:
                raise APIProblem(502, "EVALUATION_FAILURE", str(exc)) from exc

            summary = coach.summary()
            current = len(coach.state.attempts) if next_question is None else len(coach.state.attempts) + 1
            self.logger.info(
                "Answer submission completed",
                extra={
                    "event": "answer_submission_completed",
                    "session_id": session_id,
                    "topic": attempt.question.topic,
                    "score": attempt.evaluation.score,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return AnswerResponse(
                evaluation=self._evaluation(attempt),
                next_question=(self._question(session_id, next_question, current) if next_question else None),
                progress=ProgressResponse(current=current, total=coach.state.max_questions),
                topic_scores=summary["topic_scores"],
                weak_topics=summary["weakest_topics"],
                strong_topics=summary["strongest_topics"],
                final_summary=(self._final_summary(coach) if next_question is None else None),
            )

    def get_session(self, session_id: str) -> SessionResponse:
        managed = self._get(session_id)
        with managed.lock:
            coach = managed.coach
            state = coach.state
            assert state is not None
            summary = coach.summary()
            if state.ended:
                status = "ended"
            elif state.is_complete:
                status = "completed"
            else:
                status = "active"
            current_number = len(state.attempts) + 1 if coach.current_question else len(state.attempts)
            return SessionResponse(
                session_id=session_id,
                status=status,
                current_question=(self._question(session_id, coach.current_question, current_number) if coach.current_question else None),
                progress=ProgressResponse(current=current_number, total=state.max_questions),
                average_score=summary["average_score"],
                topic_scores=summary["topic_scores"],
                weak_topics=summary["weakest_topics"],
                strong_topics=summary["strongest_topics"],
                question_history=[self._history_item(index + 1, attempt) for index, attempt in enumerate(state.attempts)],
                job_summary=self._job_summary(coach),
            )

    def summary(self, session_id: str) -> FinalSummaryResponse:
        managed = self._get(session_id)
        with managed.lock:
            return self._final_summary(managed.coach)

    def reset(self, session_id: str) -> None:
        managed = self._get(session_id)
        with managed.lock:
            managed.coach.end()
        self.logger.info("Interview session ended", extra={"event": "session_ended", "session_id": session_id})

    def _get(self, session_id: str) -> ManagedSession:
        with self._registry_lock:
            managed = self._sessions.get(session_id)
        if managed is None:
            raise APIProblem(404, "SESSION_NOT_FOUND", "No interview session exists for this ID.")
        return managed

    @staticmethod
    def _job_summary(coach: InterviewCoach) -> JobSummaryResponse:
        assert coach.state is not None
        analysis = coach.state.analysis
        return JobSummaryResponse(skills=analysis.skills, priority_topics=analysis.priority_topics, topics=analysis.topics)

    @staticmethod
    def _question(session_id: str, question: InterviewQuestion, number: int) -> QuestionResponse:
        return QuestionResponse(
            id=f"{session_id}:{number}",
            text=question.question,
            topic=question.topic,
            difficulty=question.difficulty,
            question_number=number,
        )

    @staticmethod
    def _evaluation(attempt: Attempt) -> EvaluationResponse:
        result = attempt.evaluation
        return EvaluationResponse(
            score=result.score,
            strengths=result.strengths,
            missing_points=result.missing_points,
            incorrect_points=result.incorrect_points,
            feedback=result.feedback,
            weak_topics=result.weak_topics,
        )

    @staticmethod
    def _history_item(number: int, attempt: Attempt) -> HistoryItemResponse:
        return HistoryItemResponse(
            question_number=number,
            question=attempt.question.question,
            topic=attempt.question.topic,
            score=attempt.evaluation.score,
        )

    def _final_summary(self, coach: InterviewCoach) -> FinalSummaryResponse:
        summary = coach.summary()
        scores = [attempt.evaluation.score for attempt in coach.state.attempts] if coach.state else []
        recommendations = summary["recommended_revision_topics"]
        return FinalSummaryResponse(
            overall_score=summary["average_score"],
            average_score=summary["average_score"],
            strongest_topics=summary["strongest_topics"],
            weakest_topics=summary["weakest_topics"],
            topic_scores=summary["topic_scores"],
            recommended_revision_areas=recommendations,
            improvement_suggestions=[f"Review {topic} and practise one applied interview answer." for topic in recommendations],
            questions_attempted=summary["questions_answered"],
            highest_score=max(scores) if scores else None,
            lowest_score=min(scores) if scores else None,
        )
