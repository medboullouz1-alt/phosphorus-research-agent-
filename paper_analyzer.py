"""
Paper Analyzer — Groq API with Llama 3 (FREE, works worldwide)
3 papers per day with high-level mechanistic academic analysis
"""
import json, logging, time, re
import urllib.request, urllib.error
import config

logger = logging.getLogger(__name__)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ANALYSIS_PROMPT = """You are a scientific analyst specializing in biogeochemistry and agroecosystem research. Produce a high-level academic summary written in formal scientific language.

TODAY'S THEME: {theme}
OPEN ACCESS: {open_access}

PAPER:
Title: {title}
Authors: {authors}
Journal: {journal}
Year: {year}
DOI: {doi}
Abstract: {abstract}

Your task is to analyze this paper and return ONLY valid JSON — no markdown, no preamble, no text outside the JSON.

The field "mechanistic_analysis" must be a single continuous prose paragraph (minimum 300 words) written in formal scientific language that integrates ALL of the following in logical sequence:
1. The central research question stated precisely
2. The hypothesis including expected directional or nonlinear responses
3. The methodology: experimental design, treatments or gradients tested, measurement techniques, statistical or modeling approaches
4. The main quantitative findings: statistical significance, thresholds or breakpoints, rates of increase or decrease, nonlinear or exponential patterns, temporal dynamics
5. The mechanisms: biogeochemical pathways, mode of action, controlling variables (e.g., WFPS%, NO3- levels, temperature thresholds), process shifts
6. Assumptions clearly flagged using phrases such as "The authors assumed that..." or "It was hypothesized but not directly measured that..."
7. A mechanistic conclusion strictly limited to what the data support

Rules for mechanistic_analysis:
- No bullet points
- No section headings
- No simplification of terminology
- No AI commentary or general statements like "this study highlights the importance of"
- No vague wording like "increased a lot" or "strong effect"
- Prioritize mechanisms over description
- Do not add interpretation not explicitly supported by results
- Use formal scientific language appropriate for high-impact journals

Return ONLY this JSON with no extra text outside it:
{{
  "full_citation_apa": "Authors (Year). Title. Journal, Volume(Issue), Pages. https://doi.org/DOI",
  "doi_link": "https://doi.org/{doi}",
  "journal_name": "{journal}",
  "journal_impact_note": "Brief factual note on journal scope and impact factor if known",
  "open_access_status": "Open Access" or "Non-Open Access (analysis based on abstract only)",
  "study_region": "Specific country, region, or Global",
  "research_gap_addressed": "One precise sentence: what specific knowledge gap did this study fill?",
  "mechanistic_analysis": "FULL continuous prose paragraph — minimum 300 words — covering research question, hypothesis, methodology, quantitative results with statistics, mechanisms, assumptions, and mechanistic conclusion. Formal scientific language. No bullets. No headings.",
  "key_results_quantified": "Exhaustive list of ALL specific quantitative results: exact % changes, p-values, R² values, emission factors, yield values, thresholds, concentrations — every number reported",
  "emerging_trends": "What new research direction or field-level trend does this paper reveal?",
  "highlighted_gaps": "Specific remaining knowledge gaps identified by the authors after this study",
  "practical_implications": "Concrete actionable recommendations for farmers, advisors, or policymakers — derived strictly from the results",
  "limitations": "All limitations, caveats, and uncertainties explicitly stated in the paper",
  "keywords_extracted": ["kw1", "kw2", "kw3", "kw4", "kw5"]
}}"""

SYNTHESIS_PROMPT = """You are a world-leading expert in phosphorus nutrition, soil GHG emissions, and sustainable agriculture writing for a high-impact journal audience.

Synthesize these {n} deeply analyzed papers on the theme "{theme}".
Return ONLY valid JSON — no markdown, no preamble, no text outside the JSON.

PAPERS:
{summaries}

Return ONLY this JSON:
{{
  "thematic_introduction": "120-word formal scientific introduction to today's theme — its relevance to climate change mitigation and food security, current state of knowledge, and why these papers matter",
  "synthesis_paragraph": "250-word formal scientific paragraph integrating all papers — showing convergences, divergences, mechanistic links, and how they collectively advance the field. Use formal language. No bullet points.",
  "key_takeaway": "One precise, specific, mechanistically grounded sentence — the single most important scientific insight from today's papers",
  "emerging_pattern": "The strongest convergent finding or mechanistic pattern across papers, stated with precision",
  "research_gap": "The most critical unresolved mechanistic or empirical question revealed by today's papers combined",
  "contradictions": "Any conflicting quantitative findings or mechanistic interpretations between papers, stated precisely — or write: No major contradictions identified",
  "practical_implication": "One concrete, evidence-based recommendation for climate-smart phosphorus management derived strictly from today's results"
}}"""


def _call_groq(prompt: str, retries=3) -> str:
    if not config.GROQ_API_KEY:
        logger.error("GROQ_API_KEY is missing — add it to GitHub Secrets")
        return ""
    body = json.dumps({
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 3000,
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
    open_access = "Yes — full text available" if (
        paper.get("open_access") or
        (paper.get("url", "")).endswith(".pdf")
    ) else "No — analysis based on abstract only"

    prompt = ANALYSIS_PROMPT.format(
        theme       = theme["name"],
        open_access = open_access,
        title       = paper.get("title", "N/A"),
        authors     = paper.get("authors", "N/A"),
        journal     = paper.get("journal", "N/A"),
        year        = paper.get("year", "N/A"),
        doi         = paper.get("doi", "N/A"),
        abstract    = (paper.get("abstract") or "Abstract not available.")[:3000])

    raw = _call_groq(prompt)
    if not raw:
        return paper
    try:
        analysis = _parse_json(raw)
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
        logger.warning("Failed to parse Groq response: %s | Raw: %s", e, raw[:300])
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
            f"  Mechanistic analysis excerpt: {a.get('mechanistic_analysis', '')[:500]}\n"
            f"  Quantified results: {a.get('key_results_quantified', '')[:300]}\n"
            f"  Emerging trends: {a.get('emerging_trends', '')[:200]}\n")

    prompt = SYNTHESIS_PROMPT.format(
        n         = len(papers),
        theme     = theme["name"],
        summaries = "\n\n".join(summaries))

    raw = _call_groq(prompt)
    fallback = {
        "thematic_introduction": theme["name"],
        "synthesis_paragraph": "See individual paper analyses above.",
        "key_takeaway": "Review the detailed mechanistic analyses above.",
        "emerging_pattern": "N/A", "research_gap": "N/A",
        "contradictions": "N/A", "practical_implication": "N/A"}
    if not raw:
        return fallback
    try:
        return _parse_json(raw)
    except Exception as e:
        logger.error("Synthesis parse error: %s", e)
        return fallback
