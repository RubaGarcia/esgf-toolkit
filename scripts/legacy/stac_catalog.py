#!/usr/bin/env python3
"""Catalogue: compare what is downloaded locally vs what the ESGF servers offer.

Scans a local download dir (default ./esgf_data), asks the STAC API for the
matching remote datasets, and reports each dataset as complete / partial /
missing. Writes a CSV and, with --show, prints a table on screen.

Run periodically (or after stac_download) to see what still needs downloading.
"""

import argparse
import csv
import os
import sys

import requests

import esgf

STATUS_OK = "complete"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing"

# Compact on-screen profile; the CSV always carries the full pandas table.
SHOW_COLS = ["project", "model", "experiment", "variable_id", "frequency",
             "grid", "domain", "member", "status", "files", "size_gb",
             "n_servers", "available"]


def fmt_gb(size_bytes) -> str:
    """Format a byte count as 'X.XX GB' ('-' when unknown).

    Used in: none currently (stac_catalog uses gb()/fmt_row instead; kept for symmetry with stac_search.fmt_gb).
    """
    if size_bytes is None:
        return "-"
    return f"{size_bytes / 1e9:.2f} GB"


def build_filters(args) -> dict:
    """Collect the CLI filter arguments into the {column: value} dict expected by esgf.build_body.

    Used in: stac_catalog.main, stac_plot.compute_rows, stac_plot.load_rows.
    """
    return {
        "model": args.model,
        "rcm_model": args.rcm_model,
        "driving_model": args.driving_model,
        "experiment": args.experiment,
        "variable": args.variable,
        "frequency": args.frequency,
        "grid": args.grid,
        "member": args.member,
        "domain": args.domain,
        "activity": args.activity,
    }


def scan_local(out_dir: str):
    """Return ({relpath: size}, {basename: [relpaths]}) in a single walk.

    Used in: stac_catalog.main, stac_plot.compute_rows.
    """
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
    """Check whether a remote file is already downloaded locally (by path, then basename), matching size if given.

    Used in: fmt_row.
    """
    if lp in sizes:
        return sizes[lp] == size if size else True
    for cand in base.get(os.path.basename(lp), []):
        if cand in sizes:
            return sizes[cand] == size if size else True
    return False


def gb(size):
    """Convert bytes to GB (None-safe, returns 0).

    Used in: fmt_row.
    """
    return (size or 0) / 1e9


def fmt_row(item, out_dir: str, sizes: dict, base: dict, statuses: dict, show_missing_only: bool):
    """Turn one STAC item into a catalogue row: full esgf.item_to_record() metadata + local/remote counts.

    Status is complete/partial/missing based on how many remote files exist
    locally. Returns None when the item has no https data assets or when it is
    complete and show_missing_only is set.
    Used in: stac_catalog.main, stac_plot.compute_rows.
    """
    row = esgf.item_to_record(item, statuses)
    assets = [a for a in item.get("assets", {}).values() if a.get("protocol") == "https" and "data" in a.get("roles", [])]
    if not assets:
        return None

    size_remote = sum(a.get("file:size") or 0 for a in assets)
    size_local = 0
    n_local = 0
    for a in assets:
        lp = a.get("file:local_path")
        size = a.get("file:size")
        if lp and is_present(lp, size, out_dir, sizes, base):
            n_local += 1
            size_local += size or 0

    n_remote = len(assets)
    if n_local == 0:
        status = STATUS_MISSING
    elif n_local >= n_remote:
        status = STATUS_OK
    else:
        status = STATUS_PARTIAL

    if show_missing_only and status == STATUS_OK:
        return None

    row["files_remote"] = n_remote
    row["files_local"] = n_local
    row["size_remote_gb"] = round(gb(size_remote), 3)
    row["size_local_gb"] = round(gb(size_local), 3)
    row["status"] = status
    row["available"] = row.pop("avail")
    row["files"] = f"{n_local}/{n_remote}"
    row["size_gb"] = f"{row['size_local_gb']:.2f}/{row['size_remote_gb']:.2f}"
    # Legacy aliases so existing CSV consumers (stac_plot filters/heatmap)
    # keep working alongside the new snake_case names.
    row["variable"] = row.get("variable_id", "")
    row["temporal_start"] = (row.get("start_datetime") or "")[:10]
    row["temporal_end"] = (row.get("end_datetime") or "")[:10]
    return row


