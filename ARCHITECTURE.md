# Architecture

## One-Sentence Workflow

MumzCare takes a customer message plus an order ID, verifies operational facts through tools, retrieves the relevant policy section, applies safety and uncertainty rules, validates a structured decision packet, and returns English/Arabic replies for a support agent.

## Why The Design Is Simple

The assignment rewards a working, explainable AI engineering prototype more than a large framework. This project uses a deterministic core and optional model refinement:

- Deterministic code owns facts, routing, safety checks, and validation.
- RAG owns policy grounding.
- Optional OpenRouter refinement can improve reply wording, but cannot change facts.
- Evals prove the behavior against adversarial cases.

## Data Sources

All operational data is synthetic and local:

| File | Purpose |
|---|---|
| `data/orders.json` | Order status, payment method, country, priority, and items |
| `data/tracking_events.json` | Carrier status, last scan, and ETA |
| `data/returns.json` | Return pickup and collection state |
| `data/products.json` | Product category, urgency flag, English and Arabic names |
| `data/policy_docs.md` | Compact policy notes grounded in public Mumzworld policy pages |

The prototype does not scrape retailer product pages. Policy notes cite public Mumzworld URLs:

- `https://www.mumzworld.com/en/shipping-rates`
- `https://www.mumzworld.com/en/faq`
- `https://www.mumzworld.com/en/returns-policy`
- `https://www.mumzworld.com/en/contact-us`

## Runtime Flow

```text
Customer message + order_id
  -> detect input language
  -> safety gates
       medical advice refusal
       policy-abuse refusal
       missing/unknown order handling
  -> tool lookups
       get_order
       get_tracking
       get_return
       get_product
  -> classify case type
  -> compute SLA status
  -> compute urgency
  -> choose recommended actions
  -> build verified facts
  -> retrieve policy citations with TF-IDF RAG
  -> compute uncertainty flags
  -> block unsafe ETA/refund/status promises
  -> draft English and Arabic replies
  -> validate DecisionPacket with Pydantic
  -> optional LLM wording refinement
  -> return JSON/UI output
```

## Safety Rules

The system is conservative by design:

- No order ID: ask for it, do not invent facts.
- Unknown order: say it was not found in the synthetic dataset.
- Missing carrier ETA: do not promise a delivery time.
- Unsupported refund: do not approve a refund.
- Medical advice: refuse and escalate.
- Policy abuse: refuse to falsify delivery or warranty state.
- Low confidence: require human review.
- In-scope case without facts or policy citations: fail validation.

## Multilingual Design

Every valid decision includes both `reply_en` and `reply_ar`.

Arabic is written separately rather than translated from English. The system uses:

- `name_ar` product names in `products.json`
- Arabic labels for SLA states, payment methods, return statuses, and actions
- RTL rendering in the Streamlit UI
- eval checks for Arabic script presence, mojibake, and raw enum leakage

For Arabic input, the UI shows Arabic first. For English input, it shows English first. Mixed EN/AR input is detected as `mixed`.

## Why TF-IDF RAG

TF-IDF was chosen because it is fast, local, free, and explainable within a 5-hour scope. It returns visible scores and source sections, which makes grounding auditable.

Known limitation: TF-IDF is weaker than embeddings for semantic synonyms. A production version should replace `mumzcare/rag.py` with an embedding retriever such as `sentence-transformers/all-MiniLM-L6-v2` or a hosted embedding model.

## Interfaces

- CLI: `python -m mumzcare.cli analyze --order-id MW-1001 --message "..."`
- Evals: `python -m evals.run_evals`
- UI: `streamlit run streamlit_app.py`

The CLI writes UTF-8 JSON directly so Arabic text works on Windows terminals.

## Evaluation

The eval suite has 16 golden cases and 11 metrics:

- case classification
- SLA status
- urgency
- recommended action
- human-review behavior
- unsafe-promise/refusal behavior
- schema validity
- citation grounding
- bilingual output
- reply safety
- static Arabic quality

It includes easy, adversarial, Arabic, mixed-language, missing-data, medical-refusal, policy-abuse, refund, return, stock-cancellation, and delivery cases.

## What Would Change In Production

- Replace synthetic fixtures with real order, tracking, return, and payment APIs.
- Replace TF-IDF with embedding retrieval and source versioning.
- Add agent review actions: accept, edit, reject, escalate.
- Add audit logs for every recommendation.
- Tune urgency thresholds with historical support labels.
- Add native Arabic QA and region-specific tone presets.
