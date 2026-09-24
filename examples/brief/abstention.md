# Brief — Abstention / Neutral Brief

**Input:** `samples/empty.txt`

```python
build_brief(empty, premise="residential")
```

**Output (engine):**
```markdown
# NyayaMitra — Lawyer Brief (1 page)

> Information, not legal advice — verify with advocate

## Facts
- Agreement excerpt reviewed (18 clauses scanned, premise residential) [doc p.1]
- Plain-language gist: EMPTY — test empty-doc ... [doc p.1]

## Risks
- No high-tier hits; highest tier below T4 [doc p.1]

## Missing
- R06 tenure missing — verify before signing [doc p.1]
- R16 retention missing — verify before signing [doc p.1]
...
```

**Policy:** brief never hallucinates risks for empty; `risks` falls to `"No high-tier hits; highest tier below T4"` (code at `brief.py:166`). Still every bullet carries `[doc p.1]` (head slice `text[:200]` when no excerpt), so `assert_all_cited` passes — but content is explicitly neutral, not fabricated.

**Contrasted with QA:** empty QA → `NO_EVIDENCE` abstention (no answer). Brief on empty → neutral brief (no false risk). Both are non-hallucinating.

**Guard:** empty string `""` → `ValueError("text must not be empty")` → 422, not a silent brief.
