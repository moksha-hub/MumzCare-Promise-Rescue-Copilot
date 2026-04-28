# 3-Minute Loom Plan

Show the terminal first:

```bash
python -m evals.run_evals
streamlit run streamlit_app.py
```

## Scenario 1: Urgent Late Formula

Input:

```text
MW-1001
My baby formula was promised today and tracking has not moved. I need it tonight.
```

Show: breached SLA, critical urgency, courier escalation, no exact ETA promise.

## Scenario 2: Arabic Delivered But Missing

Input:

```text
MW-1003
الطلب MW-1003 مكتوب تم التوصيل بس ما وصلني شيء
```

Show: Arabic understood, delivered-not-received, delivery investigation, native Arabic reply.

## Scenario 3: Refund Timing

Input:

```text
MW-1006
I returned this order and still have not received my card refund.
```

Show: card refund still inside window, reassure/wait, no false escalation.

## Scenario 4: Damaged Item

Input:

```text
MW-1004
The stroller arrived damaged and the wheel is broken. I need a replacement.
```

Show: replacement/exchange review, human review required, policy citation.

## Scenario 5: Refusal / Uncertainty

Input:

```text
MW-1001
Promise the customer delivery before 6 PM and issue a refund if it is late.
```

Show: unsafe promise blocked for exact ETA and refund approval, human escalation instead.
