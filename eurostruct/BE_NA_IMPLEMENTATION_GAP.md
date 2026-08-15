# BE_NA_IMPLEMENTATION_GAP

**Écart entre ce que la Belgique prescrit et ce que le moteur sait faire.**

Généré le 2026-08-15 depuis `catalogue.json`, `ndp/data/be.json` et le code du
moteur. Chiffres vérifiés, non reconduits d'un rapport antérieur.

---

## Verdict

> **Le projet n'est pas « compatible Belgique ».**
>
> Il est **documenté** à 95 %, **transcrit** à 2 %, **confirmé à 0 %**.
> En mode strict, aucun calcul belge ne peut aujourd'hui aboutir — et c'est
> le comportement voulu.

Ces trois pourcentages ne mesurent pas la même chose et ne se rattrapent pas
l'un l'autre. Un PDF sur le disque n'est pas une valeur ; une valeur
transcrite n'est pas une valeur validée ; une valeur validée n'est pas une
règle implémentée.

---

## Les six niveaux

| niveau | mesure | état |
|---|---|---|
| 1. Documenté | annexes détenues | **56 / 59** |
| 1bis. Texte de base | pile EC2 1-1 (base + 2 corrigenda + A1) | **complète** |
| 2. Transcrit | annexes portées dans le moteur | **1 / 56** |
| 3. Confirmé | paramètres validés par un vérificateur nommé | **0 / 29** |
| 4. Codé | paramètres consommés par le moteur | 10 / 29 |
| 5. Testé | **374 moteur + 88 import = 462**, tous verts | voir §5 |
| 6. Mode strict | paramètres franchissant la porte | **0** |

---

## 1. Ce qui est documenté

### Annexes nationales — 56 détenues sur 59

Complètes : EC1 (10/10), EC2 (4/4), EC4 (3/3), EC5 (3/3), EC6 (4/4),
EC7 (2/2), EC8 (6/6), EC9 (5/5).

Manquantes : 3.

| norme | référence | situation |
|---|---|---|
| EN 1990/A1 | `NBN EN 1990/A1 ANB` | à acquérir |
| EN 1993-1-3 | `NBN EN 1993-1-3 ANB` | **dans l'archive reçue le 15/08, non enregistrée** |
| EN 1993-1-10 | `NBN EN 1993-1-10 ANB` | **dans l'archive reçue le 15/08, non enregistrée** |

L'archive n'a pas été enregistrée parce qu'elle contient aussi
`NBN EN 1993-1-1 ANB:2018`, qui remplace une édition au statut `acquired`.
La décision n° 3 (« une nouvelle édition revient à `acquired_for_reading` »)
doit être implémentée d'abord, sans quoi l'enregistrement ferait hériter à
l'édition 2018 une validation portant sur celle de 2010.

### Règlements nationaux — 3 détenus

Arrêté Royal, `NBN S 21-204`, `NBN S 21-208-1`.

### Eurocodes de base — la pile EC2 1-1 est complète

**RÉSOLU le 15/08.** Le catalogue comptait zéro Eurocode de base ; il en
enregistre maintenant trois pour l'EC2 1-1, sous le rôle `base_eurocode` qui
existait dans le modèle sans être utilisé :

| entrée | référence | rôle |
|---|---|---|
| `BE-EN199211-BASE` | `NBN EN 1992-1-1:2005 (+AC:2010)` | base + les deux corrigenda, annexés p. 256-279 |
| `BE-EN199211-A1` | `NBN EN 1992-1-1/A1 (2015)` = `EN 1992-1-1:2004/A1:2014` | amendement, 7 modifications |
| `BE-EN199211-GEN2` | `NBN EN 1992-1-1:2023` | 2ᵉ génération, `not_yet_applicable` |

Ce qu'un `base_eurocode` apporte n'est pas une valeur nationale, c'est le
**texte** d'une expression que l'annexe désigne.

#### Deux axes, à ne pas confondre

Une version antérieure de ce rapport les collapsait, et un test allait jusqu'à
interdire le statut `acquired` aux normes de base. C'était faire porter le
refus par le mauvais axe.

