#!/usr/bin/env python3
"""
WhatsApp Web outreach sender — text or image-with-caption messages,
sent via Playwright with randomised human-like delays.

Usage:
  python3 send_whatsapp.py --dry-run                      # preview
  python3 send_whatsapp.py --send --limit 20              # 20 text messages
  python3 send_whatsapp.py --send --images --limit 20     # with images
  python3 send_whatsapp.py --send --category ac           # filter by category
  python3 send_whatsapp.py --send --min-score 70          # only score >= 70
  python3 send_whatsapp.py --stats                        # print send stats

Reads:
  config.yaml  — categories, message templates, image paths
  .env         — Apify token, sender identity, delays
  leads/*.json — leads from process_leads.py
  sent/sent_log.json — phones already messaged (never re-sent)
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime
from glob import glob
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────

ROOT            = Path(__file__).parent
CONFIG          = yaml.safe_load((ROOT / "config.yaml").read_text())
LEADS_DIR       = ROOT / "leads"
SENT_LOG        = ROOT / "sent" / "sent_log.json"
SCREENSHOTS_DIR = ROOT / "screenshots"
WA_SESSION_DIR  = os.path.expanduser("~/.whatsapp-automation")

COUNTRY_CODE   = os.getenv("COUNTRY_CODE", "91")
SENDER_NAME    = os.getenv("SENDER_NAME", "Sender")
SENDER_PHONE   = os.getenv("SENDER_PHONE", "")
SENDER_BRAND   = os.getenv("SENDER_BRAND", "")
MIN_DELAY_SEC  = int(os.getenv("MIN_DELAY_SEC", "45"))
MAX_DELAY_SEC  = int(os.getenv("MAX_DELAY_SEC", "90"))

CATEGORY_KEYS  = list(CONFIG["categories"].keys())

# ─── Image rendering helpers ────────────────────────────────────────────────

def short_name(full_name: str) -> str:
    name = full_name.split("|")[0].strip()
    parts = name.split()
    return parts[0] if parts else "there"

def render_caption(template: str, lead: dict) -> str:
    return template.format(
        name=short_name(lead["name"]),
        area=lead.get("area") or os.getenv("DEFAULT_AREA", "your area"),
        service=CONFIG["categories"][lead["category"]]["service_name"],
        sender_name=SENDER_NAME,
        sender_phone=SENDER_PHONE,
        sender_brand=SENDER_BRAND,
    )

def get_image_for_lead(lead: dict, index: int):
    """Pick an image from rotation for this lead's category."""
    rotation = CONFIG["image_rotation"][lead["category"]]
    key = rotation[index % len(rotation)]
    img = CONFIG["images"][key]
    return {"key": key, "path": img["path"], "caption": render_caption(img["caption"], lead)}

# ─── Lead loading ───────────────────────────────────────────────────────────

def load_all_leads():
    out = {}
    for fp in sorted(glob(str(LEADS_DIR / "leads_*.json"))):
        for l in json.loads(Path(fp).read_text()):
            if l.get("phone"):
                out[l["phone"]] = l
    return list(out.values())

def load_sent_log():
    return json.loads(SENT_LOG.read_text()) if SENT_LOG.exists() else {}

def save_sent_log(log):
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    SENT_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))

def filter_leads(leads, args, sent_log):
    out = []
    for l in leads:
        if l["phone"] in sent_log:
            continue
        if args.category and l["category"] != args.category:
            continue
        if l["score"] < args.min_score:
            continue
        out.append(l)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[: args.limit] if args.limit else out

# ─── WhatsApp helpers ───────────────────────────────────────────────────────

def open_wa_chat(page, phone: str, timeout: int = 25000):
    page.goto(f"https://web.whatsapp.com/send?phone={COUNTRY_CODE}{phone}", timeout=30000)
    page.wait_for_selector(
        '[data-testid="conversation-compose-box-input"], [contenteditable="true"][data-tab="10"]',
        timeout=timeout,
    )
    time.sleep(random.uniform(2.0, 3.0))

def send_text(page, message: str) -> bool:
    """The message is pre-filled by the URL ?text= param. Just click compose + Enter."""
    compose = page.query_selector(
        '[data-testid="conversation-compose-box-input"], [contenteditable="true"][data-tab="10"]'
    )
    if compose:
        compose.click()
        time.sleep(0.5)
        page.keyboard.press("Enter")
        return True
    for sel in ['[data-testid="send"]', 'span[data-icon="send"]', '[aria-label="Send"]']:
        btn = page.query_selector(sel)
        if btn:
            btn.click()
            return True
    return False

