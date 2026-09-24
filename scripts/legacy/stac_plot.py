#!/usr/bin/env python3
"""Generate an image showing which ESGF datasets are downloaded.

Reads an existing catalogue CSV (default ./catalog.csv) when present —
applying any --variable/--model/... filters client-side — otherwise builds
rows via the STAC API (see stac_catalog). Draws an aggregated heatmap:

  rows     models (prefixed by collection when several are present)
  columns  variables
  colour   download completeness (green = all complete, red = none)

Cells are annotated with complete/total dataset counts when the grid is
small enough. A colourbar and summary counts are included.

Usage:
  python stac_plot.py                       # from ./catalog.csv
  python stac_plot.py --variable tas,hurs    # filter the CSV client-side
  python stac_plot.py --refresh              # re-query STAC and rewrite CSV
  python stac_plot.py --csv ./other.csv
"""

import argparse
import csv
import os
import sys
from collections import defaultdict

import requests

import esgf

DEFAULT_CSV = "./catalog.csv"


def read_csv_rows(csv_path):
    """Read a catalogue CSV into a list of dict rows.

    Used in: load_rows.
    """
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def write_csv_rows(csv_path, rows):
    """Write dict rows to a CSV (header from the first row); no-op when rows is empty.

    Used in: load_rows.
    """
    if not rows:
        return
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def filter_rows(rows, collection: str | None, filters: dict) -> list:
    """Apply STAC-style filters to catalogue CSV rows client-side.

    Comma-separated cell values are matched as sets so multi-value fields still hit.
    Used in: load_rows.
    """
    active = []
    for col, raw in filters.items():
        vals = esgf.parse_filter_values(raw)
        if vals:
            active.append((col, set(vals)))

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
    """Rebuild catalogue rows live from the STAC API + local scan (used on --refresh/missing CSV).

    Delegates row building to stac_catalog.fmt_row.
    Used in: load_rows.
    """
    import stac_catalog

    node = esgf.NODES[args.node]
    filters = stac_catalog.build_filters(args)
    sizes, base = stac_catalog.scan_local(args.out)
    _, statuses = esgf.load_health(args.health)
    rows = []
    for item in esgf.iter_items(node, args.collection, filters):
        r = stac_catalog.fmt_row(item, args.out, sizes, base, statuses, show_missing_only=False)
        if r:
            rows.append(r)
    return rows


def load_rows(args):
    """Return the rows to plot: refresh/build from STAC, or read + filter the existing CSV.

    Used in: main.
    """
    import stac_catalog

    filters = stac_catalog.build_filters(args)
    csv_path = args.csv or DEFAULT_CSV

    if args.refresh or not os.path.exists(csv_path):
        rows = compute_rows(args)
        if csv_path:
            write_csv_rows(csv_path, rows)
        return rows

    return filter_rows(read_csv_rows(csv_path), args.collection, filters)


def aggregate(rows):
    """Group rows -> (sorted model labels, sorted variables, score matrix, counts).

    Score is (complete + 0.5*partial)/n per (model, variable) cell; NaN where no data.
    Used in: plot.
    """
    import numpy as np

    collections = {r.get("collection") or "?" for r in rows}
    multi = len(collections) > 1
    buckets = defaultdict(lambda: {"n": 0, "complete": 0, "partial": 0, "missing": 0})
    for r in rows:
        coll = r.get("collection") or "?"
        model = r.get("model") or "?"
        var = r.get("variable") or "?"
        label = f"{coll} · {model}" if multi else model
        b = buckets[(label, var)]
        b["n"] += 1
        status = r.get("status") or "missing"
        if status in b:
            b[status] += 1
        else:
            b["missing"] += 1

    labels = sorted({k[0] for k in buckets})
    variables = sorted({k[1] for k in buckets})
    li = {x: i for i, x in enumerate(labels)}
    vi = {x: i for i, x in enumerate(variables)}

    score = np.full((len(labels), len(variables)), np.nan)
    annotate = np.zeros((len(labels), len(variables)), dtype=object)
    for (lab, var), b in buckets.items():
        i, j = li[lab], vi[var]
        score[i, j] = (b["complete"] + 0.5 * b["partial"]) / b["n"]
        annotate[i, j] = f"{b['complete']}/{b['n']}"
    return labels, variables, score, annotate


