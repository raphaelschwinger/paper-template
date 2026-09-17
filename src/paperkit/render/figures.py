"""Built-in figure renderers, and the hook a custom one implements.

A figure config's `plot:` block names a `kind` — `line`, `bar`, `scatter`, or
`butterfly` (a two-panel row chart, `paperkit.plotting.butterfly`) — and the
columns and labels that shape it. That covers most of what a paper needs. When
it does not, write `figures/<name>.py` beside the config defining either:

    def draw(data, cfg, ax):        # the usual case: you own the Axes
        ...

    def build(data, cfg):           # full control: return a Figure
        ...

Both receive the fetched DataFrame and the merged config. With `draw`, the
figure is created, labelled, legended and saved for you from the same `plot:`
keys the built-in renderers use, so a custom figure still obeys the house style
and still records provenance.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from paperkit.config import cache_path, script_path
from paperkit.data import load as load_data
from paperkit.plotting import COLORS, figure, save_figure
from paperkit.plotting.butterfly import draw_butterfly

__all__ = ["render_figure"]

# `line`/`bar`/`scatter` draw onto an Axes this module creates at a fixed size.
# `butterfly` needs full control of the canvas (its height depends on the row
# count, it draws no legend, it strips every spine) — same contract as a
# custom `figures/<name>.py` defining `build(data, cfg)` instead of `draw`.
KINDS = ("line", "bar", "scatter")
FULL_CANVAS_KINDS = {"butterfly": draw_butterfly}


def _series_color(plot: dict, label: str, index: int) -> str:
    """The colour for one series: explicit if named, else the palette in order."""
    explicit = (plot.get("colors") or {}).get(label)
    if explicit:
        return COLORS.get(explicit, explicit)
    palette = plot.get("palette") or list(COLORS)
    chosen = palette[index % len(palette)]
    return COLORS.get(chosen, chosen)


def _groups(data, plot: dict):
    """(label, frame) pairs, in the configured order.

    Ungrouped data yields a single unlabelled series, so the renderers below do
    not need a separate code path for it.
    """
    column = plot.get("group")
    if not column:
        return [(None, data)]
    if column not in data.columns:
        raise SystemExit(
            f"error: `group: {column}` is not a column in the fetched data. "
            f"Available: {', '.join(map(str, data.columns))}"
        )

    frames = {str(key): frame for key, frame in data.groupby(column, sort=True)}
    order = [str(k) for k in (plot.get("order") or sorted(frames))]
    unlisted = [k for k in sorted(frames) if k not in order]
    if unlisted and plot.get("order"):
        # An `order:` that forgets a series must not silently drop it from the
        # figure — that is a paper reporting fewer methods than it fetched.
        print(f"    note: not in `order:`, appended — {', '.join(unlisted)}")
    return [(k, frames[k]) for k in [*order, *unlisted] if k in frames]


def _require(plot: dict, key: str, name: str) -> str:
    value = plot.get(key)
    if not value:
        raise SystemExit(f"error: figures/{name}.yml: `plot.{key}` is required")
    return value


def _line(data, plot: dict, ax, name: str) -> None:
    x, y = _require(plot, "x", name), _require(plot, "y", name)
    band = plot.get("band")
    for index, (label, frame) in enumerate(_groups(data, plot)):
        color = _series_color(plot, label, index)
        ax.plot(frame[x], frame[y], label=label, color=color)
        if band:
            ax.fill_between(
                frame[x],
                frame[y] - frame[band],
                frame[y] + frame[band],
                alpha=plot.get("band_alpha", 0.18),
                linewidth=0,
                color=color,
            )


def _scatter(data, plot: dict, ax, name: str) -> None:
    x, y = _require(plot, "x", name), _require(plot, "y", name)
    for index, (label, frame) in enumerate(_groups(data, plot)):
        ax.scatter(
            frame[x],
            frame[y],
            label=label,
            color=_series_color(plot, label, index),
            s=plot.get("marker_size", 14),
        )


def _bar(data, plot: dict, ax, name: str) -> None:
    """Grouped bars, with optional symmetric error bars from `band:`.

    One bar per x value per series; series are placed side by side rather than
    stacked, which is what a results comparison almost always wants.
    """
    x, y = _require(plot, "x", name), _require(plot, "y", name)
    band = plot.get("band")
    groups = _groups(data, plot)
    categories = list(dict.fromkeys(data[x]))
    positions = range(len(categories))
    width = plot.get("bar_width", 0.8) / max(len(groups), 1)

    for index, (label, frame) in enumerate(groups):
        lookup = frame.set_index(x)
        offset = (index - (len(groups) - 1) / 2) * width
        heights = [lookup[y].get(c, 0) for c in categories]
        errors = [lookup[band].get(c, 0) for c in categories] if band else None
        ax.bar(
            [p + offset for p in positions],
            heights,
            width=width,
            yerr=errors,
            capsize=2,
            label=label,
            color=_series_color(plot, label, index),
        )

    ax.set_xticks(list(positions))
    ax.set_xticklabels([str(c) for c in categories])
    ax.grid(axis="x", visible=False)


RENDERERS = {"line": _line, "bar": _bar, "scatter": _scatter}


def _apply_axes(ax, plot: dict, labelled: bool) -> None:
    """Labels, limits, scales and legend — shared by built-in and custom draws."""
    if plot.get("xlabel"):
        ax.set_xlabel(plot["xlabel"])
    if plot.get("ylabel"):
        ax.set_ylabel(plot["ylabel"])
    if plot.get("title"):
        ax.set_title(plot["title"])
    if plot.get("xscale"):
        ax.set_xscale(plot["xscale"])
    if plot.get("yscale"):
        ax.set_yscale(plot["yscale"])
    # `null` in YAML becomes None, which is exactly matplotlib's "you decide".
    if plot.get("xlim"):
        ax.set_xlim(*plot["xlim"])
    if plot.get("ylim"):
        ax.set_ylim(*plot["ylim"])

    legend = plot.get("legend")
    if labelled and legend is not False:
        options = dict(legend) if isinstance(legend, dict) else {}
        ax.legend(**options)


def _load_custom(kind: str, name: str):
    """Import `<kind>/<name>.py`, if the author wrote one."""
    path = script_path(kind, name)
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"paperkit_custom_{kind}_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_figure(config: dict) -> Path:
    name, plot = config["name"], config["plot"]
    data = load_data("figures", name)
    source = cache_path("figures", name)
    custom = _load_custom("figures", name)
    script = script_path("figures", name) if custom else config["path"]
    kind = plot.get("kind", "line")

    # A custom `.py` always wins — a config can still override a built-in
    # `butterfly` figure with a bespoke `build`/`draw` if it ever needs to.
    if custom and hasattr(custom, "build"):
        fig = custom.build(data, config)
    elif kind in FULL_CANVAS_KINDS and not (custom and hasattr(custom, "draw")):
        fig = FULL_CANVAS_KINDS[kind](data, config)
    else:
        fig, ax = figure(width=plot.get("width", 3.3), height=plot.get("height", 2.2))
        if custom and hasattr(custom, "draw"):
            custom.draw(data, config, ax)
        else:
            if kind not in RENDERERS:
                raise SystemExit(
                    f"error: figures/{name}.yml: unknown `plot.kind: {kind}`.\n"
                    f"       Built-in kinds: {', '.join([*KINDS, *FULL_CANVAS_KINDS])}.\n"
                    f"       For anything else, write figures/{name}.py defining "
                    f"draw(data, cfg, ax)."
                )
            RENDERERS[kind](data, plot, ax, name)
        _apply_axes(ax, plot, labelled=bool(plot.get("group")))

    return save_figure(fig, name, config["document"], inputs=[source], script=script)
