"""
Paper Analyzer — Groq API with Llama 3 (FREE, works worldwide including Morocco)
Free tier: very generous limits, no credit card needed
3 deep papers per day with full structured analysis
"""
import json, logging, time, re
import urllib.request, urllib.error
import config

logger = logging.getLogger(__name__)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ANALYSIS_PROMPT = """You are a senior researcher specializing in phosphorus
biogeochemistry, soil GHG emissions (N2O, CO2, CH4), and sustainable agriculture.

Analyze the paper below with DEEP scientific rigor. Return ONLY valid JSON.
No markdown, no preamble, no explanation. Just the raw JSON object.

TODAY'S THEME: {theme}
OPEN ACCESS: {open_access}

PAPER:
Title: {title}
Authors: {authors}
Journal: {journal}
Year: {year}
DOI: {doi}
Abstract: {abstract}

Return ONLY this JSON — no extra text outside the JSON:
{{
  "full_citation_apa": "Authors (Year). Title. Journal, Volume(Issue), Pages. https://doi.org/DOI",
  "doi_link": "https://doi.org/{doi}",
  "journal_name": "{journal}",
  "journal_impact_note": "Brief note on the journal prestige and impact factor if known",
  "open_access_status": "Open Access" or "Non-Open Access (summary based on abstract only)",
  "study_region": "Specific country, region, or Global",
  "methodology": "Detailed description: study type, duration, treatments, scale",
  "research_gap_addressed": "What specific knowledge gap did this study fill? What was unknown before?",
  "main_findings": "Detailed paragraph describing ALL major findings with full scientific explanation of mechanisms and how results were interpreted by the authors",
  "key_results_quantified": "ALL specific numbers: % changes, effect sizes, concentrations, emission factors, yield values — be exhaustive",
  "emerging_trends": "What new trends or directions does this paper reveal for the field?",
  "highlighted_gaps": "What research gaps remain open after this study? What do the authors call for next?",
  "ghg_mitigation_contribution": "Specific contribution to GHG mitigation science",
  "p_management_contribution": "Specific contribution to sustainable P management",
  "practical_implications": "Concrete actionable recommendations for farmers, advisors, and policymakers",
  "limitations": "All study limitations, caveats, and uncertainties mentioned",
  "why_it_matters": "2-3 sentence compelling explanation of significance for climate-smart agriculture",
  "keywords_extracted": ["kw1", "kw2", "kw3", "kw4", "kw5"]
}}"""

SYNTHESIS_PROMPT = """You are a world-leading expert in phosphorus nutrition,
soil GHG emissions, and sustainable agriculture.

Synthesize these {n} deeply analyzed papers on the theme "{theme}".
Return ONLY valid JSON — no markdown, no preamble.

PAPERS:
{summaries}

Return ONLY this JSON:
{{
  "thematic_introduction": "120-word introduction explaining today's theme importance for climate and food security",
  "synthesis_paragraph": "200-word paragraph connecting all papers, showing how they collectively advance the field",
  "key_takeaway": "One powerful, specific, actionable sentence — the single most important insight today",
  "emerging_pattern": "The strongest recurring finding or trend across all papers",
  "research_gap": "The most critical unanswered question revealed by today's papers",
  "contradictions": "Any conflicting findings between papers, or write: No major contradictions identified",
  "practical_implication": "One concrete, specific recommendation for climate-smart P management"
}}"""


def _call_groq(prompt: str, retries=3) -> str:
    if not config.GROQ_API_KEY:
        logger.error("GROQ_API_KEY is missing — add it to GitHub Secrets")
        return ""
    body = json.dumps({
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 2048,
    })
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                GROQ_URL, data=body.encode(), method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.GROQ_API_KEY}"
                })
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()[:300]
            except Exception:
                pass
            if e.code == 429:
                logger.warning("Groq rate limit — waiting 30s...")
                time.sleep(30)
            else:
                logger.error("Groq HTTP %d attempt %d: %s", e.code, attempt + 1, err_body)
                time.sleep(5)
        except Exception as e:
            logger.error("Groq error attempt %d: %s", attempt + 1, e)
            time.sleep(5)
    return ""


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    start = raw.find("{")
    end   = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    return json.loads(raw)


def analyze_paper(paper: dict, theme: dict) -> dict:
    # Detect open access
    open_access = "Yes" if paper.get("url", "").endswith(".pdf") \
                        or paper.get("open_access") \
                        else "Unknown — treat as Non-Open Access, use abstract only"

    prompt = ANALYSIS_PROMPT.format(
        theme       = theme["name"],
        open_access = open_access,
        title       = paper.get("title", "N/A"),
        authors     = paper.get("authors", "N/A"),
        journal     = paper.get("journal", "N/A"),
        year        = paper.get("year", "N/A"),
        doi         = paper.get("doi", "N/A"),
        abstract    = (paper.get("abstract") or "Abstract not available.")[:2500])

    raw = _call_groq(prompt)
    if not raw:
        return paper
    try:
        analysis = _parse_json(raw)
        paper.update(analysis)
        paper["keywords"]     = json.dumps(analysis.get("keywords_extracted", []))
        paper["key_findings"] = analysis.get("main_findings", "")
        paper["methodology"]  = analysis.get("methodology", "")
        paper["study_region"] = analysis.get("study_region", "")
        paper["ghg_result"]   = analysis.get("key_results_quantified", "")
        paper["implications"] = analysis.get("practical_implications", "")
        paper["limitations"]  = analysis.get("limitations", "")
        paper["full_summary"] = json.dumps(analysis)
    except Exception as e:
        logger.warning("Failed to parse Groq response: %s | Raw: %s", e, raw[:200])
    return paper


def synthesize_papers(papers: list, theme: dict) -> dict:
    summaries = []
    for i, p in enumerate(papers, 1):
        a = {}
        try:
            a = json.loads(p.get("full_summary") or "{}")
        except Exception:
            pass
        summaries.append(
            f"Paper {i}: {p.get('title', '')}\n"
            f"  Journal: {p.get('journal', '')}, {p.get('year', '')}\n"
            f"  Open Access: {a.get('open_access_status', 'Unknown')}\n"
            f"  Research gap addressed: {a.get('research_gap_addressed', '')[:200]}\n"
            f"  Main findings: {a.get('main_findings', p.get('key_findings', ''))[:400]}\n"
            f"  Quantified: {a.get('key_results_quantified', p.get('ghg_result', ''))[:200]}\n"
            f"  Emerging trends: {a.get('emerging_trends', '')[:200]}\n")

    prompt = SYNTHESIS_PROMPT.format(
        n         = len(papers),
        theme     = theme["name"],
        summaries = "\n\n".join(summaries))

    raw = _call_groq(prompt)
    fallback = {
        "thematic_introduction": theme["name"],
        "synthesis_paragraph": "See individual paper summaries above.",
        "key_takeaway": "Review the detailed paper analyses above.",
        "emerging_pattern": "N/A", "research_gap": "N/A",
        "contradictions": "N/A", "practical_implication": "N/A"}
    if not raw:
        return fallback
    try:
        return _parse_json(raw)
    except Exception as e:
        logger.error("Synthesis parse error: %s", e)
        return fallback
