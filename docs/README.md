# Documentation

This pipeline builds the European DNA barcode gap list: which European animal
species have a public DNA barcode, and which do not yet. The results feed the
iBOL Europe target list website.

You do not need to program to run it. You open one notebook, run its
sections from top to bottom, and change settings in a few plain text files.

## For people running the pipeline

1. [Getting started](getting-started.md): opening the notebook and running it the first time.
2. [How it works](how-it-works.md): what each step does and where the data comes from.
3. [Changing the settings](settings.md): which countries count as Europe, which data versions to use, and so on.
4. [Reviewing names](reviewing-names.md): deciding about names the pipeline could not match on its own.
5. [Reading the results](results.md): what the output files and their columns mean.
6. [When something goes wrong](troubleshooting.md): every message the pipeline can show, and what to do.

Background: [source codes in the earlier checklist](legacy-source-codes.md).

## For developers

- [Developer guide](developer-guide.md): how the code is organised, how to test it, and how to add a source.
