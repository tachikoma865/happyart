#!/usr/bin/env python3
"""
投稿の公開をひとまとめにするスクリプト

これまで手作業で3つに分かれていた手順を1コマンドにまとめたもの。
1つでも飛ばすと投稿されないまま静かに止まるため、まとめて実行する。

  1. 変更を git にコミットして push する（＝画像をGitHub Pagesで公開する）
  2. 公開が反映されるまで待って、画像URLに実際にアクセスできるか確認する
  3. 全部OKだったときだけ、CSVの draft を pending に切り替える

3の前に必ず2を通すので、画像が無いまま投稿が走って全件 failed になる事故は起きない。

使い方:
    python3 publish.py            # コミット→push→確認→有効化
    python3 publish.py --build    # 先に build_august.py で作り直してから実行
    python3 publish.py --check    # 確認だけ（push も切り替えもしない）
"""

import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

from activate_schedule import check_url, CSV_FILE

JST = timezone(timedelta(hours=9))

WAIT_TOTAL_SEC = 420      # GitHub Pages の反映を待つ上限（7分）
WAIT_INTERVAL_SEC = 20


def run(cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"[ERROR] コマンドが失敗しました: {' '.join(cmd)}")
        print((r.stderr or r.stdout).strip())
        sys.exit(1)
    return r


def step_build():
    print("■ 投稿データを作り直します")
    r = subprocess.run([sys.executable, "build_august.py"], text=True)
    if r.returncode != 0:
        print("[ERROR] build_august.py が失敗しました。")
        sys.exit(1)
    print()


def load_rows():
    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def step_push():
    print("■ 変更を GitHub に反映します")

    status = run(["git", "status", "--porcelain"]).stdout.strip()
    if not status:
        print("  変更はありません。すでに反映済みのようです。")
    else:
        n = len(status.splitlines())
        print(f"  {n} 件の変更をコミットします")
        run(["git", "add", "-A"])
        stamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
        run(["git", "commit", "-m", f"投稿と画像を更新 ({stamp} JST)"])

    print("  push しています...")
    r = run(["git", "push", "origin", "main"], check=False)
    if r.returncode != 0:
        print("[ERROR] push に失敗しました。")
        print((r.stderr or r.stdout).strip())
        print()
        print("  よくある原因:")
        print("   ・GitHubの認証が切れている")
        print("   ・ネットワークにつながっていない")
        print("   ・リモートに新しいコミットがある（先に git pull が必要）")
        sys.exit(1)
    print("  push しました。")
    print()


def step_wait_and_check(rows, wait=True):
    targets = [r for r in rows if r["status"].lower() == "draft"]
    if not targets:
        print("■ draft の投稿はありません（すでに有効化済みです）")
        return []

    print(f"■ 画像が公開されたか確認します（{len(targets)}件）")
    if wait:
        print("  GitHub Pages への反映には数分かかることがあります。")

    deadline = time.time() + (WAIT_TOTAL_SEC if wait else 0)
    while True:
        failures = []
        for r in targets:
            ok, detail = check_url(r["media_url"])
            if not ok:
                failures.append((r, detail))

        if not failures:
            print(f"  すべて公開を確認しました（{len(targets)}件）")
            print()
            return targets

        if time.time() >= deadline:
            print(f"\n[中止] {len(failures)}件の画像がまだ公開されていません。")
            for r, detail in failures[:5]:
                print(f"   ・{r['media_url'].rsplit('/', 1)[-1]} … {detail}")
            print()
            print("  対処:")
            print("   ・数分おいてから、もう一度 python3 publish.py を実行する")
            print("   ・GitHubのSettings→Pagesが有効になっているか確認する")
            print("  ※ CSVは変更していないので、そのまま再実行して大丈夫です。")
            sys.exit(1)

        remain = int(deadline - time.time())
        print(f"  未反映 {len(failures)}件。{WAIT_INTERVAL_SEC}秒待ちます（残り約{remain}秒）")
        time.sleep(WAIT_INTERVAL_SEC)


def step_activate(headers, rows, targets):
    for r in rows:
        if r["status"].lower() == "draft":
            r["status"] = "pending"

    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)

    print(f"■ {len(targets)}件を pending に切り替えました")
    for r in targets:
        print(f"   {r['post_time']}  {r['media_url'].rsplit('/', 1)[-1]}")
    print()


def show_next(rows):
    now = datetime.now(JST).replace(tzinfo=None)
    upcoming = []
    for r in rows:
        if r["status"].lower() != "pending":
            continue
        try:
            t = datetime.strptime(r["post_time"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if t >= now:
            upcoming.append((t, r))
    upcoming.sort()

    print("■ 次に投稿されるもの")
    if not upcoming:
        print("  予定されている投稿はありません。")
        return
    for t, r in upcoming[:3]:
        h = (t - now).total_seconds() / 3600
        print(f"   {t:%m/%d %H:%M} JST（あと{h:.1f}時間） {r['media_url'].rsplit('/', 1)[-1]}")
    print()
    print("  cron は毎時05分に巡回します。予定時刻を過ぎた最初の巡回で投稿されます。")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    check_only = "--check" in sys.argv

    print("=" * 58)
    print(f" 投稿の公開  {datetime.now(JST):%Y-%m-%d %H:%M} JST")
    print("=" * 58)
    print()

    if "--build" in sys.argv:
        step_build()

    if not check_only:
        step_push()

    headers, rows = load_rows()
    targets = step_wait_and_check(rows, wait=not check_only)

    if check_only:
        print("■ 確認のみのため、CSVは変更していません")
        print()
    elif targets:
        step_activate(headers, rows, targets)
        headers, rows = load_rows()

    show_next(rows)
    print()
    print("=" * 58)
    print(" 完了")
    print("=" * 58)


if __name__ == "__main__":
    main()
