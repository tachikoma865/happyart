#!/usr/bin/env python3
"""
アカウントアイコン案ジェネレーター

顔出しなし前提。Instagramのアイコンは実際には約44pxで表示されるため、
「小さくしても何が描いてあるか分かる」ことを最優先に設計している。

出力先: icon_candidates/
  各案を 1080px（確認用）と 44px（実寸シミュレーション）の両方で出力する。

使い方:
    python3 generate_icon.py
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from generate_post_images import (
    fluid_background, PALETTES, load_font, draw_text_center, fbm,
)

OUT_DIR = "icon_candidates"
S = 1080


def circle_mask(size, margin=0):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([margin, margin, size - margin, size - margin], fill=255)
    return m


def gold_ring(img, width=14, inset=26, color=(198, 156, 74)):
    """外周に細い金のリングを描く（小さくしても輪郭が保たれる）"""
    d = ImageDraw.Draw(img)
    d.ellipse([inset, inset, S - inset, S - inset], outline=color, width=width)
    return img


def tri_color_swirl(seed=11):
    """
    案A：金・青・桃の3色が円の中で混ざり合う。
    選択占い（3色）と一致するので、アカウントの主力コンテンツが一目で伝わる。
    """
    base = Image.new("RGB", (S, S), (253, 251, 248))
    rng = np.random.default_rng(seed)

    keys = ["gold", "blue", "pink"]
    layers = [
        np.asarray(fluid_background(PALETTES[k]["colors"], seed=seed + i * 29, size=S)
                   ).astype(np.float32)
        for i, k in enumerate(keys)
    ]

    # 各色の「濃さ」を、なだらかなノイズで決める。
    # 扇形で切ると円グラフに見えてしまうので、絵の具が流れて混ざる形にする。
    weights = []
    for i in range(3):
        w = fbm(S, np.random.default_rng(seed * 7 + i * 101), octaves=4, base_cells=2)
        weights.append(w)
    wa = np.stack(weights, axis=0)

    # ソフトマックスで滑らかに支配色を決める。
    # 温度を上げすぎると3色が混ざって白っぽい塊になり、44pxで何も判別できなくなる。
    # 境界だけ柔らかく、各色の領域はしっかり残す値にしている。
    temperature = 0.045
    wa = np.exp((wa - wa.max(axis=0, keepdims=True)) / temperature)
    wa /= wa.sum(axis=0, keepdims=True)

    out = np.zeros((S, S, 3), dtype=np.float32)
    for i in range(3):
        out += layers[i] * wa[i][..., None]

    # アイコンは小さく表示されるので、彩度を上げて色を判別しやすくする
    gray = out.mean(axis=2, keepdims=True)
    out = np.clip(gray + (out - gray) * 1.75, 0, 255)
    out *= 0.94  # ほんの少し落として、色を締める

    swirl = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
    swirl = swirl.filter(ImageFilter.GaussianBlur(3))

    img = Image.composite(swirl, base, circle_mask(S, margin=40))
    return gold_ring(img)


def kanji_icon(char="光", key="gold", seed=5):
    """
    案B：淡いフルイドの円に、明朝体で一文字。
    小さくしても「文字がある」ことは判別できるので視認性が高い。
    """
    base = Image.new("RGB", (S, S), (253, 251, 248))
    bg = fluid_background(PALETTES[key]["colors"], seed=seed, size=S)
    bg = bg.filter(ImageFilter.GaussianBlur(10))
    bg = Image.blend(bg, Image.new("RGB", (S, S), (255, 255, 255)), 0.25)

    img = Image.composite(bg, base, circle_mask(S, margin=40))
    d = ImageDraw.Draw(img)

    f = load_font(560, serif=True)
    bbox = d.textbbox((0, 0), char, font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((S - w) / 2 - bbox[0], (S - h) / 2 - bbox[1] - 10), char,
           font=f, fill=PALETTES[key]["ink"])

    return gold_ring(img)


def moon_icon(seed=21):
    """
    案C：淡い夜明けの色に三日月。
    占い・暦アカウントだと一目で伝わる。文字がないので言語に依存しない。
    """
    base = Image.new("RGB", (S, S), (253, 251, 248))
    bg = fluid_background(PALETTES["blue"]["colors"], seed=seed, size=S)
    bg = bg.filter(ImageFilter.GaussianBlur(18))
    bg = Image.blend(bg, Image.new("RGB", (S, S), (255, 250, 240)), 0.30)
    img = Image.composite(bg, base, circle_mask(S, margin=40))

    # 三日月：大きい円から少しずらした円を引き算して作る
    moon = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(moon)
    r = 280
    md.ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], fill=255)
    cut = Image.new("L", (S, S), 0)
    cd = ImageDraw.Draw(cut)
    cd.ellipse([S / 2 - r + 150, S / 2 - r - 30, S / 2 + r + 150, S / 2 + r - 30], fill=255)
    moon = Image.fromarray(
        np.clip(np.asarray(moon).astype(np.int16) - np.asarray(cut).astype(np.int16), 0, 255
                ).astype(np.uint8), "L")
    moon = moon.filter(ImageFilter.GaussianBlur(2))

    img = Image.composite(Image.new("RGB", (S, S), (206, 164, 78)), img, moon)

    # 小さな星をひとつ添える
    d = ImageDraw.Draw(img)
    sx, sy, sr = S * 0.66, S * 0.34, 26
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = sr if i % 2 == 0 else sr * 0.4
        pts.append((sx + math.cos(a) * rr, sy + math.sin(a) * rr))
    d.polygon(pts, fill=(214, 176, 96))

    return gold_ring(img)


def smooth_closed(pts, samples=14):
    """
    閉じた点列をCatmull-Romスプラインで補間して、角ばりを取る。
    多角形のままだと顔の輪郭がカクカクして人物に見えないため。
    """
    n = len(pts)
    out = []
    for i in range(n):
        p0 = np.array(pts[(i - 1) % n], dtype=np.float64)
        p1 = np.array(pts[i], dtype=np.float64)
        p2 = np.array(pts[(i + 1) % n], dtype=np.float64)
        p3 = np.array(pts[(i + 2) % n], dtype=np.float64)
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            pt = 0.5 * ((2 * p1) + (-p0 + p2) * t
                        + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                        + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((pt[0], pt[1]))
    return out


def profile_silhouette(seed=33):
    """
    案D：横顔のシルエットを3色のフルイドで塗る。

    リサーチによると占い系は「属人性」が効く（誰に占ってもらうかが選択基準になる）。
    ただし顔・声を出さない方針なので、実在の顔を出さずに人格だけを立てる中間解。
    シルエットは輪郭が明快なので44pxでも人物だと判別できる。
    """
    base = Image.new("RGB", (S, S), (253, 251, 248))
    fill = tri_color_swirl(seed=seed)  # 3色のフルイドを塗りに使う

    # 左を向いたバストアップの輪郭（0〜1の正規化座標）
    # 円の中に収まるよう、頭・首・肩まで入れて重心を下げている
    pts = [
        (0.470, 0.205), (0.560, 0.212), (0.640, 0.250),   # 頭頂〜後頭部
        (0.692, 0.305), (0.712, 0.375), (0.714, 0.450),
        (0.706, 0.520), (0.730, 0.590), (0.752, 0.640),   # 髪が肩へ落ちる
        (0.820, 0.720), (0.868, 0.800), (0.888, 0.885),
        (0.895, 0.960), (0.185, 0.960),                    # 肩〜画面下端
        (0.196, 0.878), (0.232, 0.792), (0.292, 0.722),
        (0.372, 0.668), (0.418, 0.640),                    # 首
        (0.408, 0.596), (0.386, 0.566),                    # あご
        (0.350, 0.530), (0.328, 0.505),                    # 口もと
        (0.316, 0.482), (0.330, 0.466),
        (0.300, 0.452), (0.272, 0.436),                    # 鼻
        (0.318, 0.404), (0.330, 0.372),                    # 鼻筋
        (0.316, 0.348), (0.328, 0.312),                    # 眉
        (0.348, 0.272), (0.382, 0.234),                    # 額〜生え際
        (0.422, 0.211),
    ]

    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(x * S, y * S) for x, y in smooth_closed(pts)], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(2.2))

    # 淡い同系色の下地を敷いてから、シルエットを乗せる
    bg = fluid_background(PALETTES["gold"]["colors"], seed=seed + 4, size=S)
    bg = bg.filter(ImageFilter.GaussianBlur(26))
    bg = Image.blend(bg, Image.new("RGB", (S, S), (255, 255, 255)), 0.62)

    art = Image.composite(fill, bg, mask)
    img = Image.composite(art, base, circle_mask(S, margin=40))
    return gold_ring(img)


def save(img, name):
    img.save(f"{OUT_DIR}/{name}.png")
    # 実寸シミュレーション（Instagramのアイコン表示サイズ相当）
    img.resize((44, 44), Image.LANCZOS).resize((176, 176), Image.NEAREST).save(
        f"{OUT_DIR}/{name}_44px.png")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("案A：3色スワール（選択占いと一致）")
    save(tri_color_swirl(), "A_tricolor")

    print("案B：一文字「光」")
    save(kanji_icon("光", "gold"), "B_kanji_hikari")

    print("案C：三日月（暦・占い）")
    save(moon_icon(), "C_moon")

    print("案D：横顔シルエット×3色（半属人性）")
    save(profile_silhouette(), "D_silhouette")

    print(f"\n完了。{OUT_DIR}/ に出力しました。")
    print("*_44px.png は実際のアイコン表示サイズでの見え方です。")


if __name__ == "__main__":
    main()
