"""Build an Instagram caption + hashtags from a story dict (offline/deterministic)."""
from __future__ import annotations

import re

BASE_TAGS = ["#cars", "#carnews", "#automotive", "#carsofinstagram", "#auto"]

# Per-category hashtag sets (prepended so the lead tags match the category).
CATEGORY_TAGS = {
    "performance": ["#performancecars", "#sportscar", "#supercar", "#horsepower", "#carreview"],
    "racing": ["#motorsport", "#racing", "#racecar", "#trackday", "#grandprix"],
    "wagon": ["#wagon", "#stationwagon", "#estatecar", "#longroof", "#wagonlife"],
}

# Per-category one-line tagline shown in the caption body.
CATEGORY_TAGLINE = {
    "performance": "\U0001f3ce️ Performance review — ICE or electric, if it's fast it's here.",
    "racing": "\U0001f3c1 Racing — results, drama and machinery from the track.",
    "wagon": "\U0001f6fb Wagon Watch — for the longroof faithful.",
}

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
    cat_tags = CATEGORY_TAGS.get(story.get("category"), [])
    tags = [t for t in cat_tags if t not in tags] + tags
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
    tagline = CATEGORY_TAGLINE.get(story.get("category"))
    if tagline:
        lines += [tagline, ""]
    lines.append(f"\U0001f4f0 Source: {source}. Full story via the link — read it, support the writers.")
    lines.append("\U0001f449 Follow for daily performance reviews, racing & wagons.")
    lines += ["", " ".join(build_hashtags(story))]
    return "\n".join(lines)
