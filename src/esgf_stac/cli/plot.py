#!/usr/bin/env python3
"""Heatmap image of ESGF download completeness (model x variable)."""

import argparse
import csv
import os
import sys
from collections import defaultdict

import requests

from esgf_stac import NODES, iter_items, load_health, parse_filter_values
from esgf_stac.cli.catalog import fmt_row
from esgf_stac.cli.common import add_health_arg, add_node_arg
from esgf_stac.local import scan_local

DEFAULT_CSV = "./catalog.csv"


def read_csv_rows(csv_path):
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def write_csv_rows(csv_path, rows):
    if not rows:
        return
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def filter_rows(rows, collection: str | None, filters: dict) -> list:
    active = [(col, set(parse_filter_values(raw))) for col, raw in filters.items()
              if parse_filter_values(raw)]
    out = []
    for r in rows:
        if collection and r.get("collection") != collection:
            continue
        ok = True
        for col, vals in active:
            cell = str(r.get(col) or "")
            parts = {p.strip() for p in cell.split(",") if p.strip()}
            if cell not in vals and not (parts & vals):
                ok = False
                break
        if ok:
            out.append(r)
    return out


def compute_rows(args):
    node = NODES[args.node]
    filters = {"model": args.model, "experiment": args.experiment, "variable": args.variable,
               "frequency": args.frequency, "grid": args.grid, "member": args.member,
               "domain": args.domain, "activity": getattr(args, "activity", None)}
    sizes, base = scan_local(args.out)
    _, statuses = load_health(args.health)
    return [r for item in iter_items(node, args.collection, filters)
            if (r := fmt_row(item, args.out, sizes, base, statuses, show_missing_only=False))]


def aggregate(rows):
    import numpy as np

    collections = {r.get("collection") or "?" for r in rows}
    multi = len(collections) > 1
    buckets = defaultdict(lambda: {"n": 0, "complete": 0, "partial": 0, "missing": 0})
    for r in rows:
        coll, model, var = r.get("collection") or "?", r.get("model") or "?", r.get("variable") or "?"
        label = f"{coll} · {model}" if multi else model
        b = buckets[(label, var)]
        b["n"] += 1
        b[r.get("status") or "missing" if (r.get("status") or "missing") in b else "missing"] += 1
    labels = sorted({k[0] for k in buckets})
    variables = sorted({k[1] for k in buckets})
    li, vi = {x: i for i, x in enumerate(labels)}, {x: i for i, x in enumerate(variables)}
    score = np.full((len(labels), len(variables)), np.nan)
    annotate = np.zeros((len(labels), len(variables)), dtype=object)
    for (lab, var), b in buckets.items():
        i, j = li[lab], vi[var]
        score[i, j] = (b["complete"] + 0.5 * b["partial"]) / b["n"]
        annotate[i, j] = f"{b['complete']}/{b['n']}"
    return labels, variables, score, annotate


def plot(rows, title_extra, out_path):
    import matplotlib.pyplot as plt
    import numpy as np

    if not rows:
        print("No dataset rows to plot.", file=sys.stderr)
        sys.exit(1)
    labels, variables, score, annotate = aggregate(rows)
    n = len(rows)
    nc = sum(1 for r in rows if r.get("status") == "complete")
    np_ = sum(1 for r in rows if r.get("status") == "partial")
    nm = sum(1 for r in rows if r.get("status") == "missing")
    n_rows, n_cols = score.shape
    fig_w = max(6.0, min(24.0, n_cols * 0.55 + 4.0))
    fig_h = max(4.0, min(32.0, n_rows * 0.35 + 3.0))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), constrained_layout=True)
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad(color="#eceff1")
    im = ax.imshow(score, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(n_cols), labels=variables, rotation=90, fontsize=8)
    ax.set_yticks(range(n_rows), labels=labels, fontsize=8)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    if n_rows * n_cols <= 400:
        for i in range(n_rows):
            for j in range(n_cols):
                if not np.isnan(score[i, j]):
                    color = "#212121" if 0.35 <= score[i, j] <= 0.65 else "white"
                    ax.text(j, i, annotate[i, j], ha="center", va="center", fontsize=6, color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("completeness  (1=complete, 0.5=partial)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    fig.suptitle(f"ESGF Dataset Download Status\n{title_extra}"
                 f"{n} datasets   —   {nc} complete    {np_} partial    {nm} missing",
                 fontsize=12, x=0.01, ha="left")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path} ({n} datasets: {nc} complete, {np_} partial, {nm} missing)")


def main():
    import matplotlib
    matplotlib.use("Agg")
    ap = argparse.ArgumentParser(description=__doc__)
    add_node_arg(ap)
    ap.add_argument("--collection", help="Filter by collection (e.g. CMIP7)")
    ap.add_argument("--model", help="Model / source_id, comma-separated")
    ap.add_argument("--experiment", help="Experiment / scenario, comma-separated")
    ap.add_argument("--variable", help="Variable_id, comma-separated")
    ap.add_argument("--frequency", help="Frequency, comma-separated")
    ap.add_argument("--grid", help="Grid label, comma-separated")
    ap.add_argument("--member", help="Variant/member label, comma-separated")
    ap.add_argument("--domain", help="Realm, comma-separated")
    ap.add_argument("--activity", help="Activity_id, comma-separated")
    ap.add_argument("--out", default="./esgf_data", help="Local download dir to scan")
    ap.add_argument("--csv", default="", help=f"Catalogue CSV (default: {DEFAULT_CSV} when present)")
    ap.add_argument("--refresh", action="store_true", help="Re-query STAC and rewrite the CSV")
    add_health_arg(ap)
    ap.add_argument("--image", default="./catalog.png", help="Output image (default: ./catalog.png)")
    args = ap.parse_args()

    csv_path = args.csv or DEFAULT_CSV
    from_stac = args.refresh or not os.path.exists(csv_path)
    if from_stac:
        rows = compute_rows(args)
        if csv_path:
            write_csv_rows(csv_path, rows)
        title_extra = (f"collection={args.collection or '*'}  model={args.model or '*'}  "
                       f"variable={args.variable or '*'}  experiment={args.experiment or '*'}\n")
    else:
        filters = {"model": args.model, "experiment": args.experiment, "variable": args.variable,
                   "frequency": args.frequency, "grid": args.grid, "member": args.member,
                   "domain": args.domain, "activity": args.activity}
        rows = filter_rows(read_csv_rows(csv_path), args.collection, filters)
        title_extra = f"from {csv_path}\n"
    if not rows:
        print("No dataset rows to plot.", file=sys.stderr)
        sys.exit(1)
    try:
        plot(rows, title_extra, args.image)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
