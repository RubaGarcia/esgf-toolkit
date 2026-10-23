"""Shared constants for the ESGF STAC toolkit."""

CHUNK = 1024 * 256
PAGE_SIZE = 1000

NODES = {
    "east": "https://discovery.east.esgf.io",
    "west": "https://discovery.west.esgf.io",
}

DEFAULT_LIMIT = 20

PREFIXES = ["cmip7:", "cmip6plus:", "cmip6:", "cordex-cmip6:", "obs4ref:"]

COLUMN_CANDIDATES = {
    "model": ["source_id", "driving_source_id"],
    "rcm_model": ["source_id"],
    "driving_model": ["driving_source_id"],
    "experiment": ["experiment_id", "driving_experiment_id"],
    "driving_experiment": ["driving_experiment_id"],
    "variable": ["variable_id"],
    "frequency": ["frequency"],
    "grid": ["grid_label", "domain_id", "grid"],
    "domain": ["realm", "domain"],
    "member": ["variant_label", "member_id", "driving_variant_label"],
    "activity": ["activity_id"],
}

CORDEX_TITLE_KEYS = [
    "project_id", "activity_id", "domain_id", "institution_id",
    "driving_source_id", "driving_experiment_id", "driving_variant_label",
    "source_id", "version_realization", "frequency", "variable_id",
]

CMIP7_TITLE_KEYS = [
    "drs_specs", "mip_era", "activity_id", "institution_id", "source_id",
    "experiment_id", "variant_label", "area_label", "frequency",
    "variable_id", "temporal_label", "grid_label",
]

CORE_COLUMNS = [
    "collection", "project", "item_id", "title",
    "activity_id", "domain_id", "domain",
    "rcm_institution_id", "driving_institution_id",
    "rcm_model", "driving_model", "model",
    "driving_experiment_id", "experiment_id", "experiment",
    "driving_variant_label", "variant_label", "member",
    "variable_id", "variable_long_name", "variable_cf_standard_name", "variable_units",
    "frequency", "grid_label", "grid", "realm",
    "product", "mip_era", "version", "version_realization",
    "start_datetime", "end_datetime",
    "size_bytes", "n_files", "n_servers", "servers", "avail",
    "title_supplemented",
]

CORDEX_DISPLAY = [
    "project", "rcm_model", "driving_model", "driving_institution_id",
    "experiment", "n_variables", "frequency", "domain_id", "member",
    "time", "size_bytes", "n_files", "n_servers", "avail",
]

GENERIC_DISPLAY = [
    "project", "model", "experiment", "n_variables", "frequency",
    "grid_label", "realm", "member",
    "time", "size_bytes", "n_files", "n_servers", "avail",
]

FILE_COLUMNS = [
    "file_name", "local_path", "host", "href", "file_size", "checksum",
]
