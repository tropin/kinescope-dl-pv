#!/usr/bin/env python3
"""Shared helpers for the school.bazil.club (GetCourse) downloader.

Auth: a Netscape cookies.txt exported from Chrome (see export_cookies via
yt-dlp CLI). The GetCourse session cookie is httpOnly, so it must come from the
real browser jar.

Resolution chain per lesson:
  lesson page (needs cookies)
    -> data-iframe-src  (signed sign-player URL, IP+time bound)
    -> sign-player JSON  (needs correct IP + referer; no cookies)
    -> masterPlaylistUrl (JWT-signed HLS master; feed to yt-dlp/ffmpeg)
"""
import re
import json
import http.cookiejar
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
COOKIES = HERE / ".cookies.txt"
BASE = "https://school.bazil.club"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def make_session() -> requests.Session:
    jar = http.cookiejar.MozillaCookieJar(str(COOKIES))
    jar.load(ignore_discard=True, ignore_expires=True)
    s = requests.Session()
    s.cookies = jar
    s.headers.update({"User-Agent": UA})
    return s


def sanitize(name: str) -> str:
    name = re.sub(r'[\/\\:*?"<>|]', "-", str(name))
    name = re.sub(r"\s+", " ", name).strip()
    return name.rstrip(". ")


def lesson_url(lesson_id) -> str:
    return f"{BASE}/teach/control/lesson/view/id/{lesson_id}"


def stream_url(stream_id) -> str:
    return f"{BASE}/teach/control/stream/view/id/{stream_id}"


def get(session, url) -> str:
    r = session.get(url, headers={"Referer": BASE + "/"}, timeout=60)
    r.raise_for_status()
    return r.text


def lesson_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return sanitize(m.group(1)) if m else ""


IFRAME_SRC = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']')
EMBED_HOSTS = ("rutube.ru", "vimeo.com", "youtube.com", "youtu.be",
               "vk.com", "vkvideo", "kinescope.io", "boosty")


def lesson_source(session, lesson_id):
    """Inspect a lesson page and return (kind, url, title).

    kind is one of: 'getcourse-vh' (url = HLS master), 'rutube'/other host
    (url = embed page for yt-dlp), or None (no video). Fetches the page once.
    """
    html = get(session, lesson_url(lesson_id))
    title = lesson_title(html)

    m = re.search(r'data-iframe-src="([^"]+)"', html)
    if m and "sign-player" in m.group(1):
        sign_url = m.group(1).replace("&amp;", "&")
        r = session.get(sign_url, headers={"Referer": BASE + "/"}, timeout=60)
        r.raise_for_status()
        mm = re.search(r'"masterPlaylistUrl":"([^"]+)"', r.text)
        master = mm.group(1).replace("\\/", "/") if mm else None
        return ("getcourse-vh", master, title) if master else (None, None, title)

    for u in IFRAME_SRC.findall(html):
        for host in EMBED_HOSTS:
            if host in u:
                return (host.split(".")[0], u.replace("&amp;", "&"), title)

    return (None, None, title)


# Back-compat wrapper (getcourse-vh only).
def resolve_master(session, lesson_id):
    kind, url, title = lesson_source(session, lesson_id)
    return (url if kind == "getcourse-vh" else None), None, title


if __name__ == "__main__":
    import sys
    s = make_session()
    lid = sys.argv[1] if len(sys.argv) > 1 else "347617705"
    kind, url, title = lesson_source(s, lid)
    print("title:", title)
    print("kind:", kind)
    print("url_ok:", bool(url), "len:", len(url or ""))
