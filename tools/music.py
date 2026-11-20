#!/usr/bin/env python3
"""English Radio の音楽と効果音を numpy で作る（録音した素材は使わない）。

  render("lofi.2", 30, "music")   曲（.数字で調・テンポ・メロディが変わる）。"bgm" は声の後ろ用でメロディなし
  sfx("knock")                    効果音
  ambience("fire", 60)            ずっと鳴る環境音

  .venv/bin/python tools/music.py lofi.1 citypop.2   # audio/test/ に試しの mp3 を作る
  .venv/bin/python tools/music.py --sfx knock rain  # 効果音を試す
"""
import functools
import math
import random
import re
import zlib

import numpy as np
from scipy import signal

SR = 32000
TAU = 2 * np.pi


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(n):
    return np.arange(n) / SR


def ns(sec):
    return max(1, int(round(sec * SR)))


def gate(t, dur, rel):
    return np.clip(1 - (t - dur) / rel, 0, 1)


def seed_of(*xs):
    return zlib.crc32(repr(xs).encode())


def noise(n, *salt):
    return np.random.default_rng(seed_of("noise", n, *salt)).standard_normal(n)


def _filt(x, kind, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, kind, fs=SR, output="sos"), x)


def lp(x, fc, order=2):
    return _filt(x, "lowpass", fc, order)


def hp(x, fc, order=2):
    return _filt(x, "highpass", fc, order)


def bp(x, lo, hi, order=2):
    return _filt(x, "bandpass", [lo, hi], order)


def norm(x, peak=1.0):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 0 else x


# ---------------------------------------------------------------- 楽器（1音を作る）

INSTR = {}


def inst(fn):
    INSTR[fn.__name__] = fn
    return fn


def _rng(f, salt=0):
    return np.random.default_rng(int(f * 1000) + salt)


@inst
def epiano(f, dur):  # FM のエレピ
    rel = 0.3
    t = tt(ns(dur + rel))
    idx = 1.5 * np.exp(-t * 4) + 0.3
    y = np.sin(TAU * f * t + idx * np.sin(TAU * f * t))
    if 14 * f < 0.42 * SR:
        y += 0.05 * np.sin(TAU * 14 * f * t) * np.exp(-t * 60)
    y *= np.exp(-t * (0.7 + f / 900)) * np.minimum(1, t / 0.002)
    return y * gate(t, dur, rel)


@inst
def piano(f, dur):
    rel = 0.35
    t = tt(ns(min(dur, 6) + rel))
    y = np.zeros_like(t)
    rng = _rng(f)
    br = (f / 262) ** 0.35
    for k in range(1, 14):
        fk = k * f * math.sqrt(1 + 0.0003 * k * k)
        if fk > 0.42 * SR:
            break
        a = (0.9 if k == 1 else 1.0) / k ** 1.25
        y += a * np.sin(TAU * fk * t + rng.uniform(0, TAU)) * np.exp(-t * (0.45 + 0.28 * k) * br)
    y *= (0.65 + 0.35 * np.exp(-t * 3)) * np.minimum(1, t / 0.0015)
    return y * gate(t, dur, rel)


def _pluck(f, dur, pos=0.2, bright=1.0, dec=1.0, rel=0.08):
    t = tt(ns(dur + rel))
    y = np.zeros_like(t)
    for k in range(1, 17):
        if k * f > 0.42 * SR:
            break
        a = abs(math.sin(math.pi * k * pos)) / k ** (1.0 / bright)
        y += a * np.sin(TAU * k * f * t) * np.exp(-t * (1.0 + 0.7 * k) * dec * (f / 196) ** 0.35)
    y *= np.minimum(1, t / 0.001)
    return y * gate(t, dur, rel)


@inst
def pluck(f, dur):  # ギター
    return _pluck(f, dur)


@inst
def nylon(f, dur):  # ガットギター
    return _pluck(f, dur, pos=0.15, bright=0.8, dec=1.3)


@inst
def uke(f, dur):
    return _pluck(f, dur, pos=0.25, bright=1.3, dec=2.2)


@inst
def pizz(f, dur):
    return _pluck(f, min(dur, 0.4), pos=0.3, dec=4.5, rel=0.05)


@inst
def bass(f, dur):
    rel = 0.07
    t = tt(ns(dur + rel))
    y = (np.sin(TAU * f * t) + 0.45 * np.sin(TAU * 2 * f * t) * np.exp(-t * 1.5)
         + 0.2 * np.sin(TAU * 3 * f * t) * np.exp(-t * 4))
    y = np.tanh(1.4 * y) * np.exp(-t * 0.9) * np.minimum(1, t / 0.004)
    return y * gate(t, dur, rel)


@inst
def sbass(f, dur):  # シンセベース
    rel = 0.05
    t = tt(ns(dur + rel))
    b = 1.2 + 4 * np.exp(-t * 9)
    y = sum(np.sin(TAU * k * f * t) / k * np.exp(-k / b) for k in range(1, 12) if k * f < 4000)
    y = np.tanh(1.5 * y) * np.minimum(1, t / 0.003) * np.exp(-t * 1.2)
    return y * gate(t, dur, rel)


def _saws(f, t, rng, det=(-0.0055, 0, 0.0055), top=5000, bright=6, vib=None):
    y = np.zeros_like(t)
    for d in det:
        ff = f * (1 + d)
        ph = TAU * ff * (t if vib is None else np.cumsum(vib) / SR)
        for k in range(1, 40):
            if k * ff > top:
                break
            y += np.sin(k * ph + rng.uniform(0, TAU)) / k * math.exp(-k / bright)
    return y / len(det)


@inst
def pad(f, dur):
    rel = 1.2
    t = tt(ns(dur + rel))
    y = _saws(f, t, _rng(f, 1), bright=4) * np.minimum(1, t / 0.6)
    return y * gate(t, dur, rel)


@inst
def strings(f, dur):
    rel = 0.8
    t = tt(ns(dur + rel))
    rng = _rng(f, 2)
    vib = 1 + 0.0025 * np.sin(TAU * 5.2 * t + rng.uniform(0, TAU))
    y = _saws(f, t, rng, bright=6, vib=vib) * np.minimum(1, t / 0.35)
    return y * gate(t, dur, rel)


@inst
def synth(f, dur):  # 80年代ふうのパッド
    rel = 0.5
    t = tt(ns(dur + rel))
    y = _saws(f, t, _rng(f, 3), det=(-0.008, 0, 0.008), top=7000, bright=10) * np.minimum(1, t / 0.08)
    return y * gate(t, dur, rel)


