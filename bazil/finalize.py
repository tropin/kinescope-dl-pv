#!/usr/bin/env python3
"""Drive the bazil download to true completion, then verify.

1. Wait for any in-flight download_all to finish.
2. Resumable cleanup passes until no expected video is missing (or no progress).
3. Verify every expected video with ffprobe (playable, duration>0).
4. Re-check the 'none' lessons for any hidden embed we might not handle.
5. Write bazil/FINAL_REPORT.json + print a summary.

Usage: venv/bin/python -m bazil.finalize
"""
import re
import sys
import json
import time
import subprocess
from pathlib import Path
from bazil.common import make_session, get, lesson_url
from bazil.download_all import is_valid, do_one, OUT_ROOT, probe_duration

HERE = Path(__file__).resolve().parent
PY_BIN = sys.executable
CATALOG = json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))
HOSTS = json.loads((HERE / "lesson_hosts.json").read_text(encoding="utf-8"))
BYID = {v["lessonId"]: v for v in CATALOG["videos"]}
NOVIDEO_HOSTS = {"none", "ERROR"}
EXPECTED = [lid for lid, h in HOSTS.items() if h not in NOVIDEO_HOSTS]  # 840


def another_run_alive():
    r = subprocess.run(["pgrep", "-f", "bazil.download_all"], capture_output=True, text=True)
    return bool(r.stdout.strip())


def missing_ids():
    out = []
    for lid in EXPECTED:
        v = BYID.get(lid)
        if not v:
            continue
        if not is_valid(OUT_ROOT / v["relpath"]):
            out.append(lid)
    return out


def main():
    log = lambda m: print(m, flush=True)

    log("[finalize] waiting for in-flight download_all to finish...")
    while another_run_alive():
        time.sleep(30)
    log("[finalize] in-flight run done.")

    # cleanup passes
    prev = None
    for p in range(1, 9):
        miss = missing_ids()
        log(f"[finalize] pass {p}: {len(miss)} of {len(EXPECTED)} videos still missing")
        if not miss:
            break
        if prev is not None and len(miss) >= prev:
            log(f"[finalize] no progress ({prev} -> {len(miss)}); stopping cleanup loop")
            # still attempt one more targeted retry below
        prev = len(miss)
        logf = open(HERE / f"run_cleanup_{p}.log", "w")
        proc = subprocess.run([PY_BIN, "-m", "bazil.download_all", "--workers", "4"],
                              stdout=logf, stderr=subprocess.STDOUT)
        logf.close()

    # final verification
    ok, broken, missing = [], [], []
    for lid in EXPECTED:
        v = BYID.get(lid)
        rel = v["relpath"]
        f = OUT_ROOT / rel
        if not f.exists():
            missing.append({"lessonId": lid, "host": HOSTS[lid], "relpath": rel})
        elif is_valid(f):
            ok.append(lid)
        else:
            broken.append({"lessonId": lid, "host": HOSTS[lid], "relpath": rel})

    # re-check the 'none' lessons for any hidden video iframe
    s = make_session()
    hidden = []
    none_ids = [lid for lid, h in HOSTS.items() if h in NOVIDEO_HOSTS]
    for lid in none_ids:
        try:
            html = get(s, lesson_url(lid))
        except Exception:
            continue
        ifr = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
        vidlike = [u for u in ifr if not any(x in u for x in ("google", "yandex", "mailto"))]
        if "data-iframe-src" in html or vidlike:
            hidden.append({"lessonId": lid, "title": BYID.get(lid, {}).get("title"),
                           "iframes": vidlike[:3]})

    total_bytes = sum((OUT_ROOT / BYID[l]["relpath"]).stat().st_size for l in ok)
    report = {
        "expectedVideos": len(EXPECTED),
        "verifiedOk": len(ok),
        "broken": broken,
        "missing": missing,
        "hiddenInNone": hidden,
        "totalGiB": round(total_bytes / 2**30, 2),
    }
    (HERE / "FINAL_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log("\n===== FINAL =====")
    log(f"expected videos : {len(EXPECTED)}")
    log(f"verified OK     : {len(ok)}")
    log(f"broken          : {len(broken)}")
    log(f"missing         : {len(missing)}")
    log(f"hidden-in-none  : {len(hidden)}")
    log(f"total size      : {report['totalGiB']} GiB")
    if broken: log("BROKEN: " + ", ".join(b["relpath"] for b in broken[:10]))
    if missing: log("MISSING: " + ", ".join(m["relpath"] for m in missing[:10]))
    if hidden: log("HIDDEN VIDEOS IN 'none': " + json.dumps(hidden, ensure_ascii=False)[:800])
    log("Report: " + str(HERE / "FINAL_REPORT.json"))
    ok_done = not broken and not missing and not hidden
    log("STATUS: " + ("ALL COMPLETE & VERIFIED" if ok_done else "INCOMPLETE - see above"))


if __name__ == "__main__":
    main()
