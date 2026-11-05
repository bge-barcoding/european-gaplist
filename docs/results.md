# Reading the results

Section 4 writes three files to `data/output/`.

## `summary.md`: start here

A short report of the run:

- **Sources**: the exact data versions used, with DOIs. Cite the Catalogue
  of Life and GBIF DOIs whenever the gap list is published or shared.
- **Totals**: the number of European species, how many have a barcode, how
  many are gaps, how many come only from the CoL eXtended Release, and how
  many are possibly alien.
- **Notes**: anything to be aware of, such as species for which CoL gives no
  family.
- **Per class**: species, barcoded species and gaps for every class.

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
