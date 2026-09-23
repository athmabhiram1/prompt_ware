import asyncio
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv
from lightrag.llm.gemini import gemini_embed, gemini_model_complete
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import wrap_embedding_func_with_attrs
from typing import Any


load_dotenv(override=True)

logger = logging.getLogger(__name__)

# --- Model constants ---
GEMINI_MODEL_NAME = "gemini-3.1-flash-lite"
GEMINI_EMBED_MODEL = "gemini-embedding-2-preview"
GEMINI_EMBED_DIM = int(os.getenv("GEMINI_EMBED_DIM", "3072"))  # Configurable output dimension (native dim of gemini-embedding-2-preview)

GROQ_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

OLLAMA_EMBED_MODEL = "qwen3-embedding:8b"
OLLAMA_EMBED_DIM = 4096
DEFAULT_OLLAMA_LLM_MODEL = "qwen3.5:9b"


# ---------------------------------------------------------------------------
# API key verification helpers (used by healthcheck.py)
# ---------------------------------------------------------------------------

async def verify_groq_api_key(timeout_seconds: float = 15.0) -> tuple[bool, str]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return False, "GROQ_API_KEY is empty"

    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 200:
            return True, "Groq key accepted"

        return False, f"Groq verification failed with HTTP {response.status_code}: {response.text[:200]}"
    except Exception as exc:
        return False, f"Groq verification error: {exc}"


async def verify_gemini_api_key(timeout_seconds: float = 15.0) -> tuple[bool, str]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return False, "GEMINI_API_KEY is empty"

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url)

        if response.status_code == 200:
            return True, "Gemini key accepted"

        return False, f"Gemini verification failed with HTTP {response.status_code}: {response.text[:200]}"
    except Exception as exc:
        return False, f"Gemini verification error: {exc}"


# ---------------------------------------------------------------------------
# Embedding — provider selected at startup, NOT switched at runtime.
#
# IMPORTANT: embedding dimensions differ by provider. Once the first document
# is indexed, the dimension is locked to the vector DB. Switching providers
# requires deleting rag_storage/ and re-indexing everything.
#
#   EMBED_PROVIDER=gemini  → gemini-embedding-2-preview, 3072-dim  (default)
#   EMBED_PROVIDER=ollama  → nomic-embed-text,            768-dim
# ---------------------------------------------------------------------------

def _resolve_ollama_url(url: str) -> str:
    """If running inside a Docker container and url points to localhost, rewrite it to host.docker.internal."""
    if os.path.exists("/.dockerenv") and "localhost" in url:
        return url.replace("localhost", "host.docker.internal")
    return url


_ollama_sdk: tuple[Any, Any] | None = None


def _ollama_sdk_lazy() -> tuple[Any, Any]:
    """Lazily import the Ollama SDK (dev-only; never imported in the prod path)."""
    global _ollama_sdk
    if _ollama_sdk is None:
        if os.getenv("APP_ENV", "dev").strip().lower() == "prod":
            raise RuntimeError("Ollama is dev-only and disabled when APP_ENV=prod.")
        from lightrag.llm.ollama import ollama_embed as _embed
        from lightrag.llm.ollama import ollama_model_complete as _complete
        _ollama_sdk = (_embed, _complete)
    return _ollama_sdk


def _require_ollama_base_url(action: str) -> str:
    """Dev-only Ollama gate for legacy paths (canonical: app.core.config).

    No loopback default ships here: local devs set OLLAMA_BASE_URL explicitly
    (see root .env.example); prod uses Gemini/Groq. Raises RuntimeError with
    guidance instead of dialling an undeployable default.
    """
    if os.getenv("APP_ENV", "dev").strip().lower() == "prod":
        raise RuntimeError(f"Ollama is dev-only and disabled when APP_ENV=prod (during {action}).")
    base = _getenv("OLLAMA_BASE_URL", "")
    if not base:
        raise RuntimeError(
            f"OLLAMA_BASE_URL is not set (during {action}). "
            "Local dev only: set it explicitly from root .env.example; prod uses Gemini/Groq."
        )
    return _resolve_ollama_url(base)


_cached_ollama_dim = None

