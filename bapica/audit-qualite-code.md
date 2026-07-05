# 🔍 Audit Qualité Code — Bapica

**Date** : 2026-07-05
**Périmètre** : `src/` (62 fichiers TypeScript/TSX)
**Total lignes** : 6 973 lignes

---

## 1. 📏 Fichiers > 300 lignes (seuil critique)

| Fichier | Lignes | Recommandation |
|---|---|---|
| `src/app/onboarding/page.tsx` | **756** ⚠️ | À découper en plusieurs composants : chaque étape du wizard mérite son propre composant (Step0Activity, Step1AdminTasks, Step2Contact, Step3Apps, Step4Analyse, Step5Recommandation). |
| `src/components/landing/needs-finder.tsx` | **306** | Frôle le seuil ; pourrait être split en composants Step + Result distincts. |

---

## 2. 📝 TODO / FIXME : 4 occurences

| Fichier | Ligne | Contenu |
|---|---|---|
| `src/app/api/chat/route.ts` | 87 | `TODO: Vérifier l'abonnement de l'utilisateur et le rate limiting` |
| `src/app/api/vapi/create-call/route.ts` | 79 | `TODO: Sauvegarder l'appel dans Supabase (table à ajouter au schéma)` |
| `src/app/api/vapi/webhook/route.ts` | 11 | `TODO: Sauvegarder dans Supabase` |
| `src/app/dashboard/settings/page.tsx` | 12 | `TODO: Sauvegarder dans Supabase` |

Ces 4 TODO concernent des fonctionnalités manquantes (persistance, rate limiting).

---

## 3. 🖨️ console.log / console.error : 11 occurences

**Tous les logs sont dans des routes API** (pas de log côté client).  
⚠️ `console.log` (pas `.error`) repéré dans :
- `src/app/api/vapi/webhook/route.ts:9` — **log info en production** (événement webhook Vapi)

Les 10 autres sont des `console.error` dans des catch blocks → acceptable en l'état mais devrait migrer vers un logger structuré (pino/winston) pour la production.

| Fichier | Lignes | Type |
|---|---|---|
| `src/app/api/vapi/webhook/route.ts` | 9, 17 | `log` + `error` |
| `src/app/api/vapi/create-call/route.ts` | 72, 82 | `error` |
| `src/app/api/chat/route.ts` | 93 | `error` |
| `src/app/api/demo-chat/route.ts` | 101 | `error` |
| `src/app/api/stripe/checkout/route.ts` | 40 | `error` |
| `src/app/api/stripe/portal/route.ts` | 41 | `error` |
| `src/app/api/video/generate/route.ts` | 87, 106 | `error` |
| `src/app/api/webhooks/stripe/route.ts` | 93 | `error` |

---

## 4. 🧹 Imports inutilisés

| Fichier | Ligne | Import non utilisé |
|---|---|---|
| `src/app/onboarding/page.tsx` | 6 | `Bot`, `FileText`, `Phone`, `Zap`, `Shield` (5 icônes lucide-react importées mais jamais utilisées dans le JSX) |

---

## 5. ✅ Erreurs TypeScript

`tsc --noEmit` passe **sans aucune erreur** ✓ — le projet est propre côté types.

---

## 6. 🔐 .env.example vs code source

### Variables dans `.env.example` mais **non utilisées** dans le code :
| Variable | Statut |
|---|---|
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Jamais référencée |
| `OPENAI_API_KEY` | Jamais référencée |
| `ELEVENLABS_API_KEY` | Jamais référencée |
| `RUNWAY_API_KEY` | Jamais référencée |
| `TWILIO_ACCOUNT_SID` | Jamais référencée |
| `TWILIO_AUTH_TOKEN` | Jamais référencée |
| `TWILIO_PHONE_NUMBER` | Jamais référencée |
| `N8N_URL` | Jamais référencée |
| `N8N_API_KEY` | Jamais référencée |
| `RESEND_API_KEY` | Jamais référencée |

→ Ces 10 variables sont probablement prévues pour des intégrations futures. À documenter comme "à venir" ou à retirer temporairement.

### Variables utilisées dans le code et bien documentées dans `.env.example` : 14 ✓
`NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ESSENTIAL`, `STRIPE_PRICE_PRO`, `ANTHROPIC_API_KEY`, `VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, `VAPI_PHONE_NUMBER_ID`, `HEYGEN_API_KEY`, `HEYGEN_AVATAR_ID`, `HEYGEN_VOICE_ID`

---

## 7. ⚠️ Autres problèmes détectés

### 7.1 Dépendance npm inutilisée
- **`pg` (^8.22.0)** dans `package.json` — le module `pg` n'est importé dans aucun fichier source. À retirer si non prévu.

### 7.2 Artefact suspect
- **`src/app/dashboard/loading.tsx/`** — c'est un **répertoire** (pas un fichier) contenant `.hermes-tmp.7CuhJl`. Le vrai `loading.tsx` (fichier) est manquant. Cela casse la convention Next.js.

### 7.3 Duplication de type
- **`PlanKey`** est défini dans DEUX fichiers :
  - `src/lib/agents.ts:1` → `export type PlanKey = 'essential' | 'pro'`
  - `src/lib/stripe.ts:53` → `export type PlanKey = keyof typeof PLANS`
  
  → Un seul importé dans `needs-finder.tsx` (depuis `@/lib/agents`), l'autre dans `billing/page.tsx` (depuis `@/lib/stripe`). Consolider en une seule source.

### 7.4 URL Supabase en dur dans le CSP
- **`src/middleware.ts:52`** — l'URL Supabase `https://xlivseiybtkwkekyhqwg.supabase.co` est écrite en dur dans le Content-Security-Policy au lieu d'utiliser `process.env.NEXT_PUBLIC_SUPABASE_URL`. Risque : changement d'instance → CSP cassé.

### 7.5 Bloc catch vide
- **`src/app/onboarding/page.tsx:247-248`** — `catch (e) { /* Les colonnes n'existent pas encore, ce n'est pas bloquant */ }` masque silencieusement toute erreur. Ajouter au minimum un `console.error`.

---

## 8. 📊 Synthèse

| Catégorie | Sévérité | Nombre |
|---|---|---|
| Fichiers > 300 lignes | 🟡 Moyenne | 2 |
| TODO/FIXME | 🟡 Moyenne | 4 |
| console.log/error | 🟢 Faible | 11 (1 seul `log`) |
| Imports inutilisés | 🟢 Faible | 5 icônes dans 1 fichier |
| Erreurs TypeScript | ✅ Aucune | 0 |
| Variables .env orphelines | 🟡 Moyenne | 10 non utilisées |
| Dépendance inutilisée | 🟢 Faible | 1 (`pg`) |
| Artefact suspect | 🟠 Élevée | 1 (loading.tsx/) |
| Duplication de type | 🟡 Moyenne | 1 (`PlanKey`) |
| URL en dur dans CSP | 🟠 Élevée | 1 |
| Catch silencieux | 🟡 Moyenne | 1 |

**Note globale** : Code de bonne qualité générale, bien typé, pas d'erreur TypeScript. Principaux axes d'amélioration : refactorer le wizard onboarding (756 lignes !), nettoyer les TODO/fonctionnalités manquantes, corriger l'artefact `loading.tsx/`, et sortir l'URL Supabase du CSP.
