from __future__ import annotations

from mumzcare.tools import NOW, parse_dt


def build_order_journey(order: dict, tracking: dict | None, returns: dict | None, product: dict | None) -> list[dict[str, str]]:
    """Build a demo fulfillment timeline from the synthetic backend facts."""
    order_id = order["order_id"]
    product_name = product["name_en"] if product else order["items"][0]["sku"]
    qty = order["items"][0]["qty"]
    payment_method = order["payment_method"]
    status = order["status"]
    tracking_status = tracking.get("current_status") if tracking else None

    rows = [
        _row(
            "1. Order received",
            "done",
            order["created_at"],
            f"Order {order_id} was created for {qty} x {product_name}.",
            "Confirm the order ID and item the customer is asking about.",
        ),
        _row(
            "2. Payment check",
            "done",
            order["created_at"],
            f"Payment method is {payment_method}.",
            "Check whether refund path should be original method, wallet, or payment-provider window.",
        ),
    ]

    if status == "cancelled":
        rows.extend(
            [
                _row(
                    "3. Stock reservation",
                    "blocked",
                    order["created_at"],
                    "Stock could not be reserved or became unavailable before dispatch.",
                    "Offer approved substitution or route refund handling; do not imply dispatch happened.",
                ),
                _row(
                    "4. Pick and pack",
                    "not_started",
                    "not started",
                    "Order was cancelled before warehouse packing.",
                    "Avoid courier ETA promises because no courier handoff exists.",
                ),
                _row(
                    "5. Courier handoff",
                    "not_started",
                    "not started",
                    "No carrier handoff is available for this cancelled order.",
                    "Escalate urgent baby essentials for substitution or refund handling.",
                ),
            ]
        )
        return rows

    rows.extend(
        [
            _row(
                "3. Stock reservation",
                "done",
                order["created_at"],
                f"Primary SKU {order['items'][0]['sku']} is present in the order fixture.",
                "If the customer mentions cancellation or substitution, verify stock state before promising.",
            ),
            _row(
                "4. Pick and pack",
                "done" if tracking else "unknown",
                order["created_at"],
                "Warehouse processing is inferred from the available order/tracking state.",
                "A production tool would read warehouse scan events rather than infer this stage.",
            ),
            _row(
                "5. Courier handoff",
                "done" if tracking else "unknown",
                tracking.get("last_scan_at") if tracking else "unknown",
                f"Carrier is {tracking.get('carrier')}." if tracking else "No tracking record is available.",
                "If no tracking exists, avoid delivery-time promises and escalate for carrier lookup.",
            ),
        ]
    )

    delivery_status = _delivery_stage_status(status, tracking_status)
    rows.append(
        _row(
            "6. In transit / out for delivery",
            delivery_status,
            tracking.get("last_scan_at") if tracking else "unknown",
            _delivery_evidence(order, tracking),
            "Use carrier ETA only if present; otherwise give a verified-update escalation, not an exact time.",
        )
    )

    rows.append(
        _row(
            "7. Delivered / customer confirmation",
            "done" if status == "delivered" else "pending",
            tracking.get("last_scan_at") if tracking and tracking_status == "delivered" else order["promised_delivery_at"],
            _delivered_evidence(order, tracking),
            "If customer says delivered-but-not-received, open investigation before refund/replacement promises.",
        )
    )

    if returns:
        rows.extend(
            [
                _row(
                    "8. Return pickup",
                    "done" if returns["status"] == "collected" else "pending",
                    returns.get("pickup_requested_at") or "unknown",
                    f"Return status is {returns['status']}.",
                    "Check pickup window by market before rescheduling or escalating.",
                ),
                _row(
                    "9. Refund review",
                    "pending" if returns["status"] == "collected" else "not_started",
                    returns.get("collected_at") or "not collected",
                    f"Refund timing depends on {payment_method} after collection and review.",
                    "Do not promise manual acceleration unless a refund tool authorizes it.",
                ),
            ]
        )

    return rows


def _row(stage: str, status: str, timestamp: str, evidence: str, support_check: str) -> dict[str, str]:
    return {
        "Stage": stage,
        "Status": status,
        "Timestamp": timestamp,
        "Verified evidence": evidence,
        "Support check": support_check,
    }


def _delivery_stage_status(order_status: str, tracking_status: str | None) -> str:
    if tracking_status == "delivered" or order_status == "delivered":
        return "done"
    if tracking_status in {"out_for_delivery", "in_transit"}:
        return "active"
    if tracking_status in {"stale_scan", "exception"}:
        return "at_risk"
    return "unknown"


def _delivery_evidence(order: dict, tracking: dict | None) -> str:
    if not tracking:
        return "No carrier tracking record is available."
    eta = tracking.get("eta") or "unavailable"
    promised = parse_dt(order["promised_delivery_at"])
    breach = promised is not None and promised < NOW and order["status"] != "delivered"
    breach_text = " Delivery promise is breached." if breach else ""
    return f"Tracking is {tracking['current_status']}; last scan {tracking.get('last_scan_at') or 'unknown'}; carrier ETA {eta}.{breach_text}"


def _delivered_evidence(order: dict, tracking: dict | None) -> str:
    if order["status"] == "delivered":
        scan = tracking.get("last_scan_at") if tracking else "unknown"
        return f"Order status is delivered; delivery scan time is {scan}."
    return f"Order status is {order['status']}; promised delivery time is {order['promised_delivery_at']}."