def _copy_image_to_clipboard(image_path: str):
    """Copy image to clipboard — macOS (osascript), Linux (xclip/wl-copy), Windows (PowerShell)."""
    path = str(Path(image_path).resolve())

    if sys.platform == "darwin":
        script = f'set the clipboard to (read (POSIX file "{path}") as «class PNGf»)'
        subprocess.run(["osascript", "-e", script], check=True)

    elif sys.platform.startswith("linux"):
        # Prefer Wayland (wl-copy) when available, fall back to X11 (xclip).
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
            with open(path, "rb") as f:
                subprocess.run(["wl-copy", "--type", "image/png"], stdin=f, check=True)
        elif shutil.which("xclip"):
            subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-i", path],
                check=True,
            )
        else:
            raise RuntimeError(
                "No clipboard tool found. Install one:\n"
                "  sudo apt install xclip        # X11\n"
                "  sudo apt install wl-clipboard  # Wayland"
            )

    elif sys.platform == "win32":
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "Add-Type -AssemblyName System.Drawing;"
            f"$img = [System.Drawing.Image]::FromFile('{path}');"
            "[System.Windows.Forms.Clipboard]::SetImage($img);"
            "$img.Dispose()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            check=True,
        )

    else:
        raise NotImplementedError(f"Unsupported platform: {sys.platform}")

def send_image(page, image_path: str, caption: str) -> bool:
    """Send image + caption via clipboard paste — bypasses WA Web's ever-changing UI."""
    if not Path(image_path).exists():
        print(f"   ❌ Image not found: {image_path}")
        return False

    compose = None
    for sel in [
        '[data-testid="conversation-compose-box-input"]',
        '[contenteditable="true"][data-tab="10"]',
        'div[contenteditable="true"][spellcheck="true"]',
    ]:
        compose = page.query_selector(sel)
        if compose:
            break
    if not compose:
        print("   ❌ Compose box not found")
        return False

    try:
        _copy_image_to_clipboard(image_path)
    except Exception as e:
        print(f"   ❌ Clipboard copy failed: {e}")
        return False

    compose.click()
    time.sleep(0.5)
    page.keyboard.press("Meta+V" if sys.platform == "darwin" else "Control+V")
    time.sleep(3.0)

    # Find the caption box that appears after paste.
    caption_box = None
    for sel in [
        '[data-testid="media-caption-input-container"] div[contenteditable]',
        'div[data-testid="media-caption-input"]',
        'div[contenteditable="true"][data-tab="7"]',
    ]:
        el = page.query_selector(sel)
        if el and el != compose:
            caption_box = el
            break

    if caption_box:
        caption_box.click()
        time.sleep(0.3)
        for i, line in enumerate(caption.split("\n")):
            page.keyboard.type(line)
            if i < len(caption.split("\n")) - 1:
                page.keyboard.press("Shift+Enter")
        time.sleep(0.5)

    page.keyboard.press("Enter")
    time.sleep(2.0)
    return True

def take_screenshot(page, phone: str, name: str) -> str:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in name)[:25]
    ts = datetime.now().strftime("%H%M%S")
    path = str(SCREENSHOTS_DIR / f"{phone}_{safe}_{ts}.png")
    page.screenshot(path=path, full_page=False)
    return path

# ─── Main send loop ─────────────────────────────────────────────────────────

