"""
Telegram delivery — formats and sends the daily digest.
Uses only Python standard library — no pip install needed.
"""
import json, logging, re, time
import urllib.request
import config

logger = logging.getLogger(__name__)
API     = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
MAX_LEN = 4000


def _esc(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    return re.sub(r"([_*\[\]()~`>#+=|{}.!\\-])", r"\\\1", str(text or ""))


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
                return False
        return True
    except Exception as e:
        logger.error("Telegram send error: %s", e)
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
    citation = (
        a.get("full_citation_apa") or
        f"{paper.get('authors','')[:60]}... ({paper.get('year','')}). "
        f"{paper.get('title','')}. {paper.get('journal','')}")
    doi_link = a.get("doi_link") or paper.get("url") or ""
    why      = a.get("why_it_matters", "")
    methods  = a.get("methodology") or paper.get("methodology", "")
    findings = a.get("key_findings") or paper.get("key_findings", "")
    results  = a.get("quantified_results") or paper.get("ghg_result", "N/A")
    impl     = a.get("practical_implications") or paper.get("implications", "")
    limits   = a.get("limitations") or paper.get("limitations", "")
    region   = a.get("study_region") or paper.get("study_region", "")
    e = _esc
    b  = "━━━━━━━━━━━━━━━━━━━━━━━\n"
    b += f"📄 *Paper {idx}*\n\n"
    b += f"*📚 Full Reference*\n{e(citation)}\n\n"
    if region:   b += f"🌍 *Region:* {e(region)}\n\n"
    if why:      b += f"*💡 Why It Matters*\n{e(why)}\n\n"
    if methods:  b += f"*🔬 Methods*\n{e(methods)}\n\n"
    if findings: b += f"*📊 Key Findings*\n{e(findings)}\n\n"
    if results:  b += f"*📈 Quantified Results*\n{e(results)}\n\n"
    if impl:     b += f"*✅ Practical Implications*\n{e(impl)}\n\n"
    if limits:   b += f"*⚠️ Limitations*\n{e(limits)}\n\n"
    if doi_link: b += f"*🔗 Link:* {e(doi_link)}\n"
    return b


def send_digest(papers: list, theme: dict, synthesis: dict, date_str: str) -> bool:
    e    = _esc
    msgs = []
    intro = synthesis.get("thematic_introduction", "")
    msgs.append(
        f"🌿 *DAILY RESEARCH DIGEST*\n"
        f"📅 {e(date_str)}\n\n"
        f"{theme['emoji']} *Theme of the Day:*\n"
        f"*{e(theme['name'])}*\n\n"
        f"{e(intro)}\n\n"
        f"_{e('Analyzing ' + str(len(papers)) + ' peer-reviewed papers...')}_\n")
    for i, p in enumerate(papers, 1):
        msgs.append(_paper_block(i, p))
    synth  = synthesis.get("synthesis_paragraph", "")
    tk     = synthesis.get("key_takeaway", "")
    ep     = synthesis.get("emerging_pattern", "")
    gap    = synthesis.get("research_gap", "")
    prac   = synthesis.get("practical_implication", "")
    contra = synthesis.get("contradictions", "")
    footer  = "━━━━━━━━━━━━━━━━━━━━━━━\n"
    footer += f"🧠 *TODAY'S SYNTHESIS*\n\n{e(synth)}\n\n"
    if contra and "none" not in contra.lower():
        footer += f"⚡ *Contradictions:* {e(contra)}\n\n"
    footer += (
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔎 *Emerging Pattern*\n{e(ep)}\n\n"
        f"📌 *Research Gap*\n{e(gap)}\n\n"
        f"🌍 *Practical Implication for Climate\\-Smart Agriculture*\n{e(prac)}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *KEY TAKEAWAY OF THE DAY*\n\n_{e(tk)}_\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 _Powered by Gemini AI \\| Free P & GHG Research Monitor_")
    msgs.append(footer)
    ok = True
    for m in msgs:
        if not _split_send(m):
            ok = False
    return ok


def send_test() -> bool:
    return _send(
        "✅ *Research Agent Connected\\!*\n\n"
        "Your GHG \\& Phosphorus Research Agent is correctly configured\\.\n"
        "You will receive your first digest on the next scheduled run\\.")


def send_error(msg: str):
    _send(f"⚠️ *Research Agent Error*\n\n{_esc(msg)}")
```

---

## Also create — `data/README.md`

Create a file with **exactly this path**: `data/README.md`
```
This folder stores the SQLite database and CSV export.
Both files are automatically created and updated by the agent after each daily run.
```

---

## ✅ Checklist — your repository must contain these files:
```
main.py
config.py
database.py
search_engine.py
paper_analyzer.py
telegram_sender.py
requirements.txt          ← already there from earlier
.github/
  workflows/
    daily_digest.yml      ← already there from earlier
data/
  README.md