def _resolve_ollama_embed_dim(model_name: str, base_url: str, default_dim: int) -> int:
    global _cached_ollama_dim
    if _cached_ollama_dim is not None:
        return _cached_ollama_dim

    # Check env first
    env_val = os.getenv("OLLAMA_EMBED_DIM")
    if env_val:
        try:
            val = int(_strip_inline_comment(env_val))
            _cached_ollama_dim = val
            return val
        except ValueError:
            pass

    # Try auto-detect
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.post(
                f"{base_url}/api/show",
                json={"name": model_name}
            )
            if res.status_code == 200:
                info = res.json().get("model_info", {})
                for k, v in info.items():
                    if k.endswith(".embedding_length") and isinstance(v, int):
                        logger.info("Auto-detected embedding length %d for model %s", v, model_name)
                        _cached_ollama_dim = v
                        return v
    except Exception as exc:
        logger.warning("Failed to auto-detect Ollama embedding dimension: %s", exc)

    _cached_ollama_dim = default_dim
    return default_dim


def get_embedding_func() -> Callable[[list[str]], Awaitable[np.ndarray]]:
    """Return a LightRAG-compatible embedding function."""
    embed_provider = _getenv("EMBED_PROVIDER", "gemini").lower()
    gemini_api_key = _getenv("GEMINI_API_KEY")
    ollama_base_url = _getenv("OLLAMA_BASE_URL", "")
    ollama_embed_model = _getenv("OLLAMA_EMBED_MODEL", OLLAMA_EMBED_MODEL)
    ollama_embed_dim = OLLAMA_EMBED_DIM

    logger.info(
        "Embedding provider=%s model=%s dim=%s",
        embed_provider,
        ollama_embed_model if embed_provider == "ollama" else GEMINI_EMBED_MODEL,
        ollama_embed_dim if embed_provider == "ollama" else GEMINI_EMBED_DIM,
    )

    if embed_provider == "ollama":
        ollama_base_url = _require_ollama_base_url("embedding")
        ollama_embed_dim = _resolve_ollama_embed_dim(ollama_embed_model, ollama_base_url, OLLAMA_EMBED_DIM)
        # Default local embed model is qwen3-embedding:0.6b (1024 dim).
        # You can override model/dim at runtime via OLLAMA_EMBED_MODEL/OLLAMA_EMBED_DIM.
        @wrap_embedding_func_with_attrs(
            embedding_dim=ollama_embed_dim,
            max_token_size=8192,
            model_name=ollama_embed_model,
        )
        async def embedding_func_ollama(texts: list[str]) -> np.ndarray:
            start = time.perf_counter()
            try:
                result = await _ollama_sdk_lazy()[0].func(
                    texts,
                    embed_model=ollama_embed_model,
                    host=ollama_base_url,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Ollama embedding failed for model '{ollama_embed_model}' (dim={ollama_embed_dim}): {exc}"
                ) from exc
            finally:
                elapsed = time.perf_counter() - start
                logger.info(
                    "Embedding batch provider=ollama model=%s count=%d elapsed=%.3fs",
                    ollama_embed_model,
                    len(texts),
                    elapsed,
                )
            return result

        return embedding_func_ollama

    # Default: Gemini gemini-embedding-2-preview
    @wrap_embedding_func_with_attrs(
        embedding_dim=GEMINI_EMBED_DIM,
        max_token_size=2048,
        model_name=GEMINI_EMBED_MODEL,
    )
    async def embedding_func_gemini(texts: list[str]) -> np.ndarray:
        start = time.perf_counter()
        try:
            # gemini-embedding-2-preview (multimodal) treats list inputs as a single aggregated 
            # content instead of distinct items in a batch. To get individual embeddings,
            # we must call the API concurrently for each text.
            tasks = [
                gemini_embed.func(
                    [text],
                    api_key=gemini_api_key,
                    model=GEMINI_EMBED_MODEL,
                    embedding_dim=GEMINI_EMBED_DIM,
                )
                for text in texts
            ]
            embeddings_list = await asyncio.gather(*tasks)
            result = np.vstack(embeddings_list)
        except Exception as exc:
            raise RuntimeError(
                f"Gemini embedding failed: {exc}. "
                f"To use local Ollama instead, set EMBED_PROVIDER=ollama in .env "
                f"and delete backend/rag_storage/ before re-indexing."
            ) from exc
        finally:
            elapsed = time.perf_counter() - start
            logger.info(
                "Embedding batch provider=gemini model=%s count=%d elapsed=%.3fs",
                GEMINI_EMBED_MODEL,
                len(texts),
                elapsed,
            )
        return result

    return embedding_func_gemini


