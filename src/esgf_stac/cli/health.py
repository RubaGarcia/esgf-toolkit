#!/usr/bin/env python3
"""Dashboard: check ESGF STAC nodes + file servers, writing results to a CSV."""

import argparse
import time

from esgf_stac.health import print_table, run_once, write_csv
from esgf_stac.health import timestamp_now


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default="./health.csv", help="CSV output (default: ./health.csv)")
    ap.add_argument("--interval", type=float, default=0, help="Minutes between runs (0 = one shot)")
    ap.add_argument("--include-additional", action="store_true", help="Include additional/project-specific nodes")
    args = ap.parse_args()
    while True:
        rows = run_once(include_additional=args.include_additional)
        write_csv(args.csv, rows)
        print(f"[{timestamp_now()}] wrote {args.csv} ({len(rows)} hosts)\n")
        print_table(rows)
        print()
        if args.interval <= 0:
            break
        time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
