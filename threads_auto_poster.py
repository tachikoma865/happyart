#!/usr/bin/env python3
"""Threads 自動投稿スクリプト（GLINTRIA / happyart）

instagram_auto_poster.py と同じ posts_schedule.csv を共有し、
Threads 用の status 列だけを別に持つことで、Instagram と独立して投稿できる。

必要な設定（config.json）:
    THREADS_ACCESS_TOKEN … Threads の長期アクセストークン
    THREADS_USER_ID      … Threads のユーザーID（数字）

取得手順は THREADS_セットアップ手引き.md を参照。

使い方:
    python3 threads_auto_poster.py --dry-run   # 投稿せず内容だけ確認
    python3 threads_auto_poster.py --list      # 未来の予約も含めて一覧
    python3 threads_auto_poster.py             # 実際に投稿
"""

import os
import sys
import csv
import json
import time
import ssl
import argparse
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta

CONFIG_FILE = "config.json"
SCHEDULE_FILE = "posts_schedule.csv"
LOCK_FILE = "threads_poster.lock"
API_BASE = "https://graph.threads.net/v1.0"

# 画像・動画のローカルパスを公開URLに変換するためのベースURL
GITHUB_PAGES_BASE_URL = "https://tachikoma865.github.io/happyart"

# Threads 用に追加する列
THREADS_COLUMNS = ["threads_status", "threads_posted_at", "threads_post_id"]

# SSL証明書はきちんと検証する。
# 以前は ssl._create_unverified_context() を使っていたが、それだと
# 検証されていない通信でアクセストークンを送ることになり、盗聴・なりすましに弱い。
# 証明書エラーが出る場合は、証明書を無効化するのではなく certifi を入れて解決すること。
SSL_CONTEXT = ssl.create_default_context()
JST = timezone(timedelta(hours=9))


def log(msg):
    print(f"[{datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        log(f"ERROR: {CONFIG_FILE} がありません。")
        sys.exit(1)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    missing = [k for k in ("THREADS_ACCESS_TOKEN", "THREADS_USER_ID")
               if not config.get(k) or str(config[k]).startswith("YOUR_")]

    if missing:
        # 足りないキーを空で追記して、どこに書けばいいか分かるようにする
        for k in missing:
            config.setdefault(k, "")
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        log(f"ERROR: config.json に {', '.join(missing)} が未設定です。")
        log("       THREADS_セットアップ手引き.md の手順で取得し、config.json に貼り付けてください。")
        sys.exit(1)

    return config


def api_request(url, params, method="GET"):
    if method == "GET":
        url = f"{url}?{urllib.parse.urlencode(params)}"
        data = None
    else:
        data = urllib.parse.urlencode(params).encode("utf-8")

    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, context=SSL_CONTEXT) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        log(f"ERROR: APIリクエスト失敗 (HTTP {e.code}) {body}")
        try:
            return {"error": json.loads(body).get("error", {})}
        except Exception:
            return {"error": {"message": body}}
    except Exception as e:
        log(f"ERROR: 通信エラー {e}")
        return {"error": {"message": str(e)}}


def resolve_media_url(media_url):
    if media_url.startswith(("http://", "https://")):
        return media_url
    return f"{GITHUB_PAGES_BASE_URL.rstrip('/')}/{media_url.lstrip('/')}"


def wait_for_container(creation_id, token):
    """動画コンテナの処理完了を待つ（最大3分）"""
    for _ in range(12):
        res = api_request(f"{API_BASE}/{creation_id}",
                          {"fields": "status", "access_token": token})
        if "error" in res:
            return False, res["error"].get("message", "ステータス確認失敗")
        status = res.get("status")
        log(f"  コンテナ状態: {status}")
        if status == "FINISHED":
            return True, None
        if status == "ERROR":
            return False, "メディア処理エラー"
        time.sleep(15)
    return False, "タイムアウト（動画処理が長すぎます）"


