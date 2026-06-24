"""Decision Ledger — Streamlit Dashboard.

Reads from the FastAPI backend. Set API_BASE_URL in your .env or environment.
"""

import os
from datetime import date, datetime
from typing import Any

import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from charts import (
    accuracy_bar,
    accuracy_rate_line,
    compliance_heatmap,
    horizon_box,
    reversal_waterfall,
    status_donut,
    velocity_timeline,
)

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

st.set_page_config(
    page_title="Decision Ledger",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── API helpers ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def fetch(path: str) -> Any:
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        st.error(f"API error on {path}: {e}")
        return None


def post(path: str, payload: dict) -> tuple[bool, Any]:
    try:
        r = httpx.post(
            f"{API_BASE}{path}",
            json=payload,
            headers={"X-API-Key": API_KEY},
            timeout=10,
        )
        r.raise_for_status()
        return True, r.json()
    except httpx.HTTPStatusError as e:
        return False, e.response.json()
    except httpx.HTTPError as e:
        return False, str(e)


def patch(path: str, payload: dict) -> tuple[bool, Any]:
    try:
        r = httpx.patch(
            f"{API_BASE}{path}",
            json=payload,
            headers={"X-API-Key": API_KEY},
            timeout=10,
        )
        r.raise_for_status()
        return True, r.json()
    except httpx.HTTPStatusError as e:
        return False, e.response.json()
    except httpx.HTTPError as e:
        return False, str(e)


# ── Sidebar navigation ────────────────────────────────────────────────────────

st.sidebar.title("📋 Decision Ledger")
st.sidebar.caption("Nexura Commerce · Strategy & Product")

page = st.sidebar.radio(
    "Navigate",
    ["Portfolio Overview", "Decision Explorer", "Analytics", "New Decision"],
    index=0,
)

CATEGORIES = ["pricing", "product", "hiring", "market_entry", "operational"]
STATUSES = ["active", "succeeded", "failed", "reversed", "superseded"]
STATUS_COLORS = {
    "active": "🔵",
    "succeeded": "🟢",
    "failed": "🔴",
    "reversed": "🟠",
    "superseded": "🟣",
}


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Portfolio Overview
# ══════════════════════════════════════════════════════════════════════════════

if page == "Portfolio Overview":
    st.title("Portfolio Overview")

    summary_data = fetch("/analytics/summary")
    if not summary_data:
        st.stop()

    summary = summary_data if isinstance(summary_data, dict) else {}

    # ── KPI cards ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Decisions", summary.get("total_decisions", "—"))
    col2.metric("Active", summary.get("active_decisions", "—"))
    col3.metric(
        "Success Rate",
        f"{summary.get('overall_accuracy_pct', 0):.1f}%"
        if summary.get("overall_accuracy_pct") is not None
        else "—",
    )
    col4.metric("Succeeded", summary.get("succeeded_decisions", "—"))
    col5.metric("Failed", summary.get("failed_decisions", "—"))
    col6.metric(
        "Overdue Reviews",
        summary.get("overdue_decisions", "—"),
        delta_color="inverse",
    )

    st.divider()

    # ── Charts row 1 ──────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    summary_df = pd.DataFrame([summary])

    with c1:
        st.plotly_chart(status_donut(summary_df), use_container_width=True)

    accuracy_data = fetch("/analytics/accuracy")
    if accuracy_data:
        acc_df = pd.DataFrame(accuracy_data)
        with c2:
            st.plotly_chart(accuracy_rate_line(acc_df), use_container_width=True)

    # ── Charts row 2 ──────────────────────────────────────────────────────────
    c3, c4 = st.columns(2)

    compliance_data = fetch("/analytics/compliance")
    if compliance_data:
        comp_df = pd.DataFrame(compliance_data)
        with c3:
            st.plotly_chart(compliance_heatmap(comp_df), use_container_width=True)

    reversal_data = fetch("/analytics/reversal-rate")
    if reversal_data:
        rev_df = pd.DataFrame(reversal_data)
        with c4:
            st.plotly_chart(reversal_waterfall(rev_df), use_container_width=True)

    # ── Overdue alert ─────────────────────────────────────────────────────────
    overdue = summary.get("overdue_decisions", 0)
    if overdue and overdue > 0:
        st.warning(
            f"⚠️ **{overdue} decision(s)** are past their review date with no status update. "
            "Use the Decision Explorer to log outcomes.",
            icon="⚠️",
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Decision Explorer
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Decision Explorer":
    st.title("Decision Explorer")

    # ── Filter bar ────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns(3)
    sel_cat = fc1.selectbox("Category", ["All"] + CATEGORIES, key="exp_cat")
    sel_status = fc2.selectbox("Status", ["All"] + STATUSES, key="exp_status")
    sel_owner = fc3.text_input("Owner (exact)", key="exp_owner")

    params = []
    if sel_cat != "All":
        params.append(f"category={sel_cat}")
    if sel_status != "All":
        params.append(f"status={sel_status}")
    if sel_owner:
        params.append(f"owner={sel_owner}")
    params.append("limit=200")

    query = "&".join(params)
    decisions = fetch(f"/decisions?{query}")

    if not decisions:
        st.info("No decisions match the current filters.")
        st.stop()

    df = pd.DataFrame(decisions)
    df["decided_at"] = pd.to_datetime(df["decided_at"]).dt.strftime("%Y-%m-%d")
    df["review_date"] = pd.to_datetime(df["review_date"]).dt.strftime("%Y-%m-%d")

    # ── Table ─────────────────────────────────────────────────────────────────
    display_cols = ["id", "title", "category", "status", "review_date", "owner", "team", "decided_at"]
    existing_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[existing_cols].rename(
            columns={
                "id": "ID",
                "title": "Title",
                "category": "Category",
                "status": "Status",
                "review_date": "Review Date",
                "owner": "Owner",
                "team": "Team",
                "decided_at": "Decided",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(f"{len(df)} decision(s) shown")

    # ── Detail panel ──────────────────────────────────────────────────────────
    st.subheader("Decision Detail")
    decision_ids = [d["id"] for d in decisions]
    selected_id = st.selectbox("Select decision ID", decision_ids, key="detail_id")

    if selected_id:
        detail = fetch(f"/decisions/{selected_id}")
        if detail:
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.markdown(f"### {detail['title']}")
                st.markdown(
                    f"**Category:** {detail['category']}  |  "
                    f"**Status:** {STATUS_COLORS.get(detail['status'], '')} {detail['status']}  |  "
                    f"**Owner:** {detail.get('owner', '—')}  |  "
                    f"**Team:** {detail.get('team', '—')}"
                )
                with st.expander("Context", expanded=True):
                    st.write(detail["context"])
                with st.expander("Options Considered"):
                    for opt in detail.get("options_considered", []):
                        st.markdown(f"**{opt.get('option', '')}**")
                        if opt.get("pros"):
                            st.markdown("✅ " + " · ".join(opt["pros"]))
                        if opt.get("cons"):
                            st.markdown("❌ " + " · ".join(opt["cons"]))
                        st.divider()
                with st.expander("Decision & Rationale"):
                    st.markdown(f"**Decision made:** {detail['decision_made']}")
                    st.markdown(f"**Rationale:** {detail['rationale']}")
                with st.expander("Expected vs Actual Outcome"):
                    st.markdown(f"**Expected:** {detail['expected_outcome']}")
                    st.markdown(
                        f"**Actual:** {detail.get('actual_outcome') or '*(not yet recorded)*'}"
                    )
                if detail.get("data_consulted"):
                    with st.expander("Data Consulted"):
                        for d in detail["data_consulted"]:
                            st.markdown(f"- {d}")

            with col_r:
                st.markdown(f"**Review date:** {detail['review_date']}")
                reviews = detail.get("reviews", [])
                st.markdown(f"**Reviews logged:** {len(reviews)}")

                if reviews:
                    for rev in reviews:
                        with st.container(border=True):
                            rating = rev.get("outcome_rating")
                            stars = "⭐" * rating if rating else "—"
                            st.markdown(
                                f"**{rev.get('reviewer', 'Anonymous')}** {stars}"
                            )
                            st.write(rev["actual_outcome"])
                            if rev.get("lessons_learned"):
                                st.caption(f"💡 {rev['lessons_learned']}")

                # ── Status update form ─────────────────────────────────────
                if API_KEY:
                    st.subheader("Update Status")
                    with st.form(f"status_form_{selected_id}"):
                        new_status = st.selectbox("New status", STATUSES)
                        actual_outcome = st.text_area("Actual outcome (optional)")
                        submitted = st.form_submit_button("Update")
                        if submitted:
                            ok, resp = patch(
                                f"/decisions/{selected_id}/status",
                                {
                                    "status": new_status,
                                    "actual_outcome": actual_outcome or None,
                                },
                            )
                            if ok:
                                st.success("Status updated.")
                                st.cache_data.clear()
                            else:
                                st.error(f"Error: {resp}")

                    # ── Add review form ────────────────────────────────────
                    st.subheader("Add Review")
                    with st.form(f"review_form_{selected_id}"):
                        reviewer = st.text_input("Reviewer name")
                        actual_outcome_rev = st.text_area("Outcome description *", key="rev_ao")
                        rating = st.slider("Outcome rating (1–5)", 1, 5, 3)
                        lessons = st.text_area("Lessons learned")
                        rev_submitted = st.form_submit_button("Submit Review")
                        if rev_submitted:
                            if not actual_outcome_rev.strip():
                                st.warning("Outcome description is required.")
                            else:
                                ok, resp = post(
                                    f"/decisions/{selected_id}/reviews",
                                    {
                                        "reviewer": reviewer or None,
                                        "actual_outcome": actual_outcome_rev,
                                        "outcome_rating": rating,
                                        "lessons_learned": lessons or None,
                                    },
                                )
                                if ok:
                                    st.success("Review added.")
                                    st.cache_data.clear()
                                else:
                                    st.error(f"Error: {resp}")
                else:
                    st.info("Set API_KEY in your .env to enable write operations.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Analytics
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Analytics":
    st.title("Analytics")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Accuracy", "Velocity & Horizon", "Compliance", "Reversal Rate"]
    )

    with tab1:
        st.subheader("Decision Accuracy by Category")
        data = fetch("/analytics/accuracy")
        if data:
            df = pd.DataFrame(data)
            st.plotly_chart(accuracy_bar(df), use_container_width=True)
            st.plotly_chart(accuracy_rate_line(df), use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Decision Velocity Over Time")
        data = fetch("/analytics/velocity")
        if data:
            df = pd.DataFrame(data)
            st.plotly_chart(velocity_timeline(df), use_container_width=True)
            st.plotly_chart(horizon_box(df), use_container_width=True)

    with tab3:
        st.subheader("Review Compliance by Category")
        data = fetch("/analytics/compliance")
        if data:
            df = pd.DataFrame(data)
            st.plotly_chart(compliance_heatmap(df), use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("Reversal & Failure Rates by Category")
        data = fetch("/analytics/reversal-rate")
        if data:
            df = pd.DataFrame(data)
            st.plotly_chart(reversal_waterfall(df), use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: New Decision
# ══════════════════════════════════════════════════════════════════════════════

elif page == "New Decision":
    st.title("Log a New Decision")

    if not API_KEY:
        st.warning("Set API_KEY in your .env to enable decision creation.")
        st.stop()

    with st.form("new_decision_form", clear_on_submit=True):
        st.subheader("Core Details")
        title = st.text_input("Decision title *", max_chars=200)
        category = st.selectbox("Category *", CATEGORIES)
        context = st.text_area("Context narrative *", height=150, max_chars=5000)

        st.subheader("Options Considered")
        st.caption("Add 1–3 options. Fill in what you evaluated.")
        options = []
        for i in range(1, 4):
            with st.expander(f"Option {i}", expanded=(i == 1)):
                opt_text = st.text_input(f"Option {i} description", key=f"opt_{i}")
                pros = st.text_input(
                    f"Pros (comma-separated)", key=f"pros_{i}"
                )
                cons = st.text_input(
                    f"Cons (comma-separated)", key=f"cons_{i}"
                )
                if opt_text:
                    options.append(
                        {
                            "option": opt_text,
                            "pros": [p.strip() for p in pros.split(",") if p.strip()],
                            "cons": [c.strip() for c in cons.split(",") if c.strip()],
                        }
                    )

        st.subheader("The Decision")
        decision_made = st.text_area("What was decided? *", height=100)
        rationale = st.text_area("Rationale *", height=100)
        expected_outcome = st.text_area(
            "Expected outcome (measurable) *", height=100, max_chars=2000
        )

        st.subheader("Data & Metadata")
        data_consulted_raw = st.text_area(
            "Data sources consulted (one per line)"
        )
        col1, col2 = st.columns(2)
        team = col1.text_input("Team", max_chars=100)
        owner = col2.text_input("Owner", max_chars=100)
        review_date = st.date_input(
            "Review date *",
            min_value=date.today(),
            value=date.today().replace(month=date.today().month % 12 + 1),
        )

        submitted = st.form_submit_button("📋 Log Decision", type="primary")

        if submitted:
            errors = []
            if not title.strip():
                errors.append("Title is required.")
            if not context.strip() or len(context.strip()) < 10:
                errors.append("Context must be at least 10 characters.")
            if not options:
                errors.append("At least one option is required.")
            if not decision_made.strip():
                errors.append("Decision made is required.")
            if not rationale.strip() or len(rationale.strip()) < 10:
                errors.append("Rationale must be at least 10 characters.")
            if not expected_outcome.strip() or len(expected_outcome.strip()) < 10:
                errors.append("Expected outcome must be at least 10 characters.")
            if review_date <= date.today():
                errors.append("Review date must be in the future.")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                data_consulted = [
                    line.strip()
                    for line in data_consulted_raw.splitlines()
                    if line.strip()
                ]
                payload = {
                    "title": title.strip(),
                    "category": category,
                    "context": context.strip(),
                    "options_considered": options,
                    "data_consulted": data_consulted,
                    "decision_made": decision_made.strip(),
                    "rationale": rationale.strip(),
                    "expected_outcome": expected_outcome.strip(),
                    "review_date": review_date.isoformat(),
                    "team": team.strip() or None,
                    "owner": owner.strip() or None,
                }
                ok, resp = post("/decisions", payload)
                if ok:
                    st.success(f"✅ Decision logged with ID {resp['id']}")
                    st.cache_data.clear()
                else:
                    st.error(f"Failed to create decision: {resp}")
