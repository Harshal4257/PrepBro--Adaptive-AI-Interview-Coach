"""Reference-aware answer evaluation."""

from src.llm import StructuredLLM
from src.models import Evaluation, InterviewQuestion
from src.prompts import EVALUATION_PROMPT


class AnswerEvaluator:
    def __init__(self, llm: StructuredLLM):
        self.llm = llm

    def evaluate(self, question: InterviewQuestion, answer: str) -> Evaluation:
        prompt = EVALUATION_PROMPT.format_messages(
            question=question.question,
            expected_concepts=", ".join(question.expected_key_concepts),
            answer=answer,
        )
        return self.llm.invoke_structured(prompt, Evaluation)
