"""Reading `paper.yml` and the per-figure / per-table configs.

There is no central registry of datasets in this repository. A figure *is* a
file — `figures/<name>.yml` — that says where its numbers come from and how it
is drawn. `paper.yml` supplies only what every config would otherwise repeat:
the W&B connection and the house style.

This module is the read side of that, shared by the renderers. The write side
(`make fetch`) reads the same configs through `tools/_common.py`, which
deliberately avoids importing pandas so it can run as a pre-commit hook.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from paperkit.paths import repo_root

__all__ = [
    "KINDS",
    "cache_path",
    "config_names",
    "config_path",
    "load",
    "read_paper_config",
]

KINDS = ("figures", "tables")
RENDER_KEY = {"figures": "plot", "tables": "table"}


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def read_paper_config() -> dict:
    config = _read_yaml(repo_root() / "paper.yml")
    if not config:
        raise SystemExit(
            "error: paper.yml is missing or empty. It holds the W&B connection and "
            "the house style that every figure inherits."
        )
    config.setdefault("wandb", {})
    config.setdefault("style", {})
    config.setdefault("round", 6)
    return config


def config_path(kind: str, name: str) -> Path:
    if kind not in KINDS:
        raise ValueError(f"unknown config kind {kind!r} (expected one of {KINDS})")
    return repo_root() / kind / f"{name}.yml"


def config_names(kind: str) -> list[str]:
    directory = repo_root() / kind
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.yml") if not p.name.startswith("_"))


def cache_path(kind: str, name: str) -> Path:
    """`data/<kind>/<name>.csv` — where this config's fetched numbers live."""
    return repo_root() / "data" / kind / f"{name}.csv"


def script_path(kind: str, name: str) -> Path:
    """`<kind>/<name>.py` — the optional custom renderer beside the config."""
    return repo_root() / kind / f"{name}.py"


def _merge(base: dict, override: dict) -> dict:
    """Shallow-recursive merge: `override` wins, nested mappings merge."""
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load(kind: str, name: str) -> dict:
    """One config, with `paper.yml` folded in.

    The result always carries `kind`, `name`, `document`, `data` and the
    kind-specific rendering block, so every consumer sees the same shape.
    """
    path = config_path(kind, name)
    if not path.is_file():
        available = ", ".join(config_names(kind)) or "(none)"
        raise SystemExit(f"error: no {kind[:-1]} config at {kind}/{name}.yml. Have: {available}")

    paper = read_paper_config()
    config = _read_yaml(path)

    if not config.get("document"):
        raise SystemExit(
            f"error: {kind}/{name}.yml has no `document:` — it does not say which "
            f"document under docs/ it belongs to."
        )

    key = RENDER_KEY[kind]
    return {
        "kind": kind,
        "name": name,
        "path": path,
        "document": config["document"],
        "data": _merge(
            _merge(paper["wandb"], {"round": paper["round"]}), config.get("data") or {}
        ),
        key: _merge(paper["style"], config.get(key) or {}),
        "raw": config,
    }
