# Changelog

## 0.2.0 — 2026-09-24

- Split monolithic `esgf.py` into `src/esgf_stac/` utilities
  (`config`, `cql`, `client`, `records`, `files`, `tables`, `health`, `local`).
- Moved CLIs to `src/esgf_stac/cli/` (`search`, `health`, `download`, `catalog`, `plot`)
  with shared argparse helpers in `cli/common.py`.
- Added `README.md`, `LICENSE`, `CONTRIBUTING.md`, offline `tests/`.
- `esgf.py` kept as backward-compat shim.

## 0.1.0

- Initial flat scripts: `esgf.py`, `stac_*.py`, `search_nodes.py`.
