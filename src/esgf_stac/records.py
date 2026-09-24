"""STAC item -> flat record logic (properties first, title as fallback)."""

import urllib.parse

from .config import (
    CMIP7_TITLE_KEYS,
    CORDEX_TITLE_KEYS,
    PREFIXES,
)


def server_name(url: str) -> str:
    """Extract the hostname from a URL ('' on parse failure)."""
    try:
        return urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""


def prefix_for(collection: str) -> str:
    """Map a STAC collection name to its property-key prefix."""
    if collection.lower().startswith("cmip6plus"):
        return "cmip6plus:"
    if collection.lower().startswith("cmip6"):
        return "cmip6:"
    if collection.lower().startswith("cmip7"):
        return "cmip7:"
    if collection.lower().startswith("cordex"):
        return "cordex-cmip6:"
    if collection.lower().startswith("obs4ref"):
        return "obs4ref:"
    return ""


def get_prop(props, p: str, column: str):
    """Read a logical column from item properties; '?' when absent."""
    from .config import COLUMN_CANDIDATES

    for cand in COLUMN_CANDIDATES.get(column, []):
        value = props.get(f"{p}{cand}")
        if value is not None:
            return value
    return "?"


def availability(assets, statuses: dict) -> str:
    """'ok' all hosts healthy, 'down' all unhealthy, 'warn' mixed, '?' unknown."""
    hosts = {server_name(a.get("href")) for a in assets.values()
             if a.get("protocol") == "https" and "data" in a.get("roles", [])}
    hosts.discard("")
    if not hosts:
        return "?"
    states = {statuses.get(h, "?") for h in hosts}
    if "?" in states:
        return "?"
    if states <= {"ok"}:
        return "ok"
    if states <= {"down"}:
        return "down"
    return "warn"


def strip_prefixes(props: dict) -> dict:
    """Remove known '<prefix>:' from property keys (first hit wins on collision)."""
    out = {}
    for key, value in (props or {}).items():
        short = key
        for p in PREFIXES:
            if key.startswith(p):
                short = key[len(p):]
                break
        out.setdefault(short, value)
    return out


def parse_title(title: str | None, collection: str) -> dict:
    """Split a dot-separated dataset title into facet fields ({} when unknown layout)."""
    if not title:
        return {}
    parts = str(title).split(".")
    coll = (collection or "").lower()
    if coll.startswith("cordex") or parts[0].startswith("CORDEX"):
        if len(parts) == len(CORDEX_TITLE_KEYS):
            return dict(zip(CORDEX_TITLE_KEYS, parts))
        return {}
    if len(parts) == len(CMIP7_TITLE_KEYS):
        return dict(zip(CMIP7_TITLE_KEYS, parts))
    return {}


def _norm(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    return str(value)


def _first(*values: str) -> str:
    for v in values:
        if v:
            return v
    return ""


def item_to_record(item: dict, statuses: dict | None = None) -> dict:
    """Flatten one STAC item into a single snake_case record dict."""
    statuses = statuses or {}
    props = item.get("properties", {}) or {}
    collection = item.get("collection", "") or ""
    stripped = strip_prefixes(props)
    fallback = parse_title(stripped.get("title"), collection)

    merged = dict(fallback)
    supplemented = []
    for key, value in stripped.items():
        norm = _norm(value)
        if norm:
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    for key in fallback:
        if not _norm(stripped.get(key)):
            supplemented.append(key)

    def g(*names: str) -> str:
        for n in names:
            v = _norm(merged.get(n))
            if v:
                return v
        return ""

    rcm_model = g("source_id")
    driving_model = g("driving_source_id")
    driving_experiment = g("driving_experiment_id")
    experiment_id = g("experiment_id")
    driving_variant = g("driving_variant_label")
    variant = g("variant_label", "member_id")
    grid_label = g("grid_label")
    grid_raw = _norm(merged.get("grid"))
    realm = g("realm")
    domain_long = g("domain")

    assets = item.get("assets", {}) or {}
    data_assets = [a for a in assets.values()
                   if a.get("protocol") == "https" and "data" in (a.get("roles") or [])]
    hosts = sorted({server_name(a.get("href") or "") for a in data_assets} - {""})

    record = {
        "collection": collection,
        "project": _norm(props.get("project", merged.get("project_id", collection))),
        "item_id": item.get("id", "") or "",
        "title": g("title"),
        "activity_id": g("activity_id"),
        "domain_id": g("domain_id"),
        "domain": domain_long,
        "rcm_institution_id": g("institution_id"),
        "driving_institution_id": g("driving_institution_id"),
        "rcm_model": rcm_model,
        "driving_model": driving_model,
        "model": _first(rcm_model, driving_model),
        "driving_experiment_id": driving_experiment,
        "experiment_id": experiment_id,
        "experiment": _first(driving_experiment, experiment_id),
        "driving_variant_label": driving_variant,
        "variant_label": variant,
        "member": _first(variant, driving_variant),
        "variable_id": g("variable_id"),
        "variable_long_name": g("variable_long_name"),
        "variable_cf_standard_name": g("variable_cf_standard_name"),
        "variable_units": g("variable_units"),
        "frequency": g("frequency"),
        "grid_label": grid_label,
        "grid": _first(grid_label, g("domain_id"), grid_raw),
        "realm": realm,
        "product": g("product"),
        "mip_era": g("mip_era"),
        "version": g("version"),
        "version_realization": g("version_realization"),
        "start_datetime": _norm(props.get("start_datetime", "")),
        "end_datetime": _norm(props.get("end_datetime", "")),
        "size_bytes": props.get("size") if isinstance(props.get("size"), (int, float)) else 0,
        "n_files": len(data_assets),
        "n_servers": len(hosts),
        "servers": ",".join(hosts),
        "avail": availability(assets, statuses),
        "title_supplemented": ",".join(supplemented),
    }
    for key, value in merged.items():
        if key not in record:
            record[key] = _norm(value)
    return record
