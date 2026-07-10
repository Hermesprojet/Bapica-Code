#!/usr/bin/env python3
"""Vidéo Bapica — 11 agents + Conseiller Croissance en vedette"""

from PIL import Image, ImageDraw, ImageFont
import subprocess, os

W, H = 1920, 1080
BG = (13, 13, 26)
FG = (245, 245, 247)
MUTED = (161, 161, 170)
BLUE = (0, 130, 230)
TEAL = (45, 212, 191)
EMERALD = (16, 185, 129)
OUT = "/tmp/bapica-frames2"
os.makedirs(OUT, exist_ok=True)

try:
    bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    reg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    big_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
except:
    bold = reg = title_font = big_font = ImageFont.load_default()

def draw_centered(d, text, y, font, color=FG):
    bbox = d.textbbox((0,0), text, font=font)
    tw = bbox[2] - bbox[0]
    d.text(((W-tw)//2, y), text, fill=color, font=font)

def gradient_bg(img):
    """Dégradé bleu-émeraude"""
    for y in range(H):
        r = int(13 + (0 - 13) * y/H)
        g = int(13 + (130 - 13) * y/H * 0.3)
        b = int(26 + (129 - 26) * y/H * 0.5)
        for x in range(W):
            img.putpixel((x, y), (r, g, b))

# ===== SCENE 1 (0-5s): Dashboard/accroche =====
def scene1():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    # Fond avec micro-grille
    for x in range(0, W, 40):
        d.line([(x,0),(x,H)], fill=(255,255,255,4), width=1)
    for y in range(0, H, 40):
        d.line([(0,y),(W,y)], fill=(255,255,255,4), width=1)
    
    draw_centered(d, "Votre PME mérite", 300, title_font, FG)
    draw_centered(d, "une équipe qui ne dort jamais", 380, title_font, TEAL)
    
    # Barres de croissance animées (simulées statiques)
    for i in range(5):
        h = 80 + i * 40
        x = 500 + i * 160
        d.rectangle([x, 600-h, x+100, 600], fill=TEAL+(80,), outline=TEAL+(40,))
    
    draw_centered(d, "Bapica", 720, big_font, BLUE)
    return img

# ===== SCENE 2 (5-13s): Grille 11 agents =====
def scene2():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    
    draw_centered(d, "11 agents IA spécialisés", 200, title_font, FG)
    draw_centered(d, "prêts à travailler pour vous", 270, bold, TEAL)
    
    agents = [
        ("🧠", "Léo", "Général"), ("💬", "Sofia", "Support"), ("✏️", "Camille", "Contenu"),
        ("📈", "Marc", "Croissance"), ("📞", "Nadia", "Closer"), ("☎️", "Hugo", "Téléphone"),
        ("🧮", "Claire", "Comptabilité"), ("🎬", "Maya", "Vidéo"), ("🔍", "Yanis", "Recrutement"),
        ("⚖️", "Inès", "Juridique"), ("📊", "Tom", "Analytics")
    ]
    
    for i, (icon, name, _) in enumerate(agents):
        col = i % 3
        row = i // 3
        x = 280 + col * 500
        y = 380 + row * 130
        
        # Carte agent
        d.rounded_rectangle([x, y, x+420, y+100], radius=12, fill=(255,255,255,6), outline=(255,255,255,10))
        d.text((x+20, y+15), icon, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32))
        d.text((x+70, y+20), name, fill=BLUE, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22))
    
    # Highlight Marc
    d.rounded_rectangle([280, 380, 700, 480], radius=12, fill=(0,130,230,20), outline=BLUE+(60,))
    
    return img

