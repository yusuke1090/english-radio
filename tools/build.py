#!/usr/bin/env python3
"""English Radio: episodes/NNN.txt（台本）から mp3・episodes.json・feed.xml を作る。

  .venv/bin/python tools/build.py           # 台本が変わった回だけ作り、Release に上げる
  .venv/bin/python tools/build.py --local   # 上げない（audio/ に mp3 を作るだけ）
  .venv/bin/python tools/build.py 3         # 3回目を作り直す

台本の形は README を見る。
"""
import argparse
import asyncio
import email.utils
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import edge_tts
import imageio_ffmpeg
from mutagen.mp3 import MP3

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
AUDIO = ROOT / "audio"
CACHE = AUDIO / "cache"
WORDS_DIR = Path.home() / "apps/textbooks/books/ielts/words"
REPO = "yusuke1090/english-radio"
SITE = "https://yusuke1090.github.io/english-radio"
TAG = "audio"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VERSION = "1"  # 音の作り方を変えたら上げる（全部の回を作り直す）
JST = timezone(timedelta(hours=9))

VOICES = {"SONIA": "en-GB-SoniaNeural", "RYAN": "en-GB-RyanNeural", "JP": "ja-JP-NanamiNeural"}
WORD_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")

SHOW = {
    "title": "English Radio",
    "description": "A British English radio show for the commute: farming and technology, "
    "everyday chat, and IELTS words in context.",
}


def load_dict():
    d = {}
    for f in sorted(WORDS_DIR.glob("*.txt")):
        for line in f.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                p = [x.strip() for x in line.split("|")]
                d.setdefault(p[0].lower(), {"word": p[0], "ja": p[2]})
    return d


def clean(text):
    return WORD_RE.sub(lambda m: m.group(1), text)


def parse(path, dic):
    meta, voices, lines, words = {}, dict(VOICES), [], {}
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("# "):
            lines.append(("#", s[2:]))
        elif m := re.match(r"([A-Z]+):\s*(.+)", s):
            who, text = m.groups()
            if who not in voices:
                sys.exit(f"{path.name}:{n}: {who} の声がない（guest: で決める）")
            lines.append((who, text))
            for sent in SENT_RE.split(text):
                for wm in WORD_RE.finditer(sent):
                    key = (wm.group(2) or wm.group(1)).lower()
                    if key not in dic:
                        sys.exit(f"{path.name}:{n}: 「{key}」が IELTS の単語帳にない")
                    words.setdefault(key, {**dic[key], "who": who, "sentence": clean(sent)})
        elif m := re.match(r"([a-z]+):\s*(.*)", s):
            key, val = m.groups()
            if key == "guest":
                for g in val.split(","):
                    name, voice = g.split("=")
                    voices[name.strip()] = voice.strip()
            else:
                meta[key] = val
        else:
            sys.exit(f"{path.name}:{n}: 読めない行: {s}")
    return meta, voices, lines, list(words.values())


def plan(voices, lines, words):
    chime = [("gap", 0.8), ("chime",), ("gap", 0.6)]
    items = []
    for who, text in lines:
        items += chime if who == "#" else [("tts", voices[who], clean(text)), ("gap", 0.25)]
    sonia, ryan, jp = voices["SONIA"], voices["RYAN"], voices["JP"]
    items += chime + [
        ("tts", ryan, "Before we go, let's look back at today's words. For each one, you'll hear "
         "the word, its meaning in Japanese, and the sentence from today's show."),
        ("gap", 1.0),
    ]
    for w in words:
        items += [("tts", sonia, w["word"] + "."), ("gap", 0.5), ("tts", jp, w["ja"]),
                  ("gap", 0.5), ("tts", voices[w["who"]], w["sentence"]), ("gap", 1.5)]
    items += [("tts", sonia, "That's all for today. Thanks for listening to English Radio, "
               "and drive safely."), ("gap", 0.25), ("tts", ryan, "See you next time. Bye!"),
              ("gap", 1.0)]
    return items


def cache_path(item):
    key = "\n".join(map(str, item))
    return CACHE / (hashlib.sha1(key.encode()).hexdigest()[:16] + ".mp3")


def ffmpeg(*args):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True)


def make_tone(item, out):
    enc = ["-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "48k", str(out)]
    if item[0] == "gap":
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(item[1]), *enc)
    else:  # 区切りの音（2つの音のチャイム）
        expr = ("0.22*sin(2*PI*660*t)*exp(-5*t)"
                "+0.18*sin(2*PI*990*(t-0.16))*exp(-5*(t-0.16))*gte(t\\,0.16)")
        ffmpeg("-f", "lavfi", "-i", f"aevalsrc={expr}:s=24000:d=1.1", *enc)


async def synth(jobs):
    sem = asyncio.Semaphore(4)

    async def one(voice, text, out):
        async with sem:
            part = out.with_suffix(".part")
            for i in range(5):
                try:
                    await edge_tts.Communicate(text, voice).save(str(part))
                    part.rename(out)
                    return
                except Exception as e:  # 読み上げの通信はときどき切れる
                    err = e
                    await asyncio.sleep(3 * (i + 1))
            raise RuntimeError(f"読み上げに失敗: {voice}: {text[:60]}") from err

    await asyncio.gather(*(one(*j) for j in jobs))


