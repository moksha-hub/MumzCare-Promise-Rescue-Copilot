from __future__ import annotations

import os

from dotenv import load_dotenv

from mumzcare.schemas import DecisionPacket

load_dotenv()


def llm_enabled() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY")) and os.getenv("USE_LLM_DRAFTS", "false").lower() == "true"


def maybe_refine_replies(packet: DecisionPacket) -> DecisionPacket:
    """Optional OpenRouter draft refinement.

    The deterministic packet is already valid. This step is deliberately optional so the
    take-home remains runnable without paid keys or network access.
    """
    if not llm_enabled():
        return packet
    if packet.unsafe_promises_blocked:
        return packet

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        prompt = f"""
Rewrite the two customer replies below without changing facts or promises.
Arabic must be natural Modern Standard Arabic for UAE/GCC ecommerce customers,
not a word-for-word translation. Do not add compensation, ETA, refund approval,
or policy claims.

EN: {packet.reply_en}
AR: {packet.reply_ar}

Return exactly:
EN: ...
AR: ...
"""
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        if "EN:" not in text or "AR:" not in text:
            return packet
        en = text.split("EN:", 1)[1].split("AR:", 1)[0].strip()
        ar = text.split("AR:", 1)[1].strip()
        if en and ar:
            packet.reply_en = en
            packet.reply_ar = ar
            packet = DecisionPacket.model_validate(packet.model_dump())
    except Exception:
        return packet
    return packet
