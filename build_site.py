#!/usr/bin/env python3
"""Build the Gridshift website (thedrive.com-style, image-led, multi-page).

Reuses the SAME pipeline as the Instagram auto-poster:
  carnews.feeds.fetch_all   -> pull + de-dupe RSS/Atom stories
  carnews.select.filter_trucks / categorize  -> drop trucks, bucket stories

Generates a small static site into ./site:
  index.html        homepage: hero + a preview of each category (links out)
  performance.html  full Performance feed
  racing.html       full Racing feed
  wagon.html        full Wagons feed
  archive.html      every aggregated story, newest first

Every card links OUT to the original publisher (target=_blank,
rel="nofollow noopener"); only headline + source + time are shown. With
SHOW_SOURCE_IMAGES=True each card embeds the thumbnail the publisher puts in
its OWN RSS feed (image-heavy look); stories without one fall back to a
branded tile. The homepage is the Instagram bio link.

Usage:  python build_site.py [--out-dir site] [--sample]
Sandbox note: feeds 403 here; real fetch works on GitHub runners. --sample
renders synthetic stories (with placeholder images) for offline preview.
"""
from __future__ import annotations

import argparse
import html
from datetime import datetime, timezone
from pathlib import Path

from carnews.feeds import fetch_all
from carnews.select import filter_trucks, categorize

ROOT = Path(__file__).resolve().parent

SHOW_SOURCE_IMAGES = True  # image-heavy Drive look; hotlinks publisher RSS thumbs

