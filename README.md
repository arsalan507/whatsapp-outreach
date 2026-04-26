<h1 align="center">whatsapp-outreach</h1>

<p align="center">
  <em>I spent months sending B2B outreach the hard way. So I engineered the system I wish I had.</em><br>
  Most agencies use AI to <em>spam</em> shop owners. <strong>I gave shop owners a way to <em>actually be heard</em>.</strong><br>
  <em>Now it's open source.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=flat&logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/WhatsApp-Web-25D366?style=flat&logo=whatsapp&logoColor=white" alt="WhatsApp Web">
  <img src="https://img.shields.io/badge/Apify-5C5CFF?style=flat&logo=data&logoColor=white" alt="Apify">
  <img src="https://img.shields.io/badge/Google_Sheets-0F9D58?style=flat&logo=google-sheets&logoColor=white" alt="Google Sheets">
  <img src="https://img.shields.io/badge/Anthropic_Claude-D97757?style=flat&logo=anthropic&logoColor=white" alt="Claude">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT">
</p>

---

<p align="center"><strong>40 leads tested · 20% reply rate · 4 closeable conversations · ₹0 ad spend</strong></p>

<p align="center"><a href="DISCLAIMER.md"><img src="https://img.shields.io/badge/Read_the_Disclaimer_first-EA4335?style=for-the-badge&logo=warning&logoColor=white" alt="Disclaimer"></a></p>

## What Is This

`whatsapp-outreach` turns one Python script + one WhatsApp Web session into a full B2B cold-outreach pipeline. Instead of paying an agency Rs 50K/month to spam your prospects, you get a system that:

- **Scrapes leads** from Google Maps via Apify (compass~crawler-google-places)
- **Scores them 0–100** based on rating sweet spot, review count, and website presence
- **Generates messages** that pick automatically between 3 variants (no website / weak presence / established)
- **Sends via WhatsApp Web** with 45–90s human-like delays — text or image+caption
- **Tallies replies** by opening every sent chat and screenshotting it
- **Follows up** with image+caption to silent leads, 3+ days later

> **Important: This is NOT a spam tool.** It's a small-batch, proof-of-message system. The defaults send 20 messages a day with 45–90s gaps. You target only public B2B numbers (Google Business listings). You honour every "stop" / opt-out instantly. **Read [DISCLAIMER.md](DISCLAIMER.md) before using.** WhatsApp's Terms of Service prohibit automation. You can get banned. Use at your own risk.

> **Heads up: the first batch won't break records.** The defaults work, but the message templates are *yours* to write. Hormozi-style 3-line cold messages (the included templates) hit because they lead with the prospect's pain, not your pitch. The more you tune the templates to your offer + your voice, the better it gets.

Built by an Indian SMB founder who used it to score a 20% reply rate on cold WhatsApp — the highest engagement his outreach has ever produced.

## Features