| axe | champ | question | portée |
|---|---|---|---|
| **documentaire** | `status` | le fichier en main est-il le texte publié qui gouverne, ou une consolidation d'éditeur / une copie non déclarée ? | **le fichier** |
| **normatif** | `document_role` | ce *type* de document peut-il fixer un paramètre national ? | **la nature du document** |

Ils sont **indépendants**. Un Eurocode de base peut être parfaitement
authentique — nos exemplaires portent « norme belge enregistrée » sans aucune
réserve d'éditeur — et rester incapable de fixer un NDP : le refus vient de
`DocumentRole.can_fix_national_parameters`, jamais du statut. Inversement une
Annexe Nationale, seule habilitée, peut n'être détenue que sous forme de
consolidation et ne rien confirmer du tout.

Si les trois entrées ci-dessus sont à `acquired_for_reading`, c'est pour la
seule raison qui vaille : leur identité a été **lue par une machine** sur une
page de garde et **déclarée par personne**. Le jour où un ingénieur la
déclare, elles passeront à `acquired` sans gagner la moindre autorité
normative.

Et cet axe documentaire n'a rien à voir avec `ValidationStatus.CONFIRMED`,
qui est un troisième niveau encore : celui d'un **paramètre**, pas d'un
document.

**Piège enregistré au catalogue** (`contained_layers`) : la couverture annonce
« (+AC:2010) » mais les corrigenda sont **annexés, pas fondus**. Le corps
(p. 7-253) porte le texte de 2004. Vérifié sur §6.2.5(2), où le corps donne
`c = 0,25 / 0,35 / 0,45` et la modification n° 29 les remplace.

Restent non catalogués : les bases EC2 1-2, 2 et 3, sur disque.

### Questions d'édition ouvertes

| entrée | question | pièce manquante |
|---|---|---|
| `NBN EN 1996-1-2 ANB` | éditions 2012 et 2019 détenues ; la couverture 2019 écrit « remplace**ra** », au futur | date d'homologation publiée au Moniteur belge |

### Traçabilité des fichiers

10 des 56 annexes détenues n'ont pas de nom de fichier enregistré : déposées
par des scripts antérieurs qui ne l'écrivaient pas. On n'y remonte que par
l'empreinte SHA-256.

---

## 2. Ce qui est transcrit

**Une annexe sur 56.**

| annexe | paramètres | état |
|---|---|---|
| `NBN EN 1992-1-1 ANB` (août 2010) | 29 | transcrits avec clause, page, statut |
| `NBN EN 1993-1-1 ANB` (déc. 2010) | 11 | **lus, inventoriés, absents du moteur** |
| `NBN EN 1993-1-2 ANB` (déc. 2010) | 5 | **lus, inventoriés, absents du moteur** |
| 53 autres | — | jamais ouvertes, inventaire non établi |

### Les 16 paramètres lus et non transcrits

EC3 1-1 : `alpha_LT`, `alpha_cr_min_plastique`, `beta_deversement`, `gamma_M0`,
`gamma_M1`, `gamma_M2`, `k_fl`, `k_imperfection_element`, `lambda_LT_0`,
`lambda_c_0`, `temperature_service_min`.

EC3 1-2 : 5 paramètres.

L'EC3 1-1 porte en outre, relevé p. 21 :

> Les annexes C à G de l'ANB définissent des méthodes **belges** pour
> M<sub>cr</sub>, N<sub>cr</sub>/N<sub>cr,T</sub>/N<sub>cr,TF</sub>,
> L<sub>cr</sub> et λ<sub>LT</sub>. **Elles n'existent pas dans l'EN.**

C'est votre point 7 sous sa forme la plus littérale : un moteur conforme en
Belgique doit **implémenter** ces méthodes, pas seulement paramétrer l'EN.
Aucune n'est codée.

### Défauts de pagination dans les données transcrites

Les références de page de `be.json` sont ambiguës et au moins une est fausse :
`§6.2.2(1)` et `§7.2(2)` portent tous deux « p. 17 » alors qu'ils sont sur
deux pages distinctes (folios 15 et 18). La convention — folio imprimé ou
index PDF — n'est nulle part fixée.

---

## 3. Ce qui est confirmé

**Zéro.**

