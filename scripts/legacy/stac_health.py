#!/usr/bin/env python3
"""Dashboard: check ESGF STAC nodes + file servers, writing results to a CSV.

Writes ./health.csv (one row per host) so stac_search/stac_download can show
availability. Use --interval MINUTES to re-run periodically (daemon mode).
"""

import argparse
import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Current ESGF-NG STAC API endpoints (as of 2025)
STAC_SEARCH_NODES = {
    "discovery.east.esgf.io": "https://discovery.east.esgf.io/search",
    "discovery.west.esgf.io": "https://discovery.west.esgf.io/search",
}

# Current ESGF file servers from https://esgf.github.io/nodes.html (2025)
# LLNL nodes (aims3, esgf-data1, esgf-data2) were shut down July 2025
FILE_SERVERS = {
    "esgf-ui.ceda.ac.uk":      "https://esgf-ui.ceda.ac.uk/",        # CEDA (Europe)
    "esgf-data.dkrz.de":       "https://esgf-data.dkrz.de/",         # DKRZ (Europe)
    "esgf.nci.org.au":         "https://esgf.nci.org.au/",           # NCI (Australia)
    "esgf-node.ornl.gov":      "https://esgf-node.ornl.gov/",        # ORNL (US Primary)
    "metagrid.esgf-west.org":  "https://metagrid.esgf-west.org/",    # NERSC (US Backup)
    "esgf-node.ipsl.upmc.fr":  "https://esgf-node.ipsl.upmc.fr/",    # IPSL (Europe)
    "esg-dn1.nsc.liu.se":      "https://esg-dn1.nsc.liu.se/",        # LIU (Europe)
    "esgf.ipsl.fr":            "https://esgf.ipsl.fr/",              # IPSL (old URL, still in catalog)
    "esgf.dkrz.de":            "https://esgf.dkrz.de/",              # DKRZ (old URL, still in catalog)
    "esgf.ceda.ac.uk":         "https://esgf.ceda.ac.uk/",           # CEDA (old URL, still in catalog)
}

# Additional known nodes (may have limited access or be project-specific)
ADDITIONAL_NODES = {
    "esgf.ouranos.ca":         "https://esgf.ouranos.ca/",           # Ouranos (CORDEX)
    "crd-esgf-drc.ec.gc.ca":   "https://crd-esgf-drc.ec.gc.ca/",     # CCCma (CORDEX)
    "esgdata.gfdl.noaa.gov":   "https://esgdata.gfdl.noaa.gov/",     # GFDL
}

TIMEOUT = 10

CSV_COLUMNS = ["timestamp", "kind", "name", "status", "detail", "url"]


def timestamp_now():
    """Return the current time as 'YYYY-MM-DDTHH:MM:SS'.

    Used in: run_once, main.
    """
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def probe_stac(label, url):
    """POST a tiny search to a STAC node and report ('stac', label, ok/down, detail, url).

    Used in: run_once.
    """
    t0 = time.monotonic()
    try:
        r = requests.post(url, json={"limit": 1}, timeout=TIMEOUT)
        ms = (time.monotonic() - t0) * 1000
        if r.status_code == 200:
            n = r.json().get("numberMatched", "?")
            return "stac", label, "ok", f"{ms:.0f}ms | {n} items", url
        return "stac", label, "down", f"{ms:.0f}ms | HTTP {r.status_code}", url
    except requests.exceptions.RequestException as e:
        ms = (time.monotonic() - t0) * 1000
        return "stac", label, "down", f"{ms:.0f}ms | {type(e).__name__}", url


def probe_file(label, url):
    """HEAD a file server root and report ('fs', label, ok/down, detail, url).

    503/transport errors count as down; redirects and auth responses count as alive.
    Used in: run_once.
    """
    t0 = time.monotonic()
    try:
        r = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        ms = (time.monotonic() - t0) * 1000
        if r.status_code == 503:
            return "fs", label, "down", f"{ms:.0f}ms | HTTP 503 (unavailable)", url
        if r.status_code == 200:
            return "fs", label, "ok", f"{ms:.0f}ms | HTTP 200", url
        if r.status_code in (301, 302, 303, 307):
            return "fs", label, "ok", f"{ms:.0f}ms | HTTP {r.status_code} (redirect)", url
        if r.status_code in (401, 403):
            return "fs", label, "ok", f"{ms:.0f}ms | HTTP {r.status_code} (auth required)", url
        return "fs", label, "ok", f"{ms:.0f}ms | HTTP {r.status_code} (alive, no root)", url
    except requests.exceptions.RequestException as e:
        ms = (time.monotonic() - t0) * 1000
        return "fs", label, "down", f"{ms:.0f}ms | {type(e).__name__}", url


def run_once(include_additional=False):
    """Probe all STAC nodes and file servers in parallel; return CSV rows.

    Used in: main.
    """
    rows = []
    ts = timestamp_now()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for label, url in STAC_SEARCH_NODES.items():
            futures.append(pool.submit(probe_stac, label, url))
        for label, url in FILE_SERVERS.items():
            futures.append(pool.submit(probe_file, label, url))
        if include_additional:
            for label, url in ADDITIONAL_NODES.items():
                futures.append(pool.submit(probe_file, label, url))
        for f in as_completed(futures):
            kind, name, status, detail, url = f.result()
            rows.append([ts, kind, name, status, detail, url])
    return rows


def write_csv(path, rows):
    """Overwrite the health CSV with the given probe rows (with CSV_COLUMNS header).

    Used in: main.
    """
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        w.writerows(rows)


def print_table(rows):
    """Print probe results grouped by kind (STAC nodes, then file servers) with an unreachable count.

    Used in: main.
    """
    order = {"stac": 0, "fs": 1}
    groups = {"stac": "STAC Search Nodes (POST /search)", "fs": "File Servers (HEAD /)"}
    for kind in groups:
        subset = [r for r in rows if r[1] == kind]
        if not subset:
            continue
        print(groups[kind])
        print("-" * 52)
        for ts, k, name, status, detail, url in sorted(subset):
            icon = "ok  " if status == "ok" else "DOWN"
            print(f"  [{icon}] {name:30s} {detail}")
        print()
    n_down = sum(1 for r in rows if r[3] == "down")
    if n_down:
        print(f"  {n_down} host(s) unreachable")
    else:
        print("  All hosts reachable")


def main():
    """CLI entry point: probe once (or every --interval minutes) and write/print the health report.

    Used in: `python stac_health.py` / pixi tasks `stac_health`, `stac_health_daemon`.
    """
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