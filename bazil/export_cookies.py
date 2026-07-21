#!/usr/bin/env python3
"""Export the current Chrome cookie jar (incl. httpOnly GetCourse session) to a
Netscape cookies.txt that both the crawler (requests) and yt-dlp CLI reuse.

Run once (and re-run if the session expires). Requires Chrome logged in to
school.bazil.club. On macOS this may trigger a Keychain prompt.

Usage: venv/bin/python bazil/export_cookies.py
"""
from pathlib import Path
from yt_dlp.cookies import extract_cookies_from_browser

HERE = Path(__file__).resolve().parent
OUT = HERE / ".cookies.txt"

def main():
    jar = extract_cookies_from_browser("chrome")
    # keep only bazil + gceuproxy/getcourse cookies to keep the file small
    jar.save(str(OUT), ignore_discard=True, ignore_expires=True)
    n = sum(1 for _ in open(OUT) if _.strip() and not _.startswith("#"))
    print(f"Saved {n} cookies -> {OUT}")

if __name__ == "__main__":
    main()