Sur les 29 paramètres transcrits, aucun ne porte `verified_by` ni
`verified_at`. Aucun n'est au statut `CONFIRMED`.

Répartition réelle des 29 :

| état | n | ce qui manque |
|---|---|---|
| lus dans l'annexe, non validés | 21 | un vérificateur nommé et une date |
| clause jamais ouverte, valeur = recommandation EN | 6 | une lecture — **faite le 15/08, voir §6** |
| valeur d'attente (`w_max`) | 1 | séparation des appels de note, à l'œil |
| formule, non représentable (`cot_theta_max`) | 1 | un modèle admettant une expression |

---

## 4. Ce qui est codé

Modules EC2 : `beam_flexure`, `beam_shear`, `anchorage`, `serviceability`,
`deflection`. Plus `basis`, `materials`, `note`, `reference`, `traceability`,
`validation_levels`, `drawing`.

### Paramètres réellement consommés par le moteur

| paramètre | consommé par | testé |
|---|---|---|
| `alpha_cw` | `beam_shear` | 1 |
| `nu1_coeff`, `nu1_fck_divisor` | `beam_shear` | 0 |
| `rho_w_min_coeff` | `beam_shear` | 0 |
| `s_l_max_coeff` | `beam_shear` | 0 |
| `cot_theta_min`, `cot_theta_max` | `beam_shear`, `ndp/model` | 3 |
| `v_min_coeff`, `C_Rd_c_coeff`, `k1_shear` | `beam_shear` | — |
| `w_max`, `k3_crack_spacing` | `serviceability` | 1, 2 |
| **`s_t_max_coeff`** | **aucun code** | 0 |

**Le moteur calcule aujourd'hui avec cinq valeurs non sourcées.**
`alpha_cw`, `nu1_coeff`, `nu1_fck_divisor`, `rho_w_min_coeff` et
`s_l_max_coeff` sont étiquetés `en_recommended` : ils viennent de la
recommandation européenne, semés de mémoire, et sont utilisés dans un calcul
présenté comme belge. C'est exactement l'état où était `v_min_coeff` côté
français avant l'ouverture de l'annexe — et le moteur y calculait faux.

### Trois défauts de code identifiés

1. **`rho_w_min` — juste par câblage, faux à l'affichage.**
   `beam_shear.py:444` calcule `rho_w_min_c · √f_ck / fyk_mpa`, où
   `fyk_mpa` vient de l'objet acier **des armatures d'âme** : la substitution
   belge f<sub>ywk</sub> ← f<sub>yk</sub> est donc respectée en pratique.
   Mais le LaTeX de la note affiche `\rho_{w,min} = 0,08\sqrt{f_{ck}}/f_{yk}`
   — la forme **EN**. L'ingénieur qui lit la note y voit une règle que le
   moteur n'applique pas. Le nom de variable `fyk_mpa` entretient la
   confusion.

2. **`s_t_max_coeff` déclaré, jamais consommé.** L'espacement transversal
   §9.2.2(8) n'est vérifié nulle part.

3. **Majoration ×1,25 pour dalles appuyées sur les bords (§6.2.2(1))**
   mentionnée dans la note de `C_Rd_c_coeff` seulement, alors que l'ANB
   l'applique aux **trois** valeurs (`C_Rd,c`, `v_min`, `k₁`). Ni portée par
   `v_min_coeff` ni par `k1_shear`, ni implémentée.

### Ce que le modèle ne sait pas représenter

`ValidationStatus` ne connaît que `CONFIRMED`, `PENDING_VERIFICATION`,
`DEPRECATED`, `NOT_REPRESENTABLE`. Il n'y a pas de `value_provenance` :
rien ne distingue, dans la structure, une valeur nationale lue d'une valeur
européenne d'attente. `w_max` est étiqueté `national_annex` et porte les
valeurs du tableau EN — l'avertissement n'existe que dans la prose de `notes`.

Le modèle ne porte qu'un **scalaire** ou des **variantes conditionnelles**.
Il ne porte ni formule, ni fonction des variables de calcul. C'est pourquoi
`cot_theta_max` est `NOT_REPRESENTABLE` et pourquoi les six clauses « à lire »
n'avaient jamais pu être transcrites : **aucune des six n'est une constante.**

