"""Locating things in the paper repository.

Nothing here may rely on `Path.cwd()`: `make plots` runs scripts from the
repository root, an editor may run one from anywhere, and this repository is
usually checked out as a *submodule* of a code repository, so the working
directory is rarely what a script would guess.

The root is found by walking up from this file until a directory containing both
`references.bib` and `docs/` appears — the same rule `tools/_common.py` uses, so
the tooling and the scripts agree by construction.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Absolute path of the paper repository root."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "references.bib").is_file() and (candidate / "docs").is_dir():
            return candidate
    raise RuntimeError(
        "could not locate the paper repository root: no ancestor directory "
        "contains both references.bib and docs/"
    )


def data_dir() -> Path:
    """`data/` — the committed W&B cache. Created if absent."""
    path = repo_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_dir(name: str) -> Path:
    """`docs/<name>/` — a paper, literature study or thesis."""
    path = repo_root() / "docs" / name
    if not path.is_dir():
        raise FileNotFoundError(
            f"no document directory at {path}. Create one with: "
            f'make new-paper NAME={name} TITLE="..."'
        )
    return path


def generated_figures_dir() -> Path:
    """`figures/generated/` — rendered PDFs and draw.io exports. Created if absent."""
    path = repo_root() / "figures" / "generated"
    path.mkdir(parents=True, exist_ok=True)
    return path


def figures_dir(document: str) -> Path:
    """`docs/<document>/figures/` — Overleaf copies of generated figures.

    Canonical PDFs live in `figures/generated/`. The copy here exists so a
    document directory compiles standalone. Created if absent.
    """
    path = document_dir(document) / "figures"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tables_dir(document: str) -> Path:
    """`docs/<document>/tables/` — tracked table fragments. Created if absent."""
    path = document_dir(document) / "tables"
    path.mkdir(parents=True, exist_ok=True)
    return path