def plot(rows, title_extra, out_path):
    """Render the model x variable completeness heatmap and save it to out_path.

    Used in: main.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    if not rows:
        print("No dataset rows to plot.", file=sys.stderr)
        sys.exit(1)

    labels, variables, score, annotate = aggregate(rows)
    n = len(rows)
    n_complete = sum(1 for r in rows if r.get("status") == "complete")
    n_partial = sum(1 for r in rows if r.get("status") == "partial")
    n_missing = sum(1 for r in rows if r.get("status") == "missing")

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

    fig.suptitle(
        f"ESGF Dataset Download Status\n"
        f"{title_extra}"
        f"{n} datasets   —   {n_complete} complete    {n_partial} partial    {n_missing} missing",
        fontsize=12, x=0.01, ha="left",
    )

    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path} ({n} datasets: {n_complete} complete, {n_partial} partial, {n_missing} missing)")


def main():
    """CLI entry point: load catalogue rows (CSV or STAC) and write the heatmap image.

    Used in: `python stac_plot.py` / pixi task `stac_plot`.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: F401 (import in function to keep Agg before pyplot)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node", choices=esgf.NODES, default="east", help="ESGF STAC node (default: east)")
    ap.add_argument("--collection", help="Filter by collection (e.g. CMIP7)")
    ap.add_argument("--model", help="Model / source_id, comma-separated (e.g. UKESM1-3-LL,EC-Earth3)")
    ap.add_argument("--experiment", help="Experiment / scenario, comma-separated (e.g. historical,ssp585)")
    ap.add_argument("--variable", help="Variable_id, comma-separated (e.g. tas,hurs)")
    ap.add_argument("--frequency", help="Frequency, comma-separated (e.g. mon,day)")
    ap.add_argument("--grid", help="Grid label, comma-separated (e.g. gr,native)")
    ap.add_argument("--member", help="Variant/member label, comma-separated (e.g. r1i1p1f1,r2i1p1f1)")
    ap.add_argument("--domain", help="Realm, comma-separated (e.g. atmos,ocean)")
    ap.add_argument("--out", default="./esgf_data", help="Local download dir to scan (default: ./esgf_data)")
    ap.add_argument("--csv", default="", help=f"Catalogue CSV (default: {DEFAULT_CSV} when present)")
    ap.add_argument("--refresh", action="store_true", help="Re-query STAC and rewrite the CSV")
    ap.add_argument("--health", default="./health.csv", help="Health CSV (default: ./health.csv)")
    ap.add_argument("--image", default="./catalog.png", help="Output image (default: ./catalog.png)")
    args = ap.parse_args()

    csv_path = args.csv or DEFAULT_CSV
    from_stac = args.refresh or not os.path.exists(csv_path)
    has_filters = any(
        esgf.parse_filter_values(v)
        for v in (args.collection, args.model, args.experiment, args.variable,
                  args.frequency, args.grid, args.member, args.domain)
    )
    if from_stac:
        title_extra = (
            f"collection={args.collection or '*'}"
            f"  model={args.model or '*'}"
            f"  variable={args.variable or '*'}"
            f"  experiment={args.experiment or '*'}\n"
        )
    elif has_filters:
        title_extra = (
            f"from {csv_path}"
            f"  collection={args.collection or '*'}"
            f"  model={args.model or '*'}"
            f"  variable={args.variable or '*'}"
            f"  experiment={args.experiment or '*'}\n"
        )
    else:
        title_extra = f"from {csv_path}\n"

    try:
        rows = load_rows(args)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("No dataset rows to plot.", file=sys.stderr)
        sys.exit(1)

    plot(rows, title_extra, args.image)


if __name__ == "__main__":
    main()
