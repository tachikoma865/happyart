#!/usr/bin/env python3
"""
8月の選択占いをリール動画に変換する

静止画のフィード投稿はフォロワー0だと配信先が無く、ほぼ誰にも届かない。
新規リーチはリールがほぼ全部を占めるため、主力である選択占いだけを動画にする。
暦や実用テクは「保存」目的なので静止画のままで機能する。

各リールの台本は、対応する投稿のキャプションから要点を抜き出したもの。
テロップは1画面2行まで、1行10文字前後に収めている。

出力: reels_output/aug/*.mp4（1080×1920 / 30秒 / BGM付き）

使い方:
    python3 build_reels.py           # 未作成のぶんだけ作る
    python3 build_reels.py --force   # 全部作り直す
"""

import os
import subprocess
import sys
import time

from generate_choice_reel import make_reel

OUT_DIR = "reels_output/aug"
EXPECTED_SEC = 30.0


def is_valid(path, tolerance=1.0):
    """
    出来上がった動画がちゃんと再生できる長さになっているか確認する。

    生成が途中で止まると、再生できない壊れたファイルが残る。
    「ファイルが存在する＝完成」で判定すると、それを完成扱いして素通りし、
    壊れた動画がそのまま投稿されてしまう。長さまで見て判定する。
    """
    if not os.path.exists(path) or os.path.getsize(path) < 100_000:
        return False
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not r.stdout.strip():
            return False
        return abs(float(r.stdout.strip()) - EXPECTED_SEC) < tolerance
    except Exception:
        return False

# ファイル名 → (フック, [(金の見出し, 金の補足), (青…), (桃…)])
# フックは冒頭3秒。ここで「私のことだ」と思わせられるかがすべて。
REEL_TEXTS = {
    "01_choice": (
        ["直感で選んだ色で", "いまがわかります"],
        [(["外に向かうとき"], ["やってみる側に", "倒していい時期"]),
         (["休みたいとき"], ["予定を詰めるより", "余白をつくる"]),
         (["人が近づくとき"], ["浮かんだ人が", "いませんか"])],
    ),
    "07_choice": (
        ["なんとなく", "疲れている人へ"],
        [(["答えは出ている"], ["足りないのは", "始める合図だけ"]),
         (["休みが後回し"], ["今週は予定を", "ひとつ減らして"]),
         (["気を遣いすぎ"], ["断ってもいい", "場面があります"])],
    ),
    "12_choice": (
        ["この投稿が", "流れてきた人へ"],
        [(["比べてしまう"], ["比べる相手を", "減らすと進む"]),
         (["考えすぎている"], ["情報を集める段階は", "もう終わり"]),
         (["伝えそびれた"], ["明日でもいいけど", "今日のほうが軽い"])],
    ),
    "16_choice": (
        ["今月、迷って", "いる人へ"],
        [(["もう決まっている"], ["迷いではなく", "動いていないだけ"]),
         (["選べない"], ["条件を1つ捨てると", "急に決まる"]),
         (["人の意見が気になる"], ["相談相手を", "1人に絞って"])],
    ),
    "21_choice": (
        ["考えないで", "選んでください"],
        [(["自分で決めたい"], ["人に合わせる場面を", "ひとつ減らす"]),
         (["静けさが足りない"], ["音を消す時間を", "10分だけ"]),
         (["待っている"], ["こちらから出すほうが", "たぶん早い"])],
    ),
    "24_choice": (
        ["8月も", "残り1週間"],
        [(["数えるなら"], ["やり残しより", "やれたことを"]),
         (["整理するとき"], ["9月が楽になる", "片づけをひとつ"]),
         (["会えなかった人"], ["顔が浮かんだなら", "それがきっかけ"])],
    ),
    "27_choice": (
        ["明日は", "満月です"],
        [(["続けるものを"], ["手放すより", "決めるほうが向く"]),
         (["予定を手放す"], ["ものより先に", "減らすのは予定"]),
         (["距離を変える"], ["気を遣う相手と", "少しだけ"])],
    ),
}


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)

    items = list(REEL_TEXTS.items())
    print(f"選択占いのリールを作ります（{len(items)}本）")
    print()

    made = 0
    for i, (name, (hook, results)) in enumerate(items):
        out = f"{OUT_DIR}/{name}.mp4"
        if is_valid(out) and not force:
            print(f"  [skip] {name}.mp4（作成済み・検証OK）")
            continue

        t0 = time.time()
        print(f"  [{i + 1}/{len(items)}] {name}.mp4 を作成中...", flush=True)
        try:
            # seed と BGM を1本ずつずらして、模様と曲が毎回変わるようにする
            _, bgm, sec = make_reel(out, hook=hook, results=results,
                                    seed=11 + i * 23, bgm_index=i)
        except RuntimeError as e:
            print(f"        [ERROR] {e}")
            sys.exit(1)
        mb = os.path.getsize(out) / 1024 / 1024
        print(f"        完了 {sec:.0f}秒 / {mb:.1f}MB / BGM {os.path.basename(bgm)}"
              f" （{time.time() - t0:.0f}秒かかりました）")
        made += 1

    print()
    print(f"作成: {made}本 / 合計 {len(items)}本")
    print(f"出力先: {OUT_DIR}/")
    print()
    print("次は build_august.py を実行して、CSVの media_type を REELS に切り替えてください。")


if __name__ == "__main__":
    main()
