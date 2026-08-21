#!/usr/bin/env python3
"""
選択占いのリール動画を生成する

既存の generate_reel.py は「1枚の画像にズームとBGMを付ける」だけで、
場面が切り替わって文字が変わる選択占いには使えないため、別に用意した。

構成（リサーチで作った台本に沿う）:
  0〜3秒    フック。「私のことだ」と思わせる一行
  3〜9.5秒  3色を提示して選ばせる
  9.5〜12秒 「選びましたか？」の間  ← ここで視聴時間が伸びる
  12〜27秒  各色の結果を5秒ずつ
  27〜30秒  コメント誘導とLINE導線

テロップの制約（リサーチ準拠）:
  1画面あたり最大3行、理想は1〜2行。1行は10文字程度。

出力:
  reels_output/choice_reel.mp4   1080×1920（9:16）／約30秒／BGM付き

使い方:
    python3 generate_choice_reel.py
    python3 generate_choice_reel.py --fps 24 --out reels_output/test.mp4
"""

import argparse
import glob
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter

from generate_post_images import fluid_background, PALETTES, load_font

W, H = 1080, 1920
OVER = 1.12                      # ゆっくりズームさせるための余白
BG = (252, 250, 246)
INK = (46, 40, 34)
SUB = (132, 124, 114)
GOLD = (198, 156, 74)

OUT_DEFAULT = "reels_output/choice_reel.mp4"
BGM_DIR = "bgm"


# ---------------------------------------------------------------
# 画面の部品
# ---------------------------------------------------------------


