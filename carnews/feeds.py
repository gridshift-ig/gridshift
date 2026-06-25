"""Fetch and parse RSS/Atom car-news feeds (Python stdlib only).

Used by generate.py to pull candidate stories. Handles gzip and both
RSS (<item>) and Atom (<entry>) formats. Feeds that fail are skipped, not fatal.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "feeds.json").read_text(encoding="utf-8"))

USER_AGENT = "Mozilla/5.0 (CarNewsAggregator/1.0; +laptop)"
TIMEOUT = 20


def _http_get(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", s or ""))).strip()


def _cdata(s: str) -> str:
    return re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)


def _tag(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.S | re.I)
    return _cdata(m.group(1)).strip() if m else ""


def _image(block: str) -> str:
    for pat in (
        r'<media:thumbnail[^>]*\burl="([^"]+)"',
        r'<media:content[^>]*\burl="([^"]+)"',
        r'<enclosure[^>]*\burl="([^"]+)"[^>]*type="image',
        r'<enclosure[^>]*type="image[^"]*"[^>]*\burl="([^"]+)"',
    ):
        m = re.search(pat, block, re.I)
        if m:
            return unescape(m.group(1))
    content = _tag(block, "content:encoded") or _tag(block, "description")
    m = re.search(r'<img[^>]*\bsrc="([^"]+)"', content, re.I)
    return unescape(m.group(1)) if m else ""


def _date(block: str):
    raw = (
        _tag(block, "pubDate")
        or _tag(block, "published")
        or _tag(block, "updated")
        or _tag(block, "dc:date")
    )
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_feed(xml: str, source: dict) -> list[dict]:
    is_atom = bool(re.search(r"<feed[\s>]", xml)) and not re.search(r"<rss[\s>]", xml)
    block_re = r"<entry[\s>].*?</entry>" if is_atom else r"<item[\s>].*?</item>"
    out = []
    for block in re.findall(block_re, xml, re.S | re.I):
        title = _strip_tags(_tag(block, "title"))
        if is_atom:
            m = re.search(r'<link[^>]*rel="alternate"[^>]*href="([^"]+)"', block, re.I) or re.search(
                r'<link[^>]*href="([^"]+)"', block, re.I
            )
            link = unescape(m.group(1)) if m else ""
        else:
            link = _tag(block, "link")
        link = link.strip()
        if not title or not link:
            continue
        desc = _tag(block, "description") or _tag(block, "summary") or _tag(block, "content")
        cats = [
            _strip_tags(re.sub(r"</?category[^>]*>", "", c, flags=re.I))
            for c in re.findall(r"<category[^>]*>.*?</category>", block, re.S | re.I)
        ]
        dt = _date(block)
        out.append(
            {
                "source": source["name"],
                "source_id": source["id"],
                "homepage": source.get("homepage", ""),
                "title": title,
                "link": link,
                "excerpt": _strip_tags(desc)[:400],
                "image": _image(block),
                "date": dt.isoformat() if dt else None,
                "ts": dt.timestamp() if dt else 0,
                "categories": [c for c in cats if c],
            }
        )
    return out


def fetch_all(verbose: bool = True) -> tuple[list[dict], list[dict]]:
    """Return (items, source_status). Bad feeds are skipped gracefully."""
    items, status = [], []
    for src in CONFIG["feeds"]:
        rec = {"id": src["id"], "name": src["name"], "ok": False, "count": 0, "error": None}
        try:
            xml = _http_get(src["url"])
            parsed = parse_feed(xml, src)
            items.extend(parsed)
            rec.update(ok=bool(parsed), count=len(parsed), error=None if parsed else "no items parsed")
        except Exception as e:  # noqa: BLE001 - report, never crash the batch
            rec["error"] = str(e)
        if verbose:
            mark = "ok " if rec["ok"] else "SKIP"
            print(f"  [{mark}] {src['name']:<14} {rec['count']:>2} items"
                  + (f"  ({rec['error']})" if rec["error"] else ""))
        status.append(rec)
    # de-dupe by link, newest first
    seen, deduped = set(), []
    for it in sorted(items, key=lambda x: x["ts"], reverse=True):
        if it["link"] not in seen:
            seen.add(it["link"])
            deduped.append(it)
    return deduped, status
