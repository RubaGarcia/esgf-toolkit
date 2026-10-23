from esgf_stac.local import LOCAL_COLUMNS, catalog_rows, parse_drs

CORDEX_FILE = (
    "CORDEX-CMIP6/DD/EUR-12/CNRM-MF/ERA5/evaluation/r1i1p1f1/CNRM-ALADIN64E1/"
    "v1-r1/1hr/zmla/v20260624/"
    "zmla_EUR-12_ERA5_evaluation_r1i1p1f1_CNRM-MF_CNRM-ALADIN64E1_v1-r1_mon_195901-196012.nc"
)
CMIP7_FILE = (
    "MIP-DS7/CMIP7/ScenarioMIP/UKNCSP/UKESM1-3-LL/esm-scen7-vl/r8i1p1f1/glb/"
    "mon/zos/tavg-u-hxy-sea/g126/v20260916/"
    "zos_tavg-u-hxy-sea_UKESM1-3-LL_esm-scen7-vl_r8i1p1f1_glb_185001-209912.nc"
)


def test_parse_drs_cordex():
    d = parse_drs(CORDEX_FILE)
    assert d["collection"] == "CORDEX-CMIP6"
    assert d["dataset"].endswith(".v1-r1.1hr.zmla")
    assert not d["dataset"].endswith("v20260624")
    assert d["leaf"].endswith("v20260624")
    f = d["facets"]
    assert f["activity"] == "DD"
    assert f["domain"] == "EUR-12"
    assert f["institution"] == "CNRM-MF"
    assert f["driving_institution"] == ""
    assert f["model"] == "CNRM-ALADIN64E1"
    assert f["rcm_model"] == "CNRM-ALADIN64E1"
    assert f["driving_model"] == "ERA5"
    assert f["experiment"] == "evaluation"
    assert f["member"] == "r1i1p1f1"
    assert f["frequency"] == "1hr"
    assert f["variable"] == "zmla"


def test_parse_drs_cmip7():
    d = parse_drs(CMIP7_FILE)
    assert d["collection"] == "CMIP7"
    assert d["leaf"].endswith("v20260916")
    f = d["facets"]
    assert f["activity"] == "ScenarioMIP"
    assert f["institution"] == "UKNCSP"
    assert f["model"] == "UKESM1-3-LL"
    assert f["driving_model"] == ""
    assert f["experiment"] == "esm-scen7-vl"
    assert f["member"] == "r8i1p1f1"
    assert f["frequency"] == "mon"
    assert f["grid"] == "g126"
    assert f["variable"] == "zos"


def test_parse_drs_without_version_dir():
    path = "CORDEX-CMIP6/DD/EUR-12/CNRM-MF/ERA5/evaluation/r1i1p1f1/CNRM-ALADIN64E1/v1-r1/1hr/zmla/x.nc"
    d = parse_drs(path)
    assert d["dataset"].replace(".", "/") == d["leaf"]
    assert d["facets"]["variable"] == "zmla"
    assert d["facets"]["model"] == "CNRM-ALADIN64E1"


def test_parse_drs_flat_and_unknown():
    flat = parse_drs("tas_day_model_historical_r1i1p1f1_gn_1850-1859.nc")
    assert flat["collection"] == ""
    assert flat["leaf"] == "."
    assert flat["facets"]["model"] == ""
    unknown = parse_drs("foo/bar/baz.nc")
    assert unknown["collection"] == "foo"
    assert unknown["leaf"] == "foo/bar"
    assert unknown["facets"]["variable"] == ""


def _sizes():
    base = CORDEX_FILE.rsplit("/", 1)[0]
    other_version = base.rsplit("/", 1)[0] + "/v20250101/zmla_196001-196912.nc"
    return {
        CORDEX_FILE: 100,
        base + "/zmla_196001-196912.nc": 200,
        other_version: 50,
        base + "/zmla_196001-196912.nc.part": 999,
        CMIP7_FILE: 300,
        "stray.txt": 7,
    }


def test_catalog_rows_grouping():
    rows = catalog_rows(_sizes())
    assert set(rows) == {"CORDEX-CMIP6", "CMIP7", "other"}
    cordex = rows["CORDEX-CMIP6"]
    assert len(cordex) == 2  # two versions -> two leaf-dir rows
    by_leaf = {r["leaf_dir"]: r for r in cordex}
    v2026 = [r for r in cordex if r["leaf_dir"].endswith("v20260624")][0]
    assert v2026["n_files"] == 2  # .part excluded
    assert v2026["size_bytes"] == 300
    assert v2026["variable"] == "zmla"
    assert len(by_leaf) == 2
    assert rows["CMIP7"][0]["n_files"] == 1
    assert rows["CMIP7"][0]["size_bytes"] == 300
    assert rows["other"][0]["leaf_dir"] == "."  # stray.txt
    for r in cordex + rows["CMIP7"] + rows["other"]:
        assert set(r) == set(LOCAL_COLUMNS)


def test_catalog_rows_filters():
    only_cmip7 = catalog_rows(_sizes(), {"collection": "CMIP7"})
    assert set(only_cmip7) == {"CMIP7"}
    only_var = catalog_rows(_sizes(), {"variable": "zmla"})
    assert set(only_var) == {"CORDEX-CMIP6"}
    only_model = catalog_rows(_sizes(), {"model": "CNRM-ALADIN64E1"})
    assert set(only_model) == {"CORDEX-CMIP6"}
    none = catalog_rows(_sizes(), {"variable": "tas"})
    assert none == {}
