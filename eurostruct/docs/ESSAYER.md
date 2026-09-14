# Essayer EUROSTRUCT

**Il n'y a pas de lien.** L'application n'est déployée nulle part : aucun
hébergement n'a été mis en service, et rien n'a été publié sur un domaine. Ce
qui suit est la procédure exacte pour la faire tourner sur votre poste, en
partant d'un dépôt fraîchement cloné.

Deux chemins. Le premier ne demande **ni base de données, ni compte, ni
configuration** et montre le produit en une dizaine de minutes. Le second
ajoute le parcours d'autorité, et demande PostgreSQL — plus une seconde
personne, pour la raison expliquée au §4.

---

## 1. Ce qu'il faut avoir

| | version | pour quoi |
|---|---|---|
| Python | 3.11 ou plus | moteur et API |
| Node.js | 22 ou plus | interface |
| PostgreSQL | 16 | **chemin 2 seulement** — le parcours d'autorité |

Pas d'AutoCAD, pas de licence CAO, pas de compte Supabase. Le DXF est produit
par `ezdxf` (MIT) et s'ouvre avec le logiciel de votre choix.

## 2. Chemin 1 — le produit en dix minutes, sans rien configurer

```bash
git clone <url-du-depot> && cd eurostruct
python -m venv .venv && source .venv/bin/activate
pip install -e engine -e "api[dev]"
(cd web && npm install)

./dev.sh
```

`dev.sh` attend que les deux services **répondent** avant de rendre la main —
un processus lancé n'est pas un service disponible. Puis :

* l'interface : <http://127.0.0.1:3000>
* l'API : <http://127.0.0.1:8000>, sa santé sur `/health`, son diagnostic
  détaillé sur `/ready`.

Sans fichier `.env`, tout démarre quand même. `/ready` dit **ce qui manque**,
sans révéler aucune valeur.

### Ce que vous pouvez faire tout de suite

1. **Une vérification de poutre EC2 complète** — cinq chapitres : flexion,
   effort tranchant, ancrage, ouverture des fissures, flèche. Le calcul est
   déterministe et ne consulte aucune donnée d'autorité ; c'est pour cela
   qu'il marche sans base.
2. **Le PDF de la note** et **le DXF du plan de ferraillage**, plus l'aperçu
   SVG tiré du même modèle géométrique.
3. **Lire le bandeau de référentiel**, qui sépare trois états — transcrit,
   décidé ici, utilisable — et qui affichera « **non interrogé** » pour le
   deuxième, faute de base branchée. Ce n'est pas « zéro » : c'est
   « personne n'a été interrogé », et les deux appellent des gestes opposés.

### Ce que vous allez voir refuser, et c'est le produit qui fonctionne

* **Le mode strict refuse**, et rend le refus comme une **liste de travail** :
  chaque paramètre à faire confirmer, avec sa clause, son annexe et son folio.
  Une vérification belge en réclame **19**.
* **Décocher le mode strict** donne un résultat exploratoire — enregistré,
  lisible, rejouable — portant **« PROJET — NON SIGNABLE »**. L'écran demande
  une case explicite avant de partir, parce que ce choix ne se rattrape pas :
  aucune correction de section ne rendra ce résultat signable.
* **Une poutre déclarée en XF ou XA** est refusée sur `w_max`. Le tableau
  belge ne donne aucune ligne pour ces classes ; le moteur ne leur attribue
  pas 0,3 mm par défaut et demande la classe XC/XD/XS que porte aussi
  l'élément. Rien dans la géométrie ne la révèle.

## 3. Chemin 2 — avec la base, et le parcours d'autorité

Le parcours à quatre yeux dresse la pile entière et la pilote au clavier :

```bash
export PGHOST=/var/run/postgresql PGUSER=postgres \
       EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole

db/test/parcours_livrable.sh <prefixe>    # les deux parcours Chromium
```

⚠️ `EUROSTRUCT_CLUSTER_JETABLE` est un consentement, pas une formalité : ce
harnais crée et détruit bases et rôles. **Ne le pointez jamais vers un cluster
qui contient quelque chose.**

Pour vérifier l'ensemble avant d'y croire :

```bash
./run_tests.sh --require-db
```

Le verdict ne dit `COMPLET` que si les **six** surfaces ont tourné — moteur,
importeur, API, sécurité des harnais, garanties SQL, cohérence des artefacts.
Une surface non exécutée y est aussi visible qu'une surface rouge.

## 4. Ce que vous ne pourrez pas faire seul, et pourquoi

**Confirmer les 19 paramètres belges.** Il faut deux ingénieurs distincts :
l'un propose depuis l'Annexe Nationale publiée, l'autre relit le dossier gelé
et approuve, puis la décision est consommée.

Ce n'est pas une option de configuration. PostgreSQL le refuse par contrainte
de table :

```sql
constraint decision_two_distinct_principals
  check (approver_id is null or approver_id <> proposer_id)
```

Aucun rôle d'administration et aucun script du dépôt ne la lève — c'est
délibéré : une valeur nationale doit porter le nom de deux personnes qui l'ont
lue. L'écran **Décisions d'autorité** dit où vous en êtes des 19 sur
l'instance courante, et `GET /v1/ndp/BE/couverture` le rend en JSON.

## 5. Ce qui n'a pas été essayé, et ne doit pas être annoncé

| | état |
|---|---|
| Supabase réel | **jamais traversé.** `SUPABASE_UNVERIFIED`. Voir [`RECETTE_SUPABASE.md`](RECETTE_SUPABASE.md) : les sept étapes, et les 14 accès qui manquent |
| AutoCAD, BricsCAD, LibreCAD | **aucun n'a été ouvert.** Ce qui est établi sur le DXF, et ce qui ne l'est pas, est au §5 de [`DESSIN_DXF.md`](DESSIN_DXF.md) |
| validation d'un projet calculé | distincte de la validation des paramètres, et non acquise |

## 6. Avant tout usage réel

Lire [`VALIDATION.md`](VALIDATION.md). Tout document produit par un calcul non
strict porte **« PROJET — NON SIGNABLE »**, et cette mention n'est pas
décorative.
