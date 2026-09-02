# Politique de validation du moteur

> Ce document dit ce qui est vérifié, ce qui ne l'est pas, et ce qu'il faut
> faire avant qu'une note de calcul produite par ce logiciel puisse être signée.
> Il est volontairement explicite sur les limites.

## 1. Ce que le moteur garantit aujourd'hui

| Propriété | État | Preuve |
|---|---|---|
| Aucun LLM ne produit de valeur numérique | ✅ | Le paquet `eurostruct_engine` n'a aucune dépendance réseau ni IA. Vérifiable par lecture de `pyproject.toml`. |
| Chaque nombre cite sa clause | ✅ | `test_units_and_traceability.py::test_every_calculated_number_carries_a_clause` |
| Chaque entrée porte sa provenance | ✅ | `test_every_input_carries_a_provenance` |
| Le graphe de traçabilité est fermé et acyclique | ✅ | `test_trace_graph_is_closed_and_acyclic` |
| Déterminisme bit-à-bit, y compris entre processus | ✅ | `test_determinism.py::test_determinism_across_processes` |
| Homogénéité dimensionnelle (Pint) | ✅ | `test_units_and_traceability.py` |
| Refus explicite hors domaine | ✅ | `test_ec2_beam_flexure.py`, section « Refusals » |
| Taux de travail toujours affiché | ✅ | `Check` ne peut pas être construit sans `utilisation` |
| Le moteur tourne hors ligne, réseau coupé | ✅ | `test_engine_isolation.py` — socket désactivé, calcul + DXF complets |
| Arbre de dépendances sans IA ni HTTP | ✅ | `scripts/audit_engine_dependencies.py` — allowlist transitive + denylist + scan des imports différés |
| Écart sur un cas de référence rejouable ⇒ CI rouge | ✅ | `scripts/run_reference_suite.py` |
| Paramètre national non écrasable sans nouvelle version | ✅ | `db/test/02_ndp_versioning.sql` |
| Préflight listant **tous** les bloquants d'un coup | ✅ | `test_ndp.py::test_preflight_report_is_readable_and_machine_parsable` |
| Cloisonnement multi-tenant (RLS) | ✅ | `db/test/01_guarantees.sql`, test 1 |
| Aucun livrable final sans validation nominative | ✅ | `db/test/01_guarantees.sql`, tests 2–4 |
| Workflow `draft → review → validated → final`, sans raccourci ni retour | ✅ | `db/test/03_validation_workflow.sql` |
| `is_final` non écrivable directement (dérivé de `state`) | ✅ | `db/test/03_validation_workflow.sql`, test 2 |
| Livrable non validé porte le filigrane « PROJET » | ✅ | `test_legal.py::test_unvalidated_drawing_is_watermarked` |
| Aucun document ne présente le logiciel comme signataire | ✅ | `test_legal.py::test_no_document_presents_the_software_as_signatory` |
| Mentions légales en FR/NL/EN/ES/DE | ✅ | `test_legal.py`, paramétré sur les 5 langues |
| Immuabilité des documents signés | ✅ | `db/test/01_guarantees.sql`, test 5 |
| Étude à **cinq chapitres** enchaînés en un passage, quatre états par chapitre | ✅ | `test_beam_verification.py` — `passed` / `failed` / `additional_analysis_required` / `not_evaluated`, jamais fusionnés |
| Le **plan DXF** rend les mêmes octets d'un processus à l'autre | ✅ | `test_dxf_determinisme.py` — 5 germes × 2 exécutions en sous-processus, rendus concurrents, garde-fou falsifié |
| La **note PDF** rend les mêmes octets d'un processus à l'autre | ✅ | `web/e2e/recette_production.mjs` — recomposée après redémarrage de l'API : identifiant de livrable différent, mêmes octets ; aucun `/CreationDate`, `/ModDate`, `/Producer` ni `/ID` dans le fichier |
| Le plan décrit la poutre **vérifiée**, pas une autre | ✅ | La coupe est gelée avec l'étude ; le navigateur n'envoie que l'identifiant du calcul et le format |

## 2. Ce qui n'est PAS garanti — points bloquants avant commercialisation

### 2.1 Les paramètres nationaux ne sont pas vérifiés ⛔

**C'est le point bloquant principal.**

