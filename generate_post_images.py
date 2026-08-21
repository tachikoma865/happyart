#!/usr/bin/env python3
"""
投稿用画像ジェネレーター

実物のアート写真は使わず、投稿用のグラフィックをすべて新規描画する。
フルイドアート風の抽象背景をコードで生成し、その上に文字を載せる。

出力先: post_images/

使い方:
    python3 generate_post_images.py
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = "post_images"
SIZE = 1080  # Instagram正方形

# 日本語フォント候補（環境に応じて自動検出）
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]
FONT_SERIF_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJKjp-Bold.otf",
    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
]


def find_font(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    # フォールバック：システムから探す
    for root in ["/usr/share/fonts", "/System/Library/Fonts", "/Library/Fonts"]:
        for dirpath, _, files in os.walk(root):
            for f in files:
                if "CJK" in f and ("Bold" in f or "Regular" in f):
                    return os.path.join(dirpath, f)
    return None


FONT_PATH = find_font(FONT_CANDIDATES)
FONT_SERIF = find_font(FONT_SERIF_CANDIDATES) or FONT_PATH


def load_font(size, serif=False):
    path = FONT_SERIF if serif else FONT_PATH
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ---------------------------------------------------------------
# フルイドアート風の抽象背景を生成する
# ---------------------------------------------------------------

def _value_noise(size, cells, rng):
    """格子状の乱数を滑らかに補間したノイズ（1オクターブ分）"""
    g = rng.random((cells + 1, cells + 1)).astype(np.float32)
    img = Image.fromarray((g * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
    return np.asarray(img).astype(np.float32) / 255.0


def fbm(size, rng, octaves=5, base_cells=3, gain=0.5):
    """フラクタルノイズ。自然な濃淡のムラを作る"""
    out = np.zeros((size, size), dtype=np.float32)
    amp, total, cells = 1.0, 0.0, base_cells
    for _ in range(octaves):
        out += _value_noise(size, cells, rng) * amp
        total += amp
        amp *= gain
        cells *= 2
    return out / total


def _warp(field, dx, dy):
    """座標をずらして画像をゆがめる（ドメインワーピング）"""
    size = field.shape[0]
    yy, xx = np.mgrid[0:size, 0:size]
    sx = np.clip((xx + dx).astype(np.int32), 0, size - 1)
    sy = np.clip((yy + dy).astype(np.int32), 0, size - 1)
    return field[sy, sx]


def fluid_background(palette, seed=0, size=SIZE):
    """
    フルイドアート風の背景を生成。

    ドメインワーピング（ノイズでノイズを歪ませる手法）を使うことで、
    絵の具が流れて混ざり合ったような有機的なマーブル模様を作る。
    palette: [(r,g,b), ...] 明→暗の順で4〜5色
    """
    rng = np.random.default_rng(seed)

    # 3層のノイズ。q が p を歪ませ、r が q を歪ませる
    p = fbm(size, rng, octaves=5, base_cells=3)
    q1 = fbm(size, rng, octaves=4, base_cells=2)
    q2 = fbm(size, rng, octaves=4, base_cells=2)
    r1 = fbm(size, rng, octaves=3, base_cells=2)
    r2 = fbm(size, rng, octaves=3, base_cells=2)

    amp1 = size * 0.42
    amp2 = size * 0.22
    q1w = _warp(q1, (r1 - 0.5) * amp2, (r2 - 0.5) * amp2)
    q2w = _warp(q2, (r2 - 0.5) * amp2, (r1 - 0.5) * amp2)
    value = _warp(p, (q1w - 0.5) * amp1, (q2w - 0.5) * amp1)

    # 流れの筋（脈）を重ねて、絵の具が引き伸ばされた感じを出す
    veins = np.abs(np.sin((value + q1w * 0.5) * math.pi * 3.0))
    value = np.clip(value * 0.72 + veins * 0.28, 0, 1)

    # コントラストは控えめに（明度を保つため強くしすぎない）
    value = np.clip((value - 0.5) * 1.15 + 0.5, 0, 1)

    # 全体を明るい側へ持ち上げる（暗いパレット端をあまり使わないようにする）
    value = np.clip(value * 0.72 + 0.06, 0, 1)

    # 光が差す方向を作る（左上をわずかに明るく。落差は小さめ）
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    light = 1.06 - ((xx + yy) / (size * 2)) * 0.13
    value = np.clip(value * light, 0, 1)

    # パレットで着色（線形補間）
    pal = np.array(palette, dtype=np.float32)
    n = len(pal) - 1
    pos = value * n
    idx = np.clip(pos.astype(int), 0, n - 1)
    frac = (pos - idx)[..., None]
    rgb = pal[idx] * (1 - frac) + pal[idx + 1] * frac

    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    img = img.filter(ImageFilter.GaussianBlur(radius=size / 600))

    # ラメは「明るい筋の上だけ」に散らす（そこが光を受ける場所なので自然に見える）
    img = add_glitter(img, rng, size, value)
    return img


def add_glitter(img, rng, size, value, density=0.00055):
    """
    ラメの粒子。value（明るさマップ）が高い場所に集中させることで、
    絵の具の盛り上がりが光を反射しているように見せる。
    明るい配色では白飛びしないよう、加算量を控えめにしている。
    """
    arr = np.asarray(img).astype(np.float32)

    count = int(size * size * density)
    # 明るい場所ほど選ばれやすいように重み付け
    w = np.clip(value - 0.30, 0, 1).ravel() ** 2
    if w.sum() <= 0:
        return img
    picks = rng.choice(w.size, size=count, replace=False, p=w / w.sum())
    ys, xs = np.unravel_index(picks, (size, size))

    layer = np.zeros((size, size), dtype=np.float32)
    strengths = rng.random(count) ** 2.5  # 大半は弱く、ごく一部だけ強く光る
    layer[ys, xs] = strengths

    lp = Image.fromarray((np.clip(layer, 0, 1) * 255).astype(np.uint8), "L")
    lp = lp.filter(ImageFilter.GaussianBlur(size / 900))
    spark = np.asarray(lp).astype(np.float32) / 255.0

    # 金色寄りの光を加算（明るい背景では控えめに効かせる）
    tint = np.array([1.0, 0.93, 0.72], dtype=np.float32)
    arr += spark[..., None] * tint * 95.0
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------
# パレット定義（3色：金・青・桃）
# ---------------------------------------------------------------

PALETTES = {
    "gold": {
        "label": "金",
        "colors": [(255, 253, 246), (253, 242, 211), (246, 221, 156), (228, 191, 106), (188, 146, 62)],
        "ink": (74, 54, 18),
    },
    "blue": {
        "label": "青",
        "colors": [(251, 253, 255), (230, 245, 253), (186, 226, 244), (128, 192, 228), (68, 140, 192)],
        "ink": (20, 52, 84),
    },
    "pink": {
        "label": "桃",
        "colors": [(255, 251, 253), (254, 236, 243), (250, 212, 227), (243, 180, 205), (222, 132, 172)],
        "ink": (92, 34, 62),
    },
    # ↓ 選択占いが毎回「金・青・桃」の同一パターンで単調だったため追加した3色。
    #   毎回トリオを組み替えて出す。LINEの診断もこの6色ぶん用意してある。
    "green": {
        "label": "緑",
        "colors": [(248, 253, 246), (226, 244, 224), (196, 232, 196), (150, 208, 156), (96, 168, 112)],
        "ink": (28, 74, 44),
    },
    "purple": {
        "label": "紫",
        "colors": [(251, 250, 255), (238, 234, 250), (219, 209, 242), (190, 172, 226), (150, 126, 196)],
        "ink": (70, 48, 110),
    },
    "akane": {
        "label": "茜",
        "colors": [(255, 250, 246), (253, 234, 222), (250, 209, 184), (244, 172, 132), (226, 124, 84)],
        "ink": (122, 52, 24),
    },
}


# ---------------------------------------------------------------
# 文字描画のヘルパー
# ---------------------------------------------------------------

def draw_text_center(draw, text, font, y, size=SIZE, fill=(255, 255, 255),
                     shadow=False, halo=None):
    """
    中央揃えでテキストを描く。
    halo に色を渡すと、その色で文字の縁取りを描いて背景から浮かせる
    （明るい背景に濃い文字を置くときは halo に白系を指定する）。
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (size - w) / 2 - bbox[0]
    if halo is not None:
        r = max(2, int(font.size * 0.05))
        for ox in range(-r, r + 1, max(1, r)):
            for oy in range(-r, r + 1, max(1, r)):
                if ox or oy:
                    draw.text((x + ox, y + oy), text, font=font, fill=halo)
    elif shadow:
        for off in [(3, 3), (-2, 2), (2, -2)]:
            draw.text((x + off[0], y + off[1]), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def wrap_text(text, font, draw, max_width):
    """日本語向け：文字単位で折り返す"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        test = cur + ch
        if draw.textlength(test, font=font) > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------
# 生成する画像
# ---------------------------------------------------------------

def make_choice_card(key, number, seed):
    """選択占い用：番号付きの色カード（1色1枚）"""
    p = PALETTES[key]
    img = fluid_background(p["colors"], seed=seed)
    d = ImageDraw.Draw(img)

    # 下部に「白い」グラデーションを敷いて、濃い文字を読みやすくする
    # （下ほど白く、上に向かってなめらかに消える。継ぎ目が出ないようにする）
    band = int(SIZE * 0.48)
    mask = np.zeros((SIZE, SIZE), dtype=np.float32)
    ramp = np.linspace(0.0, 1.0, band) ** 2.0  # 上=0 → 下=1、二次カーブで自然に
    mask[SIZE - band:, :] = ramp[:, None]
    mask_img = Image.fromarray((mask * 232).astype(np.uint8), "L")
    img = Image.composite(Image.new("RGB", (SIZE, SIZE), (255, 253, 250)), img, mask_img)
    d = ImageDraw.Draw(img)

    ink = p["ink"]
    f_num = load_font(190, serif=True)
    f_lab = load_font(96, serif=True)
    draw_text_center(d, str(number), f_num, SIZE * 0.60, fill=ink)
    draw_text_center(d, p["label"], f_lab, SIZE * 0.83, fill=ink)
    return img


def make_choice_sheet(seed=7):
    """選択占い1枚目：3色を横に並べた選択肢シート"""
    BG = (252, 250, 246)
    INK = (46, 40, 34)
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)

    f_title = load_font(74, serif=True)
    f_sub = load_font(40)
    draw_text_center(d, "直感で選んでください", f_title, 88, fill=INK)
    draw_text_center(d, "考えないで、目が留まった色を", f_sub, 190,
                     fill=(128, 120, 110))

    keys = ["gold", "blue", "pink"]
    panel_w = 300
    gap = 30
    total = panel_w * 3 + gap * 2
    left = (SIZE - total) // 2
    top = 300
    panel_h = 480

    f_num = load_font(84, serif=True)
    f_lab = load_font(44, serif=True)

    for i, key in enumerate(keys):
        p = PALETTES[key]
        tile = fluid_background(p["colors"], seed=seed + i * 13, size=panel_w)
        tile = tile.resize((panel_w, panel_h), Image.LANCZOS)
        x = left + i * (panel_w + gap)
        img.paste(tile, (x, top))
        d.rectangle([x, top, x + panel_w, top + panel_h], outline=(226, 220, 210), width=2)

        # 番号と色名
        bbox = d.textbbox((0, 0), str(i + 1), font=f_num)
        d.text((x + panel_w / 2 - (bbox[2] - bbox[0]) / 2, top + panel_h + 22),
               str(i + 1), font=f_num, fill=INK)
        bbox = d.textbbox((0, 0), p["label"], font=f_lab)
        d.text((x + panel_w / 2 - (bbox[2] - bbox[0]) / 2, top + panel_h + 128),
               p["label"], font=f_lab, fill=(132, 124, 114))

    f_cta = load_font(38)
    draw_text_center(d, "選んだ番号をコメントで教えてください", f_cta, SIZE - 92,
                     fill=(120, 112, 102))
    return img


def make_text_card(title, body, key="gold", seed=3, kicker=None):
    """暦・開運テク用：抽象背景＋テキストのカード"""
    p = PALETTES[key]
    bg = fluid_background(p["colors"], seed=seed)
    bg = bg.filter(ImageFilter.GaussianBlur(14))

    # 白を重ねて淡くし、濃い文字を主役にする
    veil = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
    img = Image.blend(bg, veil, 0.42)
    d = ImageDraw.Draw(img)

    f_k = load_font(36)
    f_title = load_font(78, serif=True)
    f_body = load_font(42)

    title_lines = wrap_text(title, f_title, d, SIZE - 200)
    body_lines = wrap_text(body, f_body, d, SIZE - 220)

    # 全体の高さを先に測って、縦方向の中央に配置する
    total_h = (78 if kicker else 0) + len(title_lines) * 104 + 40 + len(body_lines) * 68
    y = (SIZE - total_h) / 2

    ink = p["ink"]
    if kicker:
        draw_text_center(d, kicker, f_k, y, fill=(168, 132, 62), halo=(255, 255, 255))
        y += 78

    for line in title_lines:
        draw_text_center(d, line, f_title, y, fill=ink, halo=(255, 255, 255))
        y += 104

    y += 40
    for line in body_lines:
        draw_text_center(d, line, f_body, y, fill=(92, 84, 78), halo=(255, 255, 255))
        y += 68

    return img


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1/3] 選択占いの選択肢シートを生成...")
    make_choice_sheet().save(f"{OUT_DIR}/choice_sheet.png")

    print("[2/3] 各色のカードを生成...")
    for i, key in enumerate(["gold", "blue", "pink"]):
        make_choice_card(key, i + 1, seed=100 + i * 17).save(f"{OUT_DIR}/choice_{key}.png")

    print("[3/3] テキストカードのサンプルを生成...")
    make_text_card(
        "8月の開運日\nカレンダー",
        "保存して手帳に入れておくと便利です",
        key="gold", seed=42, kicker="暦のはなし",
    ).save(f"{OUT_DIR}/sample_calendar.png")

    make_text_card(
        "財布の使い始めで\n知っておきたいこと",
        "昔から言われている4つの習わし",
        key="blue", seed=88, kicker="開運のいとなみ",
    ).save(f"{OUT_DIR}/sample_wallet.png")

    print(f"\n完了。{OUT_DIR}/ に出力しました。")
    for f in sorted(os.listdir(OUT_DIR)):
        print("  -", f)


if __name__ == "__main__":
    main()
