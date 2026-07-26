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
| Cloisonnement multi-tenant (RLS) | ✅ | `db/test/01_guarantees.sql`, test 1 |
| Aucun livrable final sans validation nominative | ✅ | `db/test/01_guarantees.sql`, tests 2–4 |
| Immuabilité des documents signés | ✅ | `db/test/01_guarantees.sql`, test 5 |

## 2. Ce qui n'est PAS garanti — points bloquants avant commercialisation

### 2.1 Les paramètres nationaux ne sont pas vérifiés ⛔

**C'est le point bloquant principal.**

Les jeux de NDP livrés (`engine/src/eurostruct_engine/ndp/data/*.json`) contiennent
les **valeurs recommandées par l'Eurocode**, pas les valeurs des Annexes
Nationales belge et française. Chaque paramètre porte le statut
`na_pending_verification`.

Conséquence voulue : **le moteur refuse de calculer en mode strict**, qui est le
mode par défaut. Un calcul destiné à un livrable signé échoue avec
`UnverifiedNationalParameter` tant qu'un ingénieur n'a pas relevé la valeur dans
l'annexe publiée.

Pour lever le blocage, paramètre par paramètre :

1. Ouvrir l'Annexe Nationale publiée (NBN EN 1992-1-1 ANB, NF EN 1992-1-1/NA).
2. Relever la valeur à la clause indiquée.
3. Mettre à jour le JSON : valeur, `status: "na_confirmed"`, `confirmed_by`,
   `confirmed_at`.
4. Régénérer le seed : `python db/seed/generate_ndp_seed.py > db/seed/0001_ndp.sql`.

Le schéma refuse un `na_confirmed` sans vérificateur nommé ni date
(contrainte `confirmed_ndp_needs_a_verifier`), et un test le vérifie.

> ⚠️ Ne jamais promouvoir un paramètre en `na_confirmed` sans avoir eu l'annexe
> sous les yeux. C'est exactement l'interdiction n°3 du cahier des charges.

### 2.2 Aucun cas de référence publié n'est encore intégré ⛔

Le cahier des charges (§8.2) exige la validation contre des exemples publiés :
guides des Eurocodes, *Designers' Guides* ICE, *Bautabellen* Schneider,
*Prontuario* espagnol, publications CSTB/Cerema, notes du CSTC/WTCB.

**Aucun de ces exemples n'est présent dans la suite de tests**, parce que les
reproduire exige de disposer des ouvrages et d'en recopier les données
d'entrée et les résultats attendus. Inventer une référence aurait été pire que
son absence.

Ce qui existe à la place, et qui est réel :

- un **calcul manuel** entièrement détaillé et reproductible
  (`test_hand_calculation_case`) ;
- une **vérification indépendante par intégration numérique** de l'équilibre de
  la section (`test_independent_equilibrium`) — elle ne réutilise pas
  l'inversion en forme fermée du module, et échouerait si l'algèbre était
  fausse ;
- la comparaison au **Tableau 3.1 publié** de l'EN 1992-1-1 pour les matériaux,
  à la précision d'impression du tableau.

Le harnais est prêt : ajouter un cas publié consiste à écrire un test marqué
`@pytest.mark.reference` avec la source citée en docstring.

### 2.3 Comparaison croisée logiciel non faite ⛔

§8.2 exige une comparaison documentée avec au moins un logiciel du marché
(SCIA, Robot, RFEM, Advance Design, CYPE). Non réalisée.

### 2.4 Interopérabilité CAO non vérifiée manuellement ⚠️

Les tests vérifient tout ce qui est automatisable : fichier R2018 valide,
audit `ezdxf` sans erreur, aller-retour sauvegarde/relecture, calques
normalisés, style de cotation lié à une police présente dans le fichier,
géométrie à l'échelle vraie. **L'ouverture effective dans AutoCAD, BricsCAD et
LibreCAD reste une recette manuelle.**

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
python -m pytest tests/ -q                    # 107 tests
python -m pytest tests/ -m reference -q       # cas de référence
python -m pytest tests/ -m golden -q          # non-régression
python -m pytest tests/ -m property -q        # invariants

# Schéma de données (exige PostgreSQL >= 15)
PGHOST=/tmp PGUSER=postgres ./db/test/run.sh
```
