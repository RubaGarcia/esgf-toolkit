from esgf_stac.records import parse_title, strip_prefixes


def test_cordex_title():
    t = "CORDEX-CMIP6.DD.NAM-12.Ourans.CCCma.ssp370.r1i1p1f1.CRCM5-SN.v1-r1.mon.tas"
    d = parse_title(t, "CORDEX-CMIP6")
    assert d["domain_id"] == "NAM-12"
    assert d["variable_id"] == "tas"


def test_strip_prefixes():
    out = strip_prefixes({"cordex-cmip6:source_id": "CRCM5", "title": "x"})
    assert out == {"source_id": "CRCM5", "title": "x"}


def test_cql_body():
    from esgf_stac.cql import build_body

    body = build_body(None, 20, {"variable": "tas,hurs"})
    assert body["filter-lang"] == "cql2-json"
    assert body["limit"] == 20
