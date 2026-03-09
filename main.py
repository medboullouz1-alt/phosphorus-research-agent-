"""
Main pipeline — runs once per day via GitHub Actions.
"""
import logging, sys, time
from datetime import datetime, timezone
from pathlib import Path

import config, database, search_engine, paper_analyzer, telegram_sender

Path("data").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_PATH, encoding="utf-8"),
    ])
logger = logging.getLogger("main")


def run():
    start    = time.time()
    date_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info("=" * 55)
    logger.info("PIPELINE START — %s", date_str)
    logger.info("=" * 55)

    database.init_db()
    theme = config.get_today_theme()
    logger.info("Theme: %s %s", theme["emoji"], theme["name"])

    # 1 — Search
    candidates = search_engine.search_literature(theme, n=config.PAPERS_PER_DAY + 5)
    if len(candidates) < 3:
        msg = f"Only {len(candidates)} papers found — skipping today."
        logger.warning(msg)
        telegram_sender.send_error(msg)
        return

    # 2 — Analyze
    analyzed, ids = [], []
    for i, paper in enumerate(candidates[:config.PAPERS_PER_DAY], 1):
        logger.info("Analyzing %d/%d: %s", i, config.PAPERS_PER_DAY,
                    (paper.get("title") or "")[:70])
        paper["theme"] = theme["name"]
        paper = paper_analyzer.analyze_paper(paper, theme)
        analyzed.append(paper)
        pid = database.save_paper(paper)
        ids.append(pid)
        time.sleep(4)

    # 3 — Synthesize
    logger.info("Generating synthesis...")
    synthesis = paper_analyzer.synthesize_papers(analyzed, theme)
    time.sleep(4)

    # 4 — Deliver
    logger.info("Sending Telegram digest...")
    sent = telegram_sender.send_digest(analyzed, theme, synthesis, date_str)
    logger.info("Telegram sent: %s", sent)

    # 5 — Archive
    database.save_digest({
        "date": date_key,
        "theme": theme["name"],
        "paper_ids": ids,
        "synthesis": synthesis.get("synthesis_paragraph"),
        "key_takeaway": synthesis.get("key_takeaway"),
        "emerging_pattern": synthesis.get("emerging_pattern"),
        "research_gap": synthesis.get("research_gap"),
        "practical_impl": synthesis.get("practical_implication"),
        "telegram_sent": sent
    })
    database.export_csv()
    logger.info("Done in %.1f seconds | Papers: %d", time.time() - start, len(analyzed))


if __name__ == "__main__":
    if "--test-telegram" in sys.argv:
        ok = telegram_sender.send_test()
        print("✅ Telegram test sent" if ok else "❌ Telegram test FAILED")
    elif "--show-theme" in sys.argv:
        t = config.get_today_theme()
        print(f"\n{t['emoji']} TODAY'S THEME: {t['name']}\n   {t['description']}\n")
    else:
        run()
