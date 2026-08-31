#!/usr/bin/env python3
"""Fetch each figure's and table's numbers from Weights & Biases.

# The shape of the thing

    paper.yml                       the W&B connection, shared
    figures/<name>.yml              one figure's query + style
    tables/<name>.yml               one table's query + layout
        |   make fetch
        v
    data/figures/<name>.csv         its numbers      [committed, CSV so it diffs]
    data/tables/<name>.csv
    data/wandb.lock.yml             the run IDs behind them   [committed]

This is the only script in the repository that talks to W&B. Renderers read the
CSVs through `paperkit.data`, so the paper compiles on a machine with no API
key, in CI with no secret, and for a coauthor with no access to the project.

# Why the lockfile

A query like "every finished run tagged paper-v1" does not name a fixed set of
runs. A sweep finishing overnight changes what it matches, and the paper's
numbers move without anyone touching the repository. So `make fetch REFRESH=1`
re-runs the queries and *records what they matched*; a plain `make fetch`
re-reads exactly those runs. The numbers in the paper are pinned to a run set
you chose, and widening it is a deliberate, reviewable act.

# Why configs that share a query are fetched once

Each config owns its own CSV, so a figure and the table beside it are honest,
independent snapshots. But they usually summarise the same runs, and querying
W&B twice for the same thing is slow and can even disagree if a run finishes in
between. Identical queries are therefore resolved once and the result copied.

    fetch.py                              re-fetch the pinned runs
    fetch.py --refresh                    re-run the queries, report the diff
    fetch.py --dataset figures/curves     just one config
    fetch.py --refresh --dry-run          what would it match? write nothing

# Ablation figures (`data.kind: rows`)

A butterfly ablation chart needs one independent query per row, not the single
`data.filters:` every other figure uses. Its `data.rows: [{label, section,
filters}, ...]` is resolved and pinned per row (see `fetch_rows`), so editing
one row's filters never forces re-resolving the other fourteen. The CSV and
lock entry still live in the usual places — it is a normal `figures/<name>.yml`
with `plot.kind: ablation`, a built-in renderer. See `figures/README.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    all_configs,
    cache_path,
    config_names,
    load_config,
    lock_key,
    read_lock,
    read_paper_config,
    rel,
    repo_root,
    spec_sha256,
    write_lock,
)

PLACEHOLDER_ENTITY = "your-wandb-entity"


def _require_wandb():
    if not os.environ.get("WANDB_API_KEY"):
        raise SystemExit(
            "error: WANDB_API_KEY is not set.\n"
            "This is the one command in this repository that needs it; everything\n"
            "else builds from the committed data/**/*.csv. Get a key from\n"
            "https://wandb.ai/authorize and export it:\n\n"
            "    export WANDB_API_KEY=...\n"
        )
    try:
        import wandb
    except ModuleNotFoundError:  # pragma: no cover - depends on environment
        raise SystemExit("error: wandb is not installed. Run: make setup") from None
    return wandb


def _require_pandas():
    try:
        import pandas as pd
    except ModuleNotFoundError:  # pragma: no cover - depends on environment
        raise SystemExit("error: pandas is not installed. Run: make setup") from None
    return pd


def check_configured(spec: dict, label: str) -> None:
    if spec.get("entity") == PLACEHOLDER_ENTITY:
        raise SystemExit(
            f"error: {label} resolves to the placeholder W&B entity.\n"
            f"Fill in `wandb.entity` and `wandb.project` in paper.yml (or override them\n"
            f"in the config's `data:` block), then run: make fetch REFRESH=1"
        )


def parse_target(target: str, root: Path) -> tuple[str, str]:
    """Accept `figures/name`, `tables/name`, or a bare unambiguous name."""
    if "/" in target:
        kind, _, name = target.partition("/")
        if name.endswith(".yml"):
            name = name[:-4]
        if name not in config_names(kind, root):
            raise SystemExit(f"error: no config at {kind}/{name}.yml")
        return kind, name

    matches = [(k, n) for k, n in all_configs(root) if n == target]
    if not matches:
        known = ", ".join(f"{k}/{n}" for k, n in all_configs(root)) or "(none)"
        raise SystemExit(f"error: no config named '{target}'. Have: {known}")
    if len(matches) > 1:
        options = ", ".join(f"{k}/{n}" for k, n in matches)
        raise SystemExit(f"error: '{target}' is ambiguous — say which: {options}")
    return matches[0]


# ---------------------------------------------------------------------------
# Querying
# ---------------------------------------------------------------------------


def resolve_runs(api, spec: dict):
    """Run the filter query and return the matching runs, in a stable order."""
    path = f"{spec['entity']}/{spec['project']}"
    runs = list(api.runs(path, filters=spec.get("filters") or {}, per_page=200))
    return sorted(runs, key=lambda r: r.id)


def pinned_runs(api, spec: dict, entry: dict):
    """Fetch exactly the runs named in the lock, in the lock's order."""
    path = f"{spec['entity']}/{spec['project']}"
    runs, missing = [], []
    for record in entry.get("runs") or []:
        try:
            runs.append(api.run(f"{path}/{record['id']}"))
        except Exception:  # wandb raises a CommError subclass; the id is what matters
            missing.append(record["id"])
    if missing:
        raise SystemExit(
            f"error: {len(missing)} pinned run(s) could not be read from W&B: "
            f"{', '.join(missing)}\n"
            f"They may have been deleted, or moved to another project. Re-resolve the\n"
            f"query and accept the new run set with:  make fetch REFRESH=1"
        )
    return runs


