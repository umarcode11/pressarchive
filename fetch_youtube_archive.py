#!/usr/bin/env python3
"""
Pulls a YouTube channel's videos and their transcripts, and writes them
out in the same article schema used for the Word archive (date, headline,
body, byline, byline_category) so they can be indexed with build_index.py
exactly like the print archive.

Requires yt-dlp (pip install yt-dlp). Run this on your own machine, this
sandbox can't reach YouTube.

Usage:
    python3 fetch_youtube_archive.py "https://www.youtube.com/@UmarCheemaExclusive" \
        --out articles_vlog.json --lang en,ur

Notes:
- Pulls auto-generated captions where available; tries each language in
  --lang in order and uses the first one found per video.
- Videos with no captions at all (rare, but happens on older uploads) are
  skipped and logged to <out>_skipped.json rather than silently dropped.
- This only reads public data, no login or API key needed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def get_video_list(channel_url):
    """Flat-playlist listing: fast, just IDs/titles/dates, no transcript yet."""
    cmd = [
        "yt-dlp", "--flat-playlist", "--dump-json",
        "--playlist-end", "100000",
        f"{channel_url.rstrip('/')}/videos",
    ]
    code, out, err = run(cmd)
    if code != 0 and not out:
        print(f"yt-dlp failed to list channel videos: {err[:500]}", file=sys.stderr)
        sys.exit(1)
    videos = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        videos.append({
            "id": d.get("id"),
            "title": d.get("title"),
            "upload_date": d.get("upload_date"),  # may be None in flat mode
        })
    return videos


def vtt_to_text(vtt_path):
    """Strip WebVTT timestamps/cue formatting down to plain spoken text."""
    with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    out_lines = []
    seen = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if re.match(r"^\d\d:\d\d:\d\d\.\d\d\d\s*-->", line):
            continue
        if re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)  # strip inline timing tags
        if line and line not in seen:
            out_lines.append(line)
            seen.add(line)
    return " ".join(out_lines)


def fetch_transcript(video_id, langs, workdir):
    """Try each language in order, return (text, lang_used) or (None, None)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    for lang in langs:
        out_tmpl = os.path.join(workdir, f"{video_id}.%(ext)s")
        cmd = [
            "yt-dlp", "--skip-download", "--write-auto-sub",
            "--sub-lang", lang, "--sub-format", "vtt",
            "--sleep-requests", "4",
            "-o", out_tmpl, url,
        ]
        run(cmd)
        vtt_path = os.path.join(workdir, f"{video_id}.{lang}.vtt")
        if os.path.exists(vtt_path):
            text = vtt_to_text(vtt_path)
            os.remove(vtt_path)
            if text.strip():
                return text, lang
    return None, None


def to_date_str(yyyymmdd):
    if not yyyymmdd or len(yyyymmdd) != 8:
        return None
    from datetime import datetime
    return datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%B %-d, %Y") if os.name != "nt" \
        else datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%B %#d, %Y")


def load_existing(out_path):
    """Load already-fetched articles (if any) so reruns can resume rather
    than refetching everything from scratch."""
    articles, skipped = [], []
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            articles = json.load(f)
    skipped_path = out_path.replace(".json", "_skipped.json")
    if os.path.exists(skipped_path):
        with open(skipped_path, "r", encoding="utf-8") as f:
            skipped = json.load(f)
    done_ids = {a["video_id"] for a in articles} | {s["id"] for s in skipped}
    return articles, skipped, done_ids


def save_progress(out_path, articles, skipped):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    with open(out_path.replace(".json", "_skipped.json"), "w", encoding="utf-8") as f:
        json.dump(skipped, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel_url")
    ap.add_argument("--out", default="articles_vlog.json")
    ap.add_argument("--lang", default="en,ur", help="comma-separated caption languages to try, in order")
    args = ap.parse_args()

    langs = [l.strip() for l in args.lang.split(",") if l.strip()]

    print("Fetching channel video list (this lists everything, no transcripts yet)...")
    videos = get_video_list(args.channel_url)
    print(f"Found {len(videos)} videos.")

    articles, skipped, done_ids = load_existing(args.out)
    if done_ids:
        print(f"Resuming: {len(done_ids)} videos already processed in a previous run, skipping those.")

    with tempfile.TemporaryDirectory() as workdir:
        for i, v in enumerate(videos, 1):
            vid = v["id"]
            if vid in done_ids:
                continue
            print(f"[{i}/{len(videos)}] {v['title'][:60]}...")
            text, lang_used = fetch_transcript(vid, langs, workdir)
            if not text:
                skipped.append(v)
                save_progress(args.out, articles, skipped)
                continue
            # if upload_date wasn't in flat-playlist output, fetch it now
            date_str = to_date_str(v.get("upload_date"))
            if date_str is None:
                code, out, err = run(["yt-dlp", "--dump-json", "--skip-download",
                                       f"https://www.youtube.com/watch?v={vid}"])
                try:
                    full = json.loads(out)
                    date_str = to_date_str(full.get("upload_date"))
                except Exception:
                    date_str = None
            articles.append({
                "source_file": "youtube_umar_cheema_exclusive",
                "date": date_str,
                "headline": v["title"],
                "byline": "Umar Cheema",
                "body": text,
                "parse_warning": None,
                "byline_category": "umar_cheema",
                "source_type": "video",
                "video_id": vid,
                "caption_lang": lang_used,
            })
            save_progress(args.out, articles, skipped)  # write after every video

    print(f"\nDone. {len(articles)} videos with transcripts -> {args.out}")
    if skipped:
        print(f"{len(skipped)} videos had no usable captions in {langs}, "
              f"logged to {args.out.replace('.json', '_skipped.json')}")


if __name__ == "__main__":
    main()
