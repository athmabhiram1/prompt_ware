# Brief — Edge Case 1: uncited bullet rejected

**Input:** caller attempts to inject custom bullet without cite:

```python
assert_all_cited(["Deposit cap breached"])  # missing [doc p.X]
```

**Engine:** `brief.py:66 assert_all_cited` at `brief.py:68-80` → `ValidationError: claim lacks [doc p.X] cite` (tested: `BriefResponse` rejects).

**Output:**
```json
{"detail":[{"loc":[0],"msg":"claim lacks [doc p.X] cite","type":"missing"}]}
```

**Why edge:** prevents LLM-drafted paragraphs from slipping into brief without spans; compose layer enforces CiteGuard-style cite discipline even for the brief.