def run_record(run) -> dict:
    return {
        "id": run.id,
        "name": run.name,
        "state": run.state,
        "heartbeat": str(getattr(run, "heartbeat_at", "") or ""),
    }


def report_run_diff(previous: dict, runs: list) -> None:
    """Print which runs entered and left the query since the last refresh."""
    before = {r["id"]: r.get("name", "") for r in (previous.get("runs") or [])}
    after = {r.id: r.name for r in runs}

    print(f"  {len(after)} run(s) match the query")
    for run_id in sorted(set(after) - set(before)):
        print(f"    + {run_id}  {after[run_id]}")
    for run_id in sorted(set(before) - set(after)):
        print(f"    - {run_id}  {before[run_id]}")
    if before and set(before) == set(after):
        print("    (unchanged run set)")


# ---------------------------------------------------------------------------
# Turning runs into a table
# ---------------------------------------------------------------------------


def _config_columns(run, spec: dict) -> dict:
    return {key: run.config.get(key) for key in (spec.get("config") or [])}


def history_frame(pd, runs: list, spec: dict):
    keys = list(spec.get("keys") or [])
    samples = int(spec.get("samples", 1000))
    frames = []
    for run in runs:
        history = run.history(keys=keys or None, samples=samples, pandas=True)
        if history is None or len(history) == 0:
            continue
        for key, value in _config_columns(run, spec).items():
            history[key] = value
        history["run_id"] = run.id
        frames.append(history)
    if not frames:
        raise SystemExit(
            "error: the query matched runs, but none of them logged the requested "
            "`keys:`. Check the metric names against a run in the W&B UI."
        )
    return pd.concat(frames, ignore_index=True)


def summary_frame(pd, runs: list, spec: dict):
    keys = list(spec.get("keys") or [])
    rows = []
    for run in runs:
        row = {"run_id": run.id, "run_name": run.name}
        row.update(_config_columns(run, spec))
        summary = dict(run.summary)
        for key in keys:
            row[key] = summary.get(key)
        rows.append(row)
    return pd.DataFrame(rows)


