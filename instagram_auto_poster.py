#!/usr/bin/env python3
import os
import sys
import csv
import json
import time
import argparse
from datetime import datetime, timezone, timedelta
import urllib.request
import urllib.parse
import urllib.error

import ssl

# 設定ファイルのパス
CONFIG_FILE = "config.json"
SCHEDULE_FILE = "posts_schedule.csv"

# SSL証明書検証をバイパスするコンテキスト
SSL_CONTEXT = ssl._create_unverified_context()

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
        with urllib.request.urlopen(req, context=SSL_CONTEXT) as response:
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

def post_to_instagram(media_url, caption, media_type, config, dry_run=False):
    """
    Instagramに画像または動画を投稿するフローを実行する。

    dry_run=True のときは「メディアコンテナの作成」までで止める。
    コンテナ作成の時点で、
      ・アクセストークンと権限が有効か
      ・画像URLにMeta側から到達できるか
      ・キャプションが受け付けられるか
    がすべて検証されるため、実際に投稿せずに設定を確認できる。
    作られたコンテナは公開しなければ24時間で自動的に消える。
    """
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

    # dry-run はここで終了。公開はしない。
    if dry_run:
        print("[DRY-RUN] 検証はここまでです。公開（media_publish）は行いません。")
        return True, f"dry-run OK (container: {creation_id})"

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


# ロックファイルのパス
LOCK_FILE = "poster.lock"

# 1回の実行で投稿する最大件数
#
# Mac がスリープしていた等で cron が飛ぶと、期限切れの pending が複数溜まる。
# その状態で次に起動すると、溜まった分が一気に連続投稿されてしまう。
# （1日1本のはずが、21:05 に3本まとめて出るような事故になる）
# そこで1回の実行につき1件までに制限する。取りこぼした分は翌日以降に順に消化される。
MAX_POSTS_PER_RUN = 1

# ロックがこの秒数より長く残っていたら、異常として解除する（30分）
LOCK_MAX_AGE_SEC = 30 * 60

def _clear_stale_lock():
    """
    置き去りになったロックファイルを片付ける。

    スクリプトが強制終了（Macのスリープ、再起動、Ctrl-C、タイムアウト）で
    落ちると poster.lock が残る。そのままだと以後の実行が毎回スキップされ、
    投稿が静かに止まり続ける。実際に長期間投稿が止まる事故が起きている。

    そこで「中のPIDのプロセスが生きているか」と「作られてから経った時間」を見て、
    実行中でないと判断できる場合はロックを解除する。

    戻り値: True=ロックを解除した（処理を続けてよい） / False=本当に実行中
    """
    try:
        with open(LOCK_FILE) as f:
            pid = int(f.read().strip())
    except (ValueError, OSError):
        print("[INFO] 壊れたロックファイルを削除しました。")
        _remove_lock()
        return True

    # そのPIDのプロセスが生きているか確認する
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    except PermissionError:
        alive = True  # 別ユーザーのプロセス。生きているとみなす
    except OSError:
        alive = False

    if not alive:
        print(f"[INFO] 前回の実行(PID {pid})は残っていません。古いロックを削除して続行します。")
        _remove_lock()
        return True

    # 生きているが、あまりに長時間残っている場合は異常とみなす
    try:
        age = time.time() - os.path.getmtime(LOCK_FILE)
    except OSError:
        age = 0
    if age > LOCK_MAX_AGE_SEC:
        print(f"[WARN] ロックが {int(age / 60)} 分残っています。異常とみなして解除します。")
        _remove_lock()
        return True

    return False


def _remove_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def process_schedule(dry_run=False):
    """CSVから予定されている投稿をチェックし、実行する

    Args:
        dry_run: Trueの場合、実際のAPI呼び出しは行わず、投稿内容の確認のみ行う
    """
    if not dry_run:
        if os.path.exists(LOCK_FILE) and not _clear_stale_lock():
            print("[WARN] 他の投稿プロセスが実行中です。重複防止のため終了します。")
            return
        # ロックファイルを作成
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))

    try:
        _process_schedule_internal(dry_run)
    finally:
        if not dry_run and os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

