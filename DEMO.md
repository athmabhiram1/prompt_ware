# DEMO.md — NyayaMitra 3:30 Demo Script (W4.1, frozen offline bundles)

One speaker, one laptop, zero network dependency. Everything below is served
from `data/preindex/*.json` via `GET /demo/*` with `LLM_LIVE=0`.
Recipes: `python scripts/build_demo_bundles.py`, then
`pytest backend/tests/test_demo.py -q` (8 passed).

## Cast

- **Priya** — tenant, HSR Layout Bengaluru. Rs 30,000/month rent,
  Rs 3,00,000 deposit (10x rent). `GET /demo/priya` → `msa.json`.
- **MSME** — Sharma Sweets, Indore, vendor NDA. `GET /demo/msme` → `nda.json`.
- **DPDP** — PixelWorks offer letter, Delhi. `GET /demo/dpdp` → `offer.json`.

## Timestamped script (3:30 total)

| Time | Beat | Say / do |
|------|------|----------|
| 0:00-0:20 | Hook | "Priya paid 10 months rent as deposit. The legal cap is 2. Watch this." Open `GET /demo/priya`. |
| 0:20-0:50 | HIGH risks | Scroll the 4 HIGHs: 10x deposit vs MTA Sec 11 cap, unilateral landlord amendment, blanket indemnity, third-party data sharing. Each excerpt is a verbatim span (`text[start:end] == excerpt`). |
| 0:50-1:10 | Maths anchors | "Cap Rs 60,000, deposited Rs 3,00,000, excess Rs 2,40,000. TDS 2% under 194-IB, and 194-IB only bites above Rs 50,000/month, so here it is not even applicable. 30-day refund clock." |
| 1:10-1:30 | Brief | Read two brief bullets aloud; point at the `[doc p.1]` cite on each. "Every bullet carries its receipt. And the footer: not legal advice." |
| 1:30-1:55 | **Abstain beat** | Ask: "What is the monthly maintenance charge?" Answer panel shows `NO_EVIDENCE` abstain with reason, zero cites invented. "When the paper is silent, the product says so. That is the whole trust model." |
| 1:55-2:20 | MSME contrast | `GET /demo/msme`: auto-renew 2-year terms, instant termination, vendor data sharing without consent. "Same engine, R01-R18, different trap family." |
| 2:20-2:40 | DPDP contrast | `GET /demo/dpdp`: outdated 5% TDS cite flagged against current 2%, 3-year retention, 72-hour breach notice. |
| 2:40-3:00 | Offline proof | "No keys, no cloud." Show `meta: {served_from: cache, llm_live: false}` and `cost_usd: 0.0` on all three. Tests block `socket.create_connection` + `getaddrinfo` and still pass. |
| 3:00-3:30 | Close | "Scan, maths, contradict, simplify, brief. Cited or silent. Talk to a lawyer with this in hand." End on the 30-day refund obligation. |

## Abstain beat (verbatim fallback lines)

- Q: "What is the monthly maintenance charge?" (priya)
- A: `null` + `abstain: {reason: "document does not contain sufficient information to answer [NO_EVIDENCE]", code: "NO_EVIDENCE"}`.
- Say: "No guess, no filler sentence, no fake cite. Silence with a code."

## Aura-paused fallback (if the live backend is cold)

1. Stay on the frozen bundles: `python -c` + `load_bundle("priya")` prints the
   same JSON the route serves; or open `data/preindex/msa.json` directly.
2. Say: "Aura paused, Render cold, `LLM_LIVE=0`. The demo does not care. Cache
   is the product." (`backend/app/routers/demo.py:88-92` ignores `LLM_LIVE`.)
3. Run `pytest backend/tests/test_demo.py -q` live: 8 passed in ~1s, network
   blocked, which *is* the offline proof.
4. If even Python is unhappy: narrate from `scripts/build_demo_bundles.py`
   constants (`PRIYA_TEXT`, obligations) — they are the frozen source of truth.

## Endpoints

- `GET /demo` → `["dpdp", "msme", "priya"]`
- `GET /demo/priya` → `msa.json` (Bengaluru lease)
- `GET /demo/msme` → `nda.json` (MSME NDA)
- `GET /demo/dpdp` → `offer.json` (offer letter)
- Unknown id → `404`; missing bundle file → `503` with rebuild hint.
