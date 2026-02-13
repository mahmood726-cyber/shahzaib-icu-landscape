#!/usr/bin/env python3
"""
Search PubMed for published ICU RCTs with hemodynamic outcomes
that may lack CT.gov registration.

Uses E-utilities esearch + efetch to find articles, extracting NCT IDs
from DataBankList for deduplication with CT.gov results.

Output: two CSVs matching the CT.gov schema for multi-source merge.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "ctgov_icu_placebo_strategy.json"
OUTPUT_DIR = ROOT / "output"

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RATE_LIMIT = 0.34  # Max 3 req/sec for NCBI polite pool
DEFAULT_MAX_PMIDS = 10000
DEFAULT_EFETCH_BATCH = 200


def _csv_safe(value: str) -> str:
    if not value:
        return value
    needs_prefix = value[0] in ("=", "+", "@", "\t", "\r")
    if not needs_prefix:
        for prefix in ("\n=", "\n+", "\n@", "\r=", "\r+", "\r@"):
            if prefix in value:
                needs_prefix = True
                break
    return "'" + value if needs_prefix else value


def _normalize_quotes(s: str) -> str:
    return s.replace("\u2018", "'").replace("\u2019", "'").replace("\u2032", "'")


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# Negative-context patterns (shared with fetch_ctgov_icu_placebo.py & build_living_map.py)
_ABBREVIATION_NEGATIVE_CONTEXT = {
    "hr": re.compile(
        r"(?:"
        r"hazard\s+ratio"
        r"|adjusted\s+hr\b"
        r"|\bahr\b"
        r"|\bchr\b"
        r"|\bcshr\b"
        r"|\bshr\b"
        r"|\bcox\s+hr\b"
        r"|sub-?distribution\s+hazard"
        r"|cause-specific\s+hazard"
        r"|proportional\s+hazards?\s+.{0,80}\bhr\b"
        r"|\bhr\s*[=:]\s*\d+\.\d"
        r"|\bhr\s+\d+\.\d"
        r"|\bhr\s*\(\s*95\s*%"
        r"|\bhr\s*\[\s*95\s*%"
        r"|\bhr\s*;?\s*95\s*%\s*ci"
        r"|\bhr\s+\d\.\d+\s*[,;(]"
        r")",
        re.IGNORECASE,
    ),
    "sv": re.compile(r"\bsv40\b", re.IGNORECASE),
    "pap": re.compile(r"\bpap\s+(?:smear|test)\b", re.IGNORECASE),
    "map": re.compile(
        r"(?:map\s*(?:kinase|pathway)|mapk|\bmitogen[-\s]activated\s+protein)",
        re.IGNORECASE,
    ),
    "ef": re.compile(
        r"(?:elongation\s+factor|enhancement\s+factor)",
        re.IGNORECASE,
    ),
    "perfusion": re.compile(
        r"(?:cerebral\s+perfusion(?!\s+pressure)"
        r"|myocardial\s+perfusion"
        r"|perfusion\s+(?:scan|imaging|study|scintigraphy))",
        re.IGNORECASE,
    ),
}


def keyword_in_text(keyword: str, text: str) -> bool:
    if not keyword or not text:
        return False
    k = _normalize_quotes(keyword).lower()
    t = _normalize_quotes(text).lower()
    neg_re = _ABBREVIATION_NEGATIVE_CONTEXT.get(k)
    if neg_re and neg_re.search(t):
        return False
    if len(k) <= 3:
        parts = t.replace("/", " ").replace("(", " ").replace(")", " ").replace("-", " ").replace(",", " ").replace(";", " ").replace("[", " ").replace("]", " ").split()
        return any(part == k for part in parts)
    return re.search(r"\b" + re.escape(k) + r"\b", t) is not None


def _eutils_get(
    endpoint: str,
    params: Dict[str, str],
    timeout: int = 30,
    retries: int = 3,
    backoff: float = 2.0,
) -> bytes:
    """Make a polite E-utilities GET request with retries."""
    url = f"{EUTILS_BASE}/{endpoint}?{urlencode(params)}"
    req = Request(url, headers={
        "User-Agent": "ICU-Living-Map/1.0 (research; OA-only)",
    })
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        time.sleep(RATE_LIMIT)
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as exc:
            last_error = exc
            if exc.code in (429, 500, 502, 503, 504):
                time.sleep(backoff * (attempt + 1))
                continue
            raise
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(backoff * (attempt + 1))
    raise last_error or RuntimeError(f"E-utilities request failed: {url}")


def _build_pubmed_query(config: Dict[str, Any]) -> str:
    """Build PubMed search query for ICU RCTs with hemodynamic outcomes."""
    # ICU terms
    icu_terms = [
        '"intensive care"', '"critical care"', '"ICU"',
        '"septic shock"', '"sepsis"', '"vasopressor"',
        '"mechanical ventilation"', '"respiratory failure"',
        '"cardiogenic shock"', '"hemorrhagic shock"',
        '"ARDS"', '"ECMO"', '"organ dysfunction"',
    ]
    icu_group = " OR ".join(icu_terms)

    # Hemodynamic terms
    hemo_terms = [
        '"hemodynamic"', '"blood pressure"', '"cardiac output"',
        '"stroke volume"', '"central venous pressure"',
        '"mean arterial pressure"', '"vasopressor"',
        '"heart rate"', '"lactate"', '"ejection fraction"',
        '"pulmonary artery pressure"', '"systemic vascular resistance"',
    ]
    hemo_group = " OR ".join(hemo_terms)

    return f"({icu_group}) AND ({hemo_group}) AND Randomized Controlled Trial[pt]"


def esearch(
    query: str,
    retmax: int = DEFAULT_MAX_PMIDS,
    updated_since: Optional[str] = None,
) -> List[str]:
    """Search PubMed and return list of PMIDs."""
    params: Dict[str, str] = {
        "db": "pubmed",
        "term": query,
        "retmax": str(retmax),
        "retmode": "json",
        "usehistory": "n",
    }
    if updated_since:
        params["mindate"] = updated_since.replace("-", "/")
        params["datetype"] = "mdat"

    print(f"  PubMed esearch: {query[:80]}...", flush=True)

    data = _eutils_get("esearch.fcgi", params, timeout=60)
    result = json.loads(data)

    esearch_result = result.get("esearchresult", {})
    pmids = esearch_result.get("idlist", [])
    total = int(esearch_result.get("count", 0))

    if total > retmax:
        print(
            f"  Warning: PubMed results ({total}) exceed max PMIDs ({retmax}); "
            "only first batch will be fetched. Use --max-pmids to increase.",
            file=sys.stderr,
            flush=True,
        )
    print(f"  PubMed: {total} results, fetching {len(pmids)} PMIDs", flush=True)
    return pmids


def efetch_articles(
    pmids: List[str],
    batch_size: int = DEFAULT_EFETCH_BATCH,
) -> List[Dict[str, Any]]:
    """Fetch article metadata from PubMed in batches."""
    articles: List[Dict[str, Any]] = []

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
            "rettype": "abstract",
        }

        data = _eutils_get("efetch.fcgi", params, timeout=60)
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            print(f"  Warning: XML parse error for batch {i//batch_size + 1}", file=sys.stderr)
            continue

        for article_el in root.findall(".//PubmedArticle"):
            article = _parse_article(article_el)
            if article:
                articles.append(article)

        print(f"  Fetched batch {i//batch_size + 1}/{(len(pmids) + batch_size - 1)//batch_size}: "
              f"{len(articles)} articles", flush=True)

    return articles


def _parse_article(article_el: ET.Element) -> Optional[Dict[str, Any]]:
    """Parse a PubmedArticle XML element into a dict."""
    medline = article_el.find(".//MedlineCitation")
    if medline is None:
        return None

    pmid_el = medline.find("PMID")
    pmid = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else ""
    if not pmid:
        return None

    article = medline.find("Article")
    if article is None:
        return None

    title_el = article.find("ArticleTitle")
    title = "".join(title_el.itertext()).strip() if title_el is not None else ""

    # Abstract text
    abstract_parts = []
    abstract_el = article.find("Abstract")
    if abstract_el is not None:
        for text_el in abstract_el.findall("AbstractText"):
            label = text_el.get("Label", "")
            text = (text_el.text or "").strip()
            # Also get tail text from child elements
            full_text = "".join(text_el.itertext()).strip()
            if full_text:
                if label:
                    abstract_parts.append(f"{label}: {full_text}")
                else:
                    abstract_parts.append(full_text)
    abstract = " ".join(abstract_parts)

    # Journal info
    journal_el = article.find("Journal")
    journal = ""
    pub_date = ""
    if journal_el is not None:
        title_j = journal_el.find("Title")
        journal = (title_j.text or "").strip() if title_j is not None else ""
        ji = journal_el.find("JournalIssue")
        if ji is not None:
            pd = ji.find("PubDate")
            if pd is not None:
                year = (pd.findtext("Year") or "").strip()
                month = (pd.findtext("Month") or "").strip()
                pub_date = f"{year}-{month}" if month else year

    # DOI
    doi = ""
    for eid in article.findall("ELocationID"):
        if eid.get("EIdType") == "doi":
            doi = (eid.text or "").strip()
            break

    # NCT IDs from DataBankList
    nct_ids = []
    for db_el in medline.findall(".//DataBankList/DataBank"):
        db_name = (db_el.findtext("DataBankName") or "").strip()
        if "ClinicalTrials" in db_name or "clinicaltrials" in db_name.lower():
            for acc_el in db_el.findall(".//AccessionNumber"):
                acc = (acc_el.text or "").strip()
                if re.match(r"^NCT\d{8}$", acc):
                    nct_ids.append(acc)

    # MeSH terms
    mesh_terms = []
    for mesh_el in medline.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
        term = (mesh_el.text or "").strip()
        if term:
            mesh_terms.append(term)

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "journal": journal,
        "pub_date": pub_date,
        "doi": doi,
        "nct_ids": nct_ids,
        "mesh_terms": mesh_terms,
    }


def search_pubmed_primary(
    hemo_keywords: List[str],
    config: Dict[str, Any],
    updated_since: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Search PubMed for ICU RCTs with hemodynamic outcomes.

    Returns (studies_rows, hemo_rows).
    """
    query = _build_pubmed_query(config)
    pmids = esearch(query, retmax=config.get("max_pmids", DEFAULT_MAX_PMIDS), updated_since=updated_since)

    if not pmids:
        return [], []

    articles = efetch_articles(pmids, batch_size=config.get("efetch_batch", DEFAULT_EFETCH_BATCH))

    studies: List[Dict[str, str]] = []
    hemo_mentions: List[Dict[str, str]] = []

    for article in articles:
        # Check abstract for hemodynamic keywords
        abstract = article.get("abstract", "")
        title = article.get("title", "")
        combined_text = f"{title} {abstract}"

        matches = []
        for kw in hemo_keywords:
            if keyword_in_text(kw, combined_text):
                matches.append(kw)

        if not matches:
            continue

        nct_ids = article.get("nct_ids", [])
        nct_id = nct_ids[0] if nct_ids else ""

        study_row = {
            "nct_id": nct_id,
            "trial_id": f"PMID:{article['pmid']}",
            "source_registry": "pubmed",
            "brief_title": _csv_safe(title),
            "official_title": "",
            "overall_status": "COMPLETED",  # Published articles imply completed trials
            "study_type": "INTERVENTIONAL",
            "allocation": "RANDOMIZED",
            "primary_purpose": "",
            "intervention_model": "",
            "masking": "",
            "masking_description": "",
            "masking_subjects": "",
            "phase": "",
            "start_date": article.get("pub_date", ""),
            "completion_date": "",
            "last_update_posted": "",
            "results_first_posted": "",
            "has_results": "True",
            "enrollment_count": "",
            "enrollment_type": "",
            "conditions": _csv_safe("; ".join(article.get("mesh_terms", [])[:10])),
            "keywords": "",
            "arm_count": "",
            "placebo_arm_count": "",
            "outcome_count": "",
            "hemo_outcome_count": str(len(matches)),
            "countries": "",
            "updated_since": "",
            "query_name": "pubmed_primary",
            "data_sources": "pubmed",
        }

        studies.append(study_row)

        for kw in matches:
            hemo_mentions.append({
                "nct_id": nct_id or f"PMID:{article['pmid']}",
                "outcome_type": "inferred",  # title/abstract keyword match, not a registered endpoint
                "measure": _csv_safe(title[:200] if title else ""),
                "keyword": kw,
                "matched_text": _csv_safe(combined_text[:500]),
                "query_name": "pubmed_primary",
            })

    print(f"  PubMed primary: {len(studies)} studies with hemo outcomes, "
          f"{len(hemo_mentions)} hemo mentions", flush=True)

    return studies, hemo_mentions