def _process_schedule_internal(dry_run=False):
    config = load_config()
    
    if dry_run:
        print("=" * 60)
        print("🔍 DRY-RUN モード：実際の投稿は行いません")
        print("=" * 60)
    
    if not os.path.exists(SCHEDULE_FILE):
        # テンプレートCSVの作成
        headers = ["id", "post_time", "media_url", "media_type", "caption", "status", "posted_at", "instagram_post_id"]
        # 注意：ここは status を "draft" にしておくこと。
        # "pending" かつ過去日時にすると、CSVが無い状態でスクリプトを走らせた瞬間に
        # このサンプルが本番投稿されてしまう（過去に実際に起きた事故）。
        sample_row = [
            "1",
            "2099-01-01 21:00:00",
            "https://example.com/replace-me.png",
            "IMAGE",
            "サンプル行です。build_august.py で本番用のCSVを生成してください。",
            "draft",
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
    # 日本時間(JST)の現在時刻を取得
    JST = timezone(timedelta(hours=+9), 'JST')
    now = datetime.now(JST).replace(tzinfo=None)

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

    posted_this_run = 0

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
            
            # 1回の実行で投稿しすぎないようにする（連続投稿の事故防止）
            # 成功だけでなく「試行」を数える。失敗を数えないと、
            # 通信断のときに全件を試して全部 failed にしてしまう。
            if posted_this_run >= MAX_POSTS_PER_RUN:
                print(f"[INFO] ID {row_id} は今回は見送ります"
                      f"（1回の実行につき{MAX_POSTS_PER_RUN}件まで。次回の実行で投稿されます）")
                continue
            posted_this_run += 1

            print(f"\n[EXEC] 投稿を実行します。ID: {row_id} | 予定時間: {post_time_str}")
            
            # 公開URLかチェック
            if not (resolved_url.startswith("http://") or resolved_url.startswith("https://")):
                print(f"[ERROR] 投稿失敗: メディアURL '{resolved_url}' は公開URLである必要があります。")
                rows[i][5] = "failed"
                rows[i][6] = now.strftime("%Y-%m-%d %H:%M:%S")
                rows[i][7] = "error: could not resolve to public URL"
                updated = True
                continue

            success, result = post_to_instagram(resolved_url, caption, media_type, config)
            
            if success:
                rows[i][5] = "posted"
                rows[i][6] = now.strftime("%Y-%m-%d %H:%M:%S")
                rows[i][7] = result
                updated = True
            else:
                rows[i][5] = "failed"
                rows[i][6] = now.strftime("%Y-%m-%d %H:%M:%S")
                rows[i][7] = result
                updated = True
                # 1件失敗した時点で、この回は打ち切る。
                # 失敗の原因はトークン切れや通信断であることが多く、
                # そのまま続けると残り全部を failed にして予定表を壊してしまう。
                print("[WARN] 投稿に失敗したため、今回の実行はここで終了します。")
                print("       原因を確認してから、該当行の status を pending に戻してください。")
                break
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


def verify_schedule(limit=1):
    """
    実際のAPIを使った事前検証（投稿はしない）。

    --dry-run は内容を表示するだけでAPIに触れないため、
    「Metaが画像URLを取得できるか」「権限が足りているか」は分からない。

    そこでこのモードでは、メディアコンテナの作成までを本番同様に実行する。
    コンテナ作成が通れば、
      ・トークンと権限が有効
      ・Meta側から画像URLに到達できる
      ・キャプションが受理される
    ことが確認できる。公開しないコンテナは24時間で自動的に消える。
    """
    config = load_config()

    if not os.path.exists(SCHEDULE_FILE):
        print(f"[ERROR] '{SCHEDULE_FILE}' がありません。")
        return

    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        rows = [r for r in reader]

    targets = [r for r in rows if r[5].lower() == "pending"][:limit]
    if not targets:
        print("[INFO] pending の投稿がありません。")
        return

    print("=" * 60)
    print(f" 事前検証モード：{len(targets)}件をAPIで検証します（投稿はしません）")
    print("=" * 60)

    ng = 0
    for row in targets:
        row_id, post_time_str, media_url, media_type, caption = row[0], row[1], row[2], row[3], row[4]
        resolved = resolve_media_url(media_url)
        print(f"\n--- ID {row_id}（予定 {post_time_str}）---")

        success, result = post_to_instagram(resolved, caption, media_type, config, dry_run=True)
        if success:
            print(f"[OK] 検証成功: {result}")
        else:
            print(f"[NG] {result}")
            ng += 1

    print("\n" + "=" * 60)
    if ng == 0:
        print(f" 結果: {len(targets)}件すべて検証OK。本番投稿できる状態です。")
        print(" ※ 作成したコンテナは公開していないので、24時間で自動的に消えます。")
    else:
        print(f" 結果: {ng}件で問題がありました。上記の[NG]を確認してください。")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instagram自動投稿スクリプト（GLINTRIA）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際の投稿は行わず、投稿内容の確認のみ行う（APIには接続しない）"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="全スケジュール（未来の予約含む）をdry-runで一覧表示する"
    )
    parser.add_argument(
        "--verify",
        nargs="?", const=1, type=int, metavar="N",
        help="APIで実際に検証する（投稿はしない）。先頭N件。既定は1件"
    )
    args = parser.parse_args()

    if args.verify:
        verify_schedule(limit=args.verify)
    elif args.list:
        # --list の場合は全投稿をdry-runで表示
        process_schedule(dry_run=True)
    else:
        process_schedule(dry_run=args.dry_run)
