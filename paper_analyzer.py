"""
Paper Analyzer — Groq API with Llama 3.3 70B (FREE, works worldwide)
3 papers per day with high-level mechanistic academic analysis
"""
import json, logging, time, re
import urllib.request, urllib.error
import config

logger = logging.getLogger(__name__)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ANALYSIS_SYSTEM = """You are a scientific analyst specializing in biogeochemistry and agroecosystem research.
You write in formal scientific language appropriate for high-impact journals.
You NEVER use bullet points. You NEVER add AI commentary.
You ALWAYS return pure valid JSON with no text outside the JSON object."""

ANALYSIS_PROMPT = """Analyze the scientific paper below and return ONLY a valid JSON object.

TODAY'S THEME: {theme}
OPEN ACCESS: {open_access}

PAPER:
Title: {title}
Authors: {authors}
Journal: {journal}
Year: {year}
DOI: {doi}
Abstract: {abstract}

CRITICAL INSTRUCTION: The field "mechanistic_analysis" must be a single continuous prose paragraph of AT LEAST 300 words in formal scientific language. It must cover in this exact logical order:
(1) The central research question stated precisely
(2) The hypothesis including expected directional or nonlinear responses
(3) The methodology: experimental design, treatments tested, measurement techniques, statistical approaches
(4) The main quantitative findings with exact statistics, thresholds, rates, nonlinear patterns, temporal dynamics
(5) The mechanisms: biogeochemical pathways, controlling variables, process shifts
(6) Assumptions flagged explicitly as: "The authors assumed that..." or "It was hypothesized but not directly measured that..."
(7) A mechanistic conclusion strictly limited to what the data support

Rules for mechanistic_analysis:
- Minimum 300 words of continuous prose
- No bullet points, no section headings, no numbered lists
- No phrases like "this study highlights" or "this research is important"
- No vague words like "significant increase" without a number
- Formal scientific vocabulary throughout
- Every quantitative result must include its exact value and statistical test

Return ONLY this JSON object — no text before or after the opening and closing braces:
{{
  "full_citation_apa": "Full APA citation including authors, year, title, journal, volume, issue, pages, doi",
  "doi_link": "https://doi.org/{doi}",
  "journal_name": "{journal}",
  "journal_impact_note": "Factual note on journal scope and impact factor if known, otherwise state Unknown",
  "open_access_status": "Open Access" or "Non-Open Access (analysis based on abstract only)",
  "study_region": "Specific country or region or Global",
  "research_gap_addressed": "One precise sentence stating the specific knowledge gap this study filled",
  "mechanistic_analysis": "MINIMUM 300 WORDS of continuous formal scientific prose covering all 7 points above",
  "key_results_quantified": "Every single quantitative result from the paper: exact percentages, p-values, R2, thresholds, concentrations, emission factors, yield values — be exhaustive",
  "emerging_trends": "What new research direction does this paper reveal for the field",
  "highlighted_gaps": "Specific remaining knowledge gaps the authors identified after this study",
  "practical_implications": "Concrete recommendations for farmers advisors or policymakers derived strictly from the results",
  "limitations": "All limitations caveats and uncertainties explicitly stated in the paper",
  "keywords_extracted": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}"""

SYNTHESIS_SYSTEM = """You are a world-leading expert in phosphorus nutrition and soil GHG emissions.
You write synthesis paragraphs in formal scientific language for high-impact journal audiences.
You ALWAYS return pure valid JSON with no text outside the JSON object."""

SYNTHESIS_PROMPT = """Synthesize these {n} deeply analyzed papers on the theme "{theme}".
Return ONLY a valid JSON object — no text before or after the braces.

PAPERS:
{summaries}

Return ONLY this JSON:
{{
  "thematic_introduction": "120-word formal scientific introduction to this theme covering its relevance to climate change mitigation, current state of knowledge, and why these papers matter",
  "synthesis_paragraph": "250-word formal scientific paragraph integrating all papers — showing convergences, divergences, mechanistic links. No bullet points. Formal language.",
  "key_takeaway": "One precise mechanistically grounded sentence — the single most important scientific insight from today",
  "emerging_pattern": "The strongest convergent mechanistic finding across papers stated with precision",
  "research_gap": "The most critical unresolved mechanistic question revealed by these papers combined",
  "contradictions": "Conflicting quantitative findings or mechanistic interpretations between papers — or write: No major contradictions identified",
  "practical_implication": "One concrete evidence-based recommendation for climate-smart phosphorus management"
}}"""


