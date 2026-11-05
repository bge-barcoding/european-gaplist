# Developer guide

## Layout

```
config/            settings users edit (validated by gaplist.config)
notebooks/         the front end: one section per step, calling the package
Start European gaplist.command / .bat   double-click launchers (macOS / Windows)
src/gaplist/       all logic
  config.py        reads and checks the settings; plain-language errors
  db.py, schema.sql  the DuckDB run database
  col_source.py    obtains a CoL ColDP release (manual file, cache, ChecklistBank)
  backbone.py      Phase 1: taxon and synonym tables from NameUsage
  names.py         normalises hand-written names
  resolve.py       matches names to the backbone; review spreadsheets
  legacy.py        Phase 2a: the earlier checklist (gaplist-data)
  gbif.py          Phase 2b: GBIF species-list downloads
  bold.py          Phase 3: BOLD BCDM snapshot, barcode status
  export.py        Phase 4: combine evidence, write the target list
  deploy.py        Phase 4b: load into the website's Postgres table
  check.py         Phase 0: settings and database check
tests/             pytest; sample data inline in the tests
data/              downloads and results; never committed
```

Every step returns a small result object (`ok`, `message`, a table). Its
`message` is what users see, so it is written in plain language and says what
to do. Never let a traceback be the user's only explanation for an expected
failure (missing file, unreachable service, bad setting).

## Environment and tests

```bash
pixi install            # locked environment from pixi.lock
pixi run -e test test   # all tests
pixi run check          # check the settings
pixi run lab            # open the notebook (what the launchers do)
pixi run kernel         # only to use the notebook from a Jupyter installed elsewhere
```

All dependencies come from conda-forge; the package is used from `src/` via
`PYTHONPATH`, so edits take effect without reinstalling. Keep `pixi.toml` and
`[project.dependencies]` in `pyproject.toml` in step.

The deploy tests start a throwaway Postgres server from the test
environment. Postgres refuses to run as root, so they skip locally as root;
they run in CI.

## The data model

DuckDB file `data/gaplist.duckdb`, created from `schema.sql` (idempotent;
new columns are added with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).

| Table | Filled by | Contents |
| --- | --- | --- |
| `run` | every step | versions, DOIs and settings fingerprint per run |
| `taxon` | backbone | accepted taxa with parent, nested sets, the seven fixed ranks, `species_id`, `xr_added` |
| `synonym` | backbone | synonyms pointing to accepted taxa |
| `name_resolution` | legacy, gbif, bold | one row per (source, name) with outcome and CoL species |
| `evidence` | legacy, gbif, bold | one row per (species, source): evidence of occurrence in Europe |
| `specimen`, `barcode`, `marker` | bold | public BOLD records placed on species |
| `barcode_status` | bold | counts per species |

Section 1 starts a new run and clears all result tables; every other step
replaces only its own rows.

## Name matching

`resolve.resolve()` is shared by all sources. Source names and CoL names are
normalised the same way (subgenus, rank markers and diacritics removed); see
the outcome codes in the module docstring. Near matches and uncertain
identifications never resolve automatically. `config/curation.tsv` decisions
are applied last.

## Adding an evidence source

1. Write a module that obtains the data and builds `resolve.Query` objects
   (source name, original name, classification hints).
2. Call `resolve.resolve()`, store with `resolve.store()`, and write a review
   list with `resolve.write_review()`.
3. Insert one `evidence` row per resolved species with a new `source` value.
4. Add a column for it in `export.build_table()` and, if it should appear on
   the website, in `export.seed_rows()` (`SpeciesLocality`).
5. Add a notebook section, a test, and a line in the user documentation.

## Things learnt from real data

- The plain CoL ColDP export has no extinct flags; the extended export
  (`format=ColDP&extended=true`) does, and is used.
- CoL XR names may include the subgenus, rank markers and diacritics.
- The XR attaches BOLD BINs to species as unranked children; they are skipped.
- GBIF may run an older CoL release than ours; about 1% of species keys
  differ and are matched by name.
- GBIF vocabulary values are lowercase (`managed`, `introduced`).
- BOLD writes missing values as the text `NA`.
- YAML reads `NO` (Norway) as false; the settings reader only treats
  `true`/`false` as booleans.
- The website's EF migration mixes SQL Server and Postgres types; the deploy
  step checks the live table's columns before writing.
