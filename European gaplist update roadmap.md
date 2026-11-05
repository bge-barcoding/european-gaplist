# European gaplist update: roadmap

Nov 4, 2026 · @rvosa

## Summary

We will rebuild the European gaplist as a rerunnable pipeline: a Catalogue of Life (CoL) backbone, filtered to a configurable political Europe, with barcode status taken from public BOLD data packages. A non-technical user runs it from one Jupyter notebook and gets a seed file for the existing target list web app.

The current workflow has three weaknesses this addresses:

- **Incoherent topology.** The higher classification in gaplist-data was synthesised by hand from many checklists, so ranks and placements conflict. CoL replaces it wholesale.
- **Private inputs.** Barcode counts relied on BGE project sheets from inside the BOLD workbench. This iteration uses only public BCDM-TSV packages, so anyone can rerun it.
- **Not repeatable.** The steps are spread over three repositories, shell scripts and manual edits. The new pipeline pins every input by version and records where each species came from.

The old checklist is not discarded. Its species names, from national checklists, Fauna Europaea and other sources, become one of several lines of evidence that a species occurs in Europe, reconciled against CoL by name matching and synonymy.

## Decisions taken

These were agreed on 4 November 2026 and set the scope of the first release. Each one is a setting in the configuration file, so it can be revisited without code changes.

| Topic | Decision |
| --- | --- |
| Kingdoms | Animalia only. Other kingdoms can be switched on later in the configuration. |
| Barcode marker | COI-5P only. |
| Barcode quality | Barcode-compliant: COI-5P of at least 500 bp. |
| Where a barcode comes from | Specimens from anywhere count. A second count covers specimens collected in Europe. |
| Own versus other barcodes | "Own" is defined by a configurable list of BOLD project codes and institutions. |
| BOLD input | The full public BCDM-TSV snapshot, pinned by release date. |
| Backbone | Latest CoL base release (not the eXtended Release), pinned by version, matched offline from the ColDP download. |
| Evidence rule | One line of evidence is enough to include a species. Every source is kept per species, so the rule can be tightened later. |
| GBIF filters | At least one record with coordinates, not flagged as captive or cultivated, with a sound basis of record. Alien species are included and flagged. |
| Europe | A configuration file of ISO country codes (see Phase 0). |
| Run environment | One step-by-step notebook on a laptop (changed from a shared hub on 5 November 2026), opened with a double-click launcher. GBIF credentials sit in a local file that is never committed. |
| Web app | The seed TSV schema stays as it is for the first release. App changes are proposed separately. |
| Code | A new repository in the bge-barcoding organisation, reusing the relational model and loader code where it fits. |

## Target workflow

The workflow keeps the shape of the current one (collate, normalise, enrich, flatten, serve), but every input is public and versioned, and every step runs from one notebook.

&#91;embedded content: target workflow · 5 stages, inputs left, settings and outputs right\]

Public inputs enter on the left; the settings a user may edit, and the review loop, sit on the right. BOLD feeds stage 3 with barcodes and also returns its European specimen records to stage 2 as evidence of occurrence.

## Phase 0: foundations

Phase 0 sets up the repository, the configuration files and the run environment, so every later phase plugs into the same skeleton.

**Repository.** A new repository in the bge-barcoding organisation, provisionally `european-gaplist`, with a Python package, the notebook, the configuration folder and tests. Large inputs (CoL, BOLD, GBIF downloads) live in a data folder that is never committed; the pipeline downloads them itself.

**Storage.** A single DuckDB database file per run. DuckDB reads the BOLD snapshot (about 24 million records) and the CoL ColDP tables directly, which SQLite cannot do at this scale. The tables follow the model in ibol-europe-gaplist-app (taxon node, synonym, specimen, marker, barcode), with two additions: an `evidence` table (one row per species per source) and a `run` table recording the versions used.

**Configuration.** Four plain-text files that a non-technical user can edit, each with comments explaining every line:

- `europe.yaml`: the countries that count as Europe.
- `sources.yaml`: pinned versions of CoL, the BOLD snapshot date and the GBIF filters.
- `own_barcodes.yaml`: the BOLD project codes and institutions that count as "own".
- `curation.tsv`: manual decisions on names (see Phase 2), kept between runs.

**Environment.** A locked environment (pixi or conda-lock) so the notebook behaves the same everywhere, run on a laptop and opened with a double-click launcher (originally planned as a kernel on a shared JupyterHub; changed on 5 November 2026). GBIF credentials go in a local `.env` file excluded from Git.

**The Europe configuration** is a list of ISO 3166-1 country codes, as GBIF and BOLD (`country_iso`) both use them. Proposed starting point:

```yaml
# Countries whose records count as "European".
# Add or remove a two-letter ISO code to change the definition.
include:
  # EU member states
  - AT  # Austria
  - BE  # Belgium
  - BG  # Bulgaria
  - HR  # Croatia
  - CY  # Cyprus
  - CZ  # Czechia
  - DK  # Denmark
  - EE  # Estonia
  - FI  # Finland
  - AX  # Åland
  - FR  # France (metropolitan; overseas regions have their own codes)
  - DE  # Germany
  - GR  # Greece
  - HU  # Hungary
  - IE  # Ireland
  - IT  # Italy
  - LV  # Latvia
  - LT  # Lithuania
  - LU  # Luxembourg
  - MT  # Malta
  - NL  # Netherlands
  - PL  # Poland
  - PT  # Portugal (includes Azores and Madeira)
  - RO  # Romania
  - SK  # Slovakia
  - SI  # Slovenia
  - ES  # Spain (includes Canary Islands)
  - SE  # Sweden
  # Rest of Europe
  - AL  # Albania
  - AD  # Andorra
  - BY  # Belarus
  - BA  # Bosnia and Herzegovina
  - FO  # Faroe Islands
  - GI  # Gibraltar
  - GG  # Guernsey
  - IS  # Iceland
  - IM  # Isle of Man
  - JE  # Jersey
  - XK  # Kosovo
  - LI  # Liechtenstein
  - MD  # Moldova
  - MC  # Monaco
  - ME  # Montenegro
  - MK  # North Macedonia
  - NO  # Norway
  - SJ  # Svalbard and Jan Mayen (to confirm)
  - SM  # San Marino
  - RS  # Serbia
  - CH  # Switzerland
  - UA  # Ukraine
  - GB  # United Kingdom
  - VA  # Vatican City
  # Beyond geographic Europe
  - AM  # Armenia
  - GE  # Georgia
  - TR  # Turkey
# Not included: RU (Russia), AZ (Azerbaijan), KZ (Kazakhstan),
# GL (Greenland), and EU outermost regions such as GF, RE, GP, MQ, YT.
```

Because Macaronesia shares its country code with Spain and Portugal, it is included automatically. Marine records in a country's waters carry that country's code in GBIF, which covers the EEZ decision.

## Phase 1: CoL backbone

Phase 1 produces the complete animal classification from one pinned CoL base release, with its synonyms, before any European filtering.

