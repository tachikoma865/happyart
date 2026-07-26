# 画像を公開URLにする手順（GitHub Pages）

Instagram Graph API は**公開URLの画像しか投稿できません**。
ローカルのファイルは使えず、これが前回 `error: local path not allowed` で失敗した原因です。

すでにGitHubリポジトリ（`tachikoma865/happyart`）があるので、GitHub Pagesを使うのが最短です。無料です。

---

## 私が済ませたこと

- ✅ 8月の投稿画像30枚を `post_images/aug/` に生成
- ✅ `build_august.py` の画像URLを `https://tachikoma865.github.io/happyart/post_images/aug` に設定
- ✅ `posts_schedule.csv` を再生成（URLは公開後のものが入っています）
- ✅ `.nojekyll` を追加（GitHub Pagesが一部ファイルを無視するのを防ぐため）
- ✅ **`config.json` をGit管理から外しました**（後述）
- ✅ `.gitignore` を整理（`.DS_Store` や `__pycache__` を除外）
- ✅ 変更をすべてステージ（`git add`）済み

残りは**あなたの操作が必要な2つ**だけです。GitHubへのpushには認証情報が要るため、私からは実行できません。

---

## ステップ1：ターミナルで、下をまるごとコピーして実行

```bash
cd /Users/tachikoma/product/test/happyart
rm -f .git/index.lock
git rm -r --cached __pycache__ -q 2>/dev/null
git add -A
git commit -m "フェーズ1: 8月の投稿30日分・画像・方針v5を追加"
git push origin main
```

> 1行目の `rm -f .git/index.lock` は、私の作業環境の制約で消せなかったロックファイルを消すためのものです。これが残っているとgitが動きません。

---

## ステップ2：GitHubでPagesを有効にする

1. https://github.com/tachikoma865/happyart/settings/pages を開く
2. **Source** を `Deploy from a branch` にする
3. **Branch** を `main` ／ `/ (root)` にして **Save**
4. 数分待つ

---

## ステップ3：ちゃんと公開されたか確認する

ブラウザで次を開いて、画像が表示されればOKです。

https://tachikoma865.github.io/happyart/post_images/aug/01_choice.png

まとめて確認するなら、ターミナルで：

```bash
cd /Users/tachikoma/product/test/happyart
python3 activate_schedule.py
```

30件すべてのURLにアクセスして、公開されているか確認します（この時点では何も変更しません）。

---

## ステップ4：投稿を有効にする

ステップ3で全件OKだったら、次を実行します。

```bash
python3 activate_schedule.py --apply
```

`posts_schedule.csv` の status が `draft` → `pending` に変わり、投稿対象になります。

> **なぜ最初から pending にしないのか**
> 画像が公開されていない状態で投稿が走ると、30件全部が失敗して `failed` になります。
> そうなると1件ずつ手で直すことになるので、先に確認してから切り替える設計にしています。

---

## ⚠️ config.json について（重要）

`config.json` には Instagram のアクセストークンを入れます。**これは絶対に公開してはいけません。**

ところが、このファイルは**これまでGitで管理されていました**。
`.gitignore` には書かれていたのですが、それより前にコミットされていたため、無効になっていた状態です。

このままだと、トークンを書き込んだ瞬間に GitHub に公開されるところでした。

**対応済みの内容**

- `config.json` をGit管理から外しました（ファイル自体はあなたのMacに残っています）
- 代わりに `config.json.example` をテンプレートとして追加しました
- 今後 `config.json` はコミットされません

なお、これまでコミットされていた `config.json` の中身は
`YOUR_LONG_LIVED_ACCESS_TOKEN` というテンプレートのままだったので、
**実際のトークンが漏れたことはありません。** 安心してください。

---

## 補足：GitHub Pagesにすると画像は誰でも見られます

公開URLである以上、URLを知っている人は誰でもアクセスできます。
今回置くのは投稿用の画像（もともとInstagramで公開するもの）なので問題ありません。

ただし、**未公開の作品写真や個人情報を含むファイルはこのリポジトリに置かないでください。**
`product_images/` の実物写真も公開対象になる点は覚えておいてください。

---

## この後の流れ

1. ステップ1〜4を済ませる
2. cron を直す（`STATUS.md` の「復旧手順」）
3. Instagram API のトークンを取得する（`API自動投稿セットアップ手引き.md`）
4. 1件だけテスト投稿して確認
5. 自動投稿を開始