def print_table(rows):
    """Render catalogue rows with pandas formatting (compact SHOW_COLS profile) on stdout.

    Used in: stac_catalog.main (with --show).
    """
    import pandas as pd

    df = pd.DataFrame(rows)
    cols = [c for c in SHOW_COLS if c in df.columns]
    with pd.option_context("display.max_columns", None, "display.width", 250,
                           "display.max_colwidth", 40, "display.expand_frame_repr", False):
        print(df[cols].to_string(index=False))


def main():
    """CLI entry point: scan local files, query STAC, write catalogue CSV, optionally print the table.

    Used in: `python stac_catalog.py` / pixi task `stac_catalog`.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node", choices=esgf.NODES, default="east", help="ESGF STAC node (default: east)")
    ap.add_argument("--collection", help="Filter by collection (e.g. CMIP7); omit to search all")
    ap.add_argument("--model", help="Model / source_id, comma-separated (e.g. UKESM1-3-LL,EC-Earth3)")
    ap.add_argument("--rcm-model", dest="rcm_model", help="RCM / source_id, comma-separated (e.g. ICON-CLM-202407-1-1)")
    ap.add_argument("--driving-model", dest="driving_model", help="Driving model / driving_source_id (e.g. MPI-ESM1-2-HR)")
    ap.add_argument("--experiment", help="Experiment / scenario, comma-separated (e.g. historical,ssp585)")
    ap.add_argument("--variable", help="Variable_id, comma-separated (e.g. tas,hurs)")
    ap.add_argument("--frequency", help="Frequency, comma-separated (e.g. mon,day)")
    ap.add_argument("--grid", help="Grid label, comma-separated (e.g. gr,native)")
    ap.add_argument("--member", help="Variant/member label, comma-separated (e.g. r1i1p1f1,r2i1p1f1)")
    ap.add_argument("--domain", help="Realm, comma-separated (e.g. atmos,ocean)")
    ap.add_argument("--activity", help="Activity_id, comma-separated (e.g. DD,ScenarioMIP)")
    ap.add_argument("--out", default="./esgf_data", help="Local download dir to scan (default: ./esgf_data)")
    ap.add_argument("--csv", default="./catalog.csv", help="CSV output (default: ./catalog.csv)")
    ap.add_argument("--health", default="./health.csv", help="Health CSV (default: ./health.csv)")
    ap.add_argument("--show", action="store_true", help="Print catalogue table on screen")
    ap.add_argument("--missing-only", action="store_true", help="Only report datasets that are partial/missing")
    args = ap.parse_args()

    node = esgf.NODES[args.node]
    filters = build_filters(args)

    if not os.path.isdir(args.out):
        print(f"Local download dir not found: {args.out}", file=sys.stderr)
        sys.exit(1)

    sizes, base = scan_local(args.out)
    print(f"Scanned {len(sizes)} local file(s) under {args.out}")

    health_ts, statuses = esgf.load_health(args.health)

    try:
        items = esgf.iter_items(node, args.collection, filters)
        rows = []
        for item in items:
            r = fmt_row(item, args.out, sizes, base, statuses, args.missing_only)
            if r:
                rows.append(r)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("No datasets found.", file=sys.stderr)
        sys.exit(1)

    with open(args.csv, "w", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    n_complete = sum(1 for r in rows if r["status"] == STATUS_OK)
    n_partial = sum(1 for r in rows if r["status"] == STATUS_PARTIAL)
    n_missing = sum(1 for r in rows if r["status"] == STATUS_MISSING)

    print(f"\n{len(rows)} datasets: {n_complete} complete, {n_partial} partial, {n_missing} missing")
    print(f"Catalogue written to {args.csv}")

    if args.show:
        print()
        print_table(rows)


if __name__ == "__main__":
    main()