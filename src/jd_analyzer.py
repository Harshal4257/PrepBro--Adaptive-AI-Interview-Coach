"""Job-description extraction."""

from src.llm import StructuredLLM
from src.models import JobAnalysis
from src.prompts import JD_ANALYSIS_PROMPT


class JobDescriptionAnalyzer:
    def __init__(self, llm: StructuredLLM):
        self.llm = llm

    def analyze(self, job_description: str) -> JobAnalysis:
        prompt = JD_ANALYSIS_PROMPT.format_messages(job_description=job_description)
        return self.llm.invoke_structured(prompt, JobAnalysis)
