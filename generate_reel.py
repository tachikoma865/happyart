#!/usr/bin/env python3
"""
リール動画生成スクリプト（GLINTRIA）

画像ファイルを入力として、以下を自動で行います：
1. ゆっくりズームインするアニメーション効果を適用
2. bgm/ フォルダからランダムにBGMを選択して合成
3. Instagram リール用の MP4 動画（9:16 or 1:1）を出力

使い方:
    python3 generate_reel.py 入力画像.png
    python3 generate_reel.py 入力画像.png --duration 15
    python3 generate_reel.py 入力画像.png --output my_reel.mp4
    python3 generate_reel.py 入力画像.png --no-bgm
"""

import os
import sys
import random
import argparse
import subprocess
import glob

# 設定
BGM_DIR = "bgm"
OUTPUT_DIR = "reels_output"
DEFAULT_DURATION = 12  # デフォルト動画長さ（秒）
ZOOM_SPEED = 0.0015    # ズーム速度（大きいほど速い）
OUTPUT_SIZE = "1080:1080"  # 1:1（正方形）。9:16にする場合は "1080:1920"


def find_random_bgm():
    """bgm/ フォルダからランダムに1曲選ぶ"""
    bgm_files = []
    for ext in ["*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg"]:
        bgm_files.extend(glob.glob(os.path.join(BGM_DIR, ext)))
    
    if not bgm_files:
        return None
    
    chosen = random.choice(bgm_files)
    print(f"🎵 BGM選択: {os.path.basename(chosen)}")
    return chosen


def generate_reel(input_image, output_path, duration, use_bgm=True):
    """画像からリール動画を生成する"""
    
    # 出力ディレクトリの作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # ズームイン効果のフィルター
    # ゆっくりズームインしながら逆回転する（吸い込まれる）効果
    total_frames = duration * 30  # 30fps
    # カクつきをなくすため、一度3000x3000に拡大してから処理する
    zoom_filter = (
        f"scale=3000x3000,"
        f"zoompan=z='min(zoom+{ZOOM_SPEED},1.5)':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={total_frames}:"
        f"s=1530x1530:"
        f"fps=30,"
        f"rotate=a=-0.1*t:c=black:bilinear=1,"
        f"crop=1080:1080,"
        f"format=yuv420p"
    )
    
    # BGMの検索
    bgm_path = None
    if use_bgm:
        bgm_path = find_random_bgm()
        if not bgm_path:
            print("⚠️  bgm/ フォルダにBGMファイルが見つかりません。無音で生成します。")
            print(f"   → bgm/ フォルダに .mp3 / .wav / .m4a ファイルを入れてください")
    
    # FFmpegコマンドの構築
    cmd = ["ffmpeg", "-y"]
    
    # 入力: 画像
    cmd.extend(["-loop", "1", "-i", input_image])
    
    # 入力: BGM（あれば）
    if bgm_path:
        cmd.extend(["-i", bgm_path])
    
    # フィルター
    cmd.extend(["-vf", zoom_filter])
    
    # 出力設定
    cmd.extend([
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",          # 高品質
        "-pix_fmt", "yuv420p", # Instagram互換
    ])
    
    # 音声設定
    if bgm_path:
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",       # 短い方に合わせる
            "-af", f"afade=t=in:st=0:d=2,afade=t=out:st={duration-2}:d=2"  # フェードイン/アウト
        ])
    else:
        # 無音の場合は音声なしで生成
        cmd.extend(["-an"])
    
    cmd.append(output_path)
    
    print(f"\n🎬 動画を生成中...")
    print(f"   入力画像: {input_image}")
    print(f"   動画の長さ: {duration}秒")
    print(f"   出力先: {output_path}")
    print(f"   サイズ: {OUTPUT_SIZE}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            print(f"\n❌ エラーが発生しました:")
            print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
            return False
        
        # ファイルサイズの確認
        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)
        print(f"\n✅ 動画生成完了！")
        print(f"   ファイル: {output_path}")
        print(f"   サイズ: {file_size_mb:.1f} MB")
        
        if file_size_mb > 100:
            print(f"   ⚠️  Instagramの上限（100MB）を超えています。durationを短くしてください。")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ タイムアウト: 動画生成に時間がかかりすぎています。")
        return False
    except FileNotFoundError:
        print("❌ FFmpegが見つかりません。先に `brew install ffmpeg` を実行してください。")
        return False


def batch_generate(image_dir, duration, use_bgm=True):
    """ディレクトリ内の全画像から動画を一括生成する"""
    image_files = []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
        image_files.extend(glob.glob(os.path.join(image_dir, ext)))
    
    if not image_files:
        print(f"❌ {image_dir} に画像ファイルが見つかりません。")
        return
    
    print(f"📂 {len(image_files)} 枚の画像から動画を生成します\n")
    
    success_count = 0
    for img in sorted(image_files):
        basename = os.path.splitext(os.path.basename(img))[0]
        output_path = os.path.join(OUTPUT_DIR, f"{basename}_reel.mp4")
        
        if generate_reel(img, output_path, duration, use_bgm):
            success_count += 1
        print()
    
    print(f"\n{'='*50}")
    print(f"🎬 完了: {success_count}/{len(image_files)} 本の動画を生成しました")
    print(f"📂 出力先: {OUTPUT_DIR}/")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="画像からInstagramリール用動画を生成する（GLINTRIA）"
    )
    parser.add_argument(
        "input",
        help="入力画像ファイルのパス、またはディレクトリ（一括処理）"
    )
    parser.add_argument(
        "--output", "-o",
        help="出力ファイル名（デフォルト: reels_output/[入力名]_reel.mp4）"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=DEFAULT_DURATION,
        help=f"動画の長さ（秒）。デフォルト: {DEFAULT_DURATION}秒"
    )
    parser.add_argument(
        "--no-bgm",
        action="store_true",
        help="BGMを付けない（無音動画を生成）"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="ディレクトリ内の全画像から一括生成"
    )
    
    args = parser.parse_args()
    
    if args.batch or os.path.isdir(args.input):
        batch_generate(args.input, args.duration, not args.no_bgm)
    else:
        if not os.path.exists(args.input):
            print(f"❌ ファイルが見つかりません: {args.input}")
            sys.exit(1)
        
        if args.output:
            output_path = args.output
        else:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            basename = os.path.splitext(os.path.basename(args.input))[0]
            output_path = os.path.join(OUTPUT_DIR, f"{basename}_reel.mp4")
        
        success = generate_reel(args.input, output_path, args.duration, not args.no_bgm)
        sys.exit(0 if success else 1)
