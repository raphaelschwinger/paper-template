# `figures/` — source figures

One directory for every figure the paper shows: data configs, optional custom
renderers, and hand-authored draw.io diagrams. **Generated output is not here**
— it lands in `figures/generated/`.

```
figures/learning_curve.yml   ──make plots──►   figures/generated/learning_curve.pdf
figures/architecture.drawio  ──make drawio──►  figures/generated/architecture.drawio.{svg,png,pdf}
```

A document directory has to compile standalone (Overleaf, `make arxiv`), so
`make plots` also copies the PDF into `docs/<document>/figures/`. That copy is
generated; never hand-edit it.

```bash
make plots                              # render every config here
make plots ONLY=learning_curve          # just one
make drawio                             # export every figures/*.drawio
make configs                            # what exists, and where it lands
make fetch DATASET=figures/learning_curve REFRESH=1   # refresh its data
```

There is no central dataset registry: each config owns its query, and its
numbers land in `data/figures/<name>.csv`. `paper.yml` supplies only the W&B
connection and the house style, which any config may override.

## Data figures

```yaml
document: paper-example         # which docs/<document>/ gets the Overleaf copy

data:                           # entity/project/round inherited from paper.yml
  kind: history                 # history (per-step) | summary (per-run)
  filters: {tags: paper-v1, state: finished}
  keys: [_step, eval/return]
  config: [method, seed]        # run config values joined onto every row
  samples: 1000
  aggregate: {by: [method, _step], of: eval/return, stats: [mean, std, count]}

plot:
  kind: line                    # line | bar | scatter
  x: _step
  y: mean
  band: std                     # shaded +/- band (line), error bars (bar)
  group: method                 # one series per value
  order: [pretrained, baseline] # series order; anything omitted is appended
  colors: {pretrained: blue}    # names from the palette, or any matplotlib colour
  xlabel: training step
  ylabel: score
  xlim: [0, null]               # null = leave it to matplotlib
  ylim: [0, null]
  xscale: log                   # optional
  legend: {loc: lower right}    # or `legend: false` to suppress
  width: 3.3                    # inches; inherited from paper.yml
  height: 2.2
```

Aggregate in `data:`, not in the plot. Collapsing seeds before the CSV is
written is what keeps the committed file small enough to read and to diff.

### When the built-in renderers are not enough

Put a `.py` beside the config, with the same stem. It still gets its data and
its style from the `.yml`; it only takes over the drawing.

```python
# figures/ablation.py
def draw(data, cfg, ax):
    """`data` is the fetched DataFrame, `cfg` the merged config."""
    ...
```

The figure is created at the configured size, then labelled, limited, legended
and saved from the same `plot:` keys — so a custom figure still obeys the house
style and still records provenance. For full control over the canvas (a grid of
subplots, a twin axis), define `build(data, cfg)` returning a `Figure` instead;
then the `plot:` keys are yours to apply or ignore.

Both forms are picked up automatically. `make configs` shows which figures use
one.

## draw.io diagrams

Hand-authored architecture diagrams and conceptual figures live here as
`*.drawio` sources. Export with `make drawio`; the SVG/PNG/PDF land in
`figures/generated/`. Commit **both** the `.drawio` and its exports. LaTeX
includes the `.pdf` (or `.png`) from the document's `figures/` copy, never the
`.drawio`.

`tools/emit_drawio.py` lets you *generate* a `.drawio` file from a script while
keeping it editable by hand afterwards — useful for diagrams with repetitive
structure.

Canonical style keys are in `tools/drawio_styles.py` (dict `S`); import from it
rather than inventing colours.

| Rule | Value |
|---|---|
| Hand-drawn look | `sketch=1;curveFitting=1;jiggle=2` on every shape and edge |
| Typography | `fontFamily=Helvetica`, `fontSize=14` minimum |
| Fills | white or transparent; never an opaque full-page background rect |
| Strokes | black by default |
| Accents (stroke only) | `#6c8ebf` `#82b366` `#d79b00` `#b85450` `#9673a6` |

The accent palette is chosen to survive a CSS dark-mode
`filter: invert(1) hue-rotate(180deg)`, which is what the notes site applies.
`tools/theme-drawio-svg.py` enforces this on export; `--check` mode fails if an
export has drifted. It is the same palette `paperkit.plotting.COLORS` uses, so a
diagram and a data plot in the same paper agree.

Requires the draw.io desktop CLI: `brew install --cask drawio`.

A document directory cannot reach up into this one. `make plots` copies data
figures automatically. For a draw.io export, copy the PDF or PNG you need into
`docs/<document>/figures/` and commit it there — never write
`\includegraphics{../../figures/generated/...}`, which breaks Overleaf and
`make arxiv` alike.

## Rules

- **Never hand-edit a generated PDF**, and never edit `data/figures/*.csv`.
  Both are regenerated. Generated files live in `figures/generated/`.
- Rebuilding an unchanged figure must not change a byte — CI enforces it on a
  different machine. That is why figures use only DejaVu Sans (it ships inside
  matplotlib) and strip PDF timestamps. Do not work around either.
- A figure whose config you delete is reported by `make check-generated`: the
  committed PDF has nothing left that can rebuild it.