def render(n, meta, items, out):
    CACHE.mkdir(parents=True, exist_ok=True)
    jobs, files = [], []
    for item in items:
        p = cache_path(item)
        files.append(p)
        if p.exists():
            continue
        if item[0] == "tts":
            jobs.append((item[1], item[2], p))
        else:
            make_tone(item, p)
    print(f"  読み上げ {len(jobs)} 本（キャッシュ {len(items) - len(jobs)}）")
    asyncio.run(synth(jobs))
    lst = CACHE / f"list-{n:03d}.txt"
    lst.write_text("".join(f"file '{f}'\n" for f in files))
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst),
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "24000", "-ac", "1",
           "-c:a", "libmp3lame", "-b:a", "48k",
           "-metadata", f"title={n}. {meta['title']}", "-metadata", "artist=English Radio",
           "-metadata", "album=English Radio", "-metadata", f"track={n}", str(out))


def gh(*args, check=True):
    return subprocess.run(["gh", *args, "-R", REPO], check=check, capture_output=True, text=True)


def write_feed(eps):
    now = email.utils.format_datetime(datetime.now(JST))
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
        'xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{SHOW['title']}</title>",
        f"<link>{SITE}/</link>",
        f'<atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>',
        "<language>en-gb</language>",
        f"<description>{escape(SHOW['description'])}</description>",
        f"<lastBuildDate>{now}</lastBuildDate>",
        "<itunes:author>English Radio</itunes:author>",
        f'<itunes:image href="{SITE}/cover.jpg"/>',
        '<itunes:category text="Education"><itunes:category text="Language Learning"/>'
        "</itunes:category>",
        "<itunes:explicit>false</itunes:explicit>",
        "<itunes:type>serial</itunes:type>",
        "<itunes:block>Yes</itunes:block>",
    ]
    for e in eps:
        date = datetime.fromisoformat(e["date"]).replace(hour=6, tzinfo=JST)
        out += [
            "<item>",
            f"<title>{e['n']}. {escape(e['title'])}</title>",
            f"<description>{escape(e['description'])}</description>",
            f'<enclosure url="{e["url"]}" length="{e["bytes"]}" type="audio/mpeg"/>',
            f'<guid isPermaLink="false">english-radio-{e["n"]:03d}</guid>',
            f"<pubDate>{email.utils.format_datetime(date)}</pubDate>",
            f"<itunes:duration>{e['seconds']}</itunes:duration>",
            f"<itunes:episode>{e['n']}</itunes:episode>",
            "<itunes:episodeType>full</itunes:episodeType>",
            "</item>",
        ]
    out += ["</channel>", "</rss>", ""]
    (ROOT / "feed.xml").write_text("\n".join(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="Release に上げない")
    ap.add_argument("redo", nargs="*", type=int, help="作り直す回の番号")
    args = ap.parse_args()

    dic = load_dict()
    index = ROOT / "episodes.json"
    old = {e["n"]: e for e in json.loads(index.read_text())} if index.exists() else {}
    if not args.local and gh("release", "view", TAG, check=False).returncode:
        gh("release", "create", TAG, "--title", "Audio", "--notes", "English Radio の音声（tools/build.py が上げる）")

    eps = []
    for path in sorted(EPISODES.glob("[0-9][0-9][0-9].txt")):
        n = int(path.stem)
        meta, voices, lines, words = parse(path, dic)
        h = hashlib.sha1((VERSION + path.read_text() + "".join(w["ja"] for w in words)).encode()).hexdigest()[:10]
        out = AUDIO / f"ep{n:03d}.mp3"
        e = old.get(n)
        if not e or e["hash"] != h or n in args.redo or not (e.get("uploaded") or out.exists()):
            print(f"{n}. {meta['title']}")
            render(n, meta, plan(voices, lines, words), out)
            e = {"hash": h, "bytes": out.stat().st_size, "seconds": round(MP3(out).info.length)}
            print(f"  {e['seconds'] // 60}分{e['seconds'] % 60}秒・{e['bytes'] / 1e6:.1f}MB・{len(words)}語")
        if not args.local and not (e.get("uploaded") == h):
            gh("release", "upload", TAG, str(out), "--clobber")
            e["uploaded"] = h
        eps.append({
            "n": n, "title": meta["title"], "description": meta.get("description", ""),
            "date": meta["date"], "hash": e["hash"], "bytes": e["bytes"], "seconds": e["seconds"],
            "uploaded": e.get("uploaded"),
            "url": f"https://github.com/{REPO}/releases/download/{TAG}/ep{n:03d}.mp3?v={e['hash']}",
            "words": [{"word": w["word"], "ja": w["ja"]} for w in words],
        })
    index.write_text(json.dumps(eps, ensure_ascii=False, indent=1) + "\n")
    write_feed(eps)
    print(f"{len(eps)} 回分の episodes.json と feed.xml を書いた")


if __name__ == "__main__":
    main()
