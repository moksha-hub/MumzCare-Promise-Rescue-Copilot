from __future__ import annotations

from datetime import timedelta

from mumzcare.llm import maybe_refine_replies
from mumzcare.schemas import CaseType, DecisionPacket, RecommendedAction, SLAStatus, Urgency
from mumzcare.tools import ORDER_RE, NOW, get_order, get_product, get_return, get_tracking, parse_dt, parse_order_id, search_policy


ARABIC_CHARS = set("ابتثجحخدذرزسشصضطظعغفقكلمنهويىةأإآؤئ")
MEDICAL_TERMS = {"fever", "rash", "breathing", "doctor", "medicine dose", "حرارة", "طفح", "تنفس", "طبيب", "جرعة"}
PROMISE_TERMS = {"promise", "guarantee", "guaranteed", "before 6", "by 6", "refund if late", "وعد", "اضمن"}
POLICY_ABUSE_TERMS = {"mark this as delivered", "claim warranty", "actually still in transit", "falsify", "fake"}
STATUS_AR = {
    "collected": "تم الاستلام",
    "pickup_requested": "تم طلب الاستلام",
    "unknown": "غير معروفة",
}
STATUS_EN = {
    "collected": "collected",
    "pickup_requested": "pickup requested",
    "unknown": "unknown",
}
ACTION_EN = {
    RecommendedAction.pickup_reschedule: "reschedule return pickup",
    RecommendedAction.reassure_wait: "reassure and monitor",
    RecommendedAction.human_escalation: "route to human review",
}
ACTION_AR = {
    RecommendedAction.pickup_reschedule: "إعادة جدولة استلام المرتجع",
    RecommendedAction.reassure_wait: "طمأنة العميل مع توضيح المدة المتوقعة",
    RecommendedAction.human_escalation: "تحويل الحالة لمراجعة بشرية",
}
PAYMENT_AR = {
    "card": "بطاقة بنكية",
    "cod": "الدفع عند الاستلام",
    "wallet": "محفظة ممزورلد",
    "mada": "مدى",
    "tabby": "تابي",
    "tamara": "تمارا",
}


def detect_language(message: str) -> str:
    normalized = ORDER_RE.sub("", message)
    ar_count = sum(1 for char in normalized if char in ARABIC_CHARS)
    en_count = sum(1 for char in normalized.lower() if "a" <= char <= "z")
    if ar_count and en_count:
        return "mixed"
    return "ar" if ar_count else "en"


