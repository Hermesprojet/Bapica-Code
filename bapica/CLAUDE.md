# Bapica — Référence du projet

> Fichier de contexte unique. Un agent (Claude Code ou l'agent QA) doit lire CE fichier
> avant de tester ou modifier Bapica, au lieu de re-parcourir tout le code.
> À tenir à jour quand l'architecture, les agents, les plans ou les capacités changent.

## 1. Ce qu'est Bapica

Bapica est une plateforme SaaS multi-agents IA pour PME et indépendants. Elle fournit **13 agents
IA spécialisés** qui **automatisent le contact et les tâches métier** — y compris **contacter et
répondre aux clients par téléphone et par email**, pas seulement organiser des données.

Positionnement à ne jamais contredire dans les réponses des agents :
- Bapica **n'est pas un simple CRM** ni un outil d'organisation passif.
- Plusieurs agents **agissent directement auprès des clients** de l'utilisateur.
- Réponse attendue si on demande « les agents peuvent-ils contacter/appeler/répondre aux
  clients par téléphone ou email ? » → **OUI**, en citant l'agent concerné.
- Interdits dans les réponses : « je ne peux pas contacter vos clients », « c'est une limite
  volontaire », « vos clients ont besoin de vous parler à vous ».

- Site : bapica.com (prod Vercel : bapica-code.vercel.app)
- Multilingue : FR / EN / AR (détection automatique dans les prompts).

## 2. Stack technique

- **Next.js 14.2.35** (App Router, dossier `src/`), TypeScript strict.
- **Tailwind CSS**.
- **Supabase** : auth + base de données (Postgres). Schéma : `supabase-schema.sql`.
- **Stripe** : abonnements (checkout + portail + webhook).
- **Anthropic Claude** : moteur des agents (`@anthropic-ai/sdk`).
- **OpenAI** : embeddings pour le RAG.
- Intégrations optionnelles : Vapi (vocal), HeyGen/Runway (vidéo), Resend (email), Twenty (CRM), n8n.
- Déploiement : **Vercel, Root Directory = `bapica`** (l'app n'est pas à la racine du repo).

## 3. Les 13 agents (source : `src/lib/agents.ts`)

| id | Persona | Rôle | Formule min |
|----|---------|------|-------------|
| `general` | Léo | Agent Général (point d'entrée, aiguillage) | Essentiel |
| `support` | Sofia | Support Client — répond aux clients par chat/email 24/7 | Essentiel |
| `content` | Camille | Créateur de Contenu (SEO, posts, newsletters) | Essentiel |
| `prospection-strategie` | Marc | Conseiller Croissance & Prospection | Essentiel |
| `closer` | Nadia | Closer Vocal — appelle et qualifie les prospects | Essentiel |
| `telephone` | Hugo | Agent Téléphonique — standard, appels entrants | Pro |
| `accounting` | Claire | Comptabilité — factures, relances email, trésorerie | Pro |
| `video` | Maya | Créateur Vidéo IA | Essentiel |
| `recruiter` | Yanis | Recruteur IA | Essentiel |
| `legal` | Inès | Administratif & Juridique (info générale, pas de conseil perso) | Essentiel |
| `analytics` | Tom | Analytics & Reporting | Pro |
| `trends` | Lina | Tendances Google / veille marché | Essentiel |
| `scaling` | Roxane | Croissance & Scaling (systématiser, déléguer, automatiser) | Pro |

- **Prompts de rôle** (RÔLE / MÉTHODE / RÈGLES) : `src/lib/agent-prompts.ts`
  → injectés via `getSystemPromptForAgent(id)` dans `/api/chat` ET `/api/demo-chat`.
- **Contenu marketing** des pages agents : `src/lib/agent-content.ts`.
- Règle : légal (Inès) et comptabilité (Claire) ne remplacent JAMAIS un professionnel.

## 4. Plans & tarifs (source : `src/lib/stripe.ts`)

- **Essentiel** — 49 €/mois — 8 agents.
- **Pro** — 79 €/mois — 13 agents, messages illimités.
- Essai gratuit : 15 jours. Appels vocaux facturés ~0,20 €/min.
- Variables prix : `STRIPE_PRICE_ESSENTIAL`, `STRIPE_PRICE_PRO`.

## 5. Routes API principales (`src/app/api/`)

| Route | Rôle | Auth |
|-------|------|------|
| `chat` | Chat des agents (dashboard, connecté) | Bearer token Supabase |
| `demo-chat` | Démo publique (3 messages, sans compte, modèle Haiku) | Aucune |
| `stripe/checkout` | Crée la session de paiement | userId côté client |
| `stripe/portal` | Portail de gestion d'abonnement | userId |
| `webhooks/stripe` | Met à jour le plan dans `profiles` (client service_role) | Signature Stripe |
| `vapi/create-call` | Lance un appel vocal sortant (Vapi) | Bearer token |
| `vapi/webhook` | Reçoit le résultat d'appel Vapi | — |
| `video/orchestrate` | Maya — idée → package de production complet (script, storyboard, prompts moteurs) | Bearer token |
| `video/generate` | Rendu direct via moteur (Runway/HeyGen) — nécessite les clés | Bearer token |

(Autres routes : cortex, genesis, reason, business-analysis, market-intelligence, etc.)

## 6. Fichiers clés

- `src/lib/agents.ts` — définition des 13 agents (SOURCE DE VÉRITÉ des agents).
- `src/lib/agent-prompts.ts` — rôle/méthode/règles par agent.
- `src/lib/supabase.ts` / `supabase-admin.ts` — clients Supabase (lazy).
- `src/lib/stripe.ts` — client Stripe (lazy) + plans + `planFromPriceId`.
- `src/lib/rag.ts` — RAG (recherche de connaissances par agent, embeddings OpenAI).
- `src/app/api/chat/route.ts` — cœur du chat connecté (auth, mémoire, RAG, live data, tools).
- `src/app/api/demo-chat/route.ts` — démo publique.

## 7. Variables d'environnement

**Requises pour le fonctionnement de base :**
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`ANTHROPIC_API_KEY`, `NEXT_PUBLIC_APP_URL`.

**Paiement :** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`,
`STRIPE_PRICE_ESSENTIAL`, `STRIPE_PRICE_PRO`.

**RAG / intégrations (optionnelles) :** `OPENAI_API_KEY` (embeddings), `VAPI_*` (vocal),
`HEYGEN_*` / `RUNWAY_API_KEY` (vidéo), `RESEND_API_KEY` (email), `TWILIO_*`, `N8N_*`.

Détail : `.env.example`.

## 8. Règles & pièges connus (IMPORTANT pour ne pas casser le build)

1. **Ne JAMAIS instancier Supabase/Stripe au niveau module.** `createClient(...)` / `new Stripe(...)`
   exécuté à l'import fait échouer le build Vercel (« supabaseUrl is required »,
   « collect page data » qui plante). Toujours **instanciation paresseuse** (dans une fonction,
   au runtime). Idem pour tout SDK qui lève une erreur si sa clé est absente.
2. **Auth des routes connectées** : le client envoie `Authorization: Bearer <access_token>`.
   Côté serveur, valider avec `supabase.auth.getUser(token)` — jamais `getUser()` sans argument
   (sinon 401 systématique).
3. **Versions de dépendances figées** (versions exactes dans `package.json`). Next.js 14.2.x.
4. **Modèles Claude valides uniquement** : `claude-sonnet-4-5`, `claude-haiku-4-5`,
   `claude-opus-4-1` (voir `resolveModel` / `optimizations.ts`). Pas d'ID inventé.
5. **Outils CRM (twentyTools)** réservés aux agents commerciaux (`prospection-strategie`,
   `closer`) — pas à l'agent général, sinon il se prend pour un CRM.
6. **Prompts** : ton pro et sobre, prose naturelle, pas d'émojis, pas de Markdown brut
   (les bulles n'affichent pas `**`/`#`).

## 9. Procédure de test / QA

Avant de conclure « ça marche », exécuter dans `bapica/` :

```bash
npm install
npx tsc --noEmit        # 0 erreur de type
npm run build           # doit finir EXIT 0 (surveiller "supabaseUrl is required")
```

Puis tests runtime (serveur local `npm run start` sur un PORT) :
- `/` → 200
- `/api/demo-chat` (POST `{message}`) → réponse ou 503 si pas de clé (jamais 500 non géré)
- `/api/chat` sans token → 401 ; avec token invalide → 401
- Pages agents `/agents/<id>` → 200 ; id inconnu → 404

Cohérence produit à vérifier dans les réponses des agents :
- « Les agents peuvent-ils contacter mes clients par téléphone/email ? » → doit répondre **OUI**
  en citant Sofia (chat/email), Hugo (téléphone), Nadia (appels), Claire (relances email).
- Chaque agent respecte son rôle (Marc demande le contexte avant de prospecter, Inès renvoie
  vers un avocat, Tom réclame les chiffres, etc.).

## 10bis. Design / thème (IMPORTANT)

- **Thème = CLAIR** (fond blanc, style épuré inspiré de Substi.ai). Ne pas réintroduire de fond sombre.
- Le système de couleurs vit dans `src/app/globals.css` : tokens HSL dans `:root` + classes custom
  (`card-professional`, `feature-card`, `pricing-card`, `agent-card`, `section-tinted`, `gradient-hero`,
  `gradient-text`, `btn-primary`…). Changer le thème = éditer CE fichier, pas chaque composant.
- Couleur primaire = bleu **#2563EB** (`--primary: 221 83% 53%`), texte **#111827**, accent teal **#0d9488**.
- La home (`src/app/page.tsx`) code ses couleurs en dur (blanc/#111827/#2563EB) et n'utilise PAS les
  composants `src/components/landing/*` (thème sombre, en grande partie orphelins) — seuls Navbar/Footer
  en sont importés.
- Exceptions volontairement sombres (bandeaux d'accent sur page claire) : sections `Chiffres`/`CTAFinal`
  de la home, le slideshow `video-presentation.tsx`.

## 10ter. Maya — Studio Vidéo (cerveau d'orchestration)

- Maya = directrice créative IA. Le « cerveau » (`src/lib/video/maya.ts`) transforme une idée en
  **package de production** JSON : concept, hook, storyboard scène par scène (décor/lumière/caméra/
  mouvement/émotion/dialogue/SFX/durée), **prompt visuel prêt par moteur**, voix/musique/sous-titres,
  formats, CTA, titre, description, hashtags. Route : `POST /api/video/orchestrate` (Bearer + Claude Sonnet).
- Routeur multi-moteurs (dans le prompt) : avatar→HeyGen, cinématique→Runway, ultra-réaliste→Veo,
  stylisé→Kling, motion→Luma. Maya ne REND pas de MP4 depuis le cerveau ; le rendu est une couche à part.
- **Rendu réel** (`src/lib/video/engines.ts`) : Runway (texte→image→vidéo, 2 étapes), HeyGen (avatar parlant),
  ElevenLabs (voix off). Routes `POST /api/video/render` (action `scene`|`animate`|`voice`) et
  `POST /api/video/status` (polling). ÉCRIT À L'AVEUGLE (non testable en sandbox : pas de clés + réseau
  bloqué) → les erreurs moteurs sont remontées brutes pour le débogage en prod. Peut nécessiter un
  ajustement des paramètres d'API au 1er test réel.
- Clés requises en prod pour le rendu : `RUNWAY_API_KEY` ; `HEYGEN_API_KEY` + `HEYGEN_AVATAR_ID` +
  `HEYGEN_VOICE_ID` ; `ELEVENLABS_API_KEY` (+ `ELEVENLABS_VOICE_ID` optionnel).
- Le **montage final** (assembler clips + voix + sous-titres + musique en 1 MP4) n'est PAS fait (exige ffmpeg).
- UI : `dashboard/video-studio` (thème clair) — brief → `ProductionPackageView`
  (`src/components/agents/production-package.tsx`), avec « Générer le clip » par scène + « Générer la voix off ».

## 10. Déploiement

- Branche de dev : `claude/hopeful-gates-nucb4p` → PR → merge dans `master` → Vercel déploie.
- Vérifier après déploiement que le build Vercel est **Ready** (pas seulement le build local).
- Si un agent « ne répond pas » : d'abord vérifier que le **build Vercel a réussi** (souvent la
  vraie cause), puis les variables d'env (`ANTHROPIC_API_KEY`, Supabase).
