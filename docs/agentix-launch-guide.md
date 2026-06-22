# Guide de Lancement — Agentix.app

## 🎯 Nom de la plateforme : **Agentix**
**Domaine :** agentix.app

---

## 📋 Étape 1 — Créer les comptes (30 min)

### 1.1 Cloudflare → Enregistrer agentix.app
1. Va sur **https://dash.cloudflare.com/signup**
2. Crée un compte (email + mot de passe)
3. Dans le dashboard, clique sur **"Add a Site"**
4. Tape **agentix.app** → "Add"
5. Choisis le plan **Free**
6. Procède au paiement (~12-15€/an) pour enregistrer le domaine
7. Note les **Nameservers** Cloudflare (ils seront donnés après achat)

> ⚠️ Le .app **nécessite HTTPS** — Cloudflare le gère automatiquement (gratuit)

### 1.2 GitHub → Héberger le code
1. Va sur **https://github.com/signup**
2. Crée un compte (gratuit)
3. Crée un dépôt privé : **agentix-platform**
4. Note le nom d'utilisateur GitHub

### 1.3 Supabase → Base de données + Auth
1. Va sur **https://supabase.com/dashboard/sign-up**
2. Crée un compte (gratuit — **Free plan** = 500mo DB + 50k users)
3. Crée un projet : **Agentix**
4. Note dans le dashboard :
   - `Project URL` (ex: https://XXXXXXXXX.supabase.co)
   - `anon public key`
   - `service_role key` (⚠️ à garder secrète)

### 1.4 Stripe → Paiements
1. Va sur **https://dashboard.stripe.com/register**
2. Crée un compte (gratuit)
3. Active le mode **Test** (en haut à droite)
4. Va dans **Developers → API keys**
5. Note :
   - `Publishable key` (pk_test_...)
   - `Secret key` (sk_test_...)

### 1.5 Claude API → Moteur des agents IA
1. Va sur **https://console.anthropic.com/signup**
2. Crée un compte
3. Ajoute un crédit (~10$ pour commencer les tests)
4. Va dans **API Keys** → Crée une clé
5. Note la clé : `sk-ant-...`

### 1.6 Vercel → Hébergement (après avoir push le code)
1. Va sur **https://vercel.com/signup**
2. Connecte-toi avec **GitHub**
3. Importe le dépôt **agentix-platform**

---

## 🔗 Étape 2 — Connecter les services

### Configurer le projet Next.js

```bash
cd /workspace/hermes-saas/platform

# Copier le template .env
cp .env.example .env.local
```

### Remplir .env.local avec les vraies clés

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://XXXXXXXXX.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...

# Stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Claude API
ANTHROPIC_API_KEY=sk-ant-...
```

### Base de données Supabase

1. Va dans **Supabase → SQL Editor**
2. Copie-colle le contenu de `/workspace/hermes-saas/agentix-platform/supabase-schema.sql`
3. Exécute la requête pour créer les tables

### Stripe Webhook

1. Va dans **Stripe Dashboard → Developers → Webhooks**
2. Clique **"Add endpoint"**
3. URL : `https://agentix.app/api/webhooks/stripe`
4. Événements à écouter : `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
5. Note le **Webhook Secret** (whsec_...) → ajoute-le dans `.env.local`

### Vercel + Domaine

1. Va dans **Vercel Dashboard → Settings → Domains**
2. Ajoute **agentix.app**
3. Suis les instructions pour configurer les DNS chez Cloudflare

---

## 🚀 Étape 3 — Déploiement

```bash
# 1. Installer les dépendances
cd /workspace/hermes-saas/platform
npm install

# 2. Build de test en local
npm run build

# 3. Déploiement Vercel
npx vercel --prod
```

---

## ✅ Étape 4 — Tests de validation

### À vérifier après déploiement :

| Test | Statut |
|---|---|
| Landing page accessible | ⬜ |
| Inscription / Connexion | ⬜ |
| Dashboard avec stats | ⬜ |
| Sélection des 11 agents | ⬜ |
| Chat avec un agent (mode démo) | ⬜ |
| Pages Stripe (pricing) | ⬜ |
| Paramètres / API Keys | ⬜ |
| Responsive mobile | ⬜ |

---

## 📌 Récapitulatif des comptes et coûts

| Service | Plan | Coût |
|---------|------|------|
| Cloudflare | Free | ~12-15€/an (domaine) |
| GitHub | Free | 0€ |
| Supabase | Free | 0€ |
| Stripe | Free (test) | 0€ |
| Claude API | Pay-as-you-go | ~10€ (dev) |
| Vercel | Free (Hobby) | 0€ |
| **Total MVP** | | **~25€** |

---

## 🆘 Support

Si tu es bloqué à une étape, dis-moi simplement :
- "Je suis à l'étape 1.X" 
- "J'ai créé le compte [Nom], quelle est la suite ?"
- Envoie-moi les clés API par message privé une fois obtenues

Je te guiderai pas à pas pour tout connecter ! 🚀
