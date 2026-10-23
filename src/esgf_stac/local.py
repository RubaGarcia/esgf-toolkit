"""Local download-directory helpers."""

import os
import re

from .config import DRS_LAYOUTS
from .cql import parse_filter_values

# Columns of the per-collection catalogue CSVs (row order).
LOCAL_COLUMNS = [
    "collection", "activity", "domain", "institution", "driving_institution",
    "model", "rcm_model", "driving_model", "experiment", "member",
    "frequency", "grid", "variable", "leaf_dir",
    "n_files", "size_bytes", "size_gb",
]

_VERSION_RE = re.compile(r"v\d+")


def scan_local(out_dir: str):
    """Return ({relpath: size}, {basename: [relpaths]}) in a single walk."""
    sizes = {}
    base = {}
    for root, _, files in os.walk(out_dir):
        for f in files:
            full = os.path.join(root, f)
            rp = os.path.relpath(full, out_dir).replace(os.sep, "/")
            try:
                sizes[rp] = os.path.getsize(full)
            except OSError:
                continue
            base.setdefault(f, []).append(rp)
    return sizes, base


def is_present(lp: str, size, out_dir: str, sizes: dict, base: dict) -> bool:
    """Check whether a remote file is already downloaded (by path, then basename)."""
    if lp in sizes:
        return sizes[lp] == size if size else True
    for cand in base.get(os.path.basename(lp), []):
        if cand in sizes:
            return sizes[cand] == size if size else True
    return False


def _map_facets(raw: dict) -> dict:
    """DRS title keys -> catalogue facet columns (missing facets become '')."""
    return {
        "activity": raw.get("activity_id") or "",
        "domain": raw.get("domain_id") or "",
        "institution": raw.get("institution_id") or "",
        "driving_institution": raw.get("driving_institution_id") or "",
        "model": raw.get("source_id") or raw.get("driving_source_id") or "",
        "rcm_model": raw.get("source_id") or "",
        "driving_model": raw.get("driving_source_id") or "",
        "experiment": raw.get("experiment_id") or raw.get("driving_experiment_id") or "",
        "member": raw.get("variant_label") or raw.get("driving_variant_label") or "",
        "frequency": raw.get("frequency") or "",
        "grid": raw.get("grid_label") or "",
        "variable": raw.get("variable_id") or "",
    }


def parse_drs(relpath: str) -> dict:
    """Split a relative file path into its DRS dataset, leaf dir and facets.

    The mirrored download path is the STAC dataset id with '/' separators; the
    trailing 'vNNNNNNN' version directory is not part of the dataset identity.
    """
    parts = relpath.split("/")[:-1]
    if not parts:
        return {"collection": "", "dataset": "", "leaf": ".", "facets": _map_facets({})}
    head = parts[0]
    keys = coll_key = None
    for prefix, layout, ckey in DRS_LAYOUTS:
        if head.startswith(prefix):
            keys, coll_key = layout, ckey
            break
    if len(parts) > 1 and _VERSION_RE.fullmatch(parts[-1]):
        ds_parts = parts[:-1]
    else:
        ds_parts = parts
    raw = {}
    if keys:
        for cand in (ds_parts, parts):
            if len(cand) == len(keys):
                raw = dict(zip(keys, cand))
                break
    if raw.get(coll_key):
        collection = raw[coll_key]
    elif keys and head.startswith("MIP-DS") and len(parts) > 1:
        collection = parts[1]
    else:
        collection = head
    return {
        "collection": collection,
        "dataset": ".".join(ds_parts),
        "leaf": "/".join(parts),
        "facets": _map_facets(raw),
    }


def _row_matches(row: dict, filters: dict) -> bool:
    """True when every active filter (comma-separated values) hits the row."""
    for col, raw in filters.items():
        values = set(parse_filter_values(raw))
        if not values:
            continue
        cell = str(row.get(col) or "")
        parts = {p.strip() for p in cell.split(",") if p.strip()}
        if cell not in values and not (parts & values):
            return False
    return True


def catalog_rows(sizes: dict, filters: dict | None = None) -> dict:
    """Group scanned files into {collection: [leaf-dir rows]} with facet filters.

    One row per leaf directory, holding the parsed DRS facets plus the number
    of files and their total size; '.part' files are ignored.
    """
    active = {k: v for k, v in (filters or {}).items() if v}
    grouped = {}
    for relpath, size in sizes.items():
        if relpath.endswith(".part"):
            continue
        info = parse_drs(relpath)
        row = dict(info["facets"])
        row["collection"] = info["collection"]
        row["leaf_dir"] = info["leaf"]
        if not _row_matches(row, active):
            continue
        g = grouped.setdefault((info["collection"], info["leaf"]), row)
        g["n_files"] = g.get("n_files", 0) + 1
        g["size_bytes"] = g.get("size_bytes", 0) + (size or 0)
    out = {}
    order = [c for c in LOCAL_COLUMNS if c not in ("n_files", "size_bytes", "size_gb")]
    for (coll, _), row in grouped.items():
        row["size_gb"] = round(row["size_bytes"] / 1e9, 3)
        out.setdefault(coll or "other", []).append(row)
    for rows in out.values():
        rows.sort(key=lambda r: tuple(str(r.get(c, "")) for c in order))
    return out
