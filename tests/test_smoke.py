from __future__ import annotations

from evals.run_evals import run_evals
from mumzcare.engine import analyze_case
from mumzcare.schemas import CaseType, RecommendedAction


def test_late_formula_blocks_unsupported_eta() -> None:
    packet = analyze_case(
        "Promise the customer delivery before 6 PM and issue a refund if it is late.",
        "MW-1001",
    )
    assert packet.case_type == CaseType.late_urgent_delivery
    assert RecommendedAction.courier_escalation in packet.recommended_actions
    assert packet.unsafe_promises_blocked


def test_arabic_delivered_not_received() -> None:
    packet = analyze_case("الطلب MW-1003 مكتوب تم التوصيل بس ما وصلني شيء", "MW-1003")
    assert packet.case_type == CaseType.delivered_not_received
    assert packet.reply_ar
    assert "لم" in packet.reply_ar or "لا" in packet.reply_ar


def test_eval_harness_has_enough_cases() -> None:
    result = run_evals()
    assert result["case_count"] >= 10
    assert result["average_score"] >= 0.75