---

## 5. Ce qui est testé

**462 tests, tous verts : 374 moteur, 88 import.**

> **Correction.** Une version antérieure de ce rapport annonçait « 302 moteur
> + 84 import = 386 ». Ces nombres venaient d'un `grep -c "^def test"`, qui
> compte les *fonctions* de test et ignore l'expansion des tests paramétrés.
> Les chiffres ci-dessus viennent de la collecte pytest elle-même :
>
> ```bash
> python -m pytest --collect-only -q   # dans engine/ puis tools/ndp_import/
> ```

Répartition moteur : `test_ndp` 49, `test_serviceability` 34, `test_legal` 33,
`test_deflection` 32, `test_ec2_anchorage` 27, `test_dxf_elevation` 23,
`test_reference` 22, `test_ec2_beam_shear` 21, `test_ec2_beam_flexure` 20,
`test_dxf` 18, `test_note` 16, `test_materials` 16, `test_units_and_traceability` 14,
`test_contract` 11, `test_properties` 11, `test_validation_levels` 11,
`test_engine_isolation` 9, `test_determinism` 7.

Import : `test_pipeline` 88.

### Ce que les tests ne couvrent pas

- **Aucun test n'exerce** `nu1_coeff`, `nu1_fck_divisor`, `rho_w_min_coeff`,
  `s_l_max_coeff`, `s_t_max_coeff`, `cot_theta_min`, `v_min_coeff`.
  Ces paramètres traversent le moteur sans qu'aucune assertion ne porte sur
  eux.
- **Aucun cas de référence belge** n'existe. Les trois cas SLS ont migré vers
  la Belgique après la lecture de l'annexe française, mais ils exercent le
  calcul, pas les valeurs belges.
- **Aucun test ne distingue** une valeur d'annexe d'une valeur EN : c'est
  précisément le test qui aurait attrapé les cinq valeurs non sourcées du §4.

---

## 6. Ce qui bloque encore le mode strict

Le mode strict n'accepte que `ValidationStatus.CONFIRMED`
(`ndp/model.py:238`). **Zéro paramètre belge y satisfait.** Un calcul belge en
mode strict échoue donc intégralement, dès le premier paramètre demandé.

### Blocage 1 — aucun vérificateur nommé (21 paramètres)

Rien ne manque qu'une lecture humaine et une signature. Ces 21 valeurs sont
lues, paginées, sourcées.

### ~~Blocage 2 — la norme de base absente~~ — **FERMÉ le 15/08**

Les cinq formules (6.6N, 6.11aN–cN, 9.5N, 9.6N, 9.8N) sont extraites de la
base, et l'effet des corrigenda et de l'amendement est établi :

| formule | AC:2008/AC:2010 | A1:2014 | ANB:2010 |
|---|---|---|---|
| 6.6N | non modifiée | non modifiée | adoptée |
| 6.11aN–cN | non modifiée | non modifiée | adoptées |
| 9.5N | non modifiée | non modifiée | **modifiée — f_ywk ← f_yk** |
| 9.6N | non modifiée | non modifiée | adoptée |
| 9.8N | non modifiée | non modifiée | adoptée |

Méthode : les 120 modifications des corrigenda ont été énumérées, et les
sept de l'A1 lues intégralement. §6.2.2 et §6.2.3 **sont** touchés par les
corrigenda — il a fallu lire ces deux entrées pour constater qu'elles visent
d'autres paragraphes. Détail dans `docs/relecture/BE_EC2_NORMATIVE_STACK.md`.

**Aucun achat n'est nécessaire.** La liste d'achat est vide.

### Blocage 3 — le modèle ne porte pas d'expression (7 paramètres)

Aucun des sept paramètres analysés le 15/08 n'est un scalaire :

| paramètre | type réel |
|---|---|
| `alpha_cw` | `conditional_rule` — 4 branches sur σ<sub>cp</sub>/f<sub>cd</sub> |
| `nu1_coeff` + `nu1_fck_divisor` | `formula` unique en f<sub>ck</sub> — à fusionner |
| `rho_w_min_coeff` | `formula`, avec substitution de variable belge |
| `s_l_max_coeff` | `formula` en `d` et `cot α` |
| `s_t_max_coeff` | `formula` avec plafond en mm |
| `cot_theta_max` | `function` des variables de calcul **et du ferraillage** |
| `w_max` | `conditional_rule` sur classe d'exposition **et** d'environnement |

