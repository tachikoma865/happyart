---
project: happyart
title: happyart / Glintria（運気アート × Instagram自動投稿）
phase: フェーズ1（スピリチュアル属性の集客・1000フォロワーまで）
health: 注意
updated: 2026-07-26
priority: 2
next_action: フェーズ1の投稿30日分を作り直す（旧30件は5パターンの使い回しなので破棄）
next_due: 2026-07-28
---

## 方針（2026-07-26 確定）

商品は **「願いをかなえるアート × お守り」一点物 198,000円**。飾るアートとしては売らない。
目的は**占い・スピリチュアル属性のリスト獲得**。作家としての知名度は追わない。
順序は「①1000フォロワーまで属性集め → ②制作過程の公開 → ③ローンチ」。

詳細は `00_ポジショニングと発信方針_v5.md`（**これが正**。旧 roadmap v2/v4 は使わない）。

## 残タスク

| 優先 | タスク | 状態 | 期限 | メモ |
|---|---|---|---|---|
| A | フェーズ1の投稿を作り直す（30日分） | 未着手 | 2026-07-28 | 柱は ①選択占い（主力・週2）②暦・開運日（週2）③開運の実用テク（週2）④色・数字の意味（週1）。表現ルールは v5 を厳守 |
| — | ~~旧 `posts_schedule.csv` と `mass_generate_images.py` を破棄~~ | ✅ 完了(7/26) | — | 投稿実績2件は `posted_log.md` に退避済み |
| A | 実物3点を商品写真として撮り直す | 未着手 | 2026-07-29 | 現行 `product_images/*_real.png` は乾燥中の写真。ペーパータオル・こぼれた絵の具・筆が写り込んでいる |
| B | cron を `run_poster.sh` を呼ぶ形に書き換える | 要対応 | 2026-07-30 | 新しい投稿ができてから。手順は本ファイル下部の「復旧手順」 |
| B | Threads のトークンを取得して config.json に設定 | 未着手 | 2026-07-30 | `THREADS_セットアップ手引き.md` の手順。20〜40分 |
| B | Threads 投稿を1件テストする | 未着手 | 2026-07-31 | `python3 threads_auto_poster.py --dry-run` → 1件だけ本番 |
| B | LINE公式アカウント作成・リッチメニュー設定 | 未着手 | 2026-08-02 | 「無料であなたの色を診断」の受け皿。属性リスト獲得の本体 |
| B | 選択占いのLINE診断コンテンツを作る | 未着手 | 2026-08-02 | 4色それぞれの詳細診断文。LINE登録の動機になる |
| C | 桃の作品を撮り直すか作り直す | 未着手 | — | ピンクと金が混ざって彩度が落ちている。フェーズ3までに |
| B | `index.html` の断定表現を直す | 未着手 | 2026-08-02 | 「飾ったその場所が、あなたの人生を動かすパワースポットに変わる」など。v5 の表現ルールに合わせる。GitHub Pages のメディア配信元でもあるので消さない |
| — | ~~旧 roadmap v2/v3/v4・旧カレンダー3種・tracker CSV を破棄~~ | ✅ 完了(7/26) | — | 4月ローンチ前提の資料。v5 と混同するため削除 |
| C | 販売プラットフォーム（STORES等）の開設 | 未着手 | — | フェーズ3で必要。一点物なので簡易でよい |

## ⚠️ cron を直す前に必ず読むこと

`posts_schedule.csv` を削除したため、**いま `instagram_auto_poster.py` を動かすとサンプル行を含む CSV が自動生成されます。**
そのサンプル行の投稿日時は過去日付なので、**そのまま実行するとサンプル投稿が本番投稿されます。**

順序を守ること。

1. フェーズ1の新しい投稿内容を作る
2. 新しい `posts_schedule.csv` を作る
3. `python3 instagram_auto_poster.py --dry-run` で内容を確認する
4. そのあとで cron を直す

## 復旧手順（ターミナルで実行）

### 1. いまの cron を確認する

```bash
crontab -l
```

`happyart` または `instagram_auto_poster.py` を含む行が、壊れている行。

### 2. 起動スクリプトに実行権限を付ける

```bash
chmod +x /Users/tachikoma/product/test/happyart/run_poster.sh
```

### 3. 手動で1回動かして、python が見つかるか確認する

```bash
/Users/tachikoma/product/test/happyart/run_poster.sh
```

`python3 = /opt/homebrew/bin/python3` のような行が出れば成功。

### 4. cron を書き換える

```bash
crontab -e
```

古い行を消し、以下を1行入れる（毎日 21:05 実行）。

```
5 21 * * * /Users/tachikoma/product/test/happyart/run_poster.sh >> /Users/tachikoma/product/test/happyart/auto_poster.log 2>&1
```

Threads も同時に投稿する場合は末尾を `run_poster.sh --threads` にする。

> cron が macOS のフルディスクアクセスで弾かれる場合は launchd に切り替える。その際は相談すること。

## 追加したファイル（2026-07-26）

- `run_poster.sh` — python3 を自動検出して投稿を実行する起動スクリプト。cron からはこれを呼ぶ
- `threads_auto_poster.py` — Threads 投稿。`posts_schedule.csv` を共有し、`threads_status` 列で独立管理
- `reschedule_pending.py` — 溜まった pending の日時を振り直す
- `THREADS_セットアップ手引き.md` — Threads トークン取得手順

## 稼働状況（2026-07-26 時点・ログ確認済み）

- `auto_poster.log` は **2026-07-23 11:15 で更新が止まっている**。中身は全行が `/bin/sh: /usr/local/bin/python3: No such file or directory`
- 最後に投稿できたのは 2026-07-21 21:30（day2_pink）。**7/22 以降 5日間、投稿はゼロ**
- `posts_schedule.csv` は 7/26 に破棄済み。投稿実績2件は `posted_log.md` に退避
- → いまは「cron が壊れている」より「**投稿するコンテンツが無い**」ほうが上流。コンテンツ再作成 → CSV作成 → dry-run → cron の順を守る

## 最近の進捗

- 2026-07-26 方針を v5 に確定（商品＝一点物198,000円のお守りアート／目的＝スピリチュアル属性のリスト獲得／フェーズ1は1000フォロワーまで集客）
- 2026-07-26 旧 posts_schedule.csv・旧 roadmap v2/v3/v4・旧カレンダー・tracker CSV を破棄。実績は posted_log.md に退避
- 2026-07-26 run_poster.sh / threads_auto_poster.py / reschedule_pending.py / THREADS手引き を追加
- 2026-07-21 Instagram 自動投稿を稼働開始。day1_gold・day2_pink の2件を投稿成功（以降 停止）

## 注意

- **7/22 以降、自動投稿は1件も成功していない。** ログは python3 のパス不正で埋まっている。実質5日間投稿が止まっている状態。
- 当初の原画販売計画（tracker CSV）と、現在動いている SNS 運用が別物になっている。片方に絞るか、tracker を書き直すのが良い。

## 参照

- `auto_poster.log` — 自動投稿の実行ログ（障害の証拠）
- `posts_schedule.csv` — 30日分の投稿スケジュールと status
- `API自動投稿セットアップ手引き.md` — Instagram Graph API の設定手順
