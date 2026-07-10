#!/usr/bin/env python3
"""Reel Bapica — 20s vertical (1080x1920) pour réseaux sociaux"""

from PIL import Image, ImageDraw, ImageFont
import subprocess, os

W, H = 1080, 1920
BG = (13, 13, 26)
FG = (245, 245, 247)
MUTED = (161, 161, 170)
BLUE = (0, 130, 230)
TEAL = (45, 212, 191)
EMERALD = (16, 185, 129)
OUT = "/tmp/bapica-reel"
os.makedirs(OUT, exist_ok=True)

try:
    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
    sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    big_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
except:
    title_font = sub_font = big_font = ImageFont.load_default()

def draw_centered(d, text, y, font, color=FG):
    bbox = d.textbbox((0,0), text, font=font)
    tw = bbox[2] - bbox[0]
    d.text(((W-tw)//2, y), text, fill=color, font=font)

# Scene 1: Accroche (3s)
def s1():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    draw_centered(d, "11 agents IA", 500, title_font, FG)
    draw_centered(d, "pour votre PME", 580, title_font, TEAL)
    draw_centered(d, "24/7 • Sans recruter", 700, sub_font, MUTED)
    return img

# Scene 2: Marc focus (5s)
def s2():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    draw_centered(d, "⭐ Conseiller", 450, title_font, TEAL)
    draw_centered(d, "Croissance", 530, title_font, FG)
    draw_centered(d, "Prospects • Messages", 680, sub_font, MUTED)
    draw_centered(d, "Stratégie CA", 740, sub_font, MUTED)
    return img

# Scene 3: Grid agents (5s)
def s3():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    draw_centered(d, "Support • Téléphone • Juridique", 450, sub_font, MUTED)
    draw_centered(d, "Compta • Vidéo • Recrutement", 520, sub_font, MUTED)
    draw_centered(d, "Analytics • Tendances", 590, sub_font, MUTED)
    draw_centered(d, "Tout. Une seule plateforme.", 700, title_font, TEAL)
    return img

# Scene 4: CTA (5s)
def s4():
    img = Image.new('RGB', (W,H), (5, 30, 50))
    d = ImageDraw.Draw(img)
    for y in range(H):
        ratio = y / H
        r = int(5 + (0-5)*ratio)
        g = int(30 + (130-30)*ratio*0.5)
        b = int(50 + (129-50)*ratio*0.5)
        for x in range(W):
            img.putpixel((x, y), (r, g, b))
    
    draw_centered(d, "Bapica", 500, big_font, FG)
    draw_centered(d, "Essayez gratuitement", 650, title_font, TEAL)
    d.rounded_rectangle([240, 800, 840, 880], radius=16, fill=BLUE)
    d.text((280, 810), "bapica.com  →", fill=(255,255,255), font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38))
    return img

scenes = [s1, s2, s3, s4]
durations = [4, 5, 5, 6]

print("Génération Reel...")
all_frames = []
for i, fn in enumerate(scenes):
    img = fn()
    path = f"{OUT}/r{i}.png"
    img.save(path)
    all_frames.extend([path] * (durations[i] * 25))

with open(f"{OUT}/frames.txt", "w") as f:
    for frame in all_frames:
        f.write(f"file '{frame}'\nduration {1/25}\n")

subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", f"{OUT}/frames.txt",
    "-i", "/tmp/bapica-short-audio.mp3",
    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
    "-shortest", "-movflags", "+faststart",
    "/root/bapica/bapica/public/bapica-reel.mp4"
], check=True)

print("✅ /root/bapica/bapica/public/bapica-reel.mp4")
