# Catalogue of Life release, by hand (usually not needed)

Normally section 1 of the notebook downloads the Catalogue of Life release
by itself, and you can leave this folder empty.

Only if that download does not work (for example when ChecklistBank cannot
be reached):

1. Go to https://www.catalogueoflife.org/data/download
2. Download the release named in `config/sources.yaml` (currently the
   **eXtended Release**), in the **ColDP** format. If there is a choice,
   take the "extended" ColDP version: only that one marks fossils, so they
   can be left out.
3. Put the zip file in this folder as it is, and run section 1 again.

Keep only one zip file here. While a file is here, it is always used instead
of the automatic download; delete it to go back to automatic downloads.
