# 残りの回の計画（11〜20話）

2026-11-20 に1〜10話を作り直して公開した。本人は「飽きない作り」「帰りの車で聞く人の気持ち」「音楽を入れたラジオ」を望んでいる。話す人（主の声）は毎回ちがう声にする。

## 書けているもの

- drafts/011.txt Pole Pole (1/3) 語り Neema（en-TZ-ImaniNeural）。単語の印もついている
- drafts/012.txt Pole Pole (2/3) 語り Haruto（en-HK-SamNeural）。単語の印はまだ（`tools/mark.py` で足す。drafts にあるので一度 episodes/ に移してから）

## 13話 Pole Pole (3/3) 語り Mzee Joseph（en-TZ-ElimuNeural -10% -8Hz）

- 書き出し: 「74歳。雨季を60回見てきた。雨は新聞もアプリも読んだことがない」
- 生い立ち（1952年生まれ、アルーシャ地方、1979年にミッションスクールの先生から雨量計をもらい毎朝記録）、妻 Mama Grace、子どもはアルーシャとダルエスサラームへ、孫 Zawadi と暮らす
- ハルトの見え方:「歩くのが速すぎる若者」。でも謝りに来た（専門家は普通、謝らずに説明する）
- 洪水の夜: 午前2時にハルトがセンサー17の警報で戸をたたく。Mzee は川の「昔の道筋」を知っていて、低い畑の新しい3家族の家に水が来ると分かる。教会の鐘（[sfx churchbell]）を鳴らさせ、子どもとヤギを学校の高台へ。40分後に泥水。けが人なし。「機械は水の音を聞いた。年寄りは水の行き先を知っていた。どちらか一つでは足りなかった」
- その後: 本当の雨が来る（雨鳥＝アカハラカッコウも新しいモデルも正しかった）。早く育つ乾燥に強い種で植え直し、2〜3月にまずまずの収穫
- 会社: ハルトが村から東京の投資家にビデオで説明（Mzee と Zawadi も）。アプリに農家が SMS で知らせる「しるし」と手書きの日誌のデータを入れる。データは協同組合のもの。Neema が現地の責任者に。上司 Ishida（ko-KR-HyunsuMultilingualNeural）も認める
- 別れ（3月）: ハルトが下手なスワヒリ語であいさつ。Mzee が名前をつける「Mwana wa Mvua（雨の子）」。チキンの Data は Zawadi に
- 終わり: 「pole pole ndio mwendo（ゆっくりが道）。でもあの若者に教わった。ときには走らなければならない」。Zawadi が日誌をパソコンに打ち込む。「雨はそれでも読まない」
- 声: JOSEPH, HARUTO, NEEMA, ZAWADI（en-US-AnaNeural、YouTube で英語を覚えたのでカリフォルニアっぽい）, GRACE（en-KE-AsiliaNeural -4Hz）, LEMA（en-KE-ChilembaNeural）, ISHIDA

## 14〜20話（1話ずつ形を変える）

| 話 | 形 | 主の声 | 中身 |
|---|---|---|---|
| 14 | ラジオのシットコム「Flatmates」 | it-IT-GiuseppeMultilingualNeural（Marco） | ロンドンのシェアハウス。冷蔵庫のルール、消えたヨーグルト…ではなく別の騒動（6話と重ねない）。Bia（pt-BR-ThalitaMultilingualNeural）、Chloé（fr-FR-VivienneMultilingualNeural）、大家 |
| 15 | スポーツ実況 | en-US-GuyNeural ＋ en-NZ-MollyNeural | 牧羊犬競技の決勝。牧羊犬を知らないアメリカ人実況と、元チャンピオンの解説。[sfx whistle.N] |
| 16 | 料理番組 | en-PH-RosaNeural（＋息子 en-PH-JamesNeural） | チキンアドボ。[amb sizzle] [sfx chop] |
| 17 | 怪談 | en-CA-LiamNeural | ニューファンドランドの灯台。[amb waves] [amb wind] |
| 18 | Vlog | en-NG-EzinneNeural | ラゴスの一日（屋台・ジョロフライス・Afrobeats のライブ） |
| 19 | 深夜の DJ 番組「Midnight FM」 | en-US-AndrewMultilingualNeural | 曲6つ（synthwave・piano・space・bossa・lofi・jazz などの別の番号）。4話と話題を重ねない |
| 20 | TED ふうの話「The Joy of Being Bad at Things」 | en-US-EmmaMultilingualNeural | 大人になってから下手なことを始める楽しさ（語学も） |

- どの回も約3,000語・単語18〜25（`tools/check.py`）。事実は確かなものだけ。作った話を本当のことのように書かない
- 書いたら `tools/build.py`（全部）→ コミット・プッシュ → Actions の Pages を確かめる
