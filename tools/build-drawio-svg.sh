#!/usr/bin/env bash
# Export one or more `.drawio` files to SVG/PNG/PDF via the draw.io desktop CLI,
# then run the normalization pass so the result plays nicely with the
# notes site's light/dark-mode filter.
#
# Sources live in figures/; exports land in figures/generated/.
#
# Usage:
#   tools/build-drawio-svg.sh figures/dqn-algorithm-flow.drawio
#   tools/build-drawio-svg.sh figures/*.drawio
#   tools/build-drawio-svg.sh       # (re)build every .drawio under figures/
#
# Requires:
#   - draw.io desktop app (macOS: `brew install --cask drawio`)
#   - python3 (stdlib only — used for the normalization script)
set -euo pipefail

# Locate the draw.io CLI.
if command -v draw.io >/dev/null 2>&1; then
  DRAWIO=draw.io
elif [ -x "/Applications/draw.io.app/Contents/MacOS/draw.io" ]; then
  DRAWIO="/Applications/draw.io.app/Contents/MacOS/draw.io"
elif [ -x "/Applications/drawio.app/Contents/MacOS/drawio" ]; then
  DRAWIO="/Applications/drawio.app/Contents/MacOS/drawio"
else
  echo "error: draw.io CLI not found. Install with: brew install --cask drawio" >&2
  exit 127
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIGURES_DIR="$REPO_ROOT/figures"
GENERATED_DIR="$REPO_ROOT/figures/generated"
NORMALIZE="$REPO_ROOT/tools/theme-drawio-svg.py"
# Minimal padding around diagram content (draw.io default border is 0).
DRAWIO_BORDER=0

mkdir -p "$GENERATED_DIR"

# Collect inputs. Only top-level `figures/*.drawio` — generated/ is output.
inputs=()
if [ $# -eq 0 ]; then
  while IFS= read -r -d '' f; do
    inputs+=("$f")
  done < <(find "$FIGURES_DIR" -maxdepth 1 -type f -name "*.drawio" -print0)
else
  inputs=("$@")
fi

if [ ${#inputs[@]} -eq 0 ]; then
  echo "no .drawio files to export" >&2
  exit 0
fi

exported=()
for src in "${inputs[@]}"; do
  if [ ! -f "$src" ]; then
    echo "skip (not a file): $src" >&2
    continue
  fi
  stem="$(basename "${src%.drawio}")"
  out_svg="$GENERATED_DIR/${stem}.drawio.svg"
  out_png="$GENERATED_DIR/${stem}.drawio.png"
  out_pdf="$GENERATED_DIR/${stem}.drawio.pdf"
  echo "exporting  $src  ->  $out_svg"
  "$DRAWIO" -x -f svg -o "$out_svg" "$src"
  echo "exporting  $src  ->  $out_pdf"
  "$DRAWIO" -x -f pdf -e -b "$DRAWIO_BORDER" --crop -o "$out_pdf" "$src"
  echo "exporting  $src  ->  $out_png"
  "$DRAWIO" -x -f png -s 2 -b "$DRAWIO_BORDER" -o "$out_png" "$src"
  exported+=("$out_svg")
done

if [ ${#exported[@]} -eq 0 ]; then
  exit 0
fi

echo
echo "normalizing exported SVG(s) for light/dark-mode compatibility..."
python3 "$NORMALIZE" "${exported[@]}"
