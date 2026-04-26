#!/usr/bin/env python3
"""
Lead processor — fetches Apify Google Maps results, scores leads, and
generates WhatsApp messages from your config.yaml templates.

Usage:
  python3 process_leads.py
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# ─── Config loading ─────────────────────────────────────────────────────────

ROOT       = Path(__file__).parent
CONFIG     = yaml.safe_load((ROOT / "config.yaml").read_text())
LEADS_DIR  = ROOT / "leads"
LEADS_DIR.mkdir(exist_ok=True)

APIFY_TOKEN    = os.getenv("APIFY_TOKEN", "")
APIFY_DATASETS = os.getenv("APIFY_DATASETS", "")  # "ac:abc,phone:def"
SENDER_NAME    = os.getenv("SENDER_NAME", "Sender")
SENDER_PHONE   = os.getenv("SENDER_PHONE", "")
SENDER_BRAND   = os.getenv("SENDER_BRAND", "")
DEFAULT_AREA   = os.getenv("DEFAULT_AREA", "your area")
COUNTRY_CODE   = os.getenv("COUNTRY_CODE", "91")

if not APIFY_TOKEN or not APIFY_DATASETS:
    sys.exit("❌ Set APIFY_TOKEN and APIFY_DATASETS in .env (see .env.example).")

# ─── Apify fetch ────────────────────────────────────────────────────────────

def fetch_run_items(dataset_id: str):
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}&format=json&limit=1000"
    with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
        return json.loads(resp.read())

# ─── Phone normalisation ────────────────────────────────────────────────────

def normalize_phone(raw: str):
    """Strip non-digits, drop country code if present, return None if invalid."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    cc = COUNTRY_CODE
    if digits.startswith(cc) and len(digits) == 10 + len(cc):
        digits = digits[len(cc):]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10:
        return digits
    return None

# ─── Scoring (rules driven by config.yaml) ──────────────────────────────────

def score_lead(place: dict):
    s = CONFIG["scoring"]
    score, reasons = 0, []

    if not place.get("phone") and not place.get("phoneUnformatted"):
        return 0, ["No phone — skip"]

    score += 25  # has phone

    rating  = place.get("totalScore") or 0
    reviews = place.get("reviewsCount") or 0

    lo, hi = s["rating_sweet_spot"]
    if lo <= rating <= hi:
        score += 20
        reasons.append(f"Rating {rating} — improvable")
    elif rating > hi:
        score += 8
        reasons.append(f"Rating {rating} — already strong")
    elif rating == 0:
        score += 10
        reasons.append("No rating — brand new or unclaimed")

    rlo, rhi = s["reviews_sweet_spot"]
    if rlo <= reviews <= rhi:
        score += 20
        reasons.append(f"{reviews} reviews — established")
    elif reviews < rlo:
        score += 12
        reasons.append(f"Only {reviews} reviews — needs growth")
    else:
        score += 5
        reasons.append(f"{reviews} reviews — market leader")

    if not place.get("website"):
        score += s["no_website_bonus"]
        reasons.append("No website — big opportunity")
    else:
        score += 8
        reasons.append("Has website")

    if place.get("permanentlyClosed"):
        return 0, ["Permanently closed — skip"]
    if place.get("temporarilyClosed"):
        score -= 10
        reasons.append("Temporarily closed")

    return min(score, 100), reasons

# ─── Message generation ─────────────────────────────────────────────────────

def pick_variant(place: dict) -> str:
    rating  = place.get("totalScore") or 0
    reviews = place.get("reviewsCount") or 0
    if not place.get("website"):
        return "no_website"
    if rating < 4.0 and reviews < 50:
        return "weak_presence"
    return "established"

