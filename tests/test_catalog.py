import argparse
import csv
import sys

from esgf_stac.cli import catalog as catalog_mod
from esgf_stac.cli.catalog import (
    LOCAL_COLUMNS,
    compare_columns,
    compare_view,
    main,
    run_compare,
    summarize,
    write_collection_csvs,
)
from esgf_stac.cli.common import default_out, union_fieldnames
from esgf_stac.local import catalog_rows

from .test_local import CMIP7_FILE, CORDEX_FILE, _sizes


def _cmp_row(**kw):
    row = {
        "collection": "CORDEX-CMIP6", "project": "CORDEX-CMIP6",
        "rcm_model": "CNRM-ALADIN64E1", "driving_model": "ERA5",
        "driving_institution_id": "ECMWF", "experiment": "evaluation",
        "variable_id": "zmla", "frequency": "mon", "domain_id": "EUR-12",
        "member": "r1i1p1f1",
        "start_datetime": "1959-01-16T12:00:00Z",
        "end_datetime": "2022-12-16T12:00:00Z",
        "size_bytes": 561616136, "n_files": 8, "n_servers": 1, "avail": "ok",
        "status": "complete", "files": "8/8", "size_gb": "0.56/0.56",
        "available": "ok",
    }
    row.update(kw)
    return row


def test_compare_view_report():
    rows = [_cmp_row(),
            _cmp_row(experiment="historical", variable_id="zg", status="missing",
                     files="0/14", n_files=14, available="?")]
    view = compare_view(rows)
    cols = compare_columns(view)
    assert cols[-2:] == ["local/remote", "status"]
    assert "variable_id" in cols and "n_variables" not in cols
    assert "avail" in cols and "time" in cols
    assert cols[cols.index("experiment") + 1] == "variable_id"
    assert view["local/remote"].tolist() == ["8/8", "0/14"]
    assert view["avail"].tolist() == ["ok", "?"]
    assert str(view["time"].iloc[0]).startswith("1959-01-16 → 2022-12-16")
    assert view["status"].tolist() == ["complete", "missing"]


def test_summarize_counts_all_datasets():
    rows = [_cmp_row(),
            _cmp_row(status="partial", files="4/8"),
            _cmp_row(status="missing", files="0/8")]
    assert summarize(rows) == "Summary: 3 datasets — 1 complete, 1 partial, 1 missing"


def test_default_out_prefers_esgf_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ESGF", str(tmp_path))
    assert default_out() == str(tmp_path)
    monkeypatch.delenv("ESGF")
    assert default_out() == "./esgf_data"


def test_write_collection_csvs(tmp_path):
    written = write_collection_csvs(catalog_rows(_sizes()), str(tmp_path))
    assert [p.split("/")[-1] for p in written] == ["CMIP7.csv", "CORDEX-CMIP6.csv", "other.csv"]
    with open(tmp_path / "CORDEX-CMIP6.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == LOCAL_COLUMNS
    assert len(rows) == 2
    assert rows[0]["collection"] == "CORDEX-CMIP6"
    assert int(rows[0]["n_files"]) in (1, 2)


def test_union_fieldnames_covers_extra_keys():
    rows = [{"a": 1, "b": 2}, {"b": 3, "c": 4}]
    assert union_fieldnames(rows) == ["a", "b", "c"]


def _item(item_id, **props):
    return {
        "id": item_id,
        "collection": "CORDEX-CMIP6",
        "properties": props,
        "assets": {"f": {"protocol": "https", "roles": ["data"], "href": "https://x/f",
                         "file:size": 10, "file:local_path": "p/f"}},
    }


def test_run_compare_writes_csv_with_varying_item_properties(tmp_path, monkeypatch):
    items = [
        _item("a", variable_id="tas", start_datetime="2000-01-01T00:00:00Z",
              end_datetime="2000-12-31T00:00:00Z"),
        _item("b", variable_id="pr", base_id="CORDEX-CMIP6.EUR-12",
              start_datetime="2000-01-01T00:00:00Z", end_datetime="2000-12-31T00:00:00Z"),
    ]
    monkeypatch.setattr(catalog_mod, "iter_items", lambda *a, **k: iter(items))
    monkeypatch.setattr(catalog_mod, "load_health", lambda *a, **k: ({}, {}))
    csv_path = tmp_path / "catalog.csv"
    args = argparse.Namespace(node="east", collection="CORDEX-CMIP6", out=str(tmp_path),
                              csv=str(csv_path), health="", missing_only=False)
    rows = run_compare(args, {}, {}, {})
    assert len(rows) == 2
    with open(csv_path, newline="") as f:
        written = list(csv.DictReader(f))
    assert "base_id" in written[0]
    assert written[0]["base_id"] == ""
    assert written[1]["base_id"] == "CORDEX-CMIP6.EUR-12"


def test_main_local_offline(tmp_path, monkeypatch):
    out = tmp_path / "esgf_data"
    for rel in (CORDEX_FILE, CMIP7_FILE):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 10)
    csv_dir = tmp_path / "catalog"
    monkeypatch.setattr(sys, "argv", ["catalog", "--out", str(out), "--csv-dir", str(csv_dir)])
    main()
    assert (csv_dir / "CORDEX-CMIP6.csv").exists()
    assert (csv_dir / "CMIP7.csv").exists()


def test_main_local_collection_scoped(tmp_path, monkeypatch):
    out = tmp_path / "esgf_data"
    for rel in (CORDEX_FILE, CMIP7_FILE):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 10)
    csv_dir = tmp_path / "catalog"
    monkeypatch.setattr(sys, "argv", ["catalog", "--out", str(out),
                                      "--csv-dir", str(csv_dir), "--collection", "CMIP7"])
    main()
    assert (csv_dir / "CMIP7.csv").exists()
    assert not (csv_dir / "CORDEX-CMIP6.csv").exists()
