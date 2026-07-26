#!/usr/bin/env python3
"""未投稿（pending）の投稿日時を、今日以降に振り直すユーティリティ。

自動投稿が止まっていた期間の pending が溜まっていると、
復旧した瞬間に何件も連続投稿されてしまう（アカウントの評価的にも良くない）。
このスクリプトで、pending を「明日から1日1件」に並べ直す。

使い方:
    python3 reschedule_pending.py --dry-run          # 変更内容の確認だけ
    python3 reschedule_pending.py                    # 明日から 21:00 に1日1件で振り直す
    python3 reschedule_pending.py --start 2026-07-28 --time 21:00 --interval 1
"""

import csv
import argparse
from datetime import datetime, timedelta, timezone

SCHEDULE_FILE = "posts_schedule.csv"
JST = timezone(timedelta(hours=9))


def main():
    p = argparse.ArgumentParser(description="pending の投稿日時を振り直す")
    p.add_argument("--start", help="開始日 YYYY-MM-DD（既定: 明日）")
    p.add_argument("--time", default="21:00", help="投稿時刻 HH:MM（既定: 21:00）")
    p.add_argument("--interval", type=int, default=1, help="何日おきか（既定: 1）")
    p.add_argument("--column", default="status",
                   help="見る status 列名（既定: status。Threads は threads_status）")
    p.add_argument("--dry-run", action="store_true", help="書き込まず表示のみ")
    a = p.parse_args()

    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = [r for r in reader]

    if a.column not in headers:
        print(f"ERROR: 列 '{a.column}' が CSV にありません。ある列: {headers}")
        return

    i_status = headers.index(a.column)
    i_time = headers.index("post_time")

    if a.start:
        start = datetime.strptime(a.start, "%Y-%m-%d")
    else:
        start = datetime.now(JST).replace(tzinfo=None) + timedelta(days=1)

    hh, mm = (int(x) for x in a.time.split(":"))
    start = start.replace(hour=hh, minute=mm, second=0, microsecond=0)

    targets = [r for r in rows if len(r) > i_status and r[i_status].lower() == "pending"]
    if not targets:
        print(f"pending の行がありません（列: {a.column}）。")
        return

    print(f"{len(targets)} 件を {start.strftime('%Y-%m-%d %H:%M')} から {a.interval} 日おきに振り直します。\n")

    for n, row in enumerate(targets):
        new_time = start + timedelta(days=n * a.interval)
        print(f"  {row[0]:<14} {row[i_time]}  →  {new_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if not a.dry_run:
            row[i_time] = new_time.strftime("%Y-%m-%d %H:%M:%S")

    if a.dry_run:
        print("\n[DRY-RUN] 書き込みは行っていません。実行するには --dry-run を外してください。")
        return

    with open(SCHEDULE_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"\n{SCHEDULE_FILE} を更新しました。")


if __name__ == "__main__":
    main()
