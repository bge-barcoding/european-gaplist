# Settings

These four files hold every choice the pipeline makes. You can change them
with any text editor, or directly on GitHub. You never need to change code.

| File | What it decides |
| --- | --- |
| `europe.yaml` | Which countries count as Europe. |
| `sources.yaml` | Which versions of Catalogue of Life, BOLD and GBIF to use, and how to filter them. |
| `own_barcodes.yaml` | Which BOLD projects and institutions count as "own" barcodes. |
| `curation.tsv` | Your decisions about names the pipeline could not match on its own. |

Each `.yaml` file explains itself in the lines starting with `#`.

## curation.tsv

This is a table (open it in Excel or LibreOffice, and save it again as
tab-separated text). When the pipeline cannot be sure which Catalogue of
Life name a source name belongs to, it lists the name for review. You record
your decision here, one row per name, and every later run applies it.

| Column | What to fill in |
| --- | --- |
| `source` | Where the name came from, as shown in the review list (for example `legacy`, `gbif`, `bold`). |
| `original_name` | The name exactly as shown in the review list. |
| `decision` | `accept` (use the suggested name), `map` (use the name in `target_name`) or `reject` (leave this name out). |
| `target_name` | Only for `map`: the Catalogue of Life name to use instead. |
| `curator` | Your name or initials. |
| `date` | The date of your decision, as YYYY-MM-DD. |
| `note` | Optional: why you decided this. |

After you change any of these files, run the notebook's first section
again. It checks the settings and tells you in plain words if something is
wrong.
