#!/usr/bin/env python3
"""Generate a batch of review-ready Instagram posts from live car-news feeds.

  python generate.py            # build today's batch (default 3 posts)
  python generate.py --count 2  # 2 posts
  python generate.py --no-ev    # don't force an EV-performance pick

Output (one folder per run, under posts/<YYYY-MM-DD_HHMM>/):
  post_1.jpg        branded card image (1080x1080)
  post_1.txt        caption + hashtags, ready to paste
  batch.json        machine-readable manifest (used by publish.py)

Nothing is posted. Review the folder, delete any post you don't want, then
publish manually, via a scheduler, or with publish.py once your Meta app is live.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from carnews.caption import build_caption
from carnews.cards import render_card
from carnews.feeds import fetch_all
from carnews.select import select_batch

ROOT = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a batch of Instagram car-news posts.")
    ap.add_argument("--count", type=int, default=3, help="number of posts (default 3)")
    ap.add_argument("--no-ev", action="store_true", help="do not force an EV-performance pick")
    ap.add_argument("--no-wagon", action="store_true", help="do not force a wagon pick")
    args = ap.parse_args()

    print("Fetching feeds…")
    items, status = fetch_all(verbose=True)
    ok_sources = [s["name"] for s in status if s["ok"]]
    if not items:
        print("\nNo stories fetched. Check your internet connection and feeds.json.")
        return
    print(f"\n{len(items)} stories from: {', '.join(ok_sources)}")

    batch = select_batch(items, count=args.count, ensure_ev=not args.no_ev,
                         ensure_wagon=not args.no_wagon)
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
                "ev_performance": bool(story.get("ev_performance")),
                "image_file": img.name,
                "caption_file": f"post_{i}.txt",
                "published": False,
            }
        )
        tag = " [EV-perf]" if story.get("ev_performance") else (" [wagon]" if story.get("wagon") else "")
        print(f"  post_{i}: [{story['source']}]{tag} {story['title'][:70]}")

    (run_dir / "batch.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDone. {len(manifest)} posts in: {run_dir}")
    print("Review them, then post manually or run:  python publish.py --dir \"%s\"" % run_dir)


if __name__ == "__main__":
    main()
