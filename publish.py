#!/usr/bin/env python3
"""Auto-publish a generated batch to Instagram via the Instagram Graph API
(Instagram-login flow - graph.instagram.com).

config.json (or GitHub secrets via env) needs:
  ig_user_id      your Instagram user id
  access_token    the long-lived IGAA... token
  image_base_url  public base URL where each run's images are hosted

Usage:
  python publish.py --dir "posts/2026-06-25_1430"
  python publish.py --refresh-token
  python publish.py --whoami
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRAPH = "https://graph.instagram.com/v21.0"
GRAPH_ROOT = "https://graph.instagram.com"


def load_config() -> dict:
    import os
    p = ROOT / "config.json"
    cfg = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    cfg["access_token"] = os.environ.get("IG_ACCESS_TOKEN", cfg.get("access_token", ""))
    cfg["ig_user_id"] = os.environ.get("IG_USER_ID", cfg.get("ig_user_id", ""))
    cfg["image_base_url"] = os.environ.get("IMAGE_BASE_URL", cfg.get("image_base_url", ""))
    if not cfg.get("access_token") or "PASTE" in cfg["access_token"]:
        sys.exit("No access token. Set IG_ACCESS_TOKEN env var or fill config.json.")
    if not cfg.get("ig_user_id"):
        sys.exit("No ig_user_id. Set IG_USER_ID env var or fill config.json.")
    return cfg


def _post(url: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def whoami(cfg: dict) -> dict:
    q = urllib.parse.urlencode({"fields": "id,username", "access_token": cfg["access_token"]})
    return _get(f"{GRAPH}/{cfg['ig_user_id']}?{q}")


def create_container(cfg: dict, image_url: str, caption: str) -> str:
    out = _post(f"{GRAPH}/{cfg['ig_user_id']}/media",
                {"image_url": image_url, "caption": caption, "access_token": cfg["access_token"]})
    return out["id"]


def publish_container(cfg: dict, creation_id: str) -> str:
    out = _post(f"{GRAPH}/{cfg['ig_user_id']}/media_publish",
                {"creation_id": creation_id, "access_token": cfg["access_token"]})
    return out["id"]


def refresh_long_lived_token(cfg: dict) -> str:
    q = urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": cfg["access_token"]})
    out = _get(f"{GRAPH_ROOT}/refresh_access_token?{q}")
    return out["access_token"]


def publish_batch(run_dir: Path) -> None:
    cfg = load_config()
    base = cfg["image_base_url"].rstrip("/")
    manifest_path = run_dir / "batch.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    posted_links = []

    for post in manifest:
        if post.get("published"):
            print(f"  post_{post['n']}: already published, skip")
            continue
        image_url = f"{base}/{run_dir.name}/{post['image_file']}"
        caption = (run_dir / post["caption_file"]).read_text(encoding="utf-8")
        print(f"  post_{post['n']}: container... ({image_url})")
        cid = create_container(cfg, image_url, caption)
        time.sleep(8)
        media_id = publish_container(cfg, cid)
        post["published"] = True
        post["media_id"] = media_id
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if post.get("link"):
            posted_links.append(post["link"])
        print(f"           published  media_id={media_id}")
        time.sleep(5)

    if posted_links:
        from carnews.select import mark_posted
        mark_posted(posted_links)
    print("Batch complete.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Publish a generated batch to Instagram.")
    ap.add_argument("--dir", help="path to a posts/<run> folder")
    ap.add_argument("--refresh-token", action="store_true", help="print a refreshed long-lived token")
    ap.add_argument("--whoami", action="store_true", help="print the token's account id + username")
    args = ap.parse_args()

    if args.refresh_token:
        print(refresh_long_lived_token(load_config()))
        return
    if args.whoami:
        print(whoami(load_config()))
        return
    if not args.dir:
        sys.exit("Pass --dir posts/<run> (or --refresh-token / --whoami).")
    publish_batch(Path(args.dir))


if __name__ == "__main__":
    main()