@inst
def spluck(f, dur):  # シンセのアルペジオ
    rel = 0.08
    t = tt(ns(dur + rel))
    b = 1.5 + 8 * np.exp(-t * 12)
    y = sum(np.sin(TAU * k * f * t) / k * np.exp(-k / b) for k in range(1, 25) if k * f < 7000)
    return y * np.exp(-t * 4) * np.minimum(1, t / 0.002) * gate(t, dur, rel)


@inst
def brass(f, dur):
    rel = 0.15
    t = tt(ns(dur + rel))
    b = 1.5 + 5.5 * np.minimum(1, t / 0.05) * (0.55 + 0.45 * np.exp(-t * 3))
    vib = 1 + 0.003 * np.sin(TAU * 5 * t) * np.clip((t - 0.25) / 0.3, 0, 1)
    ph = TAU * f * np.cumsum(vib) / SR
    y = sum(np.sin(k * ph) / k * np.exp(-k / b) for k in range(1, 30) if k * f < 6000)
    return y * np.minimum(1, t / 0.03) * gate(t, dur, rel)


def _vibph(f, t, depth=0.004, delay=0.15):
    vib = 1 + depth * np.sin(TAU * 5.5 * t) * np.clip((t - delay) / 0.2, 0, 1)
    return TAU * f * np.cumsum(vib) / SR


@inst
def lead(f, dur):
    rel = 0.1
    t = tt(ns(dur + rel))
    ph = _vibph(f, t)
    y = sum(np.sin(k * ph) / k * math.exp(-k / 6) for k in range(1, 12, 2) if k * f < 7000)
    return y * np.minimum(1, t / 0.015) * gate(t, dur, rel)


@inst
def flute(f, dur):
    rel = 0.12
    t = tt(ns(dur + rel))
    ph = _vibph(f, t, 0.005, 0.2)
    y = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    y += 0.04 * bp(noise(len(t), "flute"), 1200, 5000) * np.exp(-t * 6)
    return y * np.minimum(1, t / 0.05) * gate(t, dur, rel)


@inst
def bassoon(f, dur):
    rel = 0.06
    t = tt(ns(dur + rel))
    ph = _vibph(f, t, 0.002, 0.3)
    y = np.zeros_like(t)
    for k in range(1, 21):
        fk = k * f
        if fk > 5000:
            break
        a = (math.exp(-((fk - 500) / 220) ** 2) + 0.35 * math.exp(-((fk - 1150) / 300) ** 2) + 0.05) / k ** 0.5
        y += a * np.sin(k * ph)
    return y * np.minimum(1, t / 0.02) * gate(t, dur, rel)


def _partials(f, parts, ring):
    t = tt(ns(ring))
    y = sum(a * np.sin(TAU * r * f * t) * np.exp(-t * d) for r, a, d in parts if r * f < 0.42 * SR)
    return y * np.minimum(1, t / 0.001)


@inst
def bell(f, dur):
    return _partials(f, [(1, 1, 1.0), (2.0, 0.6, 1.6), (3.0, 0.3, 2.5), (4.2, 0.25, 4),
                         (5.4, 0.2, 6), (6.8, 0.1, 8)], 3.0)


@inst
def musicbox(f, dur):
    return _partials(f, [(1, 1, 2.5), (2.0, 0.15, 5), (5.9, 0.2, 15)], 2.0)


@inst
def kalimba(f, dur):
    return _partials(f, [(1, 1, 1.8), (5.9, 0.22, 14), (3.1, 0.05, 9)], 2.5)


@inst
def marimba(f, dur):
    return _partials(f, [(1, 1, 4), (4.0, 0.35, 14), (9.9, 0.1, 35)], 1.2)


@functools.lru_cache(maxsize=6000)
def note(name, m, dur):
    return INSTR[name](hz(m), dur).astype(np.float32)


# ---------------------------------------------------------------- 打楽器

@functools.lru_cache(maxsize=None)
def drum(name):
    def T(sec):
        return tt(ns(sec))

    if name == "kick":
        t = T(0.5)
        f = 46 + 80 * np.exp(-t * 28)
        y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t * 7) + 0.3 * lp(noise(len(t), 1), 2500) * np.exp(-t * 180)
    elif name == "snare":
        t = T(0.3)
        y = (0.6 * np.sin(TAU * 185 * t) * np.exp(-t * 20) + 0.3 * np.sin(TAU * 330 * t) * np.exp(-t * 25)
             + 0.5 * norm(bp(noise(len(t), 2), 1200, 8000)) * np.exp(-t * 15))
    elif name == "hat":
        t = T(0.08)
        y = hp(noise(len(t), 3), 7000) * np.exp(-t * 60)
    elif name == "ohat":
        t = T(0.4)
        y = hp(noise(len(t), 4), 6500) * np.exp(-t * 8)
    elif name == "clap":
        t = T(0.3)
        env = sum(np.exp(-(t - a) * 180) * (t >= a) for a in (0, 0.011, 0.023))
        env = env + 0.7 * np.exp(-np.maximum(t - 0.03, 0) * 16) * (t >= 0.03)
        y = bp(noise(len(t), 5), 900, 4000) * env
    elif name == "snap":
        t = T(0.12)
        y = bp(noise(len(t), 6), 1800, 6000) * np.exp(-t * 60)
    elif name == "rim":
        t = T(0.1)
        y = (np.sin(TAU * 1700 * t) + 0.6 * np.sin(TAU * 820 * t)) * np.exp(-t * 70)
        y += 0.3 * hp(noise(len(t), 7), 3000) * np.exp(-t * 200)
    elif name == "shaker":
        t = T(0.12)
        y = hp(noise(len(t), 8), 5000) * np.minimum(1, t / 0.012) * np.exp(-t * 30)
    elif name in ("conga", "congalo"):
        t = T(0.4)
        f0 = 330 if name == "conga" else 220
        f = f0 * (1 + 0.15 * np.exp(-t * 40))
        y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t * 14) + 0.2 * hp(noise(len(t), 9), 2000) * np.exp(-t * 120)
    elif name == "ride":
        t = T(1.2)
        rng = np.random.default_rng(10)
        y = sum(np.sin(TAU * fr * t + rng.uniform(0, TAU)) for fr in (3150, 4280, 5370, 6620, 7780, 9300)) / 6
        y = y * np.exp(-t * 3.5) + 0.3 * hp(noise(len(t), 11), 6000) * np.exp(-t * 6)
    elif name == "crash":
        t = T(2.0)
        y = hp(noise(len(t), 12), 4000) * np.exp(-t * 2.2)
    elif name == "wood":
        t = T(0.1)
        y = (np.sin(TAU * 1100 * t) + 0.5 * np.sin(TAU * 1750 * t)) * np.exp(-t * 55)
    elif name == "timp":
        t = T(2.5)
        f = 87 * (1 + 0.05 * np.exp(-t * 8))
        ph = TAU * np.cumsum(f) / SR
        y = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * np.exp(-t * 2.2) + 0.3 * lp(noise(len(t), 13), 400) * np.exp(-t * 30)
    elif name == "tom":
        t = T(0.5)
        f = 140 * (1 + 0.3 * np.exp(-t * 20))
        y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t * 8)
    elif name == "tick":
        t = T(0.06)
        y = hp(noise(len(t), 14), 3000) * np.exp(-t * 800) + 0.4 * np.sin(TAU * 2500 * t) * np.exp(-t * 300)
    else:
        raise KeyError(name)
    return norm(y).astype(np.float32)


