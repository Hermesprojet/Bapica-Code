from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1920, 1080
slides_dir = "public/video-slides"
os.makedirs(slides_dir, exist_ok=True)

NAVY = (6, 17, 38)
WHITE = (255, 255, 255)
LIGHT = (180, 190, 210)
ACCENT = (80, 120, 180)
GRADIENT_TOP = (25, 55, 95)
GRADIENT_BOT = (15, 30, 55)

font_paths = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

def load_font(size, bold=False):
    path = font_paths[0 if bold else 1]
    return ImageFont.truetype(path, size)

def gradient_bg(w, h):
    img = Image.new('RGB', (w, h))
    for y in range(h):
        r = int(GRADIENT_TOP[0] + (GRADIENT_BOT[0] - GRADIENT_TOP[0]) * y / h)
        g = int(GRADIENT_TOP[1] + (GRADIENT_BOT[1] - GRADIENT_TOP[1]) * y / h)
        b = int(GRADIENT_TOP[2] + (GRADIENT_BOT[2] - GRADIENT_TOP[2]) * y / h)
        for x in range(w):
            img.putpixel((x, y), (r, g, b))
    return img

def draw_centered(draw, text, y, font, color=WHITE):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) // 2, y), text, font=font, fill=color)

# SLIDE 1: Welcome
img = gradient_bg(W, H)
draw = ImageDraw.Draw(img)
draw_centered(draw, "Bienvenue sur", 350, load_font(48), LIGHT)
draw_centered(draw, "Bapica", 430, load_font(96, True), WHITE)
draw_centered(draw, "Vos agents IA. Votre equipe. Votre succes.", 580, load_font(32), LIGHT)
img.save(f"{slides_dir}/01-welcome.png")

# SLIDE 2: Leo
img = gradient_bg(W, H)
draw = ImageDraw.Draw(img)
draw_centered(draw, "Leo, votre agent general", 300, load_font(60, True), WHITE)
lines = ["Il comprend vos besoins", "Analyse vos demandes", "Et coordonne toute l'equipe"]
for i, line in enumerate(lines):
    draw_centered(draw, line, 420 + i * 60, load_font(32), LIGHT)
img.save(f"{slides_dir}/02-leo.png")

# SLIDE 3: Specialists
img = Image.new('RGB', (W, H), NAVY)
draw = ImageDraw.Draw(img)
draw_centered(draw, "12 agents specialises", 200, load_font(56, True), WHITE)
agents = [
    ("Marc", "Prospection LinkedIn"),
    ("Sofia", "Support client 24/7"),
    ("Camille", "Contenu and SEO"),
    ("Claire", "Comptabilite"),
    ("Nadia", "Closer telephonique"),
    ("Hugo", "Standard virtuel"),
]
for i, (name, role) in enumerate(agents):
    col = i % 3
    row = i // 3
    x = 250 + col * 480
    y = 380 + row * 140
    draw.text((x, y), name, font=load_font(36, True), fill=WHITE)
    draw.text((x, y + 50), role, font=load_font(22), fill=LIGHT)
img.save(f"{slides_dir}/03-specialists.png")

# SLIDE 4: Results
img = gradient_bg(W, H)
draw = ImageDraw.Draw(img)
draw_centered(draw, "Les resultats", 300, load_font(60, True), WHITE)
results = [
    "Prospection automatisee 24h/24",
    "Support client qui ne dort jamais",
    "Contenu SEO publie automatiquement",
    "Factures et compta a jour",
    "+30% de productivite en moyenne",
]
for i, r in enumerate(results):
    draw_centered(draw, r, 430 + i * 70, load_font(30), LIGHT)
img.save(f"{slides_dir}/04-results.png")

# SLIDE 5: CTA
img = gradient_bg(W, H)
draw = ImageDraw.Draw(img)
draw_centered(draw, "Bapica", 350, load_font(96, True), WHITE)
draw_centered(draw, "Vos agents IA. Votre equipe. Votre succes.", 500, load_font(32), LIGHT)
draw_centered(draw, "Commencez gratuitement sur bapica.com", 600, load_font(28), ACCENT)
img.save(f"{slides_dir}/05-cta.png")

print("5 slides creees")
