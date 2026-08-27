# Paper Template

A repository for **the paper**, kept separate from the code that produced its
numbers — but not disconnected from it. Figures and tables are declared as
config files, built by fetching runs from Weights & Biases into a committed,
human-readable cache, so the paper compiles anywhere: a coauthor's laptop, a TeX
Live container, Overleaf.

> Agents: read [`AGENTS.md`](AGENTS.md) first.

## Why

The usual advice is to put the paper and the experiments in one repository, so
that a figure has a traceable path back to the code that drew it. That works,
and it costs a great deal: one lockfile for torch and latexmk, one CI matrix for
training runs and PDF builds, one visibility setting for code you may want
private and a preprint you want public.

This template takes the traceability and drops the coupling. The experiment
repository stays a normal experiment repository. The paper repository is added
to it as a **git submodule**, so you (and an AI agent) still work in one tree —
but the two are separate repositories, and the only thing crossing between them
is the experiment tracker.

```
your-code-repo/                 e.g. from lightning-hydra-template
  src/  configs/  ...           experiments, tracked in W&B
  paper/                        <-- this repository, as a submodule
```

The paper never imports the code. It reads the CSVs under `data/`, which
`make fetch` wrote from W&B, and which are committed. That is what makes the PDF
in the repository verifiable rather than merely present.

```
references.bib          single source of truth for every document's bibliography
paper.yml               the W&B connection and the house style — nothing else
figures/<name>.yml      one figure: its data AND its styling -> figures/generated/
figures/<name>.drawio   hand-authored diagram -> figures/generated/
tables/<name>.yml       one table:  its data AND its layout  -> docs/<doc>/tables/
data/                   the fetched numbers + the run IDs behind them (committed)
src/paperkit/           the renderers those configs drive
docs/<document>/        one LaTeX document each; compiles standalone
docs/documentation/     this handbook, after bootstrap.sh moves it here
notes/                  MyST site for background notes
tools/                  fetch, build, draw.io export, materialization, staleness checks, template sync
  templates/              LaTeX document templates (IEEE, arXiv)
```

## Quickstart

```bash
# 1. create the paper repository from this template
gh repo create my-paper --template raphaelschwinger/paper-template --private

# 2. attach it to the code repository whose experiments it reports on
cd ~/git/my-experiments
git submodule add https://github.com/<you>/my-paper.git paper
cd paper

# 3. name it, and wire up the link back to this template
./bootstrap.sh
```

Then, from inside `paper/`:

```bash
make            # list every target
make setup      # uv sync
make all        # figures -> tables -> paper, from the committed cache
make check      # everything CI checks
```

The shipped example runs in a second and exercises the whole chain, so a fresh
clone is provably working before you point it at your own W&B project.

