"""
Telegram delivery — sends title, full reference, and abstract.
"""
import json, logging, re, time
import urllib.request
import config

logger = logging.getLogger(__name__)
API     = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
MAX_LEN = 4000


def _esc(text: str) -> str:
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
                logger.warning("Telegram error: %s", result)
                return _send_plain(text)
        return True
    except Exception as e:
        logger.error("Telegram send error: %s", e)
        return False


def _send_plain(text: str) -> bool:
    clean = re.sub(r"[*_`\[\]\\]", "", text)
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
    e = _esc

    title    = paper.get("title", "No title")
    authors  = paper.get("authors", "Unknown authors")
    journal  = paper.get("journal", "Unknown journal")
    year     = paper.get("year", "")
    doi      = paper.get("doi", "")
    url      = paper.get("url", "")
    abstract = paper.get("abstract", "Abstract not available.")
    oa       = paper.get("open_access", False)
    citations = paper.get("citation_count", 0)

    # Build APA-style reference
    apa = f"{authors} ({year}). {title}. {journal}."
    if doi:
        apa += f" https://doi.org/{doi}"

    oa_badge = "🔓 Open Access" if oa else "🔒 Non\\-Open Access"
    link = f"https://doi.org/{doi}" if doi else url

    b  = "━━━━━━━━━━━━━━━━━━━━━━━\n"
    b += f"📄 *PAPER {idx}*\n\n"
    b += f"*📌 Title*\n{e(title)}\n\n"
    b += f"*📚 Full Reference*\n{e(apa)}\n\n"
    b += f"{oa_badge}"
    if citations:
        b += f" \\| 🔢 {e(str(citations))} citations"
    b += "\n\n"
    b += f"*📝 Abstract*\n{e(abstract)}\n\n"
    if link:
        b += f"*🔗 Link:* {e(link)}\n"
    return b


def send_digest(papers: list, theme: dict, synthesis: dict, date_str: str) -> bool:
    e    = _esc
    msgs = []

    intro = synthesis.get("thematic_introduction", theme.get("description", ""))

    # Header
    msgs.append(
        f"🌿 *DAILY RESEARCH DIGEST*\n"
        f"📅 {e(date_str)}\n\n"
        f"{theme['emoji']} *Theme of the Day:*\n"
        f"*{e(theme['name'])}*\n\n"
        f"{e(intro)}\n")

    # One paper block
    for i, p in enumerate(papers, 1):
        msgs.append(_paper_block(i, p))

    # Simple footer
    msgs.append(
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 _Free P & GHG Research Monitor \\| Daily Literature Update_")

    ok = True
    for m in msgs:
        if not _split_send(m):
            ok = False
    return ok


def send_test() -> bool:
    return _send(
        "✅ *Research Agent Connected\\!*\n\n"
        "Your daily P & GHG literature digest is ready\\.\n"
        "You will receive 1 paper with full reference and abstract every morning\\.")


def send_error(msg: str):
    _send(f"⚠️ *Research Agent Error*\n\n{_esc(msg)}")
