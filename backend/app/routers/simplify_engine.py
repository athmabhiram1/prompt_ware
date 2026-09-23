"""W2.1 SIMPLIFY deterministic core — FK/FRE math, grading, Hindi subs.

Pure functions only: no FastAPI, no I/O. Schema-bound helpers (``score``,
``split_clauses``, ``extract_glossary``) build router models via deferred
imports so ``simplify.py`` stays the single schema owner (frozen W2 contract
mirrored in ``frontend/src/lib/simplify.ts``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — annotations only, avoids import cycle
    from app.routers.simplify import GlossaryTerm, ReadScores, TextChunk

FK_LEVEL_TARGETS: dict[str, float | None] = {
    "5": 6.0,
    "8": 8.5,
    "10": 10.0,
    "pro": None,
}

CLAUSE_WINDOW_CHARS = 800

_LEVEL_MAX_WORDS: dict[str, int] = {"5": 15, "8": 20, "10": 25}

_PLAIN_SUBS: tuple[tuple[str, str], ...] = (
    ("utilize", "use"),
    ("commence", "start"),
    ("terminate", "end"),
    ("prior to", "before"),
    ("in the event that", "if"),
    ("hereinafter", "below"),
    ("notwithstanding", "despite"),
    ("pursuant to", "under"),
    ("indemnify", "compensate"),
    ("remedy the default", "fix the problem"),
    ("in accordance with", "under"),
    ("shall", "must"),
    ("hereby", ""),
    ("aforementioned", "above"),
)

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z']+")
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+")

# English legal term -> Hindi term (Devanagari). English stays in brackets.
HINDI_TERMS: dict[str, str] = {
    "rent": "किराया",
    "late fee": "विलंब शुल्क",
    "notice": "नोटिस",
    "eviction": "बेदखली",
    "deposit": "जमा राशि",
    "tenant": "किराएदार",
    "landlord": "मकान मालिक",
    "lease": "पट्टा",
    "agreement": "समझौता",
    "termination": "समाप्ति",
    "liability": "दायित्व",
    "dispute": "विवाद",
    "arbitration": "मध्यस्थता",
    "consent": "सहमति",
    "refund": "धनवापसी",
}

# English legal term -> (plain-English definition, Hindi term).
LEGAL_GLOSSARY: dict[str, tuple[str, str]] = {
    "rent": ("Money the tenant pays to use the property.", "किराया"),
    "late fee": ("Extra charge for paying after the due date.", "विलंब शुल्क"),
    "notice": ("A written warning sent before further action.", "नोटिस"),
    "eviction": ("Legal process forcing a tenant to leave.", "बेदखली"),
    "deposit": ("Money held as security, returned if no damage.", "जमा राशि"),
    "tenant": ("The person renting and living in the property.", "किराएदार"),
    "landlord": ("The property owner who rents it out.", "मकान मालिक"),
    "lease": ("The rental contract with rules and duration.", "पट्टा"),
    "agreement": ("A binding promise between parties.", "समझौता"),
    "termination": ("Ending the contract before its full term.", "समाप्ति"),
    "liability": ("Legal responsibility for loss or damage.", "दायित्व"),
    "dispute": ("A disagreement resolved by the stated process.", "विवाद"),
    "arbitration": ("Private dispute resolution outside court.", "मध्यस्थता"),
    "consent": ("Permission given for a specific use.", "सहमति"),
    "refund": ("Money returned for a cancelled service.", "धनवापसी"),
}


def count_syllables(word: str) -> int:
    """Vowel-group heuristic (textstat-equivalent core)."""
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 0
    groups = len(_VOWEL_GROUP_RE.findall(cleaned))
    if cleaned.endswith("e") and groups > 1:
        groups -= 1
    return max(groups, 1)


def split_sentences(text: str) -> list[str]:
    """Split on end punctuation; never returns empty strings."""
    return [part.strip() for part in _SENT_SPLIT_RE.split(text.strip()) if part.strip()]


def _counts(text: str) -> tuple[int, int, int]:
    words = _WORD_RE.findall(text)
    sentences = split_sentences(text)
    syllables = sum(count_syllables(word) for word in words)
    return len(words), max(len(sentences), 1), syllables


def flesch_kincaid(text: str) -> float:
    """FK grade = 0.39*(w/s) + 11.8*(syl/w) - 15.59."""
    word_count, sent_count, syll_count = _counts(text)
    if not word_count:
        return 0.0
    return 0.39 * (word_count / sent_count) + 11.8 * (syll_count / word_count) - 15.59


def flesch_reading_ease(text: str) -> float:
    """FRE = 206.835 - 1.015*(w/s) - 84.6*(syl/w)."""
    word_count, sent_count, syll_count = _counts(text)
    if not word_count:
        return 0.0
    return (
        206.835 - 1.015 * (word_count / sent_count) - 84.6 * (syll_count / word_count)
    )


def score(text: str) -> ReadScores:
    """Score a passage deterministically (no LLM)."""
    from app.routers.simplify import ReadScores

    return ReadScores(
        fk=round(flesch_kincaid(text), 2), fre=round(flesch_reading_ease(text), 2)
    )


def split_clauses(text: str, max_chars: int = CLAUSE_WINDOW_CHARS) -> list[TextChunk]:
    """Sentence-aware windows of at most ``max_chars`` chars (1-based pages)."""
    from app.routers.simplify import TextChunk

    chunks: list[TextChunk] = []
    current: list[str] = []
    current_len = 0
    for sentence in split_sentences(text):
        extra = len(sentence) + (1 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append(TextChunk(page=len(chunks) + 1, text=" ".join(current)))
            current, current_len = [], 0
        current.append(sentence)
        current_len += len(sentence) + 1
    if current:
        chunks.append(TextChunk(page=len(chunks) + 1, text=" ".join(current)))
    return chunks


def _apply_plain_words(text: str) -> str:
    out = text
    for complex_word, plain in _PLAIN_SUBS:
        out = re.sub(complex_word, plain, out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


def _split_long_sentence(sentence: str, max_words: int) -> list[str]:
    if len(_WORD_RE.findall(sentence)) <= max_words:
        return [sentence]
    for sep in (";", ", which ", ", that ", " and ", ", "):
        if sep in sentence:
            parts = [p.strip(" ,") for p in sentence.split(sep) if p.strip(" ,")]
            if len(parts) > 1:
                return [p[:1].upper() + p[1:] for p in parts]
    return [sentence]


def simplify_sentence(sentence: str, level: str) -> list[str]:
    """Grade one sentence; ``pro`` returns it unchanged."""
    if level == "pro":
        return [sentence]
    graded = _apply_plain_words(sentence)
    out: list[str] = []
    for part in _split_long_sentence(graded, _LEVEL_MAX_WORDS[level]):
        out.extend(_split_long_sentence(part, _LEVEL_MAX_WORDS[level]))
    return out


def hindi_with_bracket(term: str) -> str:
    """Summarize-then-translate atom: ``"<hi> (<en>)"`` keeps English visible."""
    key = term.strip().lower()
    return f"{HINDI_TERMS.get(key, key)} ({key})"


def to_hindi_sentence(text: str) -> str:
    """Substitute known terms longest-first; unknown words pass through."""
    out = text
    for term in sorted(HINDI_TERMS, key=len, reverse=True):
        out = re.sub(
            rf"\b{re.escape(term)}\b",
            hindi_with_bracket(term),
            out,
            flags=re.IGNORECASE,
        )
    return out


def extract_glossary(text: str) -> list[GlossaryTerm]:
    """Regex term match (stub); Wave 3 LLM fills richer defs if needed."""
    from app.routers.simplify import GlossaryTerm

    lowered = text.lower()
    terms: list[GlossaryTerm] = []
    for term in sorted(LEGAL_GLOSSARY, key=len, reverse=True):
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            definition, hi = LEGAL_GLOSSARY[term]
            terms.append(GlossaryTerm(term=term, definition=definition, hi=hi))
    terms.sort(key=lambda item: lowered.index(item.term))
    return terms
