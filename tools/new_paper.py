#!/usr/bin/env python3
"""Scaffold an additional document under docs/.

The template ships with one paper; this repository earns its keep when there
are several (a conference paper, its journal extension, a literature study, a
thesis chapter) sharing one bibliography and one W&B cache.

    uv run python tools/new_paper.py paper-neurips26 --title "Some Title"
    uv run python tools/new_paper.py thesis --template ieee-conference --title "..."
    uv run python tools/set_template.py --list      # what templates exist

Creates the directory with the prose files you own (`metadata.tex`,
`abstract.tex`, `text.tex`, `acronyms.tex`), the generated `main.tex` for the
chosen template, the materialized `references.bib` and style assets, plus
`.latexmkrc` and `AGENTS.md`. Never touches an existing directory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import set_template
from _common import list_templates, repo_root, root_bib

DEFAULT_TEMPLATE = "arxiv-custom"

LATEXMKRC = """\
# latexmk configuration for this document. Everything is set explicitly so a
# global ~/.latexmkrc cannot change what this project builds.
#
# No `ensure_path('BIBINPUTS', ...)`: this directory must compile standalone —
# on Overleaf and in the flattened `make arxiv` bundle alike — so it never
# reaches up the tree. `references.bib` sits beside main.tex as a generated copy.
$out_dir = 'build';
$pdf_mode = 1;
$pdflatex = 'pdflatex -interaction=nonstopmode -file-line-error %O %S';
$bibtex_use = 2;
@default_files = ('main.tex');
"""

ACRONYMS = """\
% Acronym definitions for this document. Define them here, never inline.
% See the root AGENTS.md, "Acronyms", for the full policy.

% \\newacronym{rl}{RL}{reinforcement learning}
"""

METADATA = """\
%% Document metadata — title, authors, keywords.
%%
%% THIS FILE IS YOURS. It is template-agnostic: `make set-template` rewrites
%% main.tex but never touches this file, so switching between IEEE and arXiv
%% formats keeps your title and author list.
%%
%% Each template composes these macros into its own author block. Adding an
%% author means uncommenting the macros below AND adding one line to main.tex —
%% see tools/templates/README.md, "Author blocks".

\\newcommand{{\\PaperTitle}}{{{title}}}

%% Running head. Keep it short — it has to fit across the page.
\\newcommand{{\\PaperShortTitle}}{{{short_title}}}

%% Comma-separated. Used for \\IEEEkeywords and arxiv.sty's \\keywords.
\\newcommand{{\\PaperKeywords}}{{}}

%% PDF subject line — arXiv categories work well here, e.g. cs.LG, cs.AI.
\\newcommand{{\\PaperSubject}}{{}}

%% Flat author list for the PDF metadata.
\\newcommand{{\\PaperAuthorList}}{{Author Name}}

