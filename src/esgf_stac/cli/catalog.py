#!/usr/bin/env python3
"""Catalogue: compare local downloads vs what the ESGF servers offer."""

import argparse
import csv
import os
import sys

import requests

from esgf_stac import NODES, item_to_record, iter_items, load_health
from esgf_stac.cli.common import add_filter_args, add_health_arg, add_node_arg, build_filters
from esgf_stac.local import is_present, scan_local

STATUS_OK = "complete"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing"

SHOW_COLS = ["project", "model", "experiment", "variable_id", "frequency",
             "grid", "domain", "member", "status", "files", "size_gb",
             "n_servers", "available"]


def fmt_row(item, out_dir: str, sizes: dict, base: dict, statuses: dict, show_missing_only: bool):
    """One STAC item -> catalogue row with local/remote counts (None to skip)."""
    row = item_to_record(item, statuses)
    assets = [a for a in item.get("assets", {}).values()
              if a.get("protocol") == "https" and "data" in a.get("roles", [])]
    if not assets:
        return None
    size_remote = sum(a.get("file:size") or 0 for a in assets)
    size_local, n_local = 0, 0
    for a in assets:
        lp, size = a.get("file:local_path"), a.get("file:size")
        if lp and is_present(lp, size, out_dir, sizes, base):
            n_local += 1
            size_local += size or 0
    n_remote = len(assets)
    status = STATUS_MISSING if n_local == 0 else STATUS_OK if n_local >= n_remote else STATUS_PARTIAL
    if show_missing_only and status == STATUS_OK:
        return None
    row["files_remote"] = n_remote
    row["files_local"] = n_local
    row["size_remote_gb"] = round((size_remote or 0) / 1e9, 3)
    row["size_local_gb"] = round((size_local or 0) / 1e9, 3)
    row["status"] = status
    row["available"] = row.pop("avail")
    row["files"] = f"{n_local}/{n_remote}"
    row["size_gb"] = f"{row['size_local_gb']:.2f}/{row['size_remote_gb']:.2f}"
    row["variable"] = row.get("variable_id", "")
    row["temporal_start"] = (row.get("start_datetime") or "")[:10]
    row["temporal_end"] = (row.get("end_datetime") or "")[:10]
    return row


def print_table(rows):
    import pandas as pd

    df = pd.DataFrame(rows)
    cols = [c for c in SHOW_COLS if c in df.columns]
    with pd.option_context("display.max_columns", None, "display.width", 250,
                           "display.max_colwidth", 40, "display.expand_frame_repr", False):
        print(df[cols].to_string(index=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    add_node_arg(ap)
    add_filter_args(ap)
    ap.add_argument("--out", default="./esgf_data", help="Local download dir to scan (default: ./esgf_data)")
    ap.add_argument("--csv", default="./catalog.csv", help="CSV output (default: ./catalog.csv)")
    add_health_arg(ap)
    ap.add_argument("--show", action="store_true", help="Print catalogue table on screen")
    ap.add_argument("--missing-only", action="store_true", help="Only report partial/missing datasets")
    args = ap.parse_args()

    node = NODES[args.node]
    filters = build_filters(args)
    if not os.path.isdir(args.out):
        print(f"Local download dir not found: {args.out}", file=sys.stderr)
        sys.exit(1)
    sizes, base = scan_local(args.out)
    print(f"Scanned {len(sizes)} local file(s) under {args.out}")
    health_ts, statuses = load_health(args.health)
    try:
        rows = [r for item in iter_items(node, args.collection, filters)
                if (r := fmt_row(item, args.out, sizes, base, statuses, args.missing_only))]
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if not rows:
        print("No datasets found.", file=sys.stderr)
        sys.exit(1)
    with open(args.csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    n = lambda s: sum(1 for r in rows if r["status"] == s)
    print(f"\n{len(rows)} datasets: {n(STATUS_OK)} complete, {n(STATUS_PARTIAL)} partial, {n(STATUS_MISSING)} missing")
    print(f"Catalogue written to {args.csv}")
    if args.show:
        print()
        print_table(rows)


if __name__ == "__main__":
    main()
