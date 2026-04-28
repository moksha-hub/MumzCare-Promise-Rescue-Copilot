from __future__ import annotations

import pytest
from pydantic import ValidationError

from evals.run_evals import run_evals
from mumzcare.engine import analyze_case, compute_sla_status, confidence_score, detect_language
from mumzcare.schemas import CaseType, DecisionPacket, RecommendedAction, SLAStatus
from mumzcare.tools import get_order, get_return


def test_late_formula_blocks_unsupported_eta() -> None:
    packet = analyze_case(
        "Promise the customer delivery before 6 PM and issue a refund if it is late.",
        "MW-1001",
    )
    assert packet.case_type == CaseType.late_urgent_delivery
    assert RecommendedAction.courier_escalation in packet.recommended_actions
    assert packet.unsafe_promises_blocked


def test_arabic_delivered_not_received() -> None:
    message = "\u0627\u0644\u0637\u0644\u0628 MW-1003 \u0645\u0643\u062a\u0648\u0628 \u062a\u0645 \u0627\u0644\u062a\u0648\u0635\u064a\u0644 \u0628\u0633 \u0645\u0627 \u0648\u0635\u0644\u0646\u064a \u0634\u064a\u0621"
    packet = analyze_case(message, "MW-1003")
    assert packet.case_type == CaseType.delivered_not_received
    assert packet.input_language == "ar"
    assert packet.reply_ar
    assert "\u0644\u0645" in packet.reply_ar or "\u0644\u0627" in packet.reply_ar


def test_eval_harness_has_enough_cases() -> None:
    result = run_evals()
    assert result["case_count"] >= 10
    assert result["average_score"] >= 0.95


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("My order is late", "en"),
        ("\u0627\u0644\u0637\u0644\u0628 MW-1003 \u0644\u0645 \u064a\u0635\u0644", "ar"),
        ("I received one item \u0648\u0627\u0644\u0628\u0627\u0642\u064a \u0646\u0627\u0642\u0635", "mixed"),
    ],
)
def test_detect_language(message: str, expected: str) -> None:
    assert detect_language(message) == expected


def test_return_pickup_sla_breached_for_uae() -> None:
    order = get_order("MW-1009")
    returns = get_return("MW-1009")
    assert order is not None
    assert returns is not None
    assert compute_sla_status(CaseType.return_pickup_delay, order, None, returns) == SLAStatus.breached


def test_confidence_degrades_without_citations() -> None:
    order = get_order("MW-1001")
    assert order is not None
    score = confidence_score(CaseType.late_urgent_delivery, order, None, None, [], ["Carrier ETA unavailable"])
    assert score < 0.7


def test_decision_packet_rejects_ungrounded_in_scope_case() -> None:
    with pytest.raises(ValidationError):
        DecisionPacket(
            input_language="en",
            case_type=CaseType.late_urgent_delivery,
            sla_status=SLAStatus.breached,
            urgency="high",
            recommended_actions=[RecommendedAction.courier_escalation],
            verified_facts=[],
            policy_citations=[],
            confidence=0.9,
            human_review_required=True,
            uncertainty_flags=[],
            unsafe_promises_blocked=[],
            reply_en="We are checking this.",
            reply_ar="\u0633\u0646\u0631\u0627\u062c\u0639 \u0647\u0630\u0627 \u0627\u0644\u0637\u0644\u0628.",
            tool_trace=["unit_test"],
        )
