# happyart / Glintria プロジェクト(運気アート × Instagram自動投稿)

瞑想×運気アート(フルイドアート画像)をInstagram・Threadsに自動投稿して集客するプロジェクト。
ブランド名は **Glintria**。フェーズ1の目標: スピリチュアル属性の集客で1000フォロワー、LINE登録30件/30日。
**現状把握はまず STATUS.md を読む**(next_action / next_due に最優先タスクが書いてある)。

## 全体像
- 発信方針: `00_ポジショニングと発信方針_v5.md`
- 優先順位(2026-07-31の会議で決定): ①LINE設定(受け皿) → ②Threads参戦 → ③選択占いのリール化 → ④手動エンゲージメント。受け皿(LINE)を直すのが常に先。

## 自動投稿の仕組み
- `instagram_auto_poster.py` — IG/Threads自動投稿本体。スケジュールは `posts_schedule.csv`、実績は `posted_log.md`、ログは `auto_poster.log`。
- `generate_post_images.py` / `generate_reel.py` / `build_reels.py` — 投稿画像・リール生成(素材: fluid_art_*.png、bgm/)。
- `generate_richmenu.py` / `LINE_色診断コンテンツ.md` — LINE関連。
- `koyomi/` + `build_koyomi_site.py` — 暦コンテンツ。
- 設定は `config.json`(認証情報の扱いは `API自動投稿セットアップ手引き.md` 参照)。

## 運用ルール
- 「今日の投稿は成功した?」と聞かれたら: `posted_log.md` と `auto_poster.log` を確認し、成功/失敗と失敗理由を平易に報告する。
- **失敗した投稿は自動では再試行されない**。failedを見つけたら再投稿の要否を判断材料つきで提示する。
- 投稿文・画像のテイストは既存の投稿(post_images/、posted_log.md)に合わせる。スピリチュアル系の誇大な効能断定はしない。
- 応答はすべて日本語。
