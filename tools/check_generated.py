#!/usr/bin/env python3
"""Verify that every generated file in the repository is up to date.

This is what makes "single source of truth" enforceable rather than
aspirational. It is wired into pre-commit and into CI, and it checks:

1.  **Bibliography copies.** `docs/<doc>/references.bib` must be byte-identical
    to the root `references.bib`. The copy exists only because the document
    directory has to compile standalone — on Overleaf, and in the flattened
    `make arxiv` bundle — and cannot reach the repository root.

2.  **Template assets.** Same contract for `researchcommon.sty` and any
    vendored style the document's template declares.

3.  **Figure and table provenance.** Every artefact recorded in
    `figures/generated/.provenance.json` or `docs/<doc>/tables/.provenance.json`
    must still match the inputs it was built from. Content hashes are used
    rather than mtimes, because a fresh `git clone` gives every file the same
    checkout time. Document copies of figure PDFs under `docs/<doc>/figures/`
    must be byte-identical to `figures/generated/`.

4.  **The W&B cache.** Every figure and table config must have a CSV and a lock
    entry, and the lock's recorded query hash must match the config's `data:`
    block as it now stands. This is what catches "you edited a filter but never
    re-fetched", which would otherwise leave the paper reporting numbers from a
    query it no longer describes.

Exit status is 0 when everything is current, 1 otherwise.

    uv run python tools/check_generated.py
    uv run python tools/check_generated.py --paper paper-example
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    Reporter,
    all_configs,
    cache_path,
    load_config,
    lock_key,
    lock_path,
    paper_dirs,
    read_document_template,
    read_lock,
    read_provenance,
    read_template,
    rel,
    repo_root,
    root_bib,
    sha256_file,
    spec_sha256,
)


def check_bib_copy(paper: Path, root: Path, report: Reporter) -> None:
    source = root_bib(root)
    copy = paper / "references.bib"

    if not copy.is_file():
        report.error(f"{rel(copy, root)} is missing. Run: make sync-bib")
        return

    if source.read_bytes() != copy.read_bytes():
        report.error(
            f"{rel(copy, root)} differs from the root references.bib.\n"
            f"         If a coauthor added entries to the copy (they see only this file "
            f"on Overleaf), run `make bib-absorb PAPER={paper.name}` to lift them into "
            f"the root bib.\n"
            f"         Otherwise run `make sync-bib` to regenerate it."
        )


def check_template_assets(paper: Path, root: Path, report: Reporter) -> None:
    """Style files copied in from tools/templates/ must match their source.

    Same contract as the bibliography copy: the copies exist only because the
    document directory compiles standalone, so the source of truth is under
    tools/templates/ and the copy is regenerated, never hand-edited.
    """
    document = read_document_template(paper)
    name = document.get("template")

    if not name:
        report.warn(
            f"{rel(paper, root)} has no {rel(paper / '.template.yml', root)} — "
            f"its template is unknown, so style assets cannot be verified. "
            f"Run: make set-template PAPER={paper.name} TEMPLATE=<name>"
        )
        return

    template = read_template(name, root)

    for source in template["asset_paths"]:
        copy = paper / source.name

        if not source.is_file():
            report.error(
                f"template '{name}' lists asset {rel(source, root)}, which does not exist"
            )
            continue

        if not copy.is_file():
            report.error(f"{rel(copy, root)} is missing. Run: make sync-bib")
            continue

        if source.read_bytes() != copy.read_bytes():
            report.error(
                f"{rel(copy, root)} differs from {rel(source, root)}.\n"
                f"         That file is generated. Edit the source under "
                f"tools/templates/ instead, then run `make sync-bib`."
            )


def check_provenance(directory: Path, rebuild: str, root: Path, report: Reporter) -> None:
    """One provenance directory: `figures/generated/` or `docs/<doc>/tables/`.

    Both obey the same contract, so they are checked by the same code — the only
    difference is which command regenerates them.
    """
    provenance = read_provenance(directory)

    if not provenance:
        # A document with no generated artefacts of this kind is fine: a
        # literature study has no results table, a draw.io-only paper has no
        # data figures.
        return

    for artefact_name, record in sorted(provenance.items()):
        artefact = directory / artefact_name

        if not artefact.is_file():
            report.error(
                f"{rel(artefact, root)} is recorded in provenance but missing. Run: {rebuild}"
            )
            continue

        for input_rel, recorded_hash in sorted(record.get("inputs", {}).items()):
            input_path = root / input_rel
            if not input_path.is_file():
                report.error(
                    f"{rel(artefact, root)} was built from {input_rel}, which no longer exists."
                )
                continue
            if sha256_file(input_path) != recorded_hash:
                script = record.get("script", "its generator")
                report.error(
                    f"{rel(artefact, root)} is STALE: {input_rel} changed since it was built.\n"
                    f"         Rebuild with `{rebuild}` (script: {script})."
                )


def check_wandb_cache(root: Path, report: Reporter) -> None:
    """The committed CSVs must correspond to the configs that produced them."""
    if not (root / "paper.yml").is_file():
        report.warn("paper.yml is missing — the W&B cache cannot be verified")
        return

    configs = all_configs(root)
    lock = read_lock(root)
    known = {lock_key(kind, name) for kind, name in configs}
    cached = [(k, n) for k, n in configs if cache_path(k, n, root).is_file()]

    if not lock:
        if cached:
            report.error(
                f"{rel(lock_path(root), root)} is missing, so nothing records which W&B "
                f"runs the committed data came from.\n"
                f"         Run: make fetch REFRESH=1"
            )
        else:
            report.warn("nothing has been fetched yet. Run: make fetch REFRESH=1")
        return

    for kind, name in configs:
        key = lock_key(kind, name)
        csv = cache_path(kind, name, root)
        entry = lock.get(key) or {}

        if not csv.is_file():
            # A config that has never been fetched is a warning, not an error:
            # that is the state of a freshly written figure, and of a freshly
            # bootstrapped repository. Anything that actually *depends* on the
            # missing file — a committed PDF that declared it as an input — is
            # caught as an error by check_provenance.
            report.warn(
                f"{kind}/{name}.yml has never been fetched. "
                f"Run: make fetch DATASET={key} REFRESH=1"
            )
            continue

        if not entry:
            report.error(
                f"{kind}/{name} has data but no entry in {rel(lock_path(root), root)}, "
                f"so the runs behind it are unrecorded.\n"
                f"         Run: make fetch REFRESH=1"
            )
            continue

        if entry.get("spec_sha256") != spec_sha256(load_config(kind, name, root)):
            report.error(
                f"the `data:` block in {kind}/{name}.yml has changed since "
                f"{rel(csv, root)} was fetched.\n"
                f"         The committed numbers no longer come from the query that "
                f"describes them.\n"
                f"         Run: make fetch REFRESH=1"
            )

    for key in sorted(set(lock) - known):
        report.warn(
            f"'{key}' is locked but has no config any more. "
            f"Remove its lock entry and data/{key}.csv once nothing cites it."
        )


def check_figure_copies(paper: Path, root: Path, report: Reporter) -> None:
    """`docs/<doc>/figures/` copies must match `figures/generated/`.

    The copies exist so a document directory compiles standalone. They are not
    a second source of truth: drift means `make plots` was skipped.
    """
    generated = root / "figures" / "generated"
    copies = paper / "figures"
    provenance = read_provenance(generated)
    for artefact_name, record in sorted(provenance.items()):
        if record.get("document") != paper.name:
            continue
        source = generated / artefact_name
        copy = copies / artefact_name
        if not source.is_file():
            continue  # already reported by check_provenance
        if not copy.is_file():
            report.error(f"{rel(copy, root)} is missing. Run: make plots")
            continue
        if source.read_bytes() != copy.read_bytes():
            report.error(
                f"{rel(copy, root)} differs from {rel(source, root)}.\n"
                f"         That file is a generated copy. Run `make plots`."
            )


def check_orphan_outputs(root: Path, report: Reporter) -> None:
    """A committed figure or table whose config was deleted.

    Provenance alone cannot catch this: deleting `figures/x.yml` leaves both the
    PDF and its provenance record intact and internally consistent, so the paper
    keeps displaying a figure nothing can rebuild.
    """
    figure_names = {n for k, n in all_configs(root) if k == "figures"}
    generated = root / "figures" / "generated"
    for artefact, record in sorted(read_provenance(generated).items()):
        stem = Path(artefact).stem
        if stem not in figure_names and not record.get("external"):
            report.warn(
                f"{rel(generated / artefact, root)} has no figures/{stem}.yml — "
                f"nothing can rebuild it. Delete it, or restore the config."
            )

    table_names = {n for k, n in all_configs(root) if k == "tables"}
    for paper in paper_dirs(root):
        for artefact, record in sorted(read_provenance(paper / "tables").items()):
            stem = Path(artefact).stem
            if stem not in table_names and not record.get("external"):
                report.warn(
                    f"{rel(paper / 'tables' / artefact, root)} has no tables/{stem}.yml — "
                    f"nothing can rebuild it. Delete it, or restore the config."
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--paper",
        help="only check this document directory name (default: all of docs/*/ with a main.tex)",
    )
    # pre-commit passes the staged filenames; we always check the whole repo,
    # so accept and ignore them rather than erroring out.
    parser.add_argument("files", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = repo_root()
    papers = paper_dirs(root)
    if args.paper:
        papers = [p for p in papers if p.name == args.paper]
        if not papers:
            raise SystemExit(f"error: no document directory named docs/{args.paper}")

    report = Reporter("check-generated")

    if not papers:
        print("check-generated: no documents found under docs/")
    for paper in papers:
        check_bib_copy(paper, root, report)
        check_template_assets(paper, root, report)
        check_figure_copies(paper, root, report)
        check_provenance(paper / "tables", "make tables", root, report)

    check_provenance(root / "figures" / "generated", "make plots", root, report)

    # Repo-wide, not per-document: the configs feed every document.
    if not args.paper:
        check_wandb_cache(root, report)
        check_orphan_outputs(root, report)

    return report.finish()


if __name__ == "__main__":
    raise SystemExit(main())
