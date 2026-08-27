"""Turning a config into a figure or a table.

Most figures in a paper are one of a handful of shapes, and writing twenty-five
lines of matplotlib for each is how a repository ends up with twenty subtly
different line plots. So a config renders itself:

    figures/learning_curve.yml   ->  figures/generated/learning_curve.pdf
    tables/final_scores.yml      ->  docs/<doc>/tables/final_scores.tex

When the built-in renderers cannot draw what you need, put a `.py` beside the
`.yml` with the same stem. It still gets its data and its style from the config;
it only takes over the drawing. See `render_figure` for the hooks it may define.
"""

from paperkit.render.figures import render_figure
from paperkit.render.tables import render_table

__all__ = ["render", "render_figure", "render_table"]


def render(config: dict):
    """Render one config, dispatching on its kind."""
    if config["kind"] == "figures":
        return render_figure(config)
    return render_table(config)
