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

Open `notebooks/gaplist.ipynb` on the shared Jupyter hub and run it from
top to bottom. The notebook explains each step as you go.

To change what the pipeline does (for example, which countries count as
Europe), edit the files in the `config` folder. `config/README.md` explains
each one.

## Status

Work in progress, following the roadmap. Currently in place: the settings
files, their checks and the database layout (Phase 0), the Catalogue of
Life backbone (Phase 1), name matching with the earlier European checklist
and GBIF occurrence evidence (Phase 2).

## For developers

The environment is managed with [pixi](https://pixi.sh):

```bash
pixi install            # create the locked environment
pixi run kernel         # register the "European gaplist" Jupyter kernel
pixi run check          # check the settings from the command line
pixi run -e test test   # run the tests
```

All logic lives in the `gaplist` package under `src/`; the notebook only
calls it. Downloads and results go in `data/`, which Git ignores.

## Licence

MIT. See [LICENSE](LICENSE).
