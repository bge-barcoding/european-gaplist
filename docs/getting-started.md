# Getting started

## What you need

- Access to the shared Jupyter hub where the pipeline is installed. Your IT
  department or the pipeline's maintainer gives you the address and a login.
- A free **GBIF account**, for step 2b. Register at https://www.gbif.org if you
  do not have one.
- A **BOLD account**, to download BOLD data for step 3. Register at
  https://boldsystems.org if you do not have one.
- Only if you will update the website (step 4b): the website's database
  details, from the target list administrator.

## Before the first run

### 1. Open the notebook

Log in to the hub, open the folder `european-gaplist`, then the folder
`notebooks`, and double-click `gaplist.ipynb`. Check at the top right that the
kernel says **European gaplist**. If it says something else, choose
*Kernel*, *Change kernel*, *European gaplist*.

### 2. Enter your GBIF account

In the main `european-gaplist` folder there is a file called `.env.example`.
Make a copy of it called `.env` (with the dot, and nothing after `env`),
open it and fill in:

```
GBIF_USER=your GBIF user name
GBIF_PASSWORD=your GBIF password
GBIF_EMAIL=the e-mail address of your GBIF account
```

Save the file. It stays on the hub and is never uploaded anywhere.

Files whose names start with a dot are hidden by default. In Jupyter, choose
*View*, *Show Hidden Files* to see them.

### 3. Download a BOLD snapshot

BOLD publishes its public data as "data packages". They need a BOLD login,
so this step is done by hand:

1. Log in at BOLD and open the Data Packages page:
   https://v5.boldsystems.org/?p=21708
2. Download a snapshot, in the TSV or the Parquet version. The quarterly
   snapshots stay available for a year; use one of those if you want others
   to be able to repeat your run.
3. Upload the downloaded file, as it is, into the folder `data/bold/manual/`
   in `european-gaplist`. Do not unpack or rename it. Keep only one file in
   that folder.

## Running the pipeline

Run the sections of the notebook in order. To run a cell, click in it and
press **Shift + Enter**. While a cell runs, a `[*]` shows to its left; when it
is done, a number appears and the result is printed below the cell.

Every result starts with one of these:

- **[OK]**: the step worked. Read the few lines below it.
- **[WAITING]**: the step is waiting for someone else (only GBIF, step 2b).
  Run the same cell again later.
- **[PROBLEM]**: the step did not work. The message says why and what to do.
  See also [When something goes wrong](troubleshooting.md).

| Section | What it does | Usual time |
| --- | --- | --- |
| 0 | Checks the settings | Seconds |
| 1 | Builds the Catalogue of Life classification | About 3 minutes, plus the download the first time (about 1.4 GB) |
| 2a | Matches the earlier European checklist | About 1 minute |
| 2b | Asks GBIF which species occur in Europe | The first time: asks GBIF and says **[WAITING]**. Run it again after an hour or so. |
| 3 | Counts barcodes in the BOLD snapshot | 5 to 15 minutes |
| 4 | Writes the target list | Under a minute |
| 4b | Updates the website | Only when you choose to; see below |

You can close the notebook between sections. The results are kept on the hub
and the next section picks them up.

## Updating the website

Section 4b first only **checks**: it connects to the website's database and
says how many species the website lists now and how many it would list after
the update. Nothing changes.

To really update the website, change `confirm=False` to `confirm=True` in
that cell and run it again. The update is all or nothing: if anything goes
wrong, the website keeps its current list. The website shows the new list
after its next refresh, within a few hours.

## Afterwards

- Look at the review lists in `data/review/` and decide about the names
  there; see [Reviewing names](reviewing-names.md). Your decisions are kept
  for all later runs.
- Read `data/output/summary.md`. It lists the data versions used, with the
  DOIs to cite when the gap list is published or shared.
