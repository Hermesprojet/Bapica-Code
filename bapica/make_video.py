#!/usr/bin/env python3
"""Bapica explainer video - dynamic motion graphics style like Substi.ai"""

import subprocess
import os
import math

W, H = 1920, 1080
FPS = 60
OUTPUT = "public/bapica-dynamic.mp4"
AUDIO = "public/bapica-presentation.mp3"

# Get audio duration
result = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", AUDIO],
    capture_output=True, text=True
)
duration = float(result.stdout.strip())
print(f"Duration: {duration}s")

# Create dynamic segments with smooth zoom/pan/fade
# Each segment has its own animation effect

def make_segment(text_lines, out_file, duration, effect="zoom", subtitle=""):
    """Create a video segment with animated text + effects"""
    
    total_frames = int(duration * FPS)
    
    # Build drawtext filters for each line of text with animations
    filters = []
    
    # Animated background gradient (subtle color shift)
    filters.append(
        f"color=c=0x061126:s={W}x{H}:d={duration},"
        f"format=rgba,"
        f"geq=r='r+5*sin(2*PI*T/4)':g='g+3*sin(2*PI*T/3)':b='b+8*sin(2*PI*T/5)',"
        f"format=yuv420p[bg]"
    )
    
    # Animated text lines
    y_spacing = 90
    start_y = (H - len(text_lines) * y_spacing) // 2
    
    text_filters = []
    for i, (text, size, bold) in enumerate(text_lines):
        y = start_y + i * y_spacing
        
        # Text with fade-in and subtle floating motion
        fontfile = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        
        # Animated text: fades in from 0s to 0.8s, then floats gently
        text_filter = (
            f"drawtext=fontfile={fontfile}:"
            f"text='{text}':"
            f"fontsize={size}:"
            f"fontcolor=white@0.95:"
            f"x=(w-text_w)/2:"
            f"y={y}+3*sin(2*PI*t/6):"
            f"alpha='if(lt(t,0.3),0,if(lt(t,0.8),(t-0.3)/0.5,1))'"
        )
        text_filters.append(text_filter)
    
    joined = "[bg]" + ",".join(text_filters)
    
    # Build the ffmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        f"color=c=0x061126:s={W}x{H}:d={duration}:r={FPS}",
        "-vf", ",".join(text_filters),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "23", "-pix_fmt", "yuv420p",
        "-an",
        out_file
    ]
    
    subprocess.run(cmd, capture_output=True)
    return out_file


# Create segments
segments = []

# Segment 1: Welcome (0-10s) - zoom in effect
make_segment(
    [("Bienvenue sur", 52, False), ("Bapica", 100, True), ("Vos agents IA. Votre équipe. Votre succès.", 34, False)],
    "/tmp/seg1.mp4", 10, "zoom"
)
segments.append("/tmp/seg1.mp4")

# Segment 2: Léo (10-22s) - slide in from right
make_segment(
    [("Léo, votre agent général", 64, True), ("Il comprend, analyse, et coordonne", 34, False), ("Dites-lui ce dont vous avez besoin", 30, False)],
    "/tmp/seg2.mp4", 12, "slide"
)
segments.append("/tmp/seg2.mp4")

# Segment 3: Specialists (22-38s)
make_segment(
    [("12 agents spécialisés", 56, True), ("Prospection • Support • Contenu • Compta", 30, False), ("Chaque métier a son agent IA", 30, False)],
    "/tmp/seg3.mp4", 16, "zoom"
)
segments.append("/tmp/seg3.mp4")

# Segment 4: Results (38-52s)
make_segment(
    [("Les résultats", 60, True), ("Automatisé 24h/24", 38, False), ("Productivité +30% en moyenne", 38, False), ("Vous avez enfin du temps", 34, False)],
    "/tmp/seg4.mp4", 14, "slide"
)
segments.append("/tmp/seg4.mp4")

# Segment 5: CTA (52-63s)
make_segment(
    [("Bapica", 100, True), ("Commencez gratuitement", 44, False), ("bapica.com", 36, False)],
    "/tmp/seg5.mp4", 11, "zoom"
)
segments.append("/tmp/seg5.mp4")

# Assemble segments with crossfade transitions
print("Assemblage...")
concat_inputs = []
concat_filter = ""
for i, seg in enumerate(segments):
    concat_inputs.extend(["-i", seg])

# Simple concat (no crossfade for now - ffmpeg crossfade is complex)
concat_file = "/tmp/concat.txt"
with open(concat_file, "w") as f:
    for seg in segments:
        f.write(f"file '{seg}'\n")

subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", concat_file,
    "-i", AUDIO,
    "-c:v", "libx264", "-preset", "fast",
    "-crf", "23", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest", "-movflags", "+faststart",
    OUTPUT
], capture_output=True)

print(f"Done: {OUTPUT}")
