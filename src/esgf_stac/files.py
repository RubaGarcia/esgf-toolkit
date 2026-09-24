"""File-level helpers: replica targets, checksums, verification."""

import hashlib

from .config import CHUNK


def iter_files(items):
    """Yield download targets: (local_path, [(href, protocol, checksum, size), ...])."""
    seen = {}
    for item in items:
        for asset in item.get("assets", {}).values():
            protocol = asset.get("protocol")
            roles = asset.get("roles", [])
            if protocol != "https" or "data" not in roles:
                continue
            lp = asset.get("file:local_path")
            if lp is None:
                continue
            target = seen.setdefault(lp, (lp, []))
            target[1].append(
                (
                    asset.get("href"),
                    protocol,
                    asset.get("file:checksum"),
                    asset.get("file:size"),
                )
            )
    return [t for t in seen.values() if t[1]]


def checksum_algorithm(checksum: str | None) -> str:
    """Guess hash algorithm from a checksum string ('md5', 'sha256', or '')."""
    if not checksum:
        return ""
    if len(checksum) == 32 and checksum.isalnum():
        return "md5"
    if len(checksum) >= 68:
        return "sha256"
    return ""


def verify_file(path: str, checksum: str | None) -> bool:
    """Hash a file and compare to the expected checksum; True if unverifiable."""
    algo = checksum_algorithm(checksum)
    if not algo:
        return True
    h = hashlib.md5() if algo == "md5" else hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    digest = h.hexdigest()
    expected = checksum.lower()
    if algo == "md5":
        return digest == expected
    return expected.endswith(digest) or expected == digest
