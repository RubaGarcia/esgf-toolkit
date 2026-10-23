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
- **Catalogue** (`stac_catalog`) — per-collection CSVs of the local download
  tree (`--out`, default `$ESGF`)
  (one row per leaf directory: DRS facets + file count + size); with
  `--compare` it prints a completeness report in the same style as
  `stac_search` (search columns + `variable_id` + `local/remote` + `status`)
  and writes the master CSV (`complete / partial / missing`).
- **Plot** (`stac_plot`) — model × variable heatmap of local file counts
  (`catalog.png`); `--compare` plots remote completeness instead.

## Quickstart

```bash
pixi install
pixi run stac_health                        # write health.csv
pixi run stac_search -- --collection CORDEX-CMIP6 --variable tas --limit 5
pixi run stac_download -- --collection CORDEX-CMIP6 --variable tas --dry-run
pixi run stac_catalog -- --show                    # scan $ESGF -> ./catalog/<collection>.csv
pixi run stac_plot                           # writes catalog.png from ./catalog
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
  tables.py           items_to_dataframe(), collapse_variables(), combine_time(), printing
  health.py           probe STAC/file servers, load/write health.csv
  local.py            scan_local(), parse_drs(), catalog_rows(), is_present()
  cli/                one module per command: search, health, download, catalog, plot
    common.py         shared --node / filter / --health argparse helpers
esgf.py               backward-compat shim (prefer `import esgf_stac`)
scripts/legacy/       one-off experiments (e.g. search_nodes.py)
tests/                pytest suite (offline, no network)
examples/             example commands and sample outputs
data/                 local runtime outputs (git-ignored): esgf_data/, *.csv, *.png
```


## CLI reference

All commands share `--node {east,west}` (default `east`) and comma-separated
facet filters: `--collection --model --rcm-model --driving-model --experiment
--variable --frequency --grid --member --domain --activity`.
The local data root `--out` defaults to `$ESGF` (falling back to `./esgf_data`)
for `stac_catalog`, `stac_plot` and `stac_download`.

| Command | Purpose | Key outputs |
|---|---|---|
| `stac_search [--limit 20] [--matched] [--columns COLS] [--full] [--csv out.csv]` | metadata table + availability | stdout table, one row per dataset (`n_variables`, `time`), optional CSV |
| `stac_health [--interval 0] [--include-additional]` | probe hosts | `health.csv`, console dashboard |
| `stac_download [--out $ESGF] [--jobs 4] [--dry-run] [--manifest m.csv]` | download with resume + verify | files under `--out`, manifest CSV |
| `stac_catalog [--out $ESGF] [--csv-dir ./catalog] [--compare] [--csv ./catalog.csv] [--missing-only] [--show]` | local inventory; `--compare`: completeness report vs STAC | `<collection>.csv` per collection; with `--compare` also printed report + `catalog.csv` |
| `stac_plot [--csv-dir ./catalog] [--compare] [--csv ./catalog.csv] [--refresh] [--image ./catalog.png]` | local file-count heatmap (`--compare`: completeness) | `catalog.png` |

Availability flags (`avail` column) come from `health.csv`:
`ok` all replicas healthy · `down` all down · `warn` mixed · `?` unknown.

## Examples

```bash
# How many CORDEX tas datasets exist?
python -m esgf_stac.cli.search --collection CORDEX-CMIP6 --variable tas --matched

# Peek at CMIP7 monthly tas for two models
python -m esgf_stac.cli.search --collection CMIP7 --variable tas \
  --frequency mon --model UKESM1-3-LL,EC-Earth3 --limit 10

# One row per dataset: n_variables counts the available variables,
# time is start -> end collapsed into one column, size/files are summed
python -m esgf_stac.cli.search --collection CMIP7 --variable tas,pr \
  --frequency mon --limit 10
# `--csv` always writes the raw per-variable rows; --columns widens the table
# (e.g. variable_id for the actual list, start_datetime/end_datetime for ISO bounds)
python -m esgf_stac.cli.search --collection CORDEX-CMIP6 --variable tas,pr \
  --columns model,experiment,variable_id,n_variables,time,size_bytes

# Dry-run a download (list files + hosts, download nothing)
python -m esgf_stac.cli.download --collection CORDEX-CMIP6 --variable tas --dry-run

# Catalogue what you already have (one CSV per collection, offline; $ESGF default)
python -m esgf_stac.cli.catalog --show

# Compare local vs STAC: search-style table + complete/partial/missing verdict
python -m esgf_stac.cli.catalog --collection CORDEX-CMIP6 --compare \
  --csv ./catalog_compare.csv --missing-only

# Heatmap of local file counts (model x variable)
python -m esgf_stac.cli.plot --csv-dir ./catalog --image ./catalog.png

# Heatmap of local-vs-remote completeness instead
python -m esgf_stac.cli.plot --compare --csv ./catalog_compare.csv
```

## Development

```bash
pixi run test        # pytest
pixi run lint        # ruff (if configured)
```

## License

MIT — see [LICENSE](LICENSE).
