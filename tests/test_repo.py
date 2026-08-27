"""Tests for the repository's own machinery.

These are not tests of a paper. They test the parts that, when they break,
break silently: a template that stopped listing an asset it needs, a provenance
record that `check_generated` cannot read back, a query hash that does not
notice a changed filter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import _common  # noqa: E402
import check_generated  # noqa: E402
import materialize  # noqa: E402

from paperkit import provenance  # noqa: E402
from paperkit.render.figures import _groups, _series_color  # noqa: E402
from paperkit.tables import _escape, save_table  # noqa: E402


def _forget(target: Path) -> None:
    """Remove a scratch artefact and its provenance entry."""
    target.unlink(missing_ok=True)
    data = provenance.read(target.parent)
    data.pop(target.name, None)
    (target.parent / provenance.PROVENANCE_FILENAME).write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n"
    )


# --- templates ---------------------------------------------------------------


def test_templates_exist():
    names = _common.list_templates(ROOT)
    assert names, "no templates under tools/templates/"
    assert "arxiv-custom" in names
    assert "ieee-conference" in names


def test_default_template_is_arxiv_custom():
    import new_paper  # noqa: E402

    assert new_paper.DEFAULT_TEMPLATE == "arxiv-custom"
    assert new_paper.DEFAULT_TEMPLATE in _common.list_templates(ROOT)


@pytest.mark.parametrize("name", _common.list_templates(ROOT))
def test_template_assets_exist(name):
    """A template listing an asset it does not ship fails only when someone
    switches to it — months later, mid-deadline. Catch it here instead."""
    template = _common.read_template(name, ROOT)
    assert template["main_tex"].is_file()
    for asset in template["asset_paths"]:
        assert asset.is_file(), f"template '{name}' lists missing asset {asset}"


@pytest.mark.parametrize("name", _common.list_templates(ROOT))
def test_template_loads_shared_macros(name):
    """Prose portability depends on every template loading researchcommon.sty
    and natbib. Without both, text.tex is welded to one venue format."""
    source = _common.read_template(name, ROOT)["main_tex"].read_text()
    assert "researchcommon" in source
    assert "natbib" in source


# --- the query hash ----------------------------------------------------------


def _cfg(**data):
    base = {
        "entity": "e",
        "project": "p",
        "round": 6,
        "kind": "history",
        "filters": {"tags": "v1", "state": "finished"},
    }
    base.update(data)
    return {"kind": "figures", "name": "x", "data": base, "plot": {}}


def test_spec_hash_ignores_key_order():
    a = _cfg()
    b = _cfg(filters={"state": "finished", "tags": "v1"})
    assert _common.spec_sha256(a) == _common.spec_sha256(b)


def test_spec_hash_changes_with_the_filter():
    assert _common.spec_sha256(_cfg()) != _common.spec_sha256(
        _cfg(filters={"tags": "v2", "state": "finished"})
    )


def test_spec_hash_changes_with_the_project():
    assert _common.spec_sha256(_cfg()) != _common.spec_sha256(_cfg(project="other"))


def test_spec_hash_ignores_the_rendering_block():
    """Restyling a figure must not invalidate its data."""
    a, b = _cfg(), _cfg()
    b["plot"] = {"ylabel": "something else", "colors": {"x": "red"}}
    assert _common.spec_sha256(a) == _common.spec_sha256(b)


def test_load_config_rejects_an_unknown_name():
    with pytest.raises(SystemExit):
        _common.load_config("figures", "no-such-figure", ROOT)


# --- the shipped repository is internally consistent -------------------------


def test_every_config_names_an_existing_document():
    documents = {p.name for p in _common.paper_dirs(ROOT)}
    for kind, name in _common.all_configs(ROOT):
        config = _common.load_config(kind, name, ROOT)
        assert config["document"] in documents, (
            f"{kind}/{name}.yml targets docs/{config['document']}, which does not exist"
        )


def test_config_inherits_paper_yml_defaults():
    paper = _common.read_paper_config(ROOT)
    for kind, name in _common.all_configs(ROOT):
        config = _common.load_config(kind, name, ROOT)
        assert config["data"]["entity"] == paper["wandb"]["entity"]
        assert config["data"]["round"] == paper["round"]


def test_configs_match_what_the_lock_pins():
    lock = _common.read_lock(ROOT)
    for kind, name in _common.all_configs(ROOT):
        if not _common.cache_path(kind, name, ROOT).is_file():
            continue  # never fetched — a warning, not a failure
        key = _common.lock_key(kind, name)
        assert key in lock, f"'{key}' has data but no lock entry"
        assert lock[key]["spec_sha256"] == _common.spec_sha256(
            _common.load_config(kind, name, ROOT)
        )


def test_cached_datasets_are_readable_and_nonempty():
    for path in sorted(_common.data_dir(ROOT).rglob("*.csv")):
        assert len(pd.read_csv(path)) > 0, f"{path} is empty"


# --- the figure renderers ----------------------------------------------------


def test_group_order_is_respected_and_nothing_is_dropped():
    """An `order:` that forgets a series must not silently remove it from the
    figure — that is a paper reporting fewer methods than it fetched."""
    data = pd.DataFrame({"m": ["a", "b", "c"], "x": [1, 2, 3], "y": [1, 2, 3]})
    labels = [label for label, _ in _groups(data, {"group": "m", "order": ["c", "a"]})]
    assert labels[:2] == ["c", "a"]
    assert set(labels) == {"a", "b", "c"}


def test_ungrouped_data_is_one_series():
    data = pd.DataFrame({"x": [1, 2], "y": [1, 2]})
    assert [label for label, _ in _groups(data, {})] == [None]


def test_group_rejects_a_missing_column():
    data = pd.DataFrame({"x": [1]})
    with pytest.raises(SystemExit):
        _groups(data, {"group": "nope"})


def test_explicit_colors_win_over_the_palette():
    plot = {"colors": {"a": "red"}, "palette": ["blue", "green"]}
    from paperkit.plotting import COLORS

    assert _series_color(plot, "a", 0) == COLORS["red"]
    assert _series_color(plot, "b", 1) == COLORS["green"]


def test_materialize_is_idempotent():
    """The second run must report nothing changed, or check-generated would
    fail on a clean tree straight after a sync."""
    for paper in _common.paper_dirs(ROOT):
        materialize.materialize(paper, ROOT)
        assert materialize.materialize(paper, ROOT) == []


def test_check_generated_passes_on_the_shipped_tree():
    assert check_generated.main([]) == 0


# --- provenance round-trips --------------------------------------------------


def test_save_table_records_provenance_check_generated_accepts():
    source = _common.cache_path("tables", "final_scores", ROOT)
    if not source.is_file():
        pytest.skip("no cached final_scores dataset in this tree")

    document = _common.paper_dirs(ROOT)[0]
    frame = pd.read_csv(source)
    target = save_table(frame, "_pytest_scratch", document.name, inputs=[source], script=__file__)
    try:
        record = provenance.read(target.parent)["_pytest_scratch.tex"]
        assert record["inputs"] == {
            source.resolve().relative_to(ROOT).as_posix(): provenance.digest(source)
        }
        report = _common.Reporter("t")
        check_generated.check_provenance(document / "tables", "make tables", ROOT, report)
        assert report.errors == []
    finally:
        _forget(target)


def test_check_generated_detects_a_changed_input(monkeypatch):
    """The property the whole design exists to enforce."""
    records = provenance.read(ROOT / "figures" / "generated")
    if not records:
        pytest.skip("the shipped document has no generated figures")

    name, record = next(iter(sorted(records.items())))
    input_rel = next(iter(record["inputs"]))
    corrupted = {**records, name: {**record, "inputs": {input_rel: "0" * 64}}}
    monkeypatch.setattr(check_generated, "read_provenance", lambda _d: corrupted)

    report = _common.Reporter("t")
    check_generated.check_provenance(ROOT / "figures" / "generated", "make plots", ROOT, report)
    assert any("STALE" in e for e in report.errors)


def test_table_output_is_byte_stable():
    """Two identical renders must produce identical bytes, or every `make
    tables` dirties the tree and CI's reproducibility gate becomes noise."""
    source = _common.cache_path("tables", "final_scores", ROOT)
    if not source.is_file():
        pytest.skip("no cached final_scores dataset in this tree")

    document = _common.paper_dirs(ROOT)[0].name
    frame = pd.read_csv(source)
    target = save_table(frame, "_pytest_stable", document, inputs=[source], script=__file__)
    try:
        content = target.read_bytes()
        save_table(frame, "_pytest_stable", document, inputs=[source], script=__file__)
        assert target.read_bytes() == content
    finally:
        _forget(target)


def test_table_escapes_latex_specials():
    assert _escape("a_b") == r"a\_b"
    assert _escape("100%") == r"100\%"
    assert _escape("a&b") == r"a\&b"
