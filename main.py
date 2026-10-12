"""Terminal entry point for the Adaptive AI Interview Coach."""

from __future__ import annotations

import time

from src.config import ConfigurationError, Settings
from src.session import InterviewCoach
from src.utils import InputValidationError, ModelServiceError, configure_logging


def read_multiline(label: str, sentinel: str = "END") -> str:
    print(f"\n{label} (finish with a line containing {sentinel}):")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == sentinel:
            return "\n".join(lines)
        lines.append(line)


def print_evaluation(attempt) -> None:
    result = attempt.evaluation
    print(f"\nScore: {result.score:.1f}/10")
    print("Strengths:")
    for item in result.strengths or ["No specific strengths returned."]:
        print(f"- {item}")
    print("Missing:")
    for item in result.missing_points or ["No major omissions identified."]:
        print(f"- {item}")
    if result.incorrect_points:
        print("Incorrect points:")
        for item in result.incorrect_points:
            print(f"- {item}")
    print(f"Feedback: {result.feedback}")


def print_summary(summary: dict[str, object]) -> None:
    print("\n=== Interview Summary ===")
    print(f"Questions answered: {summary['questions_answered']}")
    print(f"Average score: {summary['average_score']}/10")
    print("Strongest topics:", ", ".join(summary["strongest_topics"]) or "Not enough evidence")
    print("Weakest topics:", ", ".join(summary["weakest_topics"]) or "Not enough evidence")
    print("Recommended revision topics:", ", ".join(summary["recommended_revision_topics"]) or "Not enough evidence")


def main() -> None:
    try:
        settings = Settings.from_env()
        logger = configure_logging(settings.logging_level)
        coach = InterviewCoach(settings, logger)
        print("=== Adaptive AI Interview Coach ===")
        job_description = read_multiline("Paste the job description")
        state = coach.start(job_description)
        print("\nExtracted priority topics:", ", ".join(state.analysis.priority_topics or state.analysis.topics))

        while (question := coach.next_question()) is not None:
            print(f"\nQuestion {len(state.attempts) + 1}/{state.max_questions} | {question.topic} | {question.difficulty}")
            print(question.question)
            started = time.perf_counter()
            answer = read_multiline("Your answer (or type /quit then END to finish)")
            if answer.strip().lower() == "/quit":
                coach.end()
                break
            attempt = coach.submit_answer(answer, response_seconds=time.perf_counter() - started)
            print_evaluation(attempt)

        print_summary(coach.summary())
    except (ConfigurationError, InputValidationError, ModelServiceError, RuntimeError) as exc:
        print(f"\nUnable to continue: {exc}")


if __name__ == "__main__":
    main()
