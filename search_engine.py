"""
Literature search — 4 free APIs with open access detection
"""
import time, logging, math, requests
from typing import Optional
import config, database

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": f"PhosphorusResearchAgent/1.0 mailto:{config.NCBI_EMAIL}"}

def _get(url, params=None) -> Optional[dict]:
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning("GET attempt %d failed: %s", attempt + 1, e)
            time.sleep(3 * (attempt + 1))
    return None

def _openalex(query, n=20) -> list:
    data = _get("https://api.openalex.org/works", {
        "search": query,
        "filter": "is_paratext:false,type:article",
        "sort": "cited_by_count:desc",
        "per_page": n,
        "select": "id,doi,title,authorships,publication_year,"
                  "primary_location,abstract_inverted_index,"
                  "cited_by_count,open_access"})
    if not data:
        return []
    out = []
    for w in data.get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        wp  = [(pos, wd) for wd, ps in inv.items() for pos in ps]
        abstract = " ".join(wd for _, wd in sorted(wp))
        loc = (w.get("primary_location") or {})
        src = (loc.get("source") or {})
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        oa  = (w.get("open_access") or {}).get("is_oa", False)
        pdf = (w.get("open_access") or {}).get("oa_url", "")
        out.append({
            "doi": doi,
            "title": w.get("title", ""),
            "authors": "; ".join(
                a.get("author", {}).get("display_name", "")
                for a in (w.get("authorships") or [])[:6]),
            "journal": src.get("display_name", ""),
            "year": w.get("publication_year"),
            "abstract": abstract,
            "citation_count": w.get("cited_by_count", 0),
            "open_access": oa,
            "url": pdf or loc.get("landing_page_url") or
                   (f"https://doi.org/{doi}" if doi else ""),
            "source": "OpenAlex"})
    return out

def _semantic(query, n=20) -> list:
    data = _get("https://api.semanticscholar.org/graph/v1/paper/search", {
        "query": query, "limit": n,
        "fields": "paperId,title,authors,year,externalIds,"
                  "abstract,journal,citationCount,openAccessPdf,isOpenAccess"})
    if not data:
        return []
    out = []
    for p in data.get("data", []):
        doi = (p.get("externalIds") or {}).get("DOI", "")
        j   = (p.get("journal") or {}).get("name", "")
        pdf = (p.get("openAccessPdf") or {}).get("url", "")
        oa  = p.get("isOpenAccess", False)
        out.append({
            "doi": doi,
            "title": p.get("title", ""),
            "authors": "; ".join(
                a.get("name", "") for a in (p.get("authors") or [])[:6]),
            "journal": j,
            "year": p.get("year"),
            "abstract": p.get("abstract") or "",
            "citation_count": p.get("citationCount", 0),
            "open_access": oa,
            "url": pdf or (f"https://doi.org/{doi}" if doi else ""),
            "source": "Semantic Scholar"})
    return out

def _crossref(query, n=15) -> list:
    data = _get("https://api.crossref.org/works", {
        "query": query, "rows": n, "sort": "relevance",
        "filter": "type:journal-article",
        "select": "DOI,title,author,published,container-title,"
                  "is-referenced-by-count,URL,license"})
    if not data:
        return []
    out = []
    for item in data.get("message", {}).get("items", []):
        doi     = item.get("DOI", "")
        title   = (item.get("title") or [""])[0]
        authors = "; ".join(
            f"{a.get('given','')} {a.get('family','')}".strip()
            for a in (item.get("author") or [])[:6])
        parts   = item.get("published", {}).get("date-parts", [[None]])
        year    = parts[0][0] if parts and parts[0] else None
        journal = ((item.get("container-title") or [""])[0])
        licenses = item.get("license") or []
        oa = any("creativecommons" in (lic.get("URL","")).lower() for lic in licenses)
        out.append({
            "doi": doi, "title": title, "authors": authors,
            "journal": journal, "year": year, "abstract": "",
            "citation_count": item.get("is-referenced-by-count", 0),
            "open_access": oa,
            "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
            "source": "CrossRef"})
    return out

