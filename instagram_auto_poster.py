#!/usr/bin/env python3
import os
import sys
import csv
import json
import time
import argparse
from datetime import datetime
import urllib.request
import urllib.parse
import urllib.error

# 設定ファイルのパス
CONFIG_FILE = "config.json"
SCHEDULE_FILE = "posts_schedule.csv"

# GitHub Pages のベースURL（画像のローカルパス → 公開URLへの変換に使用）
# ※ GitHub Pages を有効化した後、ここにあなたのURLを設定してください
GITHUB_PAGES_BASE_URL = "https://tachikoma865.github.io/happyart"

def load_config():
    """config.jsonからAPI設定を読み込む。存在しない場合はテンプレートを作成する。"""
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "ACCESS_TOKEN": "YOUR_LONG_LIVED_ACCESS_TOKEN",
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": "YOUR_INSTAGRAM_BUSINESS_ACCOUNT_ID",
            "GRAPH_API_VERSION": "v20.0"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print(f"[INFO] '{CONFIG_FILE}' が見つかりません。テンプレートを作成しました。")
        print("API設定（トークンとID）を入力してから再実行してください。")
        sys.exit(0)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def make_api_request(url, params=None, method="GET"):
    """Meta Graph APIに対してHTTPリクエストを送信する共通関数（標準ライブラリ使用）"""
    headers = {"Content-Type": "application/json"}
    
    if params:
        query_string = urllib.parse.urlencode(params)
        if method == "GET":
            url = f"{url}?{query_string}"
            data = None
        else:
            # POST用のデータ
            data = json.dumps(params).encode("utf-8")
    else:
        data = None

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode("utf-8")
            return json.loads(res_data)
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        print(f"[ERROR] APIリクエストが失敗しました。ステータスコード: {e.code}")
        print(f"[ERROR] レスポンス: {error_msg}")
        try:
            err_json = json.loads(error_msg)
            return {"error": err_json.get("error", {})}
        except Exception:
            return {"error": {"message": error_msg}}
    except Exception as e:
        print(f"[ERROR] 通信エラーが発生しました: {e}")
        return {"error": {"message": str(e)}}

def check_media_status(media_container_id, config):
    """アップロードしたメディア（特に動画）の処理ステータスを確認する"""
    access_token = config["ACCESS_TOKEN"]
    version = config["GRAPH_API_VERSION"]
    url = f"https://graph.facebook.com/{version}/{media_container_id}"
    
    params = {
        "fields": "status_code,status",
        "access_token": access_token
    }
    
    print(f"[INFO] メディアコンテナ {media_container_id} の処理状況を確認中...")
    
    # 最大3分間待つ（動画処理のため）
    for attempt in range(12):
        res = make_api_request(url, params, "GET")
        if "error" in res:
            return False, f"ステータス確認失敗: {res['error'].get('message')}"
        
        status_code = res.get("status_code")
        print(f" -> ステータス: {status_code}")
        
        if status_code == "FINISHED":
            return True, None
        elif status_code == "ERROR":
            error_desc = res.get("status", {}).get("error", {}).get("message", "不明なエラー")
            return False, f"処理エラー: {error_desc}"
        
        # まだ処理中の場合は待つ
        time.sleep(15)
        
    return False, "タイムアウト（動画処理に時間がかかりすぎています）"

