"""Embedding-dim one-truth (T1): production Gemini dim is 3072.

Single chosen dim: 3072 — the native output dim of gemini-embedding-2-preview
(backend/llm_provider.py:24-25). No rag_storage/ vector data exists, so no
stored index constrains the choice; 3072 matches AGENTS.md:12, the
llm_provider.py:85 provider comment, the main.py:723 fallback, and
migrate_to_mongo.py:39. Code defaults and GENAI.md agree on this one number.

No live calls, no secrets: dotenv loading is disabled and env overrides are
cleared, so these assert code-level defaults only.
"""

import importlib
from pathlib import Path

import dotenv

import llm_provider as _lp

CHOSEN_DIM = 3072


def _reload_code_default(monkeypatch):
    """Reimport llm_provider with dotenv + env overrides neutralised."""
    monkeypatch.delenv("GEMINI_EMBED_DIM", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    return importlib.reload(_lp)


def test_gemini_embed_dim_code_default_is_3072(monkeypatch):
    lp = _reload_code_default(monkeypatch)
    assert lp.GEMINI_EMBED_DIM == CHOSEN_DIM == 3072


def test_get_embedding_func_reports_3072(monkeypatch):
    lp = _reload_code_default(monkeypatch)
    monkeypatch.setenv("EMBED_PROVIDER", "gemini")
    func = lp.get_embedding_func()
    assert func.embedding_dim == CHOSEN_DIM == lp.GEMINI_EMBED_DIM


def test_genai_md_records_3072_one_truth():
    text = (Path(__file__).resolve().parent.parent.parent / "GENAI.md").read_text()
    assert "production Gemini embedding dim is 3072" in text


def test_vec_pg_ddl_records_3072_one_truth():
    text = (Path(__file__).resolve().parent.parent / "app" / "rag" / "vec_pg.py").read_text()
    assert f"vector({CHOSEN_DIM})" in text
    assert "vector(768)" not in text