def _pubmed(query, n=15) -> list:
    base   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search = _get(f"{base}/esearch.fcgi", {
        "db": "pubmed", "term": query, "retmax": n,
        "retmode": "json", "sort": "relevance",
        "tool": "PhosphorusResearchAgent", "email": config.NCBI_EMAIL})
    if not search:
        return []
    ids = search.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    time.sleep(0.4)
    fetch = _get(f"{base}/esummary.fcgi", {
        "db": "pubmed", "id": ",".join(ids), "retmode": "json",
        "tool": "PhosphorusResearchAgent", "email": config.NCBI_EMAIL})
    if not fetch:
        return []
    out = []
    for uid, doc in (fetch.get("result") or {}).items():
        if uid == "uids":
            continue
        doi = next(
            (i.get("value", "") for i in doc.get("articleids", [])
             if i.get("idtype") == "doi"), "")
        year = None
        try:
            year = int(doc.get("pubdate", "")[:4])
        except Exception:
            pass
        # PMC articles are open access
        pmc = next(
            (i.get("value","") for i in doc.get("articleids",[])
             if i.get("idtype") == "pmc"), "")
        oa = bool(pmc)
        out.append({
            "doi": doi,
            "title": doc.get("title", ""),
            "authors": "; ".join(
                a.get("name", "") for a in doc.get("authors", [])[:6]),
            "journal": doc.get("fulljournalname", ""),
            "year": year, "abstract": "",
            "citation_count": 0,
            "open_access": oa,
            "url": (f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc}/"
                    if pmc else f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"),
            "source": "PubMed"})
    return out

def _dedup(papers: list) -> list:
    by_doi, by_title = {}, {}
    for p in papers:
        doi   = (p.get("doi") or "").strip().lower()
        title = (p.get("title") or "").strip().lower()[:80]
        key   = doi if doi else title
        if not key:
            continue
        existing = by_doi.get(doi) or by_title.get(title)
        if existing:
            if len(p.get("abstract") or "") > len(existing.get("abstract") or ""):
                if doi:
                    by_doi[doi] = p
                by_title[title] = p
        else:
            if doi:
                by_doi[doi] = p
            by_title[title] = p
    return list({id(v): v for v in {**by_doi, **by_title}.values()}.values())

def _score(p: dict, theme_kws: list) -> float:
    text = (
        (p.get("title") or "") + " " +
        (p.get("abstract") or "") + " " +
        (p.get("journal") or "")).lower()
    score  = sum(3.0 for kw in theme_kws if kw.lower() in text)
    score += sum(2.0 for kw in [
        "phosphorus", "phosphate", "greenhouse gas", "ghg",
        "n2o", "nitrous oxide", "fertilizer", "nutrient"] if kw in text)
    journal = (p.get("journal") or "").lower()
    if any(j.lower() in journal for j in config.HIGH_IMPACT_JOURNALS):
        score += 5.0
    c = p.get("citation_count") or 0
    if c > 0:
        score += math.log10(c + 1) * 2
    yr = p.get("year") or 0
    score += 4.0 if yr >= 2024 else (2.0 if yr >= 2022 else (1.0 if yr >= 2020 else 0))
    if len(p.get("abstract") or "") > 100:
        score += 2.0
    # Open access bonus — prefer papers we can fully analyze
    if p.get("open_access"):
        score += 3.0
    return score

def search_literature(theme: dict, n=15) -> list:
    seen    = database.get_seen_dois(days=90)
    queries = config.BASE_KEYWORDS[:5] + theme.get("extra_keywords", [])[:3]
    all_papers = []
    for q in queries:
        logger.info("Searching: %s", q)
        all_papers += _openalex(q, 15)
        time.sleep(1)
        all_papers += _semantic(q, 15)
        time.sleep(2)
        all_papers += _crossref(q, 10)
        time.sleep(1)
        all_papers += _pubmed(q, 10)
        time.sleep(2)
    unique = _dedup(all_papers)
    logger.info("Unique papers found: %d", len(unique))
    fresh  = [p for p in unique if (p.get("doi") or "").lower() not in seen]
    logger.info("Fresh (not yet processed): %d", len(fresh))
    fresh.sort(key=lambda p: _score(p, theme.get("extra_keywords", [])), reverse=True)
    return fresh[:n]
