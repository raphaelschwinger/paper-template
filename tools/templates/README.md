# Document templates

Sources for the LaTeX skeleton of a document. They live under `tools/` because
they are inputs to `tools/set_template.py` and `tools/new_paper.py`, not
documents in their own right.

```bash
make set-template PAPER=paper-example TEMPLATE=ieee-conference
make set-template PAPER=paper-example TEMPLATE=arxiv-custom FORCE=1   # discard main.tex edits
```

| Template | Look | Vendored |
|---|---|---|
| `arxiv-custom` | **default** — our patched arxiv-style (single column); **edit it here** | `arxiv-custom.sty` |
| `arxiv-kourgeorge` | [kourgeorge/arxiv-style](https://github.com/kourgeorge/arxiv-style), upstream | `arxiv.sty` |
| `ieee-conference` | IEEEtran, two column, conference | — (TeX Live ships IEEEtran) |
| `ieee-journal` | IEEEtran, two column, transactions | — |

## What a template owns, and what it does not

A template owns `main.tex`: the document class, the packages, the title and
author block, and the bibliography style. **It owns none of your writing.** That
lives in the document directory and survives every switch:

| File | Owner |
|---|---|
| `main.tex` | the template (generated — do not hand-edit) |
| `metadata.tex` | you — title, authors, affiliations, keywords |
| `abstract.tex` | you |
| `text.tex` | you |
| `acronyms.tex` | you |

## Two rules that keep prose portable

**Cite with `\citep` and `\citet`.** Every template loads `natbib`, so both work
everywhere. The IEEE templates use `IEEEtranN.bst` rather than `IEEEtran.bst` for
this reason — the plain style renders `\citet` as `(author?)`. If a venue insists
on stock `IEEEtran.bst` for camera-ready, switch the `\bibliographystyle` and
confine yourself to `\cite`.

**Anything the prose uses must exist in every template.** New prose-level macros
and environments belong in `_shared/researchcommon.sty`, which every template
loads, not in one template's `main.tex`. Otherwise the first `\begin{...}` you
add welds `text.tex` to a single template again.

## Adding a template

1. `mkdir tools/templates/<name>/` with a `main.tex` and a `template.yml`.
2. `main.tex` is literal LaTeX — no placeholders. Everything variable comes from
   `\input{metadata}`, so the file can be opened and compiled as-is.
3. List every file the document directory needs in `assets:`, as a path relative
   to `tools/templates/`. They are copied in by basename and verified by
   `make check-generated`.
4. Load `researchcommon`, `natbib`, and the acronym block in the documented
   order (glossaries-extra before hyperref).
5. Add a `README.md` recording provenance and licence for anything vendored —
   including the **upstream commit it was taken from**, so a later refresh is a
   reviewable diff rather than a leap. See `arxiv-kourgeorge/README.md`.

## Author blocks

`metadata.tex` carries author names, affiliations, emails and ORCIDs, but each
template composes them into its own block — `\IEEEauthorblockN` and `authblk`
have nothing in common. Adding a second author therefore means uncommenting the
macros in `metadata.tex` **and** adding one line to `main.tex`. That is
deliberate: LaTeX conditionals over author counts are far more trouble than the
line they save.
