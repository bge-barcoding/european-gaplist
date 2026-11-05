# When something goes wrong

Every result in the notebook starts with **[OK]**, **[WAITING]** or
**[PROBLEM]**. A problem message always says what went wrong and what to do.
This page lists the messages by section, with more explanation. If a step
fails half-way, nothing is lost: the previous results are kept, and you can
simply run the cell again.

## Any section: "Please fix the following in the config folder"

One or more settings files contain mistakes. All mistakes are listed at
once, each with the file name. Common ones:

| Message contains | What to do |
| --- | --- |
| `... cannot be read near line N` | A formatting mistake in that file. Check that list items start with two spaces, a dash and a space, and that you used spaces, not tabs. |
| `'xx' is not a two-letter country code in capitals` | Write country codes in capitals, e.g. `NL`. |
| `... is listed twice` | Remove one of the two lines. |
| `... is missing. Restore it from GitHub.` | A settings file was deleted or renamed. Get it back from the repository. |
| `curation.tsv: the first row must be exactly these column names` | The file was saved in the wrong format. Save it again as tab-separated text, keeping the header row. |
| `curation.tsv, row N: decision ... must be accept, map or reject` | Fix the word in that row. |
| `a 'map' decision needs a target_name` | Fill in the CoL name to map to, or change the decision. |

See [Changing the settings](settings.md) for how the files work.

## Section 1: classification

| Message | What to do |
| --- | --- |
| `ChecklistBank could not be reached` | The Catalogue of Life server could not be reached. Try again later. Or download the ColDP file by hand from https://www.catalogueoflife.org/data/download and put it in `data/col/manual/`. |
| `No ColDP download was found for the ... release` | The version in `sources.yaml` does not exist. Check the date, or set `version: latest`. |
| `There is more than one zip file in data/col/manual/` | Keep only the release you want to use in that folder. |
| `... has no NameUsage.tsv` | The file in `data/col/manual/` is not a ColDP download. Download the **ColDP** version, not DwC-A or TextTree. |
| `kingdom 'X' does not occur in this Catalogue of Life release` | Check the spelling of the kingdom in `sources.yaml`. |
| Warning: `this release file has no extinct flags` | The file is the simple ColDP version, so fossils could not be left out. Prefer the automatic download, which uses the extended version. |

## Section 2a: earlier checklist

| Message | What to do |
| --- | --- |
| `There is no backbone yet. Run section 1 first.` | Run section 1, then this one. |
| `Could not download ... from GitHub` | Try again later, or put the two files from the gaplist-data repository in `data/legacy/manual/`. |

## Section 2b: GBIF

| Message | What to do |
| --- | --- |
| `A GBIF account is needed` | Fill in your GBIF details in the `.env` file; see [Getting started](getting-started.md). |
| `GBIF did not accept the user name and password` | Check `GBIF_USER` and `GBIF_PASSWORD` in `.env`. Log in at gbif.org to make sure they work. |
| **[WAITING]** `GBIF is preparing the download(s)` | Normal. Run the cell again later, from minutes to a few hours. It picks up the same downloads. |
| `GBIF could not prepare download ...` | GBIF's preparation failed. Run the cell again to ask for a new download. |
| `GBIF refused the download request: ...` | GBIF did not accept the request. The text after the colon is GBIF's own explanation. If it mentions a setting, check the `gbif` part of `sources.yaml`; otherwise ask the maintainer. |
| `GBIF could not be reached` | Try again later. |

## Section 3: BOLD

| Message | What to do |
| --- | --- |
| `No BOLD snapshot found` | Download a BOLD data package and put it in `data/bold/manual/`; see [Getting started](getting-started.md). |
| `There is more than one file in data/bold/manual/` | Keep only the snapshot you want to use. |
| `sources.yaml asks for the BOLD snapshot of ..., but the file ... is from ...` | Replace the file with the snapshot of that date, or change `bold: snapshot` in `sources.yaml` (or set it to `latest`). |
| `... should hold exactly one TSV or Parquet file` | The downloaded archive has an unexpected layout. Download the TSV or Parquet package again. |
| `... lacks the BCDM column(s)` | The file is not a BOLD data package in BCDM format. Download it from the Data Packages page. |
| `The BOLD file could not be read` | The file may be incomplete. Download it again. |

## Section 4: target list

| Message | What to do |
| --- | --- |
| `There is no evidence yet` | Run the sections of step 2 first. |
| `The target list was not written, because: ...` | A safety check found a fault in the list. This should not happen; report it to the maintainer with the message. |
| Note: `Not used in this run: BOLD barcodes and GBIF records` | The list was written without these sources. Run sections 2b and 3 to include them; until then every species shows as a gap. |
| Note: `N species have no family in Catalogue of Life` | Not a fault: CoL gives no name at that rank for those species. The cell is left empty. |

## Section 4b: website

| Message | What to do |
| --- | --- |
| `To update the website, fill in ... in the .env file` | Ask the target list administrator for the database details. |
| `The database has no table "Targetlist"` | The details in `.env` point to the wrong database. |
| `The "Targetlist" table lacks the column(s) ...` | The website has changed. Nothing was written. Ask the maintainer. |
| `The database reported a problem, and nothing was changed` | The website keeps its current list. Try again later, or report the message to the maintainer. |

## Still stuck?

Open an issue at https://github.com/bge-barcoding/european-gaplist/issues
with the full message, the section, and what you changed before it happened.
