#!/usr/bin/env python3
"""Build a download catalog for the DaMa club (damaclub.online) Kinescope videos.

Source of truth is the site's own /cabinet/_lessons-data.js. We parse the LESSONS
and LIVES object literals out of it (no JS eval) and reproduce the site's labelling
(theory = "N.1", practice = "N.2") to build a flat list of downloadable videos, each
with its kinescope embed URL and a Month / Lesson / video relative output path.

Usage: python3 catalog/build_catalog.py
Output: catalog/catalog.json
"""
import re
import json
import requests
from pathlib import Path

SOURCE = "https://damaclub.online/cabinet/_lessons-data.js?v=20260614a"
REFERER = "https://damaclub.online/"
HERE = Path(__file__).resolve().parent

# Month names come straight from the site's damaMonth.list() (stable, 6 months).
MONTHS = {
    1: "Волны", 2: "Sensual", 3: "Руки",
    4: "Хэдроллы", 5: "Баланс", 6: "Футворки",
}
KIND_WORD = {"theory": "Теория", "practice": "Практика"}


def sanitize(s: str) -> str:
    s = re.sub(r'[\/\\:*?"<>|]', "-", str(s))
    s = re.sub(r"\s+", " ", s).strip()
    return s.rstrip(".")


def pad2(n) -> str:
    return f"{int(n):02d}"


def region(text: str, start_marker: str, end_marker: str) -> str:
    a = text.index(start_marker)
    b = text.index(end_marker, a)
    return text[a:b]


def parse_entries(block: str):
    """Yield (id, body_text) for each top-level 'mX-...': { ... } entry.

    Splits on the next top-level key rather than matching braces, which is robust
    against the nested { kid: ... } objects.
    """
    headers = list(re.finditer(r"'(m\d+-[\w]+)':\s*\{", block))
    for i, h in enumerate(headers):
        start = h.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(block)
        yield h.group(1), block[start:end]


def field(body: str, name: str):
    m = re.search(rf"\b{name}:\s*'([^']*)'", body)
    if m:
        return m.group(1)
    m = re.search(rf"\b{name}:\s*(\d+)", body)
    return int(m.group(1)) if m else None


def kid_of(body: str, kind: str):
    m = re.search(rf"\b{kind}:\s*\{{\s*kid:\s*'([^']+)'", body)
    return m.group(1) if m else None


def embed(kid: str) -> str:
    return f"https://kinescope.io/embed/{kid}"


def main():
    code = requests.get(SOURCE, headers={"Referer": REFERER, "User-Agent": "Mozilla/5.0"}, timeout=30).text

    lessons_block = region(code, "var LESSONS = {", "var LIVES = {")
    lives_block = region(code, "var LIVES = {", "window.DAMA_MONTHS")

    videos = []

    for lid, body in parse_entries(lessons_block):
        month = field(body, "month")
        num = field(body, "num")
        title = field(body, "title")
        if month is None or num is None or title is None:
            continue
        month_folder = f"{pad2(month)} {sanitize(MONTHS.get(month, f'Месяц {month}'))}"
        lesson_folder = f"{pad2(num)} {sanitize(title)}"
        for kind in ("theory", "practice"):
            kid = kid_of(body, kind)
            if not kid:
                continue
            label = f"{num}.{'1' if kind == 'theory' else '2'}"
            video_name = f"{label} {KIND_WORD[kind]}"
            videos.append({
                "section": "month", "monthNum": month, "monthName": MONTHS.get(month),
                "lessonId": lid, "lessonNum": num, "lessonTitle": title,
                "kind": kind, "label": label, "videoName": video_name,
                "kid": kid, "embed": embed(kid),
                "relpath": str(Path(month_folder) / lesson_folder / f"{sanitize(video_name)}.mp4"),
            })

    for lid, body in parse_entries(lives_block):
        month = field(body, "month")
        num = field(body, "num")
        title = field(body, "title")
        kid = field(body, "kid")
        if not kid or month is None:
            continue
        month_folder = f"{pad2(month)} {sanitize(MONTHS.get(month, f'Месяц {month}'))}"
        video_name = f"Эфир {num} — {sanitize(title)}"
        videos.append({
            "section": "month", "monthNum": month, "monthName": MONTHS.get(month),
            "lessonId": lid, "lessonNum": 900 + (num or 0), "lessonTitle": "Эфиры",
            "kind": "live", "label": f"live{num}", "videoName": video_name,
            "kid": kid, "embed": embed(kid),
            "relpath": str(Path(month_folder) / "Эфиры" / f"{sanitize(video_name)}.mp4"),
        })

    catalog = {
        "source": SOURCE.split("?")[0],
        "referer": REFERER,
        "generatedCount": len(videos),
        "months": [{"num": n, "name": MONTHS[n]} for n in sorted(MONTHS)],
        "videos": videos,
    }
    out = HERE / "catalog.json"
    out.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    # summary
    by_month = {}
    for v in videos:
        by_month.setdefault(v["monthNum"], []).append(v)
    print(f"Total downloadable videos: {len(videos)}  ->  {out}")
    for n in sorted(by_month):
        vs = by_month[n]
        lessons = len({v["lessonId"] for v in vs if v["kind"] != "live"})
        lives = sum(1 for v in vs if v["kind"] == "live")
        print(f"  Month {n} ({MONTHS[n]}): {len(vs)} videos — {lessons} lessons, {lives} lives")


if __name__ == "__main__":
    main()