BRAND_NAME = "GRIDSHIFT"
TAGLINE = "Performance · Racing · Wagons · Daily"
IG_URL = "https://www.instagram.com/gridshift_official/"
ACCENTS = {"performance": "#e31e24", "racing": "#00a8ff", "wagon": "#f0b030"}
CAT_LABELS = {"performance": "Performance", "racing": "Racing", "wagon": "Wagons"}
CAT_PAGE = {"performance": "performance.html", "racing": "racing.html", "wagon": "wagon.html"}
CAT_ORDER = ["performance", "racing", "wagon"]
HOME_PER_CAT = 9        # cards per category shown on the homepage
CAT_PER_PAGE = 60       # cards on each category page
ARCHIVE_MAX = 150       # cards on the archive page


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _ago(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    secs = int((datetime.now(timezone.utc) - dt).total_seconds())
    if secs < 3600:
        return f"{max(1, secs // 60)}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    d = secs // 86400
    return f"{d}d ago" if d < 7 else dt.strftime("%b %-d")


def _bg(it: dict) -> str:
    img = it.get("image") or ""
    return f"background-image:url('{_esc(img)}')" if (SHOW_SOURCE_IMAGES and img) else ""


# --- cards ------------------------------------------------------------------
def _overlay_card(it: dict, cat: str, cls: str) -> str:
    accent = ACCENTS[cat]
    bg = _bg(it)
    return f"""<article class="{cls}">
  <a class="ov{'' if bg else ' tile'}" href="{_esc(it.get('link','#'))}" target="_blank" rel="noopener noreferrer nofollow" style="{bg};--a:{accent}">
    <span class="ribbon" style="--a:{accent}">{CAT_LABELS[cat].upper()}</span>
    <div class="ovtext">
      <span class="src" style="--a:{accent}">{_esc(it.get('source',''))}</span>
      <h3>{_esc(it.get('title',''))}</h3>
      <span class="meta">{_esc(_ago(it.get('date')))} · Read at {_esc(it.get('source',''))} &rarr;</span>
    </div>
  </a>
</article>"""


def _grid_card(it: dict, cat: str) -> str:
    accent = ACCENTS[cat]
    bg = _bg(it)
    src = _esc(it.get("source", ""))
    thumb = (f'<div class="thumb" style="{bg}"><span class="ribbon" style="--a:{accent}">{CAT_LABELS[cat].upper()}</span></div>'
             if bg else
             f'<div class="thumb tile" style="--a:{accent}"><span class="ribbon" style="--a:{accent}">{CAT_LABELS[cat].upper()}</span><span class="tilesrc">{src}</span></div>')
    return f"""<article class="card">
  <a class="cardlink" href="{_esc(it.get('link','#'))}" target="_blank" rel="noopener noreferrer nofollow">
    {thumb}
    <div class="body">
      <span class="src" style="--a:{accent}">{src}</span>
      <h3>{_esc(it.get('title',''))}</h3>
      <span class="meta">{_esc(_ago(it.get('date')))} · Read at {src} &rarr;</span>
    </div>
  </a>
</article>"""


# --- page shell -------------------------------------------------------------
STYLE = """
:root{--bg:#0f1117;--bg2:#161922;--card:#1b1f2a;--line:#2a2f3c;--text:#f3f5f8;--muted:#9aa2b1}
*{box-sizing:border-box;margin:0;padding:0}
img{display:block;max-width:100%}
body{background:var(--bg);color:var(--text);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
header{position:sticky;top:0;z-index:20;background:rgba(15,17,23,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.bar{display:flex;align-items:center;gap:16px;height:60px}
.brand{font-weight:800;letter-spacing:1px;font-size:22px}
.brand b{color:#e31e24}
.tag{color:var(--muted);font-size:13px;display:none}
@media(min-width:860px){.tag{display:inline}}
nav{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
nav a{font-size:13px;font-weight:600;padding:6px 12px;border-radius:20px;border:1px solid var(--line);color:var(--muted)}
nav a:hover{color:#fff;border-color:var(--a)}
nav a.on{color:#fff;border-color:var(--a);box-shadow:inset 0 -2px 0 var(--a)}
.ig{font-size:13px;font-weight:700;padding:6px 14px;border-radius:20px;background:#e31e24;color:#fff;white-space:nowrap}
.herowrap{padding:22px 0 4px}
.pagehead{padding:26px 0 4px;border-left:6px solid var(--a);padding-left:14px;margin:22px 0 6px}
.pagehead h1{font-size:clamp(22px,3.4vw,32px);font-weight:800;text-transform:uppercase;letter-spacing:.5px}
.pagehead p{color:var(--muted);font-size:14px;margin-top:4px}
.cat{padding:24px 0 6px}
.cathead{display:flex;align-items:center;gap:14px;border-left:5px solid var(--a);padding-left:12px;margin-bottom:18px}
.cathead h2{font-size:20px;font-weight:800;text-transform:uppercase;letter-spacing:.5px}
.cathead .more{margin-left:auto;color:var(--a);font-size:13px;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;transition:transform .12s,border-color .12s}
.card:hover{transform:translateY(-3px);border-color:#3a414f}
.card.lead{grid-column:1/-1}
@media(min-width:760px){.card.lead{grid-column:span 2}}
.ov{position:relative;display:flex;align-items:flex-end;min-height:230px;background-size:cover;background-position:center;background-color:#10131a}
.card.hero .ov{min-height:clamp(300px,46vw,460px)}
.card.lead .ov{min-height:300px}
.ov::after{content:"";position:absolute;inset:0;background:linear-gradient(to top,rgba(8,9,12,.92) 0%,rgba(8,9,12,.55) 38%,rgba(8,9,12,.12) 70%,rgba(8,9,12,0) 100%)}
.ov.tile{background:linear-gradient(135deg,#12151d,#222838)}
.ovtext{position:relative;z-index:2;padding:22px}
.card.hero .ovtext{padding:30px}
.ovtext h3{font-weight:800;line-height:1.18;margin:6px 0 8px;font-size:clamp(20px,2.6vw,30px);text-shadow:0 2px 12px rgba(0,0,0,.6)}
.card.hero .ovtext h3{font-size:clamp(24px,3.6vw,40px)}
.cardlink{display:flex;flex-direction:column;height:100%}
.thumb{position:relative;aspect-ratio:16/9;background-size:cover;background-position:center;background-color:#10131a}
.thumb.tile{display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#12151d,#222838)}
.thumb.tile .tilesrc{font-weight:800;letter-spacing:1.5px;font-size:clamp(15px,2vw,22px);color:#fff;opacity:.22;text-transform:uppercase;text-align:center;padding:0 16px}
.thumb.tile::after{content:"";position:absolute;left:0;top:0;width:100%;height:4px;background:var(--a)}
.ribbon{position:absolute;left:12px;top:12px;z-index:3;font-size:11px;font-weight:800;letter-spacing:1px;color:#0f1117;background:var(--a);padding:4px 10px;border-radius:4px}
.body{padding:14px 16px 16px;display:flex;flex-direction:column;gap:7px;flex:1}
.src{font-size:11px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:var(--a)}
.card h3{font-size:16px;font-weight:700;line-height:1.3}
.meta{margin-top:auto;color:var(--muted);font-size:12px}
.ovtext .meta{color:#cfd4de}
footer{border-top:1px solid var(--line);margin-top:40px;padding:26px 0;color:var(--muted);font-size:13px}
footer a{color:#cdd3de;text-decoration:underline}
.note{margin-top:8px;font-size:12px;opacity:.8}
"""


def _nav(active: str) -> str:
    links = [("index.html", "Home", "home")]
    links += [(CAT_PAGE[c], CAT_LABELS[c], c) for c in CAT_ORDER]
    links += [("archive.html", "All Stories", "archive")]
    out = []
    for href, label, key in links:
        accent = ACCENTS.get(key, "#e31e24")
        on = " on" if key == active else ""
        out.append(f'<a class="{on.strip()}" href="{href}" style="--a:{accent}">{label}</a>')
    return "\n".join(out)


def _page(title: str, desc: str, body: str, active: str, total: int, updated: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{_esc(desc)}">
<style>{STYLE}</style>
</head>
<body>
<a id="top"></a>
<header><div class="wrap bar">
  <a class="brand" href="index.html"><b>GRID</b>SHIFT</a>
  <span class="tag">{TAGLINE}</span>
  <nav>{_nav(active)}</nav>
  <a class="ig" href="{IG_URL}" target="_blank" rel="noopener">Instagram</a>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
  <div>{BRAND_NAME} aggregates headlines and links to original publishers. All articles, images and trademarks belong to their respective owners. Follow on <a href="{IG_URL}" target="_blank" rel="noopener">Instagram</a>.</div>
  <div class="note">{total} stories · auto-generated {updated} · summaries only — read the full story at the source.</div>
</div></footer>
</body>
</html>"""


# --- page bodies ------------------------------------------------------------
def _home_body(buckets: dict) -> tuple[str, str | None]:
    newest = None
    for c in CAT_ORDER:
        for s in buckets.get(c, []):
            if newest is None or s.get("ts", 0) > newest[0].get("ts", 0):
                newest = (s, c)
    hero, hero_link = "", None
    if newest:
        s, c = newest
        hero_link = s.get("link")
        hero = f'<div class="herowrap">{_overlay_card(s, c, "card hero")}</div>'
    parts = [hero]
    for c in CAT_ORDER:
        stories = [s for s in buckets.get(c, []) if s.get("link") != hero_link]
        if not stories:
            continue
        lead = _overlay_card(stories[0], c, "card lead")
        rest = "\n".join(_grid_card(s, c) for s in stories[1:])
        parts.append(f"""<section class="cat" id="{c}">
  <div class="cathead" style="--a:{ACCENTS[c]}"><h2>{CAT_LABELS[c]}</h2><a class="more" href="{CAT_PAGE[c]}">View all {CAT_LABELS[c]} &rarr;</a></div>
  <div class="grid">
    {lead}
    {rest}
  </div>
</section>""")
    return "\n".join(parts), hero_link


def _category_body(cat: str, stories: list) -> str:
    if not stories:
        return f'<div class="pagehead" style="--a:{ACCENTS[cat]}"><h1>{CAT_LABELS[cat]}</h1><p>No stories right now — check back soon.</p></div>'
    lead = _overlay_card(stories[0], cat, "card lead")
    rest = "\n".join(_grid_card(s, cat) for s in stories[1:])
    return f"""<div class="pagehead" style="--a:{ACCENTS[cat]}"><h1>{CAT_LABELS[cat]}</h1><p>{len(stories)} latest stories · each links to the original source.</p></div>
<div class="grid">
{lead}
{rest}
</div>"""


def _archive_body(items: list) -> str:
    cards = "\n".join(_grid_card(s, s["category"]) for s in items)
    return f"""<div class="pagehead" style="--a:#e31e24"><h1>All Stories</h1><p>{len(items)} aggregated stories, newest first · each links to the original source.</p></div>
<div class="grid">
{cards}
</div>"""


# --- build ------------------------------------------------------------------
def build(items: list, out_dir: Path) -> None:
    items = filter_trucks(list(items))
    categorize(items)
    items = [it for it in items if it.get("category") in CAT_ORDER]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)

    by_cat = {c: [it for it in items if it["category"] == c] for c in CAT_ORDER}
    home = {c: by_cat[c][:HOME_PER_CAT] for c in CAT_ORDER}
    total = len(items)
    updated = datetime.now(timezone.utc).strftime("%b %-d, %Y · %H:%M UTC")
    out_dir.mkdir(parents=True, exist_ok=True)

    home_body, _ = _home_body(home)
    (out_dir / "index.html").write_text(
        _page(f"{BRAND_NAME} — Performance, Racing & Wagon News",
              "The latest performance car, motorsport and wagon news, aggregated daily. Headlines link to the original source.",
              home_body, "home", total, updated), encoding="utf-8")

    for c in CAT_ORDER:
        (out_dir / CAT_PAGE[c]).write_text(
            _page(f"{CAT_LABELS[c]} — {BRAND_NAME}",
                  f"The latest {CAT_LABELS[c]} car news, aggregated daily. Links to original sources.",
                  _category_body(c, by_cat[c][:CAT_PER_PAGE]), c, total, updated), encoding="utf-8")

    (out_dir / "archive.html").write_text(
        _page(f"All Stories — {BRAND_NAME}",
              "Every aggregated car-news story, newest first. Links to original sources.",
              _archive_body(items[:ARCHIVE_MAX]), "archive", total, updated), encoding="utf-8")

    print(f"Wrote site to {out_dir}/  (index + {len(CAT_ORDER)} category pages + archive)")
    for c in CAT_ORDER:
        print(f"  {CAT_LABELS[c]:<12} {len(by_cat[c])} stories")
    print(f"  Archive      {min(total, ARCHIVE_MAX)} of {total}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(ROOT / "site"))
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()
    if args.sample:
        items = _sample_items()
    else:
        print("Fetching feeds...")
        items, _ = fetch_all(verbose=True)
        print(f"  -> {len(items)} unique stories")
    build(items, Path(args.out_dir))


def _sample_items() -> list:
    base = "2026-06-28T"
    raw = [
        ("Jalopnik", "2026 Porsche 911 GT3 RS first drive: still the sharpest tool", "12:00:00+00:00", 11),
        ("The Drive", "BMW M2 review: the last great manual coupe?", "11:30:00+00:00", 22),
        ("Car and Driver", "Tested: Tesla Model S Plaid runs a 9-second quarter mile", "10:00:00+00:00", 33),
        ("Road & Track", "Civic Type R long-term update: 10,000 miles in", "09:00:00+00:00", 44),
        ("Throttle House", "Audi RS3 vs Mercedes-AMG A45: hot hatch showdown", "08:45:00+00:00", 144),
        ("Motorsport.com", "Le Mans 24 Hours: Ferrari takes thrilling overall win", "08:00:00+00:00", 55),
        ("Motorsport.com", "F1 qualifying: pole position decided by 0.012s at Monza", "07:30:00+00:00", 66),
        ("Hagerty", "IMSA at Daytona: GTP class delivers an instant classic", "06:00:00+00:00", 77),
        ("The Drive", "WRC Rally Finland: massive jumps, tighter championship", "05:00:00+00:00", 88),
        ("Chris Harris", "Onboard: a flying lap of the new GT3 race car", "04:30:00+00:00", 155),
        ("Hagerty", "Why the Audi RS6 Avant is the only wagon you need", "04:00:00+00:00", 99),
        ("Jalopnik", "Mercedes-AMG E63 S wagon: the 200-mph grocery getter", "03:30:00+00:00", 101),
        ("The Drive", "Volvo V60 Polestar: the understated fast wagon", "02:00:00+00:00", 112),
        ("Car and Driver", "Porsche Taycan Cross Turismo: the electric longroof", "01:00:00+00:00", 123),
    ]
    items = []
    for src, title, t, seed in raw:
        items.append({
            "source": src, "source_id": src.lower().replace(" ", ""), "homepage": "",
            "title": title, "link": "https://example.com/" + title.lower().replace(" ", "-")[:40],
            "excerpt": "", "image": f"https://picsum.photos/seed/{seed}/900/520",
            "date": base + t, "ts": datetime.fromisoformat(base + t).timestamp(), "categories": [],
        })
    return items


if __name__ == "__main__":
    main()
