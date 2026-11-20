#!/usr/bin/env python3
"""English Radio: episodes/NNN.txt（台本）から mp3・episodes.json・feed.xml を作る。

  .venv/bin/python tools/build.py           # 台本が変わった回だけ作り、Release に上げる
  .venv/bin/python tools/build.py --local   # 上げない（audio/ に mp3 を作るだけ）
  .venv/bin/python tools/build.py 3 5       # 3回目と5回目を作り直す
  .venv/bin/python tools/build.py --only 3  # 3回目だけ作る（ほかは触らない）

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
import numpy as np
from mutagen.mp3 import MP3
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import music  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
AUDIO = ROOT / "audio"
CACHE = AUDIO / "cache"
WORDS_DIR = Path.home() / "apps/textbooks/books/ielts/words"
REPO = "yusuke1090/english-radio"
SITE = "https://yusuke1090.github.io/english-radio"
TAG = "audio"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VERSION = "2"  # 音の作り方を変えたら上げる（全部の回を作り直す）
JST = timezone(timedelta(hours=9))
SR = music.SR

JP_VOICE = "ja-JP-NanamiNeural"
WORD_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")
LINE_RE = re.compile(r"([A-Z][A-Z_]*)(?:\s*\(([a-z ]+)\))?:\s*(.+)")

# 気分: (速さ %, 高さ Hz, 大きさ %)
MOODS = {
    "excited": (12, 8, 10), "happy": (6, 5, 0), "cheerful": (8, 6, 5), "sad": (-12, -6, -10),
    "quiet": (-6, -2, -35), "whisper": (-10, -3, -50), "angry": (8, -3, 15), "shout": (10, 10, 20),
    "slow": (-15, 0, 0), "fast": (18, 2, 0), "tired": (-14, -6, -15), "nervous": (10, 4, -5),
    "serious": (-6, -4, 0), "dramatic": (-10, -5, 5), "scared": (8, 6, -20), "proud": (-3, 2, 10),
    "dry": (-4, -3, -5), "warm": (-5, -2, 0), "loud": (4, 4, 20), "calm": (-8, -2, -5),
}
SHOW = {
    "title": "English Radio",
    "description": "English for the commute: stories in three parts, talks, vlogs, comedy, "
    "radio drama and music shows, with a different voice every time.",
}
MUSIC_SRC = (Path(__file__).resolve().parent / "music.py").read_text()


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


def directive(s, where):
    p = s[1:-1].split()
    cmd = p[0] if p else ""
    try:
        if cmd == "music":
            music.STYLES[p[1].partition(".")[0]]
            return ("music", p[1], float(p[2]) if len(p) > 2 else 12.0)
        if cmd in ("bgm", "amb"):
            name = None if p[1] == "off" else p[1]
            if name and cmd == "bgm":
                music.STYLES[name.partition(".")[0]]
            if name and cmd == "amb":
                music._amb_loop(name)
            return (cmd, name, float(p[2]) if len(p) > 2 else None)
        if cmd == "sfx":
            music.sfx(p[1])
            nums = [float(x) for x in p[2:] if x != "&"]
            return ("sfx", p[1], nums[0] if nums else 1.0, "&" in p)
        if cmd == "pause":
            return ("pause", float(p[1]))
    except (KeyError, IndexError, ValueError) as e:
        sys.exit(f"{where}: 読めない指示 {s}（{e}）")
    sys.exit(f"{where}: 知らない指示 {s}")


def parse(path, dic):
    meta, voices, items, words = {}, {"JP": (JP_VOICE, 0, 0)}, [], {}
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        s = raw.strip()
        where = f"{path.name}:{n}"
        if not s:
            continue
        if s.startswith("# "):
            items.append(("head", s[2:]))
        elif s.startswith("["):
            items.append(directive(s, where))
        elif m := LINE_RE.fullmatch(s):
            who, mood, text = m.groups()
            if who not in voices:
                sys.exit(f"{where}: {who} の声がない（voice: で決める）")
            if mood and mood not in MOODS:
                sys.exit(f"{where}: 気分「{mood}」がない（{', '.join(MOODS)}）")
            items.append(("say", who, mood, text))
            for sent in SENT_RE.split(text):
                for wm in WORD_RE.finditer(sent):
                    key = (wm.group(2) or wm.group(1)).lower()
                    if key not in dic:
                        sys.exit(f"{where}: 「{key}」が IELTS の単語帳にない")
                    words.setdefault(key, {**dic[key], "who": who, "sentence": clean(sent)})
        elif m := re.fullmatch(r"([a-z]+):\s*(.*)", s):
            key, val = m.groups()
            if key == "voice":
                name, spec = (x.strip() for x in val.split("=", 1))
                vid, *mods = spec.split()
                rate = next((int(x[:-1]) for x in mods if x.endswith("%")), 0)
                pitch = next((int(x[:-2]) for x in mods if x.endswith("Hz")), 0)
                voices[name] = (vid, rate, pitch)
                meta.setdefault("host", name)
            else:
                meta[key] = val
        else:
            sys.exit(f"{where}: 読めない行: {s}")
    return meta, voices, items, list(words.values())


def plan(n, meta, items, words):
    """台本の最後に、その回の話し手が読む単語のふり返りと終わりの曲を足す"""
    host = meta["host"]
    out = list(items)
    open_bgm = any(i[0] == "bgm" for i in items) and [i for i in items if i[0] == "bgm"][-1][1]
    if open_bgm:
        out.append(("bgm", None, None))
    if any(i[0] == "amb" for i in items) and [i for i in items if i[0] == "amb"][-1][1]:
        out.append(("amb", None, None))
    out += [("head", "Words"), ("bgm", meta.get("wordsbgm", f"lofi.{n}"), 0.14),
            ("say", host, None, "Before you go, here are some words from today."), ("pause", 0.8)]
    for w in words:
        out += [("say", host, None, w["word"] + "."), ("pause", 0.4), ("say", "JP", None, w["ja"]),
                ("pause", 0.4), ("say", w["who"], None, w["sentence"]), ("pause", 1.2)]
    out.append(("bgm", None, None))
    first = next((i[1] for i in items if i[0] == "music"), f"piano.{n}")
    out.append(("music", meta.get("outro", first), 10.0))
    return out


def tts_key(voices, who, mood, text):
    vid, rate, pitch = voices[who]
    dr, dp, dv = MOODS.get(mood, (0, 0, 0))
    return (vid, clean(text), f"{rate + dr:+d}%", f"{pitch + dp:+d}Hz", f"{dv:+d}%")


def cache_path(key):
    return CACHE / (hashlib.sha1("\n".join(key).encode()).hexdigest()[:16] + ".mp3")


async def synth(jobs):
    sem = asyncio.Semaphore(6)

    async def one(key, out):
        vid, text, rate, pitch, vol = key
        async with sem:
            part = out.with_suffix(".part")
            err = None
            for i in range(6):
                try:
                    c = edge_tts.Communicate(text, vid, rate=rate, pitch=pitch, volume=vol)
                    await asyncio.wait_for(c.save(str(part)), 90)
                    part.rename(out)
                    return
                except Exception as e:  # 読み上げの通信はときどき切れる
                    err = e
                    await asyncio.sleep(3 * (i + 1))
            raise RuntimeError(f"読み上げに失敗: {vid}: {text[:60]}") from err

    await asyncio.gather(*(one(*j) for j in jobs))


def decode(path):
    r = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                        "-ar", str(SR), "-"], check=True, capture_output=True)
    y = np.frombuffer(r.stdout, dtype=np.float32)
    nz = np.flatnonzero(np.abs(y) > 0.003)  # 前後の無音を詰める
    if len(nz):
        y = y[max(0, nz[0] - int(0.03 * SR)): nz[-1] + int(0.08 * SR)]
    return y


def place(buf, arr, t, g=1.0):
    i = int(round(t * SR))
    j = min(len(buf), i + len(arr))
    buf[i:j] += arr[: j - i] * g


def render(n, meta, voices, items, out):
    CACHE.mkdir(parents=True, exist_ok=True)
    keys = {}
    for it in items:
        if it[0] == "say":
            k = tts_key(voices, *it[1:])
            keys[k] = cache_path(k)
    jobs = [(k, p) for k, p in keys.items() if not p.exists()]
    print(f"  読み上げ {len(jobs)} 本（キャッシュ {len(keys) - len(jobs)}）")
    asyncio.run(synth(jobs))
    clips = {k: decode(p) for k, p in keys.items()}

    # 声ごとに大きさをそろえる（気分で変えた大きさは残す）
    gain = {}
    for who in voices:
        r = [np.sqrt(np.mean(c ** 2)) for k, c in clips.items() if k[0] == voices[who][0] and k[4] == "+0%"]
        gain[voices[who][0]] = 0.12 / np.median(r) if r else 1.0

    # 並べる
    t, last = 1.0, None
    say, fx, mus, beds, ambs, spans = [], [], [], [], [], []
    bed = amb = None
    for it in items:
        kind = it[0]
        if kind == "say":
            k = tts_key(voices, *it[1:])
            if last == "say":
                t += 0.45 if prev_who == it[1] else 0.3
            y = clips[k] * gain[k[0]]
            say.append((t, y))
            spans.append((t, t + len(y) / SR))
            t += len(y) / SR
            prev_who = it[1]
        elif kind == "pause":
            t += it[1]
        elif kind == "sfx":
            y = music.sfx(it[1])
            act = y[np.abs(y) > 0.01]
            g = min(0.05 / (np.sqrt(np.mean(act ** 2)) if len(act) else 1), 0.6 / np.max(np.abs(y)))
            fx.append((t + 0.1, y, g * it[2]))
            if not it[3]:
                t += 0.1 + len(y) / SR + 0.2
        elif kind == "music":
            y = music.render(it[1], it[2], "music")
            mus.append((t + 0.2, y))
            t += 0.2 + len(y) / SR - 1.2
        elif kind == "bgm":
            if bed:
                beds.append((bed[0], bed[1], t + 1.5, bed[2]))
                t += 2.2
            bed = (it[1], t, it[2] or 0.17) if it[1] else None
            if bed:
                t += 2.8
        elif kind == "amb":
            if amb:
                ambs.append((amb[0], amb[1], t + 0.5, amb[2]))
            amb = (it[1], t, it[2] or 1.0) if it[1] else None
            if amb:
                t += 1.5
        if kind != "head":
            last = kind
    if bed:
        beds.append((bed[0], bed[1], t + 1.5, bed[2]))
    if amb:
        ambs.append((amb[0], amb[1], t + 0.5, amb[2]))
    total = t + 4.0
    N = int(total * SR) + SR * 12
    voice = np.zeros(N, np.float32)
    for st, y in say:
        place(voice, y, st)

    # 声のある所で BGM を下げる（短い間では上げない）
    cr = 100
    mask = np.zeros(int(total * cr) + 1200)
    for a, b in spans:
        mask[max(0, int((a - 0.35) * cr)): int((b + 0.5) * cr)] = 1
    mask = ndimage.binary_closing(mask, structure=np.ones(int(1.6 * cr))).astype(float)
    mask = ndimage.gaussian_filter1d(mask, 0.12 * cr)

    back = np.zeros(N, np.float32)
    for name, a, b, level in beds:
        ln = b - a + 3.0
        y = music.render(name, ln, "bgm").astype(np.float32)
        tm = a + np.arange(len(y)) / SR
        d = np.interp(tm, np.arange(len(mask)) / cr, mask)
        g = (1 - d) + level * d
        fade = np.clip((a + ln - tm) / 3.0, 0, 1) * np.clip((tm - a) / 0.05, 0, 1)
        place(back, y * g * fade, a)
    for name, a, b, level in ambs:
        ln = b - a + 2.0
        y = music.ambience(name, ln)
        tm = np.arange(len(y)) / SR
        fade = np.clip(tm / 1.5, 0, 1) * np.clip((ln - tm) / 2.0, 0, 1)
        place(back, y * fade * 0.35 * level, a)
    for st, y in mus:
        place(back, y * 1.3, st)
    for st, y, g in fx:
        place(back, y * g, st)

    mix = voice + back
    mix = music.limit(mix * 1.2, 0.8) * 0.92
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    end = int((total + 1) * SR)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "libmp3lame", "-b:a", "64k",
                    "-metadata", f"title={n}. {meta['title']}", "-metadata", "artist=English Radio",
                    "-metadata", "album=English Radio", "-metadata", f"track={n}", str(out)],
                   input=pcm[:end].tobytes(), check=True)


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
        "<language>en</language>",
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
            f'<guid isPermaLink="false">english-radio-v2-{e["n"]:03d}</guid>',
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
    ap.add_argument("--only", type=int, help="この回だけ作る（episodes.json は書かない）")
    ap.add_argument("redo", nargs="*", type=int, help="作り直す回の番号")
    args = ap.parse_args()

    dic = load_dict()
    index = ROOT / "episodes.json"
    old = {e["n"]: e for e in json.loads(index.read_text())} if index.exists() else {}
    if not args.local and not args.only and gh("release", "view", TAG, check=False).returncode:
        gh("release", "create", TAG, "--title", "Audio", "--notes", "English Radio の音声（tools/build.py が上げる）")

    eps = []
    for path in sorted(EPISODES.glob("[0-9][0-9][0-9].txt")):
        n = int(path.stem)
        if args.only and n != args.only:
            continue
        meta, voices, items, words = parse(path, dic)
        src = VERSION + MUSIC_SRC + path.read_text() + "".join(w["ja"] for w in words)
        h = hashlib.sha1(src.encode()).hexdigest()[:10]
        out = AUDIO / f"ep{n:03d}.mp3"
        e = old.get(n)
        if args.only or not e or e["hash"] != h or n in args.redo or not (e.get("uploaded") or out.exists()):
            print(f"{n}. {meta['title']}")
            render(n, meta, voices, plan(n, meta, items, words), out)
            e = {"hash": h, "bytes": out.stat().st_size, "seconds": round(MP3(out).info.length)}
            print(f"  {e['seconds'] // 60}分{e['seconds'] % 60}秒・{e['bytes'] / 1e6:.1f}MB・{len(words)}語")
        if args.only:
            continue
        if not args.local and not (e.get("uploaded") == h):
            gh("release", "upload", TAG, str(out), "--clobber")
            e["uploaded"] = h
        eps.append({
            "n": n, "title": meta["title"], "description": meta.get("description", ""),
            "date": meta["date"], "hash": e["hash"], "bytes": e["bytes"], "seconds": e["seconds"],
            "uploaded": e.get("uploaded"),
            "url": f"{SITE}/audio/ep{n:03d}.mp3?v={e['hash']}",
            "words": [{"word": w["word"], "ja": w["ja"]} for w in words],
        })
    if args.only:
        return
    index.write_text(json.dumps(eps, ensure_ascii=False, indent=1) + "\n")
    write_feed(eps)
    print(f"{len(eps)} 回分の episodes.json と feed.xml を書いた")


if __name__ == "__main__":
    main()
