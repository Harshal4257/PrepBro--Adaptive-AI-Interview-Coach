"""FastAPI application exposing the existing interview-coach service."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.schemas import (
    AnswerRequest,
    AnswerResponse,
    ErrorResponse,
    HealthResponse,
    ReadinessResponse,
    ResetResponse,
    SessionResponse,
    StartInterviewRequest,
    StartInterviewResponse,
    FinalSummaryResponse,
)
from backend.app.service import APIProblem, InterviewSessionService
from src.config import ConfigurationError
from src.utils import configure_logging, reset_request_id, set_request_id


def create_app(service: InterviewSessionService | None = None) -> FastAPI:
    session_service = service or InterviewSessionService()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger = configure_logging(session_service.settings.logging_level)
        try:
            session_service.settings.validate_runtime()
        except ConfigurationError:
            logger.exception("Startup configuration validation failed", extra={"event": "startup_failed"})
            raise
        app.state.ready = True
        logger.info("Application started", extra={"event": "application_started"})
        yield
        app.state.ready = False
        logger.info("Application stopped", extra={"event": "application_stopped"})

    app = FastAPI(title="Adaptive AI Interview Coach API", version="3.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(session_service.settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.interview_service = session_service
    app.state.ready = False
    logger = logging.getLogger("interview_coach")

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = set_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            logger.info(
                "API request completed",
                extra={
                    "event": "api_request_completed",
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "status_code": locals().get("response", None).status_code if "response" in locals() else 500,
                },
            )
            reset_request_id(token)

    @app.exception_handler(APIProblem)
    async def api_problem_handler(_: Request, exc: APIProblem) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        message = exc.errors()[0].get("msg", "Invalid request.")
        return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": message}})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error", extra={"event": "api_error"})
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "The service encountered an unexpected error. Please try again."}},
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="healthy",
            service="adaptive-ai-interview-coach",
            configuration="loaded",
            session_store="ready",
        )

    @app.get("/api/ready", response_model=ReadinessResponse, responses={503: {"model": ErrorResponse}})
    def ready() -> ReadinessResponse:
        if not app.state.ready:
            raise APIProblem(503, "SERVICE_NOT_READY", "The service is still initializing.")
        return ReadinessResponse(status="ready", service="adaptive-ai-interview-coach", configuration="validated")

    @app.post("/api/interview/start", response_model=StartInterviewResponse, responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}})
    def start_interview(request: StartInterviewRequest) -> StartInterviewResponse:
        return app.state.interview_service.start(request)

    @app.post("/api/interview/{session_id}/answer", response_model=AnswerResponse, responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 502: {"model": ErrorResponse}})
    def submit_answer(session_id: str, request: AnswerRequest) -> AnswerResponse:
        return app.state.interview_service.answer(session_id, request.answer)

    @app.get("/api/interview/{session_id}", response_model=SessionResponse, responses={404: {"model": ErrorResponse}})
    def get_interview(session_id: str) -> SessionResponse:
        return app.state.interview_service.get_session(session_id)

    @app.get("/api/interview/{session_id}/summary", response_model=FinalSummaryResponse, responses={404: {"model": ErrorResponse}})
    def get_summary(session_id: str) -> FinalSummaryResponse:
        return app.state.interview_service.summary(session_id)

    @app.post("/api/interview/{session_id}/reset", response_model=ResetResponse, responses={404: {"model": ErrorResponse}})
    def reset_interview(session_id: str) -> ResetResponse:
        app.state.interview_service.reset(session_id)
        return ResetResponse(session_id=session_id, status="ended")

    return app


app = create_app()
