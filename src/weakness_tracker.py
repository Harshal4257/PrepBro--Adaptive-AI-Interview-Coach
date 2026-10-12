"""In-memory performance history by interview topic."""

from __future__ import annotations

from src.models import Evaluation, TopicStats


class WeaknessTracker:
    def __init__(self, priority_topics: list[str]):
        self._topics: dict[str, TopicStats] = {}
        for position, topic in enumerate(priority_topics):
            self.ensure_topic(topic, importance=max(1, len(priority_topics) - position))

    def ensure_topic(self, topic: str, importance: int = 1) -> None:
        key = topic.strip()
        if not key:
            return
        if key not in self._topics:
            self._topics[key] = TopicStats(importance=importance)
        else:
            self._topics[key].importance = max(self._topics[key].importance, importance)

    def record(self, question_topic: str, evaluation: Evaluation) -> None:
        self.ensure_topic(question_topic)
        stats = self._topics[question_topic]
        stats.attempts += 1
        stats.total_score += evaluation.score
        # Newly identified weak subtopics are deliberately tracked as lower-priority
        # candidates; the next selector can introduce targeted follow-up questions.
        for topic in evaluation.weak_topics:
            self.ensure_topic(topic)
            if topic != question_topic:
                weak = self._topics[topic]
                weak.attempts += 1
                weak.total_score += min(evaluation.score, 5.0)

    def stats(self) -> dict[str, TopicStats]:
        return dict(self._topics)

    def weakest(self, limit: int = 3) -> list[tuple[str, TopicStats]]:
        return sorted(self._topics.items(), key=lambda item: (-item[1].weakness_level, item[1].average_score or 5.0))[:limit]

    def strongest(self, limit: int = 3) -> list[tuple[str, TopicStats]]:
        attempted = [(topic, stats) for topic, stats in self._topics.items() if stats.attempts]
        return sorted(attempted, key=lambda item: item[1].average_score or 0, reverse=True)[:limit]