def _strip_inline_comment(value: str) -> str:
    """Strip shell-style inline comments from env var values.

    python-dotenv does NOT strip inline comments (e.g. 'ollama  # or gemini').
    This helper removes everything from the first ' #' onwards.
    """
    idx = value.find(" #")
    return value[:idx].strip() if idx != -1 else value.strip()


def _getenv(key: str, default: str = "") -> str:
    """os.getenv with inline-comment stripping."""
    return _strip_inline_comment(os.getenv(key, default))


def get_active_index_namespace() -> str:
    """Return a stable namespace key for the active embedding setup."""
    embed_provider = _getenv("EMBED_PROVIDER", "gemini").lower()
    if embed_provider == "ollama":
        model = _getenv("OLLAMA_EMBED_MODEL", OLLAMA_EMBED_MODEL).lower()
        base_url = _resolve_ollama_url(_getenv("OLLAMA_BASE_URL", ""))
        dim = _resolve_ollama_embed_dim(model, base_url, OLLAMA_EMBED_DIM)
    else:
        model = GEMINI_EMBED_MODEL.lower()
        dim = GEMINI_EMBED_DIM
    safe_model = re.sub(r"[^a-z0-9]+", "_", model).strip("_")
    return f"{embed_provider}_{safe_model}_{dim}"


def get_active_rag_storage_dir() -> Path:
    """Return the base per-embedding storage directory.

    Company-specific data lives in subdirectories under this path:
        <base>/<company_id>/
    This function returns the base; callers that need a company-scoped path
    should append the company_id themselves.
    """
    base_dir = Path(__file__).resolve().parent / "rag_storage"
    return base_dir / get_active_index_namespace()


# ---------------------------------------------------------------------------
# LLM — Gemini → Groq (Llama 4 Scout) → Ollama fallback chain
# ---------------------------------------------------------------------------

def _gemini_cost_profile(keyword_extraction: bool) -> dict[str, object]:
    """Tune Gemini generation cost based on LightRAG stage."""
    if keyword_extraction:
        # Indexing/entity extraction path: keep outputs minimal and deterministic.
        return {
            "temperature": 0.0,
            "top_p": 0.1,
            "max_output_tokens": 384,
            "generation_config": {
                "thinking_config": {
                    "thinking_budget": 0
                }
            }
        }
    # Query path: low-reasoning budget with enough room for concise structured answers.
    return {
        "temperature": 0.1,
        "top_p": 0.3,
        "max_output_tokens": 768,
        "generation_config": {
            "thinking_config": {
                "thinking_budget": 1024
            }
        }
    }


def _openai_like_cost_profile(keyword_extraction: bool) -> dict[str, object]:
    """Cost profile for Groq/OpenAI-compatible calls."""
    if keyword_extraction:
        return {"temperature": 0.0, "top_p": 0.1, "max_tokens": 384}
    return {"temperature": 0.1, "top_p": 0.3, "max_tokens": 768}


def _ollama_cost_profile(keyword_extraction: bool, kwargs: dict[str, object]) -> dict[str, object]:
    """Merge conservative Ollama generation options into kwargs.

    num_ctx: must be set explicitly — Ollama defaults to ~2048 which truncates
    LightRAG's entity extraction prompts (system prompt alone is ~1305 tokens).
    think: must be top-level only (not inside options) per Ollama API spec.

    NOTE: LightRAG entity extraction calls llm_model_func with keyword_extraction=False.
    Only query-time keyword extraction uses keyword_extraction=True.
    Entity extraction responses can be 3000+ chars (~800+ tokens), so num_predict
    must be large enough for the non-keyword_extraction path too.
    """
    next_kwargs = dict(kwargs)
    base_options = next_kwargs.get("options")
    options: dict[str, object] = dict(base_options) if isinstance(base_options, dict) else {}
    num_ctx = int(_getenv("OLLAMA_NUM_CTX", "32768") or "32768")
    if keyword_extraction:
        # Query-time keyword extraction: JSON output, keep it tight
        options.update({"temperature": 0.0, "top_p": 0.1, "num_predict": 512, "num_ctx": num_ctx})
    else:
        # Entity extraction during indexing AND query responses both use this path.
        # Entity extraction responses can be 800+ tokens; query answers need ~768.
        # Use 2048 to safely cover both without truncation.
        options.update({"temperature": 0.1, "top_p": 0.3, "num_predict": 2048, "num_ctx": num_ctx})
    next_kwargs["options"] = options
    next_kwargs["think"] = False  # top-level only — Ollama API spec
    return next_kwargs


