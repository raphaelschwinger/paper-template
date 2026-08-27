#!/usr/bin/env python3
"""Render every figure and table config into its document.

    uv run python tools/build.py figures            # make plots
    uv run python tools/build.py tables             # make tables
    uv run python tools/build.py figures tables     # both
    uv run python tools/build.py figures --only learning_curve

Each config under `figures/` or `tables/` is rendered by `paperkit.render`,
which uses the built-in renderers unless a `.py` beside the config takes over.
Output goes to `figures/generated/` (and a copy into `docs/<document>/figures/`
so the document compiles standalone) or `docs/<document>/tables/`, with
provenance recorded so `make check-generated` can detect staleness.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import config_names, repo_root


def cmd_list() -> int:
    """What exists, and where each one lands."""
    from paperkit import config as paperkit_config

    root = repo_root()
    for kind in ("figures", "tables"):
        names = config_names(kind, root)
        print(f"\n{kind}/ ({len(names)})")
        if not names:
            print("  (none)")
            continue
        for name in names:
            config = paperkit_config.load(kind, name)
            custom = (root / kind / f"{name}.py").is_file()
            renderer = (
                "custom .py"
                if custom
                else config["plot" if kind == "figures" else "table"].get("kind", "built-in")
            )
            dest = (
                f"figures/generated/{name}.pdf"
                if kind == "figures"
                else f"docs/{config['document']}/tables/{name}.tex"
            )
            print(f"  {name:<24} -> {dest}   [{renderer}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # No `choices=` here: argparse validates a list default against choices, so
    # `--list` with no positional args would fail on its own default.
    parser.add_argument("kinds", nargs="*", metavar="{figures,tables}")
    parser.add_argument("--only", help="render just this config, by name")
    parser.add_argument(
        "--list", action="store_true", help="list every config and the document it targets"
    )
    args = parser.parse_args(argv)

    if args.list:
        return cmd_list()

    if not args.kinds:
        parser.error("say which kinds to render: figures, tables, or both")
    for kind in args.kinds:
        if kind not in ("figures", "tables"):
            parser.error(f"invalid kind '{kind}' (choose from figures, tables)")

    # Imported here rather than at module scope: this pulls in matplotlib and
    # pandas, and `tools/` is otherwise import-light on purpose.
    from paperkit import config as paperkit_config
    from paperkit.render import render

    root = repo_root()
    rendered = 0

    for kind in args.kinds:
        names = config_names(kind, root)
        if args.only:
            if args.only not in names:
                raise SystemExit(
                    f"error: no {kind[:-1]} config named '{args.only}'. "
                    f"Have: {', '.join(names) or '(none)'}"
                )
            names = [args.only]

        if not names:
            print(f"no configs under {kind}/ — nothing to render")
            continue

        for name in names:
            print(f"--> {kind}/{name}.yml")
            render(paperkit_config.load(kind, name))
            rendered += 1

    if rendered == 0:
        print("nothing rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
