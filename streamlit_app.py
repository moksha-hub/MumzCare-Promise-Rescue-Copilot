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
    "Unsafe promise request": ("MW-1008", "Promise a refund today even if the return is not collected yet."),
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {
            --bg: #f5f1e8;
            --bg-soft: #fbf8f2;
            --panel: #fffdf8;
            --panel-alt: #f8f4ec;
            --line: #ddd4c6;
            --line-strong: #cdbfa9;
            --text: #2d2418;
            --muted: #706354;
            --soft: #4b4033;
            --accent: #8d6e43;
            --accent-soft: #efe3cf;
            --danger: #9e4f4f;
            --warning: #a27535;
            --ok: #5f7a5a;
            --radius: 14px;
            --shadow: 0 10px 30px rgba(72, 51, 24, 0.06);
        }

        *, *::before, *::after { box-sizing: border-box; }

        .block-container {
            max-width: 1320px;
            padding-top: 2rem;
            padding-bottom: 3.2rem;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }

        .stApp {
            background: linear-gradient(180deg, var(--bg-soft) 0%, var(--bg) 100%);
            color: var(--text);
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }

        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"] {
            display: none !important;
        }

        .stDeployButton {
            display: none !important;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        h1, h2, h3 {
            letter-spacing: -0.01em;
            font-family: 'Inter', system-ui, sans-serif;
            color: var(--text);
        }

        button[kind="primary"],
        .stButton > button,
        [data-testid="stFormSubmitButton"] button {
            background: var(--accent) !important;
            color: #fffdf8 !important;
            font-weight: 700 !important;
            border: 1px solid var(--accent) !important;
            border-radius: 10px !important;
            transition: background 0.2s ease, border-color 0.2s ease !important;
            font-family: 'Inter', system-ui, sans-serif !important;
            box-shadow: none !important;
        }

        button[kind="primary"]:hover,
        .stButton > button:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            background: #7c613a !important;
            border-color: #7c613a !important;
            transform: none !important;
        }

        [data-testid="stMetric"] {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: none;
        }

        [data-testid="stMetric"] label {
            color: var(--muted) !important;
            font-size: 0.76rem !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        [data-testid="stMetricValue"] {
            color: var(--text) !important;
            font-size: 1.28rem !important;
            font-variant-numeric: tabular-nums;
        }

        .mw-hero {
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 28px 30px 26px;
            background: var(--panel);
            margin-bottom: 18px;
            box-shadow: var(--shadow);
        }

        .mw-eyebrow {
            color: var(--accent);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .mw-title {
            color: var(--text);
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 10px;
            letter-spacing: -0.02em;
        }

        .mw-subtitle {
            color: var(--muted);
            max-width: 820px;
            line-height: 1.58;
            font-size: 0.95rem;
        }

        .mw-panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            padding: 18px;
            margin-bottom: 16px;
            box-shadow: var(--shadow);
        }

        .mw-section-title {
            color: var(--text);
            font-size: 1rem;
            font-weight: 750;
            margin-bottom: 12px;
        }

        .mw-kicker {
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.5;
            margin-top: -4px;
            margin-bottom: 14px;
        }

        .mw-problem {
            border-left: 3px solid var(--accent);
            background: var(--accent-soft);
            padding: 15px 16px;
            border-radius: 10px;
            color: var(--soft);
            font-size: 0.96rem;
            line-height: 1.56;
            margin-bottom: 14px;
        }

        .mw-task {
            border: 1px solid var(--line);
            background: var(--panel-alt);
            border-radius: 12px;
            padding: 16px;
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
            font-weight: 700;
            font-size: 0.95rem;
            overflow-wrap: anywhere;
        }

        .mw-team {
            color: var(--accent);
            font-size: 0.84rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .mw-label {
            color: var(--muted);
            font-size: 0.74rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 10px;
            margin-bottom: 3px;
        }

        .mw-text {
            color: var(--soft);
            line-height: 1.52;
            font-size: 0.91rem;
        }

        .mw-text ul {
            margin: 6px 0 0 1rem;
            padding: 0;
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
            border-radius: 999px;
            border: 1px solid var(--line-strong);
            background: #fcf8f1;
            color: var(--soft);
            padding: 6px 11px;
            font-size: 0.79rem;
            font-weight: 600;
        }

        .mw-pill.danger {
            border-color: #d8b3b3;
            background: #f8ecec;
            color: var(--danger);
        }

        .mw-pill.warning {
            border-color: #dec8a1;
            background: #f7f0e1;
            color: var(--warning);
        }

        .mw-pill.ok {
            border-color: #bfd0bb;
            background: #eef4ec;
            color: var(--ok);
        }

        .mw-note {
            background: #eef4ec;
            border: 1px solid #c9d8c6;
            color: #40563d;
            border-radius: 12px;
            padding: 14px 16px;
            line-height: 1.52;
            margin-bottom: 14px;
        }

        .mw-alert {
            background: #f9ece9;
            border: 1px solid #e2c1ba;
            color: #7a4239;
            border-radius: 12px;
            padding: 14px 16px;
            line-height: 1.52;
            margin-bottom: 14px;
        }

        .mw-timeline {
            display: grid;
            gap: 10px;
        }

        .mw-stage {
            display: grid;
            grid-template-columns: 26px 1fr auto;
            gap: 10px;
            align-items: start;
            padding: 12px 14px;
            border: 1px solid var(--line);
            background: var(--panel-alt);
            border-radius: 12px;
        }

        .mw-dot {
            height: 10px;
            width: 10px;
            margin-top: 5px;
            border-radius: 50%;
            background: var(--muted);
        }

        .mw-dot.done { background: var(--ok); }
        .mw-dot.active { background: var(--accent); }
        .mw-dot.pending { background: var(--warning); }
        .mw-dot.blocked, .mw-dot.at_risk { background: var(--danger); }

        .mw-stage-title {
            color: var(--text);
            font-weight: 700;
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
            font-size: 0.76rem;
            border: 1px solid var(--line);
            background: #fffdf8;
            padding: 4px 8px;
            border-radius: 999px;
            font-weight: 600;
            white-space: nowrap;
        }

        .mw-reply {
            background: var(--panel-alt);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 18px;
            color: var(--soft);
            line-height: 1.65;
            margin-bottom: 14px;
        }

        .mw-rtl {
            direction: rtl;
            text-align: right;
            font-size: 1rem;
        }

        .mw-trace-span {
            display: grid;
            grid-template-columns: 190px 130px 1fr;
            gap: 10px;
            align-items: start;
            border: 1px solid var(--line);
            border-radius: 10px;
            padding: 11px 12px;
            background: rgba(255,255,255,0.035);
            margin-bottom: 8px;
        }

        .mw-trace-service {
            color: var(--accent);
            font-size: 0.8rem;
            font-weight: 800;
            overflow-wrap: anywhere;
        }

        .mw-trace-status {
            color: var(--soft);
            font-size: 0.78rem;
            font-weight: 700;
            border: 1px solid var(--line);
            border-radius: 6px;
            padding: 4px 7px;
            width: fit-content;
        }

        .mw-trace-evidence {
            color: var(--soft);
            font-size: 0.86rem;
            line-height: 1.45;
        }

        .mw-empty {
            border: 1px dashed var(--line-strong);
            border-radius: 16px;
            padding: 44px 32px;
            text-align: center;
            color: var(--muted);
            background: var(--panel);
            font-size: 0.94rem;
            line-height: 1.6;
            box-shadow: var(--shadow);
        }

        .mw-intake-note {
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 14px 16px;
            background: #f8f3ea;
            color: var(--muted);
            font-size: 0.84rem;
            line-height: 1.5;
            margin-bottom: 14px;
        }

        .mw-demo-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 6px 0 18px;
        }

        .mw-demo-chip {
            border: 1px solid var(--line-strong);
            border-radius: 999px;
            padding: 7px 11px;
            color: var(--muted);
            background: #fffdf8;
            font-size: 0.8rem;
            font-weight: 650;
        }

        .mw-intake-grid {
            display: grid;
            grid-template-columns: 1fr 1fr auto;
            gap: 12px;
            align-items: end;
            margin-bottom: 16px;
        }

        .mw-form-panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: var(--shadow);
        }

        .mw-diagnosis-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 16px;
        }

        .mw-diagnosis-card {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 16px;
            min-height: 116px;
            box-shadow: var(--shadow);
        }

        .mw-diagnosis-label {
            color: var(--accent);
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 7px;
        }

        .mw-diagnosis-value {
            color: var(--text);
            font-size: 0.9rem;
            line-height: 1.5;
            font-weight: 650;
        }

        @media (max-width: 900px) {
            .mw-diagnosis-grid,
            .mw-intake-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .mw-trace-span {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 560px) {
            .mw-diagnosis-grid,
            .mw-intake-grid {
                grid-template-columns: 1fr;
            }
        }

        input, textarea,
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea {
            background: #fffdf8 !important;
            color: var(--text) !important;
            border: 1px solid var(--line-strong) !important;
            border-radius: 10px !important;
            caret-color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            opacity: 1 !important;
        }

        [data-testid="stTextInput"] label,
        [data-testid="stTextArea"] label {
            color: var(--text) !important;
            font-weight: 650 !important;
        }

        input::placeholder,
        textarea::placeholder {
            color: #8b7d6e !important;
            opacity: 1 !important;
        }

        div[data-testid="stTabs"] [role="tablist"] {
            border-bottom: 0;
            gap: 8px;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 8px;
            margin-bottom: 16px;
        }

        div[data-testid="stTabs"] [role="tab"] {
            transition: background 0.2s ease;
            border-radius: 9px;
            border: 1px solid transparent;
            padding: 8px 12px;
            background: #fffdf8;
        }

        div[data-testid="stTabs"] [role="tab"]:hover {
            background: var(--accent-soft);
            border-color: var(--line-strong);
        }

        div[data-testid="stTabs"] [role="tab"] p {
            color: var(--text) !important;
            font-weight: 700;
            font-size: 0.9rem;
        }

        div[data-testid="stTabs"] [aria-selected="true"] {
            background: var(--accent) !important;
            border-color: var(--accent) !important;
        }

        div[data-testid="stTabs"] [aria-selected="true"] p {
            color: #fffdf8 !important;
            font-weight: 800;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--line) !important;
            border-radius: 12px !important;
            background: var(--panel) !important;
        }

        .stSpinner > div { color: var(--accent) !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def esc(value: Any) -> str:
    return html.escape(str(value))


def render_task(task: dict[str, Any]) -> None:
    steps = "".join(f"<li>{esc(step)}</li>" for step in task["next_steps"])
    payload = "".join(f"<li>{esc(item)}</li>" for item in task["escalation_payload"])
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
          <div class="mw-label">Root-cause hypothesis</div>
          <div class="mw-text">{esc(task['root_cause_hypothesis'])}</div>
          <div class="mw-label">Backend signal to check</div>
          <div class="mw-text">{esc(task['backend_signal_to_check'])}</div>
          <div class="mw-label">Escalation payload</div>
          <div class="mw-text"><ul>{payload}</ul></div>
          <div class="mw-label">Promise boundary</div>
          <div class="mw-text">{esc(task['customer_promise_boundary'])}</div>
          <div class="mw-label">Next steps</div>
          <div class="mw-text"><ul>{steps}</ul></div>
          <div class="mw-label">Success metric</div>
          <div class="mw-text">{esc(task['success_metric'])}</div>
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


def render_promise_trace(trace: dict[str, Any] | None) -> None:
    st.markdown("<div class='mw-section-title'>Promise Trace Overlay</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='mw-kicker'>Synthetic OpenTelemetry-style spans that map the customer complaint to the backend signal operations should inspect.</div>",
        unsafe_allow_html=True,
    )
    if not trace:
        st.markdown("<div class='mw-alert'>No promise trace exists for this unknown or unsupported order.</div>", unsafe_allow_html=True)
        return

    missing = ", ".join(trace["missing_signals"]) if trace["missing_signals"] else "No missing signal for this trace."
    playbook = "".join(f"<li>{esc(step)}</li>" for step in trace["operational_playbook"])
    st.markdown(
        f"""
        <div class="mw-panel">
          <div class="mw-section-title">{esc(trace['trace_id'])}</div>
          <div class="mw-problem">{esc(trace['root_cause_summary'])}</div>
          <div class="mw-pill-row">
            <span class="mw-pill">Broken span: {esc(trace['broken_span'])}</span>
            <span class="mw-pill">Missing signals: {esc(missing)}</span>
          </div>
          <div class="mw-label">Customer-visible symptom</div>
          <div class="mw-text">{esc(trace['customer_visible_symptom'])}</div>
          <div class="mw-label">Instrumentation gap</div>
          <div class="mw-text">{esc(trace['instrumentation_gap'])}</div>
          <div class="mw-label">Operational playbook</div>
          <div class="mw-text"><ul>{playbook}</ul></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for span in trace["spans"]:
        st.markdown(
            f"""
            <div class="mw-trace-span">
              <div>
                <div class="mw-trace-service">{esc(span['service'])}</div>
                <div class="mw-text">{esc(span['span_name'])}</div>
              </div>
              <div class="mw-trace-status">{esc(span['status'])}</div>
              <div class="mw-trace-evidence">{esc(span['evidence'])}<br/>Duration: {esc(span['duration_ms'])} ms</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_ops_memory(insights: list[dict[str, Any]]) -> None:
    st.markdown("<div class='mw-section-title'>Outcome-Aware Ops Memory</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='mw-kicker'>Synthetic historical cases are matched by failure signature and outcome, not only exact courier or zone. Memory is advisory; verified tools and policy still win.</div>",
        unsafe_allow_html=True,
    )
    if not insights:
        st.markdown("<div class='mw-alert'>No reliable historical precedent was found for this path. Route conservatively and update the case note after closure.</div>", unsafe_allow_html=True)
        return
    for insight in insights:
        signal = insight["outcome_signal"]
        playbook = "".join(f"<li>{esc(step)}</li>" for step in insight["recommended_playbook"])
        outcome_class = "ok" if insight["resolution_outcome"] == "resolved" else "warning"
        repeat = "yes" if signal["repeat_contact_within_72h"] else "no"
        st.markdown(
            f"""
            <div class="mw-task">
              <div class="mw-task-head">
                <div>
                  <div class="mw-task-id">{esc(insight['memory_id'])} - {esc(insight['title'])}</div>
                  <div class="mw-text">Similarity {esc(insight['similarity_score'])}</div>
                </div>
                <div class="mw-team">{esc(insight['resolution_outcome'])}</div>
              </div>
              <div class="mw-pill-row">
                <span class="mw-pill {outcome_class}">Outcome: {esc(insight['resolution_outcome'])}</span>
                <span class="mw-pill">Repeat contact 72h: {repeat}</span>
                <span class="mw-pill">Resolution: {esc(signal['resolution_hours'])}h</span>
                <span class="mw-pill">CSAT: {esc(signal.get('csat') or 'n/a')}</span>
              </div>
              <div class="mw-label">Failure pattern</div>
              <div class="mw-text">{esc(insight['pattern_summary'])}</div>
              <div class="mw-label">Prior action</div>
              <div class="mw-text">{esc(insight['prior_action'])}</div>
              <div class="mw-label">Lesson learned</div>
              <div class="mw-text">{esc(insight['lesson'])}</div>
              <div class="mw-label">Semantic reasoning</div>
              <div class="mw-text">{esc(insight['semantic_reasoning'])}</div>
              <div class="mw-label">Outcome-aware playbook</div>
              <div class="mw-text"><ul>{playbook}</ul></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def operational_diagnosis(
    data: dict[str, Any],
    order: dict[str, Any] | None,
    tracking: dict[str, Any] | None,
    returns: dict[str, Any] | None,
) -> dict[str, str]:
    """Convert the packet into the company-side problem the support agent must resolve."""
    case_type = data["case_type"]
    if case_type == "late_urgent_delivery":
        eta = tracking.get("eta") if tracking else None
        return {
            "stage": "Last-mile delivery / courier handoff",
            "bottleneck": "Promised window is breached or at risk, and exact carrier ETA is not safe to promise." if not eta else "Carrier ETA exists, so the agent can reassure inside that verified window.",
            "owner": "Courier Ops + Senior Customer Care",
            "safe_resolution": "Open courier escalation, request verified update, then send reply without inventing an exact time.",
        }
    if case_type == "delivered_not_received":
        return {
            "stage": "Delivered scan / customer confirmation",
            "bottleneck": "Carrier state says delivered, but the customer disputes receipt.",
            "owner": "Delivery Investigation",
            "safe_resolution": "Check proof of delivery, address notes, and customer claim before refund or replacement.",
        }
    if case_type == "damaged_or_wrong_item":
        return {
            "stage": "Post-delivery quality / return evidence",
            "bottleneck": "Item condition is disputed and needs evidence plus eligibility review.",
            "owner": "Returns & Replacement Desk",
            "safe_resolution": "Collect evidence, check stock and policy eligibility, then approve exchange/replacement only after review.",
        }
    if case_type == "return_pickup_delay":
        status = returns.get("status") if returns else "missing"
        return {
            "stage": "Return pickup operations",
            "bottleneck": f"Return record is {status}; pickup window must be checked against the market SLA.",
            "owner": "Return Pickup Ops",
            "safe_resolution": "Reschedule or escalate pickup partner when the policy window is breached.",
        }
    if case_type == "refund_timing":
        payment = order.get("payment_method") if order else "unknown"
        return {
            "stage": "Refund review / payment rail",
            "bottleneck": f"Refund timing depends on verified return state and the {payment} payment rail.",
            "owner": "Payments & Refunds",
            "safe_resolution": "Follow the payment-method window; do not promise manual acceleration unless authorized.",
        }
    if case_type == "stock_cancellation":
        return {
            "stage": "Stock reservation before dispatch",
            "bottleneck": "The order did not safely reach courier handoff because stock was unavailable.",
            "owner": "Catalog / Stock Recovery + Payments",
            "safe_resolution": "Offer an approved substitute for the baby need or route original-method refund handling.",
        }
    if case_type == "out_of_scope":
        return {
            "stage": "Safety / trust boundary",
            "bottleneck": "The request is outside safe support automation.",
            "owner": "Senior Customer Care",
            "safe_resolution": "Refuse unsafe advice or policy abuse and route to a human reviewer.",
        }
    return {
        "stage": "Intake",
        "bottleneck": "The copilot does not have enough verified information to classify the issue.",
        "owner": "Customer Care Intake",
        "safe_resolution": "Ask for missing order details before checking facts or promising a resolution.",
    }


def render_diagnosis_cards(diagnosis: dict[str, str]) -> None:
    cards = [
        ("Process stage", diagnosis["stage"]),
        ("Bottleneck found", diagnosis["bottleneck"]),
        ("Internal owner", diagnosis["owner"]),
        ("Safe company action", diagnosis["safe_resolution"]),
    ]
    html_cards = "".join(
        f"<div class='mw-diagnosis-card'>"
        f"<div class='mw-diagnosis-label'>{esc(label)}</div>"
        f"<div class='mw-diagnosis-value'>{esc(value)}</div>"
        f"</div>"
        for label, value in cards
    )
    st.markdown(f"<div class='mw-diagnosis-grid'>{html_cards}</div>", unsafe_allow_html=True)


inject_css()

st.markdown(
    """
    <div class="mw-hero">
      <div class="mw-eyebrow">Internal support workspace</div>
      <div class="mw-title">MumzCare Promise Rescue Copilot</div>
      <div class="mw-subtitle">
        Converts a post-order complaint into an internal recovery plan, promise trace, and safe English/Arabic reply draft.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "selected_demo" not in st.session_state:
    st.session_state.selected_demo = "Late formula delivery"
if "case_order_id" not in st.session_state or "case_message" not in st.session_state:
    default_order, default_message = SAMPLES[st.session_state.selected_demo]
    st.session_state.case_order_id = default_order
    st.session_state.case_message = default_message

st.markdown("<div class='mw-section-title'>Demo scenarios</div>", unsafe_allow_html=True)
demo_cols = st.columns(5, gap="small")
for index, sample_name in enumerate(SAMPLES):
    with demo_cols[index % 5]:
        if st.button(sample_name, key=f"demo_{index}", use_container_width=True):
            st.session_state.selected_demo = sample_name
            st.session_state.case_order_id, st.session_state.case_message = SAMPLES[sample_name]
            st.rerun()

st.markdown(
    f"<div class='mw-demo-row'><span class='mw-demo-chip'>Selected: {esc(st.session_state.selected_demo)}</span></div>",
    unsafe_allow_html=True,
)

order_col = st.columns([1])[0]
with order_col:
    order_id = st.text_input("Order ID", key="case_order_id", placeholder="MW-1001")

with st.form("case_form"):
    message = st.text_area("Customer message", key="case_message", height=120, placeholder="Paste the customer's email, chat, or WhatsApp message.")
    analyze = st.form_submit_button("Analyze case", type="primary", use_container_width=True)
st.caption("Synthetic orders: MW-1001 to MW-1010. External IDs return an explicit unknown-order path.")

if not analyze:
    st.markdown(
        """
        <div class="mw-empty">
          <div style="font-weight:700; font-size:1.05rem; color:var(--soft); margin-bottom:8px;">Ready to analyze</div>
          Select a demo or paste a message, then run analysis.
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

with st.spinner("Analyzing case - checking order data, policy, and building resolution..."):
    packet = analyze_case(message=clean_message, order_id=clean_order_id or None)
data = packet.model_dump(mode="json")
resolved_order_id = clean_order_id or parse_order_id(clean_message)
order = get_order(resolved_order_id) if resolved_order_id else None
tracking = get_tracking(resolved_order_id) if resolved_order_id else None
returns = get_return(resolved_order_id) if resolved_order_id else None

problem = data["resolution_tasks"][0]["problem_detected"] if data["resolution_tasks"] else "No problem detected yet."
priority_class = PRIORITY_CLASS.get(data["urgency"], "neutral")
diagnosis = operational_diagnosis(data, order, tracking, returns)

st.markdown(
    f"""
    <div class="mw-panel">
      <div class="mw-section-title">Case summary</div>
      <div class="mw-problem">{esc(problem)}</div>
      <div class="mw-pill-row">
        <span class="mw-pill">Issue type: {esc(data['case_type'])}</span>
        <span class="mw-pill">SLA status: {esc(data['sla_status'])}</span>
        <span class="mw-pill {priority_class}">Urgency: {esc(data['urgency'])}</span>
        <span class="mw-pill">Confidence: {esc(f"{data['confidence']:.2f}")}</span>
        <span class="mw-pill">Input language: {esc(data['input_language'])}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_diagnosis_cards(diagnosis)

if data["human_review_required"]:
    st.markdown("<div class='mw-note'><strong>Human review required</strong><br/>A senior agent should approve the final resolution before it is communicated to the customer.</div>", unsafe_allow_html=True)
if data["unsafe_promises_blocked"]:
    blocked = "<br/>".join(esc(item) for item in data["unsafe_promises_blocked"])
    st.markdown(f"<div class='mw-alert'><strong>Promise blocked</strong><br/>{blocked}</div>", unsafe_allow_html=True)

tab_resolution, tab_memory, tab_trace, tab_evidence, tab_reply, tab_json = st.tabs(
    ["Resolution plan", "Ops memory", "Promise trace", "Evidence", "Reply draft", "Audit JSON"]
)

with tab_resolution:
    col_tasks, col_actions = st.columns([1.45, 0.85], gap="large")
    with col_tasks:
        st.markdown("<div class='mw-section-title'>Resolution tasks</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='mw-kicker'>These simulated internal tasks show who should act next and what can be safely promised.</div>",
            unsafe_allow_html=True,
        )
        for task in data["resolution_tasks"]:
            render_task(task)

    with col_actions:
        st.markdown("<div class='mw-section-title'>Recommended actions</div>", unsafe_allow_html=True)
        for action in data["recommended_actions"]:
            st.markdown(f"<span class='mw-pill'>{esc(ACTION_LABELS.get(action, action))}</span>", unsafe_allow_html=True)
        if data["uncertainty_flags"]:
            st.markdown("<div class='mw-section-title' style='margin-top:18px;'>Open questions</div>", unsafe_allow_html=True)
            for flag in data["uncertainty_flags"]:
                st.markdown(f"<div class='mw-alert'>{esc(flag)}</div>", unsafe_allow_html=True)

with tab_trace:
    render_promise_trace(data.get("promise_trace"))

with tab_memory:
    render_ops_memory(data.get("ops_memory_insights", []))
    note = data.get("obsidian_case_note")
    if note:
        st.markdown("<div class='mw-section-title'>Auto-generated Obsidian note draft</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='mw-kicker'>Agent reviews this Markdown at closure and fills the outcome fields so the memory graph learns whether the response worked.</div>",
            unsafe_allow_html=True,
        )
        st.code(note, language="markdown")

with tab_evidence:
    if order:
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
        st.markdown("<div class='mw-section-title'>Arabic draft</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mw-reply mw-rtl'>{esc(data['reply_ar'])}</div>", unsafe_allow_html=True)
        st.markdown("<div class='mw-section-title'>English draft</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mw-reply'>{esc(data['reply_en'])}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='mw-section-title'>English draft</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mw-reply'>{esc(data['reply_en'])}</div>", unsafe_allow_html=True)
        st.markdown("<div class='mw-section-title'>Arabic draft</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mw-reply mw-rtl'>{esc(data['reply_ar'])}</div>", unsafe_allow_html=True)

with tab_json:
    st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")
