from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from mumzcare.data_loader import memory_cases
from mumzcare.llm import DEFAULT_OPENROUTER_MODEL
from mumzcare.schemas import CaseType, OpsMemoryInsight, SLAStatus

load_dotenv()


def memory_llm_enabled() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY")) and os.getenv("USE_LLM_MEMORY", "false").lower() == "true"


def current_failure_signature(
    message: str,
    case_type: CaseType,
    sla_status: SLAStatus,
    order: dict[str, Any] | None,
    tracking: dict[str, Any] | None,
    returns: dict[str, Any] | None,
    product: dict[str, Any] | None,
    promise_trace: Any | None,
) -> str:
    parts = [
        f"message: {message}",
        f"case_type: {case_type.value}",
        f"sla_status: {sla_status.value}",
    ]
    if order:
        parts.extend(
            [
                f"market: {order.get('country')}",
                f"zone: {order.get('emirate')}",
                f"order_status: {order.get('status')}",
                f"payment_method: {order.get('payment_method')}",
                f"priority: {order.get('priority')}",
            ]
        )
    if tracking:
        parts.extend(
            [
                f"courier: {tracking.get('carrier')}",
                f"tracking_status: {tracking.get('current_status')}",
                f"eta_available: {bool(tracking.get('eta'))}",
            ]
        )
    if returns:
        parts.append(f"return_status: {returns.get('status')}")
    if product:
        parts.extend(
            [
                f"product_category: {product.get('category')}",
                f"urgent_essential: {bool(product.get('urgent_essential'))}",
            ]
        )
    if promise_trace:
        parts.extend(
            [
                f"broken_span: {promise_trace.broken_span}",
                f"missing_signals: {', '.join(promise_trace.missing_signals)}",
                f"root_cause: {promise_trace.root_cause_summary}",
            ]
        )
    return "\n".join(parts)


def _memory_signature(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            row["title"],
            f"case_type: {row['case_type']}",
            f"courier: {row['courier']}",
            f"market: {row['market']}",
            f"zone: {row['zone']}",
            f"product_category: {row['product_category']}",
            f"prior_action: {row['prior_action']}",
            f"outcome: {row['resolution_outcome']}",
            " ".join(row["failure_signature"]),
            row["lesson"],
        ]
    )


def _score_case(current_text: str, row: dict[str, Any], case_type: CaseType, order: dict[str, Any] | None, tracking: dict[str, Any] | None, product: dict[str, Any] | None) -> float:
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform([current_text, _memory_signature(row)])
    score = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    if row["case_type"] == case_type.value:
        score += 0.22
    if order and row["market"] == order.get("country"):
        score += 0.05
    if order and row["zone"] == order.get("emirate"):
        score += 0.04
    if tracking and row["courier"] == tracking.get("carrier"):
        score += 0.04
    if product and row["product_category"] == product.get("category"):
        score += 0.12
    if row["resolution_outcome"] in {"re_escalated", "churned"}:
        score += 0.03
    return round(max(0.0, min(score, 1.0)), 3)


def _fallback_reasoning(row: dict[str, Any], score: float) -> str:
    outcome = row["resolution_outcome"].replace("_", " ")
    if row["resolution_outcome"] == "resolved":
        return f"Similar failure signature with a resolved outcome; reuse the playbook cautiously because verified current facts still control the decision. Similarity={score}."
    if row["resolution_outcome"] == "re_escalated":
        return f"Similar failure signature but the prior response was re-escalated, so avoid copying the first action blindly. Similarity={score}."
    if row["resolution_outcome"] == "churned":
        return f"Similar failure signature ended in churn, so require senior review before repeating the same response. Similarity={score}."
    return f"Similar failure signature has {outcome} outcome; treat as precedent, not proof. Similarity={score}."


def _optional_llm_reasoning(current_text: str, candidates: list[dict[str, Any]]) -> dict[str, str]:
    if not memory_llm_enabled() or not candidates:
        return {}
    try:
        from openai import OpenAI

        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
        prompt = f"""
You are ranking historical ecommerce support cases by failure signature, not exact field equality.
Use outcomes to avoid repeating failed playbooks.

Current case:
{current_text}

Candidate memory cases:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

Return compact JSON mapping memory_id to one sentence of semantic reasoning.
Do not invent facts. Do not recommend refunds, ETAs, or replacements unless candidate outcomes support cautious review.
"""
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        text = response.choices[0].message.content or "{}"
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return {}
        parsed = json.loads(text[start : end + 1])
        return {str(key): str(value) for key, value in parsed.items()}
    except Exception:
        return {}


