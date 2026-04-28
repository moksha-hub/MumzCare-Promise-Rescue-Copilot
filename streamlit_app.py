from __future__ import annotations

import json

import streamlit as st

from mumzcare.engine import analyze_case


SAMPLES = {
    "Late formula delivery": ("MW-1001", "My baby formula was promised today and tracking has not moved. I need it tonight."),
    "Arabic delivered missing": ("MW-1003", "الطلب MW-1003 مكتوب تم التوصيل بس ما وصلني شيء"),
    "Card refund timing": ("MW-1006", "I returned this order and still have not received my refund."),
    "Damaged stroller": ("MW-1004", "The stroller arrived damaged and the wheel is broken. I need a replacement."),
    "Unsafe promise request": ("MW-1001", "Promise the customer delivery before 6 PM and issue a refund if it is late."),
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


st.set_page_config(page_title="MumzCare Promise Rescue", layout="wide")
st.title("MumzCare Promise Rescue Copilot")
st.caption("Policy-grounded support decisions for urgent mother/baby order issues.")

sample = st.sidebar.selectbox("Demo scenario", list(SAMPLES))
default_order, default_message = SAMPLES[sample]

order_id = st.text_input("Order ID", value=default_order)
message = st.text_area("Customer message", value=default_message, height=120)

if st.button("Analyze", type="primary"):
    packet = analyze_case(message=message, order_id=order_id or None)
    data = packet.model_dump(mode="json")
    top = st.columns(5)
    top[0].metric("Case", data["case_type"])
    top[1].metric("SLA", data["sla_status"])
    top[2].metric("Urgency", data["urgency"])
    top[3].metric("Confidence", f"{data['confidence']:.2f}")
    top[4].metric("Input", data["input_language"])

    if data["human_review_required"]:
        st.warning("Human review required before promising a resolution.")
    if data["unsafe_promises_blocked"]:
        st.error("Unsafe promise blocked: " + "; ".join(data["unsafe_promises_blocked"]))

    left, right = st.columns(2)
    with left:
        st.subheader("Verified Facts")
        for fact in data["verified_facts"]:
            st.write(f"- {fact}")
        st.subheader("Policy Citations")
        if data["policy_citations"]:
            primary = data["policy_citations"][0]
            if primary.get("source_url"):
                st.write(f"**{primary['section']}**: {primary['summary']} [{primary['source_url']}]")
            else:
                st.write(f"**{primary['section']}**: {primary['summary']}")
        with st.expander("All policy citations and scores"):
            for citation in data["policy_citations"]:
                st.write(f"- **{citation['section']}** ({citation['score']}): {citation['summary']} {citation.get('source_url') or ''}")
        with st.expander("Tool trace"):
            st.code("\n".join(data["tool_trace"]))
    with right:
        st.subheader("Recommended Actions")
        for action in data["recommended_actions"]:
            st.write(f"- {ACTION_LABELS.get(action, action.replace('_', ' ').title())} (`{action}`)")
        if data["input_language"] == "ar":
            st.subheader("Reply AR")
            st.markdown(f"<div dir='rtl' style='text-align:right'>{data['reply_ar']}</div>", unsafe_allow_html=True)
            st.subheader("Reply EN")
            st.write(data["reply_en"])
        else:
            st.subheader("Reply EN")
            st.write(data["reply_en"])
            st.subheader("Reply AR")
            st.markdown(f"<div dir='rtl' style='text-align:right'>{data['reply_ar']}</div>", unsafe_allow_html=True)
        with st.expander("Raw validated JSON"):
            st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")
