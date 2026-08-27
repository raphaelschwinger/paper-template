# `data/` — the committed W&B cache

Every number in every document comes from a file in this directory. Nothing here
is written by hand.

| File | What it is |
|---|---|
| `figures/<name>.csv` | the numbers behind `figures/<name>.yml` |
| `tables/<name>.csv` | the numbers behind `tables/<name>.yml` |
| `wandb.lock.yml` | the exact W&B run IDs behind each of them |
| `raw/` | scratch space while you work out a query — gitignored |

One cache file per config, namespaced by kind so a figure and a table may share
a name. Two configs that resolve to an identical query are fetched once and the
result copied — they stay independent snapshots without querying W&B twice.

```bash
make fetch REFRESH=1                    # re-run every query, repin the run set
make fetch                              # re-read the pinned runs only
make fetch DATASET=figures/learning_curve REFRESH=1
```

## Why CSV, and why committed

**Committed**, because it is what makes the paper buildable by someone who is not
you: a coauthor with no W&B access, a TeX Live container in CI, Overleaf. The
alternative — figures built live from the API — means the PDF in the repository
has no verifiable relationship to anything.

**CSV rather than Parquet**, because it renders in the GitHub UI and diffs as
text. A pull request that moves the paper's numbers shows *which* numbers moved,
in the review, before anyone rebuilds a figure.

Both only work while these files stay small. Aggregate in the config (the
`aggregate:` block collapses seeds into mean/std/count) rather than committing
one row per run per step. If a file here is over a megabyte, the query is doing
too little.

## The rules

- **Never hand-edit a `.csv` or the lock.** Being readable does not make it a
  source of truth — `make fetch` regenerates both, and an edit is silently lost.
  The source of truth is the W&B project plus the config's `data:` block.
- **A changed `data:` block without a re-fetch is a build failure.**
  `make check-generated` compares each config against the hash recorded in the
  lock. Changing a config's `plot:` or `table:` block does *not* invalidate the
  cache — restyling is not a change to what the figure reports.
- **A changed `.csv` without a rebuild is a build failure too.** Figure and table
  provenance records the hash of what it read, so run `make plots && make tables`
  after every fetch, and read `git diff data/`.
