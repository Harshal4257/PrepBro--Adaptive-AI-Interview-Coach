from pathlib import Path

import pytest

from src.config import Settings
from src.models import Evaluation, JobAnalysis
from src.question_selector import NextQuestionSelector
from src.session import InterviewCoach
from src.utils import InputValidationError
from src.weakness_tracker import WeaknessTracker


def mock_settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_provider="mock",
        llm_model="mock",
        max_questions=3,
        initial_difficulty="Easy",
        minimum_score_threshold=6.0,
        max_query_length=1000,
        max_answer_length=1000,
        max_output_tokens=200,
    )


def test_session_is_adaptive_and_prevents_duplicate_questions(tmp_path: Path) -> None:
    coach = InterviewCoach(mock_settings(tmp_path))
    state = coach.start("Need an AI engineer with Python, RAG, and transformer experience.")
    first = coach.next_question()
    assert first is not None
    first_attempt = coach.submit_answer("I would measure relevance and grounded answer quality.", response_seconds=4.0)
    assert first_attempt.evaluation.score == 7.0

    second = coach.next_question()
    assert second is not None
    assert second.question != first.question
    assert second.topic in coach.tracker.stats()

    summary = coach.summary()
    assert summary["questions_answered"] == 1
    assert "LLM Fundamentals" in summary["topic_scores"]
    assert state.analysis.priority_topics


def test_empty_answers_are_rejected(tmp_path: Path) -> None:
    coach = InterviewCoach(mock_settings(tmp_path))
    coach.start("Need an ML engineer.")
    coach.next_question()
    with pytest.raises(InputValidationError, match="cannot be empty"):
        coach.submit_answer("   ")


def test_low_scoring_required_topic_gets_next_priority() -> None:
    analysis = JobAnalysis(topics=["LLM Evaluation", "Python"], priority_topics=["LLM Evaluation", "Python"])
    tracker = WeaknessTracker(analysis.priority_topics)
    tracker.record(
        "LLM Evaluation",
        Evaluation(score=4.0, strengths=[], missing_points=["grounding"], incorrect_points=[], feedback="Review evaluation.", weak_topics=[]),
    )
    tracker.record(
        "Python",
        Evaluation(score=9.0, strengths=["clear"], missing_points=[], incorrect_points=[], feedback="Strong.", weak_topics=[]),
    )
    assert NextQuestionSelector().select_topic(analysis, tracker) == "LLM Evaluation"


def test_high_scoring_topic_is_deprioritized_after_a_weak_score_elsewhere() -> None:
    analysis = JobAnalysis(topics=["Transformers", "RAG"], priority_topics=["Transformers", "RAG"])
    tracker = WeaknessTracker(analysis.priority_topics)
    tracker.record(
        "Transformers",
        Evaluation(score=9.0, strengths=["precise"], missing_points=[], incorrect_points=[], feedback="Strong.", weak_topics=[]),
    )
    tracker.record(
        "RAG",
        Evaluation(score=3.0, strengths=[], missing_points=["retrieval evaluation"], incorrect_points=[], feedback="Review retrieval.", weak_topics=[]),
    )
    assert NextQuestionSelector().select_topic(analysis, tracker) == "RAG"
