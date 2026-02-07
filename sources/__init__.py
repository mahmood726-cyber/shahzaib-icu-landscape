"""
Adapter registry for enrichment sources.

Each adapter queries one external data source and stores results
into the enrichment SQLite database.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from sources.base_adapter import AdapterConfig, BaseAdapter
from sources.pubmed_adapter import PubMedAdapter
from sources.europmc_adapter import EuropePMCAdapter
from sources.openalex_adapter import OpenAlexAdapter
from sources.crossref_adapter import CrossrefAdapter
from sources.opencitations_adapter import OpenCitationsAdapter
from sources.unpaywall_adapter import UnpaywallAdapter
from sources.who_ictrp_adapter import WHOICTRPAdapter
from sources.openfda_adapter import OpenFDAAdapter

ADAPTERS: Dict[str, type] = {
    "pubmed": PubMedAdapter,
    "europmc": EuropePMCAdapter,
    "openalex": OpenAlexAdapter,
    "crossref": CrossrefAdapter,
    "opencitations": OpenCitationsAdapter,
    "unpaywall": UnpaywallAdapter,
    "who_ictrp": WHOICTRPAdapter,
    "openfda": OpenFDAAdapter,
}

# Dependency chain: sources that produce DOIs must run before sources
# that consume DOIs.  "phase_1" sources run first (NCT→PMIDs/DOIs),
# then "phase_2" sources use those DOIs.
SOURCE_PHASES: Dict[str, int] = {
    "pubmed": 1,
    "europmc": 1,
    "who_ictrp": 1,
    "openalex": 2,
    "crossref": 2,
    "opencitations": 2,
    "unpaywall": 2,
    "openfda": 1,  # queries drug names from trials table, not DOIs
}


DEFAULT_BASE_URLS: Dict[str, str] = {
    "pubmed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
    "europmc": "https://www.ebi.ac.uk/europepmc/webservices/rest",
    "openalex": "https://api.openalex.org",
    "crossref": "https://api.crossref.org",
    "opencitations": "https://opencitations.net/index/coci/api/v1",
    "unpaywall": "https://api.unpaywall.org/v2",
    "who_ictrp": "",
    "openfda": "https://api.fda.gov/drug/event.json",
}


def get_adapter(
    name: str,
    db_path: Path,
    config: Dict[str, Any],
    global_config: Dict[str, Any],
) -> BaseAdapter:
    """Create an adapter instance from config dict."""
    cls = ADAPTERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown adapter: {name}")

    source_cfg = config.get("sources", {}).get(name, {})
    email = source_cfg.get("email", "") or global_config.get("email", "")
    base_url = source_cfg.get("base_url", "") or DEFAULT_BASE_URLS.get(name, "")

    adapter_config = AdapterConfig(
        source_name=name,
        base_url=base_url,
        rate_limit=source_cfg.get("rate_limit", 3.0),
        retries=source_cfg.get("retries", 3),
        email=email,
        enabled=source_cfg.get("enabled", True),
        max_age_days=global_config.get("max_age_days", 30),
    )
    return cls(db_path, adapter_config)
