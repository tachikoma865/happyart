#!/bin/bash
# happyart 自動投稿ランナー
#
# cron / launchd から呼ばれることを想定した起動スクリプト。
# python3 の絶対パスをハードコードせず、実行時に自動検出する。
# （2026-07-22 以降、cron が /usr/local/bin/python3 を指していて全件失敗した対策）
#
# 使い方:
#   ./run_poster.sh              … Instagram のみ投稿
#   ./run_poster.sh --threads    … Threads にも投稿
#
# cron 登録例（毎日 21:05 に実行）:
#   5 21 * * * /Users/tachikoma/product/test/happyart/run_poster.sh >> /Users/tachikoma/product/test/happyart/auto_poster.log 2>&1

set -uo pipefail

# このスクリプトが置かれているディレクトリへ移動（cron は cwd が違うため必須）
cd "$(dirname "$0")" || exit 1

# cron の PATH は極端に短いので、python がありそうな場所を足す
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.pyenv/shims:$PATH"

# cron は「毎時05分」で回るため、ログが1日あたり24回分たまる。
# 放っておくと肥大するので、大きくなったら古い分を捨てる。
LOG_FILE="auto_poster.log"
MAX_LOG_LINES=3000
if [ -f "$LOG_FILE" ]; then
    lines=$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$lines" -gt "$MAX_LOG_LINES" ]; then
        tail -n 1500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
fi

# cron はローカル時刻で動くが、投稿予定は日本時間で書かれている。
# 追跡しやすいよう、ログには両方の時刻を出す。
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z') / JST $(TZ=Asia/Tokyo date '+%m-%d %H:%M')] $*"
}

# --- python3 を自動検出 ---
PY=""
for candidate in \
    "$(command -v python3 2>/dev/null)" \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python3 \
    "$HOME/.pyenv/shims/python3"
do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    log "ERROR: python3 が見つかりません。PATH=$PATH"
    exit 1
fi

log "python3 = $PY"

# --- Instagram 投稿 ---
log "--- Instagram 投稿を開始 ---"
"$PY" instagram_auto_poster.py
IG_STATUS=$?
log "Instagram 終了コード: $IG_STATUS"

# --- Threads 投稿（--threads 指定時のみ）---
THREADS_STATUS=0
if [ "${1:-}" = "--threads" ]; then
    if [ -f threads_auto_poster.py ]; then
        log "--- Threads 投稿を開始 ---"
        "$PY" threads_auto_poster.py
        THREADS_STATUS=$?
        log "Threads 終了コード: $THREADS_STATUS"
    else
        log "WARN: threads_auto_poster.py が見つかりません。スキップします"
    fi
fi

if [ $IG_STATUS -ne 0 ] || [ $THREADS_STATUS -ne 0 ]; then
    exit 1
fi

log "--- 正常終了 ---"
exit 0
