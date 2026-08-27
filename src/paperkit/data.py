"""Reading the committed W&B cache.

This is the **only** way a figure or table gets numbers. Nothing under
`figures/` or `tables/` imports `wandb`, takes a network call, or reads a
sibling code repository — which is what lets the paper rebuild on a laptop with
no API key, in CI with no secret, and for a coauthor who has no access to the
W&B project at all.

Each config owns its cache file:

    figures/learning_curve.yml   ->  data/figures/learning_curve.csv
    tables/final_scores.yml      ->  data/tables/final_scores.csv

filled by `make fetch` and pinned to a run set in `data/wandb.lock.yml`. See
README.md, "Where the numbers come from".
"""

from __future__ import annotations

import pandas as pd

from paperkit.config import cache_path, config_names

__all__ = ["load"]


def load(kind: str, name: str, **read_csv_kwargs) -> pd.DataFrame:
    """Read one config's fetched data.

    Raises with the command that would fix it rather than a bare
    FileNotFoundError, because "missing" here almost always means "never
    fetched".
    """
    path = cache_path(kind, name)
    if not path.is_file():
        known = "a known config" if name in config_names(kind) else "NOT a known config"
        raise FileNotFoundError(
            f"no cached data for {kind}/{name} at {path} — {name} is {known}.\n"
            f"Fetch it with:  make fetch DATASET={kind}/{name} REFRESH=1"
        )
    return pd.read_csv(path, **read_csv_kwargs)
