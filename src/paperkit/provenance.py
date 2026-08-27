"""Recording what a generated file was built from, so staleness is detectable.

Every figure and every table in this repository is generated, committed, and
therefore capable of silently disagreeing with the data behind it. A figure PDF
looks exactly as authoritative the day after the numbers changed as it did the
day it was drawn.

The fix is a sidecar file next to each generated artefact:

    figures/generated/.provenance.json
    docs/<doc>/tables/.provenance.json

recording, per artefact, the script that produced it and the SHA-256 of every
input it declared. `tools/check_generated.py` re-hashes those inputs and fails
when one has moved — which is what turns "the paper's numbers came from this
data" from a claim into a check.

Content hashes rather than mtimes: a fresh `git clone` gives every file the same
checkout time, so mtimes would report everything as current on the one machine
where you most want the check to work — CI.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from paperkit.paths import repo_root

PROVENANCE_FILENAME = ".provenance.json"

__all__ = ["PROVENANCE_FILENAME", "digest", "read", "record"]


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(directory: Path) -> dict:
    path = directory / PROVENANCE_FILENAME
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def record(
    target: Path,
    document: str,
    inputs: Sequence[Path],
    script: Path | None,
) -> None:
    """Add or replace `target`'s entry in its directory's provenance file."""
    root = repo_root()
    path = target.parent / PROVENANCE_FILENAME

    data = read(target.parent)
    data[target.name] = {
        "document": document,
        "script": script.resolve().relative_to(root).as_posix() if script else None,
        "inputs": {
            file.resolve().relative_to(root).as_posix(): digest(file)
            for file in sorted(Path(f).resolve() for f in inputs)
        },
    }

    # sort_keys and no timestamp field: rebuilding an unchanged figure must not
    # dirty the git tree, or `make plots` churns the repository on every run and
    # the CI reproducibility gate becomes noise.
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
