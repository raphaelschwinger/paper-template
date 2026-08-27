"""Everything a figure or table script in this repository needs.

    from paperkit.data import load
    from paperkit.plotting import figure, save_figure
    from paperkit.tables import save_table

The package exists to make three things impossible to get wrong: where a script
reads its numbers from (`data/`, never W&B directly), where it writes its output
(`figures/generated/` and `docs/<doc>/tables/`, never anywhere else), and whether
that output records what it was built from (always — see `paperkit.provenance`).
"""

__all__ = ["data", "paths", "plotting", "provenance", "tables"]
