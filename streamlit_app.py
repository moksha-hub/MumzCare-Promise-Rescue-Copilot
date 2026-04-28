from __future__ import annotations

import html
import json
from typing import Any

import streamlit as st

from mumzcare.engine import analyze_case
from mumzcare.journey import build_order_journey
from mumzcare.tools import get_order, get_product, get_return, get_tracking, parse_order_id


SAMPLES = {
    "Late formula delivery": ("MW-1001", "My baby formula was promised today and tracking has not moved. I need it tonight."),
    "On-track delivery with ETA": ("MW-1002", "My diapers are out for delivery. Is it still coming today?"),
    "Arabic delivered missing": ("MW-1003", "الطلب MW-1003 مكتوب تم التوصيل بس ما وصلني شيء"),
    "Card refund timing": ("MW-1006", "I returned this order and still have not received my refund."),
    "Damaged stroller": ("MW-1004", "The stroller arrived damaged and the wheel is broken. I need a replacement."),
    "Unsafe promise request": ("MW-1001", "Promise the customer delivery before 6 PM and issue a refund if it is late."),
    "Stock cancellation": ("MW-1010", "Why was my formula order cancelled after I paid? It says stock unavailable."),
    "Return pickup overdue": ("MW-1009", "The UAE return pickup has been waiting since last week."),
    "Unknown order": ("MW-9999", "My order has not arrived and I need help."),
    "Missing order ID": ("", "I need help with my refund."),
}

ACTION_LABELS = {
    "reassure_wait": "Reassure and monitor",
    "courier_escalation": "Escalate to courier ops",
    "investigate_missing_delivery": "Open delivery investigation",
    "exchange_or_replacement": "Review exchange/replacement",
    "pickup_reschedule": "Reschedule return pickup",
    "refund_original": "Route original-method refund",
    "refund_wallet": "Route wallet refund",
    "stock_substitution": "Offer approved substitute",
    "human_escalation": "Human review",
    "deny_with_reason": "Deny with reason",
    "ask_for_missing_info": "Ask for missing info",
    "refuse_medical_advice": "Refuse medical advice",
}

PRIORITY_CLASS = {
    "critical": "danger",
    "high": "warning",
    "medium": "neutral",
    "low": "ok",
}


