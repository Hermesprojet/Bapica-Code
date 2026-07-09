# 🔍 Audit Complet de bapica.com — Rapport d'Erreurs

**Date** : 09/07/2026  
**Méthodologie** : Curl de chaque page + analyse du code source Next.js + vérifications CSS/HTML/SEO/Accessibilité  
**Périmètre** : Toutes les pages publiques, 13 pages agents, pages légales, formulaires, métadonnées

---

## 🔴 ERREURS CRITIQUES (bloquantes)

### 1. `manifest.json` dit "12 agents" au lieu de "13"
- **Fichier** : `/public/manifest.json` ligne 4
- **Actuel** : `"12 agents spécialisés, messagerie illimitée."`
- **Attendu** : `"13 agents spécialisés, messagerie illimitée."`
- **Impact** : Incohérence publique visible dans le PWA manifest

### 2. Lien `#demo` cassé dans le CTA
- **Fichier** : `src/components/landing/cta-section.tsx` ligne 24
- **Problème** : `<Link href="#demo">` mais **aucun** `id="demo"` n'existe dans toute la codebase
- **Impact** : Le bouton "Parler à un conseiller" ne fait rien — les utilisateurs cliquent dans le vide

### 3. `/essai-gratuit` → 404 mais référencé dans le sitemap
- **Fichier** : `src/app/sitemap.ts` ligne 17
- **Problème** : Le sitemap liste `https://bapica.com/essai-gratuit` mais la page n'existe PAS
- **Vérifié** : Aucun fichier `src/app/essai-gratuit/` ni route
- **Impact** : Google voit une 404 dans le sitemap → pénalité SEO

### 4. Meta `google-site-verification` avec placeholder
- **Rendu HTML** : `<meta name="google-site-verification" content="REMOVED_PLACEHOLDER_GET_CODE_FROM_SEARCH_CONSOLE"/>`
- **Source** : Non trouvé dans le code source — probablement injecté via Vercel/env
- **Impact** : Google Search Console ne peut pas vérifier le site

### 5. `og-image.png` → 404 (JSON-LD logo cassé)
- **Fichier** : `src/lib/jsonld.tsx` lignes 32-33
- **Problème** : Le JSON-LD Organization pointe `"logo": "https://bapica.com/og-image.png"` → HTTP 404
- **Réel** : L'OG image est générée par Next.js à `/opengraph-image` (HTTP 200)
- **Impact** : Google Knowledge Graph ne peut pas afficher le logo

### 6. FAQ JSON-LD : "4 agents" pour Essentiel (faux)
- **Fichier** : `src/lib/jsonld.tsx` ligne 123
- **Actuel** : `"Essentiel à 49€/mois avec 4 agents (Général, Support, Contenu, Téléphonique)"`
- **Réel** : Le plan Essentiel a **8 agents** (general, support, content, prospector, closer, recruiter, legal, trends)
- **Impact** : Données structurées incorrectes → risque de pénalité Google

---

## 🟠 ERREURS MOYENNES (SEO / UX)

### 7. Pages agents sans métadonnées uniques
- **Fichier** : `src/app/agents/[id]/page.tsx`
- **Problème** : C'est un `'use client'` component → pas d'export `metadata` → toutes les 13 pages ont le même title/description que la homepage
- **Vérifié** : curl des 13 pages confirme `<title>Bapica — Agents IA pour votre entreprise</title>` partout
- **Impact** : SEO désastreux pour les pages agents — Google voit 13 pages avec le même contenu meta

### 8. Page affiliation sans métadonnées
- **Fichier** : `src/app/affiliation/page.tsx`
- **Problème** : Pas d'export `metadata` → utilise le title/description par défaut
- **Impact** : Page invisible dans les SERP

### 9. Mention "Charly+" dans le comparatif
- **Fichier** : `src/components/landing/comparison-section.tsx` ligne 9
- **Problème** : `'✅ Inclus (Charly+)'` — mention d'un concurrent par son nom
- **Impact** : Risque juridique (nom de marque déposée) + fait la pub du concurrent

---

## 🟡 ERREURS MINEURES

### 10. Prix "~39€/mois" avec tilde dans le comparatif
- **Fichier** : `src/components/landing/comparison-section.tsx` ligne 10
- **Problème** : `'À partir de ~39€/mois'` — le tilde donne un aspect approximatif non professionnel
- **Suggestion** : `'À partir de 39€/mois'` ou `'Environ 39€/mois'`

