# bazil — school.bazil.club (GetCourse) bulk downloader

Scrapes a whole [school.bazil.club](https://school.bazil.club) GetCourse package
and downloads every lesson video into a folder tree that mirrors the site,
verified playable, in the best available quality.

> **Not Kinescope.** Despite living in this repo, school.bazil.club does **not**
> use Kinescope. Its videos are served by GetCourse's **native video hosting**
> (`vh-api-*.gceuproxy.com`) and, for some lessons, embedded from **RuTube**. So
> `kinescope-dl` does not apply — this pipeline handles both hosts via `yt-dlp`.

## What it does

```
Package (stream) ─▶ courses ─▶ (optional) modules ─▶ lessons ─▶ video
```

For the "ALL IN" package (stream id `935412619`) this is **855 lessons**:
**758 GetCourse-VH + 82 RuTube + 15 text-only** = **840 downloadable videos**.

Per lesson the video source is resolved live (the site flag `data-vh-files` is
unreliable and is ignored):

- **GetCourse VH** — lesson page → `data-iframe-src` (signed, IP+time bound) →
  `sign-player` JSON → `masterPlaylistUrl` (JWT-signed HLS master) → `yt-dlp`
  picks the best rendition (up to 1080p).
- **RuTube** — a `rutube.ru/play/embed/…` iframe → `yt-dlp` downloads it directly
  (best rendition, up to 720p in practice).
- **none** — genuinely text/audio lessons (podcasts, "итоги недели"); skipped.

Output tree, e.g.:
```
export/Пакет «ALL IN»/01 Курс «БАЧАТА ТОПЧИКИ»…/02 «Традишка»/01 Урок 1. Виды качей и бедер (база).mp4
```

## Requirements

- Python venv at `../venv` with `requests` and `yt-dlp` installed
  (`../venv/bin/pip install requests yt-dlp`)
- `yt-dlp`, `ffmpeg`, `ffprobe` on `PATH`
- Chrome logged in to school.bazil.club (for the session cookie)

## Usage

Run from the repo root.

```shell
# 1. Export the browser session cookie jar (httpOnly GetCourse cookie).
#    Re-run whenever the session expires. May prompt for macOS Keychain access.
yt-dlp --cookies-from-browser chrome --cookies bazil/.cookies.txt \
       --skip-download "https://school.bazil.club/teach/control/lesson/view/id/<any-lesson-id>"
#    (the "Unsupported URL" error is harmless — the cookie file is what we need)

# 2. Crawl the package tree -> bazil/catalog.json
venv/bin/python -m bazil.crawl [root_stream_id]      # default root = 935412619

# 3. Download every video -> ./export  (resumable, parallel, verified)
venv/bin/python -m bazil.download_all --workers 4

# 4. Drive to completion + verify everything -> bazil/FINAL_REPORT.json
venv/bin/python -m bazil.finalize
```

Re-running `download_all` skips files that already exist and pass an `ffprobe`
validity check, so it is safe to interrupt and resume.

## Files

| File | Purpose |
|------|---------|
| `common.py` | Auth session + `lesson_source()` (resolves GC-VH master / RuTube embed per lesson) |
| `crawl.py` | Walks the package tree → `catalog.json` (mirrors site structure) |
| `download_all.py` | Per lesson: resolve → `yt-dlp` best quality → `ffprobe` verify; resumable, parallel; writes `download_manifest.json` |
| `finalize.py` | Waits for a run, resumable cleanup passes until nothing is missing, verifies all, re-checks the `none` lessons for hidden embeds → `FINAL_REPORT.json` |
| `export_cookies.py` | Alternative cookie exporter using yt-dlp's cookie library (the CLI method above is usually simpler) |
| `catalog.json` | Snapshot of the crawled tree (generated) |
| `lesson_hosts.json` | Per-lesson host classification (generated) |
| `FINAL_REPORT.json` | Last verification result (generated) |

Not committed (gitignored): `.cookies.txt` (secret), `*.log`, `download_manifest.json`, and `export/` (the videos).

## Last verified run

840 / 840 videos verified playable · 0 broken · 0 missing · ~135 GB.
