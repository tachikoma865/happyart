#!/usr/bin/env python3
"""
Threads に届いたコメントを取得する

コメントに気づかず放置すると会話が途切れる。Threads は会話がリーチのエンジンなので、
拾えていないコメントがあること自体が機会損失になる。

**このスクリプトは返信を投稿しない。** 取得して一覧にするだけ。
返信文は人が目を通してから送る。理由は3つ。
  ・自動生成と分かった時点で「断定しない誠実さ」という差別化が崩れる
  ・自動化された不自然なエンゲージメントは規約上のリスクがある
  ・占いアカウントには弱っている人が来る。人の目を通さずに公開すべきでない

必要な権限: threads_basic / threads_manage_replies
  （権限を足したあと、アクセストークンを取り直す必要がある）

使い方:
    python3 threads_replies.py              # 新しいコメントだけ表示
    python3 threads_replies.py --all        # 既読ぶんも含めて表示
    python3 threads_replies.py --json       # 機械可読な形で出力
    python3 threads_replies.py --mark-read  # 表示済みとして記録する
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

CONFIG_FILE = "config.json"
SEEN_FILE = "threads_replies_seen.json"
API_BASE = "https://graph.threads.net/v1.0"
JST = timezone(timedelta(hours=9))
SSL_CONTEXT = ssl.create_default_context()

# 自分の投稿を何件さかのぼって見るか
POSTS_TO_CHECK = 25


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"[ERROR] {CONFIG_FILE} がありません。")
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        c = json.load(f)
    for k in ("THREADS_ACCESS_TOKEN", "THREADS_USER_ID"):
        if not c.get(k):
            print(f"[ERROR] config.json に {k} がありません。")
            sys.exit(1)
    return c


def api_get(path, params):
    url = f"{API_BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=30) as res:
            return json.loads(res.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        msg = body
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            pass
        return None, f"HTTP {e.code}: {msg}"
    except Exception as e:
        return None, str(e)


def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=1)


def jst(ts):
    """APIのタイムスタンプを日本時間の読みやすい形にする"""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(JST).strftime("%m/%d %H:%M")
    except Exception:
        return ts or "?"


def fetch(config):
    token = config["THREADS_ACCESS_TOKEN"]
    user_id = config["THREADS_USER_ID"]

    posts, err = api_get(f"{user_id}/threads", {
        "fields": "id,text,timestamp,permalink",
        "limit": POSTS_TO_CHECK,
        "access_token": token,
    })
    if err:
        print(f"[ERROR] 投稿一覧を取得できませんでした: {err}")
        if "permission" in err.lower() or "scope" in err.lower():
            print()
            print("  権限が足りていない可能性があります。")
            print("  threads_manage_replies を追加して、トークンを取り直してください。")
        sys.exit(1)

    out = []
    for p in posts.get("data", []):
        replies, err = api_get(f"{p['id']}/replies", {
            "fields": "id,text,username,timestamp,permalink",
            "access_token": token,
        })
        if err:
            # 1件の失敗で全体を止めない
            continue
        for r in replies.get("data", []):
            # 自分の返信は除く
            if r.get("username") == config.get("THREADS_USERNAME"):
                continue
            out.append({
                "reply_id": r["id"],
                "username": r.get("username", "?"),
                "text": (r.get("text") or "").strip(),
                "time": jst(r.get("timestamp")),
                "permalink": r.get("permalink", ""),
                "post_excerpt": (p.get("text") or "").split("\n")[0][:40],
                "post_time": jst(p.get("timestamp")),
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="既読も含めて表示する")
    ap.add_argument("--json", action="store_true", help="JSONで出力する")
    ap.add_argument("--mark-read", action="store_true", help="表示したものを既読にする")
    args = ap.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    config = load_config()
    replies = fetch(config)
    seen = load_seen()

    targets = replies if args.all else [r for r in replies if r["reply_id"] not in seen]
    targets.sort(key=lambda r: r["time"])

    if args.json:
        print(json.dumps(targets, ensure_ascii=False, indent=2))
    else:
        print("=" * 58)
        print(f" Threadsのコメント  {datetime.now(JST):%m/%d %H:%M} JST")
        print("=" * 58)
        if not targets:
            print("\n 新しいコメントはありません。")
        else:
            print(f"\n 未読 {len(targets)}件\n")
            for r in targets:
                print("-" * 58)
                print(f" @{r['username']}  {r['time']}")
                print(f" （{r['post_excerpt']}… への返信）")
                print()
                for line in r["text"].split("\n"):
                    print(f"   {line}")
                if r["permalink"]:
                    print(f"\n   {r['permalink']}")
                print()
        print("=" * 58)

    if args.mark_read:
        save_seen(seen | {r["reply_id"] for r in replies})
        print(f"\n{len(replies)}件を既読にしました。")


if __name__ == "__main__":
    main()