def aggregate(pd, frame, spec: dict):
    """Collapse seeds into statistics, so the committed CSV stays small and readable."""
    plan = spec.get("aggregate")
    if not plan:
        return frame

    by, of = list(plan["by"]), plan["of"]
    stats = list(plan.get("stats") or ["mean", "std", "count"])

    for column in [*by, of]:
        if column not in frame.columns:
            raise SystemExit(
                f"error: aggregate refers to column '{column}', which the query did "
                f"not produce. Available: {', '.join(map(str, frame.columns))}"
            )

    return frame.groupby(by, dropna=False, sort=True)[of].agg(stats).reset_index()


def identity_columns(spec: dict, frame) -> list[str]:
    """The columns that identify a row: what to sort by, and what to put first.

    For an aggregated dataset that is the `by:` of the aggregation. Otherwise it
    is the run, the config values that distinguish runs, and the step.
    """
    plan = spec.get("aggregate")
    if plan:
        candidates = list(plan["by"])
    else:
        candidates = ["run_id", "run_name", *(spec.get("config") or []), "_step"]
    return [c for c in candidates if c in frame.columns]


def stabilize(pd, frame, decimals: int, keys: list[str]):
    """Deterministic row order, column order and float precision.

    Everything here exists so that the same query on two machines writes the
    same bytes: identity columns first and sorted on, remaining columns in the
    order the query produced them, every float rounded, no index.
    """
    if keys:
        frame = frame.sort_values(keys, kind="mergesort")

    ordered = keys + [c for c in frame.columns if c not in keys]
    frame = frame[ordered].reset_index(drop=True)

    for column in frame.columns:
        if pd.api.types.is_float_dtype(frame[column]):
            frame[column] = frame[column].round(decimals)
    return frame


