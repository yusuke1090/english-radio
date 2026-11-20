#!/usr/bin/env python3
"""台本の中から IELTS の単語帳の言葉を探して [[...]] で囲む（回ごとに 18〜24 語）。

  .venv/bin/python tools/mark.py 5        # episodes/005.txt に印をつける
  .venv/bin/python tools/mark.py 5 --dry  # 候補を見るだけ
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import EPISODES, LINE_RE, WORD_RE, load_dict  # noqa: E402

# やさしすぎて覚える意味の少ない言葉
EASY = set("""data online user test pass fail skip key green local label snack recipe robot drone stage factor
issue means term grade staff shift wage brand market loss profit trade cell gene dose nurse cure stress diet
cause effect reason value norm stream crash update upgrade password access digital virtual remote device gadget
download browse platform hospital clinic patient surgery injury fitness hunger famine journal publish survey
sample discover scientist physics chemistry biology research researcher experiment laboratory test proof prove
supply demand coal mineral mining protest campaign activist treaty waste litter dump recycle recycling reuse
smartphone social media online career interview salary colleague manager workplace overtime commute commuter
retire volunteer experience teamwork responsibility leadership deadline workload income budget invest investor
consumer producer export import industry enterprise competition competitor economy poverty wealth crisis debt
cuisine ingredient flavour appetite portion beverage vegetarian vegan takeaway supermarket label allergy
vitamin protein calorie diet snack hygiene nutrition recover recovery treatment medication antibiotic vaccine
tutor lecturer mentor pupil campus faculty semester timetable term assignment coursework thesis skill knowledge
pass fail excel cram revise engage concentrate motivate motivation discipline academic graduate scholarship
interactive theoretical hands-on competence expertise proficiency literate literacy numeracy
habitat species wildlife ecosystem drought flood heatwave glacier pollution toxic smog landfill compost
solar wind turbine battery coal power station power grid power cut insulation
global local national international public private urban rural domestic modern traditional contemporary
common rare typical general specific particular natural physical mental emotional financial economic social
cultural political environmental positive negative major minor primary secondary key basic
mainly mostly partly entirely probably possibly certainly clearly obviously generally typically frequently
occasionally rarely directly indirectly recently currently previously initially eventually ultimately
""".split())


def forms(head):
    words = head.split()
    if any(w in ("sth", "sb", "one's") for w in words) or "/" in head or "(" in head:
        return set()

    def infl(w):
        out = {w, w + "s", w + "es", w + "ed", w + "d", w + "ing", w + "er", w + "ers"}
        if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
            out |= {w[:-1] + "ies", w[:-1] + "ied"}
        if w.endswith("e"):
            out |= {w[:-1] + "ing", w[:-1] + "ed"}
        if len(w) > 2 and w[-1] not in "aeiouwxy" and w[-2] in "aeiou" and w[-3] not in "aeiou":
            out |= {w + w[-1] + "ed", w + w[-1] + "ing"}
        if w.endswith("is"):
            out.add(w[:-2] + "es")
        if w.endswith("on") and w in ("phenomenon", "criterion"):
            out.add(w[:-2] + "a")
        return out

    irregular = {"lay": {"laid", "laying", "lays"}, "lead": {"led", "leading", "leads"},
                 "arise": {"arose", "arisen", "arising", "arises"}, "overcome": {"overcame", "overcoming", "overcomes"},
                 "undertake": {"undertook"}, "seek": {"sought"}, "drop": {"dropped", "dropping", "drops"}}
    if len(words) == 1:
        return infl(words[0]) | irregular.get(words[0], set())
    first = infl(words[0]) | irregular.get(words[0], set())
    last = infl(words[-1])
    mid = " ".join(words[1:-1])
    out = set()
    for f in first:
        out.add(" ".join([f] + words[1:]))
    for l in last:
        out.add(" ".join(words[:-1] + [l]))
    return {re.sub(r"\s+", " ", o) for o in out} | {head} if mid is not None else out


def main():
    n = int(sys.argv[1])
    dry = "--dry" in sys.argv
    skip = set(next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--skip=")), []))
    want = 22
    path = EPISODES / f"{n:03d}.txt"
    lines = path.read_text().split("\n")
    dic = load_dict()
    pats = []
    for key, v in dic.items():
        if key in EASY or key in skip or len(key) < 5:
            continue
        fs = forms(key)
        if not fs:
            continue
        rx = re.compile(r"(?<![\w\[|-])(" + "|".join(sorted(map(re.escape, fs), key=len, reverse=True)) + r")(?![\w\]|-])", re.I)
        score = len(key) + (6 if " " in key else 0)
        pats.append((score, key, rx))
    already = {(m.group(2) or m.group(1)).lower() for l in lines for m in WORD_RE.finditer(l)}
    speech = [i for i, l in enumerate(lines) if LINE_RE.fullmatch(l.strip())]
    found = {}  # key -> (line, start, end, score)
    for i in speech:
        text = lines[i]
        body_at = text.index(":") + 1
        for score, key, rx in pats:
            if key in found or key in already:
                continue
            for m in rx.finditer(text, body_at):
                if "[[" in text[max(0, m.start() - 2): m.start()] or WORD_RE.search(text[max(0, m.start() - 40): m.end() + 2]) and text[max(0, m.start() - 2): m.start()] == "[[":
                    continue
                found[key] = (i, m.start(), m.end(), score)
                break
    # 台本全体に散らばるように選ぶ
    picks = []
    if found:
        total = len(speech)
        buckets = {}
        for key, (i, a, b, sc) in found.items():
            pos = speech.index(i) * (want - len(already)) // max(1, total)
            buckets.setdefault(pos, []).append((sc, key))
        for pos in sorted(buckets):
            picks.append(max(buckets[pos])[1])
        rest = sorted(((found[k][3], k) for k in found if k not in picks), reverse=True)
        while len(picks) + len(already) < want and rest:
            picks.append(rest.pop(0)[1])
        picks = picks[: max(0, want - len(already))]
    # 後ろから書き換える（位置がずれないように）
    edits = sorted(((found[k][0], found[k][1], found[k][2], k) for k in picks), reverse=True)
    for i, a, b, k in edits:
        s = lines[i][a:b]
        rep = f"[[{s}]]" if s.lower() == k else f"[[{s}|{dic[k]['word']}]]"
        print(f"  {dic[k]['word']:<24} {dic[k]['ja'][:20]:<20} ← {s}")
        if not dry:
            lines[i] = lines[i][:a] + rep + lines[i][b:]
    print(f"{len(already)} 語は前からある・{len(picks)} 語を足す（候補 {len(found)}）")
    if not dry:
        path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
