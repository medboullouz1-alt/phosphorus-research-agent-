"""
Paper Analyzer — uses Google Gemini 1.5 Flash (FREE tier)
Free tier: 15 requests/minute, 1 million tokens/day
This agent uses ~12 requests/day — well within limits.
"""
import json, logging, time, re
import urllib.request, urllib.error
import config

logger = logging.getLogger(__name__)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)

ANALYSIS_PROMPT = """You are a senior researcher specializing in phosphorus
biogeochemistry, soil GHG emissions (N2O, CO2, CH4), and sustainable agriculture.
Analyze the paper below and return ONLY valid JSON — no markdown, no preamble,
no explanation. Just the raw JSON object.

TODAY'S THEME: {theme}

PAPER:
Title: {title}
Authors: {authors}
Journal: {journal}
Year: {year}
DOI: {doi}
Abstract: {abstract}

Return ONLY this JSON structure with no extra text:
{{
  "full_citation_apa": "...",
  "doi_link": "https://doi.org/...",
  "journal_name": "...",
  "journal_impact_note": "brief note on journal prestige",
  "study_region": "country or region or global",
  "methodology": "field trial / meta-analysis / modeling / lab / LCA / review",
  "key_findings": "3-5 bullet points, use newline and bullet for each",
  "quantified_results": "specific numbers: % GHG reduction, yield change, etc.",
  "ghg_mitigation_contribution": "how this advances GHG mitigation knowledge",
  "p_management_contribution": "how this advances sustainable P management",
  "practical_implications": "what farmers, advisors, or policymakers should do",
  "limitations": "study limitations and uncertainties",
  "why_it_matters": "2-3 sentence compelling explanation",
  "keywords_extracted": ["kw1", "kw2", "kw3", "kw4", "kw5"]
}}"""

SYNTHESIS_PROMPT = """You are an expert in phosphorus nutrition, soil GHG
emissions, and sustainable agriculture. Synthesize these {n} papers on the
theme "{theme}" and return ONLY valid JSON — no markdown, no preamble.

PAPERS SUMMARY:
{summaries}

Return ONLY this JSON with no extra text:
{{
  "thematic_introduction": "100-word introduction to today's theme and why it matters",
  "synthesis_paragraph": "150-word paragraph connecting all papers together",
  "key_takeaway": "one powerful actionable sentence summarizing the day",
  "emerging_pattern": "the main recurring finding across papers",
  "research_gap": "the most important unanswered question",
  "contradictions": "any conflicting findings, or write None identified",
  "practical_implication": "one concrete climate-smart agriculture recommendation"
}}"""


def _call_gemini(prompt: str, retries=3) -> str:
    url  = GEMINI_URL.format(model=config.GEMINI_MODEL, key=config.GEMINI_API_KEY)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
    })
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=body.encode(), method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning("Rate limit — waiting 65 seconds...")
                time.sleep(65)
            else:
                logger.error("Gemini HTTP %d on attempt %d", e.code, attempt + 1)
                time.sleep(5)
        except Exception as e:
            logger.error("Gemini error attempt %d: %s", attempt + 1, e)
            time.sleep(5)
    return ""


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    # Remove markdown code blocks
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    # Find the first { and the last }
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end != -1:
        raw = raw[start:end+1]
    # Replace common issues
    raw = raw.replace('\n', ' ').replace('\r', '')
    return json.loads(raw)


def analyze_paper(paper: dict, theme: dict) -> dict:
    prompt = ANALYSIS_PROMPT.format(
        theme   = theme["name"],
        title   = paper.get("title", "N/A"),
        authors = paper.get("authors", "N/A"),
        journal = paper.get("journal", "N/A"),
        year    = paper.get("year", "N/A"),
        doi     = paper.get("doi", "N/A"),
        abstract= (paper.get("abstract") or "Abstract not available.")[:2000])
    raw = _call_gemini(prompt)
    if not raw:
        return paper
    try:
        analysis = _parse_json(raw)
        paper.update(analysis)
        paper["keywords"]     = json.dumps(analysis.get("keywords_extracted", []))
        paper["key_findings"] = analysis.get("key_findings", "")
        paper["methodology"]  = analysis.get("methodology", "")
        paper["study_region"] = analysis.get("study_region", "")
        paper["ghg_result"]   = analysis.get("quantified_results", "")
        paper["implications"] = analysis.get("practical_implications", "")
        paper["limitations"]  = analysis.get("limitations", "")
        paper["full_summary"] = json.dumps(analysis)
    except Exception as e:
        logger.warning("Failed to parse Gemini response: %s", e)
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
            f"  Key findings: {a.get('key_findings', p.get('key_findings', ''))[:300]}\n"
            f"  Quantified: {a.get('quantified_results', p.get('ghg_result', ''))[:200]}\n")
    prompt = SYNTHESIS_PROMPT.format(
        n        = len(papers),
        theme    = theme["name"],
        summaries= "\n\n".join(summaries))
    raw = _call_gemini(prompt)
    fallback = {
        "thematic_introduction": theme["name"],
        "synthesis_paragraph": "See individual papers above.",
        "key_takeaway": "Review the papers above for today's key insights.",
        "emerging_pattern": "N/A", "research_gap": "N/A",
        "contradictions": "N/A", "practical_implication": "N/A"}
    if not raw:
        return fallback
    try:
        return _parse_json(raw)
    except Exception as e:
        logger.error("Synthesis parse error: %s", e)
        return fallback
