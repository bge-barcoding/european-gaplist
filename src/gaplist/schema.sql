-- Database layout for one pipeline run (DuckDB).
--
-- Follows the model of ibol-europe-gaplist-app (taxon node, synonym,
-- specimen, marker, barcode), with CoL identifiers as keys, plus tables
-- for runs, evidence of European occurrence and name resolution.

-- One row per run: which versions and settings produced the results.
CREATE TABLE IF NOT EXISTS run (
    run_id              INTEGER PRIMARY KEY,
    started_at          TIMESTAMP NOT NULL DEFAULT current_timestamp,
    finished_at         TIMESTAMP,
    package_version     VARCHAR NOT NULL,
    settings_fingerprint VARCHAR NOT NULL,
    col_release_type    VARCHAR,
    col_version         VARCHAR,   -- the resolved release date, never 'latest'
    col_doi             VARCHAR,
    bold_snapshot       VARCHAR,   -- the resolved snapshot date
    gbif_download_key   VARCHAR,
    gbif_download_doi   VARCHAR,
    notes               VARCHAR
);

-- The CoL classification: accepted taxa at every rank (Phase 1).
-- lft/rgt are nested-set indices for fast subtree queries.
CREATE TABLE IF NOT EXISTS taxon (
    taxon_id    VARCHAR PRIMARY KEY,   -- CoL identifier
    parent_id   VARCHAR,
    rank        VARCHAR NOT NULL,
    name        VARCHAR NOT NULL,      -- canonical name, no authorship
    authorship  VARCHAR,
    lft         INTEGER,
    rgt         INTEGER,
    -- the seven ranks the web app shows, filled for species
    kingdom     VARCHAR,
    phylum      VARCHAR,
    class       VARCHAR,
    "order"     VARCHAR,
    family      VARCHAR,
    genus       VARCHAR,
    species     VARCHAR,
    -- for species and infraspecific taxa: the species they belong to,
    -- so that subspecies are counted with their species
    species_id  VARCHAR
);

-- Added in Phase 1; keeps databases made by earlier versions usable.
ALTER TABLE taxon ADD COLUMN IF NOT EXISTS species_id VARCHAR;
-- Added in Phase 2.
ALTER TABLE run ADD COLUMN IF NOT EXISTS legacy_commit VARCHAR;
ALTER TABLE run ADD COLUMN IF NOT EXISTS gbif_alien_download_key VARCHAR;
-- True for taxa the CoL eXtended Release adds to the expert-curated base release.
ALTER TABLE taxon ADD COLUMN IF NOT EXISTS xr_added BOOLEAN;

-- CoL synonyms, each pointing to its accepted taxon (Phase 1).
CREATE TABLE IF NOT EXISTS synonym (
    synonym_id  VARCHAR PRIMARY KEY,   -- CoL identifier of the synonym
    name        VARCHAR NOT NULL,
    authorship  VARCHAR,
    status      VARCHAR,               -- e.g. synonym, ambiguous synonym, misapplied
    accepted_id VARCHAR NOT NULL       -- taxon.taxon_id
);

-- How each name from each source was matched to CoL (Phase 2 and 3).
CREATE TABLE IF NOT EXISTS name_resolution (
    source          VARCHAR NOT NULL,  -- legacy, gbif, bold, ...
    original_name   VARCHAR NOT NULL,
    canonical_name  VARCHAR,
    outcome         VARCHAR NOT NULL,  -- exact, synonym, disambiguated, review, curated, unmatched, rejected
    taxon_id        VARCHAR,           -- accepted CoL taxon, when resolved
    via_synonym_id  VARCHAR,           -- the synonym used, if any
    candidates      VARCHAR[],         -- for review: possible CoL ids
    note            VARCHAR,
    PRIMARY KEY (source, original_name)
);

-- Evidence that a species occurs in Europe: one row per species per source (Phase 2).
CREATE TABLE IF NOT EXISTS evidence (
    taxon_id        VARCHAR NOT NULL,
    source          VARCHAR NOT NULL,  -- legacy, gbif, bold, col_distribution
    source_detail   VARCHAR,           -- e.g. the legacy source codes (FE, SyDip)
    record_count    INTEGER,
    possibly_alien  BOOLEAN DEFAULT false,
    PRIMARY KEY (taxon_id, source)
);

-- Markers (Phase 3).
CREATE TABLE IF NOT EXISTS marker (
    marker_code VARCHAR PRIMARY KEY    -- e.g. COI-5P
);

-- Public BOLD specimens resolved to CoL (Phase 3).
CREATE TABLE IF NOT EXISTS specimen (
    processid           VARCHAR PRIMARY KEY,
    sampleid            VARCHAR,
    inst                VARCHAR,
    country_iso         VARCHAR,
    bold_species        VARCHAR,       -- the name as given in BOLD
    identification_rank VARCHAR,
    taxon_id            VARCHAR,       -- accepted CoL taxon, when resolved
    bin_uri             VARCHAR,
    recordsets          VARCHAR[],     -- bold_recordset_code_arr
    is_european         BOOLEAN,
    is_own              BOOLEAN
);

-- Sequences per specimen and marker (Phase 3).
CREATE TABLE IF NOT EXISTS barcode (
    processid       VARCHAR NOT NULL,
    marker_code     VARCHAR NOT NULL,
    nuc_basecount   INTEGER,
    is_compliant    BOOLEAN,           -- meets the marker and length rules
    PRIMARY KEY (processid, marker_code)
);

-- Barcode status per backbone species (Phase 3).
CREATE TABLE IF NOT EXISTS barcode_status (
    taxon_id            VARCHAR PRIMARY KEY,  -- backbone species
    specimens           INTEGER,  -- public BOLD specimens identified as this species
    compliant           INTEGER,  -- barcode-compliant sequences, collected anywhere
    european_compliant  INTEGER,  -- the same, from specimens collected in Europe
    own                 INTEGER,  -- compliant, from projects or institutions in own_barcodes.yaml
    other               INTEGER,  -- compliant minus own
    bins                INTEGER   -- distinct BINs among compliant sequences
);
