#!/usr/bin/env python3
"""Download every video in bazil/catalog.json into ./export, mirroring the site.

Per lesson: resolve a fresh master HLS URL (signed, expires fast) -> yt-dlp best
quality -> ffprobe validity check. Resumable (skips valid files), parallel, and
writes bazil/download_manifest.json with per-lesson status.

Usage:
  venv/bin/python -m bazil.download_all [--workers N] [--limit N] [--only-missing]
"""
import sys
import time
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor, as_completed
from bazil.common import make_session, lesson_source

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT_ROOT = ROOT / "export"
MANIFEST = HERE / "download_manifest.json"
MIN_SIZE = 300_000  # bytes


def probe_duration(path: Path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
            capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except Exception:
        return None


def is_valid(path: Path):
    if not path.exists() or path.stat().st_size < MIN_SIZE:
        return False
    d = probe_duration(path)
    return bool(d and d > 0)


def ytdlp(url, target: Path, referer):
    part = target.with_suffix(".dl.mp4")
    cmd = ["yt-dlp", "--no-update", "--quiet", "--no-warnings",
           "-S", "res,br,tbr", "--referer", referer,
           "--merge-output-format", "mp4",
           "--concurrent-fragments", "8", "--retries", "10",
           "--fragment-retries", "20", "--file-access-retries", "10",
           "-o", str(part), url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0 and is_valid(part):
        part.replace(target)
        return True, ""
    err = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or [""]
    part.unlink(missing_ok=True)
    return False, err[0][:300]


# one session per thread (requests.Session isn't guaranteed thread-safe)
import threading
_local = threading.local()
def sess():
    if not hasattr(_local, "s"):
        _local.s = make_session()
    return _local.s


def do_one(v):
    target = OUT_ROOT / v["relpath"]
    if is_valid(target):
        return {"lessonId": v["lessonId"], "relpath": v["relpath"],
                "status": "skip", "size": target.stat().st_size}
    target.parent.mkdir(parents=True, exist_ok=True)
    kind = url = None
    last = ""
    for attempt in range(4):  # resolve is signed + network-flaky; retry transient errors
        try:
            kind, url, _ = lesson_source(sess(), v["lessonId"])
            break
        except Exception as e:
            last = f"resolve: {e}"[:300]
            _local.s = make_session()  # fresh connection pool
            time.sleep(2 * (attempt + 1))
    if kind is None and last:
        return {"lessonId": v["lessonId"], "relpath": v["relpath"], "status": "fail", "error": last}
    if not url:
        return {"lessonId": v["lessonId"], "relpath": v["relpath"], "status": "novideo"}
    # getcourse master needs the vh origin as referer; external embeds use the site
    referer = (f"{urlsplit(url).scheme}://{urlsplit(url).netloc}/"
               if kind == "getcourse-vh" else "https://school.bazil.club/")
    err = ""
    for _ in range(2):
        ok, err = ytdlp(url, target, referer)
        if ok:
            return {"lessonId": v["lessonId"], "relpath": v["relpath"], "status": "ok",
                    "kind": kind, "size": target.stat().st_size,
                    "duration": round(probe_duration(target) or 0, 1)}
    return {"lessonId": v["lessonId"], "relpath": v["relpath"], "status": "fail",
            "kind": kind, "error": err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-missing", action="store_true",
                    help="(deprecated) previously filtered to the hasVideo flag; "
                         "every lesson is now probed live, so this is a no-op")
    args = ap.parse_args()

    catalog = json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))
    videos = catalog["videos"]  # probe all lessons; text-only ones return 'novideo'
    if args.limit:
        videos = videos[:args.limit]

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    total = len(videos)
    print(f"Downloading {total} videos, {args.workers} workers -> {OUT_ROOT}", flush=True)

    results, done = [], 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(do_one, v): v for v in videos}
        for fut in as_completed(futs):
            r = fut.result(); results.append(r); done += 1
            mark = {"ok": "OK", "skip": "==", "fail": "XX", "novideo": ".."}.get(r["status"], "??")
            extra = f' {r.get("duration","")}s {round(r.get("size",0)/1e6,1)}MB' if r["status"] == "ok" else (
                f' ERR {r.get("error","")}' if r["status"] == "fail" else "")
            print(f"[{done}/{total}] {mark} {r['relpath']}{extra}", flush=True)
            if done % 10 == 0:
                MANIFEST.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    by = {}
    for r in results:
        by[r["status"]] = by.get(r["status"], 0) + 1
    MANIFEST.write_text(json.dumps({"summary": by, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n=== {by} ===")
    print("Manifest:", MANIFEST)


if __name__ == "__main__":
    main()
