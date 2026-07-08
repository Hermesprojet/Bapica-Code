#!/usr/bin/env python3
"""Salesforce-style product demo video for Bapica"""

from PIL import Image, ImageDraw, ImageFont
import os, subprocess, math

W, H = 1920, 1080
FPS = 30
OUTDIR = "/tmp/bapica-demo-frames"
os.makedirs(OUTDIR, exist_ok=True)

# Couleurs Bapica
NAVY = (6, 17, 38)
WHITE = (255, 255, 255)
GRAY = (180, 195, 220)
GREEN = (34, 197, 94)
BLUE = (45, 90, 158)
PURPLE = (139, 92, 246)
AMBER = (245, 158, 11)

# Polices
try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 96)
except:
    font_title = ImageFont.load_default()
    font_sub = font_title
    font_small = font_title
    font_big = font_title

def draw_rounded_rect(draw, xy, radius, fill, outline=None):
    """Draw rounded rectangle"""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline)

def draw_annotation(draw, x, y, text, color=WHITE):
    """Draw an annotation arrow + text like Salesforce demos"""
    # Circle
    r = 16
    draw.ellipse([x-r, y-r, x+r, y+r], outline=color, width=3)
    # Arrow
    draw.line([x, y-r-10, x, y-40], fill=color, width=3)
    # Text bg
    bbox = draw.textbbox((0,0), text, font=font_small)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw_rounded_rect(draw, (x+15, y-60, x+15+tw+20, y-60+th+16), 8, color)
    draw.text((x+25, y-58), text, fill=NAVY, font=font_small)

def ease_out(t):
    return 1 - (1-t)**3

def ease_in_out(t):
    return 3*t*t - 2*t*t*t

total_frames = int(48.3 * FPS)  # 1449 frames
print(f"Generating {total_frames} frames...")

frame = 0
last_pct = -1

