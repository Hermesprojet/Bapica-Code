#!/usr/bin/env bash
# ============================================================
# Hermes SaaS — Script de démarrage rapide
# Génère la structure Next.js + Tailwind + Supabase
# Usage: bash setup-saas.sh
# ============================================================
set -euo pipefail

PROJECT="hermes-saas"
echo "🚀 Création du projet SaaS multi-agents : $PROJECT"

mkdir -p "$PROJECT"
cd "$PROJECT"

# Structure des dossiers
mkdir -p \
  agents/prompts \
  agents/configs \
  agents/logs \
  platform/lib \
  platform/components/ui \
  platform/components/agents \
  platform/components/dashboard \
  platform/components/landing \
  platform/components/auth \
  platform/pages/api \
  platform/pages/dashboard \
  platform/styles \
  platform/public/images \
  platform/public/icons \
  platform/types \
  supabase/migrations \
  supabase/seed \
  n8n/workflows \
  n8n/credentials \
  docs

# Fichiers clés
cat > platform/README.md << 'EOF'
# Hermes SaaS — Plateforme multi-agents IA

## Structure
- `/agents` — Prompts système et configs des 11 agents
- `/platform` — App Next.js (frontend + API)
- `/supabase` — Base de données et migrations
- `/n8n` — Workflows d'automatisation
- `/docs` — Documentation

## Démarrage rapide
```bash
npm install
npm run dev
```
EOF

cat > n8n/README.md << 'EOF'
# Workflows n8n pour Hermes SaaS

Importer les workflows JSON depuis `/workflows` dans n8n.
Les credentials sont à configurer dans l'interface n8n.

Workflows disponibles :
- prospect-lead-scoring.json — Score et qualification leads
- content-publishing.json — Publication automatique contenu
- invoice-followup.json — Relances factures impayées
- support-triage.json — Tri automatique tickets support
EOF

cat > supabase/README.md << 'EOF'
# Base de données Supabase

## Tables principales
- users — Profils utilisateurs (lié à auth.users)
- organizations — Entreprises clientes
- subscriptions — Abonnements Stripe
- agents_config — Configuration des agents par org
- conversations — Historique des conversations
- leads — Prospects générés
- invoices — Factures et devis
- analytics_events — Événements d'analyse

## Migration
```bash
npx supabase link --project-ref <ref>
npx supabase db push
```
EOF

# .env.example
cat > .env.example << 'EOF'
# Base de données
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# Agents IA
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Services vocaux
VAPI_API_KEY=
ELEVENLABS_API_KEY=

# Automatisation
N8N_URL=http://localhost:5678
N8N_API_KEY=

# App
NEXT_PUBLIC_APP_URL=http://localhost:3000
EOF

echo "✅ Structure créée avec succès !"
echo ""
echo "📁 Contenu du projet :"
find . -type d | sort | head -30