# ---------------------------------------------------------------- 和音と曲の形

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
QUAL = {
    "": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10),
    "m9": (0, 3, 7, 10, 14), "maj9": (0, 4, 7, 11, 14), "9": (0, 4, 7, 10, 14), "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9), "sus4": (0, 5, 7), "7sus4": (0, 5, 7, 10), "dim": (0, 3, 6),
    "m7b5": (0, 3, 6, 10), "add9": (0, 4, 7, 14), "aug": (0, 4, 8),
}
SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10), "harmonic": (0, 2, 3, 5, 7, 8, 11),
    "pent": (0, 2, 4, 7, 9), "mpent": (0, 3, 5, 7, 10), "dorian": (0, 2, 3, 5, 7, 9, 10),
}


def chord(sym, tr):
    m = re.fullmatch(r"([A-G])([#b]?)(.*?)(?:/([A-G][#b]?))?", sym)
    root = (NOTE[m[1]] + {"#": 1, "b": -1, "": 0}[m[2]] + tr) % 12
    ints = QUAL[m[3]]
    b = root
    if m[4]:
        b = (NOTE[m[4][0]] + {"#": 1, "b": -1, "": 0}[m[4][1:]] + tr) % 12
    return root, ints, b


def bar_chords(spec, tr):
    """"Ebm7 Ab7" → [(chord, 拍の始まり, 拍数)]"""
    parts = spec.split()
    w = 4 / len(parts)
    return [(chord(p, tr), i * w, w) for i, p in enumerate(parts)]


def at(chords, beat):
    for c, s, w in chords:
        if s <= beat < s + w:
            return c
    return chords[-1][0]


def near(pc, center):
    return center + ((pc - center + 6) % 12) - 6


def voicing(c, center, rootless=True):
    root, ints, _ = c
    pcs = [(root + i) % 12 for i in ints]
    if rootless and len(pcs) >= 4:
        pcs = pcs[1:]
    return sorted({near(p, center) for p in pcs})


def bass_pitch(c, ch, nxt):
    root, ints, b = c
    base = 36 + b % 12
    if base > 45:
        base -= 12
    off = {"R": 0, "r": 0, "5": 7, "O": 12, "3": ints[1], "7": ints[3] if len(ints) > 3 else 10}
    if ch == "A":  # 次の和音へ半音で近づく
        return 36 + (nxt[2] % 12) - 1 if 36 + nxt[2] % 12 <= 45 else 24 + nxt[2] % 12 - 1
    return base + off[ch]


def pattern_events(pat):
    out = []
    for i, c in enumerate(pat):
        if c in ".-":
            continue
        j = i + 1
        while j < len(pat) and pat[j] == "-":
            j += 1
        out.append((i, j - i, c))
    return out


VEL = {"x": 1.0, "o": 0.65, "s": 0.4, "d": 1.0, "u": 0.7, "r": 0.5}

RHYTHMS = {
    "slow": [[(0, 2), (2, 2)], [(0, 3), (3, 1)], [(0, 1), (1, 3)], [(0, 1.5), (1.5, 0.5), (2, 2)],
             [(1, 1), (2, 2)], [(0, 2), (2, 1), (3, 1)]],
    "mid": [[(0, 1), (1, 1), (2, 2)], [(0, 1.5), (1.5, 0.5), (2, 2)], [(0.5, 0.5), (1, 0.5), (1.5, 1), (3, 1)],
            [(0, 0.5), (0.5, 0.5), (1, 1), (2, 1), (3, 1)], [(0, 2), (2, 1), (3, 1)],
            [(0, 1), (1.5, 0.5), (2, 1), (3, 0.5), (3.5, 0.5)], [(1, 1), (2, 0.5), (2.5, 1.5)]],
    "busy": [[(0, 0.5), (0.5, 0.5), (1, 0.5), (1.5, 1), (3, 0.5), (3.5, 0.5)],
             [(0, 0.75), (0.75, 0.75), (1.5, 1), (3, 0.5), (3.5, 0.5)],
             [(0, 0.5), (0.5, 1), (1.5, 0.5), (2, 1), (3, 1)], [(0.5, 0.5), (1, 0.5), (1.5, 0.5), (2, 2)],
             [(0, 1), (1, 0.5), (1.5, 0.5), (2, 0.5), (2.5, 0.5), (3, 1)]],
}
ENDS = [[(0, 3)], [(0, 1), (1, 3)], [(0, 0.5), (0.5, 0.5), (1, 3)]]


def L(kind, inst=None, pat="", vel=0.5, **kw):
    d = dict(kind=kind, inst=inst, pat=pat, vel=vel)
    d.setdefault("sec", "IABCE" if kind in ("chords", "pad", "arp", "strum") else
                 "ABCE" if kind == "bass" else "AB")
    d.update(kw)
    return d