def analyze_ops_memory(
    message: str,
    case_type: CaseType,
    sla_status: SLAStatus,
    order: dict[str, Any] | None,
    tracking: dict[str, Any] | None,
    returns: dict[str, Any] | None,
    product: dict[str, Any] | None,
    promise_trace: Any | None,
) -> list[OpsMemoryInsight]:
    if case_type in {CaseType.unknown, CaseType.out_of_scope}:
        return []
    current_text = current_failure_signature(message, case_type, sla_status, order, tracking, returns, product, promise_trace)
    scored = []
    for row in memory_cases():
        score = _score_case(current_text, row, case_type, order, tracking, product)
        if score >= 0.2:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:3]
    llm_reasoning = _optional_llm_reasoning(current_text, [row for _, row in top])
    insights: list[OpsMemoryInsight] = []
    for score, row in top:
        semantic_reasoning = llm_reasoning.get(row["memory_id"]) or _fallback_reasoning(row, score)
        insights.append(
            OpsMemoryInsight(
                memory_id=row["memory_id"],
                title=row["title"],
                similarity_score=score,
                pattern_summary="; ".join(row["failure_signature"][:3]),
                prior_action=row["prior_action"],
                resolution_outcome=row["resolution_outcome"],
                outcome_signal=row["outcome_signal"],
                lesson=row["lesson"],
                recommended_playbook=row["recommended_playbook"],
                semantic_reasoning=semantic_reasoning,
            )
        )
    return insights


def generate_obsidian_case_note(
    packet: Any,
    message: str,
    order: dict[str, Any] | None,
    tracking: dict[str, Any] | None,
    product: dict[str, Any] | None,
) -> str:
    order_id = order.get("order_id") if order else "unknown-order"
    courier = tracking.get("carrier") if tracking else "unknown-courier"
    zone = order.get("emirate") if order else "unknown-zone"
    product_category = product.get("category") if product else "unknown-product"
    owner = packet.resolution_tasks[0].owner_team if packet.resolution_tasks else "Human Review"
    actions = ", ".join(action.value for action in packet.recommended_actions)
    memory_links = "\n".join(f"- [[Memory/{insight.memory_id}]] {insight.title}" for insight in packet.ops_memory_insights) or "- No similar memory case found."
    facts = "\n".join(f"- {fact}" for fact in packet.verified_facts) or "- No verified operational facts available."
    blocked = "\n".join(f"- {item}" for item in packet.unsafe_promises_blocked) or "- None"
    playbook = "\n".join(f"- {step}" for insight in packet.ops_memory_insights[:1] for step in insight.recommended_playbook) or "- Follow the current resolution task and require human review where flagged."
    return f"""---
order_id: {order_id}
case_type: {packet.case_type.value}
urgency: {packet.urgency.value}
sla_status: {packet.sla_status.value}
owner_team: "{owner}"
courier: "{courier}"
zone: "{zone}"
product_category: "{product_category}"
resolution_outcome: pending
tags:
  - mumzcare/case
  - case/{packet.case_type.value}
  - urgency/{packet.urgency.value}
---

# {order_id} - {packet.case_type.value.replace("_", " ").title()}

> [!summary]
> AI-generated draft note for agent review. It records verified facts, memory precedent, blocked promises, and the pending outcome field that must be updated after closure.

## Customer Message
{message}

## Internal Owner
[[Teams/{owner}]]

## Recommended Actions
{actions}

## Verified Facts
{facts}

## Unsafe Promises Blocked
{blocked}

## Similar Memory Cases
{memory_links}

## Outcome-Aware Playbook
{playbook}

## Closure Outcome
- resolution_outcome: pending
- repeat_contact_within_72h:
- resolution_hours:
- csat:

## Reply Drafts
### English
{packet.reply_en}

### Arabic
{packet.reply_ar}
"""
