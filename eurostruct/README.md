# EUROSTRUCT — vérification de poutre béton armé, de la saisie au plan

Plateforme SaaS d'études de stabilité assistée par IA — Belgique, France,
Espagne, Allemagne.

> **Projet indépendant.** Rien ici n'est lié au dossier `bapica/` du même dépôt.

> **Ce document décrit le produit tel qu'il est aujourd'hui.** Les comptes
> rendus de lot rangés dans `docs/RAPPORT_*.md` décrivent chacun **le SHA de
> leur époque** et n'ont pas été réécrits : ils vieillissent volontairement, et
> c'est ce qui les rend lisibles comme une histoire. Ce README, lui, est tenu à
> jour.

---

## Ce que le produit fait aujourd'hui

**Une verticale complète, sur un seul élément : la poutre rectangulaire en
béton armé.** Pas quarante modules à 30 %.

| Capacité | État |
|---|---|
| **Vérification complète en cinq chapitres** — flexion, effort tranchant, ancrage, ouverture des fissures, flèche — en une seule saisie | ✅ orchestrateur déterministe, quatre états par chapitre |
| **Saisie guidée en sept étapes**, qui rend visible ce qui manque plutôt que de le faire découvrir au refus | ✅ |
| **Note de calcul à cinq chapitres**, HTML et PDF, avec la mention obligatoire de validation | ✅ PDF sans horodatage : deux compositions rendent les mêmes octets |
| **Plan de ferraillage DXF R2018** depuis la coupe gelée avec l'étude | ✅ déterministe entre processus, germes et appels concurrents |
| **Aperçu SVG** du plan, depuis le même modèle géométrique, sans rien déposer | ✅ non contractuel, et il le dit |
| **Atelier** — organisations, projets, rôles, historique, livrables, révisions | ✅ frontière dans PostgreSQL, pas dans l'écran |
| **Attestation puis émission** à quatre yeux, sous identité vérifiée | ✅ l'émission exige l'attestation d'un ingénieur validateur |
| Schéma PostgreSQL — RLS `FORCE`, immuabilité décennale, quatre-yeux | ✅ testé contre PostgreSQL 16 |
| Contrat d'interface Pydantic → TypeScript généré | ✅ régénération vérifiée en CI |
| **Flexion seule** — vérification rapide, un chapitre sur cinq | ✅ conservée, sous son propre titre |

### Ce que le produit ne fait pas

Poutres rectangulaires uniquement : pas de dalle, pas de poteau, pas de
fondation, pas de charpente métallique. **Pas de descente de charges** — les
sollicitations sont *saisies*, elles ne sont pas calculées. Pas de DWG natif :
DXF R2018 par `ezdxf`, la question de licence ODA reste ouverte.

## Le principe non négociable, dans le code

> Le LLM ne calcule jamais. Le moteur déterministe calcule.

`eurostruct_engine` n'a **aucune** dépendance IA ni réseau : `pint`, `pydantic`,
`ezdxf`, `numpy`. C'est vérifiable en lisant `engine/pyproject.toml`. Un LLM ne
peut pas produire un nombre qui finit dans une note de calcul, parce qu'aucun
LLM n'est atteignable depuis le moteur.

## Démarrer l'application

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e engine -e "api[dev]"
(cd web && npm install)

