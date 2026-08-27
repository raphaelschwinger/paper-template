# `tables/` — result tables

One file per table, exactly like `figures/`. `final_scores.yml` says where its
numbers come from and how they are laid out, and renders itself:

```
tables/final_scores.yml  ──make tables──►  docs/<document>/tables/final_scores.tex
```

```bash
make tables                       # render every config here
make tables ONLY=final_scores     # just one
make fetch DATASET=tables/final_scores REFRESH=1
```

## The config

```yaml
document: paper-example

data:                             # same schema as a figure's `data:` block
  kind: summary
  filters: {tags: paper-v1, state: finished}
  keys: [eval/return]
  config: [method, seed]
  aggregate: {by: [method], of: eval/return, stats: [mean, std, count]}

table:
  columns:                        # order defines the layout
    - {from: method, as: Method}
    - {from: mean, as: Score, decimals: 2}
    - {from: std, as: SD, decimals: 2}
    - {from: count, as: Seeds, decimals: 0}
  sort: {by: mean, ascending: false}   # `by` accepts the source name or the header
  align: lrrr                     # optional; default is l for text, r for numbers
```

## What is written, and what stays yours

The output is a **bare `tabular`** — no `\begin{table}`, no caption, no label.
Float placement, the caption and the label belong to the prose:

```latex
\begin{table}[!t]
  \centering
  \caption{Final scores, mean over five seeds.}
  \label{tab:final_scores}
  \input{tables/final_scores.tex}
\end{table}
```

This split is deliberate. A caption is writing, and writing lives in `text.tex`
where it can be revised without touching the data pipeline.

## When the built-in layout is not enough

Put a `.py` beside the config defining `build`:

```python
# tables/ablation.py
def build(data, cfg):
    """Return the DataFrame to typeset."""
    ...
```

Formatting, LaTeX escaping, writing and provenance stay with the renderer, so a
custom table still looks like the others and is still checked for staleness.

## Rules

- **Never hand-edit the output `.tex`.** `make check-generated` verifies the
  table's *inputs*, not its bytes, so a hand edit survives the check and quietly
  desynchronises the paper from its data. Change the config.
- Numbers are formatted to fixed decimals, never float repr: repr differs in the
  last digit between machines and would churn the committed file.
