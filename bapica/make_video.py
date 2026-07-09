#!/usr/bin/env python3
"""Crée une vidéo MP4 avec slides + voix off ElevenLabs"""

from PIL import Image, ImageDraw, ImageFont
import subprocess, os

W, H = 1920, 1080
BG = (13, 13, 26)        # #0d0d1a
FG = (245, 245, 247)     # #f5f5f7
MUTED = (161, 161, 170)  # #a1a1aa
ACCENT = (0, 130, 230)   # #0082e6
TEAL = (45, 212, 191)    # #2dd4bf
OUTDIR = "/tmp/bapica-frames"
os.makedirs(OUTDIR, exist_ok=True)

def draw_text(draw, text, y, size=48, color=FG, bold=False, max_w=1600):
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except:
        font = ImageFont.load_default()
    # Centrer
    bbox = draw.textbbox((0,0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y), text, fill=color, font=font)
    return y + size + 20

def draw_label(draw, text, y):
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except:
        font = ImageFont.load_default()
    # Label pill background
    bbox = draw.textbbox((0,0), text.upper(), font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    x = (W - tw - 40) // 2
    draw.rounded_rectangle([x, y-2, x+tw+40, y+th+10], radius=20, fill=(45,212,191,20), outline=(45,212,191,40))
    draw.text((x+20, y+5), text.upper(), fill=TEAL, font=font)
    return y + 40

# Slide functions
def make_slide1():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    y = 300
    y = draw_label(d, "Présentation", y)
    y += 20
    y = draw_text(d, "Des agents IA qui comprennent", y, 72, bold=True)
    draw_text(d, "votre business", y, 72, TEAL, bold=True)
    y += 100
    draw_text(d, "13 agents spécialisés. Une plateforme. Zéro configuration.", y+30, 28, MUTED)
    return img

def make_slide2():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    y = 250
    y = draw_label(d, "Le constat", y)
    y += 20
    draw_text(d, "32 heures par semaine perdues", y, 56, bold=True)
    y += 100
    # 3 cards
    cards = [("📞 Appels manqués", "Chaque appel sans réponse = un client perdu"),
             ("📧 Admin chronophage", "Factures, relances, devis — des heures"),
             ("🔍 Prospection lente", "70% du temps commercial sans outil")]
    for i, (title, desc) in enumerate(cards):
        cx = 160 + i * 560
        d.rounded_rectangle([cx, y, cx+480, y+200], radius=16, fill=(255,255,255,8), outline=(255,255,255,15))
        draw_text(d, title, y+30, 28, bold=True)
        draw_text(d, desc, y+80, 22, MUTED)
    return img

def make_slide3():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    y = 200
    y = draw_label(d, "La solution", y)
    y += 20
    draw_text(d, "Une équipe d'agents IA qui", y, 56, bold=True)
    draw_text(d, "travaille pour vous", y+60, 56, TEAL, bold=True)
    y += 140
    agents = [("L", "Léo", "Coordinateur", (59,130,246)), ("S", "Sofia", "Support", (16,185,129)),
              ("M", "Marc", "Commercial", (245,158,11)), ("R", "Roxane", "Croissance", (139,92,246)),
              ("C", "Camille", "Contenu", (236,72,153)), ("H", "Hugo", "Téléphone", (6,182,212))]
    for i, (letter, name, role, color) in enumerate(agents):
        col = i % 3
        row = i // 3
        ax = 300 + col * 480
        ay = y + row * 120
        # Avatar circle
        d.ellipse([ax, ay, ax+50, ay+50], fill=color)
        d.text((ax+13, ay+8), letter, fill=(255,255,255), font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24))
        d.text((ax+65, ay+5), name, fill=FG, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22))
        d.text((ax+65, ay+30), role, fill=MUTED, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16))
    return img

def make_slide4():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    y = 300
    y = draw_label(d, "Résultats", y)
    y += 20
    draw_text(d, "Mesurable. Immédiat.", y, 56, bold=True)
    y += 120
    stats = [("3×", "plus de leads qualifiés"), ("32h", "économisées / semaine"), ("−80%", "de coûts vs un employé")]
    for i, (val, label) in enumerate(stats):
        sx = 240 + i * 520
        draw_text(d, val, y, 80, TEAL, bold=True)
        draw_text(d, label, y+90, 24, MUTED)
    return img

