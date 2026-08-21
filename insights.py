#!/usr/bin/env python3
"""
Instagram と Threads の数字をまとめて取る

「静止画は表示0、リールは42」のような事実を、毎回スマホで確認するのは大変。
投稿ごとの数字を一覧にして、どの形式・どの題材が効いているかを判断できるようにする。

必要な権限:
  Instagram … instagram_basic / instagram_manage_insights
  Threads   … threads_basic / threads_manage_insights

使い方:
    python3 insights.py               # Instagram と Threads の両方
    python3 insights.py --instagram   # Instagramだけ
    python3 insights.py --threads     # Threadsだけ
    python3 insights.py --csv         # CSVで出力（表計算に貼る用）
"""

import argparse
import csv
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

CONFIG_FILE = "config.json"
JST = timezone(timedelta(hours=9))
SSL_CONTEXT = ssl.create_default_context()
LIMIT = 30


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def api(base, path, params):
    url = f"{base}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url),
                                    context=SSL_CONTEXT, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return None, json.loads(body).get("error", {}).get("message", body)
        except Exception:
            return None, body
    except Exception as e:
        return None, str(e)


def jst(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST).strftime("%m/%d %H:%M")
    except Exception:
        return "?"


# ---------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------

def instagram(config):
    base = f"https://graph.facebook.com/{config.get('GRAPH_API_VERSION', 'v20.0')}"
    token = config["ACCESS_TOKEN"]
    ig_id = config["INSTAGRAM_BUSINESS_ACCOUNT_ID"]

    me, err = api(base, ig_id, {
        "fields": "username,followers_count,media_count", "access_token": token})
    if err:
        return None, [], f"アカウント情報を取得できません: {err}"

    media, err = api(base, f"{ig_id}/media", {
        "fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count",
        "limit": LIMIT, "access_token": token})
    if err:
        return me, [], f"投稿一覧を取得できません: {err}"

    rows = []
    for m in media.get("data", []):
        is_reel = m.get("media_product_type") == "REELS"
        metrics = "reach,saved,shares,total_interactions"
        if is_reel:
            metrics += ",views"
        ins, e = api(base, f"{m['id']}/insights", {
            "metric": metrics, "access_token": token})
        vals = {}
        if not e:
            for d in ins.get("data", []):
                v = d.get("values", [{}])[0].get("value")
                vals[d["name"]] = v
        rows.append({
            "platform": "Instagram",
            "time": jst(m.get("timestamp")),
            "type": "リール" if is_reel else "画像",
            "head": (m.get("caption") or "").split("\n")[0][:24],
            "views": vals.get("views", "-"),
            "reach": vals.get("reach", "-"),
            "saved": vals.get("saved", "-"),
            "likes": m.get("like_count", 0),
            "comments": m.get("comments_count", 0),
            "permalink": m.get("permalink", ""),
        })
    return me, rows, None


# ---------------------------------------------------------------
# Threads
# ---------------------------------------------------------------

def threads(config):
    base = "https://graph.threads.net/v1.0"
    token = config.get("THREADS_ACCESS_TOKEN")
    uid = config.get("THREADS_USER_ID")
    if not token or not uid:
        return None, [], "config.json に Threads の設定がありません"

    posts, err = api(base, f"{uid}/threads", {
        "fields": "id,text,timestamp,permalink,media_type",
        "limit": LIMIT, "access_token": token})
    if err:
        return None, [], f"投稿一覧を取得できません: {err}"

    rows = []
    for p in posts.get("data", []):
        ins, e = api(base, f"{p['id']}/insights", {
            "metric": "views,likes,replies,reposts,quotes", "access_token": token})
        vals = {}
        if e and ("permission" in e.lower() or "scope" in e.lower()):
            return None, [], ("インサイトの権限がありません。"
                              "threads_manage_insights を追加して、トークンを取り直してください。")
        if not e:
            for d in ins.get("data", []):
                vals[d["name"]] = d.get("values", [{}])[0].get("value")
        rows.append({
            "platform": "Threads",
            "time": jst(p.get("timestamp")),
            "type": "テキスト" if p.get("media_type") == "TEXT_POST" else "メディア",
            "head": (p.get("text") or "").split("\n")[0][:24],
            "views": vals.get("views", "-"),
            "reach": "-",
            "saved": "-",
            "likes": vals.get("likes", "-"),
            "comments": vals.get("replies", "-"),
            "permalink": p.get("permalink", ""),
        })
    return None, rows, None


# ---------------------------------------------------------------

def show(rows):
    if not rows:
        print("  投稿がありません。")
        return
    print(f"  {'日時':<12} {'種別':<6} {'表示':>6} {'リーチ':>6} {'保存':>5} "
          f"{'いいね':>5} {'コメ':>4}  冒頭")
    print("  " + "-" * 76)
    for r in sorted(rows, key=lambda x: x["time"]):
        print(f"  {r['time']:<12} {r['type']:<6} {str(r['views']):>6} "
              f"{str(r['reach']):>6} {str(r['saved']):>5} "
              f"{str(r['likes']):>5} {str(r['comments']):>4}  {r['head']}")


def summarize(rows):
    """形式ごとに平均を出す。どの形式が効いているかを判断するため。"""
    groups = {}
    for r in rows:
        key = f"{r['platform']}／{r['type']}"
        v = r["views"] if isinstance(r["views"], int) else (
            r["reach"] if isinstance(r["reach"], int) else None)
        groups.setdefault(key, []).append(v)
    print("\n■ 形式ごとの平均表示数")
    for k, vs in groups.items():
        nums = [v for v in vs if isinstance(v, int)]
        avg = f"{sum(nums) / len(nums):.0f}" if nums else "取得できず"
        print(f"  {k:<20} {len(vs)}件  平均 {avg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instagram", action="store_true")
    ap.add_argument("--threads", action="store_true")
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    config = load_config()
    both = not (args.instagram or args.threads)
    all_rows = []

    if args.instagram or both:
        print("=" * 80)
        print(" Instagram")
        print("=" * 80)
        me, rows, err = instagram(config)
        if me:
            print(f"  @{me.get('username')}  フォロワー {me.get('followers_count')}人  "
                  f"投稿 {me.get('media_count')}件\n")
        if err:
            print(f"  [ERROR] {err}")
        else:
            show(rows)
            all_rows += rows
        print()

    if args.threads or both:
        print("=" * 80)
        print(" Threads")
        print("=" * 80)
        _, rows, err = threads(config)
        if err:
            print(f"  [ERROR] {err}")
        else:
            show(rows)
            all_rows += rows
        print()

    if all_rows:
        summarize(all_rows)

    if args.csv and all_rows:
        out = "insights.csv"
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
        print(f"\nCSVを書き出しました: {out}")


if __name__ == "__main__":
    main()
