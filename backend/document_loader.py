import os
import re
from collections import Counter

import pymupdf


_TRAILING_PAGINATION_RE = re.compile(r"[\s\d/]+$")
_PAGE_NUMBER_RE = re.compile(r"^\d+\s*/\s*\d+$")


def _normalize(line: str) -> str:
    """Strip trailing whitespace, page numbers, and slashes for frequency comparison.

    Ensures 'https://example.com/  19/20' and 'https://example.com/  2/20'
    both normalize to 'https://example.com' and are counted as the same line.
    """
    return _TRAILING_PAGINATION_RE.sub("", line).strip()


def _compute_noise_lines(page_texts: list[str], threshold: float = 0.5) -> set[str]:
    """Return normalized lines that appear on >= threshold fraction of pages.

    Normalization handles the common case where headers/footers include a
    per-page counter (e.g. a URL followed by '19/20') that would otherwise
    make each occurrence look unique.
    """
    total = len(page_texts)
    if total == 0:
        return set()
    counts: Counter[str] = Counter()
    for page_text in page_texts:
        seen_on_this_page: set[str] = set()
        for line in page_text.split("\n"):
            norm = _normalize(line)
            if norm and norm not in seen_on_this_page:
                counts[norm] += 1
                seen_on_this_page.add(norm)
    return {norm for norm, count in counts.items() if count >= total * threshold}


def _clean_page(page_text: str, noise_norms: set[str]) -> str:
    """Strip noise lines and bare page-number patterns from a single page."""
    cleaned: list[str] = []
    for line in page_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _normalize(stripped) in noise_norms:
            continue
        if _PAGE_NUMBER_RE.match(stripped):
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


def load_pdf(pdf_path: str) -> tuple[str, dict[str, str | int]]:
    """
    Extract clean text from a PDF and return it with basic metadata.

    Header/footer removal uses a frequency-based method: lines that appear on
    >= 50 % of pages (e.g. browser-print timestamps, document titles, URLs) are
    stripped from every page before the text is joined.

    Returns:
        (full_text, {"filename": str, "page_count": int})
    """
    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(
            f"Invalid or unreadable PDF: {pdf_path}. Error: {exc}"
        ) from exc

    page_count = document.page_count
    raw_pages: list[str] = []
    try:
        for page in document:
            raw = page.get_text("text", sort=True).strip()
            if raw:
                raw_pages.append(raw)
    finally:
        document.close()

    noise_norms = _compute_noise_lines(raw_pages)
    clean_pages = [_clean_page(pt, noise_norms) for pt in raw_pages]
    clean_pages = [p for p in clean_pages if p]

    full_text = "\n\n".join(clean_pages)
    metadata: dict[str, str | int] = {
        "filename": os.path.basename(pdf_path),
        "page_count": page_count,
    }
    return full_text, metadata
