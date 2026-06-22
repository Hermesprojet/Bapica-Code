# Hermes SaaS — Configuration & Roadmap
# Plateforme multi-agents IA pour PME
# Multilingue : Français / Anglais / Arabe

## Stack Technologique Complète

### Frontend
- Next.js 14 (App Router)
- Tailwind CSS + shadcn/ui
- Framer Motion (animations)
- Recharts (graphiques dashboard)
- React Hook Form + Zod (formulaires)

### Backend & Auth
- Supabase (PostgreSQL + Auth + Realtime)
- Stripe (abonnements)
- Resend (emails transactionnels)

### Agents IA
- Claude API (agent principal — recommandé ratio qualité/prix)
- OpenAI API (fallback)
- Vapi (voix IA sortante/entrante)
- ElevenLabs (voix naturelle)
- HeyGen (avatars vidéo)
- Runway (génération vidéo)

### Automatisation
- n8n (self-hosted ou cloud)

### Hébergement
- Vercel (frontend + API routes)
- Render (n8n)
- Supabase Cloud (DB)

## Roadmap Semaine par Semaine

### Semaine 1 : Infrastructure + Landing Page
```bash
# 1.1 Créer le projet Next.js
npx create-next-app@latest . --typescript --tailwind --app
npm install @supabase/supabase-js @supabase/ssr
npm install @radix-ui/react-* framer-motion recharts
npm install stripe @stripe/stripe-js lucide-react
npm install react-hook-form zod @hookform/resolvers

# 1.2 Configurer Supabase
# Aller sur https://supabase.com → New project
# Copier URL et anon key dans .env.local

# 1.3 Landing page (hero, features, pricing, FAQ, CTA)
```
**Livrable :** Landing page en ligne sur Vercel 🎉

### Semaine 2 : Auth + Dashboard
- Inscription/Connexion avec Supabase Auth (magic link + email)
- Route protégée /dashboard
- Layout dashboard avec sidebar
- Profil utilisateur

### Semaine 3 : Abonnements Stripe
- Webhook Stripe → Supabase
- 3 formules : Starter (29€) / Pro (59€) / Business (99€)
- Gestion automatique des accès selon abonnement
- Portail client Stripe

### Semaine 4 : Interface des agents
- Page de sélection des agents accessibles
- Configuration par agent (API key entreprise, paramètres)
- Interface de chat avec chaque agent
- Historique des conversations

### Semaine 5 : API Gateway des agents
- API route `/api/chat` qui route vers le bon modèle
- Rate limiting par abonnement
- Logging et monitoring
- Mode démo gratuit (3 messages)

### Semaine 6-7 : Test utilisateur + Lancement
- Tests avec 5-10 PME bêta
- Corrections et améliorations
- Mise en production
- Campagne de lancement

## Script de démarrage (Semaine 1)

```bash
# Après avoir créé le projet Next.js
cd hermes-saas/platform
npm install
npm run dev
```

## Variables d'environnement nécessaires

```env
# Fichier .env.local (NE JAMAIS COMMIT)
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
VAPI_API_KEY=
ELEVENLABS_API_KEY=
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Budget Démarrage

| Poste | Coût |
|---|---|
| Supabase Free | 0€ |
| Vercel Free | 0€ |
| Domaine (.fr) | ~10€/an |
| OpenAI API (dev) | ~20€ |
| Claude API (dev) | ~20€ |
| Stripe | 0€ (frais par transaction) |
| n8n self-hosted | 0€ |
| **Total démarrage** | **~50€** |