| Feature | Description |
|---------|-------------|
| **Apify scraper integration** | Pull any Google Maps query into a JSON dataset, then score it |
| **3-variant message generator** | Picks no-website / weak-presence / established template per lead automatically |
| **Image + caption sender** | Clipboard-paste approach (bypasses WA Web's ever-changing UI selectors) |
| **Reply tally** | Open every sent chat in headless Chromium, screenshot it, detect reply bubbles |
| **Image follow-up** | Rotates through proof / competitor / curiosity images for non-responders |
| **Score-based filtering** | Send only to leads above your `--min-score` threshold |
| **Category routing** | Define your own categories (`ac`, `phone`, `salon`, anything) — each gets its own message bank |
| **Persistent WA session** | Scan QR once per device, then it stays logged in |
| **Flat-file state** | Everything lives in JSON files you can `jq` / `git diff` / hand-edit |
| **Human-in-the-loop** | The system sends, but YOU close the deal. No auto-replies, no auto-pricing |

## Quick Start

```bash
# 1. Clone + install
git clone https://github.com/arsalan507/whatsapp-outreach.git
cd whatsapp-outreach
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure
cp .env.example .env                    # set APIFY_TOKEN, sender identity, country code
cp config.example.yaml config.yaml      # edit categories + message templates

# 3. Scrape leads (one-time, manual, on Apify)
#    Run "compass~crawler-google-places" with your search query
#    e.g. "AC repair Bangalore" → note the dataset ID
#    Paste it into APIFY_DATASETS in .env as "ac:abc123"

# 4. Process the scrape into scored leads
python3 process_leads.py

# 5. Preview what's about to go out
python3 send_whatsapp.py --dry-run --limit 20

# 6. Send (browser opens, scan QR on first run)
python3 send_whatsapp.py --send --limit 20

# 7. Wait 3+ days, then check who replied
python3 followup.py --tally

# 8. Image-follow-up the silent leads
python3 followup.py --send --limit 20
```

> **The system is designed to be customised by you.** Categories, scoring rules, message templates, image rotation — all live in `config.yaml`. The Python scripts read it and behave accordingly. No code changes needed for most tweaks.

See [DISCLAIMER.md](DISCLAIMER.md) for safe-use guidelines.

## How It Works

```
You scrape Google Maps via Apify
        │
        ▼
┌──────────────────┐
│  Apify Dataset   │  one-time per category
│  (Google Places) │
└────────┬─────────┘
         │ dataset_id
         ▼
┌──────────────────┐
│ process_leads.py │  ← reads config.yaml + .env
│ score 0-100      │  ← picks message variant per lead
│ generate msg     │
└────────┬─────────┘
         │ leads/leads_YYYYMMDD.json
         ▼
┌──────────────────┐
│ send_whatsapp.py │  ← Playwright + WhatsApp Web
│ text or image    │  ← 45-90s delays
│ skip if in log   │
└────────┬─────────┘
         │ sent/sent_log.json
         ▼
┌──────────────────┐
│ followup.py      │  ← screenshot every chat
│ --tally          │  ← detect .message-in bubble
│ --send           │  ← image follow-up to silent
└──────────────────┘
```

## Message Philosophy — Hormozi cold-outreach

The default templates lead with **their pain** in the first line, not your pitch. Three lines max. No "I hope this finds you well." No 150-word warm intros — they don't work cold.

```
Hi! *{name}* doesn't show up when people search "{service} near me" in {area}.

That's calls going to competitors every day.

Want me to show you exactly how many? Free, 5 mins. — {sender_name}
```

That's it. One ask: a 5-min audit. The recipient says YES or doesn't. Don't try to close in message #1.

## Common Operations

```bash
# Stats — total sent, by category, by type, recent 10
python3 send_whatsapp.py --stats

# Send only one category, score-filtered
python3 send_whatsapp.py --send --category ac --min-score 75 --limit 30

# Image messages instead of text (clipboard-paste, macOS only for now)
python3 send_whatsapp.py --send --images --limit 20

# Tally only the most-recent N chats
python3 followup.py --tally --limit 40

# Preview eligible follow-ups
python3 followup.py --dry-run

# Send follow-ups only to chats sent more than 5 days ago
python3 followup.py --send --min-days 5 --limit 20
```

## Project Structure

```
whatsapp-outreach/
├── README.md                # This file
├── DISCLAIMER.md            # WhatsApp ToS + responsible use
├── LICENSE                  # MIT
├── .env.example             # Apify token, sender identity
├── .gitignore               # Secrets, sessions, generated data
├── config.example.yaml      # Categories, messages, image rotation
├── requirements.txt         # python deps
│
├── process_leads.py         # Apify → scored leads JSON
├── send_whatsapp.py         # Cold sender (text + image)
├── followup.py              # Reply tally + image follow-up
│
├── examples/
│   └── leads.example.json   # Mock leads for testing
│
├── docs/                    # (you'll add) hero-banner.png, demo.gif
│
├── leads/                   # (gitignored) scraped lead lists
├── sent/                    # (gitignored) sent_log.json, followup_log.json
└── screenshots/             # (gitignored) tally screenshots
```

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat&logo=playwright&logoColor=white)
![Apify](https://img.shields.io/badge/Apify-5C5CFF?style=flat&logo=data&logoColor=white)
![YAML](https://img.shields.io/badge/YAML-CB171E?style=flat&logo=yaml&logoColor=white)
![Google_Sheets](https://img.shields.io/badge/Google_Sheets-0F9D58?style=flat&logo=google-sheets&logoColor=white)

- **Browser automation:** Playwright Chromium with persistent WhatsApp session
- **Scraping:** Apify `compass~crawler-google-places` actor (fastest Google Maps API)
- **Config:** YAML + dotenv — every business-specific knob lives outside the code
- **Storage:** Flat JSON — no DB, fully diffable
- **Image send:** macOS clipboard via AppleScript (Linux/Windows adapters welcome)

## Roadmap

- [ ] Linux/Windows clipboard adapters (currently macOS-only for image send)
- [ ] Optional Google Sheets CRM sync (`crm_sheet.py`) — sanitised port coming
- [ ] Retry queue for transient WA Web failures
- [ ] Demo GIF + hero banner in `docs/`
- [ ] Translation hooks (Spanish, Portuguese, Hindi message templates)
- [ ] Twilio / Cloud API path for compliant high-volume use

## Star History

<a href="https://www.star-history.com/?repos=arsalan507%2Fwhatsapp-outreach&type=Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=arsalan507/whatsapp-outreach&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=arsalan507/whatsapp-outreach&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=arsalan507/whatsapp-outreach&type=Date" />
 </picture>
</a>

## Contributors

<a href="https://github.com/arsalan507/whatsapp-outreach/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=arsalan507/whatsapp-outreach" />
</a>

Got real replies using this? [Share your story!](https://github.com/arsalan507/whatsapp-outreach/issues/new)

## Disclaimer

**whatsapp-outreach is a local, open-source tool — NOT a hosted service.** By using this software, you acknowledge:

1. **You control your data.** Lead lists, sent logs, screenshots stay on your machine. Nothing is sent anywhere except to WhatsApp Web (which is the user, not us).
2. **You comply with WhatsApp's ToS.** WhatsApp prohibits automation. Your number can be rate-limited or banned. The defaults (45–90s delays, 20/day) reduce risk but don't eliminate it.
3. **You comply with anti-spam law.** TRAI, CAN-SPAM, GDPR, PECR — your jurisdiction's rules apply. Only message public B2B numbers. Honour every opt-out.
4. **No guarantees.** Reply rates depend on your message, offer, and audience. The author's 20% rate is one anecdote, not a promise.

See [DISCLAIMER.md](DISCLAIMER.md) for full guidelines. Provided under [MIT License](LICENSE) "as is", without warranty.

## License

MIT. See [LICENSE](LICENSE).

## Let's Connect

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/arsalan507)
[![KineticXHub](https://img.shields.io/badge/KineticXHub-0D1B2A?style=for-the-badge&logo=safari&logoColor=white)](https://kineticxhub.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/arsalan507)
[![X](https://img.shields.io/badge/X-000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/arsalan507)
[![Email](https://img.shields.io/badge/Email-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:arsalanahmed507@gmail.com)

---

**Build something with this?** Open an issue or PR — especially Linux/Windows clipboard support, additional country normalisations, and message-template improvements. Read [DISCLAIMER.md](DISCLAIMER.md) before contributing.
