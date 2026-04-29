# MumzCare Promise Rescue Copilot

Track: A - AI Engineering Intern

## Summary

MumzCare is an internal support and operations copilot for urgent Mumzworld post-order issues: late baby essentials, delivered-but-missing orders, damaged or wrong items, return pickup delays, refund timing confusion, and stock cancellations.

Given a customer message and an order ID, it verifies synthetic order facts, retrieves policy citations, traces where the promise broke, checks outcome-aware Ops Memory, builds an internal recovery plan, blocks unsafe promises, generates an Obsidian-compatible case note, and drafts safe English and Arabic replies.

The core question is:

```text
Have we seen this failure pattern before, and did our response actually fix it?
```

This is not a customer chatbot, a translation wrapper, or a status page. It is a company-side decision tool for support agents who need to know what happened, what is verified, who should act next, what not to promise, and what can safely be sent to the customer.

## Why This Problem

Mumzworld operates in a high-trust category. If baby formula, diapers, a stroller, a return pickup, or a refund goes wrong, the support reply must be accurate and careful. The risky part is not only the delay itself. The risky part is a weak recovery flow:

- promising an ETA when the carrier has not confirmed one
- approving a refund before the payment/return state supports it
- giving generic apologies instead of a real escalation payload
- routing the ticket to the wrong internal team
- answering Arabic as if it were a literal English translation
- repeating the same failed playbook because past outcomes were not reused

This prototype makes no assumption about Mumzworld's internal support tools. It proposes an AI layer that could sit above existing order, tracking, return, payment, helpdesk, and observability systems.

## Why Obsidian Matters

The strongest add-on is the Obsidian-style Ops Memory layer.

A normal ticket system closes tickets one by one. Obsidian-style linked Markdown turns each resolved case into reusable institutional memory. Each case note can link to an owner team, courier, zone, product category, case type, similar memory record, and outcome.

Example generated links:

```text
[[Teams/Courier Ops]]
[[Memory/MEM-002]]
case/late_urgent_delivery
urgency/critical
resolution_outcome: pending
```

That creates a support knowledge graph. Over time, patterns become visible:

- formula + stale scan + missing ETA repeatedly re-escalates
- delivered-not-received cases resolve faster when proof-of-delivery is checked first
- damaged stroller cases fail when replacement is promised before evidence and stock review
- a courier/zone combination may need vendor-performance review rather than standard escalation

The prototype currently generates the Obsidian-compatible Markdown note locally. In a real system, reviewed notes could sync to an internal Obsidian vault, Git-backed Markdown repo, or knowledge base. The note includes a `resolution_outcome` field because memory is only useful if the system learns whether the recommended response actually worked.

## What It Does

For each case, MumzCare returns a validated `DecisionPacket`:

| Field | Purpose |
|---|---|
| `input_language` | Detects English, Arabic, or mixed input |
| `case_type` | Late delivery, delivered-not-received, damaged/wrong item, return pickup delay, refund timing, stock cancellation, unknown, or out of scope |
| `sla_status` | On track, at risk, breached, not applicable, or unknown |
| `urgency` | Low, medium, high, or critical |
| `recommended_actions` | Controlled actions such as courier escalation, pickup reschedule, refund routing, replacement review, or human escalation |
| `resolution_tasks` | Internal task cards with owner team, root-cause hypothesis, backend signal to check, escalation payload, next steps, promise boundary, and success metric |
| `promise_trace` | Synthetic OpenTelemetry-style trace showing broken span, missing signals, instrumentation gap, and operations playbook |
| `ops_memory_insights` | Similar synthetic historical cases with outcome, prior action, lesson, similarity score, and recommended playbook |
| `obsidian_case_note` | Auto-generated Markdown note with frontmatter, links, verified facts, blocked promises, memory matches, and closure outcome fields |
| `verified_facts` | Facts from order, tracking, return, and product tools only |
| `policy_citations` | Retrieved policy sections with source URL and score |
| `confidence` | Bounded 0 to 1 score degraded by missing data and uncertainty |
| `human_review_required` | True when urgency, uncertainty, blocked promises, or confidence require a human |
| `uncertainty_flags` | What the system could not verify |
| `unsafe_promises_blocked` | ETA/refund/replacement/medical promises the copilot refused |
| `reply_en`, `reply_ar` | Safe bilingual customer reply drafts |
| `tool_trace` | Ordered audit trail of lookups and checks |

