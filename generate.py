#!/usr/bin/env python3
"""Generate review-ready Instagram posts from live car-news feeds.

  python generate.py                          # 3-post batch (one per category)
  python generate.py --count 1 --category auto  # single post, rotated by UTC hour
  python generate.py --category racing          # single racing post (perf backfill)

Rotation: with --category auto, the category cycles performance -> racing ->
wagon based on the UTC hour ((hour // 3) % 3), so 3-hourly runs spread the
categories across the day. Empty racing/wagon slots backfill with performance.

Output (one folder per run, under posts/<YYYY-MM-DD_HHMM>/):
  post_1.jpg  branded card | post_1.txt  caption | batch.json  manifest
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from carnews.caption import build_caption
from carnews.cards import render_card
from carnews.feeds import fetch_all
from carnews.select import SLOTS, select_category_batch, select_for_slots

ROOT = Path(__file__).resolve().parent


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
