// Maya — Directeur créatif IA (cerveau d'orchestration vidéo, façon Alexya).
// Ce module NE génère pas de MP4 : il transforme une idée en package de
// production complet (concept, script, storyboard scène par scène, prompts
// visuels prêts pour chaque moteur, voix, musique, sous-titres, formats).
// Le rendu réel (Runway / Veo / HeyGen / Kling…) est une couche séparée qui
// s'active quand les clés API correspondantes sont configurées.

export type VideoEngine = 'Runway' | 'Veo' | 'HeyGen' | 'Kling' | 'Luma' | 'Best Available'

export interface ProductionScene {
  n: number
  title: string
  duration: string          // ex : "0-3s"
  decor: string
  lighting: string          // éclairage
  mood: string              // ambiance
  cameraAngle: string       // angle de caméra
  cameraMovement: string    // mouvement de caméra
  emotion: string
  dialogue: string          // dialogue / voix off de la scène
  sfx: string               // effets sonores
  visualPrompt: string      // prompt EN, optimisé pour le moteur recommandé
  recommendedEngine: VideoEngine
}

export interface ProductionPackage {
  concept: string
  hook: string              // accroche 0-3s
  platform: string
  objective: string
  ratio: string             // ex : "9:16"
  totalDuration: string
  audience: string
  language: string
  scenes: ProductionScene[]
  voiceover: { profile: string; tone: string; provider: string }
  music: string
  sfxOverall: string
  subtitles: { style: string; animation: string }
  formatVariants: string[]  // TikTok, Reels, Shorts, Pub Meta, VSL…
  cta: string
  title: string             // titre YouTube
  description: string
  hashtags: string[]
  primaryEngine: VideoEngine
}

export interface MayaBrief {
  idea: string
  platform?: string         // TikTok | Reels | Shorts | YouTube | Meta Ad | VSL
  objective?: string        // vente | publicité | storytelling | UGC | formation
  duration?: string         // ex : "20s"
  style?: string            // UGC, cinématique, corporate…
  audience?: string
  language?: string         // fr | en | …
  voice?: string            // femme | homme | énergique…
  avatar?: boolean          // présentateur qui parle face caméra ?
}

// Règles de routage : quel moteur pour quel type de plan (le « cerveau »).
export const ENGINE_ROUTING = `Règles de routage vers le moteur de génération (choisis recommendedEngine par scène et primaryEngine global) :
- Présentateur / avatar qui parle face caméra, lip-sync → "HeyGen"
- Publicité cinématique, image→vidéo, transitions léchées → "Runway"
- Plan ultra-réaliste (produit, humain photoréaliste, "commercial") → "Veo"
- Style anime, stylisé, illustratif → "Kling"
- Motion design, logo animé, texte animé, parallax d'image fixe → "Luma"
- En cas de doute → "Best Available"`

export function buildMayaSystemPrompt(): string {
  return `Tu es Maya, directrice créative IA de Bapica, spécialisée dans la production de vidéos virales prêtes à publier (niveau Alexya.ai).

À partir d'une simple idée, tu conçois un PACKAGE DE PRODUCTION complet et exploitable, pas de vagues conseils. Tu maximises la rétention, le taux de clic, le temps de visionnage, la viralité et le rythme narratif.

Pour chaque demande :
1. Comprends le public cible, l'objectif (vente / pub / storytelling / UGC / formation), la plateforme et le format.
2. Écris un HOOK puissant (0-3 secondes) qui stoppe le scroll.
3. Écris un script optimisé, puis découpe-le en SCÈNES.
4. Pour CHAQUE scène, précise : décor, éclairage, ambiance, angle de caméra, mouvement de caméra, émotion, dialogue/voix off, effets sonores, durée.
5. Pour CHAQUE scène, écris un "visualPrompt" EN ANGLAIS, ultra détaillé et prêt à coller dans un moteur de génération (caméra, objectif, lumière, ambiance, style, 4K, etc.) — jamais une phrase vague comme "une femme court".
6. Choisis le meilleur moteur par scène et global.
7. Ajoute : direction voix off, musique, SFX, style de sous-titres, adaptation par format, CTA final, titre, description, hashtags.

${ENGINE_ROUTING}

CONTRAINTE DE SORTIE ABSOLUE :
Réponds UNIQUEMENT avec un objet JSON valide (aucun texte avant/après, pas de balises Markdown, pas de \`\`\`). Le JSON DOIT respecter EXACTEMENT ce schéma :
{
  "concept": "string",
  "hook": "string",
  "platform": "string",
  "objective": "string",
  "ratio": "string",
  "totalDuration": "string",
  "audience": "string",
  "language": "string",
  "scenes": [{
    "n": 1,
    "title": "string",
    "duration": "string",
    "decor": "string",
    "lighting": "string",
    "mood": "string",
    "cameraAngle": "string",
    "cameraMovement": "string",
    "emotion": "string",
    "dialogue": "string",
    "sfx": "string",
    "visualPrompt": "string (EN ANGLAIS)",
    "recommendedEngine": "Runway|Veo|HeyGen|Kling|Luma|Best Available"
  }],
  "voiceover": { "profile": "string", "tone": "string", "provider": "ElevenLabs" },
  "music": "string",
  "sfxOverall": "string",
  "subtitles": { "style": "string", "animation": "string" },
  "formatVariants": ["string"],
  "cta": "string",
  "title": "string",
  "description": "string",
  "hashtags": ["string"],
  "primaryEngine": "Runway|Veo|HeyGen|Kling|Luma|Best Available"
}

Tous les champs textuels (sauf visualPrompt qui reste en anglais pour les modèles) sont rédigés dans la langue du brief (français par défaut). 3 à 6 scènes selon la durée. Sois concret, professionnel, orienté performance.`
}

export function buildMayaUserPrompt(brief: MayaBrief): string {
  const lines = [
    `Idée : ${brief.idea}`,
    brief.platform ? `Plateforme : ${brief.platform}` : 'Plateforme : à déduire (défaut TikTok, 9:16)',
    brief.objective ? `Objectif : ${brief.objective}` : '',
    brief.duration ? `Durée cible : ${brief.duration}` : '',
    brief.style ? `Style : ${brief.style}` : '',
    brief.audience ? `Public : ${brief.audience}` : '',
    brief.language ? `Langue : ${brief.language}` : 'Langue : français',
    brief.voice ? `Voix off : ${brief.voice}` : '',
    typeof brief.avatar === 'boolean' ? `Avatar parlant : ${brief.avatar ? 'oui' : 'non'}` : '',
  ].filter(Boolean)
  return lines.join('\n')
}

// Extrait un objet JSON depuis une réponse LLM (tolère le texte parasite / fences).
export function parseProductionPackage(raw: string): ProductionPackage {
  let text = raw.trim()
  // Retire d'éventuelles fences Markdown.
  text = text.replace(/^```(?:json)?/i, '').replace(/```$/i, '').trim()
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start === -1 || end === -1 || end <= start) {
    throw new Error('Réponse Maya sans JSON exploitable')
  }
  const json = text.slice(start, end + 1)
  const pkg = JSON.parse(json) as ProductionPackage
  if (!Array.isArray(pkg.scenes) || pkg.scenes.length === 0) {
    throw new Error('Package de production sans scènes')
  }
  return pkg
}