STYLES = {
    "lofi": dict(bpm=76, swing=("16", 0.6), key=5, scale="pent", rev=(0.2, 1.6), lp=5500, crackle=True,
                 progs=[["Fmaj7", "Em7", "Dm7", "Cmaj7"], ["Bbmaj7", "Am7", "Gm7", "Gm7 C7"]],
                 layers=[L("chords", "epiano", "x------.x-----..", 0.45, center=64),
                         L("bass", "bass", "R-------..R-5---", 0.7),
                         L("drum", "kick", "x.........x.....", 0.9),
                         L("drum", "snare", "....x.......x...", 0.45),
                         L("drum", "hat", "s.o.s.o.s.o.s.oo", 0.2),
                         L("melody", "epiano", vel=0.4, range=(69, 86), rhythm="slow", music=True)]),
    "citypop": dict(bpm=114, key=1, scale="major", rev=(0.15, 1.2),
                    progs=[["Dbmaj7", "C7", "Fm7", "Ebm7 Ab7"], ["Gbmaj7", "Fm7", "Ebm7", "Ab7sus4 Ab7"]],
                    layers=[L("chords", "epiano", "x-----x-..x---x.", 0.42, center=65),
                            L("bass", "bass", "R.O.R.O.R.O.R.O.", 0.72),
                            L("drum", "kick", "x...x...x...x...", 0.85),
                            L("drum", "clap", "....x.......x...", 0.5),
                            L("drum", "hat", "x.x.x.x.x.x.x.x.", 0.18),
                            L("drum", "ohat", "..x...x...x...x.", 0.15),
                            L("pad", "strings", vel=0.22, center=67, sec="B"),
                            L("chords", "brass", "......x.....x...", 0.28, center=67, sec="B", music=True),
                            L("melody", "lead", vel=0.48, range=(72, 88), rhythm="busy", music=True)]),
    "acoustic": dict(bpm=96, key=7, scale="major", rev=(0.18, 1.5),
                     progs=[["G", "D", "Em", "C"], ["C", "G", "Am", "D"]],
                     layers=[L("arp", "nylon", "0.1.2.3.2.1.2.1.", 0.5, center=50),
                             L("bass", "bass", "R.......5.......", 0.55),
                             L("drum", "shaker", "x.s.x.s.x.s.x.s.", 0.2),
                             L("drum", "kick", "x.......x.......", 0.45),
                             L("pad", "strings", vel=0.15, center=62, sec="B"),
                             L("melody", "flute", vel=0.42, range=(72, 88), rhythm="mid", music=True)]),
    "mystery": dict(bpm=74, key=9, scale="harmonic", rev=(0.25, 2.0),
                    progs=[["Am", "Fmaj7", "Dm", "E7"], ["Dm", "Am", "Bb", "E7"]],
                    layers=[L("arp", "pizz", "0.1.2.1.0.1.2.1.", 0.5, center=45),
                            L("pad", "strings", vel=0.2, center=52),
                            L("bass", "bass", "R.......R.......", 0.5),
                            L("drum", "tick", "x...x...x...x...", 0.25),
                            L("drum", "timp", "x" + "." * 31, 0.35, sec="B"),
                            L("melody", "bell", vel=0.35, range=(69, 84), rhythm="slow", music=True)]),
    "afro": dict(bpm=106, key=0, scale="major", rev=(0.12, 1.0),
                 progs=[["C", "F", "G", "F"], ["Am", "F", "C", "G"]],
                 layers=[L("arp", "pluck", "0.12.01.2.10.2.1", 0.42, center=60),
                         L("bass", "bass", "R..R..5.R..R.O..", 0.7),
                         L("drum", "shaker", "xsxsxsxsxsxsxsxs", 0.16),
                         L("drum", "conga", "....o..x....o.x.", 0.35),
                         L("drum", "congalo", "x.....o...x.....", 0.4),
                         L("drum", "kick", "x.......x.......", 0.7),
                         L("drum", "wood", "x..x..x...x.x...", 0.18),
                         L("melody", "kalimba", vel=0.45, range=(72, 88), rhythm="mid", music=True)]),
    "space": dict(bpm=64, key=2, scale="dorian", rev=(0.4, 3.5),
                  progs=[["Dm9", "Bbmaj7", "Gm9", "A7sus4"], ["Bbmaj7", "Fmaj7", "Gm9", "Dm9"]],
                  layers=[L("pad", "pad", vel=0.35, center=57),
                          L("arp", "bell", "0...1...2...3...", 0.22, center=69),
                          L("bass", "bass", "R---------------", 0.35),
                          L("melody", "flute", vel=0.35, range=(74, 88), rhythm="slow", music=True)]),
    "comedy": dict(bpm=128, key=0, scale="major", rev=(0.12, 1.0), short=True,
                   progs=[["C", "A7", "Dm", "G7"], ["F", "C", "D7", "G7"]],
                   layers=[L("bass", "bassoon", "R...5...R...5...", 0.6, sec="IABCE"),
                           L("chords", "pizz", "..x...x...x...x.", 0.45, center=64),
                           L("drum", "wood", "....x.......x...", 0.25),
                           L("drum", "kick", "x.......x.......", 0.35),
                           L("melody", "marimba", vel=0.55, range=(67, 84), rhythm="busy", music=True)]),
    "orchestral": dict(bpm=66, key=2, scale="major", rev=(0.35, 2.8),
                       progs=[["D", "Bm", "G", "A"], ["G", "D", "Em", "A7"]],
                       layers=[L("pad", "strings", vel=0.35, center=62),
                               L("bass", "strings", "R---------------", 0.3),
                               L("arp", "pluck", "0.1.2.3.4.3.2.1.", 0.28, center=55, sec="AB"),
                               L("drum", "timp", "x" + "." * 31, 0.45),
                               L("melody", "brass", vel=0.45, range=(57, 72), rhythm="slow", music=True)]),
    "jazz": dict(bpm=138, swing=("8", 0.66), key=5, scale="major", rev=(0.18, 1.6),
                 progs=[["Gm7", "C7", "Fmaj7", "D7"], ["Gm7", "C7", "Am7 D7", "Gm7 C7"]],
                 layers=[L("chords", "piano", "x-....x-........", 0.4, center=62),
                         L("bass", "bass", "R...3...5...A...", 0.65),
                         L("drum", "ride", "x...x.x.x...x.x.", 0.22),
                         L("drum", "hat", "....x.......x...", 0.2),
                         L("melody", "piano", vel=0.5, range=(67, 84), rhythm="mid", music=True)]),
    "synthwave": dict(bpm=100, key=9, scale="minor", rev=(0.3, 2.2),
                      progs=[["Am", "F", "C", "G"], ["F", "C", "G", "Am"]],
                      layers=[L("pad", "synth", vel=0.28, center=60),
                              L("bass", "sbass", "R.R.R.R.R.R.R.R.", 0.55),
                              L("arp", "spluck", "0.1.2.1.0.1.2.1.", 0.22, center=69),
                              L("drum", "kick", "x...x...x...x...", 0.85),
                              L("drum", "snare", "....x.......x...", 0.5),
                              L("drum", "hat", "..x...x...x...x.", 0.2),
                              L("melody", "lead", vel=0.45, range=(69, 86), rhythm="mid", music=True)]),
    "piano": dict(bpm=70, key=0, scale="major", rev=(0.3, 2.2),
                  progs=[["C", "G", "Am", "F"], ["F", "C", "Dm7", "G"]],
                  layers=[L("arp", "piano", "0.1.2.1.3.1.2.1.", 0.38, center=50),
                          L("bass", "piano", "R---------------", 0.42),
                          L("pad", "strings", vel=0.12, center=60, sec="B"),
                          L("melody", "piano", vel=0.55, range=(67, 84), rhythm="slow", music=True)]),
    "spooky": dict(bpm=56, key=2, scale="harmonic", rev=(0.45, 3.5),
                   progs=[["Dm", "Bb", "Gm", "A7"], ["Dm", "Eb", "Dm", "A7"]],
                   layers=[L("pad", "pad", vel=0.3, center=50),
                           L("bass", "bass", "R---------------", 0.3),
                           L("arp", "musicbox", "0...2...1...3...", 0.25, center=74),
                           L("melody", "musicbox", vel=0.35, range=(74, 90), rhythm="slow", music=True)]),
    "sports": dict(bpm=128, key=10, scale="major", rev=(0.15, 1.3),
                   progs=[["Bb", "Eb", "F", "Eb"], ["Gm", "Eb", "Bb", "F"]],
                   layers=[L("chords", "brass", "x..x..x...x.x...", 0.38, center=65),
                           L("pad", "strings", vel=0.2, center=62, sec="B"),
                           L("bass", "sbass", "R.R.R.R.R.R.R.R.", 0.6),
                           L("drum", "kick", "x...x...x...x...", 0.85),
                           L("drum", "snare", "....x.......x.x.", 0.5),
                           L("drum", "hat", "x.x.x.x.x.x.x.x.", 0.2),
                           L("melody", "brass", vel=0.5, range=(65, 82), rhythm="mid", music=True)]),
    "kitchen": dict(bpm=118, key=7, scale="major", rev=(0.12, 1.0),
                    progs=[["G", "Em", "C", "D"], ["C", "D", "Bm", "Em"]],
                    layers=[L("strum", "uke", "d.du.udud.du.udu", 0.42, center=64),
                            L("bass", "bass", "R...5...R...5...", 0.55),
                            L("drum", "clap", "....x.......x...", 0.35),
                            L("drum", "shaker", "x.s.x.s.x.s.x.s.", 0.15),
                            L("drum", "kick", "x.......x.......", 0.4),
                            L("melody", "flute", vel=0.45, range=(74, 90), rhythm="busy", music=True)]),
    "bossa": dict(bpm=132, key=0, scale="major", rev=(0.2, 1.6),
                  progs=[["Dm7", "G7", "Cmaj7", "Cmaj7"], ["Em7", "A7", "Dm7", "G7"]],
                  layers=[L("bass", "bass", "R.....5.R.....5.", 0.55),
                          L("chords", "nylon", "x..x..x...x..x..", 0.4, center=60),
                          L("drum", "rim", "x..x..x...x..x..", 0.22),
                          L("drum", "shaker", "xsxsxsxsxsxsxsxs", 0.12),
                          L("melody", "flute", vel=0.45, range=(72, 88), rhythm="mid", music=True)]),
}
TRANSPOSE = [0, 2, -2, 3, -3, 1, -1, 4]


