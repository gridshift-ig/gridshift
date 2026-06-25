"""Build an Instagram caption + hashtags from a story dict (offline/deterministic)."""
from __future__ import annotations

import re

BASE_TAGS = ["#cars", "#carnews", "#automotive", "#carsofinstagram", "#auto"]
EV_TAGS = ["#ev", "#electriccars", "#evperformance"]
PERF_TAGS = ["#performancecars", "#sportscar", "#supercar", "#horsepower"]
WAGON_TAGS = ["#wagon", "#stationwagon", "#estatecar", "#longroof", "#wagonlife"]

KEYWORD_TAGS = {
    "tesla": "#tesla", "porsche": "#porsche", "ferrari": "#ferrari",
    "lamborghini": "#lamborghini", "bmw": "#bmw", "audi": "#audi",
    "mercedes": "#mercedes", "ford": "#ford", "chevrolet": "#chevrolet",
    "corvette": "#corvette", "mustang": "#mustang", "toyota": "#toyota",
    "honda": "#honda", "nissan": "#nissan", "hyundai": "#hyundai",
    "racing": "#motorsport", "review": "#carreview", "first drive": "#firstdrive",
    "hybrid": "#hybrid", "truck": "#trucks", "suv": "#suv",
}


def _first_sentences(text, max_chars=220):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in (". ", "! ", "? "):
        i = cut.rfind(sep)
        if i > 60:
            return cut[: i + 1].strip()
    i = cut.rfind(" ")
    return (cut[:i] if i > 0 else cut).strip() + "…"


def build_hashtags(story, max_tags=12):
    tags = []
    hay = f"{story['title']} {story.get('excerpt','')} {' '.join(story.get('categories', []))}".lower()
    for kw, tag in KEYWORD_TAGS.items():
        if kw in hay and tag not in tags:
            tags.append(tag)
    if story.get("ev_performance"):
        tags = EV_TAGS + tags
    elif any(t in hay for t in ("performance", "sports car", "supercar", "horsepower", "track")):
        tags += [t for t in PERF_TAGS if t not in tags]
    if story.get("wagon"):
        tags = [t for t in WAGON_TAGS if t not in tags] + tags
    for t in BASE_TAGS:
        if t not in tags:
            tags.append(t)
    return tags[:max_tags]


def build_caption(story):
    headline = story["title"].strip()
    summary = _first_sentences(story.get("excerpt", ""))
    source = story["source"]
    lines = [headline]
    if summary:
        lines += ["", summary]
    lines.append("")
    if story.get("ev_performance"):
        lines += ["⚡ Electric performance — where EVs meet the sports-car world.", ""]
    elif story.get("wagon"):
        lines += ["\U0001f6fb Wagon Watch — for the longroof faithful.", ""]
    lines.append(f"\U0001f4f0 Source: {source}. Full story via the link — read it, support the writers.")
    lines.append("\U0001f449 Follow for daily car news, reviews, EV performance & wagons.")
    lines += ["", " ".join(build_hashtags(story))]
    return "\n".join(lines)
