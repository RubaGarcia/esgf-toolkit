"""pandas tables: item records, file manifests, display helpers."""

from .config import CORE_COLUMNS, CORDEX_DISPLAY, FILE_COLUMNS, GENERIC_DISPLAY
from .records import item_to_record, server_name


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

    with pd.option_context("display.max_columns", None, "display.width", 250,
                           "display.max_colwidth", 40, "display.expand_frame_repr", False):
        print(view.to_string(index=False))