def send_messages(leads, dry_run=False, use_images=False, take_shots=True):
    sent_log = load_sent_log()
    success, failed = 0, 0

    if dry_run:
        print(f"\n{'─'*65}\nDRY RUN — {len(leads)} messages "
              f"({'images' if use_images else 'text'})\n{'─'*65}")
        for i, l in enumerate(leads):
            print(f"\n[{i+1}/{len(leads)}] {l['name']} ({l['phone']}) | {l['category']} | score:{l['score']}")
            if use_images:
                img = get_image_for_lead(l, i)
                print(f"  Image: {img['key']}\n  Caption: {img['caption'][:90]}...")
            else:
                print(f"  Message: {l['message'][:100]}...")
        print(f"\nDry run done. Run with --send to send.")
        return

    print(f"\n🚀 {len(leads)} messages ({'images' if use_images else 'text'}), "
          f"delay {MIN_DELAY_SEC}-{MAX_DELAY_SEC}s. Don't close browser.\n")

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    with sync_playwright() as p:
        first_run = not os.path.exists(WA_SESSION_DIR)
        if first_run:
            print("📱 First run — scan the WhatsApp QR with your phone.\n")

        ctx = p.chromium.launch_persistent_context(
            user_data_dir=WA_SESSION_DIR,
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"],
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.goto("https://web.whatsapp.com", timeout=30000)

        try:
            page.wait_for_selector(
                '[data-testid="chat-list"], [data-testid="default-user"], [aria-label="Chat list"]',
                timeout=180000 if first_run else 45000,
            )
            print("✅ WhatsApp Web logged in\n")
        except PWTimeout:
            print("❌ Not logged in — QR not scanned in time.")
            ctx.close()
            return

        for i, lead in enumerate(leads, 1):
            print(f"[{i}/{len(leads)}] {lead['name']} ({lead['phone']}) | {lead['category']} | score:{lead['score']}")
            try:
                open_wa_chat(page, lead["phone"])

                if use_images:
                    img = get_image_for_lead(lead, i - 1)
                    print(f"   📸 {img['key']}")
                    sent = send_image(page, img["path"], img["caption"])
                    img_key = img["key"]
                else:
                    encoded = urllib.parse.quote(lead["message"])
                    page.goto(f"https://web.whatsapp.com/send?phone={COUNTRY_CODE}{lead['phone']}&text={encoded}",
                              timeout=30000)
                    page.wait_for_selector(
                        '[data-testid="conversation-compose-box-input"], [contenteditable="true"][data-tab="10"]',
                        timeout=20000)
                    time.sleep(random.uniform(2.0, 3.0))
                    sent = send_text(page, lead["message"])
                    img_key = None

                if sent:
                    time.sleep(1.5)
                    shot = take_screenshot(page, lead["phone"], lead["name"]) if take_shots else ""
                    sent_log[lead["phone"]] = {
                        "name":      lead["name"],
                        "category":  lead["category"],
                        "area":      lead.get("area", ""),
                        "score":     lead["score"],
                        "sent_at":   datetime.now().isoformat(),
                        "type":      "image" if use_images else "text",
                        "image_key": img_key,
                        "screenshot": shot,
                    }
                    save_sent_log(sent_log)
                    print("   ✅ Sent!")
                    success += 1
                else:
                    print("   ⚠️  Send failed")
                    failed += 1

            except Exception as e:
                print(f"   ❌ {str(e).splitlines()[0][:80]}")
                failed += 1
                time.sleep(random.uniform(5, 10))

            if i < len(leads):
                d = random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC)
                print(f"   ⏱  {d:.0f}s")
                time.sleep(d)

        ctx.close()

    print(f"\n{'='*65}\n✅ Sent: {success} | Failed: {failed} | Total: {len(sent_log)}")

# ─── Stats ──────────────────────────────────────────────────────────────────

def print_stats():
    log = load_sent_log()
    if not log:
        print("No messages sent yet.")
        return
    by_cat = {}
    img = txt = 0
    for v in log.values():
        by_cat[v["category"]] = by_cat.get(v["category"], 0) + 1
        if v.get("type") == "image":
            img += 1
        else:
            txt += 1
    print(f"\n📊 Sent Stats — total: {len(log)}")
    for c, n in by_cat.items():
        print(f"  {c}: {n}")
    print(f"  images: {img} | text: {txt}")
    print("\nRecent 10:")
    for phone, info in sorted(log.items(), key=lambda x: x[1]["sent_at"], reverse=True)[:10]:
        icon = "📸" if info.get("type") == "image" else "💬"
        print(f"  {icon} {info['sent_at'][:16]} | {info['name'][:30]} ({phone}) | {info['category']}")

# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WhatsApp Web outreach")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--send",    action="store_true")
    mode.add_argument("--stats",   action="store_true")
    parser.add_argument("--images",        action="store_true")
    parser.add_argument("--limit",         type=int, default=None)
    parser.add_argument("--category",      type=str, default=None, choices=CATEGORY_KEYS)
    parser.add_argument("--min-score",     type=int, default=65)
    parser.add_argument("--no-screenshot", action="store_true")
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    leads = filter_leads(load_all_leads(), args, load_sent_log())
    if not leads:
        print("No leads match filters. Did you run process_leads.py?")
        return

    cat = args.category or "ALL"
    print(f"\n📋 {len(leads)} leads | {cat} | score≥{args.min_score} | "
          f"{'IMAGES' if args.images else 'TEXT'}")
    send_messages(leads, dry_run=args.dry_run, use_images=args.images,
                  take_shots=not args.no_screenshot)

if __name__ == "__main__":
    main()
