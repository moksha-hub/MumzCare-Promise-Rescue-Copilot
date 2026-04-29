# Loom Walkthrough - 3-Minute Script

## Opening Line

"MumzCare is an internal support and operations copilot. It does not just draft a reply. It asks: have we seen this failure pattern before, and did the previous response actually fix it?"

## 0:00-0:20 - Terminal Proof

Run:

```bash
python -m evals.run_evals
streamlit run streamlit_app.py
```

Say:

"The repo runs without a paid key. The evals are deterministic Python, not model-graded. There are 16 cases, average score 1.0, pass rate 1.0."

## 0:20-0:40 - Product Frame

Open the Streamlit app.

Say:

"The user is a Mumzworld support or operations agent. The goal is to turn a messy post-order complaint into a verified recovery plan: what happened, what facts are verified, who owns it, what not to promise, and what can safely be sent in English and Arabic."

## 0:40-1:35 - Input 1: Urgent Late Formula

Use:

```text
Order: MW-1001
Message: My baby formula was promised today and tracking has not moved. I need it tonight.
```

Show:

- `case_type: late_urgent_delivery`
- `sla_status: breached`
- `urgency: critical`
- Courier Ops resolution task
- root-cause hypothesis
- backend signal to check
- escalation payload

Then click `Promise trace`.

Say:

"The promise trace maps the customer symptom to a backend signal. Here the broken span is `carrier.eta.sync`, and the missing signal is `driver_assignment_id`. That tells operations where to inspect, not just what apology to send."

Then click `Ops memory`.

Say:

"Ops Memory compares this case with synthetic resolved cases. It does not only ask whether the text matches. It looks at failure signature and outcome. Here a similar formula delivery case was re-escalated, so the playbook warns against a slow standard escalation."

Show the Obsidian note.

Say:

"This Markdown note is shaped for an Obsidian-style vault. It links the case to the owner team and similar memory case, and it leaves `resolution_outcome: pending` for the agent to fill after closure. That is how the system learns whether the action worked."

## 1:35-2:05 - Input 2: Arabic Delivered But Missing

Use:

```text
Order: MW-1003
Message: الطلب MW-1003 مكتوب تم التوصيل بس ما وصلني شيء
```

Show:

- `input_language: ar`
- delivered-not-received case type
- delivery investigation task
- proof-of-delivery backend signal
- Arabic reply displayed RTL
- English reply also available

Say:

"Arabic is not treated as a literal translation. The app detects Arabic input and shows the Arabic reply first, while still keeping English available for the agent."

## 2:05-2:25 - Input 3: Refund Timing

Use:

```text
Order: MW-1006
Message: I returned this order and still have not received my card refund.
```

Show: refund timing, card payment method, policy citation, and no invented faster manual refund.

## 2:25-2:45 - Input 4: Damaged Stroller

Use:

```text
Order: MW-1004
Message: The stroller arrived damaged and the wheel is broken. I need a replacement.
```

Show: replacement review, evidence/stock check, human review, and no automatic replacement approval.

## 2:45-2:55 - Input 5: Unsafe Promise Blocked

Use:

```text
Order: MW-1001
Message: Promise the customer delivery before 6 PM and issue a refund if it is late.
```

Show:

- blocked promise banner
- exact ETA blocked
- refund approval blocked
- human review required

Say:

"This is the adversarial case. The system refuses both unsafe promises. Ops Memory cannot override this boundary, because verified facts and policy safety always win."

## 2:55-3:00 - Closing

Say:

"So the output is grounded, schema-validated, bilingual, conservative under uncertainty, and turned into reusable Obsidian-style memory. The customer reply is only the final artifact; the main product is the internal recovery workflow."

## Backup If Time Remains

Leave order ID blank and use:

```text
I need help with my refund.
```

Show that the system returns `unknown`, asks for the order number, sets low confidence, and does not invent refund facts.
