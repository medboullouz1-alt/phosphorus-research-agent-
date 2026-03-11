"""
Paper Analyzer — Groq API, 1 deep mechanistic paper per day
"""
import json, logging, time, re
import urllib.request, urllib.error
import config

logger = logging.getLogger(__name__)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ANALYSIS_PROMPT = """You are a scientific analyst specializing in biogeochemistry and agroecosystem research. Analyze the paper below.

THEME: {theme}
TITLE: {title}
AUTHORS: {authors}
JOURNAL: {journal}
YEAR: {year}
DOI: {doi}
ABSTRACT: {abstract}

Return a JSON object. The mechanistic_analysis field must be a continuous prose paragraph of at least 400 words in formal scientific language covering:
1. The central research question stated precisely
2. The hypothesis including expected directional or nonlinear responses
3. The methodology: experimental design, treatments, measurement techniques, statistical approaches
4. The main quantitative findings with exact statistics, thresholds, rates, nonlinear patterns, temporal dynamics
5. The biogeochemical mechanisms: pathways, controlling variables such as WFPS percent, NO3- levels, temperature thresholds, process shifts
6. Assumptions flagged explicitly as: "The authors assumed that..." or "It was hypothesized but not directly measured that..."
7. A mechanistic conclusion strictly limited to what the data support

Rules: no bullet points, no headings, no vague language, every number must include its statistical test, formal scientific vocabulary throughout, minimum 400 words.

Respond with ONLY the following JSON and nothing else before or after it:

{{"full_citation_apa": "full APA citation here","doi_link": "https://doi.org/{doi}","journal_name": "{journal}","journal_impact_note": "journal scope and impact factor if known","open_access_status": "Open Access or Non-Open Access (analysis based on abstract only)","study_region": "country or region or Global","research_gap_addressed": "one precise sentence on the knowledge gap this study filled","mechanistic_analysis": "MINIMUM 400 WORDS of continuous formal scientific prose here","key_results_quantified": "every quantitative result with exact values p-values R2 thresholds","emerging_trends": "new research direction this paper reveals","highlighted_gaps": "remaining knowledge gaps authors identified","practical_implications": "concrete recommendations for farmers advisors policymakers","limitations": "all limitations caveats uncertainties from the paper","keywords_extracted": ["kw1","kw2","kw3","kw4","kw5"]}}"""

SYNTHESIS_PROMPT = """You are an expert in phosphorus nutrition and soil GHG emissions.

Write a synthesis for this paper on the theme "{theme}".

PAPER ANALYSIS:
{summaries}

Respond with ONLY the following JSON and nothing else before or after it:

{{"thematic_introduction": "120-word formal scientific introduction to this theme","synthesis_paragraph": "200-word formal paragraph on how this paper advances the field","key_takeaway": "one precise mechanistically grounded sentence","emerging_pattern": "strongest mechanistic finding stated precisely","research_gap": "most critical unresolved question after this paper","contradictions": "No major contradictions identified","practical_implication": "one concrete evidence-based recommendation for climate-smart P management"}}"""


def _call_groq(prompt: str, retries=3) -> str:
    if not config.GROQ_API_KEY:
        logger.error("GROQ_API_KEY is missing")
        return ""
    body = json.dumps({
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4000,
    })
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                GROQ_URL, data=body.encode(), method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.GROQ_API_KEY}"
                })
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            logger.info("Groq OK — response length: %d chars", len(content))
            logger.info("Groq raw preview: %s", content[:300])
            return content
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()[:400]
            except Exception:
                pass
            if e.code == 429:
                logger.warning("Rate limit — waiting 40s...")
                time.sleep(40)
            else:
                logger.error("Groq HTTP %d attempt %d: %s", e.code, attempt + 1, err_body)
                time.sleep(5)
        except Exception as e:
            logger.error("Groq error attempt %d: %s", attempt + 1, e)
            time.sleep(5)
    return ""


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    # Remove markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
    raw = raw.strip()
    # Extract outermost JSON object
    start = raw.find("{")
    end   = raw.rfind("}")
    if start == -1 or end == -1:
        logger.error("No JSON braces found. Raw: %s", raw[:400])
        raise ValueError("No JSON found")
    raw = raw[start:end + 1]
    # Attempt direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e1:
        logger.warning("Direct JSON parse failed: %s — trying repair", e1)
        # Replace unescaped newlines inside string values
        try:
            repaired = re.sub(r'(?<!\\)\n', '\\n', raw)
            return json.loads(repaired)
        except json.JSONDecodeError as e2:
            logger.error("Repaired JSON also failed: %s", e2)
            logger.error("JSON content: %s", raw[:600])
            raise