Les jeux de NDP livrés (`engine/src/eurostruct_engine/ndp/data/*.json`)
contiennent les **valeurs recommandées par l'Eurocode**, pas celles des Annexes
Nationales. Les 4 pays × **29 paramètres** portent tous le statut
`pending_verification`, et l'édition de chaque annexe est `NON RELEVE`.

Le chemin de confirmation à quatre yeux, lui, fonctionne : un ingénieur propose
depuis l'annexe publiée, un second approuve, la décision consommée devient un
effet normatif. **Il bute en Belgique sur `EN 1992-1-1:w_max`**, que la
NBN EN 1992-1-1 ANB ne relève pas au Tableau 7.1N. Douze des treize paramètres
réclamés par les cinq chapitres se confirment ; celui-là est refusé nommément,
et EUROSTRUCT ne l'invente pas. Une vérification **complète** en mode strict
reste donc fermée en Belgique tant que cette valeur n'est pas transcrite depuis
un document officiel.

Conséquence voulue : **le moteur refuse de calculer en mode strict**, le mode
par défaut. Le préflight rend la liste complète des bloquants en un passage :

```
Calcul impossible pour BE au 2026-07-26: 8 parametre(s) bloquant(s) sur 8 requis.
  [pending_verification] Valeur non relevee dans l'annexe publiee
    - EN 1992-1-1:alpha_cc (§3.1.6(1)P) — NBN EN 1992-1-1 ANB
    - EN 1992-1-1:gamma_C_persistent (§2.4.2.4(1), Tab. 2.1N) — NBN EN 1992-1-1 ANB
    ...
```

Pour lever le blocage, paramètre par paramètre :

1. Ouvrir l'Annexe Nationale publiée (NBN EN 1992-1-1 ANB, NF EN 1992-1-1/NA,
   UNE-EN 1992-1-1 AN, DIN EN 1992-1-1/NA).
2. Relever l'**édition** et la date d'entrée en vigueur, puis la valeur à la
   clause indiquée.
3. Mettre à jour le JSON : `parameter_value`, `source_type: "national_annex"`,
   `validation_status: "confirmed"`, `verified_by`, `verified_at`.
4. Régénérer le seed : `python db/seed/generate_ndp_seed.py > db/seed/0001_ndp.sql`.

Trois garde-fous, tous vérifiés contre PostgreSQL :

- un `confirmed` sans vérificateur nommé, sans date, ou dont la source reste
  `en_recommended` est **refusé** (`confirmed_ndp_is_signed`) ;
- une valeur publiée ne peut pas être **écrasée** : la corriger exige de clore
  la version courante (`effective_to`) et d'en insérer une nouvelle ;
- une valeur déjà confirmée ne peut pas être **déclassée** en place.

> ⚠️ Ne jamais passer un paramètre en `confirmed` sans avoir eu l'annexe sous
> les yeux. C'est exactement l'interdiction n°3 du cahier des charges.

**Attention Espagne** (interdiction 4) : même une fois l'annexe UNE-EN relevée,
le référentiel réglementairement opposable reste le **Código Estructural
(RD 470/2021)**, le **CTE** et **NCSE-02**. Le registre le déclare
explicitement et la note de calcul l'imprime.

### 2.2 Aucun cas de référence *publié* n'est intégré ⛔

Le cahier des charges (§8.2) exige la validation contre des exemples publiés :
guides des Eurocodes, *Designers' Guides* ICE, *Bautabellen* Schneider,
*Prontuario* espagnol, publications CSTB/Cerema, notes du CSTC/WTCB.

**Aucun de ces exemples n'est présent**, parce que les reproduire exige de
disposer des ouvrages. Inventer une référence aurait été pire que son absence :
le cas serait vert sans rien prouver.

La bibliothèque de cas (EPIC 2) rend cette lacune **visible et suivie** plutôt
que silencieuse :

```
18 cas: passed=5, refused=2, awaiting_source=1, awaiting_module=10
```

- `EC2-BF-PUB-001` est déclaré `awaiting_source` : identifiant, périmètre
  normatif et tolérance de 1 % fixés, source à choisir, **aucune valeur
  attendue renseignée**.
- Dix cas sont `awaiting_module` : acier, mixte, bois, géotechnique, sismique,
  plus l'effort tranchant, les ancrages et la flexion composée en béton armé.

