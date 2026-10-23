#!/usr/bin/env python3
"""Search the ESGF STAC API and print a metadata table (no files)."""

import argparse
import sys

import requests

from esgf_stac import (
    DEFAULT_LIMIT,
    NODES,
    collapse_variables,
    combine_time,
    display_columns,
    items_to_dataframe,
    load_health,
    print_dataframe,
    search,
)
from esgf_stac.cli.common import add_filter_args, add_health_arg, add_node_arg, build_filters


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    add_node_arg(ap)
    add_filter_args(ap)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Max rows (default: {DEFAULT_LIMIT})")
    ap.add_argument("--matched", action="store_true", help="Only print number of matching items")
    ap.add_argument("--columns", default="", help="Comma-separated columns to display (default: auto profile)")
    ap.add_argument("--full", action="store_true", help="Show every parsed column, not just the display profile")
    ap.add_argument("--csv", default="", help="Write the full pandas table to CSV")
    add_health_arg(ap)
    args = ap.parse_args()

    node = NODES[args.node]
    filters = build_filters(args)
    health_ts, statuses = load_health(args.health)

    try:
        if args.matched:
            data = search(node, args.collection, 1, filters)
            print(data.get("numberMatched", "?"), "items matched")
            return
        data = search(node, args.collection, args.limit, filters)
        items = data.get("features", [])
        if not items:
            print("No items found.", file=sys.stderr)
            return
        df = items_to_dataframe(items, statuses)
        if args.csv:
            df.to_csv(args.csv, index=False)
            print(f"Full table ({len(df)} rows, {len(df.columns)} cols) written to {args.csv}")
        view = combine_time(collapse_variables(df))
        cols = None if args.full else display_columns(view, args.columns or None)
        print_dataframe(view, cols)
        footer = (f"\n{data.get('numberMatched', '?')} items matched, showing {len(view)}, "
                  f"total {df['size_bytes'].sum() / 1e9:.2f} GB")
        if health_ts:
            footer += f"  |  health: {health_ts}"
        print(footer)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