def analyze_case(message: str, order_id: str | None = None) -> DecisionPacket:
    tool_trace: list[str] = []
    language = detect_language(message)
    lower = message.lower()

    if any(term in lower or term in message for term in MEDICAL_TERMS):
        packet = DecisionPacket(
            input_language=language,
            case_type=CaseType.out_of_scope,
            sla_status=SLAStatus.not_applicable,
            urgency=Urgency.critical,
            recommended_actions=[RecommendedAction.refuse_medical_advice, RecommendedAction.human_escalation],
            verified_facts=[],
            policy_citations=[],
            confidence=0.95,
            human_review_required=True,
            uncertainty_flags=["The message asks for medical or safety advice, which this support copilot cannot provide."],
            unsafe_promises_blocked=["Medical guidance was not provided."],
            reply_en="I cannot give medical advice. Please contact a doctor or emergency care if the baby may be at risk. I can still help an agent review the order or delivery issue separately.",
            reply_ar="لا يمكنني تقديم نصيحة طبية. إذا كان هناك أي خطر على الطفل، يرجى التواصل مع طبيب أو جهة طوارئ فورًا. يمكنني فقط مساعدة فريق الدعم في مراجعة مشكلة الطلب أو التوصيل بشكل منفصل.",
            tool_trace=["safety.medical_scope_check"],
        )
        return packet

    if any(term in lower for term in POLICY_ABUSE_TERMS):
        resolved_order_id = order_id or parse_order_id(message)
        facts = [f"Customer requested a status change that is not supported by verified delivery facts."]
        if resolved_order_id:
            facts.append(f"Referenced order is {resolved_order_id}.")
        packet = DecisionPacket(
            input_language=language,
            case_type=CaseType.out_of_scope,
            sla_status=SLAStatus.not_applicable,
            urgency=Urgency.low,
            recommended_actions=[RecommendedAction.deny_with_reason, RecommendedAction.human_escalation],
            verified_facts=facts,
            policy_citations=[],
            confidence=0.94,
            human_review_required=True,
            uncertainty_flags=["The requested action would falsify operational status and cannot be performed by the copilot."],
            unsafe_promises_blocked=["Delivery status was not changed or represented as delivered without verified carrier evidence."],
            reply_en="I cannot mark an in-transit order as delivered or help create an inaccurate warranty claim. I can help check the real tracking status and route the warranty question through the correct process once delivery is verified.",
            reply_ar="لا يمكنني تسجيل طلب ما زال قيد التوصيل على أنه تم تسليمه أو المساعدة في طلب ضمان بمعلومة غير دقيقة. يمكنني مراجعة حالة التتبع الفعلية وتحويل طلب الضمان عبر الإجراء الصحيح بعد تأكيد التسليم.",
            tool_trace=["safety.policy_abuse_check"],
        )
        return packet

    resolved_order_id = order_id or parse_order_id(message)
    if not resolved_order_id:
        return DecisionPacket(
            input_language=language,
            case_type=CaseType.unknown,
            sla_status=SLAStatus.unknown,
            urgency=Urgency.medium,
            recommended_actions=[RecommendedAction.ask_for_missing_info],
            verified_facts=[],
            policy_citations=[],
            confidence=0.5,
            human_review_required=True,
            uncertainty_flags=["Order ID is missing, so order, tracking, return, and payment facts cannot be verified."],
            unsafe_promises_blocked=[],
            reply_en="I need the order number before I can check delivery, return, or refund facts.",
            reply_ar="أحتاج إلى رقم الطلب أولًا حتى أتمكن من التحقق من معلومات التوصيل أو الإرجاع أو استرداد المبلغ.",
            tool_trace=["parse_order_id"],
        )

    order = get_order(resolved_order_id)
    tool_trace.append(f"get_order({resolved_order_id})")
    if not order:
        return DecisionPacket(
            input_language=language,
            case_type=CaseType.unknown,
            sla_status=SLAStatus.unknown,
            urgency=Urgency.medium,
            recommended_actions=[RecommendedAction.ask_for_missing_info],
            verified_facts=[],
            policy_citations=[],
            confidence=0.45,
            human_review_required=True,
            uncertainty_flags=[f"Order {resolved_order_id} was not found in the synthetic order dataset."],
            unsafe_promises_blocked=[],
            reply_en=f"I could not verify order {resolved_order_id}. Please confirm the order number before we promise a resolution.",
            reply_ar=f"لم أتمكن من التحقق من الطلب {resolved_order_id}. يرجى تأكيد رقم الطلب قبل تقديم أي وعد للعميل.",
            tool_trace=tool_trace,
        )

    tracking = get_tracking(resolved_order_id)
    returns = get_return(resolved_order_id)
    product = get_product(order["items"][0]["sku"])
    tool_trace.extend([f"get_tracking({resolved_order_id})", f"get_return({resolved_order_id})", f"get_product({order['items'][0]['sku']})"])

    case_type = classify_case(lower, message, order, tracking, returns)
    sla_status = compute_sla_status(case_type, order, tracking, returns)
    urgency = compute_urgency(case_type, sla_status, order, product, lower)
    actions = choose_actions(case_type, sla_status, order, returns, urgency)
    facts = build_facts(order, tracking, returns, product)
    query = policy_query(case_type, sla_status, order)
    citations = search_policy(query)
    tool_trace.append("search_policy(...)")
    uncertainty = uncertainty_flags(case_type, order, tracking, returns, citations)
    blocked = blocked_promises(message, tracking, returns, actions)
    confidence = confidence_score(case_type, order, tracking, returns, citations, uncertainty)
    human_review = (
        urgency in {Urgency.high, Urgency.critical}
        or RecommendedAction.human_escalation in actions
        or confidence < 0.75
        or bool(blocked)
    )
    reply_en, reply_ar = draft_replies(case_type, sla_status, actions, order, tracking, returns, product, uncertainty, language)

    packet = DecisionPacket(
        input_language=language,
        case_type=case_type,
        sla_status=sla_status,
        urgency=urgency,
        recommended_actions=actions,
        verified_facts=facts,
        policy_citations=citations,
        confidence=confidence,
        human_review_required=human_review,
        uncertainty_flags=uncertainty,
        unsafe_promises_blocked=blocked,
        reply_en=reply_en,
        reply_ar=reply_ar,
        tool_trace=tool_trace,
    )
    return maybe_refine_replies(packet)


