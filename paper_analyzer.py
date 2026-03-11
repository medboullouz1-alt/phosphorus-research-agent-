"""
Paper Analyzer — No AI. Just returns paper metadata and abstract.
"""
import json, logging
import config

logger = logging.getLogger(__name__)


def analyze_paper(paper: dict, theme: dict) -> dict:
    """No analysis — just pass the paper through as-is."""
    paper["theme"] = theme["name"]
    paper["full_summary"] = json.dumps({
        "title": paper.get("title", ""),
        "authors": paper.get("authors", ""),
        "journal": paper.get("journal", ""),
        "year": paper.get("year", ""),
        "doi": paper.get("doi", ""),
        "abstract": paper.get("abstract", "Abstract not available."),
        "url": paper.get("url", ""),
        "open_access": paper.get("open_access", False),
        "citation_count": paper.get("citation_count", 0),
    })
    logger.info("Paper ready: %s", paper.get("title", "")[:80])
    return paper


def synthesize_papers(papers: list, theme: dict) -> dict:
    """Simple theme intro — no AI."""
    return {
        "thematic_introduction": theme.get("description", theme["name"]),
        "synthesis_paragraph": "",
        "key_takeaway": "",
        "emerging_pattern": "",
        "research_gap": "",
        "contradictions": "",
        "practical_implication": ""
    }