def generate_message(place: dict, category: str) -> str:
    raw_name = place.get("title", "there")
    name = re.split(r"\s*[\|]\s*", raw_name)[0].strip()
    if len(name) > 40:
        name = name[:40].rsplit(" ", 1)[0]

    raw_area = place.get("neighborhood") or place.get("city") or DEFAULT_AREA
    parts = [p.strip() for p in raw_area.split(",")]
    area = parts[-1] if len(parts) > 1 else raw_area

    service = CONFIG["categories"][category]["service_name"]
    template = CONFIG["messages"][pick_variant(place)]

    return template.format(
        name=name, area=area, service=service,
        sender_name=SENDER_NAME, sender_phone=SENDER_PHONE,
        sender_brand=SENDER_BRAND,
    ).strip()

# ─── Main ────────────────────────────────────────────────────────────────────

def parse_datasets(s: str):
    """Parse 'ac:abc,phone:def' into [(category, dataset_id), ...]."""
    out = []
    for pair in s.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            sys.exit(f"❌ Bad APIFY_DATASETS entry: {pair!r}. Expected 'category:dataset_id'.")
        cat, ds = pair.split(":", 1)
        cat = cat.strip()
        if cat not in CONFIG["categories"]:
            sys.exit(f"❌ Category {cat!r} not in config.yaml categories.")
        out.append((cat, ds.strip()))
    return out

def process_dataset(category: str, dataset_id: str):
    label = CONFIG["categories"][category]["label"]
    print(f"\n{'='*60}\nProcessing {label} — Dataset: {dataset_id}\n{'='*60}")

    try:
        items = fetch_run_items(dataset_id)
    except Exception as e:
        print(f"❌ ERROR fetching results: {e}")
        return []

    print(f"Raw results: {len(items)} places")
    seen, leads = set(), []

    for place in items:
        phone = normalize_phone(place.get("phone") or place.get("phoneUnformatted") or "")
        if not phone or phone in seen:
            continue
        seen.add(phone)

        score, reasons = score_lead(place)
        if score == 0:
            continue

        raw_area = place.get("neighborhood") or place.get("city") or ""
        parts    = [p.strip() for p in raw_area.split(",")]
        area     = parts[-1] if len(parts) > 1 else raw_area

        leads.append({
            "name":            place.get("title", ""),
            "phone":           phone,
            "area":            area,
            "address":         place.get("address") or place.get("street") or "",
            "rating":          place.get("totalScore") or 0,
            "reviews":         place.get("reviewsCount") or 0,
            "website":         place.get("website") or "",
            "google_maps_url": place.get("url") or "",
            "category":        category,
            "score":           score,
            "score_reasons":   reasons,
            "message":         generate_message(place, category),
            "status":          "pending",
            "scraped_at":      datetime.now().isoformat(),
        })

    leads.sort(key=lambda x: x["score"], reverse=True)
    hot  = sum(1 for l in leads if l["score"] >= CONFIG["scoring"]["hot_threshold"])
    warm = sum(1 for l in leads if CONFIG["scoring"]["warm_threshold"] <= l["score"] < CONFIG["scoring"]["hot_threshold"])
    cold = len(leads) - hot - warm
    print(f"Qualified: {len(leads)}  🔥 Hot: {hot}  🟡 Warm: {warm}  🔵 Cold: {cold}")
    return leads

if __name__ == "__main__":
    all_leads = []
    for cat, ds in parse_datasets(APIFY_DATASETS):
        all_leads.extend(process_dataset(cat, ds))

    if not all_leads:
        sys.exit("\nNo qualified leads. Check Apify dataset IDs.")

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = LEADS_DIR / f"leads_{ts}.json"
    out.write_text(json.dumps(all_leads, indent=2, ensure_ascii=False))
    print(f"\n✅ Saved {len(all_leads)} leads → {out}")

    print(f"\n{'─'*60}\nTOP 10 LEADS\n{'─'*60}")
    for i, l in enumerate(all_leads[:10], 1):
        site = "✓ web" if l["website"] else "✗ no web"
        print(f"{i:2}. [{l['score']:3}/100] {l['name'][:35]:<35} | {l['phone']} | ⭐{l['rating']} ({l['reviews']}) | {site} | {l['area']}")
