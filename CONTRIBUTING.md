# Contributing

1. Create a feature branch from `main`.
2. Keep the `src/esgf_stac/` module split: `config`, `cql`, `client`, `records`,
   `files`, `tables`, `health`, `local`, `cli/*`. Don't re-merge into one file.
3. Add/extend offline tests in `tests/` (`pixi run test` must pass without network).
4. Update `README.md` and `CHANGELOG.md` when CLI flags or outputs change.

## Release checklist

- [ ] `pixi run test` green
- [ ] `CHANGELOG.md` entry
- [ ] tag `vX.Y.Z`
