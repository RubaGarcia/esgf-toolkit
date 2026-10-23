import sys

from esgf_stac.cli.catalog import write_collection_csvs
from esgf_stac.cli.plot import aggregate, filter_downloaded_variables, filter_rows, main

from .test_local import _sizes


def _local_rows():
    return [
        {"collection": "CMIP7", "model": "M1", "variable": "tas", "n_files": 5},
        {"collection": "CMIP7", "model": "M1", "variable": "tas", "n_files": 7},
        {"collection": "CMIP7", "model": "M1", "variable": "pr", "n_files": 2},
    ]


def test_aggregate_files_metric():
    result = aggregate(_local_rows(), "files")
    labels, variables, score, annotate = result["?"]
    assert labels == ["M1"]
    assert variables == ["pr", "tas"]
    assert score[0, variables.index("tas")] == 12
    assert score[0, variables.index("pr")] == 2
    assert annotate[0, variables.index("tas")] == "12"


def test_aggregate_status_metric():
    rows = [
        {"collection": "CMIP7", "model": "M1", "variable": "tas", "status": "complete"},
        {"collection": "CMIP7", "model": "M1", "variable": "tas", "status": "partial"},
        {"collection": "CMIP7", "model": "M1", "variable": "tas", "status": "missing"},
        {"collection": "CMIP7", "model": "M1", "variable": "pr", "status": "complete"},
    ]
    result = aggregate(rows, "status")
    labels, variables, score, annotate = result["?"]
    tas = variables.index("tas")
    assert score[0, tas] == 0.5  # (1 complete + 0.5 partial) / 3
    assert annotate[0, tas] == "1/3"
    assert score[0, variables.index("pr")] == 1.0


def test_aggregate_multi_frequency():
    rows = [
        {"collection": "CMIP7", "model": "M1", "variable": "tas", "frequency": "mon", "status": "complete"},
        {"collection": "CMIP7", "model": "M1", "variable": "tas", "frequency": "day", "status": "missing"},
        {"collection": "CMIP7", "model": "M1", "variable": "pr", "frequency": "mon", "status": "complete"},
    ]
    result = aggregate(rows, "status")
    assert set(result.keys()) == {"mon", "day"}
    mon_labels, mon_vars, mon_score, _ = result["mon"]
    assert mon_score[0, mon_vars.index("tas")] == 1.0
    day_labels, day_vars, day_score, _ = result["day"]
    assert day_score[0, day_vars.index("tas")] == 0.0


def test_filter_downloaded_variables_keeps_missing_rows():
    rows = [
        {"variable": "tas", "files_local": "3", "status": "partial"},
        {"variable": "tas", "files_local": "0", "status": "missing"},
        {"variable": "pr", "files_local": "0", "status": "missing"},
    ]
    out = filter_downloaded_variables(rows)
    assert [r["variable"] for r in out] == ["tas", "tas"]
    assert [r["status"] for r in out] == ["partial", "missing"]


def test_filter_downloaded_variables_local_catalogue():
    rows = [{"variable": "tas", "n_files": "5"}, {"variable": "pr", "n_files": "0"}]
    assert [r["variable"] for r in filter_downloaded_variables(rows)] == ["tas"]


def test_filter_rows_domain_matches_domain_and_grid_columns():
    local = [{"collection": "CORDEX-CMIP6", "domain": "EUR-12", "grid": ""},
             {"collection": "CORDEX-CMIP6", "domain": "NAM-12", "grid": ""}]
    assert [r["domain"] for r in filter_rows(local, None, {"domain": "EUR-12"})] == ["EUR-12"]
    assert [r["domain"] for r in filter_rows(local, None, {"grid": "EUR-12"})] == ["EUR-12"]

    compare = [{"collection": "CORDEX-CMIP6", "domain": "Europe",
                "domain_id": "EUR-12", "grid": "EUR-12"},
               {"collection": "CORDEX-CMIP6", "domain": "North America",
                "domain_id": "NAM-12", "grid": "NAM-12"}]
    assert [r["domain_id"] for r in filter_rows(compare, None, {"domain": "EUR-12"})] == ["EUR-12"]
    assert [r["domain_id"] for r in filter_rows(compare, None, {"grid": "EUR-12"})] == ["EUR-12"]


def test_plot_local_smoke(tmp_path, monkeypatch):
    from esgf_stac.local import catalog_rows

    csv_dir = tmp_path / "catalog"
    write_collection_csvs(catalog_rows(_sizes()), str(csv_dir))
    image = tmp_path / "catalog.png"
    monkeypatch.setattr(sys, "argv", ["plot", "--csv-dir", str(csv_dir), "--image", str(image)])
    main()
    assert image.exists()
