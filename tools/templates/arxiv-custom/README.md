# `arxiv-custom` — our patched arXiv preprint style

`arxiv-custom.sty` is **ours to edit**. It is the one vendored style file in this
repository that is not upstream's: change it here, run `make sync-bib`, and every
document using this template picks the change up.

## Provenance

Derived from [kourgeorge/arxiv-style](https://github.com/kourgeorge/arxiv-style)
(MIT, `License.txt`), by way of the Overleaf gallery copy used in the PretrainWM
paper. It diverges from upstream `master` in exactly three hunks, all tightening
vertical spacing:

| Line | Upstream | Here | Effect |
|---|---|---|---|
| `\paragraph` pre-skip | `1.5ex plus 0.5ex minus 0.2ex` | `0.5ex plus 0.2ex minus 0.05ex` | run-in paragraph headings hug the text |
| `\parskip` | `5.5pt` | `2pt` | tighter inter-paragraph spacing |
| before `\@date` | `\vskip 0.4in` | `\vskip 0.2in` | less air under the author block |

Upstream is vendored unmodified alongside, at
`tools/templates/arxiv-kourgeorge/arxiv.sty`, so the difference stays checkable:

```bash
diff tools/templates/arxiv-kourgeorge/arxiv.sty tools/templates/arxiv-custom/arxiv-custom.sty
```

Keep that diff small. If you find yourself adding packages or macros, they
probably belong in `_shared/researchcommon.sty` (where every template can use
them) rather than in this style file.

## What it provides

Only `geometry` and `fancyhdr` are required by the style — **do not re-import
either** in `main.tex`. Beyond page geometry it redefines the font sizes with
reduced leading, tightens `\@startsection` for all heading levels, restyles
`\@maketitle` (rules above and below the title, `\And`/`\AND` author separators),
and redefines the `abstract` environment as a centred, quoted block.

It also defines `\keywords{...}`, `\headeright` and `\undertitle`, all of which
`main.tex` uses.

## Not carried over from PretrainWM

The `contributions` box lived in PretrainWM's preamble, copy-pasted per
document. It now lives in `_shared/researchcommon.sty` so that prose using it
compiles under the IEEE templates too.

The ORCID icon (`_shared/orcid.pdf`) is shared with `arxiv-kourgeorge` rather
than duplicated per template.
