# Performance notes

The application measures wall-clock latency with `time.perf_counter()` for JD analysis, question generation, answer evaluation, and the total answer-submission API operation. Values are retained per in-memory session and emitted in structured application logs.

Provider token counts are recorded only when the LangChain provider response exposes them. The project does not estimate tokens or monetary cost.

## How to collect a real demo measurement

1. Run one short Gemini interview (two or three questions).
2. Keep `LOG_LEVEL=INFO`.
3. Save the JSON log entries for `jd_analyzed`, `question_generated`, `answer_evaluated`, and `answer_submission_completed`.
4. Record the reported `latency_ms` values below, including the model and date.

| Environment | Model | JD analysis | Question generation | Evaluation | Total answer submission |
| --- | --- | ---: | ---: | ---: | ---: |
| Populate after one real demo |  |  |  |  |  |

Mock-mode latency is useful for API regression testing but is not an LLM performance benchmark.

## Recorded local smoke result

On 2026-10-10, the offline mock flow completed a one-question API session on this development machine in 38 ms for the start request and 9 ms for the answer request. These are HTTP/application measurements only and explicitly exclude real model latency.
