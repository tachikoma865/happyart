# Threads 自動投稿 セットアップ手引き

`threads_auto_poster.py` を動かすために必要なのは **2つの値** だけです。

- `THREADS_ACCESS_TOKEN` … Threads の長期アクセストークン（60日有効）
- `THREADS_USER_ID` … あなたの Threads ユーザーID（数字）

所要時間は 20〜40分ほど。Instagram の設定とは**別物**なので、既に取得済みの Instagram トークンは使えません。

途中で分からなくなったら、そのステップ番号を伝えてください。その場面から一緒に進めます。

---

## 前提

- Threads アカウントが**公開（非公開でない）**であること
- Meta for Developers に登録済みであること（Instagram の設定で作った開発者アカウントをそのまま使えます）
- Instagram の設定で作ったアプリを流用できますが、**Threads API は別の製品として追加する必要があります**

---

## ステップ1：アプリに Threads API を追加する

1. https://developers.facebook.com/apps/ を開く
2. Instagram 自動投稿で使っているアプリを選ぶ（無ければ「アプリを作成」→ ユースケースで **「Threads API へのアクセス」** を選択）
3. 左メニューの「製品を追加」から **Threads API** を追加する
4. 「Threads API」→「設定」で、以下の権限（スコープ）にチェックを入れる
   - `threads_basic`
   - `threads_content_publish`

---

## ステップ2：リダイレクトURLを登録する

Threads API は認証にリダイレクト先の登録が必須です。

1. 「Threads API」→「設定」→「リダイレクトコールバックURL」に以下を入力
   ```
   https://tachikoma865.github.io/happyart/
   ```
   （GitHub Pages を使っているのでこのURLで通ります。他のURLでも構いませんが、後の手順と一致させてください）
2. 保存する

---

## ステップ3：短期トークンを取得する

1. 「Threads API」→「Threads テストユーザー」で、自分の Threads アカウントをテストユーザーとして追加し、承認する
2. 同じ画面の **「アクセストークンを生成」** を押す
3. Threads へのログインと権限の許可を求められるので、すべて許可する
4. 表示された長い文字列（短期トークン、有効期限1時間）をコピーしておく

> この画面が見つからない場合は、グラフAPIエクスプローラ（https://developers.facebook.com/tools/explorer/）でも取得できます。その際はアプリとして自分のアプリを選び、権限に `threads_basic` と `threads_content_publish` を追加してください。

---

## ステップ4：短期トークンを長期トークン（60日）に交換する

ターミナルで以下を実行します。`<APP_SECRET>` と `<短期トークン>` は自分の値に置き換えてください。

APP_SECRET は「アプリの設定」→「ベーシック」→「app secret」の「表示」ボタンで確認できます。

```bash
curl -s "https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=<APP_SECRET>&access_token=<短期トークン>"
```

返ってきた JSON の `access_token` の値が **長期トークン** です。これをコピーします。

---

## ステップ5：ユーザーIDを取得する

長期トークンを使って、以下を実行します。

```bash
curl -s "https://graph.threads.net/v1.0/me?fields=id,username&access_token=<長期トークン>"
```

返ってきた `id` の数字が `THREADS_USER_ID` です。`username` が自分のアカウント名になっているか確認してください。

---

## ステップ6：config.json に貼り付ける

`config.json` を開き、以下の2行を追加します（既存の Instagram 用の値はそのまま残してください）。

```json
{
    "ACCESS_TOKEN": "（既存のInstagram用トークン）",
    "INSTAGRAM_BUSINESS_ACCOUNT_ID": "（既存のID）",
    "GRAPH_API_VERSION": "v20.0",
    "THREADS_ACCESS_TOKEN": "ここに長期トークン",
    "THREADS_USER_ID": "ここにユーザーID"
}
```

---

## ステップ7：投稿せずに動作確認する

```bash
cd /Users/tachikoma/product/test/happyart
python3 threads_auto_poster.py --dry-run
```

投稿予定の内容が表示されれば設定は正しく読めています。この時点ではまだ投稿されません。

続けて1件だけ本番投稿を試すには、`posts_schedule.csv` の `threads_status` 列を1行だけ `pending` にして（他は `skip` などにして）、以下を実行します。

```bash
python3 threads_auto_poster.py
```

---

## トークンの更新について

長期トークンの有効期限は **60日** です。期限が切れると投稿が止まります。
期限内に以下を実行すると、さらに60日延長できます。

```bash
curl -s "https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token&access_token=<現在の長期トークン>"
```

**50日目あたりでリマインドが必要**です。Cowork に「Threadsのトークン更新を50日後にリマインドして」と伝えれば、定期タスクとして登録できます。

---

## よくあるつまずき

| 症状 | 原因と対処 |
|---|---|
| `(#100) Invalid parameter` | Threads アカウントが非公開になっている。公開に切り替える |
| `Application does not have permission` | 権限に `threads_content_publish` が入っていない。ステップ1に戻る |
| 画像URLでエラー | GitHub Pages の URL がブラウザで開けるか確認する。開けなければ Pages が未有効 |
| 動画が FINISHED にならない | Threads の動画要件（MP4・H.264・最長5分）を満たしているか確認する |