def post_to_instagram(media_url, caption, media_type, config):
    """Instagramに画像または動画を投稿するフローを実行する"""
    access_token = config["ACCESS_TOKEN"]
    instagram_id = config["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
    version = config["GRAPH_API_VERSION"]
    
    # 1. メディアコンテナの作成
    container_url = f"https://graph.facebook.com/{version}/{instagram_id}/media"
    
    params = {
        "caption": caption,
        "access_token": access_token
    }
    
    if media_type.upper() == "REELS":
        params["media_type"] = "REELS"
        params["video_url"] = media_url
        # リールの場合は、動画のアスペクト比や秒数に制限があります
    else:
        params["image_url"] = media_url
        # 通常画像投稿
        
    print(f"[INFO] メディアコンテナを作成しています... (URL: {media_url})")
    res = make_api_request(container_url, params, "POST")
    
    if "error" in res:
        return False, f"コンテナ作成に失敗しました: {res['error'].get('message')}"
        
    creation_id = res.get("id")
    if not creation_id:
        return False, "コンテナIDがレスポンスに含まれていません。"
        
    print(f"[SUCCESS] メディアコンテナが作成されました。ID: {creation_id}")
    
    # 2. 動画の場合は処理待ちをする
    if media_type.upper() == "REELS":
        success, err = check_media_status(creation_id, config)
        if not success:
            return False, err
            
    # 3. メディアの公開（パブリッシュ）
    publish_url = f"https://graph.facebook.com/{version}/{instagram_id}/media_publish"
    publish_params = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    
    print("[INFO] メディアを公開（投稿）しています...")
    pub_res = make_api_request(publish_url, publish_params, "POST")
    
    if "error" in pub_res:
        return False, f"公開に失敗しました: {pub_res['error'].get('message')}"
        
    posted_id = pub_res.get("id")
    print(f"[SUCCESS] Instagramへの投稿が完了しました！ 投稿ID: {posted_id}")
    return True, posted_id

def resolve_media_url(media_url):
    """メディアURLを解決する。ローカルパスの場合はGitHub PagesのURLに変換する。"""
    if media_url.startswith("http://") or media_url.startswith("https://"):
        return media_url
    
    # ローカルパス → GitHub Pages URL に変換
    if GITHUB_PAGES_BASE_URL and GITHUB_PAGES_BASE_URL != "https://tachikoma865.github.io/happyart":
        # カスタムURLが設定されている場合
        resolved = f"{GITHUB_PAGES_BASE_URL.rstrip('/')}/{media_url.lstrip('/')}"
        print(f"[INFO] ローカルパスを公開URLに変換しました: {media_url} → {resolved}")
        return resolved
    else:
        # デフォルトのGitHub Pages URLを使用
        resolved = f"{GITHUB_PAGES_BASE_URL.rstrip('/')}/{media_url.lstrip('/')}"
        print(f"[INFO] ローカルパスをGitHub Pages URLに変換しました: {media_url} → {resolved}")
        print(f"[WARN] GitHub Pages が有効化されていることを確認してください。")
        return resolved


def process_schedule(dry_run=False):
    """CSVから予定されている投稿をチェックし、実行する
    
    Args:
        dry_run: Trueの場合、実際のAPI呼び出しは行わず、投稿内容の確認のみ行う
    """
    config = load_config()
    
    if dry_run:
        print("=" * 60)
        print("🔍 DRY-RUN モード：実際の投稿は行いません")
        print("=" * 60)
    
    if not os.path.exists(SCHEDULE_FILE):
        # テンプレートCSVの作成
        headers = ["id", "post_time", "media_url", "media_type", "caption", "status", "posted_at", "instagram_post_id"]
        sample_row = [
            "1",
            "2026-07-21 20:00:00",
            "product_images/gold_front.png",
            "IMAGE",
            "【空間をパワースポットに変える、運命の光】\nGlint（輝き）＋ -ria（場所・国）を意味するアートブランド『GLINTRIA』始動。\n\n#スピリチュアル #波動 #引き寄せ",
            "pending",
            "",
            ""
        ]
        with open(SCHEDULE_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerow(sample_row)
        print(f"[INFO] '{SCHEDULE_FILE}' が見つかりません。サンプルレコードを含んだCSVを作成しました。")
        return

    # CSVの読み込みと更新準備
    rows = []
    headers = []
    updated = False
    now = datetime.now()

    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            rows.append(row)

    if not rows:
        print("[INFO] スケジュールCSVに投稿データがありません。")
        return

    pending_count = sum(1 for row in rows if row[5].lower() == "pending")
    print(f"[INFO] スケジュール読み込み完了: 全{len(rows)}件 / 保留中(pending): {pending_count}件")

    # 各行のチェック
    for i, row in enumerate(rows):
        # CSVのインデックス定義
        # ["id", "post_time", "media_url", "media_type", "caption", "status", "posted_at", "instagram_post_id"]
        row_id = row[0]
        post_time_str = row[1]
        media_url = row[2]
        media_type = row[3]
        caption = row[4]
        status = row[5]

        if status.lower() != "pending":
            continue

        try:
            post_time = datetime.strptime(post_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"[WARN] 行 ID {row_id} の日時フォーマットが不正です: {post_time_str}。'YYYY-MM-DD HH:MM:SS' で記載してください。")
            continue

        # 予定日時が現在時刻以前の場合、投稿処理を行う
        if post_time <= now:
            # メディアURLの解決（ローカルパス → 公開URL）
            resolved_url = resolve_media_url(media_url)
            
            if dry_run:
                # Dry-run モード：投稿内容を表示するだけ
                print(f"\n{'─' * 50}")
                print(f"📋 投稿ID: {row_id}")
                print(f"⏰ 予定時間: {post_time_str}")
                print(f"🖼  メディア種別: {media_type}")
                print(f"🔗 元のURL: {media_url}")
                print(f"🌐 解決後URL: {resolved_url}")
                print(f"📝 キャプション（冒頭100文字）:")
                print(f"   {caption[:100]}..." if len(caption) > 100 else f"   {caption}")
                print(f"{'─' * 50}")
                continue
            
            print(f"\n[EXEC] 投稿を実行します。ID: {row_id} | 予定時間: {post_time_str}")
            
            # 公開URLかチェック
            if not (resolved_url.startswith("http://") or resolved_url.startswith("https://")):
                print(f"[ERROR] 投稿失敗: メディアURL '{resolved_url}' は公開URLである必要があります。")
                rows[i][5] = "failed"
                rows[i][6] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows[i][7] = "error: could not resolve to public URL"
                updated = True
                continue

            success, result = post_to_instagram(resolved_url, caption, media_type, config)
            
            if success:
                rows[i][5] = "posted"
                rows[i][6] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows[i][7] = result
            else:
                rows[i][5] = "failed"
                rows[i][6] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows[i][7] = result
                
            updated = True
        else:
            if dry_run:
                # 未来の投稿も表示
                resolved_url = resolve_media_url(media_url)
                print(f"\n{'─' * 50}")
                print(f"📋 投稿ID: {row_id} ⏳ （未来の予約投稿）")
                print(f"⏰ 予定時間: {post_time_str}")
                print(f"🖼  メディア種別: {media_type}")
                print(f"🔗 元のURL: {media_url}")
                print(f"🌐 解決後URL: {resolved_url}")
                print(f"📝 キャプション（冒頭100文字）:")
                print(f"   {caption[:100]}..." if len(caption) > 100 else f"   {caption}")
                print(f"{'─' * 50}")

    # 変更があった場合はCSVを書き戻す（dry-runでは書き込まない）
    if updated and not dry_run:
        with open(SCHEDULE_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print("\n[INFO] 投稿処理が完了し、スケジュールシートを更新しました。")
    elif not dry_run:
        print("[INFO] 現在の時間に実行予定の保留中（pending）の投稿はありませんでした。")
    else:
        print(f"\n[INFO] DRY-RUN完了。上記の内容で投稿されます。")
        print(f"[INFO] 実際に投稿するには: python3 instagram_auto_poster.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instagram自動投稿スクリプト（GLINTRIA）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際の投稿は行わず、投稿内容の確認のみ行う"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="全スケジュール（未来の予約含む）をdry-runで一覧表示する"
    )
    args = parser.parse_args()
    
    if args.list:
        # --list の場合は全投稿をdry-runで表示
        process_schedule(dry_run=True)
    else:
        process_schedule(dry_run=args.dry_run)
