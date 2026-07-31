#!/usr/bin/env python3
"""
スケジュールを draft → pending に切り替えるスクリプト

いきなり pending にすると、画像URLが公開されていない状態で投稿が走り、
「local path not allowed」や404で全件失敗する事故が起きる。

そこでこのスクリプトは、
  1. CSVの全 media_url に実際にアクセスして、画像が公開されているか確認する
  2. 全部OKだったときだけ draft → pending に書き換える
という順番にしている。1件でも失敗したら何も変更しない。

使い方:
    python3 activate_schedule.py           # 確認のみ（変更しない）
    python3 activate_schedule.py --apply   # 確認して、全部OKなら pending に切り替える
"""

import csv
import sys
import urllib.request
import urllib.error

CSV_FILE = "posts_schedule.csv"
TIMEOUT = 15


def check_url(url):
    """
    メディアが公開URLとして取得できるか確認する。

    画像だけでなく動画（リール）も扱うため、image/ と video/ の両方を通す。
    ここを image/ だけにしていると、リールの投稿が必ず失敗する。
    """
    if not url.startswith(("http://", "https://")):
        return False, "公開URLではありません（ローカルパスは投稿できません）"
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "happyart-checker"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            ctype = res.headers.get("Content-Type", "")
            if res.status != 200:
                return False, f"HTTP {res.status}"
            if not ctype.startswith(("image/", "video/")):
                return False, f"画像でも動画でもありません（Content-Type: {ctype}）"
            return True, ctype
    except urllib.error.HTTPError as e:
        hint = "（GitHub Pagesがまだ有効化されていない可能性があります）" if e.code == 404 else ""
        return False, f"HTTP {e.code} {hint}"
    except Exception as e:
        return False, str(e)


def main():
    apply_changes = "--apply" in sys.argv

    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)

    targets = [r for r in rows if r["status"].lower() == "draft"]
    if not targets:
        print("[INFO] draft の行がありません。すでに切り替え済みかもしれません。")
        return

    print(f"{len(targets)} 件の画像URLを確認します...\n")

    ok_count = 0
    failures = []
    for r in targets:
        ok, detail = check_url(r["media_url"])
        mark = "OK " if ok else "NG "
        print(f"  [{mark}] {r['post_time'][:10]}  {r['media_url'].split('/')[-1]}"
              + ("" if ok else f"  ← {detail}"))
        if ok:
            ok_count += 1
        else:
            failures.append((r["id"], r["media_url"], detail))

    print(f"\n結果: {ok_count} / {len(targets)} 件が公開済み")

    if failures:
        print("\n[中止] 公開されていない画像があるため、何も変更しませんでした。")
        print("次を確認してください。")
        print("  1. git push が完了しているか")
        print("  2. GitHubのSettings → Pages が有効になっているか")
        print("  3. 有効化から数分待ったか（反映に時間がかかります）")
        sys.exit(1)

    if not apply_changes:
        print("\n全件OKです。切り替えるには次を実行してください:")
        print("    python3 activate_schedule.py --apply")
        return

    for r in rows:
        if r["status"].lower() == "draft":
            r["status"] = "pending"

    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)

    print(f"\n[完了] {len(targets)} 件を pending に切り替えました。")
    print("次は cron の設定です（STATUS.md の「復旧手順」を参照）。")


if __name__ == "__main__":
    main()
