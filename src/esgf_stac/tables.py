"""pandas tables: item records, file manifests, display helpers."""

from .config import CORE_COLUMNS, CORDEX_DISPLAY, FILE_COLUMNS, GENERIC_DISPLAY
from .records import item_to_record, server_name

VARIABLE_PREFIX = "variable"
META_COLUMNS = ("title", "item_id", "title_supplemented")
TITLE_COLUMNS = ("title", "item_id", "base_id")
VARIABLE_SPECIFIC_COLUMNS = ("base_id", "vertical_label")
SUM_COLUMNS = ("size_bytes", "n_files", "n_servers", "size")
VOLATILE_COLUMNS = ("pid", "created", "updated")


def items_to_dataframe(items: list, statuses: dict | None = None):
    """STAC items -> DataFrame (one row per item, core columns first)."""
    import pandas as pd

    records = [item_to_record(it, statuses) for it in items]
    if not records:
        return pd.DataFrame(columns=CORE_COLUMNS)
    extra = sorted({k for r in records for k in r} - set(CORE_COLUMNS))
    return pd.DataFrame(records)[CORE_COLUMNS + extra]


def files_to_dataframe(items: list, statuses: dict | None = None):
    """STAC items -> per-file manifest DataFrame (item facets repeated per file)."""
    import pandas as pd

    rows = []
    for item in items:
        rec = item_to_record(item, statuses)
        for name, asset in (item.get("assets", {}) or {}).items():
            if asset.get("protocol") != "https" or "data" not in (asset.get("roles") or []):
                continue
            href = asset.get("href") or ""
            row = dict(rec)
            row["file_name"] = name
            row["local_path"] = asset.get("file:local_path") or ""
            row["host"] = server_name(href)
            row["href"] = href
            row["file_size"] = asset.get("file:size") or 0
            row["checksum"] = asset.get("file:checksum") or ""
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=CORE_COLUMNS + FILE_COLUMNS)
    extra = sorted({k for r in rows for k in r} - set(CORE_COLUMNS + FILE_COLUMNS))
    return pd.DataFrame(rows)[CORE_COLUMNS + FILE_COLUMNS + extra]


def _star_variables(value, variables: set) -> str:
    """Replace the variable segment(s) of a dotted id/title with '*'."""
    return ".".join("*" if p in variables else p for p in str(value).split("."))


def _merge_texts(values: list, variables: set) -> str:
    """Merge dotted ids/titles of one dataset: segments that differ become '*'."""
    lists = [str(v).split(".") for v in values]
    if len({len(p) for p in lists}) > 1:
        return _star_variables(values[0], variables)
    return ".".join(t[0] if all(x == t[0] for x in t) else "*" for t in zip(*lists))


def collapse_variables(df) -> "pd.DataFrame":
    """Merge rows that differ only in variable fields into one row per dataset.

    Adds `n_variables` (distinct variables available), turns `variable_id` into a
    comma-separated list and sums the per-variable numeric totals.
    """
    import pandas as pd

    if df.empty or "variable_id" not in df.columns:
        return df
    var_cols = [c for c in df.columns if str(c).startswith(VARIABLE_PREFIX)]
    sums = [c for c in SUM_COLUMNS if c in df.columns]
    excluded = (set(var_cols) | set(META_COLUMNS) | set(sums)
                | set(VOLATILE_COLUMNS) | set(VARIABLE_SPECIFIC_COLUMNS))
    identity = [c for c in df.columns if c not in excluded]
    if not identity:
        return df

    g = df.groupby(identity, dropna=False, sort=False)
    out = g.first()
    variables = g["variable_id"].agg(
        lambda s: sorted({str(x).strip() for x in s if str(x).strip()})).tolist()
    sizes = g.size().tolist()
    out["variable_id"] = [",".join(v) for v in variables]
    out["n_variables"] = [len(v) or int(n) for v, n in zip(variables, sizes)]
    for col in sums:
        if col == "size":
            out[col] = g[col].apply(
                lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum()))
        else:
            out[col] = g[col].sum()
    for col in var_cols:
        if col != "variable_id" and col in out.columns:
            out = out.drop(columns=col)
    var_sets = [set(v) for v in variables]
    for col in TITLE_COLUMNS:
        if col in out.columns:
            texts = g[col].agg(list).tolist()
            out[col] = [_merge_texts(t, vs) for t, vs in zip(texts, var_sets)]
    if "title_supplemented" in out.columns:
        out["title_supplemented"] = [
            ",".join(_star_variables(t, vs) for t in str(v).split(","))
            for v, vs in zip(out["title_supplemented"], var_sets)]
    out = out.reset_index()

    order = [c for c in df.columns if c in out.columns]
    if "variable_id" in order:
        order.insert(order.index("variable_id") + 1, "n_variables")
    else:
        order.append("n_variables")
    return out[order]


def _fmt_time(value) -> str:
    v = "" if value is None else str(value)
    if v in ("", "nan", "NaT", "None"):
        return ""
    return v[:10] if v[10:] in ("T00:00:00Z", "T12:00:00Z") else v


def combine_time(df) -> "pd.DataFrame":
    """Add one `time` column combining start/end datetimes (period bounds)."""
    if "start_datetime" not in df.columns or "end_datetime" not in df.columns:
        return df
    out = df.copy()
    times = []
    for start, end in zip(out["start_datetime"], out["end_datetime"]):
        s, e = _fmt_time(start), _fmt_time(end)
        times.append(s if not e or s == e else f"{s} → {e}")
    out.insert(list(out.columns).index("end_datetime") + 1, "time", times)
    return out


def display_columns(df, requested: str | None = None) -> list:
    """Resolve which columns to print: explicit --columns, else CORDEX vs generic."""
    if requested:
        wanted = [c.strip() for c in requested.split(",") if c.strip()]
        return [c for c in wanted if c in df.columns] or list(df.columns)
    cols = (CORDEX_DISPLAY if ("driving_model" in df.columns
            and df["driving_model"].astype(str).ne("").any()) else GENERIC_DISPLAY)
    return [c for c in cols if c in df.columns]


def print_dataframe(df, columns: list | None = None, max_rows: int = 0) -> None:
    """Print a DataFrame with wide pandas formatting (optional head limit)."""
    if df.empty:
        print("No items found.")
        return
    view = df[columns] if columns else df
    if max_rows and len(view) > max_rows:
        view = view.head(max_rows)
    import pandas as pd

    def _cut(value):
        if isinstance(value, str) and len(value) > 40:
            return value[:37] + "..."
        return value

    view = view.map(_cut) if hasattr(view, "map") else view.applymap(_cut)
    with pd.option_context("display.max_columns", None, "display.width", 250,
                           "display.max_colwidth", 40, "display.expand_frame_repr", False):
        print(view.to_string(index=False))
