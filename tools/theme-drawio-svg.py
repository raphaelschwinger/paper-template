#!/usr/bin/env python3
"""Post-process draw.io SVG exports for light/dark mode compatibility.

The site CSS inverts drawio SVGs in dark mode via ``filter: invert(1)
hue-rotate(180deg)`` (see ``notes/site.css``). For that to work reliably,
the exported SVG must always render in its "light" form so the filter has
a consistent input to invert. Two things in recent drawio exports break
this and need to be neutered:

1. White shape fills (``fill="#ffffff"``). They were only there to match
   the white page in light mode; after ``invert(1)`` they become pure
   black rectangles that stick out against the dark page background.
   We replace them with ``fill="none"`` so the shape interior is
   transparent in both modes.

2. CSS ``light-dark(<light>, <dark>)`` calls in inline ``style`` attributes
   (and the root ``color-scheme: light dark`` declaration). Drawio adds
   these so the SVG auto-adapts to the OS theme. Combined with our CSS
   filter, this causes a *double* inversion when the OS is in dark mode
   (SVG renders in its dark form, then the filter inverts it again),
   producing dark boxes with near-invisible strokes. We collapse every
   ``light-dark(X, Y)`` call to just ``X`` (the light value) and drop the
   ``color-scheme: light dark`` declaration, so the SVG always renders in
   its light form.

We also strip the legacy opaque white background rectangle that some
older drawio exports place behind the whole diagram.

Usage:
    python tools/theme-drawio-svg.py         # process every *.drawio.svg under figures/generated/
    python tools/theme-drawio-svg.py path/to/file.drawio.svg ...

It is idempotent: running it multiple times on the same file is safe.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "figures" / "generated"

WHITE_FILL_ATTR_RE = re.compile(
    r'fill="(?:#[fF]{3}|#[fF]{6}|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))"'
)
# Same as above but inside an inline ``style="..."`` attribute, after we
# have resolved any ``light-dark()`` calls.
WHITE_FILL_STYLE_RE = re.compile(
    r"fill:\s*(?:#[fF]{3}|#[fF]{6}|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))"
)
# Matches ``light-dark(<light>, <dark>)`` where both arguments can contain
# nested parentheses (e.g. ``rgb(0, 0, 0)``). We resolve it by keeping only
# the first (light-mode) argument.
LIGHT_DARK_RE = re.compile(
    r"light-dark\(\s*"
    r"((?:[^(),]|\([^)]*\))+?)"  # light value: rgb(...) / #hex / named
    r"\s*,\s*"
    r"(?:[^(),]|\([^)]*\))+?"  # dark value (discarded)
    r"\s*\)"
)
COLOR_SCHEME_RE = re.compile(r"color-scheme:\s*light\s+dark;?\s*")


def process(svg_path: Path) -> tuple[int, int, int]:
    """Normalize an SVG for dark-mode-via-filter. Returns counts of
    (white_fills_replaced, light_dark_calls_resolved, page_rects_removed)."""
    original = svg_path.read_text(encoding="utf-8")
    updated = original

    # Resolve ``light-dark()`` first so whites hidden inside those calls
    # are exposed to the white-fill normalization below.
    updated, n_light_dark = LIGHT_DARK_RE.subn(r"\1", updated)
    updated = COLOR_SCHEME_RE.sub("", updated)
    updated, n_white_attr = WHITE_FILL_ATTR_RE.subn('fill="none"', updated)
    updated, n_white_style = WHITE_FILL_STYLE_RE.subn("fill: none", updated)
    n_white = n_white_attr + n_white_style

    n_page_rect = 0
    svg_open_match = re.search(r"<svg\b[^>]*>", updated)
    if svg_open_match:
        svg_body_start = svg_open_match.end()
        head = updated[:svg_body_start]
        body = updated[svg_body_start:]

        def _strip_first_page_rect(s: str) -> tuple[str, int]:
            # Only remove a full-page opaque rect that sits at the very start
            # of the SVG body (possibly wrapped in <g> / <defs>-adjacent
            # whitespace). We bail out quickly if the first element isn't such
            # a rect to avoid touching interior rectangles.
            prefix_re = re.compile(
                r"\A(\s*(?:<defs\b[^/]*/>\s*|<g\b[^>]*>\s*)*)"
                r'<rect\b[^>]*\bfill="#[fF]{3,6}"[^>]*/>\s*'
            )
            m = prefix_re.match(s)
            if not m:
                return s, 0
            return m.group(1) + s[m.end() :], 1

        body, n_page_rect = _strip_first_page_rect(body)
        updated = head + body

    if updated != original:
        svg_path.write_text(updated, encoding="utf-8")
    return n_white, n_light_dark, n_page_rect


def find_svgs(root: Path) -> list[Path]:
    return sorted(root.rglob("*.drawio.svg"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="SVG files (or directories) to process. Defaults to figures/generated/.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any file would be modified instead of writing changes.",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    if args.paths:
        for p in args.paths:
            if p.is_dir():
                targets.extend(find_svgs(p))
            elif p.suffix == ".svg" and p.name.endswith(".drawio.svg"):
                targets.append(p)
            else:
                print(f"skip (not a .drawio.svg file or directory): {p}", file=sys.stderr)
    else:
        if not DEFAULT_ROOT.exists():
            print(
                f"default generated-figures directory not found: {DEFAULT_ROOT}", file=sys.stderr
            )
            return 2
        targets = find_svgs(DEFAULT_ROOT)

    if not targets:
        print("no .drawio.svg files found", file=sys.stderr)
        return 0

    total_white = 0
    total_light_dark = 0
    total_rects = 0
    changed: list[Path] = []

    for svg in targets:
        before = svg.read_text(encoding="utf-8")
        n_white, n_light_dark, n_rect = process(svg)
        after = svg.read_text(encoding="utf-8")
        if before != after:
            changed.append(svg)
        if args.check and before != after:
            # Restore file; --check must not mutate the tree.
            svg.write_text(before, encoding="utf-8")
        total_white += n_white
        total_light_dark += n_light_dark
        total_rects += n_rect
        rel = svg.relative_to(REPO_ROOT) if svg.is_absolute() and REPO_ROOT in svg.parents else svg
        status = (
            "would change"
            if args.check and before != after
            else ("changed" if before != after else "ok")
        )
        print(
            f"{status:>12}  {rel}  "
            f"(white-fills: {n_white}, light-dark: {n_light_dark}, page-rect: {n_rect})"
        )

    print()
    print(
        f"summary: {len(changed)} file(s) modified, "
        f"{total_white} white fill(s) replaced, "
        f"{total_light_dark} light-dark() call(s) resolved, "
        f"{total_rects} page rect(s) removed"
    )

    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
