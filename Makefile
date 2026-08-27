# =============================================================================
# Paper repository — one entry point for documents, figures and tables.
#
#   make            list the targets
#   make setup      create the environment
#   make all        figures + tables -> paper, from the committed W&B cache
#   make fetch      refresh that cache from W&B (the only target needing a key)
#
# A figure is a file: figures/<name>.yml says where its numbers come from AND
# how it is drawn. Tables the same, under tables/.
#
# PAPER defaults to the first document under docs/ that has a main.tex, so the
# common case needs no arguments even after bootstrap.sh renames things.
# =============================================================================

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON := uv run python
PAPER ?= $(notdir $(patsubst %/,%,$(dir $(firstword $(wildcard docs/*/main.tex)))))

DOCS := $(patsubst docs/%/main.tex,%,$(wildcard docs/*/main.tex))
FIGURE_CONFIGS := $(wildcard figures/*.yml)
TABLE_CONFIGS := $(wildcard tables/*.yml)

.DEFAULT_GOAL := help
.PHONY: help all setup fetch figures plots tables configs drawio check-figures \
        sync-bib bib-absorb check-generated \
        templates set-template new-paper paper papers watch notes \
        wordcount diff arxiv \
        template-link template-update template-contribute \
        lint format test check clean clean-all

# --- meta --------------------------------------------------------------------

help:  ## show this help
	@echo "Paper repository — targets (PAPER=$(PAPER))"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-23s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Documents: $(DOCS)"

# Deliberately does NOT depend on `fetch`. Everything here builds from the
# committed data/*.csv, so `make all` works with no network and no API key —
# on a coauthor's laptop, in CI, and inside a TeX Live container.
all: figures tables paper  ## rebuild everything from the committed cache

setup:  ## create the uv environment
	uv sync
	@echo
	@echo "environment ready. Try: make all"

# --- data --------------------------------------------------------------------

# The one target that talks to W&B. Everything downstream reads data/*.csv.
fetch:  ## pull runs from W&B into data/  (REFRESH=1 to re-run the queries, DATASET=<kind>/<name> for one)
	$(PYTHON) tools/fetch.py $(if $(DATASET),--dataset $(DATASET),) $(if $(REFRESH),--refresh,) $(if $(DRYRUN),--dry-run,)

# --- figures and tables ------------------------------------------------------

figures: drawio plots  ## rebuild every figure (draw.io + data plots)

plots:  ## render figures/*.yml from the committed cache into figures/generated/
	@test -n "$(FIGURE_CONFIGS)" || { echo "no configs under figures/ — skipping"; exit 0; }
	$(PYTHON) tools/build.py figures $(if $(ONLY),--only $(ONLY),)

tables:  ## render tables/*.yml from the committed cache into docs/*/tables/
	@test -n "$(TABLE_CONFIGS)" || { echo "no configs under tables/ — skipping"; exit 0; }
	$(PYTHON) tools/build.py tables $(if $(ONLY),--only $(ONLY),)

configs:  ## list every figure and table config, with the document it targets
	$(PYTHON) tools/build.py --list

drawio:  ## export figures/*.drawio to figures/generated/ (needs the draw.io desktop CLI)
	@if ls figures/*.drawio >/dev/null 2>&1; then \
	  tools/build-drawio-svg.sh; \
	else \
	  echo "no .drawio sources under figures/ — skipping"; \
	fi

check-figures:  ## verify draw.io SVG exports are normalized for light/dark mode
	@if ls figures/generated/*.drawio.svg >/dev/null 2>&1; then \
	  $(PYTHON) tools/theme-drawio-svg.py --check; \
	else \
	  echo "no .drawio.svg exports — skipping"; \
	fi

# --- generated files ---------------------------------------------------------

sync-bib:  ## materialize the root references.bib and style assets into every document
	$(PYTHON) tools/materialize.py

bib-absorb:  ## lift bib entries a coauthor added on Overleaf into the root bib
	$(PYTHON) tools/bib_absorb.py --paper $(PAPER)

check-generated:  ## fail if any generated file is stale (bib, figures, tables, W&B cache)
	$(PYTHON) tools/check_generated.py

# --- documents ---------------------------------------------------------------

# `-norc -r .latexmkrc` makes the build hermetic: it skips the system and user
# rc files and reads only the project one. Without this, a global ~/.latexmkrc
# (a copy of Overleaf's, with overleaf_pre/post_process hooks, is common on
# these machines) silently participates in every build.
LATEXMK := latexmk -norc -r .latexmkrc

templates:  ## list the available document templates
	$(PYTHON) tools/set_template.py --list

set-template:  ## switch docs/$(PAPER) to TEMPLATE=<name> (FORCE=1 to discard main.tex edits)
	@test -n "$(TEMPLATE)" || { echo "usage: make set-template PAPER=<doc> TEMPLATE=<name> [FORCE=1]"; echo; $(MAKE) --no-print-directory templates; exit 1; }
	$(PYTHON) tools/set_template.py --paper $(PAPER) --template $(TEMPLATE) $(if $(FORCE),--force,)

new-paper:  ## scaffold another document: NAME=<dir> TITLE="..." [TEMPLATE=...] (default: arxiv-custom)
	@test -n "$(NAME)" || { echo 'usage: make new-paper NAME=<dir> TITLE="..." [TEMPLATE=<name>]'; exit 1; }
	$(PYTHON) tools/new_paper.py $(NAME) $(if $(TITLE),--title "$(TITLE)",) $(if $(TEMPLATE),--template $(TEMPLATE),)

paper:  ## compile docs/$(PAPER) -> docs/$(PAPER)/build/main.pdf
	@test -n "$(PAPER)" || { echo "error: no document found under docs/"; exit 1; }
	cd docs/$(PAPER) && $(LATEXMK)

papers:  ## compile every document under docs/
	@for doc in $(DOCS); do echo "--> $$doc"; $(MAKE) --no-print-directory paper PAPER=$$doc; done

watch:  ## continuously recompile docs/$(PAPER) on change
	cd docs/$(PAPER) && $(LATEXMK) -pvc

notes:  ## serve the MyST notes site (needs: npm install -g mystmd)
	cd notes && myst start

wordcount:  ## word count for docs/$(PAPER)
	cd docs/$(PAPER) && texcount -inc -sum main.tex

diff:  ## latexdiff docs/$(PAPER) against OLD=<git-ref>
	@test -n "$(OLD)" || { echo "usage: make diff OLD=<git-ref> [PAPER=...]"; exit 1; }
	@rm -rf build/$(PAPER)-diff && mkdir -p build/$(PAPER)-diff/old
	# Materialize the whole document as it was, so --flatten can resolve the
	# \input{}s on both sides. Diffing main.tex alone would show nothing: it is
	# generated from the template, and the prose lives in text.tex.
	git archive $(OLD) docs/$(PAPER) | tar -x -C build/$(PAPER)-diff/old --strip-components=2
	@test -f build/$(PAPER)-diff/old/main.tex || { \
	  echo "error: docs/$(PAPER) does not exist at $(OLD) — nothing to diff against."; \
	  echo "       Pick a ref where the document already existed:"; \
	  echo "         git log --oneline -- docs/$(PAPER)"; exit 1; }
	latexdiff --flatten build/$(PAPER)-diff/old/main.tex docs/$(PAPER)/main.tex \
	  > build/$(PAPER)-diff/main.tex
	@cp docs/$(PAPER)/references.bib build/$(PAPER)-diff/
	@cp docs/$(PAPER)/*.sty docs/$(PAPER)/*.cls docs/$(PAPER)/*.bst docs/$(PAPER)/orcid.pdf \
	  build/$(PAPER)-diff/ 2>/dev/null || true
	@cp -r docs/$(PAPER)/figures docs/$(PAPER)/tables build/$(PAPER)-diff/ 2>/dev/null || true
	cd build/$(PAPER)-diff && latexmk -norc -pdf -interaction=nonstopmode main.tex
	@echo "wrote build/$(PAPER)-diff/main.pdf"

arxiv: check-generated  ## flat submission bundle for arXiv / IEEE PDF eXpress
	$(MAKE) --no-print-directory paper PAPER=$(PAPER)
	@rm -rf build/$(PAPER)-arxiv build/$(PAPER)-arxiv.zip
	@mkdir -p build/$(PAPER)-arxiv
	cp docs/$(PAPER)/main.tex docs/$(PAPER)/references.bib build/$(PAPER)-arxiv/
	# The prose files main.tex \input{}s, plus any vendored class/style the
	# template needs (arxiv.sty is not on arXiv's TeX Live either) and the
	# ORCID icon the arxiv templates embed in the author block.
	@for f in metadata.tex abstract.tex text.tex acronyms.tex orcid.pdf; do \
	  cp "docs/$(PAPER)/$$f" build/$(PAPER)-arxiv/ 2>/dev/null || true; \
	done
	@cp docs/$(PAPER)/*.sty docs/$(PAPER)/*.cls docs/$(PAPER)/*.bst build/$(PAPER)-arxiv/ 2>/dev/null || true
	# Ship the built .bbl so the submission system never has to run BibTeX.
	cp docs/$(PAPER)/build/main.bbl build/$(PAPER)-arxiv/
	# Flatten figures/ and tables/ into the top level. \graphicspath's {./}
	# fallback finds the figures; the \input{tables/x} paths are rewritten
	# below, since arXiv rejects a bundle whose \input points at a directory
	# that the flattening removed.
	@cp docs/$(PAPER)/figures/*.pdf docs/$(PAPER)/figures/*.png build/$(PAPER)-arxiv/ 2>/dev/null || true
	@cp docs/$(PAPER)/tables/*.tex build/$(PAPER)-arxiv/ 2>/dev/null || true
	@if ls docs/$(PAPER)/tables/*.tex >/dev/null 2>&1; then \
	  perl -pi -e 's/\\input\{tables\//\\input\{/g' build/$(PAPER)-arxiv/*.tex; \
	fi
	cd build/$(PAPER)-arxiv && zip -r ../$(PAPER)-arxiv.zip .
	@echo "wrote build/$(PAPER)-arxiv.zip"

# --- upstream template --------------------------------------------------------
#
# This repository was generated from paper-template. "Use this template" copies a
# tree and not a history, so the link has to be made explicitly before any of
# this works — see tools/template_sync.py.
#
# A fix you make here to tools/, the Makefile or a LaTeX template is worth
# sending back: the next paper starts from it.

template-link:  ## establish the template merge base (once): make template-link [REF=<commit>]
	$(PYTHON) tools/template_sync.py link $(if $(REF),--ref $(REF),)

template-update:  ## merge improvements made in the upstream template into this repo
	$(PYTHON) tools/template_sync.py update

template-contribute:  ## send a fix back: make template-contribute BRANCH=fix-x COMMITS="<sha>..."
	@test -n "$(BRANCH)" -a -n "$(COMMITS)" || { echo 'usage: make template-contribute BRANCH=<name> COMMITS="<sha> [<sha>...]"'; exit 1; }
	$(PYTHON) tools/template_sync.py contribute --branch $(BRANCH) $(COMMITS)

# --- quality -----------------------------------------------------------------

check: lint test check-generated check-figures  ## everything CI checks

lint:  ## ruff check + format check
	uv run ruff check .
	uv run ruff format --check .

format:  ## apply ruff formatting and autofixes
	uv run ruff check --fix .
	uv run ruff format .

test:  ## run the test suite
	uv run pytest

# --- cleaning ----------------------------------------------------------------

clean:  ## remove build artifacts (keeps committed figures, tables and data)
	@for doc in $(DOCS); do (cd docs/$$doc && latexmk -C >/dev/null 2>&1) || true; done
	rm -rf build docs/*/build notes/_build
	find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

clean-all: clean  ## also remove the environment and the raw W&B scratch directory
	rm -rf .venv data/raw wandb
