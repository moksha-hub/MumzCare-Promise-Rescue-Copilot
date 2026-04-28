# 3-Minute Loom Plan

Goal: show that the prototype is grounded, bilingual, schema-validated, and conservative about uncertainty. Do not scroll through every raw JSON field. Open raw JSON once only to prove structured validation.

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

Show: breached SLA, critical urgency, courier escalation, verified facts, strongest policy citation, and no exact ETA promise.

## Scenario 2: Arabic Delivered But Missing

Input:

```text
MW-1003
الطلب MW-1003 مكتوب تم التوصيل بس ما وصلني شيء
```

Show: `input_language: ar`, delivered-not-received, delivery investigation, Arabic reply displayed RTL, and English reply still available.

## Scenario 3: Refund Timing

Input:

```text
MW-1006
I returned this order and still have not received my card refund.
```

Show: card refund still inside window, reassure/wait, policy citation, and no false escalation.

## Scenario 4: Damaged Item

Input:

```text
MW-1004
The stroller arrived damaged and the wheel is broken. I need a replacement.
```

Show: replacement/exchange review, human review required, policy citation, and bilingual reply.

## Scenario 5: Refusal / Uncertainty

Input:

```text
MW-1001
Promise the customer delivery before 6 PM and issue a refund if it is late.
```

Show: unsafe promise blocked for exact ETA and refund approval, human escalation instead. This is the required refusal/uncertainty example.

Optional backup if there is time: run `I need help with my refund.` without an order ID to show the `unknown` path. It should ask for the order number, set low confidence, and avoid inventing refund facts.
