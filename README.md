# whatsapp-outreach

> **Educational, open-source WhatsApp Web outreach automation.**
> Scrape Google Maps leads → score them → send Hormozi-style cold messages →
> follow up with image+caption → measure replies. All from your terminal.

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=flat&logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT">
  <img src="https://img.shields.io/badge/WhatsApp-Web-25D366?style=flat&logo=whatsapp&logoColor=white" alt="WhatsApp Web">
</p>

> ⚠️ **Read [DISCLAIMER.md](DISCLAIMER.md) first.** WhatsApp's Terms of Service
> prohibit automated use of WhatsApp Web. You can get banned. This repo exists
> to teach the architecture — use responsibly, only on public B2B numbers,
> with proper opt-outs.

---

## What it does

| Step | Script | What happens |
|------|--------|--------------|
| 1. **Scrape** | (Apify "compass~crawler-google-places") | Pull businesses from Google Maps for any search query |
| 2. **Score** | `process_leads.py` | Fetch the Apify dataset, score each lead 0–100 (rating sweet spot, review count, website presence), generate a personalized message |
| 3. **Send** | `send_whatsapp.py` | Drive WhatsApp Web via Playwright. Send text or image+caption, with 45–90s human-like delays |
| 4. **Tally** | `followup.py --tally` | Open every sent chat, screenshot it, detect incoming replies |
| 5. **Follow up** | `followup.py --send` | Image+caption follow-ups to non-responders, 3+ days after the cold message |

Everything lives on disk: `leads/*.json`, `sent/sent_log.json`,
`sent/followup_log.json`, `screenshots/*.png`. No database. No SaaS. No login.

---

## Quickstart

```bash
# 1. Clone + install
git clone https://github.com/arsalan507/whatsapp-outreach.git
cd whatsapp-outreach
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure
cp .env.example .env          # fill in APIFY_TOKEN, sender identity
cp config.example.yaml config.yaml   # edit categories + message templates

# 3. Scrape leads on Apify (one-time, manual)
#    Run "compass~crawler-google-places" with your search queries
#    e.g. "AC repair Bangalore", "phone repair Bangalore"
#    Note the dataset IDs and paste into APIFY_DATASETS in .env

# 4. Process the scraped data into scored leads
python3 process_leads.py

# 5. Preview the first 20 outbound messages
python3 send_whatsapp.py --dry-run --limit 20

# 6. Send (browser opens, scan QR on first run)
python3 send_whatsapp.py --send --limit 20

# 7. Wait 3+ days, then check who replied
python3 followup.py --tally

# 8. Send image follow-ups to silent leads
python3 followup.py --send --limit 20
```

---

## Architecture

```
                    ┌─────────────────────┐
                    │  Apify (Google Maps │
                    │   Places scraper)   │
                    └──────────┬──────────┘
                               │  dataset_id
                               ▼
                    ┌─────────────────────┐
                    │  process_leads.py   │  ← reads .env + config.yaml
                    │   score + generate  │
                    └──────────┬──────────┘
                               │  leads/leads_YYYYMMDD.json
                               ▼
                    ┌─────────────────────┐
                    │  send_whatsapp.py   │  ← Playwright + WhatsApp Web
                    │  text or image      │     45-90s delays
                    └──────────┬──────────┘
                               │  sent/sent_log.json
                               ▼
                    ┌─────────────────────┐
                    │  followup.py        │  ← tally replies, then send
                    │  --tally / --send   │     image followups
                    └─────────────────────┘
```

### Why these design choices

- **Playwright over a WhatsApp Business API client** — the Business API costs
  money, requires verification, and is overkill for someone testing 100
  leads. Playwright gives you the same UI a human would use.
- **Clipboard-paste for images** instead of clicking the attach button —
  WhatsApp Web changes its UI selectors often. The clipboard path is stable.
- **Flat JSON files** instead of a database — debuggable, reviewable,
  versionable. You can `jq` your funnel.
- **45–90s delays** — slower than you want, but slower than what gets banned.

---

## Configuration

All knobs live in two files:

### `.env` — secrets and sender identity
```env
APIFY_TOKEN=apify_api_xxxxxx
APIFY_DATASETS=ac:abc123,phone:def456     # category:dataset_id pairs
SENDER_NAME=Your Name
SENDER_PHONE=+91 99999 99999
SENDER_BRAND=YourBrand
COUNTRY_CODE=91                            # 91=IN, 44=UK, 1=US, etc.
DEFAULT_AREA=Bangalore
MIN_DELAY_SEC=45
MAX_DELAY_SEC=90
```

### `config.yaml` — categories, message templates, image rotation
- Define your own lead categories (anything, not just `ac` / `phone`)
- Three message variants: `no_website`, `weak_presence`, `established`
  — picked automatically based on the lead's profile
- Image-with-caption library + per-category rotation
- Follow-up images + caption library
- Scoring rules (rating sweet spot, review count, no-website bonus)

See [`config.example.yaml`](config.example.yaml) for the full schema.

---

## Message philosophy — Hormozi cold-outreach

The default templates lead with **their** pain in the first line, not your
pitch. Three lines max. No "I hope this finds you well." No 150-word warm
intros — they don't work cold.

```
Hi! *{name}* doesn't show up when people search "{service} near me" in {area}.

That's calls going to competitors every day.

Want me to show you exactly how many? Free, 5 mins. — {sender_name}
```

That's it. Your call to action is one ask: a 5-minute audit. The recipient
either says YES or doesn't. Don't try to close in message #1.

---

## Common operations

```bash
# Stats
python3 send_whatsapp.py --stats

# Send only AC leads with score >= 75
python3 send_whatsapp.py --send --category ac --min-score 75 --limit 30

# Image messages instead of text
python3 send_whatsapp.py --send --images --limit 20

# Tally a specific number of recent chats
python3 followup.py --tally --limit 40

# Dry-run follow-ups to see who's eligible
python3 followup.py --dry-run

# Follow up only conversations sent more than 5 days ago
python3 followup.py --send --min-days 5 --limit 20
```

---

## Roadmap

- [ ] Linux/Windows clipboard adapters (currently macOS-only for image send)
- [ ] Optional Google Sheets CRM sync (`crm_sheet.py`) — coming soon
- [ ] Retry queue for transient WA Web failures
- [ ] Optional Twilio/Cloud API path for compliant high-volume use

---

## Credits

Built by [@arsalan507](https://github.com/arsalan507) at
[KineticXHub](https://kineticxhub.com) — AI-powered growth for Indian SMBs.

Hormozi cold-message style adapted from his public B2B outreach principles.

---

## License

MIT. See [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome — especially Linux/Windows clipboard support, additional
country normalisations, and message-template improvements. Read
[DISCLAIMER.md](DISCLAIMER.md) before contributing.