def _call_groq(system: str, prompt: str, retries=3) -> str:
    if not config.GROQ_API_KEY:
        logger.error("GROQ_API_KEY is missing — add it to GitHub Secrets")
        return ""
    body = json.dumps({
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt}
        ],
        "temperature": 0.15,
        "max_tokens": 3500,
    })
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                GROQ_URL, data=body.encode(), method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.GROQ_API_KEY}"
                })
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            logger.info("Groq response length: %d chars", len(content))
            return content
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()[:400]
            except Exception:
                pass
            if e.code == 429:
                logger.warning("Groq rate limit — waiting 30s...")
                time.sleep(30)
            elif e.code == 413:
                logger.error("Prompt too long — truncating abstract")
                return ""
            else:
                logger.error("Groq HTTP %d attempt %d: %s", e.code, attempt + 1, err_body)
                time.sleep(5)
        except Exception as e:
            logger.error("Groq error attempt %d: %s", attempt + 1, e)
            time.sleep(5)
    return ""


def _parse_json(raw: str) -> dict:
    """Robustly extract JSON from Groq response."""
    raw = raw.strip()
    # Remove markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
    raw = raw.strip()
    # Find outermost JSON object
    start = raw.find("{")
    end   = raw.rfind("}")
    if start == -1 or end == -1:
        logger.error("No JSON object found in response. Raw: %s", raw[:300])
        raise ValueError("No JSON object found")
    raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # Try to fix common issues: unescaped newlines inside string values
        logger.warning("JSON decode error: %s — attempting repair", e)
        # Replace literal newlines inside JSON strings
        fixed = re.sub(r'(?<!\\)\n', ' ', raw)
        return json.loads(fixed)


def analyze_paper(paper: dict, theme: dict) -> dict:
    open_access = (
        "Yes — full text available"
        if (paper.get("open_access") or paper.get("url", "").endswith(".pdf"))
        else "No — analysis must be based on abstract only")

    prompt = ANALYSIS_PROMPT.format(
        theme       = theme["name"],
        open_access = open_access,
        title       = paper.get("title", "N/A"),
        authors     = paper.get("authors", "N/A"),
        journal     = paper.get("journal", "N/A"),
        year        = paper.get("year", "N/A"),
        doi         = paper.get("doi", "N/A"),
        abstract    = (paper.get("abstract") or "Abstract not available.")[:3000])

    raw = _call_groq(ANALYSIS_SYSTEM, prompt)
    if not raw:
        logger.warning("Empty Groq response for: %s", paper.get("title", "")[:60])
        return paper
    try:
        analysis = _parse_json(raw)
        logger.info("Analysis parsed OK — mechanistic_analysis length: %d",
                    len(analysis.get("mechanistic_analysis", "")))
        paper.update(analysis)
        paper["keywords"]     = json.dumps(analysis.get("keywords_extracted", []))
        paper["key_findings"] = analysis.get("mechanistic_analysis", "")
        paper["methodology"]  = analysis.get("mechanistic_analysis", "")[:200]
        paper["study_region"] = analysis.get("study_region", "")
        paper["ghg_result"]   = analysis.get("key_results_quantified", "")
        paper["implications"] = analysis.get("practical_implications", "")
        paper["limitations"]  = analysis.get("limitations", "")
        paper["full_summary"] = json.dumps(analysis)
    except Exception as e:
        logger.error("Failed to parse Groq response: %s", e)
        logger.error("Raw response was: %s", raw[:500])
    return paper


def synthesize_papers(papers: list, theme: dict) -> dict:
    summaries = []
    for i, p in enumerate(papers, 1):
        a = {}
        try:
            a = json.loads(p.get("full_summary") or "{}")
        except Exception:
            pass
        mechanistic = a.get("mechanistic_analysis", p.get("key_findings", ""))
        summaries.append(
            f"Paper {i}: {p.get('title', '')}\n"
            f"  Journal: {p.get('journal', '')}, {p.get('year', '')}\n"
            f"  Open Access: {a.get('open_access_status', 'Unknown')}\n"
            f"  Research gap: {a.get('research_gap_addressed', '')[:200]}\n"
            f"  Analysis excerpt: {mechanistic[:600]}\n"
            f"  Quantified results: {a.get('key_results_quantified', '')[:300]}\n"
            f"  Emerging trends: {a.get('emerging_trends', '')[:200]}\n")

    prompt = SYNTHESIS_PROMPT.format(
        n         = len(papers),
        theme     = theme["name"],
        summaries = "\n\n".join(summaries))

    raw = _call_groq(SYNTHESIS_SYSTEM, prompt)
    fallback = {
        "thematic_introduction": theme["description"],
        "synthesis_paragraph": "Synthesis unavailable — see individual paper analyses above.",
        "key_takeaway": "See individual mechanistic analyses above.",
        "emerging_pattern": "N/A", "research_gap": "N/A",
        "contradictions": "N/A", "practical_implication": "N/A"}
    if not raw:
        return fallback
    try:
        result = _parse_json(raw)
        logger.info("Synthesis parsed OK")
        return result
    except Exception as e:
        logger.error("Synthesis parse error: %s", e)
        logger.error("Raw synthesis response: %s", raw[:500])
        return fallback
