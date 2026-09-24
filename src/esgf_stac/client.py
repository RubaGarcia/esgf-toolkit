"""HTTP client for the ESGF STAC API (shared session + pagination)."""

import requests

from .config import PAGE_SIZE
from .cql import build_body

_session: requests.Session | None = None


def post(node: str, body: dict, timeout: int = 60):
    """POST a search body to {node}/search and return the parsed JSON."""
    global _session
    if _session is None:
        _session = requests.Session()
    r = _session.post(f"{node}/search", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()


def search(node: str, collection: str | None, limit: int, filters: dict):
    """Run a single (first-page) search and return the full response JSON."""
    return post(node, build_body(collection, limit, filters))


def iter_items(node: str, collection: str | None, filters: dict,
               max_items: int = 0, page_size: int = PAGE_SIZE):
    """Yield all items matching filters, paginating via POST next links."""
    body = build_body(collection, page_size, filters)
    yielded = 0
    while True:
        data = post(node, body)
        for item in data.get("features", []):
            yield item
            yielded += 1
            if max_items and yielded >= max_items:
                return
        next_link = next((l for l in data.get("links", []) if l.get("rel") == "next"), None)
        if not next_link:
            return
        body = next_link.get("body")
        if not body:
            return
