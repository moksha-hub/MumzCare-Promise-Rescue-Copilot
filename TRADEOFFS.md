# TRADEOFFS

## Problem Selection

I chose MumzCare Promise Rescue Copilot because it sits at the exact point where a parent can lose trust: a promised delivery, return, refund, or replacement becomes uncertain. This is more valuable than a generic support chatbot because the system must reason about policy, order facts, payment method, timing, urgency, and safe communication.

The chosen user is the internal support or operations agent. I deliberately did not build a customer-facing status page because the higher-risk failure is inside the company workflow: the wrong team is routed, the wrong promise is made, or the reply is sent before the facts are verified.

Rejected ideas:

- Gift finder: useful but common and less urgent.
- PDP generator: feasible but commodity and easier to fake with good prose.
- Review summarizer: feasible but lower operational value.
- Duplicate catalog detector: high internal value, but realistic catalog data would be hard to defend in 5 hours.
- Full customer service chatbot: too broad and riskier than a decision copilot.

## Architecture Choice

The implementation is intentionally small:

- JSON fixtures for orders, tracking, returns, and products
- compact policy markdown file
- TF-IDF retrieval for policy citations
- deterministic tools for operational facts
- Pydantic schema for structured output
- optional OpenRouter reply refinement
- Streamlit UI and CLI
- eval runner and focused unit tests

This is less flashy than a multi-agent framework, but easier to run, explain, and evaluate in under 5 minutes.

Retrieval uses TF-IDF rather than embedding models. This trades off semantic synonym matching for speed, zero-cost local execution, and explainable scores. A production version should replace it with an embedding retriever or hybrid retrieval.

## Model Choice

The default prototype runs without a model key. That is deliberate. Free model gateways can be rate-limited and structured JSON support varies by provider. The optional OpenRouter path can polish replies, but it cannot change verified facts.

The boundary is:

- code verifies facts
- RAG retrieves citations
- schema validates shape
- safety checks block unsafe promises
- optional LLM improves wording only

## Auditability Choice

The output intentionally includes more than a final reply. `verified_facts`, `policy_citations`, `tool_trace`, `confidence`, `uncertainty_flags`, and `unsafe_promises_blocked` form an audit trail. This makes the prototype easier to grade and closer to a real internal support tool, where a supervisor needs to know why a recommendation was made.

I added `resolution_tasks` so the prototype does not stop at "what to say." It also shows the simulated company-side owner and next steps, such as Courier Ops requesting a verified carrier update, Delivery Investigation checking proof of delivery, or Payments & Refunds reviewing the payment-method path. These are mock tasks, not live API calls, because the assignment forbids relying on real Mumzworld internals.

I also chose strict schema validation because several Track A failure modes are structural: malformed JSON, empty fields, unsupported claims, and confident out-of-scope answers. Pydantic makes those failures explicit instead of relying on prompt wording.

The Pydantic tradeoff is that the system may reject or escalate more cases than a looser prompt-only prototype. I accepted that because explicit failures are easier to debug and safer than silently passing malformed or ungrounded output.

The fixed evaluation clock is another tradeoff. It makes the demo reproducible, but a production system would replace it with the real current time and create relative test fixtures.

The classifier is also intentionally rule-based. That keeps the prototype explainable and easy to evaluate in 5 hours, but it can miss indirect, typo-heavy, slang, or unusual Arabic phrasing. A production system should use a semantic intent classifier or LLM router, then preserve the current schema, citations, uncertainty flags, and unsafe-promise blockers as the safety boundary.

## Arabic Tradeoff

Arabic replies are written as native MSA-style support copy, not English translated word by word. This is safer for a regional ecommerce platform than trying to imitate dialects without native review.

What is missing:

- native-speaker Arabic QA
- KSA/UAE tone variants
- dialect handling
- Arabic-specific retrieval expansion

## Uncertainty Tradeoff

The copilot is conservative. It may escalate some cases that a human could solve directly. I accepted that because the assignment explicitly values knowing what the model does not know.

The cost of over-escalation is lower than the cost of inventing a refund, ETA, replacement approval, or policy exception.

## What Was Cut

- live Mumzworld backend integration
- real courier integration
- real refund actions
- full CRM workflow
- product-page scraping
- fine-tuning
- image evidence for damaged products
- model-as-judge evals
- advanced vector DB or reranking

## What I Would Build Next

- agent review UI: accept, edit, reject, and reason codes
- native Arabic review and regression suite
- real policy ingestion with versioning
- support-severity labels from historical tickets
- audit log for every recommendation
- A/B test on repeat contact rate and first-response resolution
