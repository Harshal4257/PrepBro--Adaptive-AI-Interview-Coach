"""Polished Streamlit UI for the Adaptive AI Interview Coach."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from api_client import APIClientError, InterviewAPIClient

load_dotenv()
st.set_page_config(page_title="Adaptive AI Interview Coach", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
    :root { --ink:#17212b; --muted:#64748b; --line:#e5eaf0; --navy:#182b49; --blue:#356ae6; --mint:#eaf7f2; --paper:#ffffff; }
    .stApp { background:#f6f8fb; color:var(--ink); }
    [data-testid="stSidebar"] { background:#111f35; }
    [data-testid="stSidebar"] * { color:#edf3fb; }
    .block-container { max-width:1180px; padding-top:2.2rem; padding-bottom:3rem; }
    .hero { background:linear-gradient(115deg,#162947 0%,#244a7c 100%); color:#fff; border-radius:22px; padding:2.7rem 2.9rem; margin-bottom:1.5rem; box-shadow:0 16px 34px rgba(23,42,72,.16); }
    .hero h1 { font-size:2.3rem; letter-spacing:-.04em; margin:0 0 .55rem 0; }
    .hero p { color:#d6e4f5; font-size:1.05rem; max-width:680px; margin:0; }
    .eyebrow { font-size:.73rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:#79b8ff; margin-bottom:.65rem; }
    .question-card { background:var(--paper); border:1px solid var(--line); border-radius:18px; padding:1.75rem 1.9rem; box-shadow:0 7px 22px rgba(16,24,40,.05); margin:0 0 1.15rem 0; }
    .question-card h2 { color:#142746; font-size:1.45rem; line-height:1.35; margin:.8rem 0 0; }
    .badge { display:inline-block; border-radius:999px; padding:.28rem .7rem; margin-right:.4rem; background:#eaf0fb; color:#2d5a9e; font-size:.78rem; font-weight:650; }
    .badge-dark { background:#dff3ed; color:#167052; }
    .feedback-card { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.2rem 1.35rem; min-height:132px; }
    .feedback-card h4 { margin:0 0 .65rem 0; color:#223a61; }
    .score-card { background:#142b4a; border-radius:16px; padding:1.15rem 1.35rem; color:#fff; min-height:132px; }
    .score-card .score { font-size:2.35rem; font-weight:750; line-height:1; }
    .score-card .label { color:#c8ddf5; margin-top:.45rem; }
    .adaptive { border-left:4px solid #3f7ddd; background:#eef5ff; color:#23436e; padding:1rem 1.15rem; border-radius:0 12px 12px 0; margin:1rem 0; }
    .role-card { border:1px solid var(--line); background:#fff; border-radius:14px; padding:1rem 1.1rem; color:#32445c; }
    .muted { color:var(--muted); }
    .stButton > button, .stFormSubmitButton > button { border-radius:10px; font-weight:650; min-height:2.65rem; border:0; background:#2d63d7; color:#fff; }
    .stButton > button:hover, .stFormSubmitButton > button:hover { background:#234fae; color:#fff; }
    div[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); padding:.8rem; border-radius:12px; }
</style>
"""


def client() -> InterviewAPIClient:
    return InterviewAPIClient()


