"""Built-in table renderer, and the hook a custom one implements.

A table config's `table:` block names the columns to show, their headers and
their precision. That is enough for a results table. When it is not — a
multi-level header, a computed column, per-cell emphasis — write
`tables/<name>.py` beside the config defining:

    def build(data, cfg):       # return the DataFrame to typeset
        ...

It receives the fetched DataFrame and the merged config, and returns the frame
to render. Formatting, escaping, writing and provenance stay here, so a custom
table still looks like the others and is still checked for staleness.
"""

from __future__ import annotations

from pathlib import Path

from paperkit.config import cache_path, script_path
from paperkit.data import load as load_data
from paperkit.render.figures import _load_custom
from paperkit.tables import save_table

__all__ = ["render_table"]


def _select(data, spec: dict, name: str):
    """Apply `columns:` — pick, order, rename. Returns (frame, decimals-per-column)."""
    columns = spec.get("columns")
    if not columns:
        # No `columns:` means "show what was fetched", which is a reasonable
        # first draft and a bad final one — but it should not be an error.
        return data, {}

    frame, decimals = {}, {}
    for entry in columns:
        if isinstance(entry, str):
            entry = {"from": entry}
        source = entry.get("from")
        if source is None:
            raise SystemExit(f"error: tables/{name}.yml: a `columns:` entry has no `from:`")
        if source not in data.columns:
            raise SystemExit(
                f"error: tables/{name}.yml: column '{source}' is not in the fetched "
                f"data. Available: {', '.join(map(str, data.columns))}"
            )
        header = entry.get("as", source)
        frame[header] = data[source]
        if "decimals" in entry:
            decimals[header] = entry["decimals"]

    import pandas as pd

    return pd.DataFrame(frame), decimals


def _sort(frame, spec: dict, name: str):
    plan = spec.get("sort")
    if not plan:
        return frame
    by = plan["by"] if isinstance(plan, dict) else plan
    ascending = plan.get("ascending", True) if isinstance(plan, dict) else True

    # `sort.by` may name either the source column or the header it was renamed
    # to; both read naturally in the config, so accept both.
    keys = [by] if isinstance(by, str) else list(by)
    renamed = {
        e.get("as", e.get("from")): e.get("from")
        for e in (spec.get("columns") or [])
        if isinstance(e, dict)
    }
    resolved = []
    for key in keys:
        if key in frame.columns:
            resolved.append(key)
        else:
            match = next((h for h, src in renamed.items() if src == key), None)
            if match is None:
                raise SystemExit(
                    f"error: tables/{name}.yml: `sort.by: {key}` is not a column of "
                    f"the table. Available: {', '.join(map(str, frame.columns))}"
                )
            resolved.append(match)

    return frame.sort_values(resolved, ascending=ascending, kind="mergesort")


def render_table(config: dict) -> Path:
    name, spec = config["name"], config["table"]
    data = load_data("tables", name)
    source = cache_path("tables", name)
    custom = _load_custom("tables", name)
    script = script_path("tables", name) if custom else config["path"]

    if custom and hasattr(custom, "build"):
        frame = custom.build(data, config)
        decimals = {}
    else:
        frame, decimals = _select(data, spec, name)
        frame = _sort(frame, spec, name)

    return save_table(
        frame,
        name,
        config["document"],
        inputs=[source],
        script=script,
        decimals=spec.get("decimals", 2),
        per_column_decimals=decimals,
        column_format=spec.get("align"),
        escape_header=spec.get("escape_header", True),
    )