def make_slide5():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    y = 300
    y = draw_label(d, "Pourquoi Bapica", y)
    y += 20
    draw_text(d, "13 agents coordonnés.", y, 56, bold=True)
    draw_text(d, "Une seule plateforme.", y+60, 56, TEAL, bold=True)
    y += 140
    cards = [("🧠 IA Supérieure", "Claude Sonnet vs GPT-4o-mini"),
             ("📊 Business Intelligence", "Analyse stratégique et ROI"),
             ("🤝 Coordination native", "Léo orchestre l'équipe")]
    for i, (title, desc) in enumerate(cards):
        cx = 160 + i * 560
        d.rounded_rectangle([cx, y, cx+480, y+160], radius=16, fill=(255,255,255,8), outline=(255,255,255,15))
        draw_text(d, title, y+20, 28, bold=True)
        draw_text(d, desc, y+70, 22, MUTED)
    return img

def make_slide6():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    y = 280
    y = draw_label(d, "Tarifs", y)
    y += 20
    draw_text(d, "Simple. Transparent.", y, 56, bold=True)
    y += 120
    # Essential
    d.rounded_rectangle([400, y, 830, y+300], radius=24, fill=(255,255,255,5), outline=(255,255,255,15))
    draw_text(d, "Essentiel", y+30, 28, MUTED, max_w=400, bold=True)
    draw_text(d, "49€", y+80, 56, bold=True)
    draw_text(d, "/mois", y+80, 24, MUTED)
    draw_text(d, "8 agents IA", y+160, 24, MUTED)
    draw_text(d, "Messages illimités", y+190, 24, MUTED)
    # Pro
    d.rounded_rectangle([900, y, 1330, y+300], radius=24, fill=(0,130,230,15), outline=(0,130,230,50))
    draw_text(d, "Pro", y+30, 28, MUTED, max_w=400, bold=True)
    draw_text(d, "79€", y+80, 56, bold=True)
    draw_text(d, "/mois", y+80, 24, MUTED)
    draw_text(d, "13 agents IA", y+160, 24, MUTED)
    draw_text(d, "Appels 0,20€/min", y+190, 24, MUTED)
    return img

def make_slide7():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    y = 350
    draw_text(d, "Prêt à automatiser", y, 72, bold=True)
    draw_text(d, "votre croissance ?", y+80, 72, TEAL, bold=True)
    y += 160
    draw_text(d, "15 jours d'essai gratuit. Sans CB.", y, 28, MUTED)
    y += 50
    # CTA button
    d.rounded_rectangle([710, y, 1210, y+70], radius=14, fill=ACCENT)
    draw_text(d, "bapica.com  →", y+15, 28, (255,255,255), bold=True)
    return img

slides = [make_slide1, make_slide2, make_slide3, make_slide4, make_slide5, make_slide6, make_slide7]
durations = [5, 6, 7, 5, 6, 6, 5]  # seconds per slide

# Generate all frames
print("Generating frames...")
all_frames = []
for i, slide_fn in enumerate(slides):
    img = slide_fn()
    path = f"{OUTDIR}/slide{i}.png"
    img.save(path)
    # Repeat each frame for its duration at 25fps
    n_frames = durations[i] * 25
    all_frames.extend([path] * n_frames)

# Write frame list
with open(f"{OUTDIR}/frames.txt", "w") as f:
    for frame in all_frames:
        f.write(f"file '{frame}'\n")
        f.write(f"duration {1/25}\n")

# Combine frames into video + add audio
print(f"Combining {len(all_frames)} frames...")
subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", f"{OUTDIR}/frames.txt",
    "-i", "/tmp/bapica-audio.mp3",
    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k",
    "-shortest",
    "-movflags", "+faststart",
    "/root/bapica/bapica/public/bapica-video.mp4"
], check=True)

print("Done! /root/bapica/bapica/public/bapica-video.mp4")
