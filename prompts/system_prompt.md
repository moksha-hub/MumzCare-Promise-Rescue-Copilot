# Optional LLM Reply Refinement Prompt

The default prototype does not require an LLM. If `USE_LLM_DRAFTS=true`, this is the material prompt used for reply refinement:

```text
Rewrite the two customer replies below without changing facts or promises.
Arabic must be natural Modern Standard Arabic for UAE/GCC ecommerce customers,
not a word-for-word translation. Do not add compensation, ETA, refund approval,
or policy claims.

EN: {reply_en}
AR: {reply_ar}

Return exactly:
EN: ...
AR: ...
```

The important instruction is that the model may improve tone but may not change verified facts. The application validates and displays the original decision packet either way.
