#!/usr/bin/env python3
"""
One-off migration off Libsyn.

For every episode in the Libsyn RSS feed:
  1. use the MP3 already in the local archive if its size matches the feed's
     enclosure length, otherwise download it from Libsyn into the archive,
  2. upload it to the R2 bucket (via rclone),
  3. write audio_url / audio_length / duration / guid into the post's front matter.

Safe to re-run: existing archive files are reused, rclone skips identical
objects, and front matter keys are replaced rather than duplicated.

Credentials come from ~/.config/unnamedre/r2.env
(R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET).

Usage:
  python3 _sitegen/migrate_from_libsyn.py --dry-run
  python3 _sitegen/migrate_from_libsyn.py --only 78
  python3 _sitegen/migrate_from_libsyn.py
"""

import argparse
import datetime
import email.utils
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

FEED_URL = "https://reverseengineering.libsyn.com/rss"
MEDIA_BASE = "https://media.unnamedre.com"
R2_PREFIX = "episodes"
ARCHIVE_DIR = Path("/mnt/media/urep_archive/mp3_archive/Unnamed Reverse Engineering Podcast")
SNAPSHOT_DIR = Path("/mnt/media/urep_archive/misc")
ENV_FILE = Path.home() / ".config/unnamedre/r2.env"
CACHE_CONTROL = "public, max-age=604800"
USER_AGENT = "unnamedre-migration/1.0"

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
REPO = Path(__file__).resolve().parent.parent
POSTS = REPO / "_posts"
FM_KEYS = ("audio_url", "audio_length", "duration", "guid")


def load_env(path):
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET") if not env.get(k)]
    if missing:
        sys.exit(f"{path} is missing {', '.join(missing)}")
    return env


def fetch(url, dest=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        if dest is None:
            return resp.read()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
        tmp.rename(dest)


def episode_id(title):
    """'078 - Foo' -> '078'; '026a Easter Egg Extra' -> '026a'."""
    m = re.match(r"\s*(\d+[a-z]?)\b", title)
    if not m:
        raise ValueError(f"can't find episode number in {title!r}")
    return m.group(1)


def safe_filename(s):
    return re.sub(r'[/\\:*?"<>|]', "_", s).strip()


def find_archived(ep, length):
    """Archive files are named 'YYYYMMDD-NNN - Title.mp3'. Return the one for
    this episode whose size matches the feed (026 has two copies)."""
    for f in sorted(ARCHIVE_DIR.glob("*.mp3")):
        m = re.match(r"\d{8}-(\d+[a-z]?) ", f.name)
        if m and m.group(1) == ep and f.stat().st_size == length:
            return f
    return None


def ffprobe_seconds(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def hms(seconds):
    s = int(round(seconds))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def find_post(ep):
    """Map an episode id to its post via `permalink: episode/<n>`."""
    if not ep.isdigit():
        return None
    want = f"permalink: episode/{int(ep)}"
    hits = [p for p in POSTS.glob("*.md") if want in p.read_text().splitlines()]
    if len(hits) > 1:
        raise RuntimeError(f"multiple posts for episode {ep}: {hits}")
    return hits[0] if hits else None


def update_front_matter(path, fields):
    text = path.read_text()
    if not text.startswith("---\n"):
        raise RuntimeError(f"{path} has no front matter")
    end = text.index("\n---", 4)
    lines = text[4:end].split("\n")
    lines = [l for l in lines if l.split(":", 1)[0].strip() not in FM_KEYS]
    for k in FM_KEYS:
        v = fields[k]
        lines.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
    new = "---\n" + "\n".join(lines) + text[end:]
    if new != text:
        path.write_text(new)
        return True
    return False


def rclone_upload(env, src, key, dry_run):
    rc_env = dict(
        os.environ,
        RCLONE_S3_PROVIDER="Cloudflare",
        RCLONE_S3_ACCESS_KEY_ID=env["R2_ACCESS_KEY_ID"],
        RCLONE_S3_SECRET_ACCESS_KEY=env["R2_SECRET_ACCESS_KEY"],
        RCLONE_S3_ENDPOINT=env["R2_ENDPOINT"],
        RCLONE_S3_NO_CHECK_BUCKET="true",
    )
    cmd = [
        "rclone", "copyto", str(src), f":s3:{env['R2_BUCKET']}/{key}",
        "--header-upload", "Content-Type: audio/mpeg",
        "--header-upload", f"Cache-Control: {CACHE_CONTROL}",
    ]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, env=rc_env, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="download nothing, upload nothing, edit nothing")
    ap.add_argument("--only", action="append", default=[], help="episode id(s) to process, e.g. 78 or 026a")
    ap.add_argument("--feed", help="use a local copy of the feed instead of fetching it")
    args = ap.parse_args()

    env = load_env(ENV_FILE)
    only = {o.lstrip("0") or "0" for o in args.only}

    feed_xml = Path(args.feed).read_bytes() if args.feed else fetch(FEED_URL)
    items = ET.fromstring(feed_xml).find("channel").findall("item")
    print(f"{len(items)} items in feed")

    if not args.dry_run:
        snap = SNAPSHOT_DIR / f"libsyn_rss_{datetime.date.today():%Y%m%d}.xml"
        if not snap.exists():
            snap.write_bytes(feed_xml)
            print(f"saved feed snapshot {snap}")

    problems = []
    for item in reversed(items):  # oldest first
        title = item.findtext("title").strip()
        ep = episode_id(title)
        if only and ep.lstrip("0") not in only:
            continue

        enc = item.find("enclosure")
        src_url = enc.get("url")
        feed_len = int(enc.get("length") or 0)
        guid = item.findtext("guid").strip()
        pub = email.utils.parsedate_to_datetime(item.findtext("pubDate"))

        archive_file = find_archived(ep, feed_len) or ARCHIVE_DIR / safe_filename(f"{pub:%Y%m%d}-{title}.mp3")
        key = f"{R2_PREFIX}/unnamedre-{ep}.mp3"
        print(f"\n== {title}\n   {src_url}\n   -> {archive_file.name}\n   -> r2:{key}")

        if args.dry_run:
            post = find_post(ep)
            have = "archived" if archive_file.exists() else "DOWNLOAD"
            print(f"   {have}; post: {post.name if post else 'NONE'}")
            continue

        if not archive_file.exists():
            print("   downloading...")
            fetch(src_url, archive_file)
        size = archive_file.stat().st_size
        if feed_len and size != feed_len:
            problems.append(f"{ep}: downloaded {size} bytes, feed says {feed_len}")
            print(f"   WARNING size {size} != feed length {feed_len}")

        seconds = ffprobe_seconds(archive_file)
        rclone_upload(env, archive_file, key, dry_run=False)

        post = find_post(ep)
        if post is None:
            problems.append(f"{ep}: no post on the site (uploaded and archived only)")
            print("   no post for this episode")
            continue
        changed = update_front_matter(post, {
            "audio_url": f"{MEDIA_BASE}/{key}",
            "audio_length": size,
            "duration": hms(seconds),
            "guid": guid,
        })
        print(f"   {'updated' if changed else 'unchanged'} {post.name} ({size} bytes, {hms(seconds)})")

    print("\nDone.")
    if problems:
        print("Check these:")
        for p in problems:
            print("  -", p)


if __name__ == "__main__":
    main()
