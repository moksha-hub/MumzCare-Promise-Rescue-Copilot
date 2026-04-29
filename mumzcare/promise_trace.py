from __future__ import annotations

from mumzcare import data_loader
from mumzcare.schemas import CaseType, PromiseTrace, SLAStatus


def analyze_promise_trace(order_id: str, case_type: CaseType, sla_status: SLAStatus) -> PromiseTrace | None:
    """Build an OpenTelemetry-style promise trace overlay for known synthetic orders.

    This is the unique layer on top of the support decision engine: it maps a
    customer complaint to the backend span or missing signal an operations team
    would need to resolve before making a promise.
    """
    raw = data_loader.promise_traces().get(order_id)
    if not raw:
        return None

    trace = PromiseTrace.model_validate(raw)
    if case_type == CaseType.late_urgent_delivery and sla_status == SLAStatus.breached:
        return trace
    if case_type in {
        CaseType.delivered_not_received,
        CaseType.return_pickup_delay,
        CaseType.refund_timing,
        CaseType.stock_cancellation,
    }:
        return trace
    return trace
