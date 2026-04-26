# Visual assets — to add

These two files turn the README into a proper landing page. Drop them here and the README references will pick them up.

## `hero-banner.png` (or `.jpg`)
- **Size:** 1600×600 ideal (will render at 800px wide on GitHub)
- **Style:** Clean dark background, project name + 1-line pitch, optional WhatsApp green accent (`#25D366`)
- **Tools:** Canva (free template), Figma, ChatGPT image gen, or shields.io stack
- **What it should say:**
  > whatsapp-outreach
  > Cold WhatsApp outreach that actually gets replies — open source.

## `demo.gif`
- **What to record:** a 15–30s terminal walk-through of the dry-run flow
  ```
  python3 process_leads.py
  python3 send_whatsapp.py --dry-run --limit 5
  python3 followup.py --tally --limit 10
  ```
- **Tools:** [`asciinema`](https://asciinema.org/) → `agg` for GIF, or [`vhs`](https://github.com/charmbracelet/vhs), or QuickTime + Gifski
- **Size:** keep under 5 MB so GitHub doesn't lazy-load it

## After adding both files

Re-add the `<img>` blocks to the README (right after the title and right after the badges):

```html
<p align="center">
  <img src="docs/hero-banner.png" alt="WhatsApp Outreach" width="800">
</p>
```

```html
<p align="center">
  <img src="docs/demo.gif" alt="Demo" width="800">
</p>
```
