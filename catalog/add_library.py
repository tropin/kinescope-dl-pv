#!/usr/bin/env python3
"""Merge the library.html (Библиотека знаний) videos into catalog/catalog.json.

library.html is Supabase-rendered, so its cards can't be fetched server-side; the
kid + category + title for all 54 cards were captured from the rendered DOM and
saved to catalog/library_rows.tsv (tab-separated: kid<TAB>category<TAB>title).

Library output tree:  Библиотека знаний / <NN category> / <MM title>.mp4

Usage: python3 catalog/add_library.py
"""
import re
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = HERE / "library_rows.tsv"
CATALOG = HERE / "catalog.json"
REFERER = "https://damaclub.online/"
LIBRARY_ROOT = "Библиотека знаний"


def sanitize(s: str) -> str:
    s = re.sub(r'[\/\\:*?"<>|]', "-", str(s))
    s = re.sub(r"\s+", " ", s).strip()
    return s.rstrip(".")


def pad2(n) -> str:
    return f"{int(n):02d}"


def main():
    rows = []
    for line in ROWS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        kid, category, title = line.split("\t")
        rows.append((kid.strip(), category.strip(), title.strip()))

    # order categories by first appearance, and videos within each category
    cat_order, cat_index, within = [], {}, {}
    library_videos = []
    for kid, category, title in rows:
        if category not in cat_index:
            cat_order.append(category)
            cat_index[category] = len(cat_order)
            within[category] = 0
        within[category] += 1
        cat_n = cat_index[category]
        vid_n = within[category]
        cat_folder = f"{pad2(cat_n)} {sanitize(category)}"
        file_name = f"{pad2(vid_n)} {sanitize(title)}.mp4"
        library_videos.append({
            "section": "library",
            "monthNum": None,
            "monthName": LIBRARY_ROOT,
            "lessonId": f"lib-{cat_n}-{vid_n}",
            "lessonNum": vid_n,
            "lessonTitle": category,
            "kind": "library",
            "label": f"{cat_n}.{vid_n}",
            "videoName": title,
            "kid": kid,
            "embed": f"https://kinescope.io/embed/{kid}",
            "relpath": str(Path(LIBRARY_ROOT) / cat_folder / file_name),
        })

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    # drop any previously-added library entries, then append fresh
    catalog["videos"] = [v for v in catalog["videos"] if v.get("section") != "library"]
    catalog["videos"].extend(library_videos)
    catalog["generatedCount"] = len(catalog["videos"])
    catalog["librarySource"] = "https://damaclub.online/cabinet/library.html"
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Library videos added: {len(library_videos)} (in {len(cat_order)} categories)")
    for cat in cat_order:
        n = sum(1 for k, c, t in rows if c == cat)
        print(f"  {cat}: {n}")
    print(f"Total catalog videos now: {catalog['generatedCount']}")


if __name__ == "__main__":
    main()
