# Reading the results

Section 4 writes three files to `data/output/`.

## `summary.md`: start here

A report of the run, written to be read on its own by anyone, including
people who have never seen the pipeline. Share it as it is. It explains:

- **In short**: how many species count as European, how many have a barcode,
  how many are gaps, and how many are barcoded from European specimens.
- **How a species gets on the list**: the three sources, the countries that
  count as Europe, and how many species each combination of sources supports.
- **Barcodes: own and other**: BGE's own barcodes versus everyone else's.
- **Things to keep in mind**: names still waiting for a person, species whose
  names only the Catalogue of Life eXtended Release has, possibly alien
  species, and gaps in the classification.
- **Coverage per group**: species, barcoded species and gaps for every class,
  with common names.
- **Data used in this run**: the exact versions, with the DOIs to cite.
- **Glossary**: the few technical words used.

## `targetlist_seed.tsv`: for the website

One row per European species, in exactly the columns the website loads:

| Column | Meaning |
| --- | --- |
| `Kingdom` to `Species` | The classification, from Catalogue of Life. A cell is empty when CoL gives no name at that rank. |
| `SpeciesLocality` | Which sources say the species occurs in Europe: `GBIF`, `BOLD`, and the source codes of the earlier checklist (e.g. `FE,SyDip`; see [source codes](legacy-source-codes.md)). |
| `SpeciesOccurrenceStatus` | `gap` when there is no barcode-compliant sequence; otherwise empty. |
| `Collected` | Set in `target_list.yaml`; 0 for now. |
| `Wanted` | 0, 1 or 2, set in `target_list.yaml`. |
| `OwnBarcodes` | Barcode-compliant sequences from BGE projects. |
| `OtherBarcodes` | All other barcode-compliant sequences. |

The website adds its own columns from these, such as the total number of
barcodes.

## `gaplist_full.tsv`: all details

The same species with everything the pipeline knows. Open it in a
spreadsheet program to filter and sort.

| Column | Meaning |
| --- | --- |
| `taxon_id` | The species' Catalogue of Life identifier. |
| `kingdom` to `species` | The classification. |
| `xr_only` | `True` when only the CoL eXtended Release has this species, not the expert-curated base release. |
| `sources` | How many sources say the species occurs in Europe (1 to 3). |
| `in_legacy`, `in_gbif`, `in_bold` | Which sources. |
| `legacy_codes` | The earlier checklist's source codes. |
| `gbif_records` | Number of qualifying GBIF records in Europe. |
| `bold_european_specimens` | Number of BOLD specimens collected in Europe. |
| `possibly_alien` | `True` when GBIF has records of it marked as introduced. |
| `compliant` | Barcode-compliant sequences (COI-5P, at least 500 bases), from anywhere. |
| `european_compliant` | The same, from specimens collected in Europe. |
| `own`, `other` | Compliant sequences from BGE projects, and from everyone else. |
| `bins` | Number of distinct BOLD BINs among the compliant sequences. |
| `bold_specimens` | All public BOLD specimens identified as this species. |

## Other files

| Folder | What is there |
| --- | --- |
| `data/review/` | The review lists: see [Reviewing names](reviewing-names.md). |
| `data/reports/` | Species per class in the backbone, and the earlier checklist's source codes. |
| `data/gaplist.duckdb` | The pipeline's database with all intermediate results, for people who know SQL. |
