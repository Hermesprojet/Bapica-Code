# 🚀 Bapica — Plateforme Multi-Agents IA pour PME

## 1. Créer tes comptes (10 minutes)

### Supabase (gratuit)
1. Va sur https://supabase.com → "Start your project"
2. Crée un projet, note l'URL et la clé `anon public`
3. Va dans Authentication → Settings → confirme l'email/password comme provider

### Stripe (gratuit)
1. Va sur https://stripe.com → crée un compte
2. Va dans Products → créer 3 produits : Starter (29€), Pro (59€), Business (99€)
3. Note les Price ID de chaque produit

### Claude API (payant à l'usage)
1. Va sur https://console.anthropic.com
2. Génère une clé API → note-la

### Vercel (gratuit)
1. Va sur https://vercel.com
2. Connecte avec GitHub/GitLab

---

## 2. Déploiement (5 minutes)

```bash
# 1. Télécharge le projet
git clone <ton-repo> hermes-saas
cd hermes-saas/platform

# 2. Crée le fichier .env.local avec tes clés
cat > .env.local << 'EOF'
NEXT_PUBLIC_SUPABASE_URL=ton_url_supabase
NEXT_PUBLIC_SUPABASE_ANON_KEY=ta_cle_anon
SUPABASE_SERVICE_ROLE_KEY=ta_cle_service_role
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_STARTER_PRICE_ID=price_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_BUSINESS_PRICE_ID=price_...
CLAUDE_API_KEY=sk-ant-...
NEXT_PUBLIC_APP_URL=http://localhost:3000
EOF

# 3. Install et lance
npm install
npm run dev

# 4. Pour déployer sur Vercel
npx vercel --prod
```

---

## 3. Connexion Supabase

Dans Supabase, crée les tables suivantes via SQL Editor :

```sql
-- Table des profils utilisateurs
CREATE TABLE profiles (
  id UUID REFERENCES auth.users PRIMARY KEY,
  email TEXT,
  company_name TEXT,
  plan TEXT DEFAULT 'starter',
  stripe_customer_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table des conversations
CREATE TABLE conversations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  agent_id TEXT NOT NULL,
  messages JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Puis active Row Level Security et ajoute les policies de base.

---

## 4. Ce que tu obtiens

| Page | Description |
|---|---|
| `/` | Landing page (Hero, Features, 11 agents, Pricing, FAQ, CTA) |
| `/signup` | Inscription |
| `/login` | Connexion |
| `/dashboard` | Tableau de bord avec stats |
| `/dashboard/agents` | Sélection des 11 agents |
| `/dashboard/agents/[id]` | Chat avec un agent |
| `/dashboard/billing` | Gestion abonnement |
| `/dashboard/settings` | API keys, profil, langue |

---

## 5. Prochaines étapes (après déploiement)

1. ✅ **Landing page** — Déjà faite
2. ⬜ **Stripe webhook** — Connecter les paiements réels
3. ⬜ **API Claude réelle** — Remplacer la réponse simulée dans `api/chat/route.ts`
4. ⬜ **n8n workflows** — Importer les templates d'automatisation
5. ⬜ **Vapi** — Connecter les agents vocaux
6. ⬜ **Beta testeurs** — Trouver 5-10 PME pour tester

---

## 6. Budget pour le lancement

| Poste | Coût |
|---|---|
| Domaine Bapica.com | ~15€/an |
| Vercel (gratuit) | 0€ |
| Supabase (gratuit) | 0€ |
| Claude API (test) | ~5-10€ |
| Stripe | 0€ (+ frais par transaction) |
| **Total** | **~20€** |

Bonne chance avec Bapica ! 🚀
