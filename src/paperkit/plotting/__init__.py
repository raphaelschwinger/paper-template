"""Shared figure style and the `save_figure` entry point.

Every data-driven figure in every document goes through `save_figure`. That buys
three things this repository depends on:

1.  **One visual language.** `apply_style()` is applied on import, so figures
    from different scripts look like they belong in the same paper.

2.  **Byte-stable PDFs.** Timestamps are stripped and fonts embedded as
    TrueType. Without this, rebuilding an unchanged figure produces a different
    file every time, the committed PDFs churn in git on every `make plots`, and
    CI's "figures are reproducible" gate can never pass.

3.  **Provenance.** Each figure records the script and the input CSVs it was
    built from, with content hashes, into
    `figures/generated/.provenance.json`. `tools/check_generated.py` reads that
    back and fails when a figure is stale. This is what makes "the paper's
    numbers came from these runs" checkable.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

import matplotlib

# Non-interactive backend: figures are built in CI and over SSH, never shown.
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from paperkit import provenance
from paperkit.paths import figures_dir, generated_figures_dir, repo_root

__all__ = ["COLORS", "apply_style", "figure", "save_figure"]

# Accent palette shared with the draw.io styles (tools/drawio_styles.py),
# so hand-drawn diagrams and data plots use the same colours.
COLORS = {
    "blue": "#6c8ebf",
    "green": "#82b366",
    "orange": "#d79b00",
    "red": "#b85450",
    "purple": "#9673a6",
    "grey": "#666666",
}


def apply_style() -> None:
    """Apply the repo-wide matplotlib style. Idempotent."""
    plt.rcParams.update(
        {
            # Determinism: TrueType fonts, no timestamps (see savefig metadata).
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.hashsalt": "paper-template",
            # Typography sized for a two-column paper at ~3.3in width.
            # DejaVu Sans and nothing else: it ships *inside* matplotlib, so the
            # same font file is embedded on a laptop and in CI. Preferring a
            # system font (Helvetica, Arial) silently changes the embedded font
            # with the machine, and the committed PDF stops being reproducible.
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"],
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            # Restrained frame: no top/right spines, light grid.
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linewidth": 0.5,
            "axes.prop_cycle": plt.cycler(color=list(COLORS.values())),
            "figure.constrained_layout.use": True,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "lines.linewidth": 1.5,
        }
    )


apply_style()


def figure(width: float = 3.3, height: float = 2.2, **kwargs):
    """A figure sized for one column of a two-column paper (inches)."""
    return plt.subplots(figsize=(width, height), **kwargs)


def save_figure(
    fig,
    name: str,
    document: str,
    inputs: Iterable[str | Path] = (),
    script: str | Path | None = None,
    close: bool = True,
) -> Path:
    """Write `fig` into `figures/generated/<name>.pdf` and record provenance.

    A byte-identical copy is placed in `docs/<document>/figures/` so the
    document directory still compiles standalone (Overleaf, `make arxiv`).

    Args:
        fig: the matplotlib Figure.
        name: figure basename, without extension (e.g. ``"learning_curve"``).
        document: document directory name under ``docs/`` (e.g. ``"paper-example"``).
        inputs: the cache files this figure was built from, normally
            ``[cache_path("<dataset>")]``. Recorded with content hashes so
            `make check-generated` can detect staleness. Passing nothing means
            the figure claims no data dependency — correct for a purely
            illustrative plot, wrong for anything reporting results.
        script: the script that produced the figure; defaults to the caller's
            ``__file__`` when invoked from a module.
        close: close the figure afterwards (avoids leaking figures in loops).

    Returns:
        The path written under ``figures/generated/``.
    """
    if script is None:
        import inspect

        script = inspect.stack()[1].filename

    target = generated_figures_dir() / f"{name}.pdf"
    resolved_inputs = [Path(p) for p in inputs]
    for file in resolved_inputs:
        if not file.is_file():
            raise FileNotFoundError(f"declared figure input does not exist: {file}")

    # `CreationDate: None` strips the timestamp, making the PDF byte-stable
    # across rebuilds. Without it every `make plots` dirties the git tree.
    fig.savefig(target, format="pdf", metadata={"CreationDate": None})

    provenance.record(target, document, resolved_inputs, Path(script))

    copy = figures_dir(document) / f"{name}.pdf"
    shutil.copyfile(target, copy)

    if close:
        plt.close(fig)

    print(f"wrote {target.relative_to(repo_root())}")
    return target
