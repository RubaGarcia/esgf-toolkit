"""Local download-directory helpers."""

import os


def scan_local(out_dir: str):
    """Return ({relpath: size}, {basename: [relpaths]}) in a single walk."""
    sizes = {}
    base = {}
    for root, _, files in os.walk(out_dir):
        for f in files:
            full = os.path.join(root, f)
            rp = os.path.relpath(full, out_dir).replace(os.sep, "/")
            try:
                sizes[rp] = os.path.getsize(full)
            except OSError:
                continue
            base.setdefault(f, []).append(rp)
    return sizes, base


def is_present(lp: str, size, out_dir: str, sizes: dict, base: dict) -> bool:
    """Check whether a remote file is already downloaded (by path, then basename)."""
    if lp in sizes:
        return sizes[lp] == size if size else True
    for cand in base.get(os.path.basename(lp), []):
        if cand in sizes:
            return sizes[cand] == size if size else True
    return False
