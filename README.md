# kinescope-dl

A fast command-line downloader for [Kinescope](https://kinescope.io)-hosted videos.
It reads the video's DASH manifest, downloads the video and audio tracks (as
byte-range segments), decrypts ClearKey-protected streams when needed, and merges
everything into a single `.mp4` with FFmpeg.

> This is a maintained fork of [`anijackich/kinescope-dl`](https://github.com/anijackich/kinescope-dl),
> updated for the current Kinescope delivery format and for running from source on
> macOS. See [What's different in this fork](#whats-different-in-this-fork).

---

## Requirements

- **Python 3.10+**
- **FFmpeg** — merges the video and audio tracks
- **mp4decrypt** (part of [Bento4](https://www.bento4.com/)) — only needed for
  ClearKey-encrypted videos, but recommended to have installed

### Install the external tools

**macOS (Homebrew):**
```shell
brew install ffmpeg bento4
```

**Debian/Ubuntu:**
```shell
sudo apt install ffmpeg
# Bento4 (mp4decrypt) — download from https://www.bento4.com/downloads/ and put it on PATH
```

**Windows:** download FFmpeg from <https://ffmpeg.org/download.html> and Bento4 from
<https://www.bento4.com/downloads/>, then add both to your `PATH`.

After installing, both binaries should be discoverable:
```shell
ffmpeg -version
mp4decrypt
```

---

## Setup (run from source)

```shell
git clone https://github.com/tropin/kinescope-dl-pv.git
cd kinescope-dl-pv

python3 -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

---

## Usage

```shell
python kinescope-dl.py [OPTIONS] INPUT_URL OUTPUT_FILE
```

- **`INPUT_URL`** — the Kinescope video URL. Accepts either form:
  - `https://kinescope.io/<id>`
  - `https://kinescope.io/embed/<id>`
- **`OUTPUT_FILE`** — path to the output file. The `.mp4` extension is enforced;
  parent directories are created automatically.

If you don't pass `--best-quality`, the tool prints the available resolutions and
asks you to pick one interactively.

### Options

| Option | Description |
| --- | --- |
| `-r, --referer URL` | Referer of the site the video is embedded on. **Required for private/embedded videos** (see below). |
| `--best-quality` | Automatically pick the highest available resolution (non-interactive). |
| `--temp PATH` | Directory for temporary track files (default: `./temp`, auto-deleted). |
| `--ffmpeg-path PATH` | Path to the `ffmpeg` binary (default: `ffmpeg`, looked up on `PATH`). |
| `--mp4decrypt-path PATH` | Path to the `mp4decrypt` binary (default: `mp4decrypt`, looked up on `PATH`). |
| `--help` | Show help and exit. |

### Examples

Public video, choose quality interactively:
```shell
python kinescope-dl.py https://kinescope.io/embed/203613411 ./out/video.mp4
```

Best quality, no prompt:
```shell
python kinescope-dl.py --best-quality https://kinescope.io/embed/203613411 ./out/video.mp4
```

**Private / embedded video** — pass the embedding site as the referer. Kinescope
validates the `Referer` for private videos and will return HTTP 403 without it:
```shell
python kinescope-dl.py -r https://example.com/ --best-quality \
  https://kinescope.io/embed/<id> ./out/video.mp4
```

---

## How to find the video ID

Open the page with the embedded player and inspect the embed `iframe` — its `src`
looks like `https://kinescope.io/embed/<id>`. The `<id>` is what you pass in the URL.
If the player is created dynamically (no static `iframe`), look for the id in the
page's data/scripts or the network requests to `kinescope.io`.

---

## Notes & limitations

- **Encryption:** only **ClearKey** DRM is supported (it is decrypted transparently).
  Widevine/PlayReady-protected videos cannot be downloaded.
- **Referer scope:** the referer you pass is applied to the embed page, the DASH
  manifest, every segment request, and the ClearKey license request — all of which
  private videos validate.
- A `temp/` working directory is created during the download and removed afterwards.

---

## What's different in this fork

- **Runs cleanly on macOS from source** — default binary paths are `ffmpeg` /
  `mp4decrypt` (resolved on `PATH`) instead of `./ffmpeg` / `./mp4decrypt`.
- **Current Kinescope page format** — video-id extraction handles the modern
  `"id":"<uuid>"` embed pages as well as the legacy `id: "..."` format.
- **Byte-range segments** — the current Kinescope DASH manifests serve each track as
  a single CDN file referenced by `<BaseURL>` + `SegmentList` byte ranges (plus an
  initialization range). Downloading now resolves segments against their `BaseURL`,
  sends HTTP `Range` headers, and de-duplicates by `(url, range)`.
- **Referer propagation** — the `--referer` value flows through the manifest,
  segment, and license requests (not just the embed page), enabling downloads of
  private/embedded videos.

---

## Build a standalone binary (optional)

```shell
pip install pyinstaller
export FFMPEG_PATH=$(which ffmpeg)
export MP4DECRYPT_PATH=$(which mp4decrypt)
pyinstaller kinescope-dl.spec
# bundled executable lands in ./dist
```

---

## License

See [LICENSE](LICENSE). Original project by
[anijackich](https://github.com/anijackich/kinescope-dl).