def write_csv(frame, path: Path, decimals: int) -> None:
    # `float_format` as well as the rounding above: without it pandas writes the
    # repr of the rounded float, which can still differ in the last digit across
    # platforms and would show up as a diff on every fetch.
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n", float_format=f"%.{decimals}f")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _row_digest(entity: str, project: str, filters: dict) -> str:
    """Content hash of one ablation row's query — scoped to that row alone.

    Mirrors `spec_sha256`, but per row instead of per config: with fifteen
    independent queries feeding one CSV, hashing the whole `data:` block would
    make editing any one row invalidate the pin for all the others too.
    """
    canonical = json.dumps(
        {"entity": entity, "project": project, "filters": filters},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _runtime_value(run, metric: str, aggregate: str) -> float | None:
    """Per-run runtime figure: last logged value, or the median of the series."""
    if aggregate == "summary":
        value = run.summary.get(metric)
        return float(value) if value is not None else None

    try:
        history = run.history(keys=[metric], pandas=False, samples=2_000)
    except Exception as exc:
        print(f"    warning: history for {run.id} unavailable ({exc}); using summary")
        value = run.summary.get(metric)
        return float(value) if value is not None else None

    import numpy as np

    values = [row[metric] for row in history if row.get(metric) is not None]
    return float(np.median(values)) if values else None


def fetch_rows(api, pd, config: dict, entry: dict, refresh: bool, dry_run: bool) -> dict | None:
    """Resolve every row of an ablation figure (`data.kind: rows`) and write its CSV.

    One row = one independent W&B query (a butterfly ablation chart needs a
    separate filter per arm, unlike every other figure's single `data.filters`).
    Each row is pinned and diffed on its own — see `_row_digest`.
    """
    spec = config["data"]
    label = f"{config['kind']}/{config['name']}.yml"
    entity, project = spec["entity"], spec["project"]
    default_filters = spec.get("default_filters") or {}
    rows_cfg = spec.get("rows") or []
    if not rows_cfg:
        raise SystemExit(f"error: {label}: `data.rows` is empty")

    score_metric = spec["score"]["metric"]
    runtime_metric = spec["runtime"]["metric"]
    runtime_aggregate = spec["runtime"].get("aggregate", "summary")
    old_rows = entry.get("rows") or {}

    if not refresh:
        stale = []
        for row in rows_cfg:
            arm_key = f"{row['section']}/{row['label']}"
            filters = {**default_filters, **(row.get("filters") or {})}
            old = old_rows.get(arm_key)
            if old is None:
                stale.append(f"{arm_key}  (never fetched)")
            elif old.get("spec_sha256") != _row_digest(entity, project, filters):
                stale.append(f"{arm_key}  (filters changed)")
        if stale:
            raise SystemExit(
                f"error: {label} has row(s) not pinned to their current query:\n"
                + "\n".join(f"  - {s}" for s in stale)
                + f"\nResolve them first:  make fetch DATASET={config['kind']}/{config['name']} REFRESH=1"
            )

    rows_lock: dict[str, dict] = {}
    records: list[dict] = []
    for row in rows_cfg:
        arm_key = f"{row['section']}/{row['label']}"
        filters = {**default_filters, **(row.get("filters") or {})}
        if not filters:
            # No constraint means "every run in the project" — never what a row
            # wants, and it would silently fill the cache with unrelated runs.
            print(f"! {row['label']:44s} SKIPPED: empty filters")
            continue
        digest = _row_digest(entity, project, filters)
        old = old_rows.get(arm_key) or {}
        row_spec = {"entity": entity, "project": project, "filters": filters}

        if refresh:
            runs = resolve_runs(api, row_spec)
            report_run_diff(old, runs)
        else:
            runs = pinned_runs(api, row_spec, old)
            print(f"  {row['label']:44s} {len(runs)} pinned run(s)")

        kept, skipped = 0, 0
        for run in runs:
            score = run.summary.get(score_metric)
            if score is None:
                skipped += 1
                continue
            runtime = _runtime_value(run, runtime_metric, runtime_aggregate)
            records.append(
                {
                    "section": row["section"],
                    "label": row["label"],
                    "game": run.config.get("env_id", "unknown"),
                    "seed": run.config.get("seed", ""),
                    "run_id": run.id,
                    "state": run.state,
                    "score": float(score),
                    "runtime": "" if runtime is None else float(runtime),
                }
            )
            kept += 1
        if refresh:
            detail = f"{kept} run(s)" + (f", {skipped} without {score_metric}" if skipped else "")
            marker = "  " if kept else "! "
            print(f"{marker}{row['label']:44s} {detail}")

        rows_lock[arm_key] = {"spec_sha256": digest, "runs": [run_record(r) for r in runs]}

    if dry_run:
        print("  --dry-run: nothing written")
        return None

    if not records:
        # Every row came back empty. Overwriting here would destroy a cache
        # that is still good.
        print("\nno runs matched any row; cache left untouched")
        return None

    frame = pd.DataFrame.from_records(records)
    decimals = int(spec.get("round", 6))
    frame = stabilize(pd, frame, decimals, ["section", "label", "game", "seed"])
    path = cache_path(config["kind"], config["name"])
    write_csv(frame, path, decimals)
    print(f"\n  wrote {rel(path)}  ({len(frame)} rows, {len(frame.columns)} columns)")

    return {
        "entity": entity,
        "project": project,
        "spec_sha256": spec_sha256(config),
        "fetched": str(date.today()),
        "rows": rows_lock,
    }


def fetch_one(api, pd, config: dict, lock: dict, refresh: bool, dry_run: bool, seen: dict):
    kind, name = config["kind"], config["name"]
    spec = config["data"]
    key = lock_key(kind, name)
    label = f"{kind}/{name}.yml"

    data_kind = spec.get("kind", "history")
    if data_kind not in ("history", "summary", "rows"):
        raise SystemExit(
            f"error: {label}: unknown `data.kind: {data_kind}` (history|summary|rows)"
        )
    check_configured(spec, label)

    entry = lock.get(key) or {}
    digest = spec_sha256(config)
    print(f"\n{key}  ({data_kind})")

    # An ablation figure's `data.rows` is many independent queries, not one —
    # editing row 7 must not force re-resolving (and re-pinning) rows 1-6 and
    # 8-15 too, so it gets its own path with a per-row digest instead of the
    # single whole-config one below.
    if data_kind == "rows":
        return fetch_rows(api, pd, config, entry, refresh, dry_run)

    # Two configs with an identical query are one query. Resolving it twice is
    # slow, and can even disagree if a run finishes in between.
    if digest in seen:
        source_key, frame, record = seen[digest]
        if dry_run:
            print(f"  same query as {source_key} — would reuse")
            return None
        path = cache_path(kind, name)
        write_csv(frame, path, int(spec.get("round", 6)))
        print(f"  same query as {source_key} — reused, wrote {rel(path)}")
        return dict(record)

    if refresh:
        runs = resolve_runs(api, spec)
        report_run_diff(entry, runs)
        if not runs:
            raise SystemExit(
                f"error: the query in {label} matched no runs. Check `data.filters:` "
                f"against the W&B UI."
            )
    else:
        if not entry:
            raise SystemExit(
                f"error: {key} has no entry in data/wandb.lock.yml, so there is nothing "
                f"pinned to re-fetch.\nResolve the query first:  make fetch REFRESH=1"
            )
        if entry.get("spec_sha256") != digest:
            raise SystemExit(
                f"error: the `data:` block in {label} has changed since the data was "
                f"fetched.\nRe-resolving it may bring in different runs, so it is not "
                f"done silently:\n\n    make fetch REFRESH=1\n"
            )
        runs = pinned_runs(api, spec, entry)
        print(f"  {len(runs)} pinned run(s)")

    if dry_run:
        print("  --dry-run: nothing written")
        return None

    frame = (
        history_frame(pd, runs, spec) if data_kind == "history" else summary_frame(pd, runs, spec)
    )
    frame = aggregate(pd, frame, spec)
    decimals = int(spec.get("round", 6))
    frame = stabilize(pd, frame, decimals, identity_columns(spec, frame))

    path = cache_path(kind, name)
    write_csv(frame, path, decimals)
    print(f"  wrote {rel(path)}  ({len(frame)} rows, {len(frame.columns)} columns)")

    record = {
        "entity": spec["entity"],
        "project": spec["project"],
        "spec_sha256": digest,
        "fetched": str(date.today()),
        "runs": [run_record(r) for r in runs],
    }
    seen[digest] = (key, frame, record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dataset", help="fetch only this config: figures/<name>, tables/<name>, or <name>"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-run the queries instead of re-reading the pinned run IDs",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report what the queries match; write nothing"
    )
    args = parser.parse_args(argv)

    root = repo_root()
    read_paper_config(root)  # validates it exists

    targets = [parse_target(args.dataset, root)] if args.dataset else all_configs(root)
    if not targets:
        print("no figure or table configs found — nothing to fetch")
        return 0

    wandb = _require_wandb()
    pd = _require_pandas()
    api = wandb.Api()

    lock = read_lock(root)
    updated = dict(lock)
    seen: dict = {}

    for kind, name in targets:
        config = load_config(kind, name, root)
        record = fetch_one(api, pd, config, lock, args.refresh, args.dry_run, seen)
        if record is not None:
            updated[lock_key(kind, name)] = record

    if args.dry_run:
        return 0

    known = {lock_key(k, n) for k, n in all_configs(root)}
    for key in sorted(set(updated) - known):
        print(f"\nnote: '{key}' is in the lock but has no config any more.")
        print(f"      Remove its lock entry and data/{key}.csv when nothing cites it.")

    write_lock(updated, root)
    print(f"\nwrote {rel(root / 'data' / 'wandb.lock.yml')}")
    print("\nNext: `make plots tables` to rebuild what depends on this, then review")
    print("`git diff data/` — every number that moved is visible there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
