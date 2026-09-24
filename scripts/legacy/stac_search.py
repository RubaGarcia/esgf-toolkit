#!/usr/bin/env python3
"""Search the ESGF STAC API and print a metadata table (no files).

Every row is built by esgf.item_to_record(): all JSON properties are kept
(JSON wins), dot-separated title segments fill only missing slots, and replica
info (n_files, n_servers, servers) comes from the https data assets.
"""

import argparse
import sys

import requests

import esgf


def build_filters(args) -> dict:
    """Collect the CLI filter arguments into the {column: value} dict expected by esgf.build_body.

    Used in: main.
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


def main():
    """CLI entry point: query the STAC API and print a pandas metadata table (or just the match count with --matched).

    Used in: `python stac_search.py` / pixi task `stac_search`.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node", choices=esgf.NODES, default="east", help="ESGF STAC node (default: east)")
    ap.add_argument("--collection", help="Filter by collection (e.g. CORDEX-CMIP6); omit to search all")
    ap.add_argument("--limit", type=int, default=esgf.DEFAULT_LIMIT, help=f"Max rows (default: {esgf.DEFAULT_LIMIT})")
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
    ap.add_argument("--matched", action="store_true", help="Only print number of matching items")
    ap.add_argument("--columns", default="", help="Comma-separated columns to display (default: auto profile)")
    ap.add_argument("--full", action="store_true", help="Show every parsed column, not just the display profile")
    ap.add_argument("--csv", default="", help="Write the full pandas table to CSV")
    ap.add_argument("--health", default="./health.csv", help="Health CSV (default: ./health.csv)")
    args = ap.parse_args()

    node = esgf.NODES[args.node]
    filters = build_filters(args)
    health_ts, statuses = esgf.load_health(args.health)

    try:
        if args.matched:
            data = esgf.search(node, args.collection, 1, filters)
            print(data.get("numberMatched", "?"), "items matched")
            return

        data = esgf.search(node, args.collection, args.limit, filters)
        items = data.get("features", [])
        if not items:
            print("No items found.", file=sys.stderr)
            return

        df = esgf.items_to_dataframe(items, statuses)
        if args.csv:
            df.to_csv(args.csv, index=False)
            print(f"Full table ({len(df)} rows, {len(df.columns)} cols) written to {args.csv}")
        cols = None if args.full else esgf.display_columns(df, args.columns or None)
        esgf.print_dataframe(df, cols)
        footer = f"\n{data.get('numberMatched', '?')} items matched, showing {len(df)}, total {df['size_bytes'].sum() / 1e9:.2f} GB"
        if health_ts:
            footer += f"  |  health: {health_ts}"
        print(footer)

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
