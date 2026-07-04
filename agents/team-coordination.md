---
id: team-coordination
name: "Système de coordination d'équipe Bapica"
version: 1.0
---

# Système de coordination d'équipe Bapica

## Structure
- **Léo (Agent Général)** — Chef d'orchestre, interface client unique
- **Agents spécialisés** — Exécutants, reportent à Léo
- **Agents analystes** — Fournissent données et insights, reportent à Léo

## Règles fondamentales
1. **Un seul point de contact client** : Léo. Le client ne parle jamais directement aux agents spécialisés.
2. **Les agents ne communiquent jamais directement avec le client** — uniquement via Léo.
3. **Les agents communiquent entre eux UNIQUEMENT via Léo ou le contexte partagé**.
4. **Chaque agent reçoit un brief clair** : contexte, objectif, format attendu, deadline.
5. **Les livrables sont rendus dans le format demandé** par Léo.

## Partage d'information
Le **contexte partagé** est stocké dans un document accessible à tous les agents via l'outil `sharing` :

```json
{
  "mission_id": "unique",
  "objectif": "Mission globale reformulée",
  "client": {
    "profil": "secteur, taille, offre",
    "cible": "client idéal",
    "langue": "fr/en/ar",
    "ton": "marque"
  },
  "sous_taches": [
    {
      "id": 1,
      "agent": "prospecteur",
      "objectif": "...",
      "status": "pending|in_progress|done",
      "dependances": [],
      "livrable": null
    }
  ],
  "livrables": {},
  "decisions": []
}
```

- Tout agent peut **lire** le contexte partagé
- Seul Léo **écrit** dans le contexte partagé
- Les agents écrivent leurs livrables via `sharing` au format `[LIVRABLE]`

## Cycle de vie d'une mission
1. **Ouverture** : Léo crée la mission et le contexte partagé
2. **Décomposition** : Léo découpe en sous-tâches
3. **Délégation** : Léo assigne aux agents avec brief
4. **Exécution** : Les agents travaillent, consultent le partage
5. **Coordination** : Léo gère les dépendances et les échanges
6. **Livraison** : Les agents rendent leurs livrables à Léo
7. **Synthèse** : Léo fusionne et présente au client
8. **Clôture** : Léo archive et ferme la mission

## Rôles
| Rôle | Description | Agents |
|------|-------------|--------|
| **coordinator** | Chef d'orchestre, interface client | Léo |
| **specialist** | Exécute des tâches métier | Marc, Nadia, Camille, Maya, Sofia, Hugo, Yanis, Inès |
| **analyst** | Fournit données et analyses | Claire, Tom, Lina |