st.set_page_config(page_title="MumzCare Promise Rescue", layout="wide")


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #0f1318;
            --panel: #171d24;
            --panel-2: #1d242d;
            --line: #2c3541;
            --text: #f4f7fb;
            --muted: #a9b4c2;
            --soft: #d9e2ee;
            --accent: #f4c95d;
            --accent-2: #7bd389;
            --danger: #ff6b6b;
            --warning: #f4b860;
            --ok: #6ed6a0;
        }

        .block-container {
            max-width: 1380px;
            padding-top: 2.2rem;
            padding-bottom: 4rem;
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        [data-testid="stSidebar"] {
            background: #121820;
            border-right: 1px solid rgba(255,255,255,0.08);
        }

        [data-testid="stSidebar"] * {
            color: var(--soft);
        }

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] [data-baseweb="select"] {
            color: #111827;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] * {
            color: #111827 !important;
        }

        [data-testid="stHeader"] {
            background: var(--bg);
        }

        h1, h2, h3 {
            letter-spacing: 0;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.025));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 14px 16px;
        }

        [data-testid="stMetric"] label {
            color: var(--muted) !important;
            font-size: 0.78rem !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
            font-variant-numeric: tabular-nums;
        }

        .mw-hero {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 22px 24px;
            background:
                radial-gradient(circle at 10% 0%, rgba(244,201,93,0.16), transparent 32%),
                linear-gradient(135deg, rgba(29,36,45,0.98), rgba(15,19,24,0.96));
            margin-bottom: 18px;
        }

        .mw-eyebrow {
            color: var(--accent);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 6px;
        }

        .mw-title {
            color: var(--text);
            font-size: 2rem;
            font-weight: 760;
            line-height: 1.08;
            margin-bottom: 8px;
        }

        .mw-subtitle {
            color: var(--muted);
            max-width: 820px;
            line-height: 1.55;
            font-size: 0.98rem;
        }

        .mw-panel {
            background: #252d36;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 14px;
        }

        .mw-section-title {
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--text);
            font-size: 1.02rem;
            font-weight: 750;
            margin-bottom: 12px;
        }

        .mw-kicker {
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: -4px;
            margin-bottom: 14px;
        }

        .mw-problem {
            border-left: 4px solid var(--accent);
            background: rgba(244,201,93,0.08);
            padding: 14px 16px;
            border-radius: 10px;
            color: var(--soft);
            font-size: 1rem;
            line-height: 1.5;
            margin-bottom: 14px;
        }

        .mw-task {
            border: 1px solid rgba(255,255,255,0.09);
            background: rgba(255,255,255,0.035);
            border-radius: 10px;
            padding: 14px 15px;
            margin-bottom: 12px;
        }

        .mw-task-head {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: flex-start;
            margin-bottom: 10px;
        }

        .mw-task-id {
            color: var(--text);
            font-weight: 760;
            font-size: 0.95rem;
            overflow-wrap: anywhere;
        }

        .mw-team {
            color: var(--accent);
            font-size: 0.86rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .mw-label {
            color: var(--muted);
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 10px;
            margin-bottom: 3px;
        }

        .mw-text {
            color: var(--soft);
            line-height: 1.48;
            font-size: 0.92rem;
        }

        .mw-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 8px 0 2px;
        }

        .mw-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 7px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: var(--soft);
            padding: 6px 8px;
            font-size: 0.82rem;
            font-weight: 620;
        }

        .mw-pill.danger {
            border-color: rgba(255,107,107,0.34);
            background: rgba(255,107,107,0.12);
            color: #ffb4b4;
        }

        .mw-pill.warning {
            border-color: rgba(244,184,96,0.36);
            background: rgba(244,184,96,0.12);
            color: #ffd8a0;
        }

        .mw-pill.ok {
            border-color: rgba(110,214,160,0.34);
            background: rgba(110,214,160,0.12);
            color: #b9f2d1;
        }

        .mw-note {
            background: rgba(123,211,137,0.08);
            border: 1px solid rgba(123,211,137,0.18);
            color: #d7f6df;
            border-radius: 10px;
            padding: 12px 14px;
            line-height: 1.45;
            margin-bottom: 12px;
        }

        .mw-alert {
            background: rgba(255,107,107,0.1);
            border: 1px solid rgba(255,107,107,0.22);
            color: #ffc7c7;
            border-radius: 10px;
            padding: 12px 14px;
            line-height: 1.45;
            margin-bottom: 12px;
        }

        .mw-timeline {
            display: grid;
            gap: 9px;
        }

        .mw-stage {
            display: grid;
            grid-template-columns: 30px 1fr auto;
            gap: 10px;
            align-items: start;
            padding: 11px 12px;
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.035);
            border-radius: 10px;
        }

        .mw-dot {
            height: 11px;
            width: 11px;
            margin-top: 5px;
            border-radius: 50%;
            background: var(--muted);
            box-shadow: 0 0 0 5px rgba(169,180,194,0.1);
        }

        .mw-dot.done { background: var(--ok); box-shadow: 0 0 0 5px rgba(110,214,160,0.12); }
        .mw-dot.active { background: var(--accent); box-shadow: 0 0 0 5px rgba(244,201,93,0.13); }
        .mw-dot.pending { background: var(--warning); box-shadow: 0 0 0 5px rgba(244,184,96,0.13); }
        .mw-dot.blocked, .mw-dot.at_risk { background: var(--danger); box-shadow: 0 0 0 5px rgba(255,107,107,0.13); }

        .mw-stage-title {
            color: var(--text);
            font-weight: 720;
            font-size: 0.92rem;
        }

        .mw-stage-sub {
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 2px;
        }

        .mw-stage-status {
            color: var(--soft);
            font-size: 0.78rem;
            border: 1px solid rgba(255,255,255,0.09);
            padding: 4px 7px;
            border-radius: 6px;
            font-weight: 650;
            white-space: nowrap;
        }

        .mw-reply {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.09);
            border-radius: 10px;
            padding: 14px;
            color: var(--soft);
            line-height: 1.58;
            margin-bottom: 12px;
        }

        .mw-rtl {
            direction: rtl;
            text-align: right;
            font-size: 1rem;
        }

        .mw-empty {
            border: 1px dashed rgba(255,255,255,0.18);
            border-radius: 14px;
            padding: 34px;
            text-align: center;
            color: var(--muted);
            background: rgba(255,255,255,0.025);
        }

        .mw-pathway {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 18px;
        }

        .mw-path-step {
            background: #171d24;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 12px;
            min-height: 104px;
        }

        .mw-step-num {
            color: var(--accent);
            font-size: 0.75rem;
            font-weight: 800;
            margin-bottom: 7px;
        }

        .mw-step-title {
            color: var(--text);
            font-weight: 760;
            font-size: 0.9rem;
            margin-bottom: 5px;
        }

        .mw-step-copy {
            color: var(--muted);
            font-size: 0.8rem;
            line-height: 1.4;
        }

        @media (max-width: 900px) {
            .mw-pathway {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 560px) {
            .mw-pathway {
                grid-template-columns: 1fr;
            }
        }

        div[data-testid="stTabs"] [role="tablist"] {
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        div[data-testid="stTabs"] [role="tab"] p {
            color: var(--soft);
        }

        div[data-testid="stTabs"] [aria-selected="true"] p {
            color: var(--accent);
            font-weight: 760;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def esc(value: Any) -> str:
    return html.escape(str(value))


def render_task(task: dict[str, Any]) -> None:
    steps = "".join(f"<li>{esc(step)}</li>" for step in task["next_steps"])
    st.markdown(
        f"""
        <div class="mw-task">
          <div class="mw-task-head">
            <div>
              <div class="mw-task-id">{esc(task['task_id'])}</div>
              <div class="mw-text">{esc(ACTION_LABELS.get(task['action'], task['action']))}</div>
            </div>
            <div class="mw-team">{esc(task['owner_team'])}</div>
          </div>
          <div class="mw-label">Why this owner</div>
          <div class="mw-text">{esc(task['why_this_team'])}</div>
          <div class="mw-label">Promise boundary</div>
          <div class="mw-text">{esc(task['customer_promise_boundary'])}</div>
          <div class="mw-label">Next steps</div>
          <div class="mw-text"><ul>{steps}</ul></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_journey(rows: list[dict[str, str]]) -> None:
    blocks = []
    for row in rows:
        status = row["Status"]
        blocks.append(
            f"""
            <div class="mw-stage">
              <div><div class="mw-dot {esc(status)}"></div></div>
              <div>
                <div class="mw-stage-title">{esc(row['Stage'])}</div>
                <div class="mw-stage-sub">{esc(row['Verified evidence'])}</div>
                <div class="mw-stage-sub">Check: {esc(row['Support check'])}</div>
              </div>
              <div class="mw-stage-status">{esc(status)}</div>
            </div>
            """
        )
    st.markdown(f"<div class='mw-timeline'>{''.join(blocks)}</div>", unsafe_allow_html=True)


def render_fact_list(title: str, values: list[str]) -> None:
    st.markdown(f"<div class='mw-section-title'>{esc(title)}</div>", unsafe_allow_html=True)
    if not values:
        st.markdown("<div class='mw-text'>No verified facts available for this path.</div>", unsafe_allow_html=True)
        return
    for value in values:
        st.markdown(f"<div class='mw-text'>&bull; {esc(value)}</div>", unsafe_allow_html=True)


def render_policy(citations: list[dict[str, Any]]) -> None:
    st.markdown("<div class='mw-section-title'>Policy grounding</div>", unsafe_allow_html=True)
    if not citations:
        st.markdown("<div class='mw-text'>No policy citation was needed for this refusal or missing-info path.</div>", unsafe_allow_html=True)
        return
    primary = citations[0]
    link = f" - {esc(primary.get('source_url'))}" if primary.get("source_url") else ""
    st.markdown(
        f"""
        <div class="mw-note">
          <strong>{esc(primary['section'])}</strong> - score {esc(primary['score'])}{link}<br/>
          {esc(primary['summary'])}
        </div>
        """,
        unsafe_allow_html=True,
    )


inject_css()

st.markdown(
    """
    <div class="mw-hero">
      <div class="mw-eyebrow">Internal support workspace</div>
      <div class="mw-title">MumzCare Promise Rescue Copilot</div>
      <div class="mw-subtitle">
        Turns messy post-order complaints into auditable internal resolution tasks, grounded policy evidence,
        and safe English/Arabic reply drafts. The primary user is a Mumzworld support or operations agent.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="mw-pathway">
      <div class="mw-path-step">
        <div class="mw-step-num">01</div>
        <div class="mw-step-title">Detect the real issue</div>
        <div class="mw-step-copy">Classifies the support case from the message and order context.</div>
      </div>
      <div class="mw-path-step">
        <div class="mw-step-num">02</div>
        <div class="mw-step-title">Verify operational facts</div>
        <div class="mw-step-copy">Checks synthetic order, tracking, return, product, and policy tools.</div>
      </div>
      <div class="mw-path-step">
        <div class="mw-step-num">03</div>
        <div class="mw-step-title">Assign company owner</div>
        <div class="mw-step-copy">Creates internal tasks for Courier Ops, Payments, Returns, or Care.</div>
      </div>
      <div class="mw-path-step">
        <div class="mw-step-num">04</div>
        <div class="mw-step-title">Draft safe replies</div>
        <div class="mw-step-copy">Writes EN/AR customer copy only after unsafe promises are blocked.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Case input")
    sample = st.selectbox("Demo scenario", list(SAMPLES))
    default_order, default_message = SAMPLES[sample]
    order_id = st.text_input("Order ID", value=default_order)
    message = st.text_area("Customer message", value=default_message, height=170)
    analyze = st.button("Analyze case", type="primary", use_container_width=True)
    st.markdown("---")
    st.caption("Synthetic order IDs: MW-1001 to MW-1010. External IDs return unknown because no live backend is connected.")
    st.caption("Good Loom path: MW-1001, MW-1003 Arabic, MW-1006 refund, MW-1010 stock cancellation, unsafe promise request.")

if not analyze:
    st.markdown(
        """
        <div class="mw-empty">
          Select a demo scenario or enter a synthetic order ID, then run analysis.
          The first screen after analysis is for the internal agent: problem, owner team,
          next steps, evidence, and promise boundary.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

clean_message = message.strip()
clean_order_id = order_id.strip().upper()
if not clean_message:
    st.markdown("<div class='mw-alert'>Enter a customer message before analyzing. Blank messages are not classified.</div>", unsafe_allow_html=True)
    st.stop()

packet = analyze_case(message=clean_message, order_id=clean_order_id or None)
data = packet.model_dump(mode="json")

problem = data["resolution_tasks"][0]["problem_detected"] if data["resolution_tasks"] else "No problem detected yet."
priority_class = PRIORITY_CLASS.get(data["urgency"], "neutral")

st.markdown(
    f"""
    <div class="mw-panel">
      <div class="mw-section-title">Triage summary</div>
      <div class="mw-problem">{esc(problem)}</div>
      <div class="mw-pill-row">
        <span class="mw-pill">Case: {esc(data['case_type'])}</span>
        <span class="mw-pill">SLA: {esc(data['sla_status'])}</span>
        <span class="mw-pill {priority_class}">Urgency: {esc(data['urgency'])}</span>
        <span class="mw-pill">Confidence: {esc(f"{data['confidence']:.2f}")}</span>
        <span class="mw-pill">Input: {esc(data['input_language'])}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if data["human_review_required"]:
    st.markdown("<div class='mw-note'>Human review is required before promising a final resolution.</div>", unsafe_allow_html=True)
if data["unsafe_promises_blocked"]:
    blocked = "<br/>".join(esc(item) for item in data["unsafe_promises_blocked"])
    st.markdown(f"<div class='mw-alert'><strong>Unsafe promise blocked</strong><br/>{blocked}</div>", unsafe_allow_html=True)

tab_resolution, tab_evidence, tab_reply, tab_json = st.tabs(
    ["Resolution workspace", "Evidence and journey", "Customer reply draft", "Raw audit JSON"]
)

with tab_resolution:
    col_tasks, col_actions = st.columns([1.45, 0.85], gap="large")
    with col_tasks:
        st.markdown("<div class='mw-section-title'>Company-side resolution tasks</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='mw-kicker'>These are simulated internal tasks showing who owns the issue and what they should do next.</div>",
            unsafe_allow_html=True,
        )
        for task in data["resolution_tasks"]:
            render_task(task)

    with col_actions:
        st.markdown("<div class='mw-section-title'>Action queue</div>", unsafe_allow_html=True)
        for action in data["recommended_actions"]:
            st.markdown(f"<span class='mw-pill'>{esc(ACTION_LABELS.get(action, action))}</span>", unsafe_allow_html=True)
        if data["uncertainty_flags"]:
            st.markdown("<div class='mw-section-title' style='margin-top:18px;'>Uncertainty</div>", unsafe_allow_html=True)
            for flag in data["uncertainty_flags"]:
                st.markdown(f"<div class='mw-alert'>{esc(flag)}</div>", unsafe_allow_html=True)

with tab_evidence:
    resolved_order_id = clean_order_id or parse_order_id(clean_message)
    order = get_order(resolved_order_id) if resolved_order_id else None
    if order:
        tracking = get_tracking(order["order_id"])
        returns = get_return(order["order_id"])
        product = get_product(order["items"][0]["sku"])
        st.markdown("<div class='mw-section-title'>Order journey</div>", unsafe_allow_html=True)
        render_journey(build_order_journey(order, tracking, returns, product))
    else:
        st.markdown("<div class='mw-alert'>No synthetic order was found, so no journey can be displayed.</div>", unsafe_allow_html=True)

    evidence_left, evidence_right = st.columns(2, gap="large")
    with evidence_left:
        render_fact_list("Verified facts", data["verified_facts"])
    with evidence_right:
        render_policy(data["policy_citations"])
        with st.expander("All citations and scores"):
            for citation in data["policy_citations"]:
                st.write(f"- {citation['section']} ({citation['score']}): {citation['summary']} {citation.get('source_url') or ''}")
        with st.expander("Tool trace"):
            st.code("\n".join(data["tool_trace"]))

with tab_reply:
    if data["input_language"] == "ar":
        st.markdown("<div class='mw-section-title'>Arabic reply shown first</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mw-reply mw-rtl'>{esc(data['reply_ar'])}</div>", unsafe_allow_html=True)
        st.markdown("<div class='mw-section-title'>English reply</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mw-reply'>{esc(data['reply_en'])}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='mw-section-title'>English reply</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mw-reply'>{esc(data['reply_en'])}</div>", unsafe_allow_html=True)
        st.markdown("<div class='mw-section-title'>Arabic reply</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mw-reply mw-rtl'>{esc(data['reply_ar'])}</div>", unsafe_allow_html=True)

with tab_json:
    st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")
