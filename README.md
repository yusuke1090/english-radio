# English Radio

通勤の車で聞く、イギリス英語のラジオ（ポッドキャスト）。

- 聞く: https://yusuke1090.github.io/english-radio/ の「Podcast アプリで登録」。うまく開かないときは、Podcast アプリの「ライブラリ」→「…」→「URLで番組をフォロー」に `https://yusuke1090.github.io/english-radio/feed.xml`
- 1回は25分くらい: Farm and Tech（ゲストの話）→ The Report（ニュースふう）→ Daily Talk（雑談）→ Words（その回の単語・日本語の意味・番組の中の文）

## 回を足す

1. `episodes/NNN.txt` を書く（形は下）
2. `.venv/bin/python tools/build.py` で、読み上げ（edge-tts）から mp3 を作って Release `audio` に上げ、`episodes.json` と `feed.xml` を書き直す
3. コミットしてプッシュする（Pages が `feed.xml` を出す）

最初の準備: `python3 -m venv .venv && .venv/bin/pip install edge-tts imageio-ffmpeg mutagen`

## 台本の形

```
title: Smart Collars for Dairy Cows
date: 2026-11-18
description: 説明
guest: MOLLY=en-NZ-MollyNeural

# Farm and Tech
SONIA: 1行が1つの発話。[[symptoms|symptom]] のように単語帳の言葉を囲む。
```

- 声は SONIA・RYAN（イギリス）と JP（日本語）。ゲストは `guest:` で決める（`.venv/bin/edge-tts --list-voices`）
- `# 見出し` は区切り（チャイムが鳴る）。最後の Words とあいさつは build.py が足す
- `[[語]]`・`[[文の中の形|単語帳の形]]` は `~/apps/textbooks/books/ielts/words` にある言葉だけ使える
