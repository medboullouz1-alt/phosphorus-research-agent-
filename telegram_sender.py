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
    a = {}
    try:
        a = json.loads(paper.get("full_summary") or "{}")
    except Exception:
        pass

    e = _esc

    citation    = a.get("full_citation_apa") or (
        f"{paper.get('authors','')[:80]} ({paper.get('year','')}). "
        f"{paper.get('title','')}. {paper.get('journal','')}")
    doi_link    = a.get("doi_link") or paper.get("url") or ""
    oa_status   = a.get("open_access_status", "Unknown")
    region      = a.get("study_region") or paper.get("study_region", "")
    gap_address = a.get("research_gap_addressed", "")
    analysis    = a.get("mechanistic_analysis") or paper.get("key_findings", "")
    quantified  = a.get("key_results_quantified") or paper.get("ghg_result", "")
    trends      = a.get("emerging_trends", "")
    open_gaps   = a.get("highlighted_gaps", "")
    impl        = a.get("practical_implications") or paper.get("implications", "")
    limits      = a.get("limitations") or paper.get("limitations", "")
    j_note      = a.get("journal_impact_note", "")

    oa_badge = "🔓 Open Access" if "open access" in oa_status.lower() else "🔒 Non\\-Open Access \\(abstract only\\)"

    b  = "━━━━━━━━━━━━━━━━━━━━━━━\n"
    b += f"📄 *PAPER {idx} OF {config.PAPERS_PER_DAY}*\n\n"
    b += f"*📚 Full Reference*\n{e(citation)}\n\n"

    meta = []
    if region:  meta.append(f"🌍 {region}")
    meta.append(oa_badge)
    if j_note:  meta.append(f"📰 {e(j_note)}")
    if meta:    b += "\n".join(meta) + "\n\n"

    if gap_address:
        b += f"*🎯 Research Gap Addressed*\n{e(gap_address)}\n\n"

    if analysis:
        b += f"*🔬 Mechanistic Analysis*\n{e(analysis)}\n\n"

    if quantified:
        b += f"*📈 Quantified Results*\n{e(quantified)}\n\n"

    if trends:
        b += f"*🚀 Emerging Trends*\n{e(trends)}\n\n"

    if open_gaps:
        b += f"*🔍 Remaining Research Gaps*\n{e(open_gaps)}\n\n"

    if impl:
        b += f"*✅ Practical Implications*\n{e(impl)}\n\n"

    if limits:
        b += f"*⚠️ Limitations*\n{e(limits)}\n\n"

    if doi_link:
        b += f"*🔗 Link:* {e(doi_link)}\n"

    return b
