# MumzCare Promise Rescue Copilot

Track: A - AI Engineering Intern

## Summary

MumzCare Promise Rescue Copilot is an internal support/ops prototype for Mumzworld agents handling urgent post-purchase issues: late baby essentials, delivered-but-missing orders, damaged or wrong items, return pickup delays, refund timing confusion, and stock cancellations. Given a customer message plus an order ID, it verifies facts from synthetic order/tracking/return tools, retrieves relevant policy snippets, returns a Pydantic-validated rescue plan, blocks unsupported promises, and drafts English and Arabic replies.

The product thesis is simple: Mumzworld already promises speed. The high-leverage AI problem is recovering trust when that promise breaks.

## Why This Pain Point

Mumzworld's public experience depends on fast delivery, easy returns, refund clarity, and support trust. Public policy pages describe same-day or near-term delivery promises, return pickup windows, and refund timing by payment method. Public reviews show that when something goes wrong, the painful part is often not only the delay; it is vague recovery, unclear refund timing, or a reply that does not match the customer's actual situation.

I chose this over a gift finder, PDP generator, review summarizer, or broad chatbot because promise recovery has sharper failure modes: hallucinated ETA, unsupported refund approval, unsafe medical advice, poor Arabic, and generic apologies. Those are exactly the behaviors Track A asks us to detect and evaluate.

## What It Does

For each support case, the copilot returns:

- `case_type`: late delivery, delivered-not-received, damaged/wrong item, return pickup delay, refund timing, stock cancellation, unknown, or out of scope
- `sla_status`: on track, at risk, breached, not applicable, or unknown
- `urgency`: low, medium, high, or critical
- `recommended_actions`: controlled enum actions such as courier escalation, pickup reschedule, refund wallet, replacement review, or human escalation
- `verified_facts`: facts from order, tracking, return, and product tools
- `policy_citations`: retrieved policy snippets with source section and score
- `confidence`, `human_review_required`, `uncertainty_flags`, and `unsafe_promises_blocked`
- `reply_en` and `reply_ar`

The LLM is optional. The default path is deterministic and fully runnable without an API key. If `USE_LLM_DRAFTS=true` and `OPENROUTER_API_KEY` is set, OpenRouter can refine the replies without changing facts.

Important distinction: the project was built and audited with AI coding assistance, documented below. The default runtime prototype does not call an LLM or paid API. That was an intentional scope choice so reviewers can run and evaluate the submission without keys, rate limits, or provider variability.

## Setup

Windows PowerShell:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m evals.run_evals
python -m mumzcare.cli analyze --order-id MW-1001 --message "My baby formula was promised today and tracking has not moved."
streamlit run streamlit_app.py
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m evals.run_evals
python -m mumzcare.cli analyze --order-id MW-1001 --message "My baby formula was promised today and tracking has not moved."
streamlit run streamlit_app.py
```

The repo runs without paid keys. Optional model drafting:

Windows PowerShell:

```bash
copy .env.example .env
# set OPENROUTER_API_KEY and USE_LLM_DRAFTS=true
```

macOS/Linux:

```bash
cp .env.example .env
# set OPENROUTER_API_KEY and USE_LLM_DRAFTS=true
```

## Architecture

```text
Customer message + order_id
  -> language / safety / order parsing
  -> tools: order, tracking, return, product
  -> TF-IDF RAG over compact policy docs
  -> deterministic decision engine + optional LLM reply refinement
  -> Pydantic DecisionPacket validation
  -> safety checks: no fake ETA, no fake refund, no fake policy
  -> EN/AR replies + JSON packet + tool trace
