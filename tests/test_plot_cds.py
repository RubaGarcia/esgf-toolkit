from esgf_stac.cli.plot_cds import aggregate, filter_rows, row_status


def _rows():
    return [
        {"dataset": "era5", "variable": "t2m", "temporal_resolution": "hourly",
         "start_file_exists": "True", "final_file_exists": "True"},
        {"dataset": "era5", "variable": "t2m", "temporal_resolution": "daily",
         "start_file_exists": "True", "final_file_exists": "False"},
        {"dataset": "era5", "variable": "u10", "temporal_resolution": "hourly",
         "start_file_exists": "False", "final_file_exists": "False"},
        {"dataset": "cerra", "variable": "t2m", "temporal_resolution": "hourly",
         "start_file_exists": "True", "final_file_exists": "True"},
    ]


def test_row_status():
    assert row_status({"start_file_exists": "True", "final_file_exists": "True"}) == "downloaded"
    assert row_status({"start_file_exists": "True", "final_file_exists": "False"}) == "partial"
    assert row_status({"start_file_exists": "False", "final_file_exists": "False"}) == "not_downloaded"


def test_aggregate_cds():
    result = aggregate(_rows())
    assert set(result.keys()) == {"hourly", "daily"}
    labels, variables, score, annotate = result["hourly"]
    assert "era5" in labels
    assert "cerra" in labels
    assert "t2m" in variables
    assert "u10" in variables
    era5_idx = labels.index("era5")
    t2m_idx = variables.index("t2m")
    u10_idx = variables.index("u10")
    assert score[era5_idx, t2m_idx] == 1.0
    assert score[era5_idx, u10_idx] == 0.0
    cerra_idx = labels.index("cerra")
    assert score[cerra_idx, t2m_idx] == 1.0


def test_filter_rows():
    rows = _rows()
    filtered = filter_rows(rows, None, None, "hourly", None)
    assert len(filtered) == 3
    filtered = filter_rows(rows, None, None, None, None)
    assert len(filtered) == 4
