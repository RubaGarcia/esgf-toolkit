#!/usr/bin/env python3
"""Download files from the ESGF STAC API (checksums verified by default)."""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import esgf

CHUNK = esgf.CHUNK
RETRIES = 3


def open_stream(url: str, out_part: str, size: int | None):
    """Open a stream, resuming a partial .part file via Range if possible.

    Returns (response, offset); (None, size) when the part file is already complete.
    Used in: download_file.
    """

    def get(offset):
        """Open the GET stream, adding a Range header when resuming from offset.

        Used in: open_stream.
        """
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        r = requests.get(url, stream=True, headers=headers, timeout=60)
        r.raise_for_status()
        return r

    offset = os.path.getsize(out_part) if os.path.exists(out_part) else 0
    if size and offset >= size:
        offset = size
    if offset and offset < size:
        r = get(offset)
        return r, offset
    if offset == size:
        return None, offset
    return get(0), 0


def order_replicas(replicas, statuses: dict):
    """Order replicas: healthy hosts first, unknown next, known-down last,
    so file servers reported down are only used as a last resort.

    Used in: download_file.
    """
    rank = []
    for r in replicas:
        s = statuses.get(esgf.server_name(r[0]), "?")
        rank.append((0 if s == "ok" else 1 if s == "?" else 2, r))
    return [r for _, r in sorted(rank)]


def download_file(target, out_dir: str, flat: bool, verify: bool, statuses: dict) -> tuple:
    """Download one file (resumable .part, replica failover, size + checksum checks).

    Returns (relpath, size, status) where status is 'ok', 'failed' or
    'unavailable (server down)'.
    Used in: main (submitted to the ThreadPoolExecutor).
    """
    lp, replicas = target
    rel = os.path.basename(lp) if flat else lp
    out_path = os.path.join(out_dir, rel)
    out_part = out_path + ".part"
    replicas = order_replicas(replicas, statuses)

    for attempt in range(RETRIES):
        for href, protocol, checksum, size in replicas:
            try:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                r, offset = open_stream(href, out_part, size)

                if r is None:
                    if os.path.exists(out_part) and (not size or os.path.getsize(out_part) >= size):
                        os.replace(out_part, out_path)
                    else:
                        continue

                if r is not None:
                    with open(out_part, "ab" if offset else "wb") as f:
                        for chunk in r.iter_content(CHUNK):
                            if chunk:
                                f.write(chunk)
                    r.close()

                if size and os.path.getsize(out_part) != size:
                    raise OSError(f"size mismatch: got {os.path.getsize(out_part)}, expected {size}")
                if verify and checksum and not esgf.verify_file(out_part, checksum):
                    raise OSError("checksum mismatch")
                os.replace(out_part, out_path)
                return rel, os.path.getsize(out_path), "ok"
            except Exception as e:
                print(f"  failed {rel} ({esgf.server_name(href)}): {e}; trying next replica/href", flush=True)

    down_hosts = {esgf.server_name(r[0]) for r in replicas if statuses.get(esgf.server_name(r[0])) == "down"}
    if down_hosts and all(statuses.get(esgf.server_name(r[0])) == "down" for r in replicas):
        return rel, 0, "unavailable (server down)"

    return rel, 0, "failed"


def main():
    """CLI entry point: resolve matching STAC items to files, then download them in parallel.

    Used in: `python stac_download.py` / pixi task `stac_download`.
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
    ap.add_argument("--out", default="./esgf_data", help="Destination dir (default: ./esgf_data)")
    ap.add_argument("--columns", default="", help="Comma-separated manifest columns to display (default: auto)")
    ap.add_argument("--manifest", default="", help="Write the per-file manifest (one row per file, item facets repeated) to CSV")
    ap.add_argument("--flat", action="store_true", help="Save files flat by filename (default: mirror DRS path)")
    ap.add_argument("--health", default="./health.csv", help="Health CSV (default: ./health.csv)")
    ap.add_argument("--jobs", type=int, default=4, help="Parallel downloads (default: 4)")
    ap.add_argument("--max-files", type=int, default=0, help="Stop after N files (default: no limit)")
    ap.add_argument("--no-verify", action="store_true", help="Disable checksum verification")
    ap.add_argument("--dry-run", action="store_true", help="List files without downloading")
    args = ap.parse_args()

    node = esgf.NODES[args.node]
    filters = {
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

    try:
        health_ts, statuses = esgf.load_health(args.health)
        if args.health and not statuses:
            print(f"Warning: no health data in {args.health}; hosts treated as unknown", file=sys.stderr)

        items = list(esgf.iter_items(node, args.collection, filters, args.max_files))

        # Per-file manifest: one row per downloadable file, parent item facets
        # repeated on every row, plus file host/size/checksum. This is the same
        # pandas table as search, exploded to file granularity.
        manifest = esgf.files_to_dataframe(items, statuses)
        if not manifest.empty:
            if args.manifest:
                manifest.to_csv(args.manifest, index=False)
                print(f"Manifest ({len(manifest)} files) written to {args.manifest}")
            show_cols = [c for c in
                         ["rcm_model", "driving_model", "experiment", "variable_id",
                          "frequency", "domain_id", "member", "file_name", "host",
                          "file_size", "avail"]
                         if c in manifest.columns]
            if args.columns:
                show_cols = [c.strip() for c in args.columns.split(",")
                             if c.strip() in manifest.columns] or show_cols
            import pandas as pd
            with pd.option_context("display.max_columns", None, "display.width", 250,
                                   "display.max_colwidth", 50, "display.expand_frame_repr", False):
                head = manifest[show_cols].head(20)
                print(head.to_string(index=False))
                if len(manifest) > 20:
                    print(f"... ({len(manifest) - 20} more files)")
            n_hosts = manifest["host"].nunique()
            print(f"Hosts: {n_hosts} distinct server(s): "
                  f"{', '.join(sorted(manifest['host'].unique()))}")
        targets = esgf.iter_files(iter(items))
        if not targets:
            print("No downloadable files found.", file=sys.stderr)
            return

        total = sum(t[1][0][3] or 0 for t in targets)
        n_healthy = 0
        for lp, replicas in targets:
            if any(statuses.get(esgf.server_name(h[0])) != "down" for h in replicas):
                n_healthy += 1
        print(f"Found {len(targets)} file(s), {total / 1e9:.2f} GB total ({n_healthy} on healthy servers)")

        if args.dry_run:
            return

        if args.max_files:
            targets = targets[: args.max_files]

        os.makedirs(args.out, exist_ok=True)
        fail = 0
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(download_file, t, args.out, args.flat, not args.no_verify, statuses) for t in targets]
            for i, f in enumerate(as_completed(futures), 1):
                rel, size, status = f.result()
                if status == "ok":
                    print(f"[{i}/{len(targets)}] done  {rel} ({size / 1e6:.1f} MB)")
                else:
                    print(f"[{i}/{len(targets)}] FAIL  {rel}  ({status})")
                    fail += 1

        print(f"\n{len(targets) - fail} succeeded, {fail} failed")
        sys.exit(1 if fail else 0)

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()