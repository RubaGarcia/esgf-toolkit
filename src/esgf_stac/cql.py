"""CQL2 filter helpers for ESGF STAC search bodies."""

from .config import COLUMN_CANDIDATES, PREFIXES


def eq(prop, value):
    """Build a CQL2 equality node: property == value."""
    return {"op": "=", "args": [{"property": prop}, value]}


def cql_or(props):
    """Combine (property, value) pairs into a CQL2 OR (single pair returned bare)."""
    args = [eq(prop, value) for prop, value in props]
    if len(args) == 1:
        return args[0]
    return {"op": "or", "args": args}


def cql_props(column: str) -> list:
    """Expand a logical column to every prefixed property name it may live under."""
    return [f"{p}{cand}" for p in PREFIXES for cand in COLUMN_CANDIDATES.get(column, [])]


def parse_filter_values(value) -> list:
    """Normalize a filter value: 'tas, hurs' or ['tas','hurs'] -> ['tas', 'hurs']."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value]
    else:
        items = [v.strip() for v in str(value).split(",")]
    return [v for v in items if v]


def build_body(collection: str | None, limit: int, filters: dict) -> dict:
    """Assemble the POST /search request body: page limit, collection, CQL2 filters."""
    body = {"limit": limit}
    if collection:
        body["collections"] = [collection]
    terms = []
    for column, value in filters.items():
        values = parse_filter_values(value)
        if values:
            props = cql_props(column)
            terms.append(cql_or([(prop, v) for prop in props for v in values]))
    if terms:
        body["filter-lang"] = "cql2-json"
        body["filter"] = terms[0] if len(terms) == 1 else {"op": "and", "args": terms}
    return body
