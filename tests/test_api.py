from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.service import InterviewSessionService
from src.config import Settings


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


def client(tmp_path: Path) -> TestClient:
    service = InterviewSessionService(mock_settings(tmp_path))
    return TestClient(create_app(service))


def start_session(test_client: TestClient, num_questions: int = 2) -> dict:
    response = test_client.post(
        "/api/interview/start",
        json={
            "job_description": "We need an AI engineer with Python, prompt engineering, and model evaluation skills.",
            "difficulty": "medium",
            "num_questions": num_questions,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_health() -> None:
    response = client(Path("." )).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["configuration"] == "loaded"
    assert response.headers["X-Request-ID"]


def test_readiness_validates_mock_configuration(tmp_path: Path) -> None:
    service = InterviewSessionService(mock_settings(tmp_path))
    with TestClient(create_app(service)) as test_client:
        response = test_client.get("/api/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_start_answer_and_summary(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    started = start_session(test_client, num_questions=1)
    session_id = started["session_id"]
    assert started["question"]["question_number"] == 1
    assert started["progress"] == {"current": 1, "total": 1}

    answered = test_client.post(f"/api/interview/{session_id}/answer", json={"answer": "I would use quality metrics and a representative evaluation dataset."})
    assert answered.status_code == 200
    body = answered.json()
    assert body["evaluation"]["score"] == 7.0
    assert body["next_question"] is None
    assert body["final_summary"]["questions_attempted"] == 1

    status = test_client.get(f"/api/interview/{session_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"

    summary = test_client.get(f"/api/interview/{session_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["overall_score"] == 7.0


def test_invalid_session_and_empty_answer(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    missing = test_client.get("/api/interview/not-a-session")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SESSION_NOT_FOUND"

    started = start_session(test_client)
    empty = test_client.post(f"/api/interview/{started['session_id']}/answer", json={"answer": "   "})
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "INVALID_ANSWER"

    too_long = test_client.post(f"/api/interview/{started['session_id']}/answer", json={"answer": "x" * 1001})
    assert too_long.status_code == 400
    assert too_long.json()["error"]["code"] == "INVALID_ANSWER"


def test_reset_marks_session_ended(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    started = start_session(test_client)
    session_id = started["session_id"]
    reset = test_client.post(f"/api/interview/{session_id}/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "ended"
    assert test_client.get(f"/api/interview/{session_id}").json()["status"] == "ended"


def test_completed_session_rejects_another_answer_and_sessions_are_isolated(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    first = start_session(test_client, num_questions=1)
    second = start_session(test_client, num_questions=1)
    assert first["session_id"] != second["session_id"]
    completed = test_client.post(
        f"/api/interview/{first['session_id']}/answer",
        json={"answer": "I would use a representative evaluation dataset and quality metrics."},
    )
    assert completed.status_code == 200
    repeated = test_client.post(f"/api/interview/{first['session_id']}/answer", json={"answer": "another answer"})
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "SESSION_COMPLETED"
    assert test_client.get(f"/api/interview/{second['session_id']}").json()["status"] == "active"
