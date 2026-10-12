"""Single HTTP boundary used by the Streamlit interface."""

from __future__ import annotations

import os
from typing import Any

import requests


class APIClientError(RuntimeError):
    pass


class InterviewAPIClient:
    def __init__(self, base_url: str | None = None):
        configured_url = base_url or os.getenv("API_BASE_URL")
        # Render exposes an internal host:port for one service to reach another.
        # This fallback keeps API traffic private without hardcoding a deployed URL.
        if not configured_url and os.getenv("BACKEND_HOSTPORT"):
            configured_url = f"http://{os.environ['BACKEND_HOSTPORT']}"
        self.base_url = (configured_url or "http://127.0.0.1:8000").rstrip("/")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def start_interview(self, job_description: str, difficulty: str, num_questions: int) -> dict[str, Any]:
        return self._request("POST", "/api/interview/start", {
            "job_description": job_description,
            "difficulty": difficulty,
            "num_questions": num_questions,
        })

    def submit_answer(self, session_id: str, answer: str) -> dict[str, Any]:
        return self._request("POST", f"/api/interview/{session_id}/answer", {"answer": answer})

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/interview/{session_id}")

    def get_summary(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/interview/{session_id}/summary")

    def reset_session(self, session_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/interview/{session_id}/reset")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = requests.request(method, f"{self.base_url}{path}", json=payload, timeout=90)
        except requests.RequestException as exc:
            raise APIClientError("Unable to reach the interview API. Confirm that FastAPI is running.") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise APIClientError("The interview API returned an unreadable response.") from exc
        if not response.ok:
            message = data.get("error", {}).get("message", "The request could not be completed.")
            raise APIClientError(message)
        return data
