#!/usr/bin/env python3
"""Copy the sources of truth into each document directory.

# Why copies exist at all

There is exactly one `references.bib` in this repository and one copy of each
LaTeX style file, under `tools/templates/`. But a document directory has to be
compilable *standalone*: Overleaf builds `docs/<doc>/` with the repository
checked out as one project and no shell access, and `make arxiv` flattens the
directory into a submission bundle. Neither can reach a source of truth that
lives somewhere else in the tree.

So each `docs/<doc>/` gets a verbatim, generated copy of:

  * `references.bib` — the root bibliography;
  * the style assets its template declares (`researchcommon.sty`, and a
    vendored `arxiv*.sty` or `orcid.pdf` where the template needs them).

`tools/check_generated.py` fails when a copy has drifted, so the copies cannot
quietly become a second source of truth. **Never hand-edit one** — edit the root
bib or the file under `tools/templates/` and re-run this.

    uv run python tools/materialize.py              # every document
    uv run python tools/materialize.py --paper paper-example

`make sync-bib` is the front door.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    paper_dirs,
    read_document_template,
    read_template,
    rel,
    repo_root,
    root_bib,
)


def resolve_paper(name: str, root: Path) -> Path:
    paper = root / "docs" / name
    if not (paper / "main.tex").is_file():
        raise SystemExit(
            f"error: docs/{name}/main.tex not found — is that the right document name?"
        )
    return paper


def _copy_if_changed(source: Path, target: Path, root: Path, changed: list[str]) -> None:
    if not target.is_file() or target.read_bytes() != source.read_bytes():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        changed.append(rel(target, root))


def materialize(paper: Path, root: Path) -> list[str]:
    """Copy the sources of truth into one document directory. Returns changed files."""
    changed: list[str] = []

    _copy_if_changed(root_bib(root), paper / "references.bib", root, changed)

    document = read_document_template(paper)
    if document.get("template"):
        template = read_template(document["template"], root)
        for source in template["asset_paths"]:
            if not source.is_file():
                raise SystemExit(
                    f"error: template '{template['name']}' lists asset {rel(source, root)}, "
                    f"which does not exist"
                )
            _copy_if_changed(source, paper / source.name, root, changed)

    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--paper", help="document directory name under docs/ (default: all)")
    args = parser.parse_args(argv)

    root = repo_root()
    papers = [resolve_paper(args.paper, root)] if args.paper else paper_dirs(root)
    if not papers:
        print("materialize: no documents under docs/ — nothing to do")
        return 0

    any_changed = False
    for paper in papers:
        for path in materialize(paper, root):
            print(f"materialized {path}")
            any_changed = True
    if not any_changed:
        print("materialize: generated files already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
