r"""Writing a results table into a document, with the same provenance contract
as a figure.

A table of numbers copy-pasted from a notebook into `text.tex` is the single
most common way a paper ends up disagreeing with its own data: nothing records
where the numbers came from, and nothing notices when they change. So tables go
through `save_table`, land in `docs/<doc>/tables/<name>.tex`, and are checked by
`make check-generated` exactly like figure PDFs.

What is written is a bare `tabular` — no `\begin{table}`, no caption, no label.
Float placement, the caption and the label belong to the prose, which is yours:

    \begin{table}[!t]
      \centering
      \caption{Final scores, mean over five seeds.}
      \label{tab:final_scores}
      \input{tables/final_scores.tex}
    \end{table}

The tabular is built here rather than by `DataFrame.to_latex` so that the output
is byte-stable and does not move when pandas changes its LaTeX defaults.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from paperkit import provenance
from paperkit.paths import repo_root, tables_dir

__all__ = ["save_table"]

HEADER = (
    "%% GENERATED FILE — do not edit.\n"
    "%%\n"
    "%% Written from {script}\n"
    "%% out of the committed W&B cache. Rebuild with: make tables\n"
    "%%\n"
    "%% Editing this file by hand puts the paper's numbers out of step with the\n"
    "%% runs behind them, and `make check-generated` will not catch it — it checks\n"
    "%% the inputs, not the output. Change {source} instead.\n"
    "%%\n"
    "%% This is a bare tabular: wrap it in \\begin{{table}} with your caption and\n"
    "%% label in text.tex.\n"
)

# LaTeX special characters, longest-first so \ is replaced before the sequences
# that contain it.
_ESCAPES = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]


def _escape(text: str) -> str:
    for char, replacement in _ESCAPES:
        text = text.replace(char, replacement)
    return text


def _format_cell(value, decimals: int) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "--"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    if isinstance(value, int) and decimals == 0:
        return str(value)
    return _escape(str(value))


def save_table(
    df: pd.DataFrame,
    name: str,
    document: str,
    inputs: Iterable[str | Path] = (),
    script: str | Path | None = None,
    decimals: int = 2,
    per_column_decimals: dict[str, int] | None = None,
    index: bool = False,
    escape_header: bool = True,
    column_format: str | None = None,
) -> Path:
    r"""Write `df` as a booktabs tabular into `docs/<document>/tables/<name>.tex`.

    Args:
        df: the table. Column order and row order are written as given — sort
            before calling, so the output does not move between runs.
        name: file basename without extension (e.g. ``"final_scores"``).
        document: document directory name under ``docs/``.
        inputs: the cache files behind these numbers, normally
            ``[cache_path("<dataset>")]``. Recorded with content hashes so
            `make check-generated` detects staleness.
        script: defaults to the caller's ``__file__``.
        decimals: fixed decimal places for float cells. Fixed rather than
            repr-style for the same reason `make fetch` rounds: float repr
            differs in the last bits between machines.
        per_column_decimals: override `decimals` for named columns — a count
            column wants 0 places where a score wants 2.
        index: write the DataFrame index as a leading column.
        escape_header: escape LaTeX specials in column names. Turn off to put
            math in a header, e.g. ``$\sigma$``.
        column_format: override the alignment string (default: ``l`` for text
            columns, ``r`` for numeric ones).

    Returns:
        The path written.
    """
    if script is None:
        import inspect

        script = inspect.stack()[1].filename

    frame = df.reset_index() if index else df

    headers = [_escape(str(c)) if escape_header else str(c) for c in frame.columns]
    if column_format is None:
        column_format = "".join(
            "r" if pd.api.types.is_numeric_dtype(frame[c]) else "l" for c in frame.columns
        )
    if len(column_format) != len(frame.columns):
        raise ValueError(
            f"column_format {column_format!r} has {len(column_format)} entries "
            f"for {len(frame.columns)} columns"
        )

    places = [(per_column_decimals or {}).get(str(c), decimals) for c in frame.columns]
    rows = [
        " & ".join(_format_cell(v, p) for v, p in zip(row, places, strict=True)) + r" \\"
        for row in frame.itertuples(index=False, name=None)
    ]

    # A script run from outside the repository (an editor scratch buffer, a
    # notebook) still gets a usable header; only the pretty relative path is lost.
    script_rel = Path(script).resolve()
    with contextlib.suppress(ValueError):
        script_rel = script_rel.relative_to(repo_root())

    body = "\n".join(
        [
            HEADER.format(
                script=script_rel.as_posix(),
                source="the config" if script_rel.suffix == ".yml" else "the script",
            ),
            f"\\begin{{tabular}}{{{column_format}}}",
            r"\toprule",
            " & ".join(headers) + r" \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabular}",
        ]
    )

    target = tables_dir(document) / f"{name}.tex"
    resolved_inputs = [Path(p) for p in inputs]
    for file in resolved_inputs:
        if not file.is_file():
            raise FileNotFoundError(f"declared table input does not exist: {file}")

    target.write_text(body + "\n", newline="\n")
    provenance.record(target, document, resolved_inputs, Path(script))

    print(f"wrote {target.relative_to(repo_root())}")
    return target