def write_csv(rows: List[Dict[str, str]], path: Path, fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Search PubMed for ICU RCTs")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--updated-since", default=None, help="YYYY-MM-DD to limit results")
    parser.add_argument("--max-pmids", type=int, default=DEFAULT_MAX_PMIDS,
                        help="Max PMIDs to fetch from PubMed (default: 10000)")
    parser.add_argument("--efetch-batch", type=int, default=DEFAULT_EFETCH_BATCH,
                        help="PMIDs per efetch request (default: 200)")
    args = parser.parse_args()

    config = load_config()
    hemo_keywords = config.get("hemodynamic_keywords", [])

    print(f"Searching PubMed with {len(hemo_keywords)} hemodynamic keywords...", flush=True)

    # Allow CLI overrides without forcing edits to config JSON.
    config = dict(config)
    config["max_pmids"] = args.max_pmids
    config["efetch_batch"] = args.efetch_batch

    studies, hemo = search_pubmed_primary(hemo_keywords, config, updated_since=args.updated_since)

    output_dir = Path(args.output_dir)
    studies_fields = [
        "nct_id", "trial_id", "source_registry", "brief_title", "official_title",
        "overall_status", "study_type", "allocation", "primary_purpose",
        "intervention_model", "masking", "masking_description", "masking_subjects",
        "phase", "start_date", "completion_date", "last_update_posted",
        "results_first_posted", "has_results", "enrollment_count", "enrollment_type",
        "conditions", "keywords", "arm_count", "placebo_arm_count",
        "outcome_count", "hemo_outcome_count", "countries",
        "updated_since", "query_name", "data_sources",
    ]
    hemo_fields = ["nct_id", "outcome_type", "measure", "keyword", "matched_text", "query_name"]

    studies_path = output_dir / "pubmed_icu_studies.csv"
    hemo_path = output_dir / "pubmed_icu_hemo.csv"
    write_csv(studies, studies_path, studies_fields)
    write_csv(hemo, hemo_path, hemo_fields)

    print(f"Output: {studies_path.name} ({len(studies)} rows), {hemo_path.name} ({len(hemo)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