./dev.sh                    # API :8000 + interface :3000
```

`dev.sh` **attend que les deux services répondent** avant de rendre la main :
un processus lancé n'est pas un service disponible, et annoncer l'un pour
l'autre fait chercher la panne du mauvais côté.

Sans `.env`, l'application démarre quand même. `/health` répond, `/ready`
explique **ce qui manque** — sans révéler aucune valeur — et le calcul
fonctionne : il est déterministe et ne consulte aucune donnée d'autorité. Ce
sont les **décisions** qui exigent une identité vérifiée.

### Mode strict et mode exploratoire — l'état exact

**Le mode strict est le défaut.** Ce n'est pas une panne quand il refuse :
l'écran rend le refus comme une **liste de travail** — chaque paramètre à
faire relever ou à faire confirmer, avec sa clause, son annexe et son folio.

**Trois états, et ils ne se déduisent pas l'un de l'autre.** Le bandeau de
référentiel les sépare, parce qu'ils appellent trois gestes différents :

| état | où il vit | ce qu'il mesure |
|---|---|---|
| **transcrit** | fichiers versionnés | le travail documentaire : valeur, clause, folio, empreinte du document |
| **décidé ici** | base d'autorité de l'instance | les décisions nominatives à quatre yeux |
| **utilisable** | l'intersection, restreinte au calcul demandé | le seul qui décide si le bouton part |

Le dépôt n'écrit **jamais** `confirmed` — c'est une garantie, pas un manque —
si bien qu'un compte pris dans les fichiers dira toujours zéro, sur n'importe
quelle instance. `GET /v1/ndp/{pays}/couverture` interroge la base réelle et
rend les trois séparément, paramètre par paramètre, avec le nom des
vérificateurs. Ne lisez pas l'état d'une instance dans le premier compte.

Les paramètres se confirment **à quatre yeux** : un ingénieur propose depuis
l'Annexe Nationale publiée, un second approuve, et la décision consommée
devient un effet normatif. Ce chemin fonctionne.

Une vérification complète de poutre réclame **19 paramètres** en Belgique
(`required_parameters_for_beam("BE")`, mesuré, pas recopié). Les 19 sont
transcrits depuis la NBN EN 1992-1-1 ANB et **aucun n'est confirmé** : le
mur qui reste est le workflow humain, pas un document manquant.

`EN 1992-1-1:w_max` était l'exception, et il ne l'est plus. Son
Tableau 7.1N-ANB était illisible sur l'exemplaire déposé ; il a été lu à
l'œil sur un autre (folio 18 · page PDF 20) le 13/09, et la fiche porte
désormais 0,4 mm en X0/XC1 et 0,3 mm en XC2-XC4/XD/XS. Le dépôt **transcrit**
cette lecture ; il ne la confirme pas.

Le tableau belge ne donne **aucune ligne pour XF ni pour XA**. Une poutre
déclarée dans l'une de ces classes ne reçoit pas 0,3 mm par défaut : le
moteur refuse et demande la classe XC/XD/XS que porte aussi l'élément. Rien
dans la géométrie ne la révèle.

Décocher le mode strict donne un résultat **exploratoire** : enregistré,
lisible, rejouable, et portant la mention **« PROJET — NON SIGNABLE »**.
Aucune correction de section ne le rendra signable — il faut relancer en mode
strict après confirmation. L'écran demande une case explicite avant de partir
en exploratoire, parce que ce choix ne se rattrape pas.

## Démarrage (moteur seul)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "engine[dev]"

cd engine && python -m pytest tests/ -q          # la suite du moteur
PGHOST=/tmp PGUSER=postgres ./db/test/run.sh     # garanties du schéma
```

> Les **nombres** de tests ne sont pas recopiés ici : ils vieillissent mal.
> `./run_tests.sh` les compte et les affiche, surface par surface.

### La commande canonique

**Un compte rendu de tests ne doit venir que d'ici.** Les commandes
ci-dessus lancent chacune UNE surface; les enchaîner à la main est
exactement ce qui a permis d'annoncer « tous verts » alors qu'une
suite était rouge.

```bash
./run_tests.sh                 # tout ce qui est lançable ici
./run_tests.sh --require-db    # échoue si la base manque (CI)
```

Le verdict ne dit `COMPLET` que si **les six surfaces ont tourné** : moteur,
importeur, API, sécurité des harnais, garanties SQL, cohérence des artefacts.
Une surface non exécutée est aussi visible qu'une surface rouge — c'est la
propriété que ce script existe pour garantir.

