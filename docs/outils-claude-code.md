# Outils Claude Code — installation

Guide d'installation des skills / plugins / serveurs MCP utilisés pour développer Bapica.

> ⚠️ **Ces outils exécutent du code tiers dans votre environnement.** Validez chaque
> installation. Aucune de ces commandes ne peut être lancée depuis une session Claude Code
> non interactive : `/plugin` ouvre un panneau interactif, il faut donc les taper dans un
> **vrai terminal** `claude`.

## Choisir le périmètre

| Périmètre | Emplacement | Effet |
|---|---|---|
| **Personnel** | `~/.claude/` | Disponible dans tous vos projets, non committé. |
| **Projet** | `bapica-code/.claude/` | Committé → partagé avec l'équipe (ce repo y a déjà `agents/bapica-qa.md`). |

Pour des outils de confort personnel (mémoire, design), le **périmètre personnel** est
généralement le bon choix.

## Skills & plugins

### UI UX Pro Max — intelligence design
Base de règles UI/UX (styles, palettes, associations typographiques, presets motion, types de graphiques).
Source : [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)

```
/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
/plugin install ui-ux-pro-max@ui-ux-pro-max-skill
```

### Superpowers — méthodologie de dev agentique
Compétences composables : planification, TDD, débogage, routage d'exécution.
Source : [obra/superpowers](https://github.com/obra/superpowers)

```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers
```

### claude-mem — mémoire persistante entre sessions
Capture le déroulé des sessions, le compresse, et réinjecte le contexte utile au démarrage suivant.
Source : [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)

```
/plugin marketplace add thedotmack/claude-mem
/plugin install claude-mem
```

Alternative CLI : `npx claude-mem install`
(⚠️ `npm install -g claude-mem` **ne suffit pas** : cela n'enregistre pas les hooks.)

### Animations « Emil Kowalski » — motion web
Règles d'animation (easing, durées, propriétés GPU, accessibilité) issues de son cours.
Sources : [delphi-ai/animate-skill](https://github.com/delphi-ai/animate-skill) · [emilkowal.ski/skill](https://emilkowal.ski/skill)

```
/plugin marketplace add delphi-ai/animate-skill
/plugin install animate-skill
```

> Note : les principes de ce skill sont **déjà appliqués** dans Bapica (voir `src/app/globals.css` :
> `--ease-out-soft`, `.reveal`, `.reveal-on-scroll`, et le respect de `prefers-reduced-motion`).
> Le site anime en **CSS pur** — aucune dépendance type Framer Motion / GSAP n'est installée,
> et `package.json` ne doit pas en gagner sans décision explicite.

### « everything claude code »
❌ Aucune source fiable identifiée à ce jour. Renseigner l'URL exacte du dépôt/marketplace
avant toute installation.

## Serveur MCP — n8n

Permet de construire et modifier des workflows n8n depuis Claude Code.
Source : [czlonkowski/n8n-mcp](https://github.com/czlonkowski/n8n-mcp)

```
claude mcp add n8n-mcp \
  -e MCP_MODE=stdio \
  -e LOG_LEVEL=error \
  -e DISABLE_CONSOLE_OUTPUT=true \
  -e N8N_API_URL=https://VOTRE-INSTANCE-n8n.com \
  -e N8N_API_KEY=VOTRE_CLE_API \
  -- npx n8n-mcp
```

> 🔐 La clé API n8n donne accès à vos workflows. Ne la committez jamais dans le repo :
> elle vit dans la configuration MCP locale. Sans `N8N_API_URL` / `N8N_API_KEY`, le serveur
> fonctionne en mode documentation seule (pas de pilotage de votre instance).

## Vérifier l'installation

```
/plugin            # plugins et marketplaces installés
claude mcp list    # serveurs MCP enregistrés
claude mcp get n8n-mcp
/mcp               # état des serveurs pendant une conversation
```

## Prérequis

- Node.js 18+
- Claude Code installé (`npm install -g @anthropic-ai/claude-code`)
