#!/usr/bin/env python3
"""Download every video in catalog/catalog.json into a Month/Lesson/Video tree.

- Output root: <project>/DaMa Club Videos/<relpath from catalog>
- Resumable: skips files that already exist and pass an ffprobe validity check.
- Parallel: a small worker pool (default 4) runs the CLI per video.
- Each video gets its own temp dir so parallel downloads don't collide.
- Writes catalog/download_manifest.json with per-video status.

Usage:
  python3 catalog/download_all.py [--workers N] [--limit N] [--section month|library]
"""
import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT_DIR = Path(__file__).resolve().parent.parent
PY = str(ROOT_DIR / "venv" / "bin" / "python")
CLI = str(ROOT_DIR / "kinescope-dl.py")
OUT_ROOT = ROOT_DIR / "DaMa Club Videos"
TEMP_ROOT = ROOT_DIR / ".dl_temp"
REFERER = "https://damaclub.online/"
MANIFEST = ROOT_DIR / "catalog" / "download_manifest.json"
MIN_SIZE = 200_000  # bytes; smaller => treat as failed/partial


def probe_duration(path: Path):
    """Return media duration in seconds, or None if unreadable."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def is_valid(path: Path):
    if not path.exists() or path.stat().st_size < MIN_SIZE:
        return False
    d = probe_duration(path)
    return bool(d and d > 0)


def download_one(v, attempt_retry=True):
    target = OUT_ROOT / v["relpath"]
    if is_valid(target):
        return {"kid": v["kid"], "relpath": v["relpath"], "status": "skip",
                "size": target.stat().st_size}

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = TEMP_ROOT / v["kid"]
    cmd = [PY, CLI, "-r", REFERER, "--best-quality",
           "--temp", str(temp_dir), v["embed"], str(target)]

    last_err = ""
    for attempt in range(2 if attempt_retry else 1):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and is_valid(target):
            shutil.rmtree(temp_dir, ignore_errors=True)
            d = probe_duration(target)
            return {"kid": v["kid"], "relpath": v["relpath"], "status": "ok",
                    "size": target.stat().st_size, "duration": round(d or 0, 1)}
        last_err = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or [""]
        last_err = last_err[0][:300]
        shutil.rmtree(temp_dir, ignore_errors=True)
        if target.exists() and not is_valid(target):
            target.unlink(missing_ok=True)

    return {"kid": v["kid"], "relpath": v["relpath"], "status": "fail", "error": last_err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="download at most N (0 = all)")
    ap.add_argument("--section", choices=["month", "library"], default=None)
    args = ap.parse_args()

    catalog = json.loads((ROOT_DIR / "catalog" / "catalog.json").read_text(encoding="utf-8"))
    videos = catalog["videos"]
    if args.section:
        videos = [v for v in videos if v["section"] == args.section]
    if args.limit:
        videos = videos[: args.limit]

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    total = len(videos)
    print(f"Downloading {total} videos with {args.workers} workers -> {OUT_ROOT}", flush=True)
    results, done = [], 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(download_one, v): v for v in videos}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            done += 1
            mark = {"ok": "✓", "skip": "·", "fail": "✗"}.get(r["status"], "?")
            extra = f' {r.get("duration","")}s' if r["status"] == "ok" else (f' ERR {r.get("error","")}' if r["status"] == "fail" else "")
            print(f"[{done}/{total}] {mark} {r['relpath']}{extra}", flush=True)

    ok = sum(1 for r in results if r["status"] == "ok")
    skip = sum(1 for r in results if r["status"] == "skip")
    fail = [r for r in results if r["status"] == "fail"]
    MANIFEST.write_text(json.dumps({"total": total, "ok": ok, "skip": skip,
                                    "fail": len(fail), "results": results},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(TEMP_ROOT, ignore_errors=True)

    print(f"\n=== DONE: {ok} downloaded, {skip} skipped, {len(fail)} failed (of {total}) ===")
    for r in fail:
        print(f"  FAIL {r['relpath']}  {r.get('error','')}")
    print(f"Manifest: {MANIFEST}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
