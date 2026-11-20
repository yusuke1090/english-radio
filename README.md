# English Radio

通勤の車で聞く英語のラジオ（ポッドキャスト）。毎回ちがう形（3話つづきの物語・TED ふうの話・Vlog・お笑い・DJ の音楽番組・昔話など）で、話す人も毎回ちがう。曲と効果音は numpy で作る（tools/music.py）。

- 聞く: https://yusuke1090.github.io/english-radio/ の「Podcast アプリで登録」。うまく開かないときは、Podcast アプリの「ライブラリ」→「…」→「URLで番組をフォロー」に `https://yusuke1090.github.io/english-radio/feed.xml`
- 1回は25分くらい。最後に、その回の話し手がその回の単語（単語・日本語の意味・番組の中の文）を読む

## 回を足す

1. `episodes/NNN.txt` を書く（形は下）。`.venv/bin/python tools/check.py NNN` で語数（3,000語くらいで25分）と単語の数（18〜25）を見る
2. `.venv/bin/python tools/build.py` で、読み上げ（edge-tts）と曲を混ぜて mp3 を作り、Release `audio` に上げ、`episodes.json` と `feed.xml` を書き直す（`--only N --local` は1回分だけ試しに作る）
3. コミットしてプッシュする（Actions が Release の mp3 と一緒に Pages に出す。Release の URL のままだと iPhone でその場で再生できない）

最初の準備: `python3 -m venv .venv && .venv/bin/pip install edge-tts imageio-ffmpeg mutagen numpy scipy`

## 台本の形

```
title: Duchess Is Missing (1/3)
date: 2026-11-01
description: 説明
voice: ELLIE = en-GB-MaisieNeural
voice: WALTER = en-IE-ConnorNeural -12% -10Hz

# 見出し（音は鳴らない。ページの区切り）
[music mystery.1 16]      曲を16秒（mystery は曲調、.1 で調・テンポ・メロディが変わる）
[bgm acoustic.3]          声の後ろで小さく流す（声のない所では大きくなる）。[bgm off] で止める
[amb rain]                環境音（rain fire waves wind night birds typing sizzle boil）。[amb off]
[sfx knock]               効果音（knock applause thunder ring ringtone buzz doorbell whistle slam steps car beep tick swoosh static ...）。最後に & をつけると次と重ねる
[pause 1.5]
ELLIE: 1行が1つの発話。[[symptoms|symptom]] のように単語帳の言葉を囲む。
ELLIE (whisper): 気分をつけると速さ・高さ・大きさが変わる（excited sad whisper angry shout tired dry calm warm など。tools/build.py の MOODS）
```

- 最初の `voice:` がその回の話し手（最後の単語の振り返りを読む）。声は `.venv/bin/edge-tts --list-voices`。後ろの `-12% -10Hz` で速さと高さを変える
- 曲調: lofi citypop acoustic mystery afro space comedy orchestral jazz synthwave piano spooky sports kitchen bossa
- `[[語]]`・`[[文の中の形|単語帳の形]]` は `~/apps/textbooks/books/ielts/words` にある言葉だけ使える。`tools/mark.py N --dry` で候補を探せる（意味がずれるものは `--skip=語,語` で外す）
- 大文字だけの強調（CUP など）は読み上げで1文字ずつ読まれることがあるので書かない
