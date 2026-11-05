# European gaplist

Which European animal species already have a public DNA barcode, and which
are still missing? This repository answers that question and produces the
data behind the iBOL Europe / BGE target list.

It replaces an earlier workflow spread over three repositories
([gaplist-data](https://github.com/bge-barcoding/gaplist-data),
[ibol-europe-gaplist-app](https://github.com/bge-barcoding/ibol-europe-gaplist-app)
and [bge-targetlist](https://github.com/bge-barcoding/bge-targetlist)).
The new version can be rerun at any time by someone who does not program.

## How it works

1. **Classification.** All animal species and their synonyms come from one
   fixed release of the [Catalogue of Life](https://www.catalogueoflife.org).
2. **Europe.** A species is on the list when there is evidence that it
   occurs in one of the countries in `config/europe.yaml`. Evidence comes
   from the earlier European checklist, from GBIF records and from BOLD
   specimens. Every name is matched to Catalogue of Life, including
   synonyms.
3. **Barcodes.** For each species, public COI-5P barcodes of at least 500
   bases are counted in a fixed snapshot of
   [BOLD](https://boldsystems.org). A species without any is a gap.
4. **Target list.** The result is written in the layout the
   [target list website](https://github.com/bge-barcoding/bge-targetlist)
   expects.

## Running it

The pipeline runs on an ordinary laptop (16 GB of memory, 25 GB of free
disk). After a one-time setup, double-click `Start European gaplist.command`
(Mac) or `Start European gaplist.bat` (Windows); the notebook opens in your
browser. Run it from top to bottom; it explains each step as you go. See
[getting started](docs/getting-started.md) for the setup.

To change what the pipeline does (for example, which countries count as
Europe), edit the files in the `config` folder.

**Documentation** for people running the pipeline is in [docs](docs/README.md):
[getting started](docs/getting-started.md),
[how it works](docs/how-it-works.md),
[changing the settings](docs/settings.md),
[reviewing names](docs/reviewing-names.md),
[reading the results](docs/results.md) and
[when something goes wrong](docs/troubleshooting.md).
Developers: see the [developer guide](docs/developer-guide.md).

## Status

Work in progress, following the roadmap. Currently in place: the settings
files, their checks and the database layout (Phase 0), the Catalogue of
Life backbone (Phase 1), name matching with the earlier European checklist
and GBIF occurrence evidence (Phase 2), barcode counts from BOLD (Phase 3),
the export to the target list website (Phase 4), and documentation for
non-technical users (Phase 5).

## For developers

The environment is managed with [pixi](https://pixi.sh):

```bash
pixi install            # create the locked environment
pixi run lab            # open the notebook (what the launchers do)
pixi run check          # check the settings from the command line
pixi run -e test test   # run the tests
```

All logic lives in the `gaplist` package under `src/`; the notebook only
calls it. Downloads and results go in `data/`, which Git ignores.

## Licence

MIT. See [LICENSE](LICENSE).