def soft_fluid(color, seed, size, blur=0):
    """
    背景用のフルイドを作る。

    半分の解像度で生成してから拡大している。どのみち白を重ねたりぼかしたりして
    背景として沈めるので、見た目はほとんど変わらないのに生成が4倍近く速くなる。
    リールは1本あたり8場面あるため、ここの速度が全体を左右する。
    """
    small = fluid_background(PALETTES[color]["colors"], seed=seed, size=max(2, size // 2))
    img = small.resize((size, size), Image.LANCZOS)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img


def canvas():
    return Image.new("RGB", (int(W * OVER), int(H * OVER)), BG)


def center_text(img, lines, y, size, serif=True, fill=INK, gap=1.35):
    """複数行を中央揃えで置く。y はブロックの上端"""
    d = ImageDraw.Draw(img)
    f = load_font(size, serif=serif)
    cw = img.size[0]
    for i, line in enumerate(lines):
        bbox = d.textbbox((0, 0), line, font=f)
        x = (cw - (bbox[2] - bbox[0])) / 2 - bbox[0]
        d.text((x, y + i * size * gap), line, font=f, fill=fill)
    return y + len(lines) * size * gap


def scene_text(lines, sub_lines=None, size=96, color=None, seed=3):
    """淡い背景に文字だけ置く場面"""
    img = canvas()
    if color:
        bg = soft_fluid(color, seed, max(img.size), blur=22).resize(img.size, Image.LANCZOS)
        img = Image.blend(bg, Image.new("RGB", img.size, (255, 255, 255)), 0.45)

    total = len(lines) * size * 1.35 + (len(sub_lines) * 56 * 1.5 if sub_lines else 0)
    y = (img.size[1] - total) / 2
    y = center_text(img, lines, y, size)
    if sub_lines:
        center_text(img, sub_lines, y + 46, 56, serif=False, fill=SUB)
    return img


def scene_choices(seed=11, show_numbers=True):
    """3色を横に並べて選ばせる場面"""
    img = canvas()
    cw, ch = img.size

    center_text(img, ["直感で選んでください"], ch * 0.20, 82)
    center_text(img, ["考えないで、目が留まった色を"], ch * 0.20 + 128, 48,
                serif=False, fill=SUB)

    # リールの核心はここなので、3色をできるだけ大きく見せる。
    # 下端はコメント欄やボタンで隠れるため、中央やや上に置く。
    pw, gap = 342, 28
    total = pw * 3 + gap * 2
    left = (cw - total) / 2
    top = int(ch * 0.33)
    ph = 640

    d = ImageDraw.Draw(img)
    for i, key in enumerate(["gold", "blue", "pink"]):
        p = PALETTES[key]
        tile = fluid_background(p["colors"], seed=seed + i * 17, size=pw)
        tile = tile.resize((pw, ph), Image.LANCZOS)
        x = int(left + i * (pw + gap))
        img.paste(tile, (x, top))
        d.rectangle([x, top, x + pw, top + ph], outline=(228, 220, 208), width=2)

        if show_numbers:
            f = load_font(88, serif=True)
            bbox = d.textbbox((0, 0), str(i + 1), font=f)
            d.text((x + pw / 2 - (bbox[2] - bbox[0]) / 2, top + ph + 26),
                   str(i + 1), font=f, fill=INK)
            f2 = load_font(46, serif=True)
            bbox = d.textbbox((0, 0), p["label"], font=f2)
            d.text((x + pw / 2 - (bbox[2] - bbox[0]) / 2, top + ph + 132),
                   p["label"], font=f2, fill=SUB)
    return img


def scene_result(key, number, headline, body):
    """1色ぶんの結果を出す場面"""
    p = PALETTES[key]
    img = canvas()
    bg = soft_fluid(key, 200 + number * 29, max(img.size)).resize(img.size, Image.LANCZOS)
    img = Image.blend(bg, Image.new("RGB", img.size, (255, 255, 255)), 0.30)

    cw, ch = img.size
    d = ImageDraw.Draw(img)

    # 上部に番号と色名
    f = load_font(150, serif=True)
    label = f"{number}・{p['label']}"
    bbox = d.textbbox((0, 0), label, font=f)
    d.text(((cw - (bbox[2] - bbox[0])) / 2 - bbox[0], ch * 0.16), label,
           font=f, fill=p["ink"])

    y = ch * 0.42
    y = center_text(img, headline, y, 86, fill=p["ink"])
    center_text(img, body, y + 54, 52, serif=False, fill=(92, 84, 78))
    return img


# ---------------------------------------------------------------
# 場面の定義（台本）
# ---------------------------------------------------------------

def scene_point(lines, sub_lines=None, color="gold", seed=5, index=None):
    """
    情報系リールの1ポイント分。淡い色地に見出しと補足を置く。
    左上に小さく番号を出して、いま何番目かが分かるようにする。
    """
    img = canvas()
    bg = soft_fluid(color, seed, max(img.size), blur=20).resize(img.size, Image.LANCZOS)
    img = Image.blend(bg, Image.new("RGB", img.size, (255, 255, 255)), 0.40)

    cw, ch = img.size
    if index is not None:
        d = ImageDraw.Draw(img)
        f = load_font(52, serif=True)
        d.text((cw * 0.10, ch * 0.16), f"{index}", font=f, fill=GOLD)

    total = len(lines) * 88 * 1.35 + (len(sub_lines) * 52 * 1.5 if sub_lines else 0)
    y = (ch - total) / 2
    y = center_text(img, lines, y, 88, fill=PALETTES[color]["ink"])
    if sub_lines:
        center_text(img, sub_lines, y + 44, 52, serif=False, fill=(92, 84, 78))
    return img


def build_info_scenes(title, points, color="gold", seed=5, cta=None):
    """
    暦・実用テク・色の話などの情報系リールを組み立てる（約13秒）。

    尺を短くしているのは、フォロワーが少ない段階では7〜15秒が
    もっともループ視聴されやすく、視聴完了率がリーチに直結するため。
    30秒だと最後まで見られず、フォロワー外に推薦されにくい。
    """
    cta = cta or ["保存して使ってください"]
    scenes = [(2.0, scene_text(title, size=94, color=color, seed=seed))]
    for i, (head, body) in enumerate(points, start=1):
        scenes.append((2.8, scene_point(head, body, color=color,
                                        seed=seed + i * 13, index=i)))
    scenes.append((2.0, scene_text(cta,
                                   ["詳しくはプロフィールのLINEから"],
                                   size=80, color=color, seed=seed + 99)))
    return scenes


DEFAULT_HOOK = ["この投稿が", "流れてきた人へ"]
DEFAULT_RESULTS = [
    (["外に出るとき"], ["やってみる側に", "倒していい時期"]),
    (["整えるとき"], ["予定をひとつ", "減らしてみて"]),
    (["人が動くとき"], ["浮かんだ人に", "連絡してみて"]),
]


def build_scenes(hook=None, results=None, seed=11):
    """
    台本から場面を組み立てる。

    hook    : 冒頭3秒に出す1〜2行
    results : 金・青・桃それぞれの (見出し行, 補足行) を3つ
    """
    hook = hook or DEFAULT_HOOK
    results = results or DEFAULT_RESULTS
    keys = ["gold", "blue", "pink"]

    # 合計およそ15秒。30秒版は最後まで見られず、フォロワー外に推薦されなかった。
    # 冒頭は短く切って、すぐ3色を見せる。
    scenes = [
        (1.8, scene_text(hook, size=100)),
        (2.2, scene_choices(seed=seed, show_numbers=False)),
        (2.2, scene_choices(seed=seed, show_numbers=True)),
        (1.3, scene_text(["選びましたか？"], size=104, color="gold", seed=seed + 5)),
    ]
    for i, (head, body) in enumerate(results):
        scenes.append((2.2, scene_result(keys[i], i + 1, head, body)))
    scenes.append(
        (1.5, scene_text(["何番でしたか？"],
                         ["コメントで教えてください",
                          "詳しくはプロフィールのLINEから"], size=92)))
    return scenes


def make_reel(out, hook=None, results=None, seed=11, fps=20, bgm_index=None):
    """1本ぶんのリールを書き出す。他のスクリプトから呼ぶ用。"""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg が見つかりません")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    scenes = build_scenes(hook, results, seed)
    bgm = pick_bgm(bgm_index)
    work = tempfile.mkdtemp()
    try:
        cmd = build_ffmpeg_cmd(scenes, work, fps, out, bgm)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-1200:])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out, bgm, sum(d for d, _ in scenes)


