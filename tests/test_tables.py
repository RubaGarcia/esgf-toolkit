import pandas as pd

from esgf_stac.tables import collapse_variables, display_columns


def _row(**kw):
    base = {
        "collection": "CORDEX-CMIP6", "project": "CORDEX-CMIP6",
        "item_id": "x.tas", "title": "CORDEX-CMIP6.DD.NAM-12.OURANOS.CCCma.ssp370."
                                     "r1i1p1f1.CRCM5-SN.v1-r1.mon.tas",
        "experiment": "ssp370", "model": "CRCM5-SN", "driving_model": "CanESM5-1",
        "domain_id": "NAM-12", "frequency": "mon", "member": "r1i1p1f1",
        "variable_id": "tas", "variable_long_name": "Near-Surface Air Temperature",
        "start_datetime": "2015-01-16T12:00:00Z", "end_datetime": "2100-12-16T12:00:00Z",
        "size_bytes": 100, "n_files": 5, "n_servers": 1, "avail": "ok",
        "pid": "hdl:1", "created": "2026-01-01", "updated": "2026-01-02",
    }
    base.update(kw)
    base["item_id"] = base["title"] + ".v1"
    return base


def _df():
    return pd.DataFrame([
        _row(),
        _row(title="CORDEX-CMIP6.DD.NAM-12.OURANOS.CCCma.ssp370.r1i1p1f1.CRCM5-SN.v1-r1.mon.pr",
             variable_id="pr", variable_long_name="Precipitation", size_bytes=50,
             n_files=3, pid="hdl:2", created="2026-01-03", updated="2026-01-04"),
        _row(title="CORDEX-CMIP6.DD.NAM-12.OURANOS.CCCma.ssp370.r1i1p1f1.CRCM5-SN.v1-r1.mon.tasmax",
             variable_id="tasmax", variable_long_name="Daily Maximum Temperature",
             size_bytes=25, n_files=5, pid="hdl:3"),
        _row(experiment="historical",
             title="CORDEX-CMIP6.DD.NAM-12.OURANOS.CCCma.historical.r1i1p1f1.CRCM5-SN.v1-r1.mon.tas"),
    ])


def test_collapse_merges_variable_rows():
    out = collapse_variables(_df())
    assert len(out) == 2
    ssp = out[out["experiment"] == "ssp370"].iloc[0]
    assert ssp["n_variables"] == 3
    assert ssp["variable_id"] == "pr,tas,tasmax"
    assert ssp["size_bytes"] == 175
    assert ssp["n_files"] == 13


def test_collapse_stars_title_and_item_id():
    out = collapse_variables(_df())
    ssp = out[out["experiment"] == "ssp370"].iloc[0]
    assert ssp["title"] == "CORDEX-CMIP6.DD.NAM-12.OURANOS.CCCma.ssp370.r1i1p1f1.CRCM5-SN.v1-r1.mon.*"
    assert ssp["item_id"].endswith("mon.*.v1")
    assert "variable_long_name" not in out.columns


def test_collapse_keeps_different_datasets_apart():
    out = collapse_variables(_df())
    assert list(out["experiment"]) == ["ssp370", "historical"]
    hist = out[out["experiment"] == "historical"].iloc[0]
    assert hist["n_variables"] == 1
    assert hist["variable_id"] == "tas"


def test_collapse_single_row():
    out = collapse_variables(_df().head(1))
    assert len(out) == 1
    assert out.iloc[0]["n_variables"] == 1
    assert out.iloc[0]["size_bytes"] == 100


def test_collapse_noop_without_variable_id():
    df = _df().drop(columns=["variable_id"])
    assert collapse_variables(df).equals(df)
    assert collapse_variables(pd.DataFrame()).empty


def test_display_columns_include_n_variables():
    from esgf_stac.tables import combine_time

    view = combine_time(collapse_variables(_df()))
    cols = display_columns(view)
    assert "n_variables" in cols
    assert "variable_id" not in cols
    assert "time" in cols
    assert "start_datetime" not in cols and "end_datetime" not in cols
    assert cols.index("n_variables") == cols.index("experiment") + 1
    assert list(display_columns(view, "variable_id,n_variables")) == ["variable_id", "n_variables"]


def test_combine_time():
    from esgf_stac.tables import combine_time

    df = pd.DataFrame([
        {"start_datetime": "1950-01-16T12:00:00Z", "end_datetime": "2014-12-16T12:00:00Z"},
        {"start_datetime": "2022-01-16T00:00:00Z", "end_datetime": "2022-01-16T00:00:00Z"},
        {"start_datetime": "2022-01-16T06:00:00Z", "end_datetime": "2022-01-16T18:00:00Z"},
        {"start_datetime": "", "end_datetime": ""},
    ])
    out = combine_time(df)
    assert out["time"].tolist() == [
        "1950-01-16 → 2014-12-16",
        "2022-01-16",
        "2022-01-16T06:00:00Z → 2022-01-16T18:00:00Z",
        "",
    ]
    assert "start_datetime" in out.columns and "end_datetime" in out.columns
    assert combine_time(pd.DataFrame({"x": [1]})).empty is False


def _cmip7_df():
    def row(var, vert, temporal, size, pid):
        title = (f"MIP-DRS7.CMIP7.ScenarioMIP.UKNCSP.UKESM1-3-LL.esm-scen7-vl."
                 f"r8i1p1f1.glb.mon.{var}.{temporal}avg-{vert}-hxy-u.g110")
        return {
            "project": "CMIP7", "title": title, "item_id": title + ".v20260915",
            "base_id": title, "vertical_label": vert, "temporal_label": temporal,
            "variable_id": var, "grid_label": "g110", "member": "r8i1p1f1",
            "size_bytes": size, "n_files": 1, "n_servers": 1, "pid": pid,
        }

    return pd.DataFrame([
        row("tas", "h2m", "tmin", 10, "hdl:1"),
        row("tas", "h2m", "tmax", 11, "hdl:2"),
        row("tas", "h2m", "tavg", 12, "hdl:3"),
        row("pr", "u", "tavg", 13, "hdl:4"),
    ])


def test_collapse_merges_variable_specific_facets():
    out = collapse_variables(_cmip7_df())
    assert len(out) == 3
    tavg = out[out["temporal_label"] == "tavg"].iloc[0]
    assert tavg["n_variables"] == 2
    assert tavg["variable_id"] == "pr,tas"
    assert tavg["size_bytes"] == 25
    assert out["n_variables"].tolist() == [1, 1, 2]


def test_collapse_merges_title_tokens_per_position():
    out = collapse_variables(_cmip7_df())
    tavg = out[out["temporal_label"] == "tavg"].iloc[0]
    assert tavg["title"] == ("MIP-DRS7.CMIP7.ScenarioMIP.UKNCSP.UKESM1-3-LL."
                             "esm-scen7-vl.r8i1p1f1.glb.mon.*.*.g110")
    assert tavg["item_id"].endswith(".v20260915")
    tmin = out[out["temporal_label"] == "tmin"].iloc[0]
    assert tmin["title"].endswith(".mon.tas.tminavg-h2m-hxy-u.g110")


def test_print_dataframe_cuts_long_cells(capsys=None):
    import io
    from contextlib import redirect_stdout

    from esgf_stac.tables import print_dataframe

    buf = io.StringIO()
    with redirect_stdout(buf):
        print_dataframe(pd.DataFrame({"variable_id": ["x" * 60], "n_variables": [1]}))
    assert "x" * 37 + "..." in buf.getvalue()
    assert "x" * 40 not in buf.getvalue()
