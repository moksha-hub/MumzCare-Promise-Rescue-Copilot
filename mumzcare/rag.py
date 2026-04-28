from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from mumzcare.data_loader import policy_text
from mumzcare.schemas import Citation


@dataclass(frozen=True)
class PolicyChunk:
    source: str
    section: str
    text: str


SECTION_URLS = {
    "Same-Day And Yalla Delivery": "https://www.mumzworld.com/en/shipping-rates",
    "Standard Delivery Windows": "https://www.mumzworld.com/en/faq",
    "Return Pickup Windows": "https://www.mumzworld.com/en/faq",
    "Refund Timing And Payment Method": "https://www.mumzworld.com/en/returns-policy",
    "Damaged Wrong Or Missing Items": "https://www.mumzworld.com/en/returns-policy",
    "Delivered But Not Received": "https://www.mumzworld.com/en/faq",
    "Stock Cancellation": "https://www.mumzworld.com/en/shipping-rates",
    "Customer Communication Safety": "https://www.mumzworld.com/en/contact-us",
    "Arabic Reply Quality": "https://www.mumzworld.com/en/contact-us",
}


def _split_policy_docs(text: str) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    current_section = "overview"
    current_lines: list[str] = []
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+)$", line)
        if heading:
            if current_lines:
                chunks.append(
                    PolicyChunk(
                        source="data/policy_docs.md",
                        section=current_section,
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_section = heading.group(1).strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        chunks.append(
            PolicyChunk(
                source="data/policy_docs.md",
                section=current_section,
                text="\n".join(current_lines).strip(),
            )
        )
    return [chunk for chunk in chunks if chunk.text]


@lru_cache(maxsize=1)
def _index() -> tuple[list[PolicyChunk], TfidfVectorizer, object]:
    chunks = _split_policy_docs(policy_text())
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform([chunk.text for chunk in chunks])
    return chunks, vectorizer, matrix


def retrieve_policy(query: str, top_k: int = 3) -> list[Citation]:
    chunks, vectorizer, matrix = _index()
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix).flatten()
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]
    citations: list[Citation] = []
    for idx, score in ranked:
        if score <= 0:
            continue
        chunk = chunks[idx]
        summary = _clean_summary(chunk)
        citations.append(
            Citation(
                source=chunk.source,
                source_url=SECTION_URLS.get(chunk.section),
                section=chunk.section,
                summary=summary,
                score=round(float(score), 3),
            )
        )
    return citations


def _clean_summary(chunk: PolicyChunk) -> str:
    lines = [line.strip() for line in chunk.text.splitlines() if line.strip()]
    if lines and lines[0].startswith("##"):
        lines = lines[1:]
    text = " ".join(lines)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    compact = " ".join(sentences[:2]).strip()
    return compact or text[:280].rstrip()