### 11. Page d'accueil : 270 KB
- **Problème** : La homepage pèse 270 KB (HTML seul, sans assets)
- **Cause** : Tous les composants sont inclus dans une seule page (Hero, Features, UseCases, Agents, Team, Limova, Pricing, Testimonials, Comparison, FAQ, CTA, Footer)
- **Impact** : LCP lent sur mobile, surtout en 3G/4G

### 12. 8 scripts async dans le `<head>`
- **Problème** : 8 chunks JS chargés en async dans le head — tous bloquent le parsing
- **Fichiers** : webpack.js, fd9d1056, 2117, main-app, 2972, 964, 3652, 6932, page, layout
- **Impact** : Temps de blocage du rendu élevé

---

## ✅ POINTS VÉRIFIÉS ET CONFORMES

| Point | Statut |
|-------|--------|
| Prix (49€/79€) | ✅ Correct |
| Anciens prix (69€/99€) | ✅ Correct |
| Période d'essai (15 jours) | ✅ Correct partout |
| Plans "Business"/"Starter" | ✅ Aucune trace |
| 13 agents dans `agents.ts` | ✅ Exactement 13 agents |
| Pages agents (13/13 HTTP 200) | ✅ Toutes accessibles |
| Noms/personas cohérents | ✅ Cohérents entre agents.ts et agents-section |
| Description agents | ✅ Chaque agent a sa description unique |
| `border-white/5` transparent | ✅ Aucune occurrence |
| `text-white` sur fond blanc | ✅ Aucun problème — text-white uniquement sur fonds foncés/gradients |
| Images (favicon, icons) | ✅ Tous les fichiers existent dans /public |
| `og:image` généré | ✅ `/opengraph-image` retourne HTTP 200 |
| Formulaires (required, labels) | ✅ Contact, Signup, Login : tous ont `required`, `type`, `label` |
| Pages légales | ✅ CGV, CGU, Privacy, RGPD, Mentions : HTTP 200 |
| Sitemap XML | ✅ HTTP 200 |
| Robots.txt | ✅ Correct |
| Pages statiques | ✅ FAQ, A-propos, Contact, Blog, Login, Signup : HTTP 200 |
| Pas de placeholder dans le contenu | ✅ Aucun "TODO", "FIXME", "Lorem ipsum" |
| Pas d'images cassées (img tags) | ✅ Zéro `<img>` tag — tout en SVG/CSS |
| Reste cohérent "13 agents" dans le HTML | ✅ Le rendered HTML mentionne toujours "13 agents" |
| JSON-LD valide (schema.org) | ✅ `schema.org` correct dans tous les blocs JSON-LD |
| Métadonnées uniques (pages standards) | ✅ FAQ, À propos, Contact, Blog, Login, Signup : OK |

---

## 📋 RÉSUMÉ DES ACTIONS CORRECTIVES

| # | Priorité | Action | Fichier |
|---|----------|--------|---------|
| 1 | 🔴 | Changer "12" → "13" agents | `public/manifest.json:4` |
| 2 | 🔴 | Supprimer ou créer `#demo` | `src/components/landing/cta-section.tsx:24` |
| 3 | 🔴 | Créer page ou retirer du sitemap | `src/app/sitemap.ts:17` |
| 4 | 🔴 | Remplacer placeholder par vrai code GSC | Layout ou config Vercel |
| 5 | 🔴 | Changer logo URL vers `/opengraph-image` | `src/lib/jsonld.tsx:32` |
| 6 | 🔴 | Corriger "4 agents" → "8 agents" | `src/lib/jsonld.tsx:123` |
| 7 | 🟠 | Ajouter metadata aux 13 pages agents | `src/app/agents/[id]/page.tsx` |
| 8 | 🟠 | Ajouter metadata à la page affiliation | `src/app/affiliation/page.tsx` |
| 9 | 🟠 | Retirer mention "Charly+" | `src/components/landing/comparison-section.tsx:9` |
| 10 | 🟡 | Nettoyer le tilde du prix | `src/components/landing/comparison-section.tsx:10` |

---

**Total erreurs trouvées** : 12  
**Critiques** : 6 | **Moyennes** : 3 | **Mineures** : 3