```

Key design choice: the model is not the source of operational truth. Order facts, tracking state, return state, policy citations, and unsafe promise checks come from code-level tools and validation.

For a fuller explanation of each component and workflow, see `ARCHITECTURE.md`.

Editable architecture diagram: `diagrams/mumzcare_architecture.drawio`.

Deterministic timing note: `mumzcare/tools.py` fixes `NOW` at `2026-04-27 21:15` in the `Asia/Dubai` timezone. That is deliberate for this take-home so SLA, return-pickup, and refund-window evals are reproducible on any reviewer machine.

## Demo Surface

The Streamlit app keeps the agent-facing decision simple:

- Top line: case type, SLA status, urgency, confidence, detected input language.
- Main answer: recommended actions plus the English/Arabic reply drafts.
- Grounding: verified facts and the strongest policy citation.
- Audit evidence: full citations, tool trace, and raw validated JSON are available in expanders.

This is intentional. A support agent should not have to read a debug dump, but a reviewer can still inspect how the answer was grounded. `tool_trace` is an audit artifact: it shows which lookup tools were actually called before the recommendation was produced.

## Arabic Quality Strategy

Arabic is not generated as a literal translation of English. The prompt and templates ask for clear Modern Standard Arabic suitable for UAE/GCC ecommerce support. The Arabic reply must preserve verified facts, avoid adding compensation or ETA, and keep a warm but direct customer-care tone.

I chose MSA over dialect-specific Arabic because Mumzworld serves multiple GCC markets and the prototype needs consistency. A production version should add native-speaker review, regional tone presets, and regression tests for Arabic wording.

## Uncertainty Handling

The system is intentionally conservative. It returns `unknown`, `null`-like missing facts, or `human_review_required: true` when facts are not supported.

Hard rules:

- Unknown order ID: ask for the order ID, do not invent facts.
- Missing carrier ETA: do not promise an exact delivery time.
- Refund unsupported by payment/return state: do not approve it.
- No policy citation: do not claim policy support.
- Medical/safety advice: refuse and escalate.
- Low confidence: require human review.
- Malformed output: fail validation instead of silently passing.

The product principle is promise safety: it is better to say "I do not know yet" than to invent a delivery time, refund approval, or policy exception.

## Quality Guardrails

The assignment calls out several failure modes. This prototype treats them as explicit guardrails:

- Inventing facts not in the input: all operational facts come from `get_order`, `get_tracking`, `get_return`, and `get_product`; the final packet exposes `verified_facts` and `tool_trace`.
- Hiding uncertainty: missing order IDs, unknown orders, missing carrier ETA, missing return records, and low-confidence cases populate `uncertainty_flags` and require human review.
- Padding with generic claims: replies mention the verified order, product, status, payment method, or missing fact instead of generic apology-only text.
- Literal Arabic translation: Arabic copy uses separate templates, Arabic product names, Arabic status/action/payment labels, and RTL UI rendering. Evals check for Arabic script, mojibake, and raw enum leakage.
- Malformed JSON or empty-string fields: Pydantic validates the `DecisionPacket`; in-scope decisions require facts and citations, and list fields reject empty strings.
- Confident out-of-scope answers: medical advice and policy-abuse requests return `out_of_scope`, refusal actions, blocked-promise notes, and human escalation.

Schema guardrails in `DecisionPacket`:

- `reply_en` and `reply_ar` are required non-empty strings.
- `confidence` and citation scores are bounded from `0.0` to `1.0`.
- In-scope cases require `verified_facts`.
- In-scope cases require at least one `policy_citation`.
- `out_of_scope` and `unknown` cases are intentionally allowed to have no citations because medical refusals, policy-abuse refusals, and missing-order cases should not pretend to cite an irrelevant policy.
- If `confidence < 0.65`, `human_review_required` must be true.
- List fields such as `verified_facts`, `uncertainty_flags`, `unsafe_promises_blocked`, and `tool_trace` reject empty strings.

## Tradeoffs

Why this problem: I chose promise rescue because it is a real support pain point with concrete failure modes: broken delivery promises, missing items, delayed refunds, unclear return pickup, and unsafe agent replies. It is narrower and more testable than a full chatbot, but still valuable for customer trust and support operations.

What I rejected: a gift finder, PDP generator, review summarizer, duplicate catalog detector, and full support chatbot. The first three are easier to fake with polished prose. Duplicate detection is valuable but hard to defend without real catalog data. A chatbot is too broad for a 5-hour prototype and harder to evaluate safely.

Model and architecture choice: the default system is deterministic and local because reviewers should be able to run it without paid keys. RAG provides policy grounding, Pydantic validates structure, rule-based tools verify order facts, and optional OpenRouter refinement can improve wording only after the packet is already valid.

What I cut: live backend integrations, courier APIs, real refund actions, image evidence for damaged items, fine-tuning, vector databases, and model-graded evals.

What I would build next: real API adapters, embedding retrieval, policy versioning, native Arabic QA, support-agent accept/edit/reject feedback, and severity calibration from historical tickets.

## Evals

Run:

```bash
python -m evals.run_evals
```

Current result:

- 16 test cases
- Average score: 1.0
- Pass rate: 1.0
- Refusal/unsafe-promise pass rate: 1.0

The eval set includes easy, adversarial, Arabic, mixed EN/AR, missing-order, refund-window, return-pickup, stock cancellation, delivered-not-received, policy-abuse, and medical out-of-scope cases. It also checks bilingual output presence, reply safety, and static Arabic quality issues such as mojibake or raw enum leakage.

Evals and unit tests are separate on purpose. Evals are product-behavior benchmarks: they check whether the copilot makes the right support decision across realistic and adversarial scenarios. Unit tests are logic checks: they cover language detection, SLA calculation, confidence degradation, schema failure behavior, and key safety paths.

One honest residual risk: urgency calibration is still based on hand-written rules. E07 now treats an overdue Mada refund on a breast-pump order as `high`, not `critical`, because a refund delay is serious but not the same as an active delivery emergency. In production I would tune these thresholds with real support severity labels.

## Tooling

Tools used:

- Codex/GPT-5 coding agent for pair-programming, repo edits, debugging, documentation, and reviewer-style audit passes.
- Agent-style review loops for product strategy, senior engineering review, eval design, Arabic/bilingual audit, UI/demo audit, and README/TRADEOFFS drafting.
- Web research for official Mumzworld policy pages and public review signals.
- Pydantic for schema validation.
- scikit-learn `TfidfVectorizer` for lightweight local RAG.
- Streamlit for the one-page demo UI.
- Pytest and the custom eval runner for regression checks.
- OpenRouter is supported as an optional reply-refinement path, but the default verified run does not require a key.

Runtime model usage:

- Default verified path: no external LLM call. Decisions, routing, RAG retrieval, validation, EN/AR templates, and evals run locally.
- Optional path: OpenRouter can be enabled with `USE_LLM_DRAFTS=true` and `OPENROUTER_API_KEY`. It may rewrite `reply_en` and `reply_ar` for tone only after the structured packet is already valid.
- Model configured for optional path: `google/gemini-2.5-flash-lite` by default through OpenRouter, configurable via `OPENROUTER_MODEL`.
- Why no required runtime LLM: the Track A requirement is non-trivial AI engineering, not mandatory paid inference. This prototype satisfies that through tool use, RAG, structured output validation, multilingual handling, and evals beyond vibes while remaining reproducible without keys.

Resources used:

- Official Mumzworld public pages for delivery, FAQ, returns, and contact policy grounding, re-checked on 2026-04-28.
- Public customer-review signals for problem discovery only.
- Synthetic order, tracking, product, and return fixtures for implementation and evals.
- No retailer product-page scraping.

Official source snapshot:

- Shipping page: UAE same-day delivery for Dubai, Sharjah, and Abu Dhabi; KSA Yalla same-day and non-Yalla 3-5 days.
- FAQ: return pickup timing is UAE 1-3 business days and KSA 2-5 business days; refunds include wallet, credit card, Mada, and COD-to-wallet behavior.
- Returns policy / FAQ: eligible returns are tied to a 14-day window and product condition review.
- Contact / footer pages: support and category context for the internal-agent workflow.

How I used AI:

- Pair-coding and implementation: Codex proposed and edited code; I kept deterministic tools, Pydantic validation, and evals as the source of truth.
- Agent loops: subagents independently challenged the problem framing, engineering scope, Arabic quality, eval coverage, and UI/demo clarity.
- Prompt iteration: the optional OpenRouter prompt in `prompts/system_prompt.md` was narrowed so it may refine wording but not change facts or promises.
- Eval grading: the eval suite is deterministic Python, not model-graded, so results are reproducible without paid APIs.

Where I overruled agents: I rejected a broad support chatbot, avoided LangChain/LlamaIndex-style framework weight, kept OpenRouter optional, moved raw JSON/tool trace behind expanders, made EN/AR replies mandatory, and added Arabic static checks after the bilingual audit flagged that "Arabic quality" should be tested, not only claimed.

## Time Log

- 0:00-0:45 - Re-read Track A, validated the promise-rescue pain point, and rejected broader ideas.
- 0:45-1:45 - Built schemas, synthetic fixtures, policy notes, and deterministic order/tracking/return tools.
- 1:45-2:45 - Implemented RAG, decision logic, bilingual replies, safety checks, and optional LLM refinement.
- 2:45-4:00 - Added eval runner, 16 cases, expanded unit tests, Streamlit UI, and CLI.
- 4:00-5:00 - Wrote README, EVALS, TRADEOFFS, ARCHITECTURE, and Loom scenarios.

If spending more than 5 hours in a real submission, I would state the overage honestly and attribute it to Arabic QA and eval tuning.

## Submission Checklist

- GitHub repo: push this local repository to GitHub and paste the repo URL here.
- Loom: record the 3-minute walkthrough from `demos/loom_scenarios.md` and paste the Loom URL here.
