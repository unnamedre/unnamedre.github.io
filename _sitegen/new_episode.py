#!/usr/bin/env python3
"""
Publish a new episode: archive the MP3, upload it to R2 and write the post.

  python3 _sitegen/new_episode.py 79 "The Kids Need E-Waste" episode_79.mp3 \
      --subtitle "Chuck E. Cheese animatronics with Frank Palazzolo and Evan Allen" \
      --notes "~/Downloads/Episode 079 - /Episode079_shownotes.md"

Steps:
  1. copy the MP3 into the local archive as 'YYYYMMDD-NNN - Title.mp3'
  2. upload it to R2 as episodes/unnamedre-NNN.mp3
  3. write _posts/YYYY-MM-DD-NNN_-_Title.md with audio_url, audio_length,
     duration and a fresh guid; the body is the Markdown show notes

Re-running is safe. If the post already exists, only its audio fields are
refreshed and its guid is kept. Replacing an already uploaded MP3 with a
different file needs --replace.

Nothing goes live until the commit is pushed. Credentials come from
~/.config/unnamedre/r2.env.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

MEDIA_BASE = "https://media.unnamedre.com"
R2_PREFIX = "episodes"
ARCHIVE_DIR = Path("/mnt/media/urep_archive/mp3_archive/Unnamed Reverse Engineering Podcast")
ENV_FILE = Path.home() / ".config/unnamedre/r2.env"
CACHE_CONTROL = "public, max-age=604800"

REPO = Path(__file__).resolve().parent.parent
POSTS = REPO / "_posts"
AUDIO_KEYS = ("audio_url", "audio_length", "duration")


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


def rclone(env, *args, capture=False):
    rc_env = dict(
        os.environ,
        RCLONE_S3_PROVIDER="Cloudflare",
        RCLONE_S3_ACCESS_KEY_ID=env["R2_ACCESS_KEY_ID"],
        RCLONE_S3_SECRET_ACCESS_KEY=env["R2_SECRET_ACCESS_KEY"],
        RCLONE_S3_ENDPOINT=env["R2_ENDPOINT"],
        RCLONE_S3_NO_CHECK_BUCKET="true",
    )
    return subprocess.run(["rclone", *args], env=rc_env, check=True, text=True, capture_output=capture)


def remote_size(env, key):
    out = rclone(env, "lsjson", f":s3:{env['R2_BUCKET']}/{key}", capture=True).stdout
    items = json.loads(out or "[]")
    return items[0]["Size"] if items else None


def duration_hms(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    s = int(round(float(out)))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def post_filename(date, full_title):
    # Spaces become underscores and other punctuation is dropped (matches older posts).
    title = "".join(c for c in full_title.replace(" ", "_") if c.isalnum() or c in "_-")
    return f"{date:%Y-%m-%d}-{title}.md"


def find_post(num):
    want = f"permalink: episode/{num}"
    hits = [p for p in POSTS.glob("*.md") if want in p.read_text().splitlines()]
    if len(hits) > 1:
        sys.exit(f"multiple posts claim episode {num}: {hits}")
    return hits[0] if hits else None


def yaml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def update_audio_fields(path, fields):
    text = path.read_text()
    end = text.index("\n---", 4)
    lines = [l for l in text[4:end].split("\n") if l.split(":", 1)[0].strip() not in AUDIO_KEYS]
    if not any(l.startswith("guid:") for l in lines):
        lines.append(f"guid: {yaml_str(str(uuid.uuid4()))}")
    for k in AUDIO_KEYS:
        v = fields[k]
        lines.append(f"{k}: {yaml_str(v) if isinstance(v, str) else v}")
    path.write_text("---\n" + "\n".join(lines) + text[end:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("number", type=int, help="episode number, e.g. 79")
    ap.add_argument("title", help='title without the number, e.g. "The Kids Need E-Waste"')
    ap.add_argument("mp3", type=Path, help="final exported MP3")
    ap.add_argument("--subtitle", default="", help="short one-line summary")
    ap.add_argument("--notes", type=Path, help="Markdown show notes for the post body")
    ap.add_argument("--date", help='publish time, "YYYY-MM-DD HH:MM" local (default: now)')
    ap.add_argument("--replace", action="store_true", help="overwrite an uploaded MP3 that differs")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    args = ap.parse_args()

    mp3 = args.mp3.expanduser()
    if not mp3.is_file():
        sys.exit(f"no such file: {mp3}")
    notes = args.notes.expanduser() if args.notes else None
    if notes and not notes.is_file():
        sys.exit(f"no such notes file: {notes}")

    now = datetime.datetime.now().astimezone()
    date = (datetime.datetime.strptime(args.date, "%Y-%m-%d %H:%M").astimezone() if args.date else now).replace(microsecond=0)
    if date > now + datetime.timedelta(minutes=5):
        print(f"NOTE: {date} is in the future. Jekyll skips future posts, so the episode only "
              "appears once a build runs after that time (GitHub Pages builds on push).")

    num = args.number
    full_title = f"{num:03d} - {args.title.strip()}"
    key = f"{R2_PREFIX}/unnamedre-{num:03d}.mp3"
    size = mp3.stat().st_size
    duration = duration_hms(mp3)
    archive_file = ARCHIVE_DIR / re.sub(r'[/\\:*?"<>|]', "_", f"{date:%Y%m%d}-{full_title}.mp3")
    existing_post = find_post(num)
    post = existing_post or POSTS / post_filename(date, full_title)

    print(f"{full_title}\n  {size} bytes, {duration}")
    print(f"  archive: {archive_file}")
    print(f"  r2:      {key}")
    print(f"  post:    {post.name} ({'update audio fields' if existing_post else 'new'})")
    if args.dry_run:
        return

    env = load_env(ENV_FILE)

    # 1. archive
    if ARCHIVE_DIR.is_dir():
        if not archive_file.exists():
            shutil.copy2(mp3, archive_file)
            print("  archived")
        elif archive_file.stat().st_size != size:
            sys.exit(f"{archive_file} exists with a different size; move it aside first")
    else:
        print(f"  WARNING: {ARCHIVE_DIR} not mounted, skipped archiving. Copy it there later.")

    # 2. upload
    current = remote_size(env, key)
    if current is not None and current != size and not args.replace:
        sys.exit(f"r2:{key} already exists with {current} bytes (new file: {size}). Use --replace if intended.")
    rclone(env, "copyto", str(mp3), f":s3:{env['R2_BUCKET']}/{key}",
           "--header-upload", "Content-Type: audio/mpeg",
           "--header-upload", f"Cache-Control: {CACHE_CONTROL}")
    if remote_size(env, key) != size:
        sys.exit("upload size mismatch; check the bucket")
    print("  uploaded")

    # 3. post
    fields = {"audio_url": f"{MEDIA_BASE}/{key}", "audio_length": size, "duration": duration}
    if existing_post:
        update_audio_fields(post, fields)
    else:
        body = notes.read_text().strip() + "\n" if notes else "Show notes go here.\n"
        post.write_text("\n".join([
            "---",
            "layout: episode",
            f"title: {yaml_str(full_title)}",
            f"subtitle: {yaml_str(args.subtitle)}",
            f"date: {date:%Y-%m-%d %H:%M:%S %z}",
            "categories: episode",
            f"permalink: episode/{num}",
            f"audio_url: {yaml_str(fields['audio_url'])}",
            f"audio_length: {size}",
            f"duration: {yaml_str(duration)}",
            f"guid: {yaml_str(str(uuid.uuid4()))}",
            "---",
            "",
        ]) + body)
    print(f"  wrote {post.relative_to(REPO)}")
    print("\nNext: review the post, preview it, then commit and push.")


if __name__ == "__main__":
    main()