`bootstrap.sh` also wires up a `template` remote, so this paper can keep pulling
improvements from the template it came from — and push fixes back. See
[below](#staying-in-sync-with-the-template).

### Working in the submodule

All `make` targets run from **inside** `paper/`. A submodule is an ordinary git
repository with its own branches and its own history; commit and push in it as
you would anywhere, and commit the updated pointer in the parent repository
afterwards.

```bash
cd paper && git add -A && git commit -m "..." && git push
cd .. && git add paper && git commit -m "Bump paper"
```

Cloning the code repository later needs `git submodule update --init` to
populate `paper/`.

## How it fits together

```
   figures/learning_curve.yml        one file: the query AND the styling
        │
        │  make fetch                                         [needs an API key]
        ▼
   data/figures/learning_curve.csv  +  data/wandb.lock.yml         [committed]
        │
        │  make plots                                    [no network, no key]
        ▼
   figures/generated/learning_curve.pdf                           [committed]
        │  copied into docs/<doc>/figures/ so Overleaf can compile
        │
        │   references.bib ──make sync-bib──► docs/<doc>/references.bib
        ▼
   docs/<doc>/main.tex   make paper
```

Tables work identically, from `tables/<name>.yml` to
`docs/<doc>/tables/<name>.tex`.

Four ideas do the work:

**A figure is a file.** `figures/learning_curve.yml` says where its numbers come
from *and* how it is drawn, and renders itself — no Python. There is no central
dataset registry to keep in step with the figures that read it, and no
twenty-five-line plotting script per figure. When the built-in renderers cannot
draw what you need, a `.py` beside the config takes over the drawing and keeps
everything else.

**One bibliography.** Only the root `references.bib` is edited by hand. Each
document gets a verbatim generated copy, because a document directory has to
compile in isolation — Overleaf has no access to the repository root, and
`make arxiv` flattens the directory into a bundle. `make check-generated` fails
if a copy has drifted.

**The cache is committed, and it is CSV.** Committed, because a figure built
live from an API is a figure nobody else can rebuild. CSV rather than Parquet,
because it renders in the GitHub UI and diffs as text: a pull request that moves
the paper's numbers shows *which* numbers moved, in the review.

**Everything generated carries provenance.** Each figure and table records the
config or script that made it and the content hash of every input. Change the
data without rebuilding and the build fails instead of shipping a stale result.

## Adding a figure

A figure is one file. Create `figures/<name>.yml`:

```yaml
document: paper-neurips26        # Overleaf copy -> docs/paper-neurips26/figures/

data:                            # entity/project/round inherited from paper.yml
  kind: history                  # history (per-step) | summary (per-run)
  filters: {tags: paper-v1, state: finished}
  keys: [_step, eval/return]
  config: [method, seed]         # run config values joined onto every row
  samples: 1000
  aggregate: {by: [method, _step], of: eval/return, stats: [mean, std, count]}

plot:
  kind: line                     # line | bar | scatter
  x: _step
  y: mean
  band: std                      # shaded +/- band
  group: method                  # one series per value
  order: [pretrained, baseline]
  colors: {pretrained: blue}
  xlabel: training step
  ylabel: score
  ylim: [0, null]                # null = leave it to matplotlib
  legend: {loc: lower right}
```

```bash
make fetch DATASET=figures/<name> REFRESH=1   # pull its runs, pin them
make plots ONLY=<name>                        # draw it
make configs                                  # what exists, and where it lands
```

A table is the same shape, under `tables/<name>.yml`, with a `table:` block
instead of `plot:`:

```yaml
table:
  columns:
    - {from: method, as: Method}
    - {from: mean, as: Score, decimals: 2}
    - {from: count, as: Seeds, decimals: 0}
  sort: {by: mean, ascending: false}
```

`paper.yml` holds only the W&B connection and the house style — the width, the
palette, the legend defaults every figure would otherwise repeat. It declares no
datasets, so it never becomes a registry that has to be kept in step with the
figures reading it.

Full schemas: [`figures/README.md`](figures/README.md) and
[`tables/README.md`](tables/README.md).

### When a config is not enough

Put a `.py` beside it with the same stem. It still gets its data and its style
from the `.yml`; it only takes over the drawing.

```python
# figures/ablation.py
def draw(data, cfg, ax):
    ...            # `data` is the fetched DataFrame, `cfg` the merged config
```

The figure is still created at the configured size, labelled, legended, saved
and given provenance. For full control over the canvas, define
`build(data, cfg)` returning a `Figure` instead. Tables use `build(data, cfg)`
returning the DataFrame to typeset.

## Where the numbers come from

Each config owns its query, and `make fetch` resolves it:

```bash
make fetch REFRESH=1              # run every query, report the run-set diffs, pin
make fetch                        # re-read the PINNED runs only
make fetch DATASET=figures/curves # just one config
make fetch REFRESH=1 DRYRUN=1     # what would it match? write nothing
```

A query like *"every finished run tagged paper-v1"* does not name a fixed set of
runs: a sweep finishing overnight changes what it matches, and the paper's
numbers move without anyone touching the repository. So `REFRESH=1` records what
it matched, into `data/wandb.lock.yml`, and a plain `make fetch` re-reads exactly
those runs. Widening the set is deliberate and reviewable — the run-set diff is
printed, and the number diff is in `git diff data/`.

Configs that resolve to an identical query are fetched **once** and the result
copied, so a figure and the table beside it stay independent snapshots without
querying W&B twice — which is slower and can even disagree if a run finishes in
between.

**Editing a config's `data:` block without re-fetching is a build failure.** The
lock records a hash of it; `make check-generated` compares them and tells you to
`make fetch REFRESH=1`. Editing the `plot:` block does *not* invalidate the data
— restyling a figure is not a change to what it reports.

`WANDB_API_KEY` is needed for `make fetch` and for nothing else. Every other
target builds from the committed CSVs.

## More than one document

A conference paper, its journal extension, a literature study and a thesis
chapter all cite the same work and report the same runs. They live side by side
under `docs/`, sharing one `references.bib` and one cache:

```bash
make new-paper NAME=lit-review TITLE="What We Know About X"
make papers                 # compile all of them
make paper PAPER=lit-review # or just one
```

Each config names its target document, so the same data can be plotted
differently for a four-page workshop paper and a thesis chapter — two configs,
one query, fetched once.

## Switching venue formats

Your writing lives in `metadata.tex`, `abstract.tex`, `text.tex` and
`acronyms.tex`. `main.tex` — the document class, packages and author block — is
generated from a template, so changing format does not touch a word of the prose:

```bash
make templates                                          # list them
make set-template PAPER=paper-example TEMPLATE=ieee-conference
make paper
```

| Template | Look |
|---|---|
| `arxiv-custom` | **default** — our patched arxiv-style (single column); edit it in `tools/templates/` |
| `arxiv-kourgeorge` | [kourgeorge/arxiv-style](https://github.com/kourgeorge/arxiv-style), upstream |
| `ieee-conference` | IEEEtran, two column, conference |
| `ieee-journal` | IEEEtran, two column, transactions |

Cite with `\citep` / `\citet` (every template loads `natbib`) and put any new
prose-level macro in `tools/templates/_shared/researchcommon.sty`. Those two
habits are what keep `text.tex` compiling under all four — CI checks it on every
push.

## Overleaf

Overleaf links to **this repository** directly, through its GitHub integration.
There is no satellite repository and no `git subtree`:

1. In Overleaf: **Menu → GitHub → link** this repository.
2. **Menu → Settings → Main document** → `docs/<doc>/main.tex`.

Coauthors then work in Overleaf and their edits come back with a plain
`git pull`. Because they see the document directory rather than the repository
root, they will add bibliography entries to `docs/<doc>/references.bib` — the
generated copy. Lift them into the root bib rather than resolving by hand:

```bash
make bib-absorb PAPER=<doc>
make sync-bib
```

With several documents in the project, Overleaf compiles whichever one is set as
the main document. Switching is a settings change, not a repository change.

## Requirements

| Tool | For | Install |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python environment | `brew install uv` |
| TeX Live / MacTeX | `latexmk`, `pdflatex` | `brew install --cask mactex` |
| draw.io desktop | schematic export (optional) | `brew install --cask drawio` |
| `mystmd` | notes site (optional) | `npm install -g mystmd` |
| `gh` | creating the repository (optional) | `brew install gh` |

Python 3.12. No torch, no CUDA — this repository compiles a paper.

`.gitattributes` marks the generated files under `docs/` as `merge=ours`, which
only takes effect once a driver by that name exists. `bootstrap.sh` sets it; on a
clone that skipped bootstrap, set it once — it is per-clone config and cannot be
committed:

```bash
git config merge.ours.driver true
```

## Common tasks

| Task | Command |
|---|---|
| List every figure and table config | `make configs` |
| Refresh the data from W&B | `make fetch REFRESH=1` |
| Rebuild all figures | `make figures` |
| Rebuild one figure | `make plots ONLY=<name>` |
| Rebuild all tables | `make tables` |
| Compile the paper | `make paper` |
| Add another document | `make new-paper NAME=lit-review TITLE="..."` |
| List document templates | `make templates` |
| Switch venue format | `make set-template PAPER=<doc> TEMPLATE=<name>` |
| Add a bibliography entry | edit `references.bib`, then `make sync-bib` |
| Lift a coauthor's bib entries | `make bib-absorb PAPER=<doc>` |
| Word count | `make wordcount` |
| Diff against an earlier version | `make diff OLD=<git-ref>` |
| Submission bundle (arXiv / PDF eXpress) | `make arxiv` |
| Serve the notes site | `make notes` |
| Pull improvements from the template | `make template-update` |
| Send a fix back to the template | `make template-contribute BRANCH=fix-x COMMITS="<sha>"` |

## Staying in sync with the template

The tooling in `tools/`, the `Makefile`, `src/paperkit/` and the LaTeX templates
are shared infrastructure. A fix you make to them while writing *this* paper
should reach the next one — otherwise every paper repository silently forks the
toolchain on the day it is created. That return path is the reason this template
exists as a repository rather than a folder you copy.

GitHub's "Use this template" copies a tree, **not a history** — so a generated
repository shares no commit with the template and `git merge` refuses as
unrelated. `bootstrap.sh` closes that gap on the way through: it adds a
`template` remote from `.template-upstream.yml` and records a merge base with an
`ours` merge that changes not one file. From then on:

```bash
make template-update    # merge template improvements made since your copy
```

It is an ordinary three-way merge carrying only what came after your link point.
**Expect conflicts in the handful of files `bootstrap.sh` rewrote for you** — the
renamed document under `docs/`, its `metadata.tex`, `paper.yml`. Keep your
version in those. The substance of a template update lands in `tools/`,
`Makefile`, `src/paperkit/` and `.github/`, which bootstrap
does not touch. This handbook is moved rather than edited, so updates to it
follow the rename into `docs/documentation/README.md` and merge cleanly; your own
root `README.md` is yours alone and the template never touches it.

To take one fix rather than everything, cherry-pick instead:

```bash
git fetch template && git log --oneline HEAD..template/main
git cherry-pick -x <commit>
```

Going the other way, your commits cannot be pushed to the template directly —
they carry your paper. `template-contribute` branches off the template tip and
replays only the commits you name onto it:

```bash
make template-contribute BRANCH=fix-latexmk COMMITS="a1b2c3d"
```

It prints the `gh repo fork` / `git push` / `gh pr create` lines to finish with.
Keep such a commit **generic and self-contained** — a fix to `tools/`, a Makefile
target, a template preamble, a new `plot.kind` — and it will apply cleanly
upstream. A commit that mixes a tooling fix with a paragraph of your paper cannot
be sent anywhere; split it first.

On a repository that was bootstrapped before any of this existed, link it once by
naming the template commit you originally copied:

```bash
make template-link REF=<commit>     # git log --oneline template/main to find it
```

Without `REF` it links at the current tip, which silently writes off every
improvement made before today — the command says so and asks first.

### The LaTeX styles

`arxiv.sty` under `tools/templates/arxiv-kourgeorge/` is vendored verbatim from
[kourgeorge/arxiv-style](https://github.com/kourgeorge/arxiv-style) at a pinned
commit recorded in that directory's `README.md`; refreshing it is a `curl` and a
reviewable diff. It has no automated return path — a fix there is an ordinary
GitHub PR to that repository. `arxiv-custom.sty` is deliberately **ours**, a
patched fork that goes nowhere upstream; edit it in place.

## Conventions

Documented in [`AGENTS.md`](AGENTS.md), which is written for AI assistants but is
the authoritative reference for humans too. The parts worth knowing before your
first commit:

- Never hand-edit a generated file; regenerate it.
- Figures and tables must rebuild byte for byte — CI enforces it on a different
  machine than yours. Never let one depend on a system font or a timestamp.
- The cache is generated. `make fetch` overwrites it; edits there are lost.
- Verify every citation. Never fabricate one.
- Commit both `.drawio` sources and their exports.

## License

Add your own before publishing.

---

## The project README

Everything above documents the *template*. A repository generated from it needs a
README about the paper, not about the machinery — so `bootstrap.sh` moves this
file to `docs/documentation/README.md` (verbatim, so template updates to it keep
merging cleanly) and writes the skeleton below to `README.md`, substituting the
`{{...}}` placeholders with what you answered.

To regenerate or restore it later, copy the block between the two
`PROJECT-README-SKELETON` markers in `docs/documentation/README.md`.

<!-- PROJECT-README-SKELETON:START -->
<div align="center">

# {{PROJECT_NAME}}

[![python](https://img.shields.io/badge/-Python_3.12-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/-uv-de5fe9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![W&B](https://img.shields.io/badge/tracking-W%26B-ffbe00?logo=weightsandbiases&logoColor=black)](https://wandb.ai/)
[![template](https://img.shields.io/badge/-paper--template-017F2F?style=flat&logo=github&labelColor=gray)]({{TEMPLATE_URL}})
<br>
[![paper](https://img.shields.io/badge/paper-arXiv:XXXX.XXXXX-b31b1b.svg)](https://arxiv.org/)

**{{PAPER_TITLE}}**

{{AUTHOR_NAME}} · {{AFFILIATION}}

</div>

## Description

<!-- What question does this paper answer, and what is the short version of the
     answer? Two or three sentences — the abstract lives in the paper. -->

## Building the paper

```bash
make setup                 # uv sync
make all                   # figures -> tables -> paper
make paper                 # docs/{{PAPER_SLUG}}/build/main.pdf
make check                 # what CI checks
```

Needs Python 3.12, [uv](https://docs.astral.sh/uv/) and a TeX distribution.
**No W&B access is required** — the numbers are committed under `data/`.

## The figures and tables

Each one is a config file declaring the runs it reports and how it is drawn:

```bash
make configs               # every figure and table, and where it lands
make plots ONLY=<name>     # redraw one
```

## Refreshing the numbers

```bash
make fetch REFRESH=1       # re-run every config's query, repin the run set
make plots && make tables  # rebuild what depends on them
git diff data/             # review every number that moved
```

Needs `WANDB_API_KEY`. The runs are in
[`{{WANDB_ENTITY}}/{{WANDB_PROJECT}}`](https://wandb.ai/{{WANDB_ENTITY}}/{{WANDB_PROJECT}}),
and the exact ones behind this paper are pinned in `data/wandb.lock.yml`.

## Layout

| Path | Holds |
|---|---|
| `docs/{{PAPER_SLUG}}/` | the paper — write in `metadata`/`abstract`/`text`/`acronyms.tex` |
| `docs/documentation/` | how this repository works: data, figures, Overleaf, the template |
| `notes/` | background notes (MyST) |
| `references.bib` | the single bibliography; the only one edited by hand |
| `paper.yml` | the W&B connection and the house style |
| `figures/`, `tables/` | one config per figure and table: its data and its styling |
| `figures/generated/` | rendered figure PDFs and draw.io exports |
| `data/` | the fetched numbers, committed as CSV |

Figures and tables are committed and reproducible: CI rebuilds them from the
committed data and requires the files back byte for byte. Never hand-edit a
generated file — regenerate it. The rules are in
[`docs/documentation/README.md`](docs/documentation/README.md) and, for AI
assistants, [`AGENTS.md`](AGENTS.md).

## The code

The experiments behind this paper live in {{CODE_REPO}}. This repository is
normally checked out as a submodule of it, under `paper/`.

## Citation

```bibtex
@misc{{{CITE_KEY}},
  title  = {{{PAPER_TITLE}}},
  author = {{{AUTHOR_NAME}}},
  year   = {{{YEAR}}},
}
```

## License

<!-- Add one before publishing. -->
<!-- PROJECT-README-SKELETON:END -->
