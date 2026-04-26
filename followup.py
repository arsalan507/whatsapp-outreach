#!/usr/bin/env python3
"""
Follow-up — tally replies on previously sent conversations and send
image+caption follow-ups to non-responders.

Usage:
  python3 followup.py --tally               # screenshot every sent chat, detect replies
  python3 followup.py --dry-run             # preview follow-ups
  python3 followup.py --send --limit 20     # send 20 follow-ups
  python3 followup.py --send --min-days 5   # only follow up if original sent >= 5 days ago

A sent chat enters the follow-up pool when:
  - it's older than --min-days
  - the phone is not in sent/followup_log.json
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT            = Path(__file__).parent
CONFIG          = yaml.safe_load((ROOT / "config.yaml").read_text())
SENT_LOG        = ROOT / "sent" / "sent_log.json"
FOLLOWUP_LOG    = ROOT / "sent" / "followup_log.json"
SCREENSHOTS_DIR = ROOT / "screenshots"
WA_SESSION_DIR  = os.path.expanduser("~/.whatsapp-automation")

COUNTRY_CODE   = os.getenv("COUNTRY_CODE", "91")
SENDER_NAME    = os.getenv("SENDER_NAME", "Sender")
SENDER_PHONE   = os.getenv("SENDER_PHONE", "")
SENDER_BRAND   = os.getenv("SENDER_BRAND", "")
DEFAULT_AREA   = os.getenv("DEFAULT_AREA", "your area")
MIN_DELAY_SEC  = int(os.getenv("MIN_DELAY_SEC", "50"))
MAX_DELAY_SEC  = int(os.getenv("MAX_DELAY_SEC", "100"))

FOLLOWUP_IMAGES   = CONFIG["followup"]["images"]
FOLLOWUP_ROTATION = CONFIG["followup"]["rotation"]

def load_json(p): return json.loads(p.read_text()) if p.exists() else {}
def save_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def short_name(full_name: str) -> str:
    parts = full_name.split("|")[0].split()
    for w in parts:
        if len(w) > 2:
            return w.title()
    return parts[0].title() if parts else "there"

def render_caption(template: str, lead: dict) -> str:
    return template.format(
        name=short_name(lead["name"]),
        area=lead.get("area") or DEFAULT_AREA,
        sender_name=SENDER_NAME, sender_phone=SENDER_PHONE, sender_brand=SENDER_BRAND,
    )

# ─── Tally: open each chat, screenshot, detect reply ─────────────────────────

def tally(limit: int = None):
    sent_log = load_json(SENT_LOG)
    if not sent_log:
        sys.exit("No sent_log — run send_whatsapp.py first.")

    entries = sorted(sent_log.items(), key=lambda x: x[1]["sent_at"], reverse=True)
    if limit:
        entries = entries[:limit]

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n📷 Tallying {len(entries)} conversations…")

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    results = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=WA_SESSION_DIR, headless=False,
            args=["--no-first-run"], viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        page.goto("https://web.whatsapp.com", timeout=30000)
        try:
            page.wait_for_selector('[data-testid="chat-list"]', timeout=45000)
            print("✅ WhatsApp logged in\n")
        except PWTimeout:
            print("❌ WhatsApp not logged in.")
            ctx.close()
            return []

        for phone, info in entries:
            print(f"  {info['name']} ({phone})…", end=" ", flush=True)
            try:
                page.goto(f"https://web.whatsapp.com/send?phone={COUNTRY_CODE}{phone}", timeout=30000)
                page.wait_for_selector('[data-testid="conversation-compose-box-input"]', timeout=20000)
                time.sleep(2.0)

                safe = "".join(c if c.isalnum() else "_" for c in info["name"])[:25]
                ts = datetime.now().strftime("%H%M%S")
                shot = str(SCREENSHOTS_DIR / f"tally_{phone}_{safe}_{ts}.png")
                page.screenshot(path=shot)

                replied = bool(
                    page.query_selector(".message-in") or
                    page.query_selector('[data-testid="msg-container"] [class*="message-in"]')
                )
                print("💬 REPLIED" if replied else "🔇 no reply")
                results.append({
                    "phone":    phone,
                    "name":     info["name"],
                    "category": info["category"],
                    "area":     info.get("area", ""),
                    "sent_at":  info["sent_at"][:10],
                    "replied":  replied,
                    "screenshot": shot,
                })
                time.sleep(random.uniform(4, 8))
            except Exception as e:
                print(f"❌ {str(e)[:60]}")
                results.append({"phone": phone, "name": info["name"],
                                "replied": False, "error": str(e)[:80]})

        ctx.close()

    replied  = [r for r in results if r.get("replied")]
    no_reply = [r for r in results if not r.get("replied") and not r.get("error")]
    print(f"\n📊 {len(replied)} replied / {len(no_reply)} no reply / "
          f"{len(results) - len(replied) - len(no_reply)} errors")
    if replied:
        print("\n✅ Replied:")
        for r in replied:
            print(f"   {r['name']} ({r['phone']}) | sent {r.get('sent_at','?')}")

    out = SCREENSHOTS_DIR / f"tally_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nTally saved → {out}")
    return results

# ─── Send follow-ups ─────────────────────────────────────────────────────────

def build_candidates(sent_log: dict, followup_log: dict, min_days: int):
    cutoff = datetime.now() - timedelta(days=min_days)
    out = []
    for phone, info in sent_log.items():
        if phone in followup_log:
            continue
        try:
            sent_at = datetime.fromisoformat(info["sent_at"])
        except Exception:
            continue
        if sent_at <= cutoff:
            out.append({
                "phone": phone, "name": info["name"], "category": info["category"],
                "area": info.get("area", ""), "sent_at": info["sent_at"][:10],
            })
    out.sort(key=lambda x: x["sent_at"])
    return out

def send_followups(pending: list, dry_run: bool):
    if not pending:
        print("No follow-ups pending.")
        return

    if dry_run:
        print(f"\n{'─'*65}\nDRY RUN — {len(pending)} follow-ups\n{'─'*65}")
        for i, l in enumerate(pending):
            key = FOLLOWUP_ROTATION[i % len(FOLLOWUP_ROTATION)]
            cap = render_caption(FOLLOWUP_IMAGES[key]["caption"], l)
            print(f"\n[{i+1}] {l['name']} ({l['phone']}) | {l['category']}")
            print(f"  Image: {key}\n  Caption: {cap[:100]}…")
        print(f"\nRun --send to fire {len(pending)} follow-ups.")
        return

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from send_whatsapp import send_image  # reuse the proven clipboard-paste sender

    followup_log = load_json(FOLLOWUP_LOG)
    print(f"\n🚀 Sending {len(pending)} follow-ups\n")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=WA_SESSION_DIR, headless=False,
            args=["--no-first-run"], viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.goto("https://web.whatsapp.com", timeout=30000)
        try:
            page.wait_for_selector('[data-testid="chat-list"]', timeout=45000)
        except PWTimeout:
            print("❌ WhatsApp not logged in.")
            ctx.close()
            return

        success = 0
        for i, lead in enumerate(pending, 1):
            key = FOLLOWUP_ROTATION[(i - 1) % len(FOLLOWUP_ROTATION)]
            img = FOLLOWUP_IMAGES[key]
            cap = render_caption(img["caption"], lead)
            print(f"[{i}/{len(pending)}] {lead['name']} ({lead['phone']}) → {key}")

            try:
                page.goto(f"https://web.whatsapp.com/send?phone={COUNTRY_CODE}{lead['phone']}",
                          timeout=30000)
                page.wait_for_selector('[data-testid="conversation-compose-box-input"]', timeout=20000)
                time.sleep(random.uniform(2, 3))

                if not send_image(page, img["path"], cap):
                    continue
                time.sleep(1.5)

                SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
                safe = "".join(c if c.isalnum() else "_" for c in lead["name"])[:25]
                shot = str(SCREENSHOTS_DIR / f"followup_{lead['phone']}_{safe}.png")
                page.screenshot(path=shot)

                followup_log[lead["phone"]] = {
                    "name": lead["name"], "category": lead["category"],
                    "sent_at": datetime.now().isoformat(),
                    "image_key": key, "screenshot": shot,
                }
                save_json(FOLLOWUP_LOG, followup_log)
                print("   ✅ Sent!")
                success += 1

            except Exception as e:
                print(f"   ❌ {str(e)[:70]}")

            if i < len(pending):
                d = random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC)
                print(f"   ⏱  {d:.0f}s")
                time.sleep(d)

        ctx.close()
    print(f"\n✅ Follow-ups: {success}/{len(pending)} sent")

# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WhatsApp follow-up manager")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tally",   action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--send",    action="store_true")
    parser.add_argument("--limit",    type=int, default=None)
    parser.add_argument("--min-days", type=int,
                        default=CONFIG["followup"]["min_days_after_send"])
    args = parser.parse_args()

    if args.tally:
        tally(limit=args.limit)
        return

    sent_log = load_json(SENT_LOG)
    if not sent_log:
        sys.exit("No sent_log — run send_whatsapp.py first.")

    pending = build_candidates(sent_log, load_json(FOLLOWUP_LOG), args.min_days)
    if args.limit:
        pending = pending[: args.limit]
    send_followups(pending, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
