#!/usr/bin/env python3
"""Generate review-ready Instagram posts from live car-news feeds.

  python generate.py                          # 3-post batch (one per category)
  python generate.py --count 1 --category auto  # single post, rotated by UTC hour
  python generate.py --category racing          # single racing post (perf backfill)

Rotation: with --category auto, the category cycles performance -> racing ->
wagon based on the UTC hour ((hour // 3) % 3), so 3-hourly runs spread the
categories across the day. Empty racing/wagon slots backfill with performance.

Pickup-truck stories are removed before selection per feeds.json "truck_filter"
(default: drop ICE trucks, keep EV trucks).

Output (one folder per run, under posts/<YYYY-MM-DD_HHMM>/):
  post_1.jpg  branded card | post_1.txt  caption | batch.json  manifest
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from carnews.caption import build_caption
from carnews.cards import render_card
from carnews.feeds import USER_AGENT, fetch_all
from carnews.select import SLOTS, filter_trucks, select_category_batch, select_for_slots

ROOT = Path(__file__).resolve().parent

MIN_PHOTO_PX = 500  # skip logos / tracking pixels / tiny thumbs


def _download_photo(url, dest):
    """Download a story's publisher photo for use as the card background.

    Returns the saved path on success, else None (caller falls back to the
    branded gradient). Mirrors the website's use of the same RSS image.
    """
    if not url:
        return None
    try:
        from PIL import Image
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        Image.open(BytesIO(data)).verify()          # validate it is a real image
        img = Image.open(BytesIO(data))             # reopen (verify exhausts it)
        if min(img.size) < MIN_PHOTO_PX:            # too small to fill a 1080 card
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.convert("RGB").save(dest, "JPEG", quality=92)
        return dest
    except Exception:
        return None


def _rotated_category() -> str:
    """Pick a category from SLOTS based on the current UTC hour."""
    hour = datetime.now(timezone.utc).hour
    return SLOTS[(hour // 3) % len(SLOTS)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Instagram car-news posts.")
    ap.add_argument("--count", type=int, default=3,
                    help="posts per batch when no --category (default 3)")
    ap.add_argument("--category", choices=SLOTS + ["auto"], default=None,
                    help="post a single story of this category; 'auto' rotates by UTC hour")
    args = ap.parse_args()

    print("Fetching feeds…")
    items, status = fetch_all(verbose=True)
    ok_sources = [s["name"] for s in status if s["ok"]]
    if not items:
        print("\nNo stories fetched. Check your internet connection and feeds.json.")
        return
    print(f"\n{len(items)} stories from: {', '.join(ok_sources)}")

    before = len(items)
    items = filter_trucks(items)
    dropped = before - len(items)
    if dropped:
        print(f"Truck filter removed {dropped} story(ies).")

    if args.category:
        cat = _rotated_category() if args.category == "auto" else args.category
        print(f"Single-post run, category: {cat}")
        batch = select_for_slots(items, [cat])[:1]
    else:
        batch = select_category_batch(items, count=args.count)

    if not batch:
        print("Nothing new to post (all candidates already posted).")
        return

    run_dir = ROOT / "posts" / datetime.now().strftime("%Y-%m-%d_%H%M")
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i, story in enumerate(batch, 1):
        story["footer"] = "Full story — link in bio"
        bg = _download_photo(story.get("image", ""), run_dir / f"src_{i}.jpg")
        if bg:
            story["bg_image"] = str(bg)
        img = render_card(story, run_dir / f"post_{i}.jpg")
        caption = build_caption(story)
        (run_dir / f"post_{i}.txt").write_text(caption, encoding="utf-8")
        manifest.append(
            {
                "n": i,
                "title": story["title"],
                "source": story["source"],
                "link": story["link"],
                "category": story.get("category"),
                "image_file": img.name,
                "photo": bool(story.get("bg_image")),
                "caption_file": f"post_{i}.txt",
                "published": False,
            }
        )
        tag = f" [{story.get('category') or 'general'}]"
        print(f"  post_{i}: [{story['source']}]{tag} {story['title'][:70]}")

    (run_dir / "batch.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDone. {len(manifest)} post(s) in: {run_dir}")
    print("Review them, then post manually or run:  python publish.py --dir \"%s\"" % run_dir)


if __name__ == "__main__":
    main()
