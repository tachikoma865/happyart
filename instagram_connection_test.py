#!/usr/bin/env python3
"""
Instagram (Meta Graph API) 連携診断スクリプト

「連携できたか分からない」を切り分けるための健康診断ツール。
config.json のトークン/IDを使い、以下を順にチェックして日本語で結果を表示します。

  1. トークンが有効か（/me で本人確認）
  2. Instagramビジネスアカウントに到達できるか（username, フォロワー数を取得）
  3. 投稿(コンテンツ公開)の権限・投稿枠が使えるか（content_publishing_limit）

使い方:
    python3 instagram_connection_test.py

※ 投稿は行いません。読み取りのみの安全な診断です。
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

CONFIG_FILE = "config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"[NG] '{CONFIG_FILE}' が見つかりません。先に instagram_auto_poster.py を一度実行してテンプレートを作成し、値を入力してください。")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 未入力チェック
    if cfg.get("ACCESS_TOKEN", "").startswith("YOUR_") or cfg.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").startswith("YOUR_"):
        print("[NG] config.json がテンプレートのままです。ACCESS_TOKEN と INSTAGRAM_BUSINESS_ACCOUNT_ID を実際の値に書き換えてください。")
        sys.exit(1)
    return cfg


def api_get(url, params):
    query = urllib.parse.urlencode(params)
    full = f"{url}?{query}"
    req = urllib.request.Request(full, method="GET")
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err = json.loads(body).get("error", {})
            return None, err.get("message", body)
        except Exception:
            return None, body
    except Exception as e:
        return None, str(e)


def main():
    cfg = load_config()
    token = cfg["ACCESS_TOKEN"]
    ig_id = cfg["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
    ver = cfg.get("GRAPH_API_VERSION", "v20.0")
    base = f"https://graph.facebook.com/{ver}"

    print("=" * 50)
    print(" Instagram 連携 健康診断")
    print("=" * 50)

    ok = True

    # 1. トークン有効性
    print("\n[1/3] アクセストークンの有効性を確認中...")
    me, err = api_get(f"{base}/me", {"fields": "id,name", "access_token": token})
    if err:
        print(f"  [NG] トークンが無効か期限切れです: {err}")
        print("       → Meta開発者ダッシュボードで長期トークンを再発行してください。")
        ok = False
    else:
        print(f"  [OK] トークン有効。連携ユーザー/ページ: {me.get('name')} (id: {me.get('id')})")

    # 2. Instagramビジネスアカウント到達性
    print("\n[2/3] Instagramビジネスアカウントへの到達を確認中...")
    ig, err = api_get(f"{base}/{ig_id}", {
        "fields": "id,username,followers_count,media_count",
        "access_token": token,
    })
    if err:
        print(f"  [NG] IGアカウントに到達できません: {err}")
        print("       → INSTAGRAM_BUSINESS_ACCOUNT_ID が正しいか、")
        print("         IGが『ビジネス/クリエイター』でFacebookページと連携済みか確認してください。")
        ok = False
    else:
        print(f"  [OK] 連携成功！ @{ig.get('username')}")
        print(f"       フォロワー数: {ig.get('followers_count')} / 投稿数: {ig.get('media_count')}")

    # 3. コンテンツ公開枠（投稿できる状態か）
    print("\n[3/3] 投稿(コンテンツ公開)の可否を確認中...")
    lim, err = api_get(f"{base}/{ig_id}/content_publishing_limit", {
        "fields": "quota_usage,config",
        "access_token": token,
    })
    if err:
        print(f"  [NG] コンテンツ公開APIにアクセスできません: {err}")
        print("       → アプリに instagram_content_publish 権限が付与されているか確認してください。")
        ok = False
    else:
        data = lim.get("data", [{}])
        usage = data[0].get("quota_usage", "?") if data else "?"
        quota = data[0].get("config", {}).get("quota_total", 50) if data else 50
        print(f"  [OK] 投稿可能。直近24時間の使用: {usage} / {quota} 件")

    print("\n" + "=" * 50)
    if ok:
        print(" 結果: すべて正常。自動投稿の準備ができています。")
        print(" 次の注意点: 画像は『公開URL』が必須です（ローカルパス不可）。")
    else:
        print(" 結果: 未解決の項目があります。上記[NG]を修正してください。")
    print("=" * 50)


if __name__ == "__main__":
    main()
