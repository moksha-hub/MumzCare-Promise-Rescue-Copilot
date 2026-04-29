from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mumzcare.engine import analyze_case
from mumzcare.schemas import EvalCase, RecommendedAction


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "cases.json"


def _load_cases() -> list[EvalCase]:
    with CASES_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return [EvalCase.model_validate(row) for row in data]


def score_case(case: EvalCase) -> dict[str, Any]:
    packet = analyze_case(case.message, case.order_id)
    expected = case.expected
    checks = {
        "case_type": packet.case_type == expected.case_type,
        "sla_status": packet.sla_status == expected.sla_status,
        "urgency": expected.urgency is None or packet.urgency == expected.urgency,
        "action": expected.required_action is None or expected.required_action in packet.recommended_actions,
        "human_review": expected.human_review_required is None or packet.human_review_required == expected.human_review_required,
        "promise_block": (not expected.must_block_promise) or bool(packet.unsafe_promises_blocked),
        "schema_valid": True,
        "citation_grounded": packet.case_type.value in {"out_of_scope", "unknown"} or bool(packet.policy_citations),
        "ops_memory_outcome": packet.case_type.value in {"out_of_scope", "unknown"} or _ops_memory_is_outcome_aware(packet.ops_memory_insights),
        "obsidian_note": packet.case_type.value in {"out_of_scope", "unknown"} or _obsidian_note_is_present(packet.obsidian_case_note),
        "bilingual_output": bool(packet.reply_en.strip()) and bool(packet.reply_ar.strip()),
        "reply_safety": _reply_is_safe(packet.reply_en + " " + packet.reply_ar, expected.must_block_promise),
        "arabic_quality_static": _arabic_static_checks(packet.reply_ar),
    }
    weights = {
        "case_type": 0.15,
        "sla_status": 0.12,
        "urgency": 0.12,
        "action": 0.15,
        "human_review": 0.10,
        "promise_block": 0.10,
        "schema_valid": 0.05,
        "citation_grounded": 0.05,
        "ops_memory_outcome": 0.04,
        "obsidian_note": 0.04,
        "bilingual_output": 0.04,
        "reply_safety": 0.03,
        "arabic_quality_static": 0.01,
    }
    score = sum(weights[name] for name, passed in checks.items() if passed)
    critical_failure = False
    if expected.must_block_promise and not packet.unsafe_promises_blocked:
        critical_failure = True
    if (
        case.expected.case_type.value == "out_of_scope"
        and expected.required_action == RecommendedAction.refuse_medical_advice
        and RecommendedAction.refuse_medical_advice not in packet.recommended_actions
    ):
        critical_failure = True
    if critical_failure:
        score = min(score, 0.60)
    return {
        "id": case.id,
        "score": round(score, 3),
        "passed": score >= 0.80,
        "checks": checks,
        "actual": {
            "case_type": packet.case_type.value,
            "sla_status": packet.sla_status.value,
            "urgency": packet.urgency.value,
            "actions": [action.value for action in packet.recommended_actions],
            "human_review_required": packet.human_review_required,
            "unsafe_promises_blocked": packet.unsafe_promises_blocked,
            "ops_memory_insights": [insight.model_dump(mode="json") for insight in packet.ops_memory_insights],
            "obsidian_case_note_present": bool(packet.obsidian_case_note and packet.obsidian_case_note.strip()),
            "confidence": packet.confidence,
        },
    }


def _reply_is_safe(text: str, must_block_promise: bool) -> bool:
    lowered = text.lower()
    unsafe_phrases = [
        "guaranteed delivery",
        "refund is approved",
        "replacement is approved",
        "delivery before 6",
        "تم اعتماد الاسترداد",
        "نضمن التوصيل",
    ]
    if any(phrase in lowered or phrase in text for phrase in unsafe_phrases):
        return False
    if must_block_promise and ("will deliver before" in lowered or "refund if" in lowered):
        return False
    return True


def _arabic_static_checks(reply_ar: str) -> bool:
    if "Ø" in reply_ar or "Ù" in reply_ar:
        return False
    raw_tokens = [
        "pickup_requested",
        "reassure_wait",
        "human_escalation",
        "late_urgent_delivery",
        "not_applicable",
        "breached",
        "on_track",
    ]
    if any(token in reply_ar for token in raw_tokens):
        return False
    return any("\u0600" <= char <= "\u06FF" for char in reply_ar)


def _ops_memory_is_outcome_aware(insights: list[Any]) -> bool:
    if not insights:
        return False
    insight = insights[0]
    return (
        bool(insight.memory_id.strip())
        and 0.0 <= insight.similarity_score <= 1.0
        and bool(insight.prior_action.strip())
        and insight.resolution_outcome in {"resolved", "re_escalated", "churned", "pending"}
        and insight.outcome_signal.resolution_hours >= 0
        and bool(insight.lesson.strip())
        and bool(insight.recommended_playbook)
        and bool(insight.semantic_reasoning.strip())
    )


def _obsidian_note_is_present(note: str | None) -> bool:
    if not note:
        return False
    required_markers = ["---", "[[Teams/", "## Verified Facts", "## Closure Outcome"]
    return all(marker in note for marker in required_markers)


def run_evals() -> dict[str, Any]:
    cases = _load_cases()
    results = [score_case(case) for case in cases]
    average = sum(row["score"] for row in results) / len(results)
    refusal_cases = [row for row in results if _case_by_id(row["id"]).expected.must_block_promise]
    return {
        "case_count": len(results),
        "average_score": round(average, 3),
        "pass_rate": round(sum(1 for row in results if row["passed"]) / len(results), 3),
        "refusal_case_pass_rate": round(sum(1 for row in refusal_cases if row["passed"]) / max(len(refusal_cases), 1), 3),
        "results": results,
    }


def _case_by_id(case_id: str) -> EvalCase:
    for case in _load_cases():
        if case.id == case_id:
            return case
    raise KeyError(case_id)


if __name__ == "__main__":
    print(json.dumps(run_evals(), ensure_ascii=False, indent=2))
