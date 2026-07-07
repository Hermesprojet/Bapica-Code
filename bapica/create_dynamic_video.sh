#!/bin/bash
# Bapica explainer video - dynamic motion graphics
# Multi-scene animated text video with smooth transitions

AUDIO="public/bapica-presentation.mp3"
OUT="public/bapica-dynamic.mp4"

W=1920
H=1080
FPS=60

# Générer un fond animé avec gradient mouvant
ffmpeg -y -f lavfi -i "color=c=0x061126:s=${W}x${H}:d=65:r=${FPS}" \
  -vf "
    geq=r='6+15*sin(2*PI*T/8)':g='17+8*sin(2*PI*T/6)':b='38+12*sin(2*PI*T/10)',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Bapica':fontsize=110:fontcolor=white@0.8:x=(w-text_w)/2:y=(h-text_h)/2-200:enable='between(t,0,10)':alpha='if(lt(t,0.5),0,if(lt(t,1.5),(t-0.5),min(1,if(lt(t,9),1,(10-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Vos agents IA. Votre equipe. Votre succes.':fontsize=38:fontcolor=white@0.7:x=(w-text_w)/2:y=(h-text_h)/2-70:enable='between(t,0.8,10)':alpha='if(lt(t,1),0,if(lt(t,2),(t-1),min(1,if(lt(t,9),1,(10-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Leo, votre agent general':fontsize=64:fontcolor=white@0.85:x=(w-text_w)/2:y=(h-text_h)/2-120:enable='between(t,10,22)':alpha='if(lt(t,10.3),0,if(lt(t,11.3),(t-10.3),min(1,if(lt(t,21),1,(22-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Il comprend, analyse, et coordonne toute l equipe':fontsize=34:fontcolor=white@0.7:x=(w-text_w)/2:y=(h-text_h)/2+20:enable='between(t,11,22)':alpha='if(lt(t,11.5),0,if(lt(t,12.5),(t-11.5),min(1,if(lt(t,21),1,(22-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='12 agents specialises':fontsize=56:fontcolor=white@0.85:x=(w-text_w)/2:y=(h-text_h)/2-200:enable='between(t,22,38)':alpha='if(lt(t,22.5),0,if(lt(t,23.5),(t-22.5),min(1,if(lt(t,36),1,(38-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Marc - Prospection':fontsize=28:fontcolor=white@0.7:x=100:y=450:enable='between(t,23.5,38)':alpha='if(lt(t,23.5),0,if(lt(t,24.5),(t-23.5),min(1,if(lt(t,36),1,(38-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Sofia - Support 24/7':fontsize=28:fontcolor=white@0.7:x=100:y=530:enable='between(t,24.5,38)':alpha='if(lt(t,24.5),0,if(lt(t,25.5),(t-24.5),min(1,if(lt(t,36),1,(38-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Camille - Contenu SEO':fontsize=28:fontcolor=white@0.7:x=100:y=610:enable='between(t,25.5,38)':alpha='if(lt(t,25.5),0,if(lt(t,26.5),(t-25.5),min(1,if(lt(t,36),1,(38-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Claire - Comptabilite':fontsize=28:fontcolor=white@0.7:x=100:y=690:enable='between(t,26.5,38)':alpha='if(lt(t,26.5),0,if(lt(t,27.5),(t-26.5),min(1,if(lt(t,36),1,(38-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Les resultats':fontsize=60:fontcolor=white@0.85:x=(w-text_w)/2:y=(h-text_h)/2-200:enable='between(t,38,52)':alpha='if(lt(t,38.5),0,if(lt(t,39.5),(t-38.5),min(1,if(lt(t,50),1,(52-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Automatise 24h/24':fontsize=34:fontcolor=#00cc66@0.8:x=(w-text_w)/2:y=(h-text_h)/2+40:enable='between(t,40,52)':alpha='if(lt(t,40.5),0,if(lt(t,41.5),(t-40.5),min(1,if(lt(t,50),1,(52-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='+30% de productivite':fontsize=34:fontcolor=#00cc66@0.8:x=(w-text_w)/2:y=(h-text_h)/2+100:enable='between(t,42,52)':alpha='if(lt(t,42.5),0,if(lt(t,43.5),(t-42.5),min(1,if(lt(t,50),1,(52-t)))))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Bapica':fontsize=120:fontcolor=white@0.9:x=(w-text_w)/2:y=(h-text_h)/2-120:enable='between(t,52,65)',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Commencez gratuitement':fontsize=44:fontcolor=#5088cc@0.8:x=(w-text_w)/2:y=(h-text_h)/2+40:enable='between(t,54,65)':alpha='if(lt(t,54),0,if(lt(t,55),(t-54),1))',
    drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='bapica.com':fontsize=30:fontcolor=white@0.6:x=(w-text_w)/2:y=(h-text_h)/2+110:enable='between(t,55,65)':alpha='if(lt(t,55.5),0,if(lt(t,56.5),(t-55.5),1))'
  " \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
  /tmp/bapica-base.mp4 2>&1 | tail -3

echo "Base video: $(ls -lh /tmp/bapica-base.mp4 2>/dev/null | awk '{print $5}')"

# Add audio
ffmpeg -y -i /tmp/bapica-base.mp4 -i "$AUDIO" \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart \
  "$OUT" 2>&1 | tail -2

echo "Final: $(ls -lh $OUT 2>/dev/null | awk '{print $5}')"