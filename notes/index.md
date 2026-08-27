---
title: Background Notes
---

A MyST site for literature notes, derivations and reading summaries — the
material that informs the papers but does not belong in them.

It reads the root `references.bib` directly, so a note and a paper cite the same
entry by the same key. Cite with {cite:p}`mnih2015human`.

```bash
npm install -g mystmd    # once
make notes               # serve at localhost:3000
```

## Why this is separate from `docs/`

A document directory must compile standalone — Overleaf builds it in isolation,
and `make arxiv` flattens it — so it gets a generated *copy* of the bibliography
and may never reference a path outside itself. This site has no such
constraint, so it reads the root `references.bib` and `figures/` directly. That
is the whole difference.

## Suggested structure

One file per topic. Keep them short and heavily cited; they are the raw material
a related-work section is written from, not prose to be pasted into a paper.
