# latexmk configuration for this document.
#
# Everything is set explicitly rather than inherited, because a global
# ~/.latexmkrc may exist (a copy of Overleaf's, with overleaf_pre_process
# hooks) and must not change what this project builds.
#
# Note there is deliberately NO `ensure_path('BIBINPUTS', ...)` here: this
# directory must compile standalone — Overleaf builds it in isolation, and
# `make arxiv` flattens it — so it never reaches up the tree. `references.bib`
# sits beside main.tex as a generated copy, so `\bibliography{references}`
# resolves identically here, on Overleaf, and in the flattened bundle.

# Build inside this directory (gitignored by the root `build/` pattern). Kept
# relative rather than pointing at the repository-root `build/` so that renaming
# this directory — which bootstrap.sh does — cannot break the build, and so a
# bare `latexmk` and VS Code LaTeX Workshop agree with `make paper`.
$out_dir = 'build';
$pdf_mode = 1;
$pdflatex = 'pdflatex -interaction=nonstopmode -file-line-error %O %S';
$bibtex_use = 2;          # run bibtex, and clean .bbl on `latexmk -C`
@default_files = ('main.tex');