### Les deux parcours navigateur

`run_tests.sh` ne pilote pas Chromium. La verticale telle qu'un ingénieur la
vit se mesure séparément, sur une pile dressée pour l'occasion :

```bash
export PGHOST=/var/run/postgresql PGUSER=postgres \
       EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole

db/test/livrable_validation.sh <prefixe>   # primitives et routes, sous identité
db/test/parcours_livrable.sh    <prefixe>  # les DEUX parcours Chromium
```

Le second dresse la pile entière — base, migrations, sceau, quatre-yeux,
émetteur de jetons RS256 fictif, API, **build de production** de l'interface —
puis la pilote au clavier. Il éprouve le livrable *et* la vérification
complète, et **toute erreur de console y fait échouer le parcours**.

### La recette de production

Elle fait tourner la verticale métier sur la **composition réelle** — images
Docker, PostgreSQL et MinIO en conteneurs, `next build` puis `next start` —
et ajoute le seul geste qu'aucun autre harnais ne fait : **arrêter l'API et
l'interface, les redémarrer, et recomposer**.

```bash
git worktree add --detach /chemin/propre <sha>    # obligatoire, voir plus bas
cd /chemin/propre/eurostruct && db/test/recette_production.sh
```

**Elle exige un contexte de build Git-only et refuse autrement.** Les images se
construisent depuis le répertoire présent sur le disque : un fichier modifié,
indexé ou non versionné y entrerait sans qu'une ligne le dise, et la recette
prouverait alors quelque chose à propos d'un code qui n'existe nulle part. Elle
affirme donc, avant et après :

```text
HEAD identique
index propre
arbre propre
aucun fichier source non versionné dans le contexte
```

Après redémarrage, la note **et** le plan sont **recomposés** par un processus
neuf : nouveaux identifiants de livrable, **mêmes octets**. Cinq lignes de
livrable pour deux objets physiques — c'est le couple qui prouve, pas l'un des
deux.

### Déployer

Le déploiement a **trois phases** et **deux acteurs distincts** — un plan de
contrôle qui pose la racine de confiance et approuve, un migrateur qui applique
le schéma. Une seule commande les orchestre, et **vérifie** ses postconditions :

```bash
export ESC_PLAN_URL='postgresql://plan:…@hote:5432/base?sslmode=verify-full'
export ESC_MIGRATOR_URL='postgresql://migrateur:…@hote:5432/base?sslmode=verify-full'
tools/deploy_eurostruct.sh --dry-run    # les connexions, rien d'appliqué
tools/deploy_eurostruct.sh              # les dix étapes
```

Vers une cible **distante**, `verify-ca` ou `verify-full` sont **exigés** : rien
d'autre ne dit à qui l'on parle. Seuls `sslmode` et `sslrootcert` sont portés
depuis l'URL ; tout autre paramètre `ssl*` est refusé plutôt qu'ignoré.

Relancer la commande est sûr — **non parce que les migrations seraient
idempotentes** (elles ne le sont pas), mais parce qu'un registre sait lesquelles
ont été appliquées et les saute. Sur une base déjà `ACTIVE`, le dépôt et le
registre sont rapprochés en lecture ; une migration ajoutée depuis produit
`ACTIVE_SCHEMA_UPGRADE_REQUIRED` — cette commande installe et vérifie, elle ne
met pas à niveau une base en service.

Un déploiement tué brutalement laisse la base `PENDING` avec ses emprunts :
`--recover-pending` les reprend, après avoir établi ses préconditions. La
commande tient un verrou de session pendant toute sa durée et le **reconstate
avant chaque étape mutante** ; elle ne fonctionne donc pas derrière PgBouncer en
*transaction pooling*.

Prérequis, provisionnement, contrat TLS, niveaux d'assurance et limites
connues : `docs/DEPLOIEMENT_PREREQUIS.md`. Modèle de menace :
`docs/schema/MODELE_DE_MENACE_NORMATIF.md`.

