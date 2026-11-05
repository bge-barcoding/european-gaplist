# Put the BOLD data package here

Section 3 of the notebook counts barcodes in a snapshot of the public BOLD
database. BOLD only lets logged-in users download these snapshots, so you
download one by hand and put it in this folder.

## What to do

1. Log in at BOLD (https://boldsystems.org; registration is free) and open
   the Data Packages page: https://v5.boldsystems.org/?p=21708
2. Choose a snapshot and download it in the **Parquet** version if it is
   offered, otherwise in the TSV version.
   - A **quarterly** snapshot stays available for a year, so others can
     repeat your run. A weekly snapshot disappears after two weeks.
3. Move the downloaded file into this folder **as it is**: do not unpack it
   and do not rename it. The pipeline reads the snapshot's date from the
   file name (for example `BOLD_Public.30-Sep-2026`).
4. Run section 3 of the notebook.

## Good to know

- Keep **only one** snapshot here (this README does not count). To switch to
  a newer snapshot, delete the old file first.
- Accepted: a `.parquet` file, a `.tsv` or `.tsv.gz` file, or a `.zip`,
  `.tar.gz` or `.tgz` archive holding one of those. An archive is unpacked
  once, into `data/bold/unpacked/`; you can delete that folder afterwards
  to save space, but then it is unpacked again on the next run.
- Parquet is preferred: the download is smaller, and the pipeline can read
  just the columns it needs, which is much faster than reading the whole
  TSV (most of which is DNA sequences the pipeline does not use).
- If `config/sources.yaml` names a snapshot date (`bold: snapshot`), the
  file here must be from that date. With `snapshot: latest`, any snapshot
  is used.
- These files are large and are never uploaded to GitHub.
