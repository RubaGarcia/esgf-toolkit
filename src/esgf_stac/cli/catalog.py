#!/usr/bin/env python3
"""Catalogue local downloads as per-collection CSVs; --compare adds remote completeness."""

import argparse
import csv
import os
import sys

import requests

from esgf_stac import (
    NODES,
    combine_time,
    display_columns,
    iter_items,
    item_to_record,
    load_health,
    print_dataframe,
)
from esgf_stac.cli.common import (
    add_filter_args,
    add_health_arg,
    add_node_arg,
    add_out_arg,
    build_filters,
    union_fieldnames,
)
from esgf_stac.local import LOCAL_COLUMNS, catalog_rows, is_present, scan_local

STATUS_OK = "complete"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing"

SHOW_LOCAL_COLS = ["collection", "model", "rcm_model", "driving_model", "institution",
                   "experiment", "member", "variable", "frequency", "n_files", "size_gb"]


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


def compare_view(rows: list):
    """Comparison rows -> display DataFrame: restores `avail`, adds `local/remote` + `time`."""
    import pandas as pd

    df = pd.DataFrame(rows)
    if "available" in df.columns:
        df["avail"] = df["available"]
    if "files" in df.columns:
        df["local/remote"] = df["files"]
    return combine_time(df)


def compare_columns(view) -> list:
    """Search display profile with `variable_id` in place of `n_variables`, plus local/remote + status."""
    cols = display_columns(view)
    if "variable_id" in view.columns:
        if "n_variables" in cols:
            cols[cols.index("n_variables")] = "variable_id"
        elif "variable_id" not in cols:
            at = cols.index("experiment") + 1 if "experiment" in cols else len(cols)
            cols.insert(at, "variable_id")
    for c in ("local/remote", "status"):
        if c in view.columns and c not in cols:
            cols.append(c)
    return cols


def summarize(rows: list) -> str:
    n = lambda s: sum(1 for r in rows if r["status"] == s)
    return (f"Summary: {len(rows)} datasets — {n(STATUS_OK)} complete, "
            f"{n(STATUS_PARTIAL)} partial, {n(STATUS_MISSING)} missing")


def write_collection_csvs(rows_by_coll: dict, csv_dir: str) -> list:
    """Write one CSV per collection into csv_dir; returns the paths written."""
    os.makedirs(csv_dir, exist_ok=True)
    written = []
    for coll in sorted(rows_by_coll):
        rows = rows_by_coll[coll]
        if not rows:
            continue
        path = os.path.join(csv_dir, f"{coll}.csv")
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LOCAL_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        written.append(path)
    return written


def print_table(rows, cols=SHOW_LOCAL_COLS):
    import pandas as pd

    df = pd.DataFrame(rows)
    cols = [c for c in cols if c in df.columns]
    with pd.option_context("display.max_columns", None, "display.width", 250,
                           "display.max_colwidth", 40, "display.expand_frame_repr", False):
        print(df[cols].to_string(index=False))


def run_compare(args, sizes: dict, base: dict, filters: dict):
    """Query STAC, compare against the local tree, print the report, write the comparison CSV."""
    node = NODES[args.node]
    _, statuses = load_health(args.health)
    try:
        all_rows = [r for item in iter_items(node, args.collection, filters)
                    if (r := fmt_row(item, args.out, sizes, base, statuses, show_missing_only=False))]
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if not all_rows:
        print("No datasets found.", file=sys.stderr)
        sys.exit(1)
    rows = [r for r in all_rows if r["status"] != STATUS_OK] if args.missing_only else all_rows
    if rows:
        with open(args.csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=union_fieldnames(rows))
            writer.writeheader()
            writer.writerows(rows)
        view = compare_view(rows)
        print()
        print_dataframe(view, compare_columns(view))
        print(f"\n{summarize(all_rows)}")
        print(f"Comparison catalogue written to {args.csv}")
    else:
        print(f"\n{summarize(all_rows)}")
        print("Nothing to list (all datasets complete; comparison CSV not updated).")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    add_node_arg(ap)
    add_filter_args(ap)
    add_out_arg(ap, "Local download dir to scan")
    ap.add_argument("--csv-dir", default="./catalog", help="Per-collection local CSV dir (default: ./catalog)")
    ap.add_argument("--csv", default="./catalog.csv", help="Comparison CSV for --compare (default: ./catalog.csv)")
    add_health_arg(ap)
    ap.add_argument("--compare", action="store_true",
                    help="Compare local files with the STAC servers: print a completeness "
                         "report (complete/partial/missing) and write the comparison CSV")
    ap.add_argument("--show", action="store_true", help="Also print the local leaf-dir table on screen")
    ap.add_argument("--missing-only", action="store_true",
                    help="With --compare: only list partial/missing datasets (summary still counts all)")
    args = ap.parse_args()

    filters = build_filters(args)
    if not os.path.isdir(args.out):
        print(f"Local download dir not found: {args.out}", file=sys.stderr)
        sys.exit(1)
    sizes, base = scan_local(args.out)
    print(f"Scanned {len(sizes)} local file(s) under {args.out}")

    local = catalog_rows(sizes, {**filters, "collection": args.collection})
    if local:
        write_collection_csvs(local, args.csv_dir)
        n_leaves = n_files = size_bytes = 0
        for coll in sorted(local):
            rows = local[coll]
            files = sum(r["n_files"] for r in rows)
            gb = sum(r["size_bytes"] for r in rows) / 1e9
            n_leaves += len(rows)
            n_files += files
            size_bytes += sum(r["size_bytes"] for r in rows)
            print(f"  {coll}: {len(rows)} leaf dir(s), {files} file(s), {gb:.2f} GB "
                  f"-> {os.path.join(args.csv_dir, coll + '.csv')}")
        print(f"Local catalogue: {n_leaves} leaf dir(s), {n_files} file(s), "
              f"{size_bytes / 1e9:.2f} GB in {len(local)} CSV(s) under {args.csv_dir}")
        if args.show:
            print()
            print_table([r for coll in sorted(local) for r in local[coll]], SHOW_LOCAL_COLS)
    elif not args.compare:
        print("No local files found.", file=sys.stderr)
        sys.exit(1)
    else:
        print("No local files found; skipping local catalogue.", file=sys.stderr)

    if args.compare:
        run_compare(args, sizes, base, filters)


if __name__ == "__main__":
    main()