1. Download the ColDP archive of the pinned [base release](https://www.catalogueoflife.org/data/download) from ChecklistBank and record its version and DOI in the `run` table. Monthly versions stay in ChecklistBank for at least a year, so a pinned version remains retrievable.
2. Load the `NameUsage` table, keep Animalia, and separate accepted names from synonyms. Synonyms point to their accepted name, which gives Phase 2 its synonymy checks for free.
3. Build the node table with parent links and nested-set (left/right) indices, as in the current model, so that subtrees can be queried quickly.
4. Keep every CoL rank in the database, but also derive the seven fixed ranks the web app shows (kingdom, phylum, class, order, family, genus, species). Intermediate ranks such as superfamily and tribe are kept, not shown.
5. Fold infraspecific taxa into their species, as the current export already does with subspecies.
6. Write a short report: species counts per phylum and class, and anything unusual (species without a family, for instance).

**Outcome:** a coherent classification of all animal species in CoL, with their synonyms, from which Europe is selected in Phase 2.

**Reuse:** the ORM concepts from ibol-europe-gaplist-app; the NSR-specific loaders are replaced.

## Phase 2: European occurrence and name reconciliation

Phase 2 decides which CoL species count as European, by resolving every name from every source to a CoL accepted name and recording which sources support it.

**Lines of evidence**

| Source | What it contributes | How it is obtained |
| --- | --- | --- |
| Legacy checklist | About 158,000 species and synonyms from national checklists, Fauna Europaea and other lists, with their original source codes (such as FE or SyDip) | Read from gaplist-data (`Gap_list_all_updated.csv`, `all_specs_and_syn.csv`) |
| GBIF | Species with at least one qualifying occurrence in a European country | One asynchronous GBIF download per run, filtered by the Europe configuration |
| BOLD | Species with at least one specimen collected in a European country | The `country_iso` field of the snapshot loaded in Phase 3 |
| CoL distributions (optional) | Distribution records some CoL sources provide | The `Distribution` table in the ColDP archive |

**GBIF download.** GBIF now uses the CoL eXtended Release (XR) as its primary taxonomy, and its download API accepts a `checklistKey` that returns CoL identifiers ([GBIF data blog](https://data-blog.gbif.org/post/catalogue-of-life-taxonomic-backbone/)). We request one `SPECIES_LIST` download with these filters: country in the Europe list, kingdom Animalia, coordinates present, occurrence status present, and no captive or cultivated records. A second, smaller download of records marked as introduced or invasive supplies the alien flag. CoL identifiers for taxa that are also in the base release map across directly; XR-only taxa go through name matching like any other source.

**Name resolution.** Every name from every source goes through the same steps, and each name gets an outcome code that ends up in the report:

1. Parse the name into its canonical form (for example with gnparser), so authorship, spacing and stray characters do not block a match.
2. Exact match to a CoL accepted name: accept.
3. Exact match to a CoL synonym: resolve to its accepted name and record the synonym used.
4. More than one candidate (homonyms, or a synonym pointing to several names): choose the one whose family or order agrees with the source; otherwise send to review.
5. Near match (gender endings such as -us/-a, single-letter typos): never accepted automatically; listed for review with the suggested name.
6. No match: listed as unresolved, with the source it came from.

**Curation that persists.** Review lists are written as spreadsheets. A curator records a decision (accept the suggestion, map to another name, or reject) in `curation.tsv`, and every later run applies those decisions before matching. Work done once is never lost on a rerun.

**Selection rule.** A CoL species is in the European list when at least one source supports it. Its record keeps every supporting source, so a stricter rule (two sources, or GBIF required) is a single setting later.

**Reuse:** the gender-variant and duplicate handling in the gaplist-data cleaning pipeline carries over to step 5.

## Phase 3: barcode status from BOLD

Phase 3 counts, for each European species, how many public barcode-compliant COI-5P sequences exist, using one pinned BOLD snapshot.

**Input.** BOLD publishes the public reference library as [data packages](https://v5.boldsystems.org/?p=21708) in BCDM format, as TSV with FASTA and JSON metadata, and now also as Parquet. The two latest weekly snapshots and quarterly snapshots from the past year are offered. We pin a snapshot date in `sources.yaml` and keep a local copy, because a weekly snapshot disappears from the page after two weeks.

**Steps**

1. Load the snapshot into DuckDB, keeping only the columns we need: `processid`, `sampleid`, `inst`, `bin_uri`, the taxonomy columns down to `species`, `identification_rank`, `country_iso`, `marker_code`, `nuc_basecount` and `bold_recordset_code_arr`.
2. Keep Animalia records with `marker_code` = COI-5P. Records identified only to genus or higher do not count towards a species.
3. Resolve BOLD species names to CoL with the Phase 2 resolver, so a barcode filed under a synonym still counts for the accepted species.
4. Mark each sequence as barcode-compliant when `nuc_basecount` is at least 500.
5. Mark each record as "own" when one of its project or dataset codes (`bold_recordset_code_arr`) or its institution (`inst`) is listed in `own_barcodes.yaml`.
6. Aggregate per species.

**Counts per species**

| Count | Definition |
| --- | --- |
| Compliant barcodes | COI-5P sequences of at least 500 bp, collected anywhere |
| European barcodes | The same, from specimens with a European `country_iso` |
| Own barcodes | Compliant barcodes from listed projects or institutions |
| Other barcodes | Compliant barcodes minus own barcodes |
| BINs | Distinct `bin_uri` values among compliant barcodes |

A species with zero compliant barcodes is a gap.

**Reuse:** the specimen and barcode loaders in ibol-europe-gaplist-app, rewritten to read BCDM columns instead of the old workbench exports.

## Phase 4: flatten and deploy to the web app

Phase 4 writes one row per European species in the existing seed TSV layout and loads it into the target list database, without changes to the C# application.

**Column mapping**

| Seed column | Filled from |
| --- | --- |
| Kingdom to Species | The seven fixed ranks derived in Phase 1 |
| SpeciesLocality | The supporting sources, such as `GBIF;BOLD;FE` |
| SpeciesOccurrenceStatus | `gap` when there are no compliant barcodes, otherwise empty, as now |
| Collected | 0 in the first release (no public source; see open points) |
| Wanted | 1 for every species in the first release (see open points) |
| OwnBarcodes | Own barcodes from Phase 3 |
| OtherBarcodes | Other barcodes from Phase 3 |

**Checks before export.** The exporter refuses to write the file if a check fails, and says why in plain language: every row has all seven ranks, no species appears twice, counts are whole numbers, and the column order matches the app's template.

**Deployment.** The app only reads `seed-template.tsv` in development mode, when the table is empty. In production the data sits directly in the Postgres `targetlist` table. The notebook therefore offers a last step that replaces the table contents in one transaction (empty it and load the new rows), so the live site is never half updated. The app picks up the new data at its next cache refresh or restart. This step needs database credentials and is kept separate from the rest, so most users can run everything up to the export without touching production.

**Also written:** a run summary (versions, counts, number of gaps per class) and the full species table with all evidence columns, for people who want more than the app shows.

## Phase 5: notebook and documentation for non-technical users

Phase 5 makes the whole pipeline runnable by someone who does not program: one notebook, run from top to bottom, with every decision in a configuration file and every result explained in words.

**The notebook.** All logic lives in the Python package; the notebook only calls it, so users never edit code. It has one section per phase, and each section has:

- a short paragraph saying what the step does and how long it usually takes;
- one cell to run;
- a plain summary of the result ("1,234 names need review; see `review/names.xlsx`") and a green, amber or red status line.

Steps that take long or wait on others (the GBIF download, the BOLD snapshot) save their progress. If the notebook or the laptop is closed, running it again resumes where it stopped instead of starting over.

**Review loop.** When names need review, the notebook stops at that point and says so. The curator opens the review spreadsheet, records decisions in `curation.tsv`, and reruns from that section. A run can also be completed with unresolved names left out; they are then listed in the summary.

**Documentation.** Written for a biologist, not a developer, and published with the repository:

- *Getting started*: the one-time laptop setup, opening the notebook, running it for the first time.
- *What the pipeline does*: the five stages, with the diagram from this roadmap.
- *Changing the settings*: editing the Europe list, the "own" projects and the source versions, with examples.
- *Reviewing names*: how to read a review list and record a decision, with worked examples of a synonym, a homonym and a misspelling.
- *Reading the results*: what each output file and column means.
- *When something goes wrong*: the status messages and what to do about each.

A separate developer guide covers the package layout, tests and how to add a new evidence source.

**Acceptance test.** Before release, a colleague who has not seen the code runs the notebook end to end from the documentation alone. Each place where they get stuck becomes a fix.

## Milestones and effort

A first release takes about 13 weeks of one developer's time, with the notebook and documentation built alongside the European list, barcodes and export.

&#91;embedded content: roadmap · 6 phases, 5 gates\]

Each diamond is a gate: the next phase starts only when its condition is met. The gate after Phase 2 is the important one, because the base-versus-XR decision is taken there, with numbers in hand. These are estimates; the size of the name review is the largest unknown and is measured at that gate.

## Risks and open points

The main risk is that the CoL base release lacks species that our evidence supports. GBIF now runs on the eXtended Release, so this should be measured early rather than assumed.

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Base release gaps | European species with good evidence have no base release name, especially in poorly covered insect groups | Phase 2 reports how many names match only the XR. If the share is material, switch to the XR, which is one setting. |
| Identifier mapping between XR and base release | GBIF results cannot be joined to the backbone by identifier | Largely settled: CoL aims to keep one identifier per name across all releases, base and XR. Phase 2 counts GBIF keys that do not join and sends them through name matching. |
| BOLD snapshot access | Weekly snapshots drop off the download page after two weeks; downloads may need a BOLD login | Keep a local copy of each pinned snapshot; ask BOLD support for a permanent link, which they offer to data partners. |
| Run time and disk space | The BOLD snapshot (about 24 million records) and GBIF downloads are large; a GBIF download can take hours | Measured: peak memory 5 to 6 GB, about 25 GB of disk; a laptop with 16 GB of memory is enough. Resumable steps in the notebook. |
| Review workload | The legacy list holds about 158,000 names; even a small unresolved share means thousands to review | Prioritise by group; allow a run to complete with unresolved names left out and listed. |
| False positives from GBIF | One misidentified or out-of-range record puts a species on the list | Keep all evidence per species; report species supported only by a single GBIF record; a stricter rule is one setting. |
| Undocumented legacy source codes | Codes such as SyDip cannot be explained to users | Compile a code list from gaplist-data and ask the original curators to complete it. |

**Open points to settle before Phase 4**

- [ ] What fills **Collected**, now that there are no private project sheets? Options: leave at 0, count public European specimens without a compliant barcode, or drop the column in a later app release.
- [ ] What sets **Wanted** (0, 1 or 2)? Options: everything 1, or 2 for gaps in priority groups listed in a configuration file.
- [ ] Which BOLD project and dataset codes and institutions count as **own**?
- [ ] Is **Svalbard and Jan Mayen** (SJ) in or out?
- [x] Which **hub** hosts the notebook? None: it runs on a laptop (decided 5 November 2026).
- [ ] How often do we **rerun**? Aligning with BOLD's quarterly snapshots seems natural.

## Sources

- [bge-barcoding/gaplist-data](https://github.com/bge-barcoding/gaplist-data), [ibol-europe-gaplist-app](https://github.com/bge-barcoding/ibol-europe-gaplist-app) and [bge-targetlist](https://github.com/bge-barcoding/bge-targetlist)
- [BCDM field definitions](https://github.com/boldsystems-central/BCDM/blob/main/field_definitions.tsv)
- [BOLD data packages](https://v5.boldsystems.org/?p=21708)
- [Catalogue of Life downloads](https://www.catalogueoflife.org/data/download) and [base and extended releases](https://catalogueoflife.org/building/releases)
- [GBIF API downloads](https://techdocs.gbif.org/en/data-use/api-downloads) and [download formats](https://techdocs.gbif.org/en/data-use/download-formats)
- [GBIF taxonomy interpretation](https://techdocs.gbif.org/en/data-processing/taxonomy-interpretation) and [migration to CoL XR](https://data-blog.gbif.org/post/catalogue-of-life-taxonomic-backbone/)
