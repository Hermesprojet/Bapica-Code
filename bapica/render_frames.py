#!/usr/bin/env python3
"""Generate dynamic Bapica video frames with motion effects"""

from PIL import Image, ImageDraw, ImageFont
import subprocess, os, math, random

W, H = 1920, 1080
FPS = 60
OUTDIR = "/tmp/bapica-frames"
os.makedirs(OUTDIR, exist_ok=True)

NAVY = (6, 17, 38)
WHITE = (255, 255, 255)
LIGHT = (180, 190, 210)
GREEN = (34, 197, 94)
BLUE = (45, 90, 158)

font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
font_reg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)

# Generate frames for each scene
total_frames = 65 * FPS
particles = [(random.random()*W, random.random()*H, 2+random.random()*6, random.random()*0.3+0.2) for _ in range(20)]

import random
random.seed(42)

for frame_num in range(0, total_frames, 2):  # Every 2nd frame at 60fps = 30fps effective
    t = frame_num / FPS
    img = Image.new('RGB', (W, H), NAVY)
    draw = ImageDraw.Draw(img)
    
    # Animated particles
    for px, py, size, speed in particles:
        x = (px + t * 20 * speed) % W
        y = (py - t * 30 * speed) % H
        alpha = int(40 + 20 * math.sin(t * speed * 3))
        try:
            draw.ellipse([x-2, y-2, x+2, y+2], fill=(BLUE[0], BLUE[1], BLUE[2], alpha))
        except:
            draw.ellipse([x-2, y-2, x+2, y+2], fill=BLUE)
    
    if t < 10:
        # SCENE 1: Welcome
        progress = min(1, t/2)
        y_off = math.sin(t * 2) * 8
        fs = int(100 * progress) if progress < 1 else 100
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fs) if fs > 10 else font_bold
        bbox = draw.textbbox((0,0), "Bapica", font=font_b)
        draw.text(((W-bbox[2])//2, H//2 - 150 + int(y_off)), "Bapica", font=font_b, fill=WHITE)
        
        if t > 1:
            bbox2 = draw.textbbox((0,0), "Vos agents IA. Votre equipe. Votre succes.", font=font_reg)
            draw.text(((W-bbox2[2])//2, H//2 + 50), "Vos agents IA. Votre equipe. Votre succes.", font=font_reg, fill=LIGHT)
        if t > 0.5:
            fs2 = 52
            font_b2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", fs2)
            bbox3 = draw.textbbox((0,0), "Bienvenue sur", font=font_b2)
            draw.text(((W-bbox3[2])//2, H//2 - 280), "Bienvenue sur", font=font_b2, fill=LIGHT)
    
    elif t < 22:
        # SCENE 2: Leo
        lt = t - 10
        fs = 68
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fs)
        bbox = draw.textbbox((0,0), "Leo, votre agent general", font=font_b)
        draw.text(((W-bbox[2])//2, 200), "Leo, votre agent general", font=font_b, fill=WHITE)
        
        lines = ["Il comprend vos demandes", "Analyse vos besoins", "Et coordonne toute l'equipe"]
        for i, line in enumerate(lines):
            if lt > 0.5 + i * 0.6:
                font_l = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
                bbox_l = draw.textbbox((0,0), line, font=font_l)
                draw.text(((W-bbox_l[2])//2, 420 + i*60), line, font=font_l, fill=LIGHT)
    
    elif t < 38:
        # SCENE 3: Specialists
        st = t - 22
        fs = 56
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fs)
        bbox = draw.textbbox((0,0), "12 agents specialises", font=font_b)
        draw.text(((W-bbox[2])//2, 160), "12 agents specialises", font=font_b, fill=WHITE)
        
        agents = [("Marc","Prospection"), ("Sofia","Support 24/7"), ("Camille","Contenu SEO"),
                   ("Claire","Comptabilite"), ("Nadia","Closer"), ("Hugo","Telephone")]
        for i, (name, role) in enumerate(agents):
            col = i % 3
            row = i // 3
            x = 200 + col * 540
            y = 400 + row * 130
            if st > 0.3 + i * 0.3:
                # Card background
                draw.rectangle([x-130, y-15, x+330, y+85], fill=(30,40,60), outline=(60,70,100))
                font_n = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
                font_r = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
                draw.text((x-110, y+5), name, font=font_n, fill=WHITE)
                draw.text((x-110, y+45), role, font=font_r, fill=LIGHT)
    
    elif t < 52:
        # SCENE 4: Results
        rt = t - 38
        fs = 60
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fs)
        bbox = draw.textbbox((0,0), "Les resultats", font=font_b)
        draw.text(((W-bbox[2])//2, 200), "Les resultats", font=font_b, fill=WHITE)
        
        results = ["Prospection automatisee 24h/24", "Support client qui ne dort jamais",
                    "Contenu SEO publie automatiquement", "+30% de productivite"]
        for i, r in enumerate(results):
            if rt > 1 + i * 0.8:
                font_r = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30+i*2)
                bbox_r = draw.textbbox((0,0), r, font=font_r)
                draw.text(((W-bbox_r[2])//2, 400 + i*80), r, font=font_r, fill=GREEN)
    
    else:
        # SCENE 5: CTA
        ct = t - 52
        pulse = 1 + math.sin(ct * 3) * 0.03
        fs = int(140 * pulse)
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fs)
        bbox = draw.textbbox((0,0), "Bapica", font=font_b)
        draw.text(((W-bbox[2])//2, H//2-120), "Bapica", font=font_b, fill=WHITE)
        
        if ct > 2:
            font_c = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
            bbox_c = draw.textbbox((0,0), "Commencez gratuitement", font=font_c)
            draw.text(((W-bbox_c[2])//2, H//2+40), "Commencez gratuitement", font=font_c, fill=BLUE)
        if ct > 3:
            font_w = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
            bbox_w = draw.textbbox((0,0), "bapica.com", font=font_w)
            draw.text(((W-bbox_w[2])//2, H//2+120), "bapica.com", font=font_w, fill=LIGHT)
    
    img.save(f"{OUTDIR}/frame-{frame_num:05d}.png")

print(f"Generated {len(os.listdir(OUTDIR))} frames")

# Assemble video
print("Assembling video...")
subprocess.run([
    "ffmpeg", "-y",
    "-framerate", str(FPS), "-i", f"{OUTDIR}/frame-%05d.png",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
    "/tmp/bapica-video-silent.mp4"
], capture_output=True)

print("Adding audio...")
subprocess.run([
    "ffmpeg", "-y",
    "-i", "/tmp/bapica-video-silent.mp4",
    "-i", "public/bapica-presentation.mp3",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
    "-shortest", "-movflags", "+faststart",
    "public/bapica-dynamic.mp4"
], capture_output=True)

import os
size = os.path.getsize("public/bapica-dynamic.mp4")
print(f"Done! public/bapica-dynamic.mp4 ({size/1024:.0f}KB)")