def classify_case(lower: str, message: str, order: dict, tracking: dict | None, returns: dict | None) -> CaseType:
    promised = parse_dt(order["promised_delivery_at"])
    delivery_promise_request = any(word in lower for word in ["promise", "guarantee", "before 6", "by 6", "delivery", "late", "tracking"])
    if promised and promised < NOW and order["status"] != "delivered" and delivery_promise_request:
        return CaseType.late_urgent_delivery
    if order["status"] == "cancelled" or "stock" in lower or "cancel" in lower or "unavailable" in lower:
        return CaseType.stock_cancellation
    if any(word in lower for word in ["damaged", "broken", "wrong item", "defective"]) or any(word in message for word in ["تالف", "مكسور", "خاطئ", "غلط"]):
        return CaseType.damaged_or_wrong_item
    if (
        "delivered" in lower and any(word in lower for word in ["not received", "missing", "not arrived", "never got"])
        or any(word in lower for word in ["only got", "received only", "invoice says"])
        or "تم التوصيل" in message and ("ما وصل" in message or "لم يصل" in message)
    ):
        return CaseType.delivered_not_received
    if "refund" in lower or "استرداد" in message or "فلوسي" in message:
        return CaseType.refund_timing
    if "pickup" in lower or "return" in lower or "إرجاع" in message or "استلام المرتجع" in message:
        return CaseType.return_pickup_delay
    if any(word in lower for word in ["coming today", "out for delivery", "tracking", "delivery", "arrive", "late"]):
        return CaseType.late_urgent_delivery
    if promised and promised < NOW and order["status"] != "delivered":
        return CaseType.late_urgent_delivery
    if tracking and tracking.get("current_status") in {"stale_scan", "exception"}:
        return CaseType.late_urgent_delivery
    return CaseType.unknown


def compute_sla_status(case_type: CaseType, order: dict, tracking: dict | None, returns: dict | None) -> SLAStatus:
    promised = parse_dt(order["promised_delivery_at"])
    if case_type == CaseType.late_urgent_delivery and promised:
        if order["status"] != "delivered" and promised < NOW:
            return SLAStatus.breached
        if order["status"] != "delivered" and promised - NOW <= timedelta(hours=2):
            return SLAStatus.at_risk
        return SLAStatus.on_track
    if case_type == CaseType.return_pickup_delay and returns:
        requested = parse_dt(returns.get("pickup_requested_at"))
        if not requested:
            return SLAStatus.unknown
        elapsed_days = (NOW.date() - requested.date()).days
        limit = 5 if order["country"] == "KSA" else 3
        return SLAStatus.breached if elapsed_days > limit else SLAStatus.on_track
    if case_type == CaseType.refund_timing and returns:
        collected = parse_dt(returns.get("collected_at"))
        if not collected:
            return SLAStatus.unknown
        elapsed_days = (NOW.date() - collected.date()).days
        method = order["payment_method"]
        limit = {"wallet": 2, "cod": 2, "card": 7, "mada": 14, "tabby": 14, "tamara": 14}.get(method, 7)
        return SLAStatus.breached if elapsed_days > limit else SLAStatus.on_track
    if case_type in {CaseType.delivered_not_received, CaseType.damaged_or_wrong_item, CaseType.stock_cancellation}:
        return SLAStatus.not_applicable
    return SLAStatus.unknown


def compute_urgency(case_type: CaseType, sla_status: SLAStatus, order: dict, product: dict | None, lower: str) -> Urgency:
    urgent_product = bool(product and product.get("urgent_essential"))
    emotional_terms = any(word in lower for word in ["baby", "newborn", "urgent", "today", "formula", "milk"])
    if urgent_product and sla_status == SLAStatus.breached:
        return Urgency.critical
    if case_type in {CaseType.delivered_not_received, CaseType.stock_cancellation} and urgent_product:
        return Urgency.high
    if case_type == CaseType.damaged_or_wrong_item and urgent_product:
        return Urgency.high
    if emotional_terms:
        return Urgency.high
    if sla_status in {SLAStatus.breached, SLAStatus.at_risk}:
        return Urgency.high
    return Urgency.medium