Un statut `awaiting_*` ne fait **pas** échouer la CI. C'est délibéré : si une
source manquante cassait le build, la pression serait d'en inventer une. Seul
un cas qui *peut* tourner et qui dérive est une régression.

Ce qui valide réellement le module de flexion aujourd'hui :

- cinq **cas `manual_reference`** dont les valeurs attendues sont produites par
  **dichotomie sur l'équilibre de section** — méthode différente de l'inversion
  en forme fermée qu'utilise le moteur. Les deux concordent à 1e-13. Cela
  atteste l'algèbre ; ce n'est pas l'accord avec la profession ;
- deux **cas de refus** vérifiant que le moteur refuse hors domaine au lieu
  d'approximer ;
- une **vérification par intégration numérique** de l'équilibre
  (`test_independent_equilibrium`) ;
- la comparaison au **Tableau 3.1 publié** de l'EN 1992-1-1, à la précision
  d'impression du tableau.

Pour intégrer un exemple publié : renseigner `expected_outputs`,
`source_document` et `source_type: "official_worked_example"` dans
`engine/src/eurostruct_engine/reference/library/`. Le runner fait le reste, et
la CI garde le cas sous surveillance.

### 2.3 Comparaison croisée logiciel non faite ⛔

§8.2 exige une comparaison documentée avec au moins un logiciel du marché
(SCIA, Robot, RFEM, Advance Design, CYPE). Non réalisée.

### 2.4 Interopérabilité CAO non vérifiée manuellement ⚠️

Les tests vérifient tout ce qui est automatisable : fichier R2018 valide,
audit `ezdxf` sans erreur, aller-retour sauvegarde/relecture, calques
normalisés, style de cotation lié à une police présente dans le fichier,
géométrie à l'échelle vraie. **L'ouverture effective dans AutoCAD, BricsCAD et
LibreCAD reste une recette manuelle.**

Ce n'est **pas** un blocage de licence : aucune licence AutoCAD n'est
nécessaire, ni pour développer, ni pour exploiter le produit, et la recette
elle-même n'en demande aucune — elle se fait dans l'AutoCAD d'un futur
utilisateur et dans LibreCAD. La grille de contrôle, avec les valeurs attendues
tirées du code, est dans `docs/DESSIN_DXF.md` §4.

**Aucun test AutoCAD réel n'a été exécuté à ce jour, et le produit ne prétend
pas le contraire.** Ce qui est prouvé est la relecture indépendante par
`ezdxf`, énumérée ci-dessus.

## 3. Contrat de versionnement

| Incrément | Signification |
|---|---|
| PATCH | Aucun résultat numérique ne peut changer. |
| MINOR | Nouveaux modules ou nouveaux jeux de NDP. Les résultats existants restent identiques bit-à-bit. |
| MAJOR | Un résultat déjà produit change, même d'un ULP. Exige une note de release listant **chaque** valeur modifiée. |

Les *golden tests* (`test_determinism.py`) comparent avec `==`, pas
`approx`. Si l'un échoue, la question n'est jamais « quelle tolérance
mettre » mais « ce changement est-il voulu, et à quelle version ».

## 4. Domaine de validation actuel — `ec2/beam_flexure`

Le moteur **refuse** (il ne renvoie pas un résultat approché) hors de :

- section rectangulaire, largeur constante ;
- flexion simple, sans effort normal ;
- armatures tendues seules, à une seule hauteur utile ;
- béton jusqu'à C50/60 (`high_strength_concrete` au-delà) ;
- pas de redistribution des moments (δ = 1,0) ;
- section sous-armée : μ ≤ μ_lim, sinon `compression_reinforcement_required` ;
- acier plastifié : sinon `steel_not_yielding`.

## 5. Reproduire la validation

```bash
# Moteur
cd engine
python -m pytest tests/ -q                    # 199 tests
python -m pytest tests/ -m reference -q       # cas de référence
python -m pytest tests/ -m golden -q          # non-régression
python -m pytest tests/ -m property -q        # invariants

# Validation normative et isolement du moteur
python scripts/run_reference_suite.py         # cas de reference
python scripts/audit_engine_dependencies.py   # arbre de dependances

# Schéma de données (exige PostgreSQL >= 15)
PGHOST=/tmp PGUSER=postgres ./db/test/run.sh
```
