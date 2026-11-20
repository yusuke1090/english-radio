#!/usr/bin/env python3
"""台本を読み上げずに確かめる: 単語数・IELTS の言葉の数・声"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

d = build.load_dict()
for a in sys.argv[1:] or [p.stem for p in sorted(build.EPISODES.glob("[0-9][0-9][0-9].txt"))]:
    p = build.EPISODES / f"{int(a):03d}.txt"
    m, v, it, w = build.parse(p, d)
    n = sum(len(build.clean(i[3]).split()) for i in it if i[0] == "say")
    print(f"{p.stem} {m['title'][:40]:<40} {n:>5}語 単語{len(w):>3} 声:{','.join(k for k in v if k != 'JP')}")
