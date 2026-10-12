"""Interview question generation with duplicate protection."""

from src.llm import StructuredLLM
from src.models import InterviewQuestion, JobAnalysis
from src.prompts import QUESTION_PROMPT


class QuestionGenerator:
    def __init__(self, llm: StructuredLLM):
        self.llm = llm

    def generate(
        self,
        analysis: JobAnalysis,
        selected_topic: str,
        difficulty: str,
        history: list[str],
    ) -> InterviewQuestion:
        prompt = QUESTION_PROMPT.format_messages(
            topics=", ".join(analysis.topics),
            priority_topics=", ".join(analysis.priority_topics),
            selected_topic=selected_topic,
            difficulty=difficulty,
            history="\n".join(history) if history else "None",
        )
        question = self.llm.invoke_structured(prompt, InterviewQuestion)
        question.difficulty = difficulty
        question.topic = selected_topic
        if self._is_duplicate(question.question, history):
            return self._fallback_question(selected_topic, difficulty, history)
        return question

    @staticmethod
    def _is_duplicate(question: str, history: list[str]) -> bool:
        normalized = " ".join(question.lower().split()).rstrip("?!. ")
        return any(normalized == " ".join(item.lower().split()).rstrip("?!. ") for item in history)

    def _fallback_question(self, topic: str, difficulty: str, history: list[str]) -> InterviewQuestion:
        templates = [
            "In a production system, what trade-offs would you consider when applying {topic}?",
            "How would you diagnose and improve a weak result in a {topic} implementation?",
            "Design a practical approach for {topic}; what would you measure to know it works?",
        ]
        for template in templates:
            candidate = template.format(topic=topic)
            if not self._is_duplicate(candidate, history):
                return InterviewQuestion(
                    question=candidate,
                    topic=topic,
                    difficulty=difficulty,
                    expected_key_concepts=["trade-offs", "evaluation", "production constraints"],
                    rationale="Fallback question used to prevent a duplicate.",
                )
        raise RuntimeError("No non-duplicate question remains for this topic.")
