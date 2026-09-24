"""Health dashboard: probe STAC nodes + file servers, read/write health.csv."""

import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

STAC_SEARCH_NODES = {
    "discovery.east.esgf.io": "https://discovery.east.esgf.io/search",
    "discovery.west.esgf.io": "https://discovery.west.esgf.io/search",
}

FILE_SERVERS = {
    "esgf-ui.ceda.ac.uk": "https://esgf-ui.ceda.ac.uk/",
    "esgf-data.dkrz.de": "https://esgf-data.dkrz.de/",
    "esgf.nci.org.au": "https://esgf.nci.org.au/",
    "esgf-node.ornl.gov": "https://esgf-node.ornl.gov/",
    "metagrid.esgf-west.org": "https://metagrid.esgf-west.org/",
    "esgf-node.ipsl.upmc.fr": "https://esgf-node.ipsl.upmc.fr/",
    "esg-dn1.nsc.liu.se": "https://esg-dn1.nsc.liu.se/",
    "esgf.ipsl.fr": "https://esgf.ipsl.fr/",
    "esgf.dkrz.de": "https://esgf.dkrz.de/",
    "esgf.ceda.ac.uk": "https://esgf.ceda.ac.uk/",
}

ADDITIONAL_NODES = {
    "esgf.ouranos.ca": "https://esgf.ouranos.ca/",
    "crd-esgf-drc.ec.gc.ca": "https://crd-esgf-drc.ec.gc.ca/",
    "esgdata.gfdl.noaa.gov": "https://esgdata.gfdl.noaa.gov/",
}

TIMEOUT = 10
CSV_COLUMNS = ["timestamp", "kind", "name", "status", "detail", "url"]


def timestamp_now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def load_health(csv_path: str = "./health.csv"):
    """Read health CSV -> (timestamp, {hostname: status})."""
    statuses = {}
    ts = ""
    if not os.path.exists(csv_path):
        return ts, statuses
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            name = row.get("name") or ""
            status = row.get("status") or ""
            if name and status:
                statuses[name] = status
                if not ts and row.get("timestamp"):
                    ts = row["timestamp"]
    return ts, statuses


def probe_stac(label, url):
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
    rows = []
    ts = timestamp_now()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(probe_stac, label, url) for label, url in STAC_SEARCH_NODES.items()]
        futures += [pool.submit(probe_file, label, url) for label, url in FILE_SERVERS.items()]
        if include_additional:
            futures += [pool.submit(probe_file, label, url) for label, url in ADDITIONAL_NODES.items()]
        for f in as_completed(futures):
            kind, name, status, detail, url = f.result()
            rows.append([ts, kind, name, status, detail, url])
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        w.writerows(rows)


def print_table(rows):
    order_groups = {"stac": "STAC Search Nodes (POST /search)", "fs": "File Servers (HEAD /)"}
    for kind in order_groups:
        subset = [r for r in rows if r[1] == kind]
        if not subset:
            continue
        print(order_groups[kind])
        print("-" * 52)
        for ts, k, name, status, detail, url in sorted(subset):
            icon = "ok  " if status == "ok" else "DOWN"
            print(f"  [{icon}] {name:30s} {detail}")
        print()
    n_down = sum(1 for r in rows if r[3] == "down")
    print(f"  {n_down} host(s) unreachable" if n_down else "  All hosts reachable")
