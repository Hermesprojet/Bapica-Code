// Bapica explainer video - dynamic motion graphics
// p5.js animation rendered to frames

const W = 1920;
const H = 1080;
const TOTAL_FRAMES = 60 * 65; // 65 seconds at 60fps
const NAVY = [6, 17, 38];
const WHITE = [255, 255, 255];
const ACCENT = [45, 85, 155];
const LIGHT = [180, 195, 220];

let frame = 0;
let particles = [];

function setup() {
  createCanvas(W, H);
  // Create floating particles for background
  for (let i = 0; i < 30; i++) {
    particles.push({
      x: random(W), y: random(H),
      vx: random(-0.5, 0.5), vy: random(-0.3, 0.3),
      size: random(2, 8), alpha: random(20, 60)
    });
  }
}

function draw() {
  background(NAVY);
  
  // Animated particles
  for (let p of particles) {
    p.x += p.vx; p.y += p.vy;
    if (p.x < 0) p.x = W;
    if (p.x > W) p.x = 0;
    if (p.y < 0) p.y = H;
    if (p.y > H) p.y = 0;
    noStroke();
    fill(ACCENT[0], ACCENT[1], ACCENT[2], p.alpha);
    ellipse(p.x, p.y, p.size, p.size);
  }
  
  let t = frame / 60; // time in seconds
  
  // Scene-based animations
  if (t < 10) {
    // SCENE 1: Welcome
    let progress = t / 10;
    let y = H/2 - 120 + sin(t * 2) * 10;
    textSize(100 * easeOut(progress));
    textAlign(CENTER);
    fill(255, 255 * easeIn(progress + 0.2));
    text("Bapica", W/2, y + 100);
    
    textSize(34 * easeOut(progress + 0.3));
    fill(180, 195, 220, 255 * easeIn(progress + 0.5));
    text("Vos agents IA. Votre équipe. Votre succès.", W/2, y + 200);
    
  } else if (t < 22) {
    // SCENE 2: Léo
    let lt = t - 10;
    let bounce = abs(sin(lt * 1.5)) * 15;
    
    // Floating icon circles
    for (let i = 0; i < 4; i++) {
      let cx = W/4 - 80 + i * 200;
      let cy = H/2 + sin(lt * 2 + i) * 30;
      let colors = [[59,130,246],[34,197,94],[234,179,8],[239,68,68]];
      fill(colors[i]);
      ellipse(cx, cy, 80 + bounce, 80 + bounce);
    }
    
    textSize(60);
    fill(WHITE);
    textAlign(CENTER);
    text("Léo, votre agent général", W/2, 250);
    
    textSize(30);
    fill(LIGHT);
    text("Il comprend, analyse, et coordonne votre équipe IA", W/2, 600);
    
  } else if (t < 38) {
    // SCENE 3: Specialists
    let st = t - 22;
    textSize(56);
    fill(WHITE);
    textAlign(CENTER);
    text("12 agents spécialisés", W/2, 200);
    
    let agents = [
      ["Marc", "Prospection"],
      ["Sofia", "Support 24/7"],
      ["Camille", "Contenu SEO"],
      ["Claire", "Comptabilité"],
      ["Nadia", "Closer"],
      ["Hugo", "Téléphone"]
    ];
    
    for (let i = 0; i < agents.length; i++) {
      let col = i % 3;
      let row = floor(i / 3);
      let x = 300 + col * 460;
      let y = 400 + row * 130;
      let a = min(1, (st - i * 0.3) * 2);
      let cardY = y - 20 * (1 - easeOut(a));
      
      // Card
      fill(30, 40, 60, 200 * a);
      noStroke();
      rectMode(CENTER);
      rect(x, cardY, 400, 100, 12);
      
      textSize(28);
      fill(255, 255 * a);
      textAlign(LEFT);
      text(agents[i][0], x - 160, cardY - 10);
      textSize(20);
      fill(LIGHT[0], LIGHT[1], LIGHT[2], 200 * a);
      text(agents[i][1], x - 160, cardY + 25);
    }
    
  } else if (t < 52) {
    // SCENE 4: Results
    let rt = t - 38;
    let results = [
      "Prospection automatisée 24h/24",
      "Support client qui ne dort jamais",
      "Contenu SEO publié automatiquement",
      "+30% de productivité"
    ];
    
    textSize(56);
    fill(WHITE);
    textAlign(CENTER);
    text("Les résultats", W/2, 200);
    
    for (let i = 0; i < results.length; i++) {
      let a = min(1, (rt - i * 0.5) * 1.5);
      let x = W/2 + (1 - easeOut(a)) * 100;
      fill(255, 255 * a);
      textSize(30 + i * 2);
      text("✓  " + results[i], x, 400 + i * 80);
    }
    
  } else {
    // SCENE 5: CTA
    let ct = t - 52;
    let pulse = 1 + sin(ct * 3) * 0.05;
    
    textSize(120 * pulse);
    fill(WHITE);
    textAlign(CENTER);
    text("Bapica", W/2, H/2 - 50);
    
    textSize(40);
    fill(ACCENT);
    text("Commencez gratuitement", W/2, H/2 + 80);
    textSize(28);
    fill(LIGHT);
    text("bapica.com", W/2, H/2 + 140);
  }
  
  // Record frame
  if (frame < TOTAL_FRAMES) {
    saveCanvas("frame-" + nf(frame, 5), "png");
    frame++;
  } else {
    noLoop();
    print("DONE");
  }
}

function easeOut(t) { return t < 0 ? 0 : t > 1 ? 1 : 1 - pow(1 - t, 3); }
function easeIn(t) { return t < 0 ? 0 : t > 1 ? 1 : pow(t, 3); }
