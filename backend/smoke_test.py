import asyncio
import traceback
from pathlib import Path

import pytest

pytest.importorskip("lightrag", reason="needs local stack (LightRAG/Ollama/Neo4j+PDF)")

from lightrag_engine import index_document, query


def _resolve_pdf_path() -> str:
    documents_dir = Path(__file__).resolve().parent / "documents"
    default_pdf = documents_dir / "truecaller_tos.pdf"
    if default_pdf.exists():
        return str(default_pdf)

    pdf_files = sorted(documents_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {documents_dir}")
    return str(pdf_files[0])


async def main() -> None:
    try:
        pdf_path = _resolve_pdf_path()
        await index_document(pdf_path)
        print("Indexing done.")

        result = await query("Does Truecaller share my contacts with third parties?")
        print(result)
        print("Check Neo4j at http://localhost:7474 — expect 20+ nodes")
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
