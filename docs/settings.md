# Changing the settings

Every choice the pipeline makes is in the `config` folder. You can change
these files in Jupyter (double-click to open, *File*, *Save*) or directly on
GitHub. You never need to change code.

After changing a setting, run **section 0** of the notebook. It checks all
settings at once and lists every mistake, with the file and what to fix.
Then run the sections that depend on what you changed (see the table at the
end).

## How the `.yaml` files work

- Lines starting with `#` are explanations for people; the pipeline ignores them.
- A list item starts with two spaces, a dash and a space: `  - NL`.
- Indentation is made with **spaces, never tabs**.
- `true` and `false` mean yes and no.

## Which countries count as Europe: `europe.yaml`

A list of two-letter country codes (ISO 3166-1, in capitals). To add a
country, add a line; to remove one, delete its line or put `#` in front.

```yaml
include:
  - NL  # Netherlands
  - TR  # Turkey
# - RU  # Russia: not included
```

Territories with their own code (Greenland `GL`, French Guiana `GF`) count
only if listed. Islands that share their country's code are included with
it: the Canary Islands with Spain, the Azores and Madeira with Portugal.

## Data versions and filters: `sources.yaml`

| Setting | What it does |
| --- | --- |
| `col: release_type` | `xr` (eXtended Release, the current choice) or `base`. |
| `col: version` | `latest`, or a release date such as `2026-10-16`. |
| `col: kingdoms` | Which kingdoms to include. Currently `Animalia`. |
| `col: exclude_extinct` | `true` leaves out fossil taxa. |
| `legacy: commit` | Which version of the earlier checklist to use. Leave as is. |
| `bold: snapshot` | `latest` (whatever file is in `data/bold/manual/`) or a date such as `2026-06-30`, which is then checked against the file. |
| `bold: markers` | Which markers count. Currently `COI-5P`. |
| `bold: min_length` | Minimum number of bases for a barcode-compliant sequence. Currently 500. |
| `gbif: ...` | Which GBIF records count as evidence. The explanations are in the file. |
| `evidence: min_sources` | How many sources must support a species. 1 means any one is enough. |

## Own barcodes: `own_barcodes.yaml`

The BOLD project codes (and, if wanted, institution names) whose barcodes
count as "own". Currently the BGE projects. To add a project:

```yaml
projects:
  - BGENL
  - BGENEW   # a new BGE project
```

## The target list: `target_list.yaml`

| Setting | What it does |
| --- | --- |
| `wanted: default` | The "Wanted" value every species gets: 0, 1 or 2. Currently 1. |
| `wanted: priority_groups` | Groups that get the `priority` value instead (see below). |
| `collected` | The "Collected" value for every species. Currently 0. |
| `include_xr_only` | `false` leaves out species that only the eXtended Release has. |

To make all beetles and bees "very wanted":

```yaml
wanted:
  default: 1
  priority: 2
  priority_groups:
    - order: Coleoptera
    - family: Apidae
```

## Name decisions: `curation.tsv`

Your decisions about names the pipeline could not match. See
[Reviewing names](reviewing-names.md).

## What to run again after a change

| You changed | Run again from section |
| --- | --- |
| `col` settings in `sources.yaml` | 1 (and then all later sections) |
| `europe.yaml` or the `gbif` settings | 2b, then 3 and 4 |
| `legacy` settings, or `curation.tsv` | 2a, then 2b, 3 and 4 |
| `bold` settings or `own_barcodes.yaml` | 3, then 4 |
| `evidence: min_sources` or `target_list.yaml` | 4 |

Section 1 starts a fresh run and clears earlier results, so after it every
later section must be run again.
