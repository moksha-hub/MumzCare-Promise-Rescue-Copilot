from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


Language = Literal["en", "ar", "mixed"]


class CaseType(str, Enum):
    late_urgent_delivery = "late_urgent_delivery"
    delivered_not_received = "delivered_not_received"
    damaged_or_wrong_item = "damaged_or_wrong_item"
    return_pickup_delay = "return_pickup_delay"
    refund_timing = "refund_timing"
    stock_cancellation = "stock_cancellation"
    out_of_scope = "out_of_scope"
    unknown = "unknown"


class SLAStatus(str, Enum):
    on_track = "on_track"
    at_risk = "at_risk"
    breached = "breached"
    not_applicable = "not_applicable"
    unknown = "unknown"


class Urgency(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RecommendedAction(str, Enum):
    reassure_wait = "reassure_wait"
    courier_escalation = "courier_escalation"
    investigate_missing_delivery = "investigate_missing_delivery"
    exchange_or_replacement = "exchange_or_replacement"
    pickup_reschedule = "pickup_reschedule"
    refund_original = "refund_original"
    refund_wallet = "refund_wallet"
    stock_substitution = "stock_substitution"
    human_escalation = "human_escalation"
    deny_with_reason = "deny_with_reason"
    ask_for_missing_info = "ask_for_missing_info"
    refuse_medical_advice = "refuse_medical_advice"


class Citation(BaseModel):
    source: str = Field(min_length=1)
    source_url: str | None = None
    section: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)


class ResolutionTask(BaseModel):
    task_id: str = Field(min_length=1)
    owner_team: str = Field(min_length=1)
    action: RecommendedAction
    priority: Urgency
    problem_detected: str = Field(min_length=1)
    why_this_team: str = Field(min_length=1)
    root_cause_hypothesis: str = Field(min_length=1)
    backend_signal_to_check: str = Field(min_length=1)
    escalation_payload: list[str] = Field(min_length=1)
    next_steps: list[str] = Field(min_length=1)
    customer_promise_boundary: str = Field(min_length=1)
    success_metric: str = Field(min_length=1)

    @field_validator("next_steps", "escalation_payload")
    @classmethod
    def no_empty_steps(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("empty resolution steps are not allowed")
        return values


class TraceSpan(BaseModel):
    service: str = Field(min_length=1)
    span_name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    evidence: str = Field(min_length=1)


class PromiseTrace(BaseModel):
    order_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    customer_visible_symptom: str = Field(min_length=1)
    root_cause_summary: str = Field(min_length=1)
    broken_span: str = Field(min_length=1)
    missing_signals: list[str]
    instrumentation_gap: str = Field(min_length=1)
    operational_playbook: list[str] = Field(min_length=1)
    spans: list[TraceSpan] = Field(min_length=1)

    @field_validator("missing_signals", "operational_playbook")
    @classmethod
    def no_empty_trace_strings(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("empty trace strings are not allowed")
        return values


class OutcomeSignal(BaseModel):
    repeat_contact_within_72h: bool
    resolution_hours: float = Field(ge=0)
    csat: int | None = Field(default=None, ge=1, le=5)
    refund_completed: bool | None = None
    delivery_confirmed: bool | None = None


class OpsMemoryInsight(BaseModel):
    memory_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    similarity_score: float = Field(ge=0.0, le=1.0)
    pattern_summary: str = Field(min_length=1)
    prior_action: str = Field(min_length=1)
    resolution_outcome: Literal["resolved", "re_escalated", "churned", "pending"]
    outcome_signal: OutcomeSignal
    lesson: str = Field(min_length=1)
    recommended_playbook: list[str] = Field(min_length=1)
    semantic_reasoning: str = Field(min_length=1)

    @field_validator("recommended_playbook")
    @classmethod
    def no_empty_playbook_steps(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("empty memory playbook steps are not allowed")
        return values


class DecisionPacket(BaseModel):
    input_language: Language
    case_type: CaseType
    sla_status: SLAStatus
    urgency: Urgency
    recommended_actions: list[RecommendedAction]
    resolution_tasks: list[ResolutionTask]
    verified_facts: list[str]
    policy_citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
    human_review_required: bool
    uncertainty_flags: list[str]
    unsafe_promises_blocked: list[str]
    promise_trace: PromiseTrace | None = None
    ops_memory_insights: list[OpsMemoryInsight] = Field(default_factory=list)
    obsidian_case_note: str | None = None
    reply_en: str = Field(min_length=1)
    reply_ar: str = Field(min_length=1)
    tool_trace: list[str]

    @field_validator("verified_facts", "uncertainty_flags", "unsafe_promises_blocked", "tool_trace")
    @classmethod
    def no_empty_strings(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("empty strings are not allowed")
        return values

    @model_validator(mode="after")
    def validate_grounding(self) -> "DecisionPacket":
        case_value = self.case_type.value if isinstance(self.case_type, CaseType) else str(self.case_type)
        if case_value not in {CaseType.out_of_scope.value, CaseType.unknown.value} and not self.verified_facts:
            raise ValueError("in-scope decisions require verified facts")
        if self.confidence < 0.65 and not self.human_review_required:
            raise ValueError("low-confidence decisions must require human review")
        if case_value not in {CaseType.out_of_scope.value, CaseType.unknown.value} and not self.policy_citations:
            raise ValueError("in-scope decisions require at least one policy citation")
        if self.recommended_actions and not self.resolution_tasks:
            raise ValueError("recommended actions require resolution tasks")
        return self


class EvalExpected(BaseModel):
    case_type: CaseType
    sla_status: SLAStatus
    urgency: Urgency | None = None
    required_action: RecommendedAction | None = None
    human_review_required: bool | None = None
    must_block_promise: bool = False


class EvalCase(BaseModel):
    id: str
    message: str
    order_id: str | None = None
    notes: str
    expected: EvalExpected
