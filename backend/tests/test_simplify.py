"""W2.1 SIMPLIFY vertical — TDD gate (RED first, LLM stubbed, LLM_LIVE=0).

Covers: deterministic FK/FRE math on a fixture clause, clause-window bound
(<=800ch), citation presence + span validity (no invented spans), Hindi
bracket format, level->FK-target map, and request validation. No live LLM:
every test runs on the deterministic core only.
"""

import re
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.simplify import (  # noqa: E402
    FK_LEVEL_TARGETS,
    SimplifyRequest,
    SimplifySentence,
    flesch_kincaid,
    flesch_reading_ease,
    hindi_with_bracket,
    simplify_text,
    split_clauses,
    to_hindi_sentence,
)

FIXTURE = "The cat sat on the mat."

CLAUSE = (
    "The tenant shall pay the monthly rent on or before the fifth day of "
    "each calendar month. If the rent remains unpaid for fifteen days, the "
    "landlord may issue a written notice to the tenant. If the tenant fails "
    "to remedy the default within thirty days of such notice, the landlord "
    "may commence eviction proceedings in accordance with applicable law."
)

HINDI_BRACKET_RE = re.compile(r"[\u0900-\u097F].+\([A-Za-z][A-Za-z \-]+\)")


def test_fk_math_on_fixture() -> None:
    assert flesch_kincaid(FIXTURE) == pytest.approx(-1.45, abs=0.01)


def test_fre_math_on_fixture() -> None:
    assert flesch_reading_ease(FIXTURE) == pytest.approx(116.15, abs=0.05)


def test_clause_windows_bounded() -> None:
    chunks = split_clauses(CLAUSE * 6)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert len(chunk.text) <= 800


def test_citation_missing_raises() -> None:
    with pytest.raises(ValidationError):
        SimplifySentence(text="uncited sentence")  # type: ignore[call-arg]


def test_citation_span_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        SimplifySentence(text="bad span", cite={"page": 1, "start": 10, "end": 4})


def test_every_sentence_cited_with_real_spans() -> None:
    response = simplify_text(CLAUSE, level="8")
    assert len(response.sentences) >= 1
    chunks = {chunk.page: chunk.text for chunk in split_clauses(CLAUSE)}
    for sentence in response.sentences:
        assert sentence.cite.page in chunks
        chunk_text = chunks[sentence.cite.page]
        start, end = sentence.cite.start, sentence.cite.end
        assert 0 <= start < end <= len(chunk_text)


def test_hindi_bracket_format() -> None:
    assert HINDI_BRACKET_RE.search(hindi_with_bracket("rent"))


def test_hindi_sentence_keeps_english_terms_in_brackets() -> None:
    out = to_hindi_sentence("The tenant shall pay the monthly rent.")
    assert HINDI_BRACKET_RE.search(out)


def test_pro_level_keeps_legal_terms() -> None:
    text = "The landlord may terminate the lease herein pursuant to law."
    response = simplify_text(text, level="pro")
    joined = " ".join(s.text for s in response.sentences)
    assert "terminate" in joined


def test_level_targets_map() -> None:
    assert FK_LEVEL_TARGETS == {"5": 6.0, "8": 8.5, "10": 10.0, "pro": None}


def test_request_needs_doc_id_or_text() -> None:
    with pytest.raises(ValidationError):
        SimplifyRequest(level="8")


def test_before_after_scores_present() -> None:
    response = simplify_text(CLAUSE, level="5")
    assert isinstance(response.before.fk, float)
    assert isinstance(response.after.fk, float)
    assert isinstance(response.before.fre, float)
    assert isinstance(response.after.fre, float)
    assert len(response.glossary) >= 1