## Setup And Run

The project runs without paid keys.

Windows PowerShell:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m evals.run_evals
python -m mumzcare.cli analyze --order-id MW-1001 --message "My baby formula was promised today and tracking has not moved."
streamlit run streamlit_app.py
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m evals.run_evals
python -m mumzcare.cli analyze --order-id MW-1001 --message "My baby formula was promised today and tracking has not moved."
streamlit run streamlit_app.py
```

Optional OpenRouter use:

```bash
cp .env.example .env          # Windows: copy .env.example .env
# Set OPENROUTER_API_KEY=your_key
# Optional: USE_LLM_DRAFTS=true for reply tone refinement
# Optional: USE_LLM_MEMORY=true for one-sentence semantic memory reasoning
```

The default optional model is `poolside/laguna-xs.2:free`, configurable through `OPENROUTER_MODEL`.

## Architecture

```text
Customer message + order ID
  -> safety gates: blank input, medical advice, policy abuse, missing order
  -> tool lookups: order, tracking, return, product
  -> TF-IDF RAG over compact policy docs
  -> synthetic promise trace over OpenTelemetry-style spans
  -> outcome-aware fuzzy Ops Memory over synthetic case notes
  -> deterministic decision engine
  -> unsafe-promise blocking
  -> Pydantic DecisionPacket validation
  -> Obsidian-style case note generation
  -> optional OpenRouter refinement
  -> Streamlit UI / CLI / JSON output