THREADS_LIMIT = 500
LINE_URL = "https://lin.ee/qIBKNVd"

# 1回の実行で投稿する最大件数。
# 溜まった分が一気に連続投稿されるのを防ぐ。Instagram側と同じ考え方。
MAX_POSTS_PER_RUN = 1


def to_threads_text(caption):
    """
    Instagram用のキャプションを Threads 用に整える。

    そのまま投げると3つ問題がある。
      1. Threadsは500字まで。IGのキャプションは超えるものがある
      2. IG流のハッシュタグの羅列は Threads では嫌われる
      3. Threadsは本文にリンクを置けるので「プロフィールから」と書く必要がない
    """
    # ハッシュタグだけの行を落とす
    lines = [l for l in caption.split("\n") if not l.strip().startswith("#")]
    text = "\n".join(lines).strip()

    # IG向けの言い回しを、リンクを直接置く形に変える
    # （旧: 番号を送る形式 / 新: 色の名前を送る形式。どちらの投稿文にも対応する）
    text = text.replace(
        "もっと詳しい読みときは、プロフィールの公式LINEから。\n"
        "選んだ番号を送ってもらえれば、その色の話が届きます。",
        f"詳しい読みときはこちらから。番号を送ってください。\n{LINE_URL}")
    text = text.replace(
        "もっと詳しい読みときは、プロフィールの公式LINEから。\n"
        "選んだ色の名前を送ってもらえれば、その色の話が届きます。",
        f"詳しい読みときはこちらから。色の名前を送ってください。\n{LINE_URL}")
    text = text.replace(
        "もっと詳しい色の読みときは、プロフィールの公式LINEで。\n"
        "無料で受け取れます。",
        f"詳しい色の読みときは、こちらから無料で。\n{LINE_URL}")
    text = text.replace("プロフィールの公式LINE", "公式LINE")
    text = text.replace("──────────", "").strip()

    if len(text) <= THREADS_LIMIT:
        return text

    # 長すぎる場合は、末尾（問いかけやリンク）を残して本文側を削る
    paras = [p for p in text.split("\n\n") if p.strip()]
    tail = paras[-1]
    budget = THREADS_LIMIT - len(tail) - 2
    body = []
    used = 0
    for p in paras[:-1]:
        if used + len(p) + 2 > budget:
            break
        body.append(p)
        used += len(p) + 2
    return ("\n\n".join(body + [tail])).strip()[:THREADS_LIMIT]


def post_to_threads(text, media_url, media_type, config):
    token = config["THREADS_ACCESS_TOKEN"]
    user_id = config["THREADS_USER_ID"]

    params = {"text": text, "access_token": token}
    mt = (media_type or "").upper()

    if not media_url:
        params["media_type"] = "TEXT"
    elif mt in ("REELS", "VIDEO"):
        params["media_type"] = "VIDEO"
        params["video_url"] = media_url
    else:
        params["media_type"] = "IMAGE"
        params["image_url"] = media_url

    log(f"  コンテナ作成中 (media_type={params['media_type']})")
    res = api_request(f"{API_BASE}/{user_id}/threads", params, "POST")
    if "error" in res:
        return False, f"コンテナ作成失敗: {res['error'].get('message')}"

    creation_id = res.get("id")
    if not creation_id:
        return False, "コンテナIDが返りませんでした"

    if params["media_type"] == "VIDEO":
        ok, err = wait_for_container(creation_id, token)
        if not ok:
            return False, err
    else:
        # 画像でもサーバー側の取り込みに少し時間がかかる
        time.sleep(10)

    log("  公開中")
    pub = api_request(f"{API_BASE}/{user_id}/threads_publish",
                      {"creation_id": creation_id, "access_token": token}, "POST")
    if "error" in pub:
        return False, f"公開失敗: {pub['error'].get('message')}"

    return True, pub.get("id", "")


