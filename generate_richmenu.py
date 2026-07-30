#!/usr/bin/env python3
"""
LINE公式アカウント リッチメニュー画像ジェネレーター

仕様（LINE公式）:
  小サイズ推奨 2500 × 843 px（3分割にちょうど良い比率）
  形式 JPEG / PNG、ファイルサイズ 1MB以下

構成（3分割）:
  左   色を選ぶ        → 「1・金／2・青／3・桃」の選択メッセージを送る
  中央 今月の開運日     → 今月の一粒万倍日・新月・満月をまとめて送る
  右   Instagram      → https://www.instagram.com/kodoshi_hikari/ を開く

出力:
  richmenu/richmenu_3split.png
  richmenu/preview_phone.png   スマホ表示相当の縮小プレビュー

使い方:
    python3 generate_richmenu.py
"""

import os
import math
from PIL import Image, ImageDraw, ImageFilter

from generate_post_images import fluid_background, PALETTES, load_font

OUT_DIR = "richmenu"
W, H = 2500, 843
CELL = W // 3

BG = (252, 250, 246)       # 生成りの白（投稿画像と揃える）
INK = (46, 40, 34)         # 文字色
SUB = (132, 124, 114)      # 補助文字
GOLD = (198, 156, 74)      # 罫線・アクセント


def soft_wash():
    """背景に敷くごく淡いフルイドの色みを作る"""
    tile = fluid_background(PALETTES["gold"]["colors"], seed=71, size=max(W, H))
    tile = tile.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(60))
    base = Image.new("RGB", (W, H), BG)
    # ほぼ白。色みが分かる程度だけ残す
    return Image.blend(base, tile, 0.16)


def icon_three_circles(size):
    """左：3色の円が重なるアイコン（選択占いの3色を表す）"""
    s = size
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    r = int(s * 0.30)
    cx, cy = s / 2, s / 2
    offset = r * 0.62
    colors = [
        ((233, 193, 96, 225), -90),    # 金
        ((132, 194, 231, 225), 30),    # 青
        ((243, 168, 199, 225), 150),   # 桃
    ]
    for (rgba, deg) in colors:
        a = math.radians(deg)
        x = cx + math.cos(a) * offset
        y = cy + math.sin(a) * offset
        circle = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(circle).ellipse([x - r, y - r, x + r, y + r], fill=rgba)
        layer = Image.alpha_composite(layer, circle)
    return layer


def icon_moon(size):
    """中央：三日月と星（暦・開運日）"""
    s = size
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    r = int(s * 0.30)
    cx, cy = s * 0.46, s * 0.52

    full = Image.new("L", (s, s), 0)
    ImageDraw.Draw(full).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    cut = Image.new("L", (s, s), 0)
    ImageDraw.Draw(cut).ellipse(
        [cx - r + r * 0.52, cy - r - r * 0.12, cx + r + r * 0.52, cy + r - r * 0.12], fill=255)

    mask = Image.composite(Image.new("L", (s, s), 0), full, cut)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))

    moon = Image.new("RGBA", (s, s), GOLD + (255,))
    moon.putalpha(mask)
    layer = Image.alpha_composite(layer, moon)

    # 星をひとつ添える
    d = ImageDraw.Draw(layer)
    sx, sy, sr = s * 0.72, s * 0.30, s * 0.055
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = sr if i % 2 == 0 else sr * 0.42
        pts.append((sx + math.cos(a) * rr, sy + math.sin(a) * rr))
    d.polygon(pts, fill=GOLD + (255,))
    return layer


def icon_camera(size):
    """右：カメラのアイコン（Instagramへ）"""
    s = size
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lw = max(4, int(s * 0.055))
    m = s * 0.20
    box = [m, m, s - m, s - m]
    d.rounded_rectangle(box, radius=int(s * 0.20), outline=GOLD + (255,), width=lw)
    rr = s * 0.155
    d.ellipse([s / 2 - rr, s / 2 - rr, s / 2 + rr, s / 2 + rr], outline=GOLD + (255,), width=lw)
    dr = s * 0.032
    dx, dy = s - m - s * 0.115, m + s * 0.115
    d.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=GOLD + (255,))
    return layer


def draw_cell(img, index, icon, label, sublabel):
    """1マス分（アイコン＋ラベル）を描く"""
    d = ImageDraw.Draw(img)
    left = index * CELL
    cx = left + CELL / 2

    # アイコン・見出し・補足をひとかたまりとして、縦の中央に置く
    icon_size = 250
    ic = icon(icon_size)
    top = 178
    img.paste(ic, (int(cx - icon_size / 2), top), ic)

    f_label = load_font(84, serif=True)
    f_sub = load_font(44)

    bbox = d.textbbox((0, 0), label, font=f_label)
    d.text((cx - (bbox[2] - bbox[0]) / 2 - bbox[0], top + 302), label, font=f_label, fill=INK)

    bbox = d.textbbox((0, 0), sublabel, font=f_sub)
    d.text((cx - (bbox[2] - bbox[0]) / 2 - bbox[0], top + 438), sublabel, font=f_sub, fill=SUB)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    img = soft_wash()

    draw_cell(img, 0, icon_three_circles, "色を選ぶ", "金・青・桃から直感で")
    draw_cell(img, 1, icon_moon, "今月の開運日", "一粒万倍日・新月・満月")
    draw_cell(img, 2, icon_camera, "Instagram", "毎日の投稿はこちら")

    # 仕切り線（上下に余白を残して、圧迫感を出さない）
    d = ImageDraw.Draw(img)
    for i in (1, 2):
        x = i * CELL
        d.line([(x, 130), (x, H - 130)], fill=(228, 216, 194), width=3)

    path = f"{OUT_DIR}/richmenu_3split.png"
    img.save(path, optimize=True)

    size_kb = os.path.getsize(path) / 1024
    print(f"生成: {path}  ({W}×{H}px / {size_kb:.0f}KB)")

    # 1MBを超えたらJPEGで作り直す（LINEの上限は1MB）
    if size_kb > 1024:
        jpg = f"{OUT_DIR}/richmenu_3split.jpg"
        img.convert("RGB").save(jpg, quality=88, optimize=True)
        print(f"  → 1MB超のためJPEGも生成: {jpg} ({os.path.getsize(jpg)/1024:.0f}KB)")

    # スマホでの見え方を確認するための縮小プレビュー
    img.resize((750, 253), Image.LANCZOS).save(f"{OUT_DIR}/preview_phone.png")
    print(f"プレビュー: {OUT_DIR}/preview_phone.png（スマホ表示相当）")


if __name__ == "__main__":
    main()