```

Key design choice: the model is not the source of operational truth. Order facts, tracking state, return state, policy citations, and unsafe promise checks come from deterministic tools and schema validation. Optional LLM calls can improve wording or summarize memory reasoning, but they cannot approve refunds, invent ETAs, change facts, or bypass validation.

All operational data is synthetic:

- `data/orders.json`
- `data/tracking_events.json`
- `data/returns.json`
- `data/products.json`
- `data/promise_traces.json`
- `data/memory_cases.json`
- `data/policy_docs.md`

No retailer product-page scraping, catalog scraping, customer data, real order data, or real telemetry is used.

Time-sensitive evals use a fixed clock in `mumzcare/tools.py`: `2026-04-27 21:15` in `Asia/Dubai`. This keeps delivery, return pickup, and refund-window results reproducible.

## UI Demo Surface

The Streamlit app is an internal support workspace.

| Area | What to show |
|---|---|
| Triage summary | Case type, SLA, urgency, confidence, input language |
| Resolution plan | Internal owner, root cause, escalation payload, next steps, success metric |
| Ops memory | Similar past cases, outcome, prior action, lesson, playbook |
| Promise trace | Broken span, missing backend signals, instrumentation gap |
| Evidence | Verified facts, policy citations, order journey, tool trace |
| Reply draft | English and Arabic replies, separated from internal details |
| Audit JSON | Full validated packet |

Demo data uses synthetic orders `MW-1001` through `MW-1010`. Custom messages work against those orders. External order IDs return an explicit unknown-order response. Blank messages are blocked before analysis.

## Arabic Quality

Arabic is not treated as literal translation. The system uses separate Arabic templates, Arabic product names, Arabic labels for payment/status/action, and RTL rendering in the UI.

Modern Standard Arabic was chosen because Mumzworld serves multiple GCC markets. Production work should add native Arabic QA, KSA/UAE tone variants, and Arabic-specific retrieval tests.

## Uncertainty And Safety

The system is conservative by design.

Hard rules:

- unknown order ID: ask for the order number, do not invent facts
- missing carrier ETA: do not promise an exact delivery time
- unsupported refund: do not approve it
- damaged/replacement case: do not promise replacement before evidence and stock review
- no policy citation: do not claim policy support
- medical/safety advice: refuse and escalate
- low confidence: require human review
- malformed structured output: fail validation instead of silently passing

Schema guardrails:

- in-scope cases require verified facts
- in-scope cases require at least one policy citation
- `out_of_scope` and `unknown` can omit citations because they should not attach irrelevant policy
- `confidence < 0.65` forces `human_review_required`
- list fields reject empty strings
- confidence and citation scores are bounded from 0 to 1

Ops Memory is advisory. It can suggest that a prior playbook worked or failed, but current verified facts, policy citations, safety gates, and human review always win.

## Evals

Run:

```bash
python -m evals.run_evals
```

Latest verified result:

```text
case_count: 16
average_score: 1.0
pass_rate: 1.0
refusal_case_pass_rate: 1.0
```

The 16 cases include:

- easy cases: late formula delivery, on-track delivery, card refund inside window
- operations cases: delivered-not-received, damaged stroller, return pickup overdue, stock cancellation
- multilingual cases: Arabic delivered-not-received, mixed EN/AR partial delivery
- adversarial cases: promise delivery by 6 PM and refund if late, policy-abuse request
- uncertainty/refusal cases: missing order ID, unknown order, medical advice refusal

Rubric:

| Metric | Weight |
|---|---:|
| Case classification | 15% |
| SLA status | 12% |
| Urgency | 12% |
| Recommended action | 15% |
| Human review behavior | 10% |
| Unsafe-promise/refusal behavior | 10% |
| Schema validity | 5% |
| Citation grounding | 5% |
| Outcome-aware Ops Memory | 4% |
| Obsidian note presence | 4% |
| Bilingual output presence | 4% |
| Reply safety | 3% |
| Static Arabic quality | 1% |

Critical safety failures cap the score at 0.60, including medical advice, failing to block unsupported promises, malformed output, claiming policy support without citation, or leaking broken Arabic/mojibake.

Honest residual risks:

- classifier is rule-based and can miss indirect, slang-heavy, typo-heavy, or unusual Arabic phrasing
- TF-IDF policy retrieval is explainable but weaker than embeddings for semantic synonyms
- urgency thresholds are hand-calibrated and should be tuned with real support severity labels
- Ops Memory uses synthetic historical cases; production would need solved-ticket outcomes and repeat-contact signals

## Tradeoffs

Why this problem:

Promise rescue is high-leverage because urgent baby/mother orders combine customer emotion, operational constraints, policy rules, and safety risk. It is narrow enough to ship in a take-home, but still tests real AI engineering judgment.

What I rejected:

- Gift finder: useful but lower operational urgency
- PDP content generator: easier to make look good with prose, less tied to trust recovery
- Review summarizer: valuable, but less direct operational action
- Full customer-service chatbot: too broad and harder to evaluate safely in 5 hours
- Duplicate catalog detector: high internal value, but hard to defend without real catalog data

Architecture choice:

- deterministic tools for facts
- TF-IDF RAG for policy grounding
- synthetic promise trace for backend signal reasoning
- fuzzy Ops Memory for outcome-aware precedent
- Pydantic for structured output validation
- optional OpenRouter for wording/memory reasoning only
- Streamlit for a simple, inspectable UI

What I cut:

- real backend/courier/refund integrations
- live OpenTelemetry collector
- real solved-ticket ingestion
- real Obsidian vault sync
- image evidence for damaged products
- fine-tuning
- vector database/reranker
- model-as-judge evals

What I would build next:

- connect to real order, tracking, return, refund, helpdesk, and observability APIs
- replace rule-based classification with semantic intent routing
- replace TF-IDF with embeddings or hybrid retrieval
- sync reviewed notes into an Obsidian-compatible vault or internal knowledge base
- ingest outcomes: repeat contact, delivery confirmation, refund completion, CSAT, agent override
- add agent accept/edit/reject workflow
- tune urgency and confidence against real historical tickets
- add native Arabic review and region-specific tone presets

## Tooling And Provenance

This section is intentionally explicit because tooling transparency is part of the grading rubric.

Runtime tools:

| Tool | Used for |
|---|---|
| Python | Core application, CLI, evals |
| Pydantic | Validated structured output contract |
| scikit-learn `TfidfVectorizer` | Local TF-IDF policy retrieval and fuzzy memory scoring |
| Streamlit | One-page internal support workspace |
| Pytest | Unit/smoke tests |
| OpenRouter | Optional reply refinement and optional memory reasoning |

Runtime model usage:

- Default path: no external LLM call. The app runs locally and deterministically.
- Optional reply refinement: `USE_LLM_DRAFTS=true` lets OpenRouter rewrite `reply_en` and `reply_ar` for tone only.
- Optional memory reasoning: `USE_LLM_MEMORY=true` lets OpenRouter explain why already-retrieved memory candidates are semantically similar.
- Default optional model: `poolside/laguna-xs.2:free`, configurable with `OPENROUTER_MODEL`.
- Safety boundary: optional LLM output is discarded if it changes structure, misses expected markers, returns empty text, or fails Pydantic validation. Unsafe-promise cases skip reply refinement entirely.

AI assistance used during development:

- Codex/GPT-5 was used as a pair-programming and review assistant for implementation, debugging, documentation, and eval design.
- AI-assisted review passes challenged problem framing, Arabic quality, UI clarity, eval coverage, and documentation completeness.
- I kept deterministic tools, schema validation, and evals as the source of truth rather than trusting generated prose.

Where I overruled AI suggestions:

- kept the scope focused instead of building a broad chatbot
- avoided LangChain/LlamaIndex-style framework weight for a 5-hour prototype
- kept OpenRouter optional so the repo runs without paid keys
- kept memory advisory so it cannot override policy or verified facts
- separated internal resolution details from customer reply drafts
- added Arabic static checks after identifying that "Arabic quality" should be tested, not only claimed
- avoided claims about Mumzworld's internal systems because this repo uses public policy context and synthetic operational data only

Material prompt:

The optional reply-refinement prompt is committed in `prompts/system_prompt.md`. Its key rule is:

```text
Rewrite without changing facts or promises. Do not add compensation, ETA, refund approval, policy claims, Ops Memory claims, or internal case-note details.
```

## Time Log

Base 5-hour scope:

| Phase | Time | Work |
|---|---:|---|
| Scoping | 0:00-0:45 | Chose promise rescue and narrowed the problem |
| Data + tools | 0:45-1:45 | Built schemas, synthetic fixtures, policy notes, deterministic tools |
| Engine | 1:45-2:45 | Added RAG, decision logic, bilingual replies, safety checks |
| Evals + UI | 2:45-4:00 | Added eval runner, 16 cases, unit tests, Streamlit UI, CLI |
| Docs | 4:00-5:00 | Wrote README, eval notes, tradeoffs, and Loom script |

Extra refinement after the base scope: Promise Trace, outcome-aware Ops Memory, Obsidian case notes, UI polish, and documentation cleanup. I would disclose this overage because it made the prototype more differentiated and easier to evaluate.

## Loom

Video: [MumzCare Promise Rescue Copilot walkthrough](https://www.loom.com/share/5ec18ddb8e2a40b1a7b54784799067fc)

The Loom covers five inputs end to end:

1. `MW-1001` late formula delivery
2. `MW-1003` Arabic delivered-but-missing
3. `MW-1006` card refund timing
4. `MW-1004` damaged stroller
5. `MW-1001` unsafe ETA/refund promise refusal