def step_time(i, step, swing):
    if not swing:
        return i * step
    kind, s = swing
    if kind == "16":
        return (i // 2 * 2 + (i % 2) * 2 * s) * step
    w = i % 4
    return (i // 4 * 4 + [0, 2 * s, 4 * s, 2 + 2 * s][w]) * step


def form(nbars, mode):
    out = []
    if mode == "music":
        intro = 2 if nbars >= 8 else 0
        out = ["I"] * intro
        cyc = ["A"] * 8 + ["B"] * 8
        while len(out) < nbars - 1:
            out.append(cyc[(len(out) - intro) % 16])
        return out + ["E"]
    cyc = ["A"] * 8 + ["B"] * 8 + ["A"] * 8 + ["C"] * 4
    out = ["I"] * 2
    while len(out) < nbars:
        out.append(cyc[(len(out) - 2) % len(cyc)])
    return out


def melody(rng, key, scale, rng_lo_hi, rhythm, prog, tr, nbars=8):
    lo, hi = rng_lo_hi
    allowed = [m for m in range(lo, hi + 1) if (m - key) % 12 in SCALES[scale]]
    cells = RHYTHMS[rhythm]
    m1, m2, m3 = (rng.choice(cells) for _ in range(3))
    plan = [m1, m2, m1, rng.choice(ENDS), m1, m2, m3, rng.choice(ENDS)]
    prev = allowed[len(allowed) // 2]
    out = []
    for b in range(nbars):
        chords = bar_chords(prog[b % len(prog)], tr)
        cell = plan[b % 8]
        for k, (st, ln) in enumerate(cell):
            c = at(chords, st)
            tones = {(c[0] + i) % 12 for i in c[1]}
            last = b % 4 == 3 and k == len(cell) - 1
            if last:
                cands = [m for m in allowed if m % 12 == c[0]] or allowed
            elif st % 2 == 0 or ln >= 1.5:
                cands = [m for m in allowed if m % 12 in tones] or allowed
            else:
                i = min(range(len(allowed)), key=lambda j: abs(allowed[j] - prev))
                i = max(0, min(len(allowed) - 1, i + rng.choice([-2, -1, -1, 1, 1, 2])))
                cands = [allowed[i]]
            goal = prev + rng.choice([-3, -1, 0, 1, 3])
            m = min(cands, key=lambda x: abs(x - goal) + (4 if abs(x - prev) > 7 else 0))
            out.append((b, st, ln * 0.92, m, 0.85 if st == 0 else 0.7))
            prev = m
    return out


def place(buf, arr, t, vel):
    i = int(t * SR)
    if i < 0:
        arr, i = arr[-i:], 0
    j = min(len(buf), i + len(arr))
    if j > i:
        buf[i:j] += arr[: j - i] * vel


def reverb(x, amount, rt):
    if amount <= 0:
        return x
    n = ns(rt)
    t = tt(n)
    ir = lp(noise(n, "ir", rt), 5000) * np.exp(-6.9 * t / rt)
    ir[: ns(0.02)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    wet = signal.oaconvolve(x, ir)[: len(x)]
    return x + amount * wet


def crackle(n, salt):
    rng = np.random.default_rng(seed_of("crackle", salt))
    x = np.zeros(n)
    k = int(n / SR * 7)
    idx = rng.integers(0, n, k)
    x[idx] = rng.exponential(0.5, k) * rng.choice([-1, 1], k)
    return bp(x, 800, 6000) * 0.5 + 0.004 * lp(noise(n, "hiss", salt), 4000)


def limit(y, th=0.9):
    a = np.abs(y)
    over = a > th
    y = y.copy()
    y[over] = np.sign(y[over]) * (th + (1 - th) * np.tanh((a[over] - th) / (1 - th)))
    return y


@functools.lru_cache(maxsize=64)
def _render(name, nbars, mode):
    style, _, sd = name.partition(".")
    seed = int(sd or 0)
    S = STYLES[style]
    rng = random.Random(seed_of(name))
    tr = TRANSPOSE[seed % len(TRANSPOSE)]
    key = (S["key"] + tr) % 12
    bpm = S["bpm"] * (1 + ((seed * 37) % 7 - 3) * 0.012)
    beat = 60 / bpm
    step = beat / 4
    barlen = 4 * beat
    progs = S["progs"][::-1] if seed % 2 else S["progs"]
    seq = form(nbars, mode)
    total = len(seq) * barlen + 4
    buses = {"inst": np.zeros(ns(total)), "drum": np.zeros(ns(total))}
    mel = {}
    for li, ly in enumerate(S["layers"]):
        if ly["kind"] == "melody":
            for s in "AB":
                prog = progs[0] if s == "A" else progs[-1]
                mel[li, s] = melody(random.Random(seed_of(name, li, s)), key, S["scale"], ly["range"],
                                    ly["rhythm"], prog, tr)
    run = 0
    for b, sec in enumerate(seq):
        run = run + 1 if b and seq[b - 1] == sec else 0
        prog = progs[-1] if sec == "B" else progs[0]
        spec = prog[0] if sec == "E" else prog[run % len(prog)]
        chords = bar_chords(spec, tr)
        nxt = bar_chords(prog[(run + 1) % len(prog)], tr)[0][0]
        t0 = b * barlen
        for li, ly in enumerate(S["layers"]):
            if sec not in ly["sec"] or (ly.get("music") and mode != "music"):
                continue
            kind, name_i, vel = ly["kind"], ly["inst"], ly["vel"]
            bus = buses["drum" if kind == "drum" else "inst"]

            def hum(tm, v, jit=0.004):
                return tm + rng.gauss(0, jit), v * (1 + rng.uniform(-0.08, 0.08))

            if sec == "E":  # 終わりの和音
                c = chords[0][0]
                if kind in ("chords", "pad", "strum", "arp"):
                    for m in voicing(c, ly.get("center", 60), rootless=False):
                        place(bus, note(name_i, m, round(beat * 5, 2)), t0, vel * 0.8)
                elif kind == "bass":
                    place(bus, note(name_i, bass_pitch(c, "R", c), round(beat * 5, 2)), t0, vel)
                elif kind == "melody":
                    m = min((x for x in range(ly["range"][0], ly["range"][1] + 1) if x % 12 == c[0]),
                            key=lambda x: abs(x - sum(ly["range"]) / 2))
                    place(bus, note(name_i, m, round(beat * 4, 2)), t0, vel * 0.8)
                elif ly["inst"] in ("kick", "timp"):
                    place(bus, drum(ly["inst"]), t0, vel)
                continue
            if kind == "pad":
                for c, s, w in chords:
                    for m in voicing(c, ly.get("center", 60), rootless=False):
                        place(bus, note(name_i, m, round(w * beat, 2)), t0 + s * beat, vel)
                continue
            if kind == "melody":
                for mb, st, ln, m, v in mel[li, "B" if sec == "B" else "A"]:
                    if mb == run % 8:
                        tm, vv = hum(t0 + st * beat, v * vel)
                        place(bus, note(name_i, m, round(ln * beat, 2)), tm, vv)
                continue
            pat = ly["pat"]
            half = (b % (len(pat) // 16)) * 16
            for st, ln, ch in pattern_events(pat[half: half + 16]):
                tm = t0 + step_time(st, step, S.get("swing"))
                c = at(chords, st / 4)
                dur = round(ln * step * (0.5 if S.get("short") else 0.95), 2)
                if kind == "drum":
                    tm, v = hum(tm, vel * VEL[ch], 0.002)
                    place(bus, drum(name_i), tm, v)
                elif kind == "bass":
                    tm, v = hum(tm, vel * VEL.get(ch, 1.0), 0.003)
                    place(bus, note(name_i, bass_pitch(c, ch, nxt), dur), tm, v)
                elif kind == "chords":
                    tm, v = hum(tm, vel * VEL[ch])
                    for k, m in enumerate(voicing(c, ly.get("center", 60))):
                        place(bus, note(name_i, m, dur), tm + k * 0.006, v)
                elif kind == "arp":
                    root, ints, _ = c
                    lo = near(root, ly.get("center", 60))
                    tones = sorted(lo + i + 12 * o for o in (0, 1) for i in ints if i < 12)
                    m = tones[int(ch) % len(tones)]
                    tm, v = hum(tm, vel)
                    place(bus, note(name_i, m, dur), tm, v)
                elif kind == "strum":
                    ms = voicing(c, ly.get("center", 60), rootless=False)
                    ms = [ms[0] - 12] + ms if len(ms) < 4 else ms
                    if ch == "u":
                        ms = ms[::-1]
                    tm, v = hum(tm, vel * VEL[ch])
                    for k, m in enumerate(ms):
                        place(bus, note(name_i, m, dur), tm + k * 0.012, v * (0.8 + 0.2 * (k == 0)))
    rv, rt = S.get("rev", (0.15, 1.5))
    y = reverb(buses["inst"], rv, rt) + reverb(buses["drum"], rv * 0.4, rt * 0.6)
    if S.get("crackle"):
        y += crackle(len(y), name) * 0.15
    if S.get("lp"):
        y = lp(y, S["lp"])
    y = hp(y, 35)
    rms = np.sqrt(np.mean(y[ns(1): ns(len(seq) * barlen)] ** 2)) or 1
    y = limit(y * (0.08 / rms))
    return y.astype(np.float32), barlen


def render(name, seconds, mode="music"):
    """name の曲を seconds 秒ぶん。music は最後に終わりの和音、bgm はただ続く（切るのは呼ぶ側）"""
    style = name.partition(".")[0]
    barlen = 240 / STYLES[style]["bpm"]
    if mode == "bgm":  # 長い BGM は 3分くらいの曲をつなぐ
        nb = min(int(math.ceil(seconds / barlen)) + 2, int(200 / barlen) + 2)
        y, barlen = _render(name, nb, mode)
        body = y[: ns((nb - 2) * barlen)] if seconds > (nb - 2) * barlen else y
        if len(body) < ns(seconds):
            loop = y[ns(2 * barlen): ns((nb - 2) * barlen)]  # 前奏を除いてくり返す
            reps = int(math.ceil((ns(seconds) - len(body)) / len(loop)))
            body = np.concatenate([body] + [loop] * reps)
        return body[: ns(seconds)]
    nb = max(2, int(round(seconds / barlen)))
    y, barlen = _render(name, nb, mode)
    end = ns((nb - 1) * barlen + barlen * 1.8)
    y = y[:end].copy()
    f = ns(barlen * 1.2)
    y[-f:] *= np.linspace(1, 0, f) ** 2
    return y


# ---------------------------------------------------------------- 効果音

def _env(t, att, rel_at, rel):
    return np.minimum(1, t / att) * np.clip(1 - (t - rel_at) / rel, 0, 1)


def _room(x, amount=0.25, rt=0.6):
    return reverb(np.concatenate([x, np.zeros(ns(rt))]), amount, rt)


def _brown(n, salt):
    x = np.cumsum(noise(n, "brown", salt))
    x = hp(x, 20)
    return norm(x)


@functools.lru_cache(maxsize=None)
def sfx(name):
    base, _, var = name.partition(".")
    var = int(var or 0)
    R = np.random.default_rng(seed_of("sfx", name))

    def T(sec):
        return tt(ns(sec))

    if base == "applause":
        n = ns(6)
        t = tt(n)
        y = np.zeros(n)
        for k in range(6):
            train = np.zeros(n)
            for _ in range(8):
                rate = R.uniform(3.2, 5.0)
                tc = R.uniform(0, 0.25)
                while tc < 6:
                    train[min(n - 1, int(tc * SR))] += R.uniform(0.5, 1)
                    tc += 1 / rate * R.uniform(0.85, 1.15)
            kt = tt(ns(0.03))
            fc = 700 + 350 * k
            ker = bp(noise(len(kt), "clap", k), fc, fc * 2.5) * np.exp(-kt * 250)
            y += signal.oaconvolve(train, ker)[:n]
        y = _room(y * _env(t, 0.4, 4.0, 2.0), 0.35, 1.0)
    elif base == "knock":
        n = ns(0.8)
        t = tt(n)
        y = np.zeros(n)
        for a in (0, 0.2, 0.4):
            tk = tt(ns(0.15))
            k = lp(noise(len(tk), "knock", a), 900) * np.exp(-tk * 60) + 0.8 * np.sin(TAU * 120 * tk) * np.exp(-tk * 45)
            place(y, k, a, 1)
        y = _room(y, 0.3, 0.5)
    elif base == "ring":  # イギリスの電話の呼び出し（2回）
        t = T(5.6)
        on = ((t % 3.0 < 0.4) | ((t % 3.0 > 0.6) & (t % 3.0 < 1.0))).astype(float)
        on = lp(on, 60)
        y = (np.sin(TAU * 400 * t) + np.sin(TAU * 450 * t)) * on
    elif base == "ringtone":
        y = np.zeros(ns(4.2))
        mel = [76, 79, 84, 83, 79, 81]
        for r in range(2):
            for i, m in enumerate(mel):
                place(y, marimba(hz(m), 0.2), r * 2.0 + i * 0.16, 0.8)
    elif base == "buzz":
        t = T(1.4)
        on = lp(((t % 0.55) < 0.38).astype(float), 40)
        y = np.tanh(3 * np.sin(TAU * 170 * t)) * on
        y = lp(y, 1500)
    elif base == "doorbell":
        y = np.zeros(ns(2.8))
        place(y, bell(hz(76), 1), 0, 1)
        place(y, bell(hz(72), 1), 0.6, 1)
    elif base == "whistle":  # 牧羊犬への口笛
        shapes = [[(2200, 2900, 0.25), (2900, 2100, 0.35)], [(2600, 2600, 0.15), (2000, 2700, 0.3), (2700, 2700, 0.2)],
                  [(2400, 2400, 0.7)], [(1900, 2800, 0.2), (2800, 1900, 0.2), (1900, 2800, 0.2)]]
        parts = []
        for f0, f1, d in shapes[var % len(shapes)]:
            tp = tt(ns(d))
            f = np.linspace(f0, f1, len(tp))
            parts.append(np.sin(TAU * np.cumsum(f) / SR) * _env(tp, 0.02, d - 0.04, 0.04))
            parts.append(np.zeros(ns(0.05)))
        y = np.concatenate(parts)
        y += 0.05 * bp(noise(len(y), "breath"), 1500, 4000) * (np.abs(y) > 0.01)
        y = _room(y, 0.4, 1.5)
    elif base == "thunder":
        n = ns(6)
        t = tt(n)
        crack = bp(noise(n, "crack"), 400, 3000) * np.exp(-t * 6) * 0.5
        mod = 0.6 + 0.4 * norm(lp(noise(n, "mod"), 3))
        rumble = lp(_brown(n, "th"), 250, 4) * np.minimum(1, t / 0.3) * np.exp(-t * 0.6) * mod
        y = crack + 2 * norm(rumble)
    elif base in ("rain", "fire", "waves", "wind", "sizzle", "night", "typing", "boil", "birds"):
        y = ambience(base, 5.0 if base != "waves" else 8.0) * 3
        t = tt(len(y))
        y = y * _env(t, 0.5, len(y) / SR - 1.0, 1.0)
    elif base == "tick":
        y = np.zeros(ns(4))
        for i in range(4):
            place(y, drum("tick"), i, 1 if i % 2 == 0 else 0.7)
    elif base == "beep":  # 音声メッセージの始まり
        y = np.zeros(ns(0.45))
        for i, m in enumerate((79, 84)):
            tp = tt(ns(0.12))
            place(y, np.sin(TAU * hz(m) * tp) * _env(tp, 0.005, 0.09, 0.03), i * 0.13, 0.6)
    elif base == "slam":
        t = T(1.2)
        y = lp(noise(len(t), "slam"), 1200) * np.exp(-t * 25) + np.sin(TAU * 70 * t) * np.exp(-t * 12)
        y = _room(y, 0.4, 0.8)
    elif base == "steps":
        y = np.zeros(ns(3.2))
        for i in range(6):
            tk = tt(ns(0.12))
            k = lp(noise(len(tk), "step", i), 700) * np.exp(-tk * 40)
            place(y, k, 0.15 + i * 0.5, 0.9 if i % 2 else 0.7)
        y = _room(y, 0.3, 0.6)
    elif base == "chop":
        y = np.zeros(ns(2.2))
        for i in range(8):
            tk = tt(ns(0.08))
            k = bp(noise(len(tk), "chop", i), 1500, 6000) * np.exp(-tk * 90) + 0.5 * np.sin(TAU * 300 * tk) * np.exp(-tk * 70)
            place(y, k, 0.1 + i * 0.24, 0.8)
    elif base == "heartbeat":
        y = np.zeros(ns(3.6))
        for i in range(4):
            for d, v in ((0, 1), (0.22, 0.7)):
                tk = tt(ns(0.2))
                place(y, np.sin(TAU * 52 * tk) * np.exp(-tk * 18), i * 0.9 + d, v)
    elif base == "swoosh":
        t = T(1.0)
        x = noise(len(t), "sw")
        s_ = np.sin(np.pi * t) ** 2
        y = (bp(x, 300, 1200) * (1 - s_) + bp(x, 1500, 6000) * s_) * s_
    elif base == "static":  # ラジオのダイヤルを回す音
        t = T(2.0)
        y = bp(noise(len(t), "st"), 500, 6000) * (0.6 + 0.4 * np.sin(TAU * 3 * t))
        f = 600 + 900 * np.sin(TAU * 0.7 * t)
        y += 0.5 * np.sin(TAU * np.cumsum(f) / SR) * (t > 1.0)
        y *= _env(t, 0.05, 1.6, 0.4)
    elif base == "churchbell":
        y = np.zeros(ns(6))
        for i in range(3):
            place(y, _partials(hz(55), [(0.5, 0.6, 0.5), (1, 1, 0.7), (1.2, 0.5, 0.9), (1.5, 0.4, 1.0), (2.0, 0.6, 1.2),
                                        (2.5, 0.2, 1.6), (3.0, 0.15, 2)], 5), i * 1.6, 1)
    elif base == "chime":
        t = T(1.1)
        y = 0.22 * np.sin(TAU * 660 * t) * np.exp(-5 * t) + 0.18 * np.sin(TAU * 990 * (t - 0.16)) * np.exp(-5 * (t - 0.16)) * (t >= 0.16)
    elif base == "cork":
        t = T(0.3)
        f = 300 + 900 * np.exp(-t * 30)
        y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t * 25)
    elif base == "car":  # 車のドアが閉まってエンジンがかかる
        y = np.zeros(ns(4))
        place(y, sfx("slam"), 0, 0.8)
        tk = tt(ns(2.5))
        f = 35 + 15 * np.minimum(1, tk / 0.6)
        eng = np.tanh(2 * np.sin(TAU * np.cumsum(f) / SR)) * _env(tk, 0.3, 2.0, 0.5)
        place(y, lp(eng, 400) + 0.2 * lp(noise(len(tk), "eng"), 800) * _env(tk, 0.3, 2.0, 0.5), 1.0, 0.8)
    else:
        raise KeyError(f"効果音がない: {name}")
    return norm(np.asarray(y, dtype=np.float64), 0.7).astype(np.float32)


@functools.lru_cache(maxsize=32)
def _amb_loop(name):
    n = ns(20)
    t = tt(n)
    R = np.random.default_rng(seed_of("amb", name))
    if name == "rain":
        y = bp(noise(n, "rain"), 400, 7000) * 0.5
        drops = np.zeros(n)
        idx = R.integers(0, n, 20 * 40)
        drops[idx] = R.uniform(0.2, 1, len(idx))
        y += hp(drops, 2000) * 0.6
    elif name == "fire":
        y = lp(_brown(n, "fire"), 300) * 0.3
        cr = np.zeros(n)
        idx = R.integers(0, n, 20 * 12)
        cr[idx] = R.exponential(1, len(idx))
        y += bp(cr, 1500, 6000) * 2
    elif name == "waves":
        swell = 0.25 + 0.75 * (0.5 - 0.5 * np.cos(TAU * t / 10)) ** 2
        y = lp(noise(n, "w"), 900) * 0.7 * swell + bp(noise(n, "w2"), 1500, 5000) * 0.35 * swell ** 2
    elif name == "wind":
        x = noise(n, "wind")
        bands = [bp(x, 200, 400), bp(x, 350, 700), bp(x, 600, 1100)]
        w = [0.5 + 0.5 * np.sin(TAU * t / p + o) for p, o in ((7, 0), (5.3, 2), (9.1, 4))]
        y = sum(b * wi for b, wi in zip(bands, w)) * (0.6 + 0.4 * np.sin(TAU * t / 10))
    elif name == "sizzle":
        y = hp(noise(n, "sz"), 3000) * 0.25 * (0.7 + 0.3 * norm(lp(noise(n, "szm"), 2)))
        cr = np.zeros(n)
        idx = R.integers(0, n, 20 * 25)
        cr[idx] = R.exponential(1, len(idx))
        y += hp(cr, 2500) * 0.8
    elif name == "night":  # 虫の声
        y = np.zeros(n)
        for b in range(3):
            f = 4200 + 500 * b
            p = R.uniform(0.6, 1.1)
            on = ((t + b * 0.3) % p < 0.25) * (np.sin(TAU * 30 * t) > 0)
            y += np.sin(TAU * f * t) * lp(on.astype(float), 200) * 0.3
        y += 0.05 * lp(noise(n, "nt"), 600)
    elif name == "typing":
        y = np.zeros(n)
        tc = 0.0
        while tc < 20:
            tk = tt(ns(0.03))
            place(y, hp(noise(len(tk), "key", tc), 1500) * np.exp(-tk * 200), tc, R.uniform(0.4, 1))
            tc += R.uniform(0.08, 0.25) + (R.uniform(0.5, 1.5) if R.random() < 0.08 else 0)
    elif name == "boil":
        y = np.zeros(n)
        for _ in range(20 * 30):
            f0 = R.uniform(400, 1400)
            tk = tt(ns(0.05))
            place(y, np.sin(TAU * np.cumsum(f0 * (1 + 2 * tk / 0.05)) / SR) * np.exp(-tk * 80), R.uniform(0, 20), R.uniform(0.2, 0.8))
        y += 0.1 * lp(noise(n, "bl"), 500)
    elif name == "birds":
        y = np.zeros(n)
        for _ in range(20 * 2):
            tc = R.uniform(0, 19)
            for j in range(R.integers(2, 5)):
                tk = tt(ns(0.07))
                f0 = R.uniform(2800, 4200)
                f = f0 + 1200 * tk / 0.07
                place(y, np.sin(TAU * np.cumsum(f) / SR) * np.sin(np.pi * tk / 0.07) ** 2, tc + j * 0.12, R.uniform(0.3, 0.8))
    else:
        raise KeyError(f"環境音がない: {name}")
    y = norm(y, 1)
    f = ns(1.0)  # つなぎ目を目立たなくする
    y[:f] = y[:f] * np.linspace(0, 1, f) + y[-f:] * np.linspace(1, 0, f)
    return y[:-f].astype(np.float32)


def ambience(name, seconds):
    loop = _amb_loop(name)
    reps = int(math.ceil(ns(seconds) / len(loop)))
    return np.tile(loop, reps)[: ns(seconds)] * 0.25


# ---------------------------------------------------------------- 試す

if __name__ == "__main__":
    import subprocess
    import sys
    from pathlib import Path

    import imageio_ffmpeg

    out = Path(__file__).resolve().parent.parent / "audio" / "test"
    out.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    use_sfx = args and args[0] == "--sfx"
    for a in args[1:] if use_sfx else args:
        if use_sfx:
            y = sfx(a)
        else:
            nm, _, sec = a.partition(":")
            y = render(nm, float(sec or 30), "music")
        pcm = (np.clip(y, -1, 1) * 32767).astype("<i2").tobytes()
        p = out / f"{a.replace(':', '-')}.mp3"
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR),
                        "-ac", "1", "-i", "-", "-b:a", "96k", str(p)], input=pcm, check=True)
        print(f"{p.name}: {len(y) / SR:.1f}秒 peak={np.max(np.abs(y)):.2f} rms={np.sqrt(np.mean(y ** 2)):.3f}")
