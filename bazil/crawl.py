#!/usr/bin/env python3
"""Crawl the school.bazil.club package tree and build bazil/catalog.json.

Tree: Package -> courses -> (optional) modules -> lessons. Each stream page
contains either a <ul class="lesson-list"> of lessons and/or a set of child
course/module cards linking to further stream pages. Lessons that actually hold
a video carry data-vh-files on their <li>.

Output relpath mirrors the site:  <Package>/<Course>/[<Module>/]<NN Title>.mp4

Usage: venv/bin/python bazil/crawl.py [root_stream_id]
"""
import re
import sys
import json
from pathlib import Path
from bazil.common import make_session, get, stream_url, sanitize

HERE = Path(__file__).resolve().parent
ROOT_ID = "935412619"                       # Пакет «ALL IN»
EXCLUDE = {"935412590"}                      # Sale 2026 (parent breadcrumb)

LESSON_LI = re.compile(r'<li([^>]*\bdata-lesson-id="(\d+)"[^>]*)>(.*?)</li>', re.S)
TITLE_IN_LI = re.compile(r'class="[^"]*\blink title\b[^"]*"[^>]*>(.*?)<', re.S)
VH_IN_LI = re.compile(r'data-vh-files="(\d+)"')
STREAM_LINK = re.compile(r'href=["\'](?:https?://school\.bazil\.club)?/teach/control/stream/view/id/(\d+)["\']')


def page_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return sanitize(re.sub(r"\s+", " ", m.group(1))) if m else "untitled"


def parse_lessons(html: str):
    """Ordered list of (lesson_id, title, has_video)."""
    out = []
    for attrs, lid, block in LESSON_LI.findall(html):
        tm = TITLE_IN_LI.search(block)
        title = sanitize(re.sub(r"<[^>]+>", " ", tm.group(1))) if tm else f"lesson-{lid}"
        has_video = bool(VH_IN_LI.search(attrs))
        out.append((lid, title, has_video))
    return out


def child_streams(html: str, self_id: str):
    """Ordered unique child stream ids (modules/courses), minus self/parents."""
    seen, out = set(), []
    for sid in STREAM_LINK.findall(html):
        if sid in seen or sid == self_id or sid in EXCLUDE or sid == ROOT_ID:
            continue
        seen.add(sid)
        out.append(sid)
    return out


def crawl(session, sid, ancestors, visited, videos, order_idx):
    if sid in visited:
        return
    visited.add(sid)
    html = get(session, stream_url(sid))
    title = page_title(html)
    path = ancestors + [f"{order_idx:02d} {title}"] if ancestors else [title]

    lessons = parse_lessons(html)
    children = child_streams(html, sid)
    print(f"{'  '*len(ancestors)}[{sid}] {title} — {len(lessons)} lessons, {len(children)} sub", flush=True)

    for n, (lid, ltitle, has_video) in enumerate(lessons, 1):
        rel = Path(*path) / f"{n:02d} {sanitize(ltitle)}.mp4"
        videos.append({
            "lessonId": lid, "title": ltitle, "hasVideo": has_video,
            "path": path, "order": n, "relpath": str(rel),
        })

    for n, cid in enumerate(children, 1):
        crawl(session, cid, path, visited, videos, n)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else ROOT_ID
    s = make_session()
    videos, visited = [], set()
    # crawl root's children as top-level courses (root itself = package folder)
    html = get(s, stream_url(root))
    pkg_title = page_title(html)
    courses = child_streams(html, root)
    print(f"ROOT [{root}] {pkg_title} — {len(courses)} courses\n", flush=True)
    visited.add(root)
    for n, cid in enumerate(courses, 1):
        crawl(s, cid, [pkg_title], visited, videos, n)

    with_video = [v for v in videos if v["hasVideo"]]
    catalog = {
        "site": "https://school.bazil.club",
        "root": root, "package": pkg_title,
        "totalLessons": len(videos),
        "videosWithFile": len(with_video),
        "videos": videos,
    }
    out = HERE / "catalog.json"
    out.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nTotal lessons: {len(videos)}  (with video file: {len(with_video)})  -> {out}")


if __name__ == "__main__":
    main()
