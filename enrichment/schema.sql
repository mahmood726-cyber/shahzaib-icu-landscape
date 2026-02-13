-- Enrichment database schema for the ICU Living Map pipeline.
-- All tables are additive; the existing CT.gov pipeline is unchanged.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Master NCT ID list (populated from studies CSV)
CREATE TABLE IF NOT EXISTS trials (
    nct_id TEXT PRIMARY KEY,
    brief_title TEXT,
    intervention_names TEXT,
    added_utc TEXT NOT NULL
);

-- Publications linked to trials (PubMed, Europe PMC)
CREATE TABLE IF NOT EXISTS publications (
    pub_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nct_id TEXT NOT NULL,
    pmid TEXT,
    pmcid TEXT,
    doi TEXT,
    title TEXT,
    journal TEXT,
    pub_date TEXT,
    pub_type TEXT,
    source TEXT NOT NULL,
    fetched_utc TEXT NOT NULL,
    CHECK(pmid IS NOT NULL OR doi IS NOT NULL OR pmcid IS NOT NULL),
    UNIQUE(nct_id, pmid),
    UNIQUE(nct_id, doi)
);

CREATE INDEX IF NOT EXISTS idx_pub_nct ON publications(nct_id);
CREATE INDEX IF NOT EXISTS idx_pub_doi ON publications(doi);

-- MeSH descriptors per PMID
CREATE TABLE IF NOT EXISTS mesh_terms (
    mesh_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmid TEXT NOT NULL,
    descriptor_ui TEXT,
    descriptor_name TEXT NOT NULL,
    qualifier_ui TEXT,
    qualifier_name TEXT,
    is_major_topic INTEGER DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'pubmed',
    fetched_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mesh_pmid ON mesh_terms(pmid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_mesh_unique
    ON mesh_terms(pmid, COALESCE(descriptor_ui, ''), COALESCE(qualifier_ui, ''));

-- Citation counts per DOI (OpenAlex, Crossref)
CREATE TABLE IF NOT EXISTS citations (
    citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doi TEXT NOT NULL,
    cited_by_count INTEGER,
    references_count INTEGER,
    source TEXT NOT NULL,
    fetched_utc TEXT NOT NULL,
    UNIQUE(doi, source)
);

CREATE INDEX IF NOT EXISTS idx_cit_doi ON citations(doi);

-- Individual citing→cited links (OpenCitations)
CREATE TABLE IF NOT EXISTS citation_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    citing_doi TEXT NOT NULL,
    cited_doi TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('incoming', 'outgoing')),
    source TEXT NOT NULL DEFAULT 'opencitations',
    fetched_utc TEXT NOT NULL,
    UNIQUE(citing_doi, cited_doi, direction)
);

CREATE INDEX IF NOT EXISTS idx_edge_cited ON citation_edges(cited_doi);

-- OA status per DOI (Unpaywall)
CREATE TABLE IF NOT EXISTS open_access (
    oa_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doi TEXT NOT NULL UNIQUE,
    is_oa INTEGER NOT NULL,
    oa_status TEXT,
    best_oa_url TEXT,
    license TEXT,
    source TEXT NOT NULL DEFAULT 'unpaywall',
    fetched_utc TEXT NOT NULL
);

-- Text-mined entities per PMID (Europe PMC annotations)
CREATE TABLE IF NOT EXISTS annotations (
    ann_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmid TEXT,
    pmcid TEXT,
    ann_type TEXT NOT NULL,
    ann_name TEXT NOT NULL,
    ann_uri TEXT,
    prefix TEXT,
    exact TEXT,
    suffix TEXT,
    source TEXT NOT NULL DEFAULT 'europmc',
    fetched_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ann_pmid ON annotations(pmid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ann_unique
    ON annotations(COALESCE(pmid, ''), COALESCE(pmcid, ''), ann_type, ann_name, COALESCE(exact, ''));


-- Adverse event counts by drug (openFDA FAERS)
CREATE TABLE IF NOT EXISTS faers_signals (
    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nct_id TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    reaction TEXT NOT NULL,
    serious_count INTEGER,
    total_count INTEGER,
    source TEXT NOT NULL DEFAULT 'openfda',
    fetched_utc TEXT NOT NULL,
    UNIQUE(nct_id, drug_name, reaction)
);

CREATE INDEX IF NOT EXISTS idx_faers_nct ON faers_signals(nct_id);

-- Per-NCT per-source fetch log (incremental tracking)
CREATE TABLE IF NOT EXISTS enrichment_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nct_id TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ok', 'empty', 'error', 'skipped')),
    records_found INTEGER DEFAULT 0,
    fetched_utc TEXT NOT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_elog_nct_src ON enrichment_log(nct_id, source);

-- Run-level metadata
CREATE TABLE IF NOT EXISTS enrichment_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_utc TEXT NOT NULL,
    finished_utc TEXT,
    sources_requested TEXT,
    nct_count INTEGER,
    status TEXT DEFAULT 'running',
    error_message TEXT
);

-- Content hashes for TruthCert
CREATE TABLE IF NOT EXISTS source_hashes (
    hash_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    content_key TEXT NOT NULL,
    hash_value TEXT NOT NULL,
    fetched_utc TEXT NOT NULL,
    UNIQUE(source, content_key)
);