def ensure_threads_columns(headers, rows):
    """CSV に Threads 用の列が無ければ追加する"""
    added = False
    for col in THREADS_COLUMNS:
        if col not in headers:
            headers.append(col)
            added = True
    if added:
        width = len(headers)
        for row in rows:
            while len(row) < width:
                row.append("")
        # 既存行の threads_status が空なら pending にする
        idx = headers.index("threads_status")
        for row in rows:
            if not row[idx]:
                row[idx] = "pending"
    return added


def process(dry_run=False, show_future=False):
    config = None if dry_run else load_config()

    if not os.path.exists(SCHEDULE_FILE):
        log(f"ERROR: {SCHEDULE_FILE} がありません。")
        return

    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = [r for r in reader]

    added = ensure_threads_columns(headers, rows)
    if added and not dry_run:
        write_csv(headers, rows)
        log("posts_schedule.csv に Threads 用の列を追加しました。")

    i_time = headers.index("post_time")
    i_media = headers.index("media_url")
    i_type = headers.index("media_type")
    i_cap = headers.index("caption")
    i_status = headers.index("threads_status")
    i_at = headers.index("threads_posted_at")
    i_id = headers.index("threads_post_id")

    now = datetime.now(JST).replace(tzinfo=None)
    pending = sum(1 for r in rows if r[i_status].lower() == "pending")
    log(f"全 {len(rows)} 件 / Threads 未投稿 {pending} 件")

    updated = False
    posted_this_run = 0
    for row in rows:
        if row[i_status].lower() != "pending":
            continue
        try:
            post_time = datetime.strptime(row[i_time], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            log(f"WARN: 日時フォーマット不正: {row[i_time]}")
            continue

        due = post_time <= now
        if not due and not show_future:
            continue

        url = resolve_media_url(row[i_media]) if row[i_media] else ""

        if dry_run:
            mark = "実行対象" if due else "未来の予約"
            print("-" * 50)
            print(f"[{mark}] {row[0]} / {row[i_time]} / {row[i_type]}")
            print(f"  media: {url or '(テキストのみ)'}")
            t = to_threads_text(row[i_cap])
            print(f"  text ({len(t)}字): {t[:120]}...")
            continue

        if not due:
            continue

        # 「試行」を数える。成功だけ数えると、通信断のとき全件を試して
        # すべて failed にしてしまう。
        if posted_this_run >= MAX_POSTS_PER_RUN:
            log(f"  {row[0]} は今回は見送り"
                f"（1回につき{MAX_POSTS_PER_RUN}件まで。次の巡回で投稿されます）")
            continue
        posted_this_run += 1

        log(f"投稿実行: {row[0]} (予定 {row[i_time]})")
        ok, result = post_to_threads(to_threads_text(row[i_cap]), url, row[i_type], config)
        row[i_status] = "posted" if ok else "failed"
        row[i_at] = now.strftime("%Y-%m-%d %H:%M:%S")
        row[i_id] = result
        log(f"  → {'成功' if ok else '失敗'}: {result}")
        updated = True

        if not ok:
            # 失敗の原因はトークン切れや通信断のことが多い。
            # 続けると残り全部を failed にして予定表を壊すので、ここで止める。
            log("WARN: 投稿に失敗したため、今回の実行はここで終了します。")
            log("      原因を確認してから threads_status を pending に戻してください。")
            break
        time.sleep(5)

    if updated:
        write_csv(headers, rows)
        log("posts_schedule.csv を更新しました。")
    elif not dry_run:
        log("いま投稿すべき pending はありませんでした。")


def write_csv(headers, rows):
    with open(SCHEDULE_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Threads 自動投稿（GLINTRIA）")
    p.add_argument("--dry-run", action="store_true", help="投稿せず内容だけ表示")
    p.add_argument("--list", action="store_true", help="未来の予約も含めて一覧表示")
    a = p.parse_args()

    if a.list:
        process(dry_run=True, show_future=True)
    else:
        process(dry_run=a.dry_run)