def choose_actions(case_type: CaseType, sla_status: SLAStatus, order: dict, returns: dict | None, urgency: Urgency) -> list[RecommendedAction]:
    if case_type == CaseType.late_urgent_delivery:
        actions = [RecommendedAction.courier_escalation if sla_status == SLAStatus.breached else RecommendedAction.reassure_wait]
        if urgency in {Urgency.high, Urgency.critical}:
            actions.append(RecommendedAction.human_escalation)
        return actions
    if case_type == CaseType.delivered_not_received:
        return [RecommendedAction.investigate_missing_delivery, RecommendedAction.human_escalation]
    if case_type == CaseType.damaged_or_wrong_item:
        return [RecommendedAction.exchange_or_replacement, RecommendedAction.human_escalation]
    if case_type == CaseType.return_pickup_delay:
        return [RecommendedAction.pickup_reschedule, RecommendedAction.human_escalation] if sla_status == SLAStatus.breached else [RecommendedAction.reassure_wait]
    if case_type == CaseType.refund_timing:
        if order["payment_method"] == "cod":
            return [RecommendedAction.refund_wallet]
        return [RecommendedAction.human_escalation] if sla_status == SLAStatus.breached else [RecommendedAction.reassure_wait]
    if case_type == CaseType.stock_cancellation:
        return [RecommendedAction.stock_substitution, RecommendedAction.refund_original, RecommendedAction.human_escalation]
    return [RecommendedAction.ask_for_missing_info]


def build_facts(order: dict, tracking: dict | None, returns: dict | None, product: dict | None) -> list[str]:
    facts = [
        f"Order {order['order_id']} status is {order['status']}.",
        f"Promised delivery time is {order['promised_delivery_at']}.",
        f"Payment method is {order['payment_method']}.",
    ]
    if product:
        facts.append(f"Primary item is {product['name_en']} in category {product['category']}.")
    if tracking:
        facts.append(f"Tracking status is {tracking['current_status']} with last scan at {tracking.get('last_scan_at') or 'unknown'}.")
        facts.append(f"Carrier ETA is {tracking.get('eta') or 'unavailable'}.")
    if returns:
        facts.append(f"Return status is {returns['status']}.")
        if returns.get("collected_at"):
            facts.append(f"Return was collected at {returns['collected_at']}.")
        if returns.get("pickup_requested_at"):
            facts.append(f"Pickup was requested at {returns['pickup_requested_at']}.")
    return facts


def uncertainty_flags(case_type: CaseType, order: dict, tracking: dict | None, returns: dict | None, citations: list) -> list[str]:
    flags: list[str] = []
    if case_type == CaseType.late_urgent_delivery and (not tracking or not tracking.get("eta")):
        flags.append("Courier ETA is unavailable, so the copilot cannot promise an exact delivery time.")
    if case_type in {CaseType.return_pickup_delay, CaseType.refund_timing} and not returns:
        flags.append("No return/refund record is available for this order.")
    if not citations:
        flags.append("No matching policy citation was retrieved.")
    return flags


def blocked_promises(message: str, tracking: dict | None, returns: dict | None, actions: list[RecommendedAction]) -> list[str]:
    lower = message.lower()
    blocked: list[str] = []
    if any(term in lower or term in message for term in PROMISE_TERMS):
        if not tracking or not tracking.get("eta"):
            blocked.append("Exact delivery time was not promised because carrier ETA is unavailable.")
        if "refund" in lower and RecommendedAction.refund_original not in actions and RecommendedAction.refund_wallet not in actions:
            blocked.append("Refund approval was not promised because the verified facts do not authorize it.")
    return blocked


def confidence_score(case_type: CaseType, order: dict, tracking: dict | None, returns: dict | None, citations: list, uncertainty: list[str]) -> float:
    score = 0.9
    if case_type == CaseType.unknown:
        score -= 0.35
    if not tracking:
        score -= 0.1
    if case_type in {CaseType.return_pickup_delay, CaseType.refund_timing} and not returns:
        score -= 0.2
    if not citations:
        score -= 0.2
    score -= min(len(uncertainty) * 0.08, 0.24)
    return round(max(0.35, min(score, 0.95)), 2)


def policy_query(case_type: CaseType, sla_status: SLAStatus, order: dict) -> str:
    if case_type == CaseType.late_urgent_delivery:
        return f"same-day yalla delivery carrier ETA exact delivery time {order['country']} {sla_status.value}"
    if case_type == CaseType.delivered_not_received:
        return "delivered but not received delivery investigation replacement refund promise"
    if case_type == CaseType.damaged_or_wrong_item:
        return "damaged wrong missing defective item replacement exchange evidence review"
    if case_type == CaseType.return_pickup_delay:
        return f"return pickup window {order['country']} business days"
    if case_type == CaseType.refund_timing:
        return f"refund timing payment method {order['payment_method']} wallet card mada tabby tamara"
    if case_type == CaseType.stock_cancellation:
        return "stock cancellation unavailable item substitution original refund urgent baby essentials"
    return "customer communication safety missing facts human review"


