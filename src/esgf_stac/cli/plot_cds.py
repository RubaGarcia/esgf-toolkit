#!/usr/bin/env python3
"""Heatmap of CDS catalogue data (dataset x variable, split by temporal_resolution)."""

import argparse
import csv
import os
import sys
from collections import defaultdict


DEFAULT_CSV = "./all_catalogues.csv"


def read_csv_rows(csv_path):
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def row_status(row):
    start = parse_bool(row.get("start_file_exists", False))
    final = parse_bool(row.get("final_file_exists", False))
    if start and final:
        return "downloaded"
    if start or final:
        return "partial"
    return "not_downloaded"


def filter_rows(rows, dataset_type, product_type, temporal_resolution, interpolation):
    out = []
    for r in rows:
        if dataset_type and r.get("dataset_type", "") != dataset_type:
            continue
        if product_type and r.get("product_type", "") != product_type:
            continue
        if temporal_resolution and r.get("temporal_resolution", "") != temporal_resolution:
            continue
        if interpolation and r.get("interpolation", "") != interpolation:
            continue
        out.append(r)
    return out


def aggregate(rows):
    """Per-temporal-resolution dataset x variable grids.

    Returns {temporal_resolution: (labels, variables, score, annotate)}.
    """
    import numpy as np

    resolutions = sorted({r.get("temporal_resolution") or "?" for r in rows})
    result = {}
    for res in resolutions:
        res_rows = [r for r in rows if (r.get("temporal_resolution") or "?") == res]
        buckets = defaultdict(lambda: {"n": 0, "downloaded": 0, "partial": 0, "not_downloaded": 0})
        for r in res_rows:
            dataset = r.get("dataset") or "?"
            var = r.get("variable") or "?"
            b = buckets[(dataset, var)]
            b["n"] += 1
            status = row_status(r)
            b[status] += 1
        labels = sorted({k[0] for k in buckets})
        variables = sorted({k[1] for k in buckets})
        li = {x: i for i, x in enumerate(labels)}
        vi = {x: i for i, x in enumerate(variables)}
        score = np.full((len(labels), len(variables)), np.nan)
        annotate = np.zeros((len(labels), len(variables)), dtype=object)
        for (ds, var), b in buckets.items():
            i, j = li[ds], vi[var]
            score[i, j] = (b["downloaded"] + 0.5 * b["partial"]) / b["n"]
            annotate[i, j] = f"{b['downloaded']}/{b['n']}"
        result[res] = (labels, variables, score, annotate)
    return result


def plot(rows, title_extra, out_path):
    import matplotlib.pyplot as plt
    import numpy as np

    if not rows:
        print("No rows to plot.", file=sys.stderr)
        sys.exit(1)
    freq_data = aggregate(rows)
    n = len(rows)
    n_res = len(freq_data)
    n_cols = min(2, n_res)
    n_rows = (n_res + n_cols - 1) // n_cols
    max_cols = max(len(v[1]) for v in freq_data.values())
    max_rows = max(len(v[0]) for v in freq_data.values())
    fig_w = max(8.0, min(28.0, max_cols * 0.55 * n_cols + 4.0))
    fig_h = max(4.0, min(48.0, max_rows * 0.35 * n_rows + 3.0))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_w, fig_h),
                             constrained_layout=True, squeeze=False)
    for idx, (res, (labels, variables, score, annotate)) in enumerate(sorted(freq_data.items())):
        ax = axes[idx // n_cols][idx % n_cols]
        n_rows_f, n_cols_f = score.shape
        cmap = plt.get_cmap("YlGn").copy()
        vmax = 1.0
        cbar_label = "completeness"
        res_rows = [r for r in rows if (r.get("temporal_resolution") or "?") == res]
        nd = sum(1 for r in res_rows if row_status(r) == "downloaded")
        np_ = sum(1 for r in res_rows if row_status(r) == "partial")
        nm = sum(1 for r in res_rows if row_status(r) == "not_downloaded")
        cbar_text = lambda v: "#212121" if v < 0.5 else "white"
        subplot_title = f"{res} ({nd} downloaded, {np_} partial, {nm} missing)"
        cmap.set_bad(color="#eceff1")
        im = ax.imshow(score, cmap=cmap, vmin=0.0, vmax=vmax, aspect="auto", interpolation="nearest")
        ax.set_xticks(range(n_cols_f), labels=variables, rotation=90, fontsize=8)
        ax.set_yticks(range(n_rows_f), labels=labels, fontsize=8)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        if n_rows_f * n_cols_f <= 400:
            for i in range(n_rows_f):
                for j in range(n_cols_f):
                    if not np.isnan(score[i, j]):
                        ax.text(j, i, annotate[i, j], ha="center", va="center", fontsize=6,
                                color=cbar_text(float(score[i, j])))
        ax.set_title(subplot_title, fontsize=10)
        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cbar.set_label(cbar_label, fontsize=8)
        cbar.ax.tick_params(labelsize=7)
    for idx in range(n_res, n_rows * n_cols):
        axes[idx // n_cols][idx % n_cols].set_visible(False)
    nd_all = sum(1 for r in rows if row_status(r) == "downloaded")
    np_all = sum(1 for r in rows if row_status(r) == "partial")
    nm_all = sum(1 for r in rows if row_status(r) == "not_downloaded")
    fig.suptitle(f"CDS Catalogue Status\n{title_extra}"
                 f"{n} entries   —   {nd_all} downloaded    {np_all} partial    {nm_all} missing",
                 fontsize=12, x=0.01, ha="left")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path} ({n} entries: {nd_all} downloaded, {np_all} partial, {nm_all} missing)")


def main():
    import matplotlib
    matplotlib.use("Agg")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=DEFAULT_CSV,
                    help=f"CDS catalogue CSV (default: {DEFAULT_CSV})")
    ap.add_argument("--dataset-type", help="Filter by dataset_type (reanalysis, observation, projections)")
    ap.add_argument("--product-type", help="Filter by product_type (raw, derived)")
    ap.add_argument("--temporal-resolution", help="Filter by temporal_resolution (hourly, daily, monthly)")
    ap.add_argument("--interpolation", help="Filter by interpolation (native, gr006, gr025, gr100)")
    ap.add_argument("--image", default="./cds_catalog.png", help="Output image (default: ./cds_catalog.png)")
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        print(f"Catalogue CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)
    rows = read_csv_rows(args.csv)
    title_extra = (f"from {args.csv}  "
                   f"dataset_type={args.dataset_type or '*'}  "
                   f"product_type={args.product_type or '*'}  "
                   f"temporal_resolution={args.temporal_resolution or '*'}  "
                   f"interpolation={args.interpolation or '*'}\n")
    rows = filter_rows(rows, args.dataset_type, args.product_type,
                       args.temporal_resolution, args.interpolation)
    if not rows:
        print("No rows match the filters.", file=sys.stderr)
        sys.exit(1)
    plot(rows, title_extra, args.image)


if __name__ == "__main__":
    main()
