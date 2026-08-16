# EUROSTRUCT — socle P0

Plateforme SaaS d'études de stabilité assistée par IA — Belgique, France,
Espagne, Allemagne.

Ce dossier contient le **socle de la phase P0** décrite au §10 du cahier des
charges : la première verticale complète, pas quarante modules à 30 %.

> **Projet indépendant.** Rien ici n'est lié au dossier `bapica/` du même dépôt.

---

## Ce qui est livré

| §14 | Livrable | État |
|---|---|---|
| 1 | Schéma PostgreSQL complet (19 tables, RLS, immuabilité décennale) | ✅ appliqué et testé contre PostgreSQL 16 |
| 2 | Contrat d'interface Pydantic → TypeScript généré | ✅ 22 types, régénération vérifiée en CI |
| 3 | Moteur `ec2/beam_flexure.py` + suite de tests de référence | ✅ 107 tests |
| 4 | Générateur DXF : coupe de poutre, armatures, cadres, calques, cotation | ✅ audit `ezdxf` sans erreur |

## Le principe non négociable, dans le code

> Le LLM ne calcule jamais. Le moteur déterministe calcule.

`eurostruct_engine` n'a **aucune** dépendance IA ni réseau : `pint`, `pydantic`,
`ezdxf`, `numpy`. C'est vérifiable en lisant `engine/pyproject.toml`. Un LLM ne
peut pas produire un nombre qui finit dans une note de calcul, parce qu'aucun
LLM n'est atteignable depuis le moteur.

## Démarrage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "engine[dev]"

cd engine && python -m pytest tests/ -q          # 107 tests
PGHOST=/tmp PGUSER=postgres ./db/test/run.sh     # garanties du schéma
```

### La commande canonique

**Un compte rendu de tests ne doit venir que d'ici.** Les commandes
ci-dessus lancent chacune UNE surface; les enchaîner à la main est
exactement ce qui a permis d'annoncer « tous verts » alors qu'une
suite était rouge.

```bash
./run_tests.sh                 # tout ce qui est lançable ici
./run_tests.sh --require-db    # échoue si la base manque (CI)
```

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
│   │   ├── ec2/beam_flexure.py Flexion simple ELU, section rectangulaire
│   │   ├── drawing/            DXF déterministe (ezdxf)
│   │   ├── schemas/            Contrat Pydantic
│   │   └── service.py          Adaptateur DTO ↔ domaine
│   └── tests/                  107 tests
├── db/
│   ├── migrations/             0001 schéma · 0002 RLS · 0003 immuabilité
│   ├── seed/                   NDP générés depuis les JSON du moteur
│   └── test/                   Garanties vérifiées contre PostgreSQL
├── packages/contracts/         TypeScript généré — ne pas éditer à la main
└── docs/VALIDATION.md          Ce qui est vérifié, et ce qui ne l'est pas
```

## ⛔ Avant tout usage réel — lire `docs/VALIDATION.md`

Trois points bloquants, énoncés sans détour :

1. **Les Annexes Nationales ne sont pas relevées.** Les JSON contiennent les
   valeurs *recommandées par l'Eurocode*, marquées `na_pending_verification`.
   Le moteur **refuse de calculer en mode strict** tant qu'un ingénieur ne les
   a pas confirmées une par une contre l'annexe publiée. C'est délibéré :
   supposer une AN est l'interdiction n°3.

2. **Aucun cas de référence publié n'est intégré.** Il y a un calcul manuel
   détaillé et une vérification indépendante par intégration numérique de
   l'équilibre de section — mais pas encore d'exemple tiré d'un guide Eurocode.
   Inventer une citation aurait été pire que son absence.

3. **Pas de comparaison croisée** avec SCIA / Robot / RFEM, ni d'ouverture
   manuelle des DXF dans AutoCAD, BricsCAD et LibreCAD.

Le produit n'est pas commercialisable tant que ces trois points ne sont pas
levés par un ingénieur structure agréé de chaque pays visé.

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