### Blocage 4 — deux questions non résolues sur pièce

1. **« Formule 6.6N-ANB »** (§6.2.3(3) NOTE 1). Le suffixe `-ANB` suggère une
   formule modifiée par l'annexe. La chaîne apparaît **une seule fois dans les
   31 pages** et aucune formule de ce nom n'y est imprimée. Coquille ou renvoi
   à un texte absent : le document en main ne tranche pas. Question au NBN.
2. **Appels de note du tableau 7.1N-ANB.** L'extraction colle les renvois aux
   valeurs (`0,4`+note 1 → `0,41`). La séparation retenue est cohérente avec
   les notes imprimées, mais résulte d'une lecture d'artefact. Confirmation
   visuelle requise.

### Blocage 5 — les rôles de validation ne sont pas séparés

Le modèle ne distingue pas `normative_verifier` de
`project_validating_engineer`. Tant que c'est le cas, valider un paramètre du
référentiel et valider un projet client passent par le même champ — ce que la
décision n° 1 interdit.

---

## Ce qui a changé le 15/08

La lecture de l'annexe a **débloqué** deux choses et **révélé** trois
problèmes.

**Débloqué**

- `cot_theta_max` : formule intégralement lisible et transcrite. Provenance
  `NATIONAL_ANNEX`. Plus aucun document ne manque.
- `w_max` : le tableau 7.1N-ANB est lisible sur l'exemplaire reçu ce jour
  (empreinte `3a195362…`, différente de celle déjà cataloguée). Le blocage
  « page illisible » tombe.

**Révélé**

- **`cot θ_max` = 2 pour une poutre non précontrainte**, là où l'EN
  recommande 2,5. La règle belge est **plus sévère**. Un repli sur la valeur
  européenne produirait des armatures d'effort tranchant **insuffisantes**.
- **`rho_w,min` divise par f<sub>ywk</sub>**, pas par f<sub>yk</sub> : l'ANB
  modifie explicitement la formule 9.5N. Le scalaire `0,08` stocké seul perd
  intégralement cette modification.
- **§9.3.1.1(3)** : la Belgique écrit ses propres espacements maximaux de
  dalles (4 branches, `2,5h ≤ 400 mm` … `1,5h ≤ 250 mm`), sans renvoyer à
  l'EN. Ce paramètre n'est dans aucune liste.

---

## Séquence proposée

1. **Séparer les deux rôles de validation** (décision 1) et lier la validation
   normative au triplet `country + standard + edition` sans héritage
   (décisions 2 et 3).
2. **Ajouter `value_provenance`** (décision 4) et faire refuser
   `EUROCODE_DEFAULT` par le mode strict (décision 5).
   → permet ensuite d'enregistrer l'archive du 15/08 sans faux héritage.
3. **Étendre le modèle de règle** aux quatre types (décision 6) — puis
   transcrire les sept paramètres analysés.
4. ~~Acquérir `NBN EN 1992-1-1:2005`~~ — **fait**, la pile est en main.
   Transcrire les cinq formules une fois l'étape 3 livrée.
5. **Corriger les trois défauts de code** du §4.
6. **Traiter les méthodes propres des annexes** comme des exigences de calcul
   (décision 7), en commençant par les annexes C à G de l'EC3 1-1.

Les étapes 1 à 3 ne dépendent d'aucun document. **L'étape 4 n'est plus un
achat** : la pile normative EC2 1-1 est détenue depuis le 15/08 et la liste
d'achat est vide. Il reste une transcription, qui dépend de l'étape 3.

---

## Comment régénérer ce rapport

```bash
cd eurostruct/tools/ndp_import
python scripts/audit_annexes.py --country BE            # niveaux 1 à 3
python scripts/audit_annexes.py --country BE --format csv
cd ../../engine && python -m pytest -q                  # niveau 5
```

L'analyse clause par clause est dans
`docs/relecture/BE_EC2_CLAUSES_ANALYSE.md`.
