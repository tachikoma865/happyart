import os
import subprocess

def main():
    base_images = [
        ("day1_gold.png", "gold"),
        ("day2_pink.png", "pink"),
        ("day3_blue.png", "blue"),
        ("day4_green.png", "green"),
        ("day5_purple.png", "purple")
    ]
    
    input_dir = "teaser_images"
    output_dir = "mass_images"
    os.makedirs(output_dir, exist_ok=True)
    
    total_days = 30
    
    for i in range(total_days):
        day_num = i + 1
        base_img, theme = base_images[i % len(base_images)]
        
        # Calculate variations based on iteration
        iteration = i // len(base_images)
        
        # Hue shift: 0, 15, 30, 45, 60, 75
        hue_shift = iteration * 15
        
        # Flips
        hflip = ",hflip" if iteration % 2 == 1 else ""
        vflip = ",vflip" if (iteration // 2) % 2 == 1 else ""
        
        input_path = os.path.join(input_dir, base_img)
        output_name = f"day{day_num}_{theme}.png"
        output_path = os.path.join(output_dir, output_name)
        
        # FFmpeg filter
        vf = f"hue=h={hue_shift}{hflip}{vflip}"
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", vf,
            "-update", "1",
            output_path
        ]
        
        print(f"Generating Day {day_num}: {output_name}")
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    main()
