# Checklists — Abstention

**Input:** `samples/empty.txt` (no clauses)

**Policy:** checklists are **statute checklists**, not doc answers — they never abstain. Even with empty doc, the engine returns the full move-out + TDS lists with the same MTA/194-IB anchors.

**Why not NO_EVIDENCE:** abstention applies to **doc-grounded Q&A** (`qa.py:152` → `prompts.py:74`). Checklists are deterministic procedure reminders; emitting them on empty does not hallucinate doc facts — it surfaces statutory procedure (with disclaimer).

**Output:** same 6-item move-out + 5-item TDS + `.ics` as in `output.md`, disclaimer attached.

**Counter-example:** QA on empty *does* abstain (`empty.txt` + `What is the monthly maintenance charge?` → `NO_EVIDENCE` at `qa.py:42`). See `examples/qa/abstention.md`.

*LLM-drafted: none.*