### Un calcul de bout en bout

```python
from eurostruct_engine.ndp import load_parameter_set
from eurostruct_engine.materials import concrete, reinforcement, bars_area
from eurostruct_engine.ec2 import RectangularSection, design_flexure
from eurostruct_engine.units import Q_

# strict=True (défaut) refuse tant que les NDP ne sont pas relevés dans l'AN.
params = load_parameter_set("BE", strict=False)

r = design_flexure(
    section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
    concrete=concrete("C30/37"),
    steel=reinforcement("B500B"),
    M_Ed=Q_(250, "kN*m"),
    params=params,
    element="P1",
    A_s_provided=bars_area(4, 20),
)

print(r.As_required.to("mm**2"))      # 1129.5 mm²
print(r.resistance.M_Rd.to("kN*m"))   # 275.6 kN·m
print(r.utilisation)                  # 0.907

for step in r.journal.steps:          # chaque nombre, sa formule, sa clause
    if step.clause:
        print(f"{step.symbol:12} = {step.value:~P}   [{step.clause.cite()}]")
```

## Structure

```
eurostruct/
├── engine/                     Moteur déterministe (Python 3.11+)
│   ├── src/eurostruct_engine/
│   │   ├── units.py            Grandeurs typées Pint — pas de constante nue
│   │   ├── traceability.py     Clause, provenance, journal de calcul
│   │   ├── verification.py     Check + taux de travail obligatoire
│   │   ├── exceptions.py       Refus explicites (hors domaine, NDP non vérifié)
│   │   ├── ndp/                Paramètres nationaux, par pays, versionnés
│   │   ├── materials/          EN 1992-1-1 §3.1 / §3.2
│   │   ├── ec2/                LES CINQ CHAPITRES + l'orchestrateur
│   │   │   ├── beam_flexure.py       flexion simple ELU
│   │   │   ├── beam_shear.py         effort tranchant
│   │   │   ├── anchorage.py          ancrage
│   │   │   ├── serviceability.py     ouverture des fissures
│   │   │   ├── deflection.py         flèche
│   │   │   └── beam_verification.py  les cinq, en une étude
│   │   ├── drawing/            DXF déterministe (ezdxf)
│   │   ├── schemas/            Contrat Pydantic
│   │   └── service.py          Adaptateur DTO ↔ domaine
│   └── tests/                  Suite du moteur — comptée par run_tests.sh
├── api/                        FastAPI: santé, calcul, atelier, livrables
│   └── src/eurostruct_api/
│       ├── routes/             projets, livrables, autorité, référentiel
│       ├── note.py, pdf.py     note à cinq chapitres, HTML puis PDF
│       └── s3.py               magasin d'objets, chemin dérivé du contenu
├── web/                        Next.js — saisie guidée, synthèse, documents
│   └── e2e/                    Parcours Chromium et recette de production
├── db/
│   ├── migrations/             Schéma, RLS, immuabilité, autorité, livrables
│   ├── seed/                   NDP générés depuis les JSON du moteur
│   └── test/                   Garanties vérifiées contre PostgreSQL
├── deploy/, compose.yaml       Composition de production
├── packages/contracts/         TypeScript généré — ne pas éditer à la main
└── docs/VALIDATION.md          Ce qui est vérifié, et ce qui ne l'est pas
```

## ⛔ Avant tout usage réel — lire `docs/VALIDATION.md`

**Ce qui bloque aujourd'hui n'est pas logiciel.** Les cinq points ci-dessous
sont des dépendances externes : aucun commit ne les lève.

1. **Aucune décision nominative n'est livrée avec le dépôt, et il ne peut pas
   en livrer.** Les fichiers versionnés portent des valeurs *transcrites* — en
   Belgique, les 19 que réclame une vérification de poutre le sont depuis la
   NBN EN 1992-1-1 ANB. Aucune n'est *confirmée* : cette transition est l'acte
   daté de deux ingénieurs nommés, enregistré par le chemin d'autorité dans la
   base de **votre** instance. Le moteur refuse en mode strict tant qu'elle
   n'a pas eu lieu. C'est délibéré : supposer une AN est l'interdiction n°3.