_ENTITY_VALIDATION_INSTRUCTION = (
    "\n\nIMPORTANT: Only extract entities that appear VERBATIM in the input text above. "
    "Do NOT invent, infer, or hallucinate entities. Every entity name must be directly "
    "present word-for-word in the provided text. If no entities match this criterion, "
    "return an empty list."
)

def _clean_extraction_response(output: str) -> str:
    """Clean the extraction output to remove markdown code blocks and intro text.

    LightRAG expects raw text lines formatted with <|>. LLMs often wrap these
    in ``` or ```txt code blocks, which triggers parser warnings.
    """
    # Remove triple backtick code blocks (e.g. ```txt ... ```)
    cleaned = re.sub(r"```[a-zA-Z0-9_-]*\n", "", output)
    cleaned = cleaned.replace("```", "")
    return cleaned.strip()


def get_llm_func() -> tuple[Callable[..., Awaitable[str]], str]:
    """Return (llm_async_callable, primary_model_name) based on PRIMARY_LLM_PROVIDER.

    Provider priority maps:
      gemini → groq → ollama
      groq   → gemini → ollama
      ollama → gemini → groq
    """
    primary_provider = _getenv("PRIMARY_LLM_PROVIDER", "gemini").lower()
    groq_api_key = _getenv("GROQ_API_KEY")
    gemini_api_key = _getenv("GEMINI_API_KEY")
    ollama_llm_model = _getenv("OLLAMA_LLM_MODEL", DEFAULT_OLLAMA_LLM_MODEL)

    provider_priority_map: dict[str, list[str]] = {
        "gemini": ["gemini", "ollama"],
        "groq":   ["gemini", "ollama"],
        "ollama": ["ollama", "gemini"],
    }

    if primary_provider not in provider_priority_map:
        raise ValueError(
            f"PRIMARY_LLM_PROVIDER must be one of 'gemini', 'groq', or 'ollama'. Got: {primary_provider!r}"
        )

    def _process_system_prompt(sys_prompt: str | None, is_gemini_with_thinking: bool = False) -> str | None:
        if is_gemini_with_thinking:
            return sys_prompt
        thinking_mode = os.getenv("INFERENCE_THINKING_MODE", "false").strip().lower()
        if thinking_mode == "false":
            no_think_instruction = "IMPORTANT: Do NOT output any internal thinking, reasoning process, chain-of-thought, or `<think>` tags. Output the final answer directly."
            if sys_prompt:
                return sys_prompt + "\n" + no_think_instruction
            return no_think_instruction
        return sys_prompt

    async def call_gemini(
        prompt: str,
        system_prompt: str | None,
        history_messages: list[dict],
        keyword_extraction: bool,
        **kwargs: object,
    ) -> str:
        try:
            system_prompt = _process_system_prompt(system_prompt, is_gemini_with_thinking=not keyword_extraction)
            if not keyword_extraction and system_prompt:
                system_prompt += _ENTITY_VALIDATION_INSTRUCTION
            request_kwargs = {**_gemini_cost_profile(keyword_extraction), **kwargs}
            start = time.perf_counter()
            res = await gemini_model_complete(
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                keyword_extraction=keyword_extraction,
                api_key=gemini_api_key,
                model_name=GEMINI_MODEL_NAME,
                **request_kwargs,
            )
            elapsed = time.perf_counter() - start
            logger.info(
                "LLM provider=gemini model=%s keyword_extraction=%s prompt_chars=%d response_chars=%d elapsed=%.3fs",
                GEMINI_MODEL_NAME,
                keyword_extraction,
                len(prompt),
                len(res or ""),
                elapsed,
            )
            return _clean_extraction_response(res) if keyword_extraction else res
        except Exception as exc:
            raise RuntimeError(f"Gemini completion failed: {exc}") from exc

    async def call_groq(
        prompt: str,
        system_prompt: str | None,
        history_messages: list[dict],
        keyword_extraction: bool,
        **kwargs: str,
    ) -> str:
        try:
            system_prompt = _process_system_prompt(system_prompt)
            if not keyword_extraction and system_prompt:
                system_prompt += _ENTITY_VALIDATION_INSTRUCTION
            request_kwargs = {**_openai_like_cost_profile(keyword_extraction), **kwargs}
            start = time.perf_counter()
            res = await openai_complete_if_cache(
                GROQ_MODEL_NAME,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                keyword_extraction=keyword_extraction,
                api_key=groq_api_key,
                base_url=GROQ_BASE_URL,
                **request_kwargs,
            )
            elapsed = time.perf_counter() - start
            logger.info(
                "LLM provider=groq model=%s keyword_extraction=%s prompt_chars=%d response_chars=%d elapsed=%.3fs",
                GROQ_MODEL_NAME,
                keyword_extraction,
                len(prompt),
                len(res or ""),
                elapsed,
            )
            return _clean_extraction_response(res) if keyword_extraction else res
        except Exception as exc:
            raise RuntimeError(f"Groq completion failed: {exc}") from exc

    async def call_ollama(
        prompt: str,
        system_prompt: str | None,
        history_messages: list[dict],
        keyword_extraction: bool,
        **kwargs: object,
    ) -> str:
        # ollama_model_complete reads the model name from
        # kwargs["hashing_kv"].global_config["llm_model_name"] — do NOT pass
        # model_name here or the ollama client will reject it.
        try:
            host = _require_ollama_base_url("llm")
            system_prompt = _process_system_prompt(system_prompt)
            if not keyword_extraction and system_prompt:
                system_prompt += _ENTITY_VALIDATION_INSTRUCTION
            request_kwargs = _ollama_cost_profile(keyword_extraction, kwargs)
            request_kwargs["think"] = False
            options = request_kwargs.get("options", {})
            logger.info(
                "LLM request provider=ollama model=%s keyword_extraction=%s prompt_chars=%d system_prompt_chars=%d options=%s think=%s",
                ollama_llm_model,
                keyword_extraction,
                len(prompt),
                len(system_prompt or ""),
                options,
                request_kwargs.get("think"),
            )
            start = time.perf_counter()
            res = await _ollama_sdk_lazy()[1](
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                keyword_extraction=keyword_extraction,
                host=host,
                **request_kwargs,
            )
            elapsed = time.perf_counter() - start
            response_text = res or ""
            has_think = "<think>" in response_text or "</think>" in response_text
            logger.info(
                "LLM response provider=ollama model=%s keyword_extraction=%s response_chars=%d has_think=%s elapsed=%.3fs",
                ollama_llm_model,
                keyword_extraction,
                len(response_text),
                has_think,
                elapsed,
            )
            return _clean_extraction_response(res) if keyword_extraction else res
        except Exception as exc:
            raise RuntimeError(f"Ollama completion failed: {exc}") from exc

    providers: dict[str, Callable[..., Awaitable[str]]] = {
        "gemini": call_gemini,
        "groq":   call_groq,
        "ollama": call_ollama,
    }

    async def llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict] | None = None,
        keyword_extraction: bool = False,
        **kwargs: object,
    ) -> str:
        # Clean <SEP> (case-insensitive) from prompts to prevent LLM from hallucinating/outputting it
        if isinstance(prompt, str):
            prompt = re.sub(r"(?i)\s*<sep>\s*", " ", prompt)
        if isinstance(system_prompt, str):
            system_prompt = re.sub(r"(?i)\s*<sep>\s*", " ", system_prompt)

        messages = history_messages if history_messages is not None else []
        if messages:
            messages = [
                {
                    **msg,
                    "content": re.sub(r"(?i)\s*<sep>\s*", " ", msg["content"])
                    if isinstance(msg.get("content"), str)
                    else msg.get("content"),
                }
                for msg in messages
            ]

        ordered = provider_priority_map[primary_provider]
        errors: list[str] = []

        for name in ordered:
            try:
                return await providers[name](
                    prompt, system_prompt, messages, keyword_extraction, **kwargs
                )
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        raise RuntimeError(
            f"All LLM providers failed {ordered}: " + " | ".join(errors)
        )

    model_name_by_provider = {
        "gemini": GEMINI_MODEL_NAME,
        "groq":   GROQ_MODEL_NAME,
        "ollama": ollama_llm_model,
    }
    return llm_model_func, model_name_by_provider[primary_provider]