def analyze_paper(paper: dict, theme: dict) -> dict:
    open_access = (
        "Yes — full text available"
        if (paper.get("open_access") or paper.get("url", "").endswith(".pdf"))
        else "No — use abstract only")

    prompt = ANALYSIS_PROMPT.format(
        theme    = theme["name"],
        title    = paper.get("title", "N/A"),
        authors  = paper.get("authors", "N/A"),
        journal  = paper.get("journal", "N/A"),
        year     = paper.get("year", "N/A"),
        doi      = paper.get("doi", "N/A"),
        abstract = (paper.get("abstract") or "Abstract not available.")[:3000])

    logger.info("Calling Groq for: %s", paper.get("title", "")[:80])
    raw = _call_groq(prompt)

    if not raw:
        logger.error("Groq returned empty response")
        return paper

    try:
        analysis = _parse_json(raw)
        mech_len = len(analysis.get("mechanistic_analysis", ""))
        logger.info("mechanistic_analysis length: %d words", len(analysis.get("mechanistic_analysis","").split()))
        paper.update(analysis)
        paper["keywords"]     = json.dumps(analysis.get("keywords_extracted", []))
        paper["key_findings"] = analysis.get("mechanistic_analysis", "")
        paper["methodology"]  = analysis.get("mechanistic_analysis", "")[:200]
        paper["study_region"] = analysis.get("study_region", "")
        paper["ghg_result"]   = analysis.get("key_results_quantified", "")
        paper["implications"] = analysis.get("practical_implications", "")
        paper["limitations"]  = analysis.get("limitations", "")
        paper["full_summary"] = json.dumps(analysis, ensure_ascii=False)
        logger.info("Paper analysis saved successfully")
    except Exception as e:
        logger.error("Parse failed: %s", e)
        logger.error("Full raw response: %s", raw[:1000])
    return paper


def synthesize_papers(papers: list, theme: dict) -> dict:
    summaries = []
    for i, p in enumerate(papers, 1):
        a = {}
        try:
            a = json.loads(p.get("full_summary") or "{}")
        except Exception:
            pass
        mechanistic = a.get("mechanistic_analysis", p.get("key_findings", "No analysis available"))
        summaries.append(
            f"Title: {p.get('title', '')}\n"
            f"Journal: {p.get('journal', '')}, {p.get('year', '')}\n"
            f"Research gap: {a.get('research_gap_addressed', '')}\n"
            f"Analysis: {mechanistic[:800]}\n"
            f"Results: {a.get('key_results_quantified', '')[:300]}\n")

    prompt = SYNTHESIS_PROMPT.format(
        theme     = theme["name"],
        summaries = "\n\n".join(summaries))

    fallback = {
        "thematic_introduction": theme.get("description", theme["name"]),
        "synthesis_paragraph": "See mechanistic analysis above.",
        "key_takeaway": "See mechanistic analysis above.",
        "emerging_pattern": "See mechanistic analysis above.",
        "research_gap": "See highlighted gaps above.",
        "contradictions": "No major contradictions identified",
        "practical_implication": "See practical implications above."}

    raw = _call_groq(prompt)
    if not raw:
        return fallback
    try:
        result = _parse_json(raw)
        logger.info("Synthesis parsed OK")
        return result
    except Exception as e:
        logger.error("Synthesis parse error: %s", e)
        return fallback
```

---

## What this fixes

The previous version was failing because the JSON had unescaped characters inside the long `mechanistic_analysis` string, breaking the parser silently. This version:

- Logs the **raw Groq response** so you can see exactly what's returned if it fails again
- Has a **JSON repair** step that fixes common encoding issues
- Uses a **simpler, flatter prompt** that's easier for the model to follow
- Processes only **1 paper** — much less chance of timeout or token limit issues

After committing both files → **Actions → Run workflow** → check the logs for the line:
```
mechanistic_analysis length: XXX words
