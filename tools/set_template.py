#!/usr/bin/env python3
"""Apply a LaTeX template to a document, or switch it to a different one.

    uv run python tools/set_template.py --list
    uv run python tools/set_template.py --paper paper-example --template arxiv-custom
    uv run python tools/set_template.py --paper paper-example --template ieee-journal --force

Only `main.tex` and the materialized style assets change. Your writing —
`metadata.tex`, `abstract.tex`, `text.tex`, `acronyms.tex`, `figures/` — is never
touched, which is the entire point of the split.

`main.tex` is a generated file: the hash of the pristine rendering is recorded in
`.template.yml`. If it has been hand-edited, the switch refuses rather than
discarding the edits. Pass `--force` to proceed (a `.bak` is written first), and
consider whether the edit belongs in the template source under `tools/templates/`
so every document gets it.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    list_templates,
    read_document_template,
    read_template,
    rel,
    repo_root,
    sha256_file,
    templates_dir,
    write_document_template,
)


def resolve_paper(name: str, root: Path) -> Path:
    paper = root / "docs" / name
    if not paper.is_dir():
        raise SystemExit(f"error: no document directory at docs/{name}")
    return paper


def current_assets(paper: Path, root: Path) -> set[str]:
    """Basenames of the assets the document's *current* template installed."""
    document = read_document_template(paper)
    if not document.get("template"):
        return set()
    try:
        template = read_template(document["template"], root)
    except SystemExit:
        # The recorded template no longer exists; nothing reliable to clean up.
        return set()
    return {p.name for p in template["asset_paths"]}


def cmd_list(root: Path) -> int:
    print("Available templates (tools/templates/):\n")
    for name in list_templates(root):
        config = read_template(name, root)
        print(f"  {name:<20} {config.get('description', '')}")
        if config.get("assets"):
            print(f"  {'':<20} assets: {', '.join(config['assets'])}")
    print("\n  make set-template PAPER=<doc> TEMPLATE=<name>")
    return 0


def apply_template(paper: Path, name: str, root: Path, force: bool) -> int:
    template = read_template(name, root)
    document = read_document_template(paper)
    main_tex = paper / "main.tex"

    # --- guard: never silently discard hand edits ---------------------------
    recorded = document.get("main_tex_sha256")
    was_edited = main_tex.is_file() and recorded and sha256_file(main_tex) != recorded

    if was_edited and not force:
        previous = document.get("template", "")
        raise SystemExit(
            f"error: {rel(main_tex, root)} has been edited since it was generated\n"
            f"       from template '{previous or '?'}'. Switching to '{name}' would "
            f"discard those edits.\n\n"
            f"  See what changed:\n"
            f"    diff {rel(templates_dir(root) / previous / 'main.tex', root)} "
            f"{rel(main_tex, root)}\n\n"
            f"  If the edit should apply to every document, move it into the template\n"
            f"  source under tools/templates/ and re-run.\n"
            f"  To proceed anyway (a .bak is written):\n"
            f"    make set-template PAPER={paper.name} TEMPLATE={name} FORCE=1"
        )

    if was_edited:
        backup = main_tex.with_suffix(".tex.bak")
        shutil.copyfile(main_tex, backup)
        print(f"saved your edited main.tex to {rel(backup, root)}")

    # --- remove assets that belong only to the outgoing template ------------
    keep = {p.name for p in template["asset_paths"]}
    for orphan in sorted(current_assets(paper, root) - keep):
        path = paper / orphan
        if path.is_file():
            path.unlink()
            print(f"removed {rel(path, root)} (not used by '{name}')")

    # --- write main.tex and install assets ----------------------------------
    shutil.copyfile(template["main_tex"], main_tex)
    print(f"wrote {rel(main_tex, root)} from template '{name}'")

    for source in template["asset_paths"]:
        if not source.is_file():
            raise SystemExit(f"error: template asset {rel(source, root)} does not exist")
        target = paper / source.name
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            shutil.copyfile(source, target)
            print(f"installed {rel(target, root)}")

    write_document_template(paper, name, sha256_file(main_tex))

    # --- what the tool cannot decide for you --------------------------------
    print(f"\ndone. docs/{paper.name} now uses '{name}'.")
    print("Your metadata.tex, abstract.tex, text.tex and acronyms.tex are unchanged.")
    print("\nCheck by hand:")
    print("  * the author block in main.tex, if this document has more than one author")
    print(f"  * \\bibliographystyle is '{template.get('bibstyle', '?')}' — right for the venue?")
    if template.get("needs_shell_escape"):
        print("  * this template needs latexmk -shell-escape")
    print(f"\nThen: make paper PAPER={paper.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--paper", help="document directory name under docs/")
    parser.add_argument("--template", help="template name under tools/templates/")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite a hand-edited main.tex (saves a .bak first)",
    )
    parser.add_argument("--list", action="store_true", help="list available templates")
    args = parser.parse_args(argv)

    root = repo_root()

    if args.list:
        return cmd_list(root)

    if not args.paper or not args.template:
        parser.error("--paper and --template are required (or use --list)")

    return apply_template(resolve_paper(args.paper, root), args.template, root, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
