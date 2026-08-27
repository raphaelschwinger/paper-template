# Agent instructions

Conventions for AI assistants working in this repository. The human-facing
handbook is `docs/documentation/README.md` (it is the root `README.md` until
`bootstrap.sh` moves it there and puts a project README in its place).
Per-document specifics — venue, deadlines, page limits — live in
`docs/<document>/AGENTS.md`.

## What this repository is

A **paper repository**: one or more LaTeX documents, plus the machinery that
builds their figures and tables from experiment-tracker results.

It is meant to live as a **git submodule of a code repository**: a research
monorepo — one working tree — with two repositories, so the paper can stay
private while the code is not.

**The paper repository never reads the code repository.** Not `../code/`, not a
sibling package, not a checkpoint on disk. Numbers arrive through W&B and stop
in `data/`. That boundary is what lets the paper build on a coauthor's laptop,
in a TeX Live container, and on Overleaf — none of which have the code.

```
references.bib            SINGLE SOURCE OF TRUTH for every document's bibliography
paper.yml                 the W&B connection and the house style — NO datasets
figures/<name>.yml        one figure: its query AND its styling
figures/<name>.py         OPTIONAL custom renderer for that figure
figures/<name>.drawio     hand-authored diagram source
figures/generated/        rendered PDFs and draw.io exports — generated, committed
tables/<name>.yml         one table:  its query AND its layout
data/<kind>/<name>.csv    that config's fetched numbers — generated, committed
data/wandb.lock.yml       the exact run IDs behind them
src/paperkit/             config loading, renderers, provenance
docs/<document>/          one LaTeX document each; compiles standalone
docs/documentation/       the template handbook — kept verbatim, do not rewrite
notes/                    MyST site for background notes (reads the root bib directly)
tools/                    fetch, build, draw.io export, materialization, staleness checks, template sync
tools/templates/          LaTeX document templates
.template-upstream.yml    the template this repository was generated from
```

**A figure is a file, not a registry entry plus a script.** `figures/x.yml`
declares where its numbers come from and how it is drawn, and renders itself.
There is no central list of datasets to keep in step. When the built-in
renderers cannot draw something, `figures/x.py` beside it takes over the drawing
and keeps everything else.

## The generated-file contract

This is the most important thing to understand before editing anything.

| File | Status | Edit it? |
|---|---|---|
| `references.bib` (root) | **source of truth** | yes — the only bib a human edits |
| `paper.yml` | **source of truth** | yes — W&B connection + house style |
| `figures/*.yml`, `tables/*.yml` | **source of truth** | yes — each config's query and styling |
| `figures/*.py`, `tables/*.py` | **source** | yes — optional custom renderers |
| `docs/*/{metadata,abstract,text,acronyms}.tex` | **source** | yes — this is the writing |
| `figures/*.drawio` | **source** | yes |
| `.template-upstream.yml` | **source** | yes — the one place the template URL lives |
| `data/*/*.csv` | generated, **committed** | **no** — `make fetch` |
| `data/wandb.lock.yml` | generated, **committed** | **no** — `make fetch` |
| `figures/generated/*` | generated, **committed** | **no** — `make plots` / `make drawio` |
| `docs/*/figures/*.pdf` | generated copy | **no** — copied from `figures/generated/` for Overleaf |
| `docs/*/tables/*.tex` | generated, **committed** | **no** — `make tables` |
| `figures/generated/.provenance.json` | generated | **no** — written by `save_figure` |
| `docs/*/tables/.provenance.json` | generated | **no** — written by `save_table` |
| `docs/*/references.bib` | generated copy | **no** — `make sync-bib` |
| `docs/*/main.tex` | generated from a template | **no** — edit `tools/templates/<name>/main.tex` |
| `docs/*/*.sty`, `docs/*/orcid.pdf` | generated copy | **no** — edit `tools/templates/` |
| `docs/*/.template.yml` | generated | **no** — written by `make set-template` |
| `docs/documentation/README.md` | upstream, **committed** | **no** — it merges from the template |

The copies under `docs/<document>/` exist because that directory has to compile
in isolation: Overleaf builds it with no Python environment and no shell access,
and `make arxiv` flattens it into a submission bundle. Everything the compiler
needs must sit beside `main.tex`, and **no path in a document may reach outside
its own directory** — `../../figures/...` breaks both.

`make check-generated` fails if any generated file has drifted from its source.
It runs in pre-commit and in CI. **If it fails, regenerate — never hand-edit the
generated file to match.**

## Everyday commands

```bash
make              # list all targets
make setup        # uv sync
make all          # figures + tables -> paper, from the committed cache
make configs      # every figure and table config, and where it lands
make fetch        # the ONLY command that talks to W&B (needs WANDB_API_KEY)
make plots ONLY=x # render one figure
make paper        # compile the paper
make check        # everything CI checks
```