%% --- Authors ----------------------------------------------------------------
\\newcommand{{\\AuthorOneName}}{{Author Name}}
\\newcommand{{\\AuthorOneAffil}}{{Institution}}
\\newcommand{{\\AuthorOneEmail}}{{author@example.org}}
\\newcommand{{\\AuthorOneOrcid}}{{https://orcid.org/0000-0000-0000-0000}}

% \\newcommand{{\\AuthorTwoName}}{{Second Author}}
% \\newcommand{{\\AuthorTwoAffil}}{{Institution}}
% \\newcommand{{\\AuthorTwoEmail}}{{second@example.org}}
% \\newcommand{{\\AuthorTwoOrcid}}{{https://orcid.org/0000-0000-0000-0000}}
"""

ABSTRACT = """\
%% The abstract, prose only — no \\begin{abstract}, the template supplies that.
%% THIS FILE IS YOURS: `make set-template` never touches it.

% NOTE: write the abstract last.
"""

TEXT = """\
%% The body of the paper — every section lives here.
%%
%% THIS FILE IS YOURS. `make set-template` rewrites main.tex but never touches
%% this file, so the same prose compiles under every template. Two rules keep
%% that true (see tools/templates/README.md):
%%
%%   * cite with \\citep / \\citet — every template loads natbib
%%   * anything you \\begin{} must come from researchcommon.sty, not from one
%%     template's preamble

\\section{Introduction}
\\label{sec:introduction}

% NOTE: state the problem, the gap, and the contributions.
"""

AGENTS = """\
# Agent instructions — {title}

Document-specific conventions. Everything general is in the repository root
`AGENTS.md` — read that first. Keep this file to what varies per document.

## Venue and format

- **Venue:** *(fill in)*
- **Paper type:** *(fill in)*
- **Template:** `{template}` — switch with
  `make set-template PAPER={slug} TEMPLATE=<name>`
- **Submission:** *(fill in)*

## Important dates

| Milestone | Date |
|-----------|------|
| Paper submission | *(fill in)* |
| Notification | *(fill in)* |
| Camera-ready | *(fill in)* |

## Submission rules

- Original, unpublished work not under review elsewhere.
- Figures, tables and body text count toward the page limit.
- Verify every BibTeX entry before adding it to the **root** `references.bib`.

## Where things live

| File | Owner |
|---|---|
| `main.tex` | generated from the template — do not hand-edit |
| `metadata.tex` `abstract.tex` `text.tex` `acronyms.tex` | yours |
| `references.bib`, `*.sty` | generated by `make sync-bib` |
| `figures/*.pdf` | generated by `make plots` from `data/*.csv` |
| `tables/*.tex` | generated by `make tables` from `data/*.csv` |

## Building

```bash
make paper PAPER={slug}
make wordcount PAPER={slug}
make arxiv PAPER={slug}
```
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slug", help="directory name under docs/, e.g. paper-neurips26")
    parser.add_argument("--title", default=None, help="document title")
    parser.add_argument("--short-title", default=None, help="running head (default: --title)")
    parser.add_argument(
        "--template",
        default=DEFAULT_TEMPLATE,
        help=f"template under tools/templates/ (default: {DEFAULT_TEMPLATE})",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    target = root / "docs" / args.slug
    if target.exists():
        raise SystemExit(f"error: docs/{args.slug} already exists")

    available = list_templates(root)
    if args.template not in available:
        raise SystemExit(
            f"error: no template named '{args.template}'. Available: {', '.join(available)}"
        )

    title = args.title or args.slug.replace("-", " ").title()
    short_title = args.short_title or title

    (target / "figures").mkdir(parents=True)
    (target / "tables").mkdir(parents=True)

    (target / "metadata.tex").write_text(METADATA.format(title=title, short_title=short_title))
    (target / "abstract.tex").write_text(ABSTRACT)
    (target / "text.tex").write_text(TEXT)
    (target / "acronyms.tex").write_text(ACRONYMS)
    (target / ".latexmkrc").write_text(LATEXMKRC)
    (target / "AGENTS.md").write_text(
        AGENTS.format(title=title, slug=args.slug, template=args.template)
    )
    (target / "references.bib").write_bytes(root_bib(root).read_bytes())
    (target / "figures" / ".gitkeep").write_text("")
    (target / "tables" / ".gitkeep").write_text("")

    # main.tex and the style assets come from the template, through the same
    # code path `make set-template` uses — so there is one way to install a
    # template, not two that can drift apart.
    print()
    set_template.apply_template(target, args.template, root, force=True)

    print(f"\ncreated docs/{args.slug}/ — next:")
    print(f"  edit docs/{args.slug}/metadata.tex   (title, authors, keywords)")
    print(f"  edit docs/{args.slug}/AGENTS.md      (venue, dates, page limit)")
    print(f"  make paper PAPER={args.slug}")
    print()
    print("In Overleaf, this document is compiled by pointing the project's main")
    print(f'document at docs/{args.slug}/main.tex — see README.md, "Overleaf".')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