def draft_replies(
    case_type: CaseType,
    sla_status: SLAStatus,
    actions: list[RecommendedAction],
    order: dict,
    tracking: dict | None,
    returns: dict | None,
    product: dict | None,
    uncertainty: list[str],
    language: str,
) -> tuple[str, str]:
    product_en = product["name_en"] if product else "your item"
    product_ar = product.get("name_ar", product_en) if product else "المنتج"
    eta = tracking.get("eta") if tracking else None
    sla_en = sla_status.value.replace("_", " ")
    sla_ar = {
        SLAStatus.on_track: "ضمن المدة المتوقعة",
        SLAStatus.at_risk: "معرضة للتأخير",
        SLAStatus.breached: "متجاوزة للموعد الموعود",
        SLAStatus.not_applicable: "غير منطبقة",
        SLAStatus.unknown: "غير مؤكدة",
    }[sla_status]
    if case_type == CaseType.late_urgent_delivery:
        en = (
            f"I checked order {order['order_id']} for {product_en}. The delivery promise is currently {sla_en}. "
            "I am escalating this to the delivery team for a verified update. I will not promise an exact time until the carrier confirms it."
        )
        ar = (
            f"راجعت الطلب {order['order_id']} الخاص بـ {product_ar}. حالة وعد التوصيل الآن {sla_ar}. "
            "سيتم تصعيد الطلب لفريق التوصيل للحصول على تحديث مؤكد، ولن نعد بوقت محدد قبل تأكيده من شركة الشحن."
        )
    elif case_type == CaseType.delivered_not_received:
        en = f"I can see order {order['order_id']} is marked delivered, but the customer reports it was not received. This needs delivery investigation before we make a replacement or refund promise."
        ar = f"يظهر أن الطلب {order['order_id']} مسجل كتم تسليمه، لكن العميل يذكر أنه لم يستلمه. يجب فتح تحقق مع التوصيل قبل الوعد باستبدال أو استرداد مبلغ."
    elif case_type == CaseType.damaged_or_wrong_item:
        en = f"I am sorry the {product_en} arrived damaged or incorrect. The safe next step is to review the return evidence and route this for replacement or exchange approval."
        ar = f"نعتذر لأن {product_ar} وصل تالفًا أو غير مطابق. الخطوة المناسبة هي مراجعة إثبات الحالة وتحويل الطلب لاعتماد الاستبدال أو التبديل."
    elif case_type == CaseType.return_pickup_delay:
        status_en = STATUS_EN.get(returns["status"] if returns else "unknown", "unknown")
        action_en = ACTION_EN.get(actions[0], actions[0].value.replace("_", " "))
        en = f"I checked the return pickup for order {order['order_id']}. The pickup status is {status_en}, so the next action is to {action_en}."
        status_ar = STATUS_AR.get(returns["status"] if returns else "unknown", "غير معروفة")
        action_ar = ACTION_AR.get(actions[0], "مراجعة الحالة واتخاذ الإجراء المناسب")
        ar = f"راجعت حالة استلام المرتجع للطلب {order['order_id']}. الحالة الحالية: {status_ar}، والخطوة التالية هي {action_ar}."
    elif case_type == CaseType.refund_timing:
        method = order["payment_method"]
        en = f"I checked the refund path for order {order['order_id']}. The payment method is {method}, so the reply should follow the verified refund window and avoid promising a faster manual refund."
        method_ar = PAYMENT_AR.get(method, method)
        ar = f"راجعت مسار استرداد المبلغ للطلب {order['order_id']}. طريقة الدفع هي {method_ar}، لذلك يجب الالتزام بمدة الاسترداد المؤكدة وعدم الوعد باسترداد أسرع من دون اعتماد."
    elif case_type == CaseType.stock_cancellation:
        en = f"Order {order['order_id']} was affected by stock availability. The safe options are to offer an approved substitute if available or route the case for refund handling."
        ar = f"تأثر الطلب {order['order_id']} بتوفر المخزون. الخيارات الآمنة هي عرض بديل معتمد إن وجد أو تحويل الحالة لمعالجة استرداد المبلغ."
    else:
        en = "I do not have enough verified information to decide. Please collect the missing order or policy facts and route this to human review."
        ar = "لا توجد معلومات مؤكدة كافية لاتخاذ قرار. يرجى جمع بيانات الطلب أو السياسة الناقصة وتحويل الحالة للمراجعة البشرية."
    return en, ar
