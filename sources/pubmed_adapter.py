"""
PubMed E-utilities adapter.

Queries NCBI for publications linked to NCT IDs via:
  - esearch: find PMIDs referencing an NCT ID in SecondarySourceID
  - efetch: retrieve metadata (title, journal, date, DOI, MeSH) in XML

Rate limit: 3 req/sec without API key.
"""
from __future__ import annotations

import re
import sqlite3
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from urllib.parse import quote_plus

from sources.base_adapter import BaseAdapter, FetchResult


class PubMedAdapter(BaseAdapter):

    def fetch_for_trial(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        """Search PubMed for PMIDs linked to this NCT ID, then fetch metadata."""
        pmids = self._esearch(nct_id)
        if not pmids:
            return FetchResult(nct_id, self.source_name, "empty", records=0)

        articles = self._efetch(pmids)
        context["_pubmed_articles"] = articles
        context["_pubmed_pmids"] = pmids
        return FetchResult(nct_id, self.source_name, "ok", records=len(articles))

    def store_results(self, result: FetchResult, context: Dict[str, Any]) -> None:
        articles = context.get("_pubmed_articles", [])
        if not articles:
            return

        now = self._now_utc()
        conn = self._get_conn()
        try:
            for art in articles:
                # Insert publication
                conn.execute(
                    """INSERT OR IGNORE INTO publications
                       (nct_id, pmid, pmcid, doi, title, journal, pub_date, pub_type,
                        source, fetched_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.nct_id,
                        art.get("pmid"),
                        art.get("pmcid"),
                        art.get("doi"),
                        art.get("title"),
                        art.get("journal"),
                        art.get("pub_date"),
                        art.get("pub_type"),
                        self.source_name,
                        now,
                    ),
                )

                # Insert MeSH terms
                for mesh in art.get("mesh_terms", []):
                    conn.execute(
                        """INSERT OR IGNORE INTO mesh_terms
                           (pmid, descriptor_ui, descriptor_name, qualifier_ui,
                            qualifier_name, is_major_topic, source, fetched_utc)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            art.get("pmid"),
                            mesh.get("descriptor_ui"),
                            mesh.get("descriptor_name"),
                            mesh.get("qualifier_ui"),
                            mesh.get("qualifier_name"),
                            1 if mesh.get("is_major") else 0,
                            self.source_name,
                            now,
                        ),
                    )

            conn.commit()
        finally:
            conn.close()

        # Store content hash for provenance (deterministic via sorted JSON)
        import json  # noqa: late import — only used here
        raw_data = json.dumps(articles, sort_keys=True).encode("utf-8")
        self.store_hash(f"pubmed:{result.nct_id}", self._hash_bytes(raw_data))

    def _esearch(self, nct_id: str) -> List[str]:
        """Search PubMed for PMIDs associated with an NCT ID."""
        safe_nct = quote_plus(f'"{nct_id}"[si]')
        url = (
            f"{self.config.base_url}/esearch.fcgi"
            f"?db=pubmed&term={safe_nct}&retmode=json&retmax=200"
        )
        data = self._get_json(url)
        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])
        return pmids

    def _efetch(self, pmids: List[str]) -> List[Dict[str, Any]]:
        """Fetch article metadata for a list of PMIDs (batch up to 200)."""
        # Validate PMIDs are purely numeric to prevent URL parameter injection
        safe_pmids = [p for p in pmids if p and re.match(r"^\d{1,12}$", p)]
        if not safe_pmids:
            return []
        articles: List[Dict[str, Any]] = []
        # Batch in groups of 200
        for i in range(0, len(safe_pmids), 200):
            batch = safe_pmids[i : i + 200]
            ids_str = ",".join(batch)
            url = (
                f"{self.config.base_url}/efetch.fcgi"
                f"?db=pubmed&id={ids_str}&rettype=xml&retmode=xml"
            )
            raw = self._get(url)
            articles.extend(self._parse_pubmed_xml(raw))
        return articles

    def _parse_pubmed_xml(self, xml_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse PubMed XML efetch response into article dicts."""
        articles: List[Dict[str, Any]] = []
        # Reject XML with inline ENTITY declarations to prevent entity
        # expansion attacks (billion-laughs). Note: PubMed responses
        # legitimately include <!DOCTYPE> so we only block <!ENTITY>.
        if b"<!ENTITY" in xml_bytes:
            return articles
        # Cap input size to prevent memory exhaustion from very large responses
        if len(xml_bytes) > 50 * 1024 * 1024:  # 50 MB
            return articles
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return articles

        for article_el in root.findall(".//PubmedArticle"):
            art: Dict[str, Any] = {}

            # PMID (validate format — V-1)
            pmid_el = article_el.find(".//PMID")
            pmid_text = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else None
            if pmid_text and not re.match(r"^\d+$", pmid_text):
                pmid_text = None
            art["pmid"] = pmid_text

            # Title
            title_el = article_el.find(".//ArticleTitle")
            art["title"] = _text_content(title_el)

            # Journal
            journal_el = article_el.find(".//Journal/Title")
            art["journal"] = journal_el.text if journal_el is not None else None

            # Publication date
            pub_date_el = article_el.find(".//PubDate")
            art["pub_date"] = _parse_pub_date(pub_date_el)

            # Publication type
            pub_types = article_el.findall(".//PublicationType")
            art["pub_type"] = "; ".join(
                pt.text for pt in pub_types if pt.text
            ) if pub_types else None

            # DOI
            doi = None
            for aid in article_el.findall(".//ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = aid.text
                    break
            art["doi"] = doi

            # PMC ID
            pmcid = None
            for aid in article_el.findall(".//ArticleId"):
                if aid.get("IdType") == "pmc":
                    pmcid = aid.text
                    break
            art["pmcid"] = pmcid

            # MeSH terms
            mesh_terms: List[Dict[str, Any]] = []
            for mesh_heading in article_el.findall(".//MeshHeading"):
                desc = mesh_heading.find("DescriptorName")
                if desc is None:
                    continue
                qualifiers = mesh_heading.findall("QualifierName")
                if qualifiers:
                    for qual in qualifiers:
                        mesh_terms.append({
                            "descriptor_ui": desc.get("UI"),
                            "descriptor_name": desc.text,
                            "qualifier_ui": qual.get("UI"),
                            "qualifier_name": qual.text,
                            "is_major": qual.get("MajorTopicYN") == "Y",
                        })
                else:
                    mesh_terms.append({
                        "descriptor_ui": desc.get("UI"),
                        "descriptor_name": desc.text,
                        "qualifier_ui": None,
                        "qualifier_name": None,
                        "is_major": desc.get("MajorTopicYN") == "Y",
                    })
            art["mesh_terms"] = mesh_terms
            articles.append(art)

        return articles


def _text_content(element) -> str:
    """Extract all text content from an XML element (handles mixed content)."""
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _parse_pub_date(element) -> str:
    """Parse a PubDate element into a consistent YYYY-MM-DD string."""
    if element is None:
        return ""
    year = element.findtext("Year", "")
    month = element.findtext("Month", "")
    day = element.findtext("Day", "")
    medline = element.findtext("MedlineDate", "")
    if year:
        parts = [year]
        if month:
            if month.isdigit():
                parts.append(month.zfill(2))
            else:
                parts.append(_MONTH_MAP.get(month.lower()[:3], month))
        if day:
            parts.append(day.zfill(2))
        return "-".join(parts)
    return medline
