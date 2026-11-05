# Getting started

The pipeline runs on your own computer: a Mac, a Windows PC or Linux. It
needs about **16 GB of memory** and **25 GB of free disk space** (the
downloads and results are large). A recent laptop is enough.

## What you need

- A free **GBIF account**, for step 2b. Register at https://www.gbif.org if you
  do not have one.
- A **BOLD account**, to download BOLD data for step 3. Register at
  https://boldsystems.org if you do not have one.
- Only if you will update the website (step 4b): the website's database
  details, from the target list administrator.

## One-time setup

This is the only part that uses the Terminal (on Windows: PowerShell). You
copy and paste three commands; after that, you start the pipeline with a
double-click.

### 1. Install pixi

pixi installs everything the pipeline needs, in exactly the right versions,
without touching the rest of your computer.

- **Mac**: open *Terminal* (in *Applications*, *Utilities*), paste this line
  and press Enter:

  ```
  curl -fsSL https://pixi.sh/install.sh | sh
  ```

- **Windows**: open *PowerShell*, paste this line and press Enter:

  ```
  powershell -ExecutionPolicy ByPass -c "irm -useb https://pixi.sh/install.ps1 | iex"
  ```

Then **close the Terminal (or PowerShell) window and open a new one**, so it
finds pixi.

### 2. Get the pipeline

Paste these two lines in the new window and press Enter:

```
cd ~
git clone https://github.com/bge-barcoding/european-gaplist.git
```

This makes a folder `european-gaplist` in your home folder. On a Mac, the
first time you use `git` you may be asked to install the "command line
developer tools": click *Install*, wait until it is done, and paste the lines
again. On Windows, if `git` is not found, install it from
https://git-scm.com/download/win first.

(Without `git`: on https://github.com/bge-barcoding/european-gaplist click
*Code*, *Download ZIP*, unpack it, and rename the folder to
`european-gaplist`. Updating is then harder; see below.)

### 3. Install the pipeline's software

```
cd ~/european-gaplist
pixi install
```

This takes a few minutes. When it finishes, the setup is done and you can
close the window.

## Before the first run

### Enter your GBIF account

In the `european-gaplist` folder there is a file called `.env.example`. Make
a copy of it called `.env` (with the dot, and nothing after `env`), open it
in a text editor (TextEdit on a Mac, Notepad on Windows) and fill in:

```
GBIF_USER=your GBIF user name
GBIF_PASSWORD=your GBIF password
GBIF_EMAIL=the e-mail address of your GBIF account
```

Save the file. It stays on your computer and is never uploaded anywhere.

Files whose names start with a dot are hidden. To see them in the Finder on a
Mac, press **Cmd + Shift + .** (full stop). In Windows Explorer, choose
*View*, *Show*, *Hidden items*. You can also open and edit `.env` in
JupyterLab (see below), which shows hidden files after *View*, *Show Hidden
Files*.

### Download a BOLD snapshot

BOLD publishes its public data as "data packages". They need a BOLD login,
so this step is done by hand:

1. Log in at BOLD and open the Data Packages page:
   https://v5.boldsystems.org/?p=21708
2. Download a snapshot, preferably in the **Parquet** version (smaller and
   much faster to read than TSV). The quarterly snapshots stay available for
   a year; use one of those if you want others to be able to repeat your run.
3. Move the downloaded file, as it is, into the folder `data/bold/manual/`
   inside `european-gaplist`. Do not unpack or rename it. Keep only one file
   in that folder.

## Running the pipeline

### Open the notebook

In the `european-gaplist` folder, double-click:

- **Mac**: `Start European gaplist.command`
- **Windows**: `Start European gaplist.bat`

A Terminal window opens, and a moment later the notebook opens in your web
browser. **Keep the Terminal window open while you work**; close it when you
are done. (If the Mac says the file cannot be opened because it is from an
unidentified developer, right-click it, choose *Open*, and confirm. This is
needed only once.)

### Run the sections

Run the sections of the notebook in order. To run a cell, click in it and
press **Shift + Enter**. While a cell runs, a `[*]` shows to its left and
the circle at the top right of the notebook is filled in: Python is busy.
Meanwhile the cell prints what it is doing, each line with the time, and
shows progress bars for long parts such as downloads:

```
08:53:36  Unpacking the names table. This is done only once per release.
Unpacking: 100%|██████████| 3.32G/3.32G [01:18<00:00, 45.2MB/s]
08:54:56  Reading the names table (about a minute for a full release)...
```

Some parts run for a minute or more without a progress bar; as long as the
`[*]` shows, the step is working. When it is done, a number replaces the
`[*]` and the result is printed below the progress lines.

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

You can stop between sections, close everything, and carry on another day.
The results are kept in the `data` folder and the next section picks them
up. While waiting for GBIF your computer can sleep or be switched off;
GBIF prepares the download on its own servers. During the longer steps
(1 and 3), keep the computer awake and plugged in.

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

## Getting a newer version of the pipeline

If you installed with `git`: open Terminal, and paste

```
cd ~/european-gaplist
git pull
pixi install
```

Your settings changes, your `.env`, your name decisions and the `data` folder
are kept. If `git pull` says your changes to a settings file would be
overwritten, ask the maintainer for help rather than forcing it.

If you downloaded a ZIP: download the new ZIP, and copy into it your `.env`,
your `config/curation.tsv`, any other settings you changed, and the `data`
folder (to avoid downloading everything again).
