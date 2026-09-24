# ESGF STAC Toolkit

Search, monitor, download, catalogue and plot **ESGF** climate data through the
ESGF-NG STAC API (`discovery.east/west.esgf.io`).

![pixi](https://img.shields.io/badge/managed%20with-pixi-blue)
![python](https://img.shields.io/badge/python-%3E%3D3.11-blue)

## Features

- **Search** (`stac_search`) — metadata table of matching datasets, no downloads.
- **Health** (`stac_health`) — probe STAC nodes + file servers into `health.csv`,
  with daemon mode for periodic checks.
- **Download** (`stac_download`) — resumable, parallel, checksum-verified downloads
  with replica failover (healthy hosts first).
- **Catalogue** (`stac_catalog`) — compare local `esgf_data/` vs remote: per-dataset
  `complete / partial / missing` + CSV.
- **Plot** (`stac_plot`) — model × variable completeness heatmap (`catalog.png`).

## Quickstart

```bash
pixi install
pixi run stac_health                        # write health.csv
pixi run stac_search -- --collection CORDEX-CMIP6 --variable tas --limit 5
pixi run stac_download -- --collection CORDEX-CMIP6 --variable tas --dry-run
pixi run stac_catalog -- --out ./esgf_data --csv ./catalog.csv --show
pixi run stac_plot                           # writes catalog.png
```

Or with plain pip (editable install):

```bash
pip install -e .
python -m esgf_stac.cli.search --variable tas --limit 5
```

## Repository layout

```
src/esgf_stac/        library (importable)
  config.py           NODES, prefixes, column profiles, title layouts
  cql.py              CQL2 filter builders (eq/cql_or/build_body/...)
  client.py           HTTP session, search(), iter_items() pagination
  records.py          STAC item -> flat record (prefix strip, title fallback)
  files.py            iter_files(), checksum + verify_file()
  tables.py           items_to_dataframe(), files_to_dataframe(), printing
  health.py           probe STAC/file servers, load/write health.csv
  local.py            scan_local(), is_present()
  cli/                one module per command: search, health, download, catalog, plot
    common.py         shared --node / filter / --health argparse helpers
esgf.py               backward-compat shim (prefer `import esgf_stac`)
scripts/legacy/       one-off experiments (e.g. search_nodes.py)
tests/                pytest suite (offline, no network)
examples/             example commands and sample outputs
data/                 local runtime outputs (git-ignored): esgf_data/, *.csv, *.png
```

### Where did `esgf.py` go?

The old 550-line `esgf.py` was split by responsibility into the modules above
(`config` / `cql` / `client` / `records` / `files` / `tables` / `health` / `local`).
`esgf.py` remains as a thin re-export shim so old scripts keep working.

## CLI reference

All commands share `--node {east,west}` (default `east`) and comma-separated
facet filters: `--collection --model --rcm-model --driving-model --experiment
--variable --frequency --grid --member --domain --activity`.

| Command | Purpose | Key outputs |
|---|---|---|
| `stac_search [--limit 20] [--matched] [--full] [--csv out.csv]` | first-page metadata table + availability | stdout table, optional CSV |
| `stac_health [--interval 0] [--include-additional]` | probe hosts | `health.csv`, console dashboard |
| `stac_download [--out ./esgf_data] [--jobs 4] [--dry-run] [--manifest m.csv]` | download with resume + verify | files under `--out`, manifest CSV |
| `stac_catalog [--out ./esgf_data] [--csv ./catalog.csv] [--show]` | local-vs-remote completeness | `catalog.csv` |
| `stac_plot [--csv ./catalog.csv] [--refresh] [--image ./catalog.png]` | heatmap | `catalog.png` |

Availability flags (`avail` column) come from `health.csv`:
`ok` all replicas healthy · `down` all down · `warn` mixed · `?` unknown.

## Examples

```bash
# How many CORDEX tas datasets exist?
python -m esgf_stac.cli.search --collection CORDEX-CMIP6 --variable tas --matched

# Peek at CMIP7 monthly tas for two models
python -m esgf_stac.cli.search --collection CMIP7 --variable tas \
  --frequency mon --model UKESM1-3-LL,EC-Earth3 --limit 10

# Dry-run a download (list files + hosts, download nothing)
python -m esgf_stac.cli.download --collection CORDEX-CMIP6 --variable tas --dry-run

# Catalogue what you already have
python -m esgf_stac.cli.catalog --out ./esgf_data --csv ./catalog.csv --show --missing-only

# Heatmap from the catalogue
python -m esgf_stac.cli.plot --csv ./catalog.csv --image ./catalog.png
```

## Development

```bash
pixi run test        # pytest
pixi run lint        # ruff (if configured)
```

## License

MIT — see [LICENSE](LICENSE).
