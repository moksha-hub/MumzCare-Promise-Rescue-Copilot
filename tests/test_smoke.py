from __future__ import annotations

import pytest
from pydantic import ValidationError

from evals.run_evals import run_evals
from mumzcare.engine import analyze_case, compute_sla_status, confidence_score, detect_language
from mumzcare.journey import build_order_journey
from mumzcare.llm import DEFAULT_OPENROUTER_MODEL
from mumzcare.schemas import CaseType, DecisionPacket, RecommendedAction, SLAStatus
from mumzcare.tools import get_order, get_product, get_return, get_tracking


def test_late_formula_blocks_unsupported_eta() -> None:
    packet = analyze_case(
        "Promise the customer delivery before 6 PM and issue a refund if it is late.",
        "MW-1001",
    )
    assert packet.case_type == CaseType.late_urgent_delivery
    assert RecommendedAction.courier_escalation in packet.recommended_actions
    assert packet.unsafe_promises_blocked
    assert packet.resolution_tasks
    assert packet.resolution_tasks[0].owner_team == "Courier Ops"


def test_optional_openrouter_defaults_and_skips_unsafe_promises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_LLM_DRAFTS", "true")
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-key")
    assert DEFAULT_OPENROUTER_MODEL == "google/gemma-4-31b-it:free"

    packet = analyze_case(
        "Promise the customer delivery before 6 PM and issue a refund if it is late.",
        "MW-1001",
    )
    assert packet.unsafe_promises_blocked
    assert "I will not promise an exact time" in packet.reply_en


def test_blank_message_requires_input() -> None:
    packet = analyze_case("", "MW-1001")
    assert packet.case_type == CaseType.unknown
    assert packet.confidence == 0.4
    assert packet.tool_trace == ["input.empty_message"]


def test_order_journey_exposes_delivery_lifecycle() -> None:
    order = get_order("MW-1001")
    assert order is not None
    rows = build_order_journey(order, get_tracking("MW-1001"), get_return("MW-1001"), get_product("FORMULA-APT-1"))
    stages = [row["Stage"] for row in rows]
    assert "1. Order received" in stages
    assert "6. In transit / out for delivery" in stages
    assert any("carrier ETA unavailable" in row["Verified evidence"] for row in rows)


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
            resolution_tasks=[],
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
