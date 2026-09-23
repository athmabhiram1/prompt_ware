"""W2.3 CiteGuard Q&A abstention — TDD fixtures (retriever mocked, no live keys).

RED-first: imports app.rag.* + app.routers.qa which do not exist yet.
CiteGuard numbers under test: chunks 600/120, hybrid 0.65/0.35 top-8→4,
validator Overlap>=0.10 OR Sim>=0.40, ONE regen then refuse.
"""

from fastapi.testclient import TestClient

from app.rag import chunk as C
from app.rag import validator as V
from app.rag import vec_mem as M
from app.routers import qa

T_A = (
    "The tenant shall pay rent of Rs 30000 on the 5th of every month. "
    "A late fee of Rs 500 applies after the 10th."
)
T_B = (
    "The landlord must give three months notice before eviction. "
    "Termination requires written notice."
)

CH_A = C.Chunk(doc_id="lease1", chunk_id="c1", page=1, start=0, end=len(T_A), text=T_A)
CH_B = C.Chunk(doc_id="lease1", chunk_id="c2", page=2, start=0, end=len(T_B), text=T_B)


def _scored(ch, score=0.9):
    return M.ScoredChunk(chunk=ch, semantic=score, lexical=score, score=score)


def test_grounded_q_cites_correctly():
    draft = "The tenant pays Rs 30000 rent on the 5th of every month. {cite:c1}"
    resp = qa.answer_question(
        "When is rent due?",
        [_scored(CH_A), _scored(CH_B, 0.5)],
        llm_fn=lambda prompt: draft,
        doc_id="lease1",
    )
    assert resp.abstain is None, resp
    assert resp.answer and "30000" in resp.answer
    assert len(resp.citations) == 1
    cite = resp.citations[0]
    assert (cite.page, cite.start, cite.end) == (1, 0, len(T_A))
    assert cite.span == T_A  # page[start:end] == span
    assert resp.support_ratio == 1.0
    assert resp.regens == 0
    assert all(row.verdict == "Supported" for row in resp.audit)
    assert all(row.doc_id == "lease1" for row in resp.audit)


def test_ungrounded_q_abstains_with_reason():
    resp = qa.answer_question(
        "What is the capital of Mars?",
        [],
        llm_fn=lambda prompt: (_ for _ in ()).throw(AssertionError("LLM must not run")),
        doc_id="lease1",
    )
    assert resp.answer is None
    assert resp.citations == []
    assert resp.abstain is not None
    assert resp.abstain.code == "NO_EVIDENCE"
    assert "sufficient information" in resp.abstain.reason


def test_malformed_cite_triggers_regen_path():
    calls: list[str] = []

    def flaky(prompt: str) -> str:
        calls.append(prompt)
        return "Mars is red and rent is due. {cite:nope}"

    resp = qa.answer_question(
        "When is rent due?",
        [_scored(CH_A)],
        llm_fn=flaky,
        doc_id="lease1",
    )
    assert len(calls) == 2, "exactly ONE regen allowed"
    assert resp.regens == 1
    assert resp.answer is None
    assert resp.abstain is not None
    assert resp.abstain.code == "UNSUPPORTED_AFTER_REGEN"
    assert any(row.verdict == "Unsupported" for row in resp.audit)


def test_hybrid_weights_and_topk_truncation():
    texts = [f"rent clause number {i} payment due" if i == 0 else f"unrelated filler text alpha {i}" for i in range(10)]
    chunks = [
        C.Chunk(doc_id="d", chunk_id=f"k{i}", page=1, start=0, end=len(t), text=t)
        for i, t in enumerate(texts)
    ]

    def one_hot(t: str) -> list[float]:
        return [1.0, 0.0] if "rent" in t else [0.0, 1.0]

    out = M.hybrid_search("rent due date", chunks, embed_fn=one_hot, mode="hybrid")
    assert len(out) == 4, "top-8 then rerank keeps 4"
    assert out[0].chunk.chunk_id == "k0"
    expected = 0.65 * out[0].semantic + 0.35 * out[0].lexical
    assert abs(out[0].score - expected) < 1e-9
    assert out[0].semantic == 1.0


def test_chunker_is_page_span_constrained():
    page = " ".join(f"Sentence number {i} carries several plain words here." for i in range(300))
    assert C.estimate_tokens(page) > C.CHUNK_TOKENS
    chunks = C.chunk_pages("doc9", [page, T_B])
    assert C.CHUNK_TOKENS == 600 and C.CHUNK_OVERLAP_TOKENS == 120
    pages = {c.page for c in chunks}
    assert pages == {1, 2}
    for c in chunks:
        assert 0 <= c.start < c.end
        src = page if c.page == 1 else T_B
        assert src[c.start : c.end] == c.text
        assert C.estimate_tokens(c.text) <= C.CHUNK_TOKENS


def test_validator_thresholds_match_citeguard():
    assert (V.OVERLAP_MIN, V.SIM_MIN) == (0.10, 0.40)
    good = V.validate_sentence("tenant pays Rs 30000 rent on the 5th", T_A)
    assert good.supported
    bad = V.validate_sentence("quantum entanglement reverses zebra xylophones", T_A)
    assert not bad.supported


def test_qa_endpoint_grounded_and_abstain(monkeypatch):
    M.register_doc("t-lease", [T_A, T_B])
    client = TestClient(_app())
    ok = client.post("/qa", json={"doc_id": "t-lease", "question": "When is rent due?"})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["abstain"] is None
    assert body["citations"], body

    monkeypatch.setattr(qa, "hybrid_search", lambda *a, **k: [])
    refused = client.post("/qa", json={"doc_id": "t-lease", "question": "Capital of Mars?"})
    assert refused.status_code == 200
    assert refused.json()["abstain"]["code"] == "NO_EVIDENCE"


def _app():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(qa.router)
    return app
