"""Adaptive selection of the next topic and difficulty."""

from __future__ import annotations

from src.models import JobAnalysis
from src.weakness_tracker import WeaknessTracker


class NextQuestionSelector:
    def select_topic(self, analysis: JobAnalysis, tracker: WeaknessTracker) -> str:
        # Include model-identified weak subtopics as targeted follow-ups, while the
        # priority/required topics still contribute their larger importance weights.
        candidates = list(dict.fromkeys([*analysis.priority_topics, *analysis.topics, *tracker.stats().keys()]))
        if not candidates:
            candidates = ["General AI/ML Fundamentals"]
        for index, topic in enumerate(candidates):
            tracker.ensure_topic(topic, importance=max(1, len(candidates) - index))

        def priority(topic: str) -> float:
            stats = tracker.stats()[topic]
            # Low scores dominate selection, then job relevance and topic coverage.
            unseen_bonus = 2.0 if stats.attempts == 0 else 0.0
            return stats.weakness_level * 2.0 + stats.importance * 1.5 + unseen_bonus - stats.attempts * 0.25

        return max(candidates, key=priority)

    @staticmethod
    def select_difficulty(tracker: WeaknessTracker, minimum_score: float, fallback: str) -> str:
        attempted = [stats.average_score for stats in tracker.stats().values() if stats.average_score is not None]
        if not attempted:
            return fallback
        recent_average = sum(attempted) / len(attempted)
        if recent_average < minimum_score:
            return "Easy"
        if recent_average < 8.0:
            return "Medium"
        return "Hard"