2. **Le Tableau 7.1N-ANB a été lu à l'œil, pas extrait.** `EN 1992-1-1:w_max`
   porte désormais une transcription de la NBN EN 1992-1-1 ANB (folio 18 ·
   page PDF 20, empreinte `3a195362…`) et non plus les valeurs de l'EN. Le
   PDF n'est pas et ne sera pas versionné : c'est un document NBN payant, non
   redistribuable. **Cette lecture n'est donc contrôlable que sur pièce**, par
   qui détient l'exemplaire de cette empreinte. Le tableau ne donne par
   ailleurs aucune ligne pour XF ni pour XA, et le moteur refuse ces classes
   sans classe XC/XD/XS associée déclarée plutôt que d'en choisir une.

3. **La validation par un ingénieur reste due.** Aucun résultat produit ici
   n'a été relu par un ingénieur structure agréé. La mention obligatoire le
   dit sur chaque document, et la signature reste un acte humain.

4. **Aucun cas de référence publié n'est intégré.** Il y a un calcul manuel
   détaillé et une vérification indépendante par intégration numérique de
   l'équilibre de section — mais pas d'exemple tiré d'un guide Eurocode.
   Inventer une citation aurait été pire que son absence.

5. **Pas de comparaison croisée** avec SCIA / Robot / RFEM, ni **d'ouverture
   manuelle des DXF** dans AutoCAD, BricsCAD et LibreCAD. Cette dernière ne
   demande aucune licence à acheter ; grille de contrôle et valeurs attendues
   dans `docs/DESSIN_DXF.md`.

À quoi s'ajoute une dépendance d'exploitation : **la compatibilité Supabase
reste `SUPABASE_UNVERIFIED`** — aucun cycle complet n'a été validé sur une
instance réelle. L'implémentation vise PostgreSQL 16 et est éprouvée contre
lui ; voir `docs/MATRICE_SUPABASE.md`.

Le produit n'est pas commercialisable tant que ces points ne sont pas levés par
un ingénieur structure agréé de chaque pays visé.

## Décisions techniques notables

**Un statut, pas une valeur par défaut, pour les NDP.** Chaque paramètre porte
`en_recommended` / `na_confirmed` / `na_pending_verification`. Le mode strict
refuse tout ce qui n'est pas confirmé. Un paramètre absent lève une erreur : il
n'existe aucun chemin de repli silencieux vers la valeur recommandée.

**La validation humaine est une contrainte de base de données.** `is_final`
exige `validation_id`, un trigger vérifie le rôle du signataire, et
signatures et livrables finaux sont immuables. Ce n'est pas une règle
applicative qu'un correctif pourrait contourner.

**Tolérance flottante de 1e-9, documentée.** Quand `A_s` est dimensionné pour
que `M_Rd == M_Ed`, le dernier bit de mantisse ferait lire « échec » à un
contrôle satisfait exactement. La tolérance vaut quinze ordres de grandeur
sous le premier chiffre significatif ; le taux de travail affiché n'est jamais
modifié. Ce n'est pas un lissage — voir `verification.py`.

**PostgreSQL `NULLS NOT DISTINCT`.** Sans cette clause, l'unicité
`(country, region, version)` laissait insérer plusieurs jeux « BE / NULL /
0.1.0 » divergents. Trouvé en exécutant les migrations, pas en les relisant.
Requiert PostgreSQL ≥ 15.

## Suite — P1

Portiques 2D/3D, dalles, poteaux, semelles, descente de charges, neige et vent
depuis la localisation, EN 1997 fondations superficielles. Critère de sortie :
un R+2 complet comparé à SCIA ou Robot.