# ===== SCENE 3 (13-28s): Conseiller Croissance focus =====
def scene3():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    
    draw_centered(d, "⭐ Conseiller Croissance & Prospection", 150, title_font, TEAL)
    
    # Chat simulé
    chat_y = 300
    messages = [
        ("🤖", "Voici 3 prospects qualifiés dans votre secteur...", BLUE),
        ("👤", "Parfait ! Rédige les messages", MUTED),
        ("🤖", "Messages LinkedIn prêts :", BLUE),
        ("✅", "3 leads qualifiés • 85% de taux d'ouverture", EMERALD),
    ]
    
    for avatar, msg, color in messages:
        d.rounded_rectangle([300, chat_y, 1620, chat_y+60], radius=12, fill=(255,255,255,4), outline=(255,255,255,8))
        d.text((320, chat_y+10), avatar, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24))
        d.text((370, chat_y+15), msg, fill=color, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22))
        chat_y += 75
    
    # Graphique CA en hausse
    d.text((300, 650), "CA", fill=EMERALD, font=bold)
    for i in range(8):
        h = 20 + i * 25
        x = 420 + i * 140
        d.rectangle([x, 720-h, x+100, 720], fill=EMERALD+(100,), outline=EMERALD+(60,))
    
    return img

# ===== SCENE 4 (28-40s): Split-screen agents =====
def scene4():
    img = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(img)
    
    draw_centered(d, "Toute votre entreprise, automatisée", 120, title_font, FG)
    
    scenes = [
        ("📞 Support 24/7", "Réponses instantanées", 100, 250),
        ("📄 Juridique", "Contrats sécurisés", 660, 250),
        ("📊 Analytics", "Décisions éclairées", 100, 480),
        ("🎬 Vidéo", "Contenu pro en 1 clic", 660, 480),
        ("☎️ Téléphone", "Appels gérés", 100, 710),
        ("🔍 Recrutement", "CV triés auto", 660, 710),
    ]
    
    for title, desc, x, y in scenes:
        d.rounded_rectangle([x, y, x+480, y+180], radius=16, fill=(255,255,255,5), outline=(255,255,255,8))
        d.text((x+24, y+20), title, fill=TEAL, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22))
        d.text((x+24, y+65), desc, fill=MUTED, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20))
    
    return img

# ===== SCENE 5 (40-48s): Logo + CTA =====
def scene5():
    img = Image.new('RGB', (W,H), (5, 30, 50))
    d = ImageDraw.Draw(img)
    
    # Fond dégradé bleu-émeraude
    for y in range(H):
        ratio = y / H
        r = int(5 + (13-5) * ratio)
        g = int(30 + (130-30) * ratio * 0.5)
        b = int(50 + (129-50) * ratio * 0.5)
        for x in range(W):
            img.putpixel((x, y), (r, g, b))
    
    draw_centered(d, "Bapica", 300, big_font, FG)
    draw_centered(d, "11 agents. Une seule plateforme.", 420, bold, TEAL)
    draw_centered(d, "Essayez gratuitement", 520, title_font, FG)
    
    # CTA button
    d.rounded_rectangle([660, 620, 1260, 700], radius=16, fill=BLUE)
    d.text((690, 635), "bapica.com  →", fill=(255,255,255), font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36))
    
    return img

# ===== Génération =====
scenes = [scene1, scene2, scene3, scene4, scene5]
durations = [5, 8, 15, 12, 8]  # secondes

print("Génération frames...")
all_frames = []
for i, fn in enumerate(scenes):
    img = fn()
    path = f"{OUT}/s{i}.png"
    img.save(path)
    n = durations[i] * 25
    all_frames.extend([path] * n)

with open(f"{OUT}/frames.txt", "w") as f:
    for frame in all_frames:
        f.write(f"file '{frame}'\nduration {1/25}\n")

print(f"Combinaison {len(all_frames)} frames + audio...")
subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", f"{OUT}/frames.txt",
    "-i", "/tmp/bapica-voiceover.mp3",
    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
    "-shortest", "-movflags", "+faststart",
    "/root/bapica/bapica/public/bapica-11agents.mp4"
], check=True)

print("✅ /root/bapica/bapica/public/bapica-11agents.mp4")
