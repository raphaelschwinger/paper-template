#!/usr/bin/env python3
"""Lift bibliography entries added on Overleaf back into the root references.bib.

The root `references.bib` is the single source of truth; every
`docs/<paper>/references.bib` is a verbatim generated copy that exists only so
the document directory compiles standalone. A coauthor editing on Overleaf,
however, sees only the copy and will naturally add entries there.

Their commit arrives here by an ordinary `git pull` — Overleaf is linked to this
repository directly, so there is no subtree to unpick. What you then have is a
document copy that differs from the root bib, which `make check-generated`
reports. This script is how you resolve that in the direction that keeps the
root authoritative, and it is the reason `.gitattributes` can safely mark the
copies `merge=ours`: nothing a coauthor adds is lost, it just travels through
here instead of through git's merge machinery.

    uv run python tools/bib_absorb.py --paper paper-example
    uv run python tools/bib_absorb.py --paper paper-example --dry-run

Behaviour:
  * keys present in the copy but not in the root bib  -> appended to the root bib
  * keys present in both with identical fields        -> ignored
  * keys present in both with DIFFERENT fields        -> reported as a conflict,
    nothing is written; resolve by hand, deliberately.

After a successful absorb, run `make sync-bib` to regenerate the copies.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import paper_dirs, rel, repo_root, root_bib

try:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser
except ModuleNotFoundError:  # pragma: no cover - depends on environment
    raise SystemExit(
        "error: bibtexparser is not installed. Run `uv sync` and invoke this "
        "script as `uv run python tools/bib_absorb.py`."
    ) from None

# `@type{key,` at the start of a line. Comments, @string and @preamble are left
# alone by the slicer below, which only tracks entries it can key.
ENTRY_START = re.compile(r"^[ \t]*@(?P<type>[A-Za-z]+)\s*\{\s*(?P<key>[^,\s}]+)\s*,", re.MULTILINE)


def split_entries(text: str) -> dict[str, str]:
    """Map cite key -> the entry's **raw source text**, brace-matched.

    Parsing with bibtexparser and re-serializing would reformat the whole file
    and drop comments. The root references.bib is a human-owned document, so
    this tool only ever reads it and appends to it; entries move between files
    as the exact bytes their author wrote.
    """
    entries: dict[str, str] = {}
    for match in ENTRY_START.finditer(text):
        start = match.start()
        # Walk from the opening brace, tracking depth and skipping braces that
        # are escaped or inside a quoted string.
        depth = 0
        index = text.index("{", match.start())
        in_quotes = False
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == '"' and depth <= 1:
                in_quotes = not in_quotes
            elif not in_quotes:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        entries[match.group("key")] = text[start : index + 1]
                        break
            index += 1
    return entries


def _parser() -> BibTexParser:
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = False
    return parser


def load_fields(path: Path) -> dict[str, dict]:
    """Parsed field dicts, keyed by cite key. Used only for comparison."""
    if not path.is_file():
        raise SystemExit(f"error: {path} does not exist")
    database = bibtexparser.loads(path.read_text(encoding="utf-8"), parser=_parser())
    return {entry["ID"]: entry for entry in database.entries}


def entry_body(entry: dict) -> dict:
    """Comparable view of an entry: everything except provenance noise.

    DBLP-sourced entries carry `timestamp`, `biburl` and `bibsource` fields that
    differ between copies without any semantic difference. Comparing on those
    would report conflicts that are not conflicts.
    """
    noise = {"timestamp", "biburl", "bibsource"}
    return {k: v for k, v in entry.items() if k.lower() not in noise}


def absorb(paper: Path, root: Path, dry_run: bool) -> int:
    source_path = root_bib(root)
    copy_path = paper / "references.bib"

    root_text = source_path.read_text(encoding="utf-8")
    copy_text = copy_path.read_text(encoding="utf-8")

    root_raw = split_entries(root_text)
    copy_raw = split_entries(copy_text)

    root_fields = load_fields(source_path)
    copy_fields = load_fields(copy_path)

    new_keys = [key for key in copy_raw if key not in root_raw]
    conflicts = [
        key
        for key in copy_raw
        if key in root_raw
        and key in copy_fields
        and key in root_fields
        and entry_body(copy_fields[key]) != entry_body(root_fields[key])
    ]

    print(f"{paper.name}: {len(copy_raw)} entries in the copy, {len(root_raw)} in the root bib")

    if conflicts:
        print("\nCONFLICT — these keys exist in both files with different content:")
        for key in conflicts:
            print(f"  {key}")
        print(
            f"\nNothing was written. Reconcile them by hand in {rel(source_path, root)}, "
            f"then re-run. Diff them with:\n"
            f"  git diff --no-index -- {rel(source_path, root)} {rel(copy_path, root)}"
        )
        return 1

    if not new_keys:
        print("no new entries to absorb — the root bib is already current")
        return 0

    print(f"\n{len(new_keys)} new entr{'y' if len(new_keys) == 1 else 'ies'} to absorb:")
    for key in new_keys:
        title = copy_fields.get(key, {}).get("title", "").replace("\n", " ").strip("{} ")[:70]
        print(f"  + {key:<32} {title}")

    if dry_run:
        print("\n--dry-run: nothing written")
        return 0

    # APPEND ONLY. The root bib is a human-owned file: its comments, ordering
    # and formatting are never rewritten, and entries arrive as the exact bytes
    # their author wrote.
    banner = f"% --- absorbed from docs/{paper.name}/references.bib ---"
    addition = "\n\n".join([banner] + [copy_raw[key].strip() for key in new_keys])
    separator = (
        "" if root_text.endswith("\n\n") else ("\n" if root_text.endswith("\n") else "\n\n")
    )
    source_path.write_text(root_text + separator + addition + "\n", encoding="utf-8")

    print(f"\nappended to {rel(source_path, root)}")
    print("next: run `make sync-bib` to regenerate the per-paper copies")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--paper", help="document directory name under docs/ (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args(argv)

    root = repo_root()
    papers = paper_dirs(root)
    if args.paper:
        papers = [p for p in papers if p.name == args.paper]
        if not papers:
            raise SystemExit(f"error: no document directory named docs/{args.paper}")

    status = 0
    for paper in papers:
        if not (paper / "references.bib").is_file():
            continue
        status |= absorb(paper, root, args.dry_run)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