def initialize_state() -> None:
    defaults: dict[str, Any] = {
        "session_id": None,
        "current_question": None,
        "pending_question": None,
        "progress": {"current": 0, "total": 0},
        "latest_evaluation": None,
        "topic_scores": {},
        "weak_topics": [],
        "strong_topics": [],
        "job_summary": None,
        "history": [],
        "final_summary": None,
        "api_error": None,
        "retry_answer": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_ui_state() -> None:
    for key in list(st.session_state.keys()):
        if key != "FormSubmitter:start_form-Start Interview":
            del st.session_state[key]
    initialize_state()


def score_label(score: float) -> str:
    if score >= 9:
        return "Excellent"
    if score >= 7:
        return "Good"
    if score >= 5:
        return "Needs Improvement"
    return "Weak Area"


def list_items(items: list[str], empty: str = "No items yet.") -> str:
    if not items:
        return f"<p class='muted'>{html.escape(empty)}</p>"
    return "".join(f"<li>{html.escape(item)}</li>" for item in items)


def start_interview(job_description: str, difficulty: str, num_questions: int) -> None:
    try:
        with st.status("Preparing your adaptive interview…", expanded=True) as status:
            st.write("Analyzing the target role…")
            result = client().start_interview(job_description, difficulty, num_questions)
            st.write("Selecting the first role-specific question…")
            status.update(label="Interview ready", state="complete", expanded=False)
        st.session_state.session_id = result["session_id"]
        st.session_state.current_question = result["question"]
        st.session_state.progress = result["progress"]
        st.session_state.job_summary = result["job_summary"]
        st.session_state.api_error = None
    except APIClientError as exc:
        st.session_state.api_error = str(exc)


def submit_answer(answer: str) -> None:
    try:
        with st.status("Evaluating your answer…", expanded=True) as status:
            st.write("Scoring correctness, completeness, and clarity…")
            result = client().submit_answer(st.session_state.session_id, answer)
            st.write("Updating topic performance…")
            st.write("Selecting the next adaptive focus…")
            status.update(label="Feedback ready", state="complete", expanded=False)
        st.session_state.latest_evaluation = result["evaluation"]
        st.session_state.pending_question = result["next_question"]
        st.session_state.progress = result["progress"]
        st.session_state.topic_scores = result["topic_scores"]
        st.session_state.weak_topics = result["weak_topics"]
        st.session_state.strong_topics = result["strong_topics"]
        st.session_state.history.append({
            "question": st.session_state.current_question["text"],
            "topic": st.session_state.current_question["topic"],
            "score": result["evaluation"]["score"],
        })
        st.session_state.final_summary = result.get("final_summary")
        st.session_state.api_error = None
        st.session_state.retry_answer = None
    except APIClientError as exc:
        st.session_state.api_error = str(exc)
        st.session_state.retry_answer = answer


def render_landing() -> None:
    st.markdown("""<section class='hero'><div class='eyebrow'>AI-powered practice</div><h1>Adaptive AI Interview Coach</h1><p>Practice role-specific technical interviews, receive AI-powered feedback, and automatically focus on your weakest topics.</p></section>""", unsafe_allow_html=True)
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        st.subheader("Build your interview plan")
        with st.form("start_form"):
            job_description = st.text_area(
                "Job Description",
                height=260,
                placeholder="Paste the target role, responsibilities, required skills, and technologies…",
            )
            difficulty = st.radio("Difficulty", ["Easy", "Medium", "Hard"], horizontal=True, index=1)
            num_questions = st.select_slider("Number of Questions", options=[5, 10, 15], value=10)
            submitted = st.form_submit_button("Start Interview", use_container_width=True)
        if submitted:
            if len(job_description.strip()) < 20:
                st.warning("Please add a more detailed job description (at least 20 characters).")
            else:
                start_interview(job_description, difficulty, num_questions)
                if st.session_state.session_id:
                    st.rerun()
    with right:
        st.markdown("### How it works")
        st.markdown("Questions adapt dynamically based on your answers, scores, and weak topics.")
        st.markdown("<div class='role-card'><b>01 — Role analysis</b><br>Skills and priority topics are extracted from the job description.</div>", unsafe_allow_html=True)
        st.markdown("<div class='role-card'><b>02 — Guided practice</b><br>Answer one focused question at a time.</div>", unsafe_allow_html=True)
        st.markdown("<div class='role-card'><b>03 — Adaptive focus</b><br>Lower-scoring areas receive more practice.</div>", unsafe_allow_html=True)
        st.markdown("### Great for")
        for role in ["AI Engineer", "ML Engineer", "Generative AI Engineer"]:
            st.markdown(f"- {role}")


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## Interview progress")
        progress = st.session_state.progress
        total = progress.get("total", 0)
        current = progress.get("current", 0)
        st.markdown(f"**Question {current} / {total}**")
        st.progress(min(current / total, 1.0) if total else 0.0)
        scores = [entry["score"] for entry in st.session_state.history]
        average = sum(scores) / len(scores) if scores else 0.0
        st.metric("Average score", f"{average:.1f} / 10" if scores else "—")
        st.markdown("### Weak topics")
        st.markdown("\n".join(f"- {topic}" for topic in st.session_state.weak_topics) or "No weak areas identified yet.")
        st.markdown("### Strong topics")
        st.markdown("\n".join(f"- {topic}" for topic in st.session_state.strong_topics) or "Build evidence through answers.")
        st.markdown("### Interview settings")
        question = st.session_state.current_question
        st.caption(f"Difficulty: {question['difficulty'] if question else '—'}")
        st.caption(f"Questions: {total}")
        if st.button("End Interview", use_container_width=True):
            try:
                client().reset_session(st.session_state.session_id)
                st.session_state.final_summary = client().get_summary(st.session_state.session_id)
                st.rerun()
            except APIClientError as exc:
                st.error(str(exc))
        if st.button("Restart Interview", use_container_width=True):
            reset_ui_state()
            st.rerun()


def render_topic_performance() -> None:
    if not st.session_state.topic_scores:
        return
    st.markdown("### Topic performance")
    for topic, score in st.session_state.topic_scores.items():
        if score is None:
            continue
        left, right = st.columns([4, 1])
        with left:
            st.caption(topic)
            st.progress(max(0.0, min(float(score) / 10, 1.0)))
        with right:
            st.caption(f"{float(score):.1f} / 10")


def render_feedback() -> None:
    result = st.session_state.latest_evaluation
    if not result:
        return
    st.markdown("## Your feedback")
    score_column, strengths_column, missing_column = st.columns([1, 1.5, 1.5], gap="medium")
    with score_column:
        st.markdown(f"<div class='score-card'><div class='score'>{result['score']:.1f}</div><div>/ 10</div><div class='label'>{score_label(result['score'])}</div></div>", unsafe_allow_html=True)
        st.progress(float(result["score"]) / 10)
    with strengths_column:
        st.markdown(f"<div class='feedback-card'><h4>What you did well</h4><ul>{list_items(result['strengths'])}</ul></div>", unsafe_allow_html=True)
    with missing_column:
        st.markdown(f"<div class='feedback-card'><h4>Missing concepts</h4><ul>{list_items(result['missing_points'])}</ul></div>", unsafe_allow_html=True)
    if result["incorrect_points"]:
        st.markdown(f"<div class='feedback-card'><h4>Incorrect or unclear points</h4><ul>{list_items(result['incorrect_points'])}</ul></div>", unsafe_allow_html=True)
    st.markdown("### Coach feedback")
    st.info(result["feedback"])
    if result["weak_topics"]:
        st.markdown("**Weak topic detected:** " + " · ".join(result["weak_topics"]))
    next_question = st.session_state.pending_question
    if next_question:
        st.markdown(f"<div class='adaptive'><b>Adaptive focus</b><br>Your latest score and weak-topic signal will steer the next question toward <b>{html.escape(next_question['topic'])}</b>.</div>", unsafe_allow_html=True)
        if st.button("Continue to Next Question", type="primary"):
            st.session_state.current_question = next_question
            st.session_state.pending_question = None
            st.session_state.latest_evaluation = None
            st.rerun()


def render_final_report() -> None:
    summary = st.session_state.final_summary
    st.markdown("<section class='hero'><div class='eyebrow'>Interview complete</div><h1>Your practice report</h1><p>A concise view of where you performed well and what to practise next.</p></section>", unsafe_allow_html=True)
    score, answered, high, low = st.columns(4)
    score.metric("Overall score", f"{summary['overall_score']:.1f} / 10")
    answered.metric("Questions answered", summary["questions_attempted"])
    high.metric("Highest score", f"{summary['highest_score']:.1f}" if summary["highest_score"] is not None else "—")
    low.metric("Lowest score", f"{summary['lowest_score']:.1f}" if summary["lowest_score"] is not None else "—")
    left, right = st.columns(2)
    with left:
        st.markdown("### Strongest topics")
        st.markdown("\n".join(f"- {item}" for item in summary["strongest_topics"]) or "Not enough evidence.")
    with right:
        st.markdown("### Weakest topics")
        st.markdown("\n".join(f"- {item}" for item in summary["weakest_topics"]) or "Not enough evidence.")
    render_topic_performance()
    st.markdown("### Recommended revision")
    for index, item in enumerate(summary["improvement_suggestions"], start=1):
        st.markdown(f"{index}. {item}")
    if st.button("Start New Interview", type="primary"):
        reset_ui_state()
        st.rerun()


def render_interview() -> None:
    render_sidebar()
    if st.session_state.final_summary:
        render_final_report()
        return
    current = st.session_state.current_question
    if not current:
        st.error("No active question is available. Please restart the interview.")
        return
    summary = st.session_state.job_summary or {}
    with st.expander("Target Role Analysis", expanded=False):
        st.markdown("**Skills:** " + (", ".join(summary.get("skills", [])) or "Not available"))
        st.markdown("**Priority topics:** " + (", ".join(summary.get("priority_topics", [])) or "Not available"))
        st.markdown("**Topics:** " + (", ".join(summary.get("topics", [])) or "Not available"))
    st.markdown(f"<div class='question-card'><div class='eyebrow'>Question {current['question_number']} of {st.session_state.progress['total']}</div><span class='badge'>{html.escape(current['topic'])}</span><span class='badge badge-dark'>{html.escape(current['difficulty'])}</span><h2>{html.escape(current['text'])}</h2></div>", unsafe_allow_html=True)
    if st.session_state.latest_evaluation:
        render_feedback()
    else:
        st.markdown("### Your answer")
        with st.form(f"answer_{current['id']}"):
            answer = st.text_area("Type your answer as if you were speaking to an interviewer…", height=220, label_visibility="collapsed", placeholder="Type your answer as if you were speaking to an interviewer…")
            submitted = st.form_submit_button("Submit Answer", type="primary", use_container_width=True)
        if submitted:
            if not answer.strip():
                st.warning("Please enter a valid answer before continuing.")
            else:
                submit_answer(answer)
                st.rerun()
        if st.session_state.retry_answer:
            if st.button("Retry last submission"):
                submit_answer(st.session_state.retry_answer)
                st.rerun()
    render_topic_performance()
    with st.expander("Previous Questions", expanded=False):
        if not st.session_state.history:
            st.caption("Your answered questions will appear here.")
        for index, item in enumerate(st.session_state.history, start=1):
            st.markdown(f"**{index}. {item['question']}**  \n{item['topic']} · **{item['score']:.1f}/10**")


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    initialize_state()
    if st.session_state.api_error:
        st.error(st.session_state.api_error)
    if st.session_state.session_id:
        render_interview()
    else:
        render_landing()


if __name__ == "__main__":
    main()