`PAPER=` selects the document; it defaults to the first one under `docs/`.

## W&B is the only data source

```
figures/x.yml ──make fetch──► data/figures/x.csv ──make plots──► figures/generated/x.pdf
                              data/wandb.lock.yml                 └── copy ──► docs/<doc>/figures/x.pdf
```

- **Nothing under `figures/` or `tables/` imports `wandb`.** Renderers read the
  cache through `paperkit.data`. A renderer that queries the API cannot run in
  CI, cannot run for a coauthor, and produces a figure nobody else can rebuild.
- **Never hand-edit `data/**/*.csv` or `data/wandb.lock.yml`.** Being readable
  does not make them a source of truth; `make fetch` overwrites both. To change
  what the paper reports, change the config's `data:` block and re-fetch.
- **Aggregate in `data:`, not in the renderer.** The `aggregate:` block
  collapses seeds into mean/std/count before the CSV is written, which is what
  keeps the committed file small enough to diff. A renderer that reads one row
  per run per step is a sign the query is doing too little.
- **`data:` and `plot:` are different kinds of change.** Editing `data:`
  invalidates the cache and requires a re-fetch; editing `plot:` does not.
  Do not touch `data:` to fix a styling problem.
- **Widening a query is a deliberate act.** `make fetch` re-reads the pinned run
  IDs. Only `make fetch REFRESH=1` re-runs the filters, and it prints which runs
  entered and left. Do not run it to "fix" a check failure without reading that
  diff — it is the paper's numbers changing.
- After any fetch: `make plots && make tables`, then read `git diff data/`.

## Figures and tables

Two kinds of figure, and they never mix:

- **Hand-authored diagrams** — `figures/*.drawio`, exported by `make drawio`
  into `figures/generated/`. Architecture diagrams, conceptual figures.
- **Data figures** — `figures/*.yml`, rendered by `make plots` into
  `figures/generated/`.

**Prefer the config.** When asked for a new figure, write a `.yml` and check
whether `kind: line | bar | scatter` covers it before reaching for Python. Add a
`.py` only when it genuinely does not, and then implement `draw(data, cfg, ax)`
rather than `build(data, cfg)` unless the canvas itself must change — `draw`
keeps the house style, the labelling and the legend handling.

Renderers go through `paperkit.plotting.save_figure` and
`paperkit.tables.save_table`, which record provenance. Never call `fig.savefig`
or write a `.tex` table by hand.

`save_table` writes a **bare `tabular`** — no `\begin{table}`, no caption, no
label. Float placement, caption and label belong in `text.tex`, which is the
author's. Do not move them into the config or the script.

### draw.io authoring rules

Canonical style keys are in `tools/drawio_styles.py` (dict `S`). Import
from it rather than inventing colours.

1. **Hand-drawn look:** `sketch=1;curveFitting=1;jiggle=2` on every shape and edge.
2. **Typography:** `fontFamily=Helvetica`, `fontSize=14` minimum on every label.
3. **Fills:** white or transparent interiors; never an opaque full-page background rectangle.
4. **Strokes:** default black; accents `#6c8ebf` `#82b366` `#d79b00` `#b85450` `#9673a6` as *stroke only*.
5. **No `light-dark()` in exports** — the normalization script strips these.

Always commit both the `.drawio` source and its exports under
`figures/generated/`. Verify with `make check-figures`. Never reference a
`.drawio` file from LaTeX; use the `.pdf` or `.png` export.

## Reproducibility

Figures and tables are committed, so rebuilding an unchanged one must not change
a byte — otherwise every `make plots` dirties the tree and CI's reproducibility
gate becomes noise. Determinism has to hold **across machines**, and CI runs on a
different one than yours. Three things break it silently, so all three are
handled centrally and must stay handled:

- **Fonts.** Figures use only DejaVu Sans, which ships *inside* matplotlib. A
  system font such as Helvetica embeds different bytes on every machine.
- **Timestamps.** `save_figure` passes `metadata={"CreationDate": None}`.
- **Floats.** `make fetch` rounds and writes with an explicit `float_format`, and
  tables format to fixed decimals from the config's `decimals:`. numpy dispatches to whatever BLAS the
  wheel found — Accelerate on macOS, OpenBLAS in CI — and the summation orders
  disagree in the last bits.

Do not weaken any of these to make a diff go away.

## LaTeX conventions

- Build with `make paper`. It runs `latexmk -norc -r .latexmkrc`, which is
  deliberate: a global `~/.latexmkrc` must not silently participate in the build.
- Never commit `build/` or any LaTeX intermediate.
- Paths in a document are relative to its own directory and **must never reach
  outside it**.

### Templates and where the writing lives

`main.tex` is **generated**. A document's prose lives in four files that no
template switch ever touches:

| File | Holds |
|---|---|
| `metadata.tex` | title, short title, authors, affiliations, emails, ORCIDs, keywords |
| `abstract.tex` | the abstract, prose only — the template supplies `\begin{abstract}` |
| `text.tex` | every `\section` |
| `acronyms.tex` | `\newacronym` definitions |

```bash
make templates                                      # list what is available
make set-template PAPER=<doc> TEMPLATE=<name>       # switch
make new-paper NAME=lit-review TITLE="..."          # add another document (default: arxiv-custom)
```

**When asked to change the preamble, change the template source**
(`tools/templates/<name>/main.tex`), not a document's `main.tex`. A document's
copy is regenerated and its hash is recorded; editing it makes the next
`make set-template` refuse until forced.

Two rules keep prose portable across templates — if you break either, `text.tex`
is welded to one format again:

- **Cite with `\citep` / `\citet`.** Every template loads `natbib`; the IEEE
  templates use `IEEEtranN.bst` for exactly this reason (stock `IEEEtran.bst`
  renders `\citet` as `(author?)`).
- **Prose-level macros go in `tools/templates/_shared/researchcommon.sty`**,
  which every template loads — never in a single template's preamble. That is
  where the `contributions` environment lives.

Author blocks are per template (`\IEEEauthorblockN` vs `authblk`), so adding an
author means editing `metadata.tex` **and** one line of the template's
`main.tex`. This is deliberate; do not try to generate it.

### Author notes (`% NOTE:` comments)

`% NOTE: ...` comments in `docs/**/*.tex` are author instructions for prose that
is planned but not yet written.

- **Never remove, rewrite or override them** when editing nearby text.
- When drafting a section, treat the nearest `% NOTE:` as the specification for
  what belongs there.
- Remove one only after the described content is fully written **and** the user
  asks for cleanup.

### Acronyms

Managed with `glossaries-extra`.

- **Definitions:** `docs/<document>/acronyms.tex` — add `\newacronym{key}{SHORT}{long form}`
  there, never inline in the body. Use `plural=` / `shortplural=` when the first
  occurrence is `\glspl{key}`.
- **In prose:** `\gls{key}` / `\glspl{key}` mid-sentence; `\Gls{key}` / `\Glspl{key}` at sentence start.
- **Do not glossarify** proper names (DINOv2, PyTorch, NAVSIM) or affiliations.
- **Preamble order is load-bearing:** `glossaries-extra`, then `\makenoidxglossaries`,
  `\RestoreAcronyms`, `\setacronymstyle{long-short}`, then `\input{acronyms}` —
  all **before** `hyperref`.
- **Moving arguments:** in section titles wrap as `\texorpdfstring{\gls{key}}{SHORT}`.

### Bibliography

- Add entries to the **root** `references.bib` only, then `make sync-bib`.
- **Never fabricate a citation.** Verify every entry against DOI, DBLP or the
  publisher page before adding it. Prefer DBLP exports.
- Keys are `authorYEARkeyword`, e.g. `mnih2015human`.

## Overleaf

Overleaf links to **this repository** through its GitHub integration; the
coauthor selects `docs/<doc>/main.tex` as the project's main document. There is
no satellite repository and no `git subtree` — their edits come back with an
ordinary `git pull`.

What a coauthor sees is the *document directory*, so they will naturally add
bibliography entries to `docs/<doc>/references.bib` — the generated copy.
`make check-generated` reports that as drift. Resolve it in the direction that
keeps the root authoritative:

```bash
make bib-absorb PAPER=<doc>    # lift their new entries into references.bib
make sync-bib                  # regenerate the copies
```

Never resolve it by editing the copy, and never by deleting their entries.

## Staying in sync with the template

This repository was generated from `paper-template`, and the link is **two-way**.
Human-facing detail is in `docs/documentation/README.md`.

| Direction | Command |
|---|---|
| pull template improvements in | `make template-update` |
| send a fix back | `make template-contribute BRANCH=fix-x COMMITS="<sha>"` |

Rules that keep this working:

- **A commit destined for the template must touch only template files** —
  `tools/`, `Makefile`, `src/paperkit/`, `.github/`.
  `template-contribute` cherry-picks whole commits onto the template, so a
  commit that mixes a tooling fix with a paragraph of the paper cannot be sent
  anywhere. Split it first.
- **`refs/template/base` and the `Link template history at …` commit are
  bookkeeping. Do not delete them** — they are the merge base that makes
  `template-update` an ordinary three-way merge instead of an
  unrelated-histories conflict on every file.
- The `merge=ours` entries in `.gitattributes` need `git config
  merge.ours.driver true` in each clone. `bootstrap.sh` sets it.

## Scope discipline

- Prefer minimal diffs; match the existing naming and structure.
- **Only create git commits when the user explicitly asks.**
- Do not write paper narrative unless requested — section stubs are placeholders.
- Do not add dependencies without saying so.
- When a check fails, fix the cause. Do not disable the check.
