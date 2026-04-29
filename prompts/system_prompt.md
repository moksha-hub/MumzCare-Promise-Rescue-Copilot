# Optional LLM Reply Refinement Prompt

The default prototype does not require an LLM. If `USE_LLM_DRAFTS=true`, this is the material prompt used for reply refinement. The default optional OpenRouter model is `poolside/laguna-xs.2:free`, configurable with `OPENROUTER_MODEL`.

```text
Rewrite the two customer replies below without changing facts or promises.
Arabic must be natural Modern Standard Arabic for UAE/GCC ecommerce customers,
not a word-for-word translation. Do not add compensation, ETA, refund approval,
policy claims, Ops Memory claims, or internal case-note details.

EN: {reply_en}
AR: {reply_ar}

Return exactly:
EN: ...
AR: ...
```

The important instruction is that the model may improve tone but may not change verified facts. Ops Memory matches and Obsidian-style case notes are internal artifacts; they should not leak into customer-facing replies unless the deterministic packet already included the fact in the reply. The application validates and displays the original decision packet either way.

When `unsafe_promises_blocked` is non-empty, LLM refinement is skipped entirely to prevent any rewording of safety-critical refusal replies.

After a rewrite, the application re-validates the packet with Pydantic. If the optional model output is missing the expected `EN:` / `AR:` markers, returns empty text, or causes validation to fail, the deterministic original replies are kept.
