"""
Telegram delivery — deep format for 3 papers per day.
Uses only Python standard library.
"""
import json, logging, re, time
import urllib.request
import config

logger = logging.getLogger(__name__)
API     = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
MAX_LEN = 4000


def _esc(text: str) -> str:
    """Escape all MarkdownV2 special characters."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text or ""))


def _send(text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials missing")
        return False
    payload = json.dumps({
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }).encode()
    try:
        req = urllib.request.Request(
            f"{API}/sendMessage", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if not result.get("ok"):
                logger.warning("Telegram API error: %s", result)
                # Retry without markdown if formatting error
                if result.get("error_code") == 400:
                    return _send_plain(str(text))
                return False
        return True
    except Exception as e:
        logger.error("Telegram send error: %s", e)
        return False


def _send_plain(text: str) -> bool:
    """Fallback: send as plain text without markdown."""
    clean = re.sub(r"[*_`\[\]]", "", text)
    payload = json.dumps({
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": clean[:4000],
        "disable_web_page_preview": True,
    }).encode()
    try:
        req = urllib.request.Request(
            f"{API}/sendMessage", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        logger.error("Plain send error: %s", e)
        return False


def _split_send(text: str) -> bool:
    parts, ok = [], True
    while len(text) > MAX_LEN:
        cut = text.rfind("\n", 0, MAX_LEN)
        if cut == -1:
            cut = MAX_LEN
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    for p in parts:
        if p.strip():
            if not _send(p):
                ok = False
            time.sleep(1.5)
    return ok


def _paper_block(idx: int, paper: dict) -> str:
    """Format one paper with deep structured analysis."""
    a = {}
    try:
        a = json.loads(paper.get("full_summary") or "{}")
    except Exception:
        pass

    e = _esc

    # Core fields
    citation    = a.get("full_citation_apa") or (
        f"{paper.get('authors','')[:80]} ({paper.get('year','')}). "
        f"{paper.get('title','')}. {paper.get('journal','')}")
    doi_link    = a.get("doi_link") or paper.get("url") or ""
    oa_status   = a.get("open_access_status", "Unknown")
    region      = a.get("study_region") or paper.get("study_region", "")
    methods     = a.get("methodology") or paper.get("methodology", "")
    gap_address = a.get("research_gap_addressed", "")
    findings    = a.get("main_findings") or paper.get("key_findings", "")
    quantified  = a.get("key_results_quantified") or paper.get("ghg_result", "")
    trends      = a.get("emerging_trends", "")
    open_gaps   = a.get("highlighted_gaps", "")
    ghg_contrib = a.get("ghg_mitigation_contribution", "")
    p_contrib   = a.get("p_management_contribution", "")
    impl        = a.get("practical_implications") or paper.get("implications", "")
    limits      = a.get("limitations") or paper.get("limitations", "")
    why         = a.get("why_it_matters", "")

    # Open access badge
    oa_badge = "🔓 Open Access" if "open access" in oa_status.lower() else "🔒 Non-Open Access"

    b  = "━━━━━━━━━━━━━━━━━━━━━━━\n"
    b += f"📄 *PAPER {idx} OF {config.PAPERS_PER_DAY}*\n\n"

    # Reference
    b += f"*📚 Full Reference*\n{e(citation)}\n\n"

    # Metadata line
    meta_parts = []
    if region:    meta_parts.append(f"🌍 {region}")
    meta_parts.append(oa_badge)
    if meta_parts: b += e(" | ".join(meta_parts)) + "\n\n"

    # Why it matters
    if why: b += f"*💡 Why It Matters*\n{e(why)}\n\n"

    # Methods
    if methods: b += f"*🔬 Methodology*\n{e(methods)}\n\n"

    # Research gap addressed
    if gap_address: b += f"*🎯 Research Gap Addressed*\n{e(gap_address)}\n\n"

    # Main findings (full)
    if findings: b += f"*📊 Main Findings*\n{e(findings)}\n\n"

    # Quantified results
    if quantified: b += f"*📈 Key Quantified Results*\n{e(quantified)}\n\n"

    # GHG + P contributions
    if ghg_contrib: b += f"*🌡️ GHG Mitigation Contribution*\n{e(ghg_contrib)}\n\n"
    if p_contrib:   b += f"*🌱 P Management Contribution*\n{e(p_contrib)}\n\n"

    # Emerging trends
    if trends: b += f"*🚀 Emerging Trends*\n{e(trends)}\n\n"

    # Highlighted open gaps
    if open_gaps: b += f"*🔍 Remaining Research Gaps*\n{e(open_gaps)}\n\n"

    # Practical implications
    if impl: b += f"*✅ Practical Implications*\n{e(impl)}\n\n"

    # Limitations
    if limits: b += f"*⚠️ Limitations*\n{e(limits)}\n\n"

    # Link
    if doi_link: b += f"*🔗 Link:* {e(doi_link)}\n"

    return b


def send_digest(papers: list, theme: dict, synthesis: dict, date_str: str) -> bool:
    e    = _esc
    msgs = []

    # Header
    intro = synthesis.get("thematic_introduction", "")
    oa_count  = sum(1 for p in papers
                    if "open access" in str(p.get("open_access_status","")).lower())
    noa_count = len(papers) - oa_count

    msgs.append(
        f"🌿 *DAILY RESEARCH DIGEST*\n"
        f"📅 {e(date_str)}\n\n"
        f"{theme['emoji']} *Theme of the Day:*\n"
        f"*{e(theme['name'])}*\n\n"
        f"{e(intro)}\n\n"
        f"_{e(f'Presenting {len(papers)} deeply analyzed peer-reviewed papers')}_\n"
        f"_{e(f'🔓 {oa_count} Open Access  |  🔒 {noa_count} Non-Open Access')}_\n")

    # Papers
    for i, p in enumerate(papers, 1):
        msgs.append(_paper_block(i, p))

    # Synthesis footer
    synth  = synthesis.get("synthesis_paragraph", "")
    tk     = synthesis.get("key_takeaway", "")
    ep     = synthesis.get("emerging_pattern", "")
    gap    = synthesis.get("research_gap", "")
    prac   = synthesis.get("practical_implication", "")
    contra = synthesis.get("contradictions", "")

    footer  = "━━━━━━━━━━━━━━━━━━━━━━━\n"
    footer += f"🧠 *TODAY'S SYNTHESIS*\n\n{e(synth)}\n\n"
    if contra and "no major" not in contra.lower():
        footer += f"⚡ *Contradictions Between Papers*\n{e(contra)}\n\n"
    footer += (
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔎 *Emerging Pattern*\n{e(ep)}\n\n"
        f"📌 *Open Research Gap*\n{e(gap)}\n\n"
        f"🌍 *Practical Implication for Climate\\-Smart Agriculture*\n{e(prac)}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *KEY TAKEAWAY OF THE DAY*\n\n_{e(tk)}_\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 _Powered by Groq AI \\| Free P & GHG Research Monitor_")
    msgs.append(footer)

    ok = True
    for m in msgs:
        if not _split_send(m):
            ok = False
    return ok


def send_test() -> bool:
    return _send(
        "✅ *Research Agent Connected\\!*\n\n"
        "Your GHG \\& Phosphorus Research Agent is ready\\.\n"
        "Powered by Groq AI \\(Llama 3\\) \\| 3 deep papers per day\\.")


def send_error(msg: str):
    _send(f"⚠️ *Research Agent Error*\n\n{_esc(msg)}")