def make_info_reel(out, title, points, color="gold", seed=5, cta=None,
                   fps=20, bgm_index=None):
    """情報系（暦・実用テク・色）のリールを1本書き出す。"""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg が見つかりません")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    scenes = build_info_scenes(title, points, color=color, seed=seed, cta=cta)
    bgm = pick_bgm(bgm_index)
    work = tempfile.mkdtemp()
    try:
        cmd = build_ffmpeg_cmd(scenes, work, fps, out, bgm)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-1200:])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out, bgm, sum(d for d, _ in scenes)


# ---------------------------------------------------------------
# 動画に書き出す
# ---------------------------------------------------------------

def build_ffmpeg_cmd(scenes, workdir, fps, out, bgm):
    """
    場面ごとに静止画を1枚ずつ渡し、ズームと連結は ffmpeg にやらせる。

    最初はPILで全フレームを書き出していたが、1080×1920を600枚リサイズすると
    非常に遅い。ffmpeg の zoompan なら同じ絵が桁違いに速く作れる。
    """
    paths = []
    for i, (dur, img) in enumerate(scenes):
        p = os.path.join(workdir, f"s{i:02d}.png")
        img.save(p)
        paths.append((dur, p))

    cmd = ["ffmpeg", "-y"]
    for dur, p in paths:
        cmd += ["-loop", "1", "-t", f"{dur:.2f}", "-i", p]
    if bgm:
        cmd += ["-i", bgm]

    total_sec = sum(d for d, _ in scenes)
    parts = []
    for i, (dur, _) in enumerate(paths):
        # ゆっくり寄る。1画面あたり最大でも約8%まで。
        # zoompan の出力fpsは既定が25。ここを合わせないと、
        # 20fpsで作ったフレームが25fps扱いになり、動画が短くなる（30秒→24秒）。
        parts.append(
            f"[{i}:v]fps={fps},"
            f"zoompan=z='min(zoom+0.00035,1.08)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps}[v{i}]"
        )
    concat_in = "".join(f"[v{i}]" for i in range(len(paths)))
    parts.append(f"{concat_in}concat=n={len(paths)}:v=1:a=0[v]")
    filter_complex = ";".join(parts)

    cmd += ["-filter_complex", filter_complex, "-map", "[v]"]
    if bgm:
        fade_start = max(0, total_sec - 1.5)
        cmd += ["-map", f"{len(paths)}:a",
                "-af", f"volume=0.45,afade=t=out:st={fade_start:.1f}:d=1.5",
                "-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), out]
    return cmd


def pick_bgm(index=None):
    """
    BGMを選ぶ。index を渡すと曲を変えられる（毎回同じ曲だと飽きられるため）。
    """
    files = sorted(glob.glob(os.path.join(BGM_DIR, "*.mp3")))
    if not files:
        return None
    if index is not None:
        return files[index % len(files)]
    for kw in ("meditation", "relax", "piano", "ambient"):
        for f in files:
            if kw in os.path.basename(f).lower():
                return f
    return files[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--no-bgm", action="store_true")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("[ERROR] ffmpeg が見つかりません。")
        print("  Mac なら: brew install ffmpeg")
        sys.exit(1)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    print("[1/3] 場面を作っています...")
    scenes = build_scenes()
    total_sec = sum(d for d, _ in scenes)

    work = tempfile.mkdtemp()
    bgm = None if args.no_bgm else pick_bgm()
    try:
        print(f"[2/3] 場面を書き出しています（{len(scenes)}場面 / 合計{total_sec:.1f}秒）...")
        cmd = build_ffmpeg_cmd(scenes, work, args.fps, args.out, bgm)

        print("[3/3] 動画に変換しています...")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("[ERROR] ffmpeg が失敗しました:")
            print(r.stderr[-1800:])
            sys.exit(1)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    kb = os.path.getsize(args.out) / 1024
    print()
    print(f"完了: {args.out}")
    print(f"  {W}×{H}（9:16） / {total_sec:.1f}秒 / {kb / 1024:.1f}MB")
    if bgm:
        print(f"  BGM: {os.path.basename(bgm)}")


if __name__ == "__main__":
    main()