# === SCENE 1: Logo + hook (0-6s) ===
for i in range(0, int(6 * FPS)):
    img = Image.new("RGB", (W,H), NAVY)
    draw = ImageDraw.Draw(img)
    t = i / (6*FPS)
    
    # Animated gradient background
    for y in range(H):
        alpha = math.sin(y/200 + t*2) * 0.05
        c = int(6 + alpha*50)
        draw.line([(0,y), (W,y)], fill=(c, c+5, c+25))
    
    # Bapica logo
    opacity = min(1, t*3)
    draw_rounded_rect(draw, (W//2-120, H//2-120, W//2+120, H//2+120), 30, BLUE)
    draw.text((W//2, H//2-30), "B", fill=WHITE, font=font_big, anchor="mm")
    
    # Subtitle
    if t > 0.5:
        alpha_sub = min(1, (t-0.5)*3)
        sub_c = tuple(int(GRAY[i]*alpha_sub) for i in range(3))
        draw.text((W//2, H//2+150), "Vos agents IA. Votre succès.", fill=sub_c, font=font_sub, anchor="mm")
    
    img.save(f"{OUTDIR}/frame-{frame:05d}.png")
    frame += 1

# === SCENE 2: Problem → Solution (6-14s) ===
for i in range(0, int(8 * FPS)):
    img = Image.new("RGB", (W,H), NAVY)
    draw = ImageDraw.Draw(img)
    t = i / (8*FPS)
    
    # Left: Problem
    draw_rounded_rect(draw, (60, 200, 600, 500), 16, (40, 10, 10))
    draw.text((330, 250), "❌ AVANT", fill=(220, 50, 50), font=font_title, anchor="mm")
    items = ["Prospection manuelle", "Support 9h-18h", "Admin qui s'accumule", "32h/semaine perdues"]
    for j, item in enumerate(items):
        y = 340 + j*45
        draw.text((100, y), f"• {item}", fill=WHITE, font=font_small)
    
    # Center: Arrow
    if t > 1:
        arrow_x = 680 + int(min(1, (t-1)*2) * 300)
        draw.text((arrow_x, 350), "→", fill=GREEN, font=font_big)
    
    # Right: Solution
    if t > 1.5:
        draw_rounded_rect(draw, (1020, 200, 1860, 700), 16, (10, 40, 20))
        draw.text((1440, 280), "✅ APRÈS", fill=GREEN, font=font_title, anchor="mm")
        solutions = ["Prospection IA 24/7", "Support automatique", "Admin 100% automatisée", "32h économisées"]
        for j, sol in enumerate(solutions):
            y = 370 + j*45
            draw.text((1060, y), f"✓ {sol}", fill=WHITE, font=font_small)
    
    img.save(f"{OUTDIR}/frame-{frame:05d}.png")
    frame += 1

# === SCENE 3: Product demo - Dashboard (14-26s) ===
for i in range(0, int(12 * FPS)):
    img = Image.new("RGB", (W,H), NAVY)
    draw = ImageDraw.Draw(img)
    t = i / (12*FPS)
    
    # Browser frame
    draw_rounded_rect(draw, (60, 40, 1860, 1040), 12, (240,240,250))
    # Browser bar
    draw_rounded_rect(draw, (60, 40, 1860, 72), 12, (230,230,240))
    draw.text((120, 56), "bapica.com", fill=(100,100,120), font=font_small)
    
    # Dashboard content
    # Score card
    draw_rounded_rect(draw, (120, 120, 560, 320), 12, WHITE)
    draw.text((340, 160), "Score de Santé", fill=(100,100,120), font=font_small, anchor="mm")
    draw.text((340, 240), "72", fill=GREEN, font=font_big, anchor="mm")
    draw.text((340, 290), "/100", fill=(150,150,170), font=font_small, anchor="mm")
    
    # ROI card
    draw_rounded_rect(draw, (620, 120, 1060, 320), 12, WHITE)
    draw.text((840, 160), "ROI Estimé", fill=(100,100,120), font=font_small, anchor="mm")
    draw.text((840, 240), "850€/mois", fill=GREEN, font=font_title, anchor="mm")
    
    # Agents card
    draw_rounded_rect(draw, (1120, 120, 1800, 320), 12, WHITE)
    draw.text((1460, 160), "Agents Recommandés", fill=(100,100,120), font=font_small, anchor="mm")
    agents = ["Prospecteur", "Support", "Contenu"]
    for j, a in enumerate(agents):
        draw_rounded_rect(draw, (1160, 200+j*40, 1760, 230+j*40), 8, BLUE)
        draw.text((1460, 215+j*40), a, fill=WHITE, font=font_small, anchor="mm")
    
    # Annotations zoom (Salesforce style)
    if t > 2 and t < 6:
        draw_annotation(draw, 340, 240, "Score de maturité", GREEN)
    if t > 4 and t < 8:
        draw_annotation(draw, 840, 240, "Économies estimées", GREEN)
    if t > 6:
        draw_annotation(draw, 1460, 215, "3 agents prêts", PURPLE)
    
    img.save(f"{OUTDIR}/frame-{frame:05d}.png")
    frame += 1

# === SCENE 4: Agents in action (26-38s) ===
agents_visual = [
    ("Marc", "Prospection", BLUE, "50 appels/jour"),
    ("Sofia", "Support 24/7", GREEN, "140 langues"),
    ("Claire", "Comptabilité", PURPLE, "Factures auto"),
]
for i in range(0, int(12 * FPS)):
    img = Image.new("RGB", (W,H), NAVY)
    draw = ImageDraw.Draw(img)
    t = i / (12*FPS)
    
    for j, (name, role, color, stat) in enumerate(agents_visual):
        x = 160 + j * 570
        local_t = max(0, min(1, t*3 - j*0.8))
        y_offset = int((1 - ease_out(local_t)) * 80)
        
        draw_rounded_rect(draw, (x, 200+y_offset, x+500, 700+y_offset), 20, (20,30,50))
        draw_rounded_rect(draw, (x+150, 280+y_offset, x+350, 480+y_offset), 100, color)
        draw.text((x+250, 380+y_offset), name[0], fill=WHITE, font=font_big, anchor="mm")
        draw.text((x+250, 520+y_offset), name, fill=WHITE, font=font_title, anchor="mm")
        draw.text((x+250, 590+y_offset), role, fill=GRAY, font=font_sub, anchor="mm")
        draw_rounded_rect(draw, (x+100, 630+y_offset, x+400, 670+y_offset), 20, color)
        draw.text((x+250, 650+y_offset), stat, fill=WHITE, font=font_small, anchor="mm")
    
    img.save(f"{OUTDIR}/frame-{frame:05d}.png")
    frame += 1

# === SCENE 5: Results + CTA (38-48s) ===
for i in range(0, int(10.3 * FPS)):
    img = Image.new("RGB", (W,H), NAVY)
    draw = ImageDraw.Draw(img)
    t = i / (10.3*FPS)
    
    # Results grid
    results = [
        ("3×", "plus de leads", GREEN),
        ("32h", "économisées/sem", BLUE),
        ("80%", "réduction coûts", AMBER),
        ("55%", "réponses en +", PURPLE),
    ]
    
    for j, (val, label, color) in enumerate(results):
        x = 100 + j * 440
        draw_rounded_rect(draw, (x, 250, x+400, 550), 20, (20,30,50))
        draw.text((x+200, 340), val, fill=color, font=font_big, anchor="mm")
        draw.text((x+200, 440), label, fill=WHITE, font=font_sub, anchor="mm")
    
    # CTA
    if t > 2:
        cta_opacity = min(1, (t-2)*2)
        cta_y = 680 + int((1-ease_out(cta_opacity)) * 30)
        draw_rounded_rect(draw, (660, cta_y, 1260, cta_y+100), 16, BLUE)
        draw.text((960, cta_y+50), "Commencer gratuitement →", fill=WHITE, font=font_title, anchor="mm")
        draw.text((960, cta_y+110), "bapica.com", fill=GRAY, font=font_small, anchor="mm")
    
    img.save(f"{OUTDIR}/frame-{frame:05d}.png")
    frame += 1

print(f"Generated {frame} frames. Assembling video...")

# Rename frames to sequential
import glob
frames = sorted(glob.glob(f"{OUTDIR}/frame-*.png"))
for i, f in enumerate(frames):
    new_name = f"{OUTDIR}/frame-{i:05d}.png"
    if f != new_name:
        os.rename(f, new_name)

# ffmpeg assemble
out = "public/bapica-salesforce-demo.mp4"
subprocess.run([
    "ffmpeg", "-y", "-framerate", str(FPS),
    "-i", f"{OUTDIR}/frame-%05d.png",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
    "-pix_fmt", "yuv420p", "/tmp/bapica-silent.mp4"
], check=True, capture_output=True)

# Add audio
subprocess.run([
    "ffmpeg", "-y",
    "-i", "/tmp/bapica-silent.mp4",
    "-i", "/tmp/bapica-demo-audio.mp3",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
    "-shortest", out
], check=True, capture_output=True)

size = os.path.getsize(out)
print(f"Done! {out} ({size//1024}KB)")
