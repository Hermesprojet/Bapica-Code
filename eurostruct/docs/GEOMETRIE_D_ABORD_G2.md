# Géométrie d'abord — G2 : les axes par leur signature

> **Statut : réalisé (`5b86e2c`), mesuré au § 7.** Phase G2 de `GEOMETRIE_D_ABORD.md`
> (§ 11 : « classes de cercles, bulles par structure, axes A et B, zone
> structurelle »), selon les règles du § 3 (axes) et de l'échelle de preuves
> du § 1.4. Elle s'appuie sur l'information N1 lue par G1
> (`GEOMETRIE_D_ABORD_G1.md`). C'est la **première phase qui change des
> sorties** : chaque changement est mesuré et cité (§ 7).

## 0. Ce que G2 fait, et ce qu'il garantit

**Objet.** Reconnaître les axes d'un DXF par ce qu'ils SONT — une droite
longue, d'une famille de parallèles, finissant sur une bulle, ou dessinée en
trait-point parallèlement à une telle famille — avant de regarder les noms,
pour que la grille soit lue quand les calques et les blocs sont renommés, la
langue inconnue, ou qu'aucune convention de nom n'existe.

**Garanties.**

| # | Garantie | Comment |
|---|---|---|
| J1 | **Tout axe reconnu aujourd'hui par les noms le reste**, avec les mêmes traits, la même étendue, la même étiquette. | La géométrie n'enlève jamais un axe nommé ; quand elle le confirme, elle ne touche ni à ses traits ni à son étendue (§ 2.6). |
| J2 | Un axe ajouté l'est par une **signature complète** (A ou B), jamais par la géométrie partielle seule. | § 2.3 à 2.5 ; une signature partielle sans nom n'ajoute rien (les candidats exportés sont en G6). |
| J3 | Une feuille PDF ne change pas : elle reconnaît déjà ses axes par le style appris de ses bulles. | Les signatures ne sont évaluées que sur un DXF. |
| J4 | Rien n'est inventé : une étiquette est un texte LU, une bulle un contour LU, un motif un motif LU. | Interdiction 2. |
| J5 | Tout changement de sortie est cité : axes ajoutés, retirés, confiances, propositions, sur le plan réel et sur tout le corpus. | § 7. |

**Hors de G2.** Les candidats exportés et les partitions apprises (§ 1.5 et
§ 1.4, cas 3 et 6 : G6) ; les poteaux, pieux et voiles (G3 à G5) ; les cotes
d'axe à axe comme critère (corroboration seulement, § 3.1) ; le recoupement de
`$INSUNITS` (D1). Une signature PARTIELLE sans nom ne donne donc rien en G2 :
elle est seulement citée sur l'axe qu'un nom a reconnu (§ 2.6, cas 2).

## 1. Point de départ mesuré (audit, `0.4.0`)

| Variante du plan réel | Axes | Étiquettes |
|---|---|---|
| origine | 71 | 61 |
| v01 calques neutres | 65 | 61 |
| v02 blocs neutres | 60 | 43 |
| v04 aucune convention (calques, blocs neutres, tout en continu) | **0** | **0** |
| v05 calques et blocs en espagnol | 19 | 16 |
| v06 allemand / v07 AIA | 71 / 71 | 61 / 61 |
| v12 étiquettes en minuscules | 62 | 23 |
| v13 calques et blocs neutres, types de ligne gardés | 19 | 16 |

Mesure de faisabilité, sans aucun nom (`GEOMETRIE_D_ABORD.md` § 3.1) : bulles
+ famille → 60 droites, 59 / 71, 0 autre ; + trait-point parallèle → 67
droites, 66 / 71, 0 autre.

## 2. Les règles

Les seuils sont ceux de `GEOMETRIE_D_ABORD.md` § 3 ; les quelques choix que
G2 ajoute sont signalés « **choix G2** », avec leur raison.

### 2.1 Les bulles, par leur structure (N1 + N2)

Une **bulle** est un contour fermé compact, de rayon `r`, qui contient
**exactement un texte court** (et aucun autre texte) :

* un `CIRCLE` (rayon `r`) ;
* une polyligne fermée **régulière** à 4, 6 ou 8 côtés (carré, hexagone,
  octogone) : côtés égaux à 5 % près, sommets à égale distance du centre à
  5 % près ; `r` = distance moyenne des sommets au centre — **choix G2** :
  5 %, la même tolérance que l'égalité des rayons d'une famille ;
* un `INSERT` dont la DÉFINITION (G1, F4) contient un cercle ou une polyligne
  fermée et **un seul `ATTDEF`** : son cercle (ou sa polyligne) placé par
  l'insertion est le contour, la valeur de son attribut le texte — quel que
  soit le nom du bloc.

**Texte court** (`GEOMETRIE_D_ABORD.md` § 3.5) : 1 à 4 caractères parmi
lettres, chiffres, point, prime, tiret ; lu TEL QUEL (casse comprise).

**Les classes de cercles** (§ 3.2, désambiguïsation) : les bulles sont
regroupées par rayon (5 %) ; un membre est **au bout d'une droite** si un
trait droit de longueur ≥ 20 `r` passe à moins de 0,25 `r` de son centre et
finit à moins de `r` avant lui ou à moins de 4 `r` au-delà (les fenêtres des
bulles d'aujourd'hui). Une classe n'est une classe de bulles que si **la
moitié au moins** de ses membres sont au bout d'une droite — **choix G2** :
une classe de pieux numérotés ou de repères de locaux, nombreuse et posée
loin des bouts de droites, est écartée en bloc ; une classe de bulles d'axes
l'est presque entièrement (61 sur 62 au rayon modal du plan réel).

### 2.2 Les droites candidates

Les traits droits (hors arcs aplatis) sont regroupés par **partition
anonyme** (calque, type de ligne — N1 : la clé, jamais le nom), puis les
morceaux colinéaires d'une même partition sont fusionnés (même direction à
0,2° près, même décalage à 2 tolérances près : la règle d'aujourd'hui).
**Choix G2** : la partition évite qu'un nu de voile ou de poutre colinéaire
à un axe ne prolonge l'axe ; deux morceaux d'un même axe sur deux calques
restent deux droites, réunies si toutes deux sont admises (§ 2.6).

### 2.3 Signature A (complète)

Une droite candidate a la signature A si :

1. elle finit, à un bout au moins, sur une bulle d'une classe de bulles
   (§ 2.1) ;
2. elle mesure au moins **20 `r`** (r : rayon de cette bulle) ;
3. elle appartient à une **famille** — au moins deux droites parallèles (0,2°)
   qui satisfont 1 et 2 avec des bulles de **même rayon à 5 % près**.

### 2.4 La zone structurelle

L'enveloppe (rectangle) des droites de signature A, élargie de l'**entraxe
médian** de leurs familles (`GEOMETRIE_D_ABORD.md` § 3.2) : sa diagonale
remplace celle de l'espace objet entier, que gonflent cartouche, légendes et
détails (risque 12 de l'audit). Sans droite A, pas de zone, donc pas de B.

### 2.5 Signature B (complète, N1 + N2)

Une droite candidate a la signature B si :

1. son motif (G1, F1) est **`mixte`** (trait-point) ;
2. elle mesure au moins **10 % de la diagonale de la zone structurelle** ;
3. elle est **parallèle à 0,2° près à une famille A** ;
4. elle **traverse la zone** (son segment coupe le rectangle de la zone) —
   **choix G2**, lecture du § 3.1 (« traversant la zone des éléments ») : un
   trait-point parallèle à la grille dans un détail éloigné n'est pas un axe.

### 2.6 L'échelle de preuves, pour les axes

Les axes reconnus par les noms (règles actuelles, N3) et les droites de
signature complète sont réunis ainsi (`GEOMETRIE_D_ABORD.md` § 1.4) :

| Cas | Décision | `classified_by` | Confiance |
|---|---|---|---|
| 1. Signature complète, nom concordant (rôle `axe` par calque, bloc ou type de ligne) | axe ; **la droite nommée est gardée telle quelle** (traits, étendue) | `geometrie`, le nom cité (`matched_name`) | table § 2.8, **+ 0,05** (plafond 0,90) |
| 1'. Signature complète, aucun nom de rôle | axe ajouté (la droite géométrique) | `geometrie` | table § 2.8 |
| 2. Signature partielle (bulle seule, trait-point seul…), nom concordant | axe, comme aujourd'hui ; les critères vus sont cités (`signature`) | la règle du nom | règle actuelle |
| 4. Nom seul, géométrie muette | axe, comme aujourd'hui | la règle du nom | règle actuelle |
| 5. Signature complète, nom d'un AUTRE rôle (cote, texte, pieu, poteau…) | axe ajouté, **conflit dit** dans `unresolved` avec les deux preuves | `geometrie` | plafonnée à **0,4** |
| 6. Signature partielle, aucun nom | rien en G2 (candidats : G6) | — | — |

« Concordant » : un trait de la droite est classé `axe` par son nom.
« Coïncide » : même droite infinie (direction à 0,2°, décalage à 2 tolérances)
— un axe est une droite, pas un trait. Deux droites géométriques admises qui
coïncident sont réunies (morceaux d'un même axe sur deux partitions).

### 2.7 Étiquettes

* L'affectation globale d'aujourd'hui (un texte sert un seul axe, le plus
  proche ; bulle et bloc avant texte libre ; deux preuves de même force qui se
  contredisent : pas d'étiquette) s'applique à TOUTES les droites, nommées et
  géométriques.
* **Bulles-blocs par structure** (§ 2.1) : ajoutées aux bulles-blocs nommées,
  à la même force (`bloc`).
* **Textes courts hors format** (`a`, `A.1`, `1a`…) DANS une bulle : lus tel
  quels, **en complément** — comme les étiquettes « L1 » d'aujourd'hui : à une
  extrémité sans étiquette de forme courante seulement, jamais contre elle
  (`label_source.form = "texte_court"`). **Choix G2** : une étiquette
  aujourd'hui lue ne peut ni changer ni disparaître à cause d'eux.
* Hors bulle, la règle actuelle des textes libres reste.

### 2.8 Confiance (§ 3.3)

| Décision | Étiquette par une bulle ou un bloc | Par un texte libre | Sans étiquette |
|---|---|---|---|
| Signature A ou B | 0,85 | 0,75 — **choix G2** : le rang d'un texte libre d'aujourd'hui | 0,6 |
| + nom concordant | + 0,05 (plafond 0,90) | + 0,05 | + 0,05 |
| conflit de nom | ≤ 0,4 | ≤ 0,4 | ≤ 0,4 |
| Nom seul (cas 2 et 4) | règle actuelle : 0,85 (0,75 par type de ligne) | idem | 0,6 |

Les propositions suivent : `grid_line` prend la confiance de l'axe,
`grid_spacing` la plus faible des deux axes (± cotes), le tout plafonné à
0,90 (`propositions.py`, inchangé).

### 2.9 Ce qui ne change pas

Fusion des morceaux nommés, seuils des traits nommés, axes courts gardés par
leur bulle, textes libres, étiquettes « L1 », familles, repère, nœuds,
nommage, grille rayonnante (refus), et toute la lecture d'une feuille PDF.

## 3. Sorties et contrat

* `evidence.classified_by` gagne la valeur **`geometrie`** — contrat fermé :
  `engine/schemas/structure.py` (`Literal`), `packages/contracts` (régénéré),
  étiquette de l'écran (`web/lib/documents.ts`) ; aucune migration (JSON sans
  contrainte SQL sur ces valeurs).
* `evidence.signature` (nouveau, liste, facultatif) : les critères vus —
  `bulle`, `famille`, `motif_mixte`, `parallele_a_une_famille`, `zone` —
  sur tout axe qui en a au moins un.
* `unresolved` : un conflit nom/signature (cas 5) est une entrée, avec le nom
  et la signature.
* **Version `0.5.0`** : les propositions peuvent changer. (La ligne G6 de
  `GEOMETRIE_D_ABORD.md` § 11 annonçait 0.5.0 ; G2 étant la première phase qui
  change des sorties, chaque phase suivante incrémentera à son tour.)

## 4. Tests

Fixtures nouvelles (`fabrique_geometrie`), § 3.6 du plan :

* grille à bulles rondes, tout sur le calque `0`, en continu (A seule) ;
* grille à bulles hexagonales, calques sans nom de rôle ;
* grille dont une famille n'a pas de bulle mais est en trait-point (B) ;
* repère de coupe : trait-point terminé par deux cercles numérotés, parallèle
  à la grille, hors de la zone (refusé) ;
* repères de locaux et pieux numérotés dans des cercles (classe écartée) ;
* grille sans bulle ni trait-point, sans nom (refus : aucun axe) ;
* bulles-blocs à un attribut sous un nom quelconque ;
* étiquettes en minuscules dans des bulles (complément) ;
* un axe sur un calque nommé « cotes » (conflit, 0,4) ;
* **invariance** : le même plan, calques, blocs et types de ligne renommés au
  hasard → même grille, mêmes étiquettes, mêmes nœuds.

Les tests existants qui fixent `classified_by` ou une confiance d'axe sont
relus un par un : un changement voulu par § 2.6/§ 2.8 est mis à jour et dit
(§ 7) ; tout autre changement est un défaut.

## 5. Validation

* Suites d'extraction et d'API, harnais des documents, `export_contracts.py
  --check`, depuis l'arbre gelé.
* **Balayage complet** (les 94 fichiers de G1) avant (`f7e8793`, 0.4.0) /
  après : chaque fichier dont la sortie change est listé et chaque changement
  classé (axe ajouté, retiré, étiquette, confiance, `classified_by`,
  proposition).
* **Plan réel** : axes ajoutés, retirés, étiquettes, confiances, propositions
  (catégorie, valeur, confiance) ; précision et rappel contre les sorties
  actuelles.
* **Variantes de l'audit** (v01, v02, v04, v05, v06, v07, v12, v13) et deux
  nouvelles : **v14 tout renommé** (calques, blocs, types de ligne ; motifs
  gardés) et **v15 tout sur `0`** (entités des calques éteints ou gelés
  retirées, types de ligne effectifs écrits sur l'entité). Cibles du plan
  (§ 3.6) : v14 ≥ 66 axes et 61 étiquettes, 0 axe hors référence ; v04 et
  v15 ≥ 61 axes.

**Précision et rappel** : un axe d'une sortie est APPARIÉ à un axe de
référence s'ils sont sur la même droite (les deux extrémités de l'un à moins
de 2 tolérances de la droite de l'autre). Rappel = axes de référence
appariés / axes de référence ; précision = axes appariés / axes de la sortie.

## 6. Risques connus

Repère de coupe parallèle à la grille DANS la zone (peut passer B) ; carrés
de poteaux numérotés au bout d'un axe (polygone à un texte) ; deux grilles
d'échelles différentes dans un même espace objet (classes de rayons) ; axes
sans bulle ni trait-point (aucune signature : N3 seul).

## 7. Résultats

Mesuré sur le commit du code `5b86e2c` (version `0.5.0`), contre les sorties
de `0.4.0` (`f7e8793`, celles de la campagne G1). L'arbre de travail est resté
gelé pendant toutes les exécutions (empreinte identique avant et après). Les
sorties du commit sont celles qui ont été analysées pendant le
développement : balayage refait sur le commit, **94 / 94 identiques octet
pour octet** ; variantes refaites, **17 / 17 identiques** (hors durée
mesurée).

« Apparié », précision et rappel : § 5. La référence est la sortie actuelle
(`0.4.0`) du plan réel : 71 axes, dont 61 étiquetés.

**En bref.** Sur le plan réel, rien n'est ajouté ni retiré (précision et
rappel 71 / 71) ; 66 axes sur 71 sont désormais décidés par leur signature, et
leur confiance gagne 0,05 parce que le nom concorde. Quand les noms
disparaissent, la grille revient : **0 → 66 axes** sur le plan tout renommé,
précision 1,000, rappel 0,930, 59 étiquettes justes. Aucun axe n'est retiré
nulle part. Une seule variante produit des axes hors référence : les blocs
explosés (9, dont une étiquette déplacée, § 7.6).

### 7.1 Suites, contrat, harnais, balayage

| Validation | Résultat |
|---|---|
| Suite d'extraction | **446 tests, 0 échec** (417 en G1 ; 29 de plus, ci-dessous) |
| Suite de l'API | **599 tests, 0 échec**, 340 ignorés — les mêmes 599 / 340 qu'en G1 |
| `export_contracts.py --check` | 0 : le contrat commité (`classified_by` = `geometrie`, `signature`) est celui que le schéma régénère |
| Harnais des documents (`db/test/documents_extractions.sh`, base jetable) | 0 : 34 tests réussis, comme en G1 (dépôt, analyse, propositions, décisions, calcul) |
| Balayage des 94 fichiers de G1 | 94 / 94 analysés sans exception ; **62 identiques à `0.4.0`** hors numéro de version, **32 changés** (§ 7.5) |
| Variantes du plan réel (17) | 17 / 17 analysées sans exception |
| `VERSION_EXTRACTEUR` | `0.5.0` : des propositions changent (confiances, et propositions nouvelles sur les variantes sans nom) |

Tests : `test_geometrie_axes_signatures.py` (nouveau, 27 tests : chaque
fixture du § 4, et J1 sur dix plans nommés — sans les signatures puis avec :
mêmes axes, étiquettes, droites, nœuds). Un seul fichier de tests existant
change, `test_geometrie_n1.py` : son invariance « neutraliser toute
l'information N1 ne change rien » était vraie en G1 et ne l'est plus, puisque
G2 lit le motif et les définitions de blocs ; elle est restreinte (sous un
nouveau nom, mêmes deux plans) à l'information N1 que rien ne lit encore
(couleurs, multilignes, échelle d'insertion), et deux tests sont ajoutés (une
grille à bulles reste reconnue sans motif ni définition ; un motif illisible
est compté et ne fait rien lever) : 417 − 2 + 31 = 446. Aucun autre test
existant n'a été modifié. Le surcroît de durée de la suite (13 s → 32 s) est
celui de `test_ocr` (1,6 s → 15,7 s, machine chargée) ; les 414 autres tests
communs durent le même temps.

### 7.2 Plan réel

| | `0.4.0` | `0.5.0` |
|---|---|---|
| Axes | 71 | **71 : 0 ajouté, 0 retiré** ; mêmes identifiants, étiquettes, droites (traits et étendue) |
| Étiquetés | 61 | 61 |
| Nœuds, poteaux, pieux, voiles | 299, 64, 477, 4 | identiques |
| Propositions | 335 | 335 : mêmes catégories, valeurs, unités, repères |
| `unresolved` | | aucune entrée nouvelle |

**Précision 71 / 71 = 1,000 ; rappel 71 / 71 = 1,000** ; étiquettes justes
71 / 71. La géométrie décide seule **66 des 71 axes** (rappel géométrique
0,930) :

| Axes | Signature vue | Règle `0.4.0` → `0.5.0` | Confiance |
|---|---|---|---|
| 59 étiquetés | **A** : bulle, famille, trait-point | `bloc` → `geometrie` (nom concordant cité) | 0,85 → **0,90** |
| 7 sans étiquette | **B** : trait-point, parallèle à une famille, zone | `calque` (5), `bloc` (2) → `geometrie` | 0,60 → **0,65** |
| 2 étiquetés | partielle : bulle, trait-point — chacun est le seul axe à bulle de sa direction (deux obliques uniques) : pas de famille | `bloc`, inchangée | 0,85 |
| 3 sans étiquette | aucune : tracés en **tirets** (pas en trait-point), sans bulle | `calque`, inchangée | 0,60 |

Propositions : seules des confiances changent, 52 sur 335 — la règle
inchangée de `propositions.py` répercute celle des axes.

| Catégorie | Avant → après | Nombre |
|---|---|---|
| `grid_line` | 0,85 → 0,90 | 18 |
| `grid_spacing` | 0,85 → 0,90 | 15 |
| `grid_spacing` | 0,60 → 0,65 | 9 |
| `grid_spacing` | 0,65 → 0,70 | 1 |
| `building_dimension` | 0,80 → 0,85 | 9 |

### 7.3 Variantes : calques renommés, blocs renommés

| Variante du plan réel | Axes | Étiquetés | Précision | Rappel | Décidés par la géométrie |
|---|---|---|---|---|---|
| v00 réenregistré | 71 → 71 | 61 → 61 | 1,000 → 1,000 | 1,000 → 1,000 | 66 |
| **Calques renommés** | | | | | |
| v01 calques neutres | 65 → 68 | 61 → 61 | 1,000 → 1,000 | 0,915 → **0,958** | 66 |
| v05 calques et blocs en espagnol | 19 → 67 | 16 → 60 | 1,000 → 1,000 | 0,268 → **0,944** | 66 |
| v06 allemand / v07 AIA | 71 → 71 | 61 → 61 | 1,000 → 1,000 | 1,000 → 1,000 | 66 |
| v13 calques et blocs neutres, types de ligne gardés | 19 → 67 | 16 → 60 | 1,000 → 1,000 | 0,268 → **0,944** | 66 |
| v14 **tout renommé** (calques, blocs, types de ligne ; motifs gardés) | **0 → 66** | 0 → 59 | — → 1,000 | 0,000 → **0,930** | 66 |
| v15 tout sur le calque `0` | 65 → 68 | 61 → 61 | 1,000 → 1,000 | 0,915 → **0,958** | 66 |
| v04 aucune convention (calques et blocs neutres, tout en continu) | **0 → 59** | 0 → 59 | — → 1,000 | 0,000 → **0,831** | 59 |
| **Blocs renommés** | | | | | |
| v02 blocs neutres | 60 → 71 | 43 → 52 | 1,000 → 1,000 | 0,845 → **1,000** | 66 |
| v11 blocs explosés | 23 → 76 | 23 → 50 | 1,000 → **0,882** | 0,324 → **0,944** | 75 |
| **Autres** | | | | | |
| v03 sans types de ligne | 71 → 71 | 61 → 61 | 1,000 → 1,000 | 1,000 → 1,000 | 59 |
| v12 étiquettes en minuscules | 62 → 71 | 23 → 61 | 1,000 → 1,000 | 0,873 → **1,000** | 66 |
| v08 / v09 `$INSUNITS` mm / m | 71 → 71 / 72 → 72 | 61 / 62 | 1,000 / 0,986 (inchangées) | 1,000 | 66 / 67 |
| v10 rotation de 30° | 71 → 71 | 61 → 61 | (pas de référence tournée) | | 66 |

**Calques renommés.** Quels que soient les noms de calques — neutres,
espagnols, tous sur `0`, ou tout renommé jusqu'aux types de ligne —, la
grille revient à **66 à 68 axes sur 71** (71 quand les noms restent
reconnus : allemand, AIA), **sans aucun axe hors référence**, et toutes ses
étiquettes justes. Ce qui manque est dit par la signature : les 3 axes en
tirets sans bulle (aucun critère : ils ne tiennent qu'à leur nom de calque)
et, quand aucun nom ne les porte plus, les 2 axes obliques à bulle isolée
(tous deux sur v14 et v04, l'un des deux sur v05 et v13). Sans motif de ligne
du tout (v04), la signature B est impossible : les 59 axes A restent, les
7 axes B et les 5 autres manquent.

**Blocs renommés.** v02 retrouve les 71 axes (11 ajoutés, tous de la
référence) ; 9 étiquettes de la série « L » chiffrée y manquent toujours :
leurs textes sont sur un calque que son nom classe cartouche, et le veto du
cartouche dans le complément « L1 » est inchangé (§ 2.9, test
`test_le_cartouche_n_etiquette_pas_un_axe`) — absentes, pas fausses. v11
(blocs explosés, l'arrière-plan architectural mis à nu) : rappel 0,324 →
0,944, mais 9 axes hors référence (§ 7.6).

**Unités** (v09) : l'axe hors référence existait en `0.4.0` — un trait
étiqueté de la série « L » chiffrée qui double, à 0,01 unité près,
l'extrémité d'un axe de la grille ; sous l'hypothèse « mètre », la tolérance
est cent fois plus fine et les deux droites ne coïncident plus. G2 ne fait que
le confirmer (signature complète) : 0,85 → 0,90.

**Étiquettes en minuscules** (v12) : 71 axes, 61 étiquetés, **71 / 71
justes à la casse près** — la casse est lue telle quelle : 38 étiquettes en
minuscules par le complément « texte court » (`label_source.form =
"texte_court"`), contre 23 étiquettes en tout en `0.4.0` ; aucune étiquette
lue en `0.4.0` ne change ni ne disparaît.

### 7.4 Chaque axe ajouté, chaque axe retiré

**Retirés : 0** — sur le plan réel, les 17 variantes et les 94 fichiers du
balayage (appariement par la droite). Le classement du balayage par
identifiant affiche des « retraits » sur v01, v02, v05, v12, v13 et v15 :
l'identifiant d'un axe sans étiquette est son rang dans sa famille, et un axe
ajouté avant lui le renumérote ; **chaque identifiant disparu a sa droite
retrouvée sous un autre** (2, 10, 2, 33, 2 et 2). Aucune droite d'un axe déjà
trouvé n'a changé, aucune de ses étiquettes n'a changé ni disparu ; v12 seul
en gagne (29, en minuscules).

**Ajoutés** (aucun sur le plan réel) :

| Fichier | Ajoutés | Lesquels |
|---|---|---|
| v01, v15 | 3 | 3 axes B sans étiquette de la référence (0,65) |
| v02 | 11 | 9 axes A étiquetés de la série « L » lettrée, étiquettes justes (0,90) ; 2 axes A sans étiquette de la série « L » chiffrée (0,65) — tous de la référence |
| v04 | 59 | les 59 axes A de la référence, étiquettes justes (0,85) |
| v05, v13 | 48 | 44 axes A étiquetés justes (0,90) et 4 axes B sans étiquette (0,65), de la référence |
| v11 | 53 | 44 de la référence (26 A étiquetés justes à 0,90, 11 A sans étiquette à 0,65, 7 B à 0,65) ; **9 hors référence** (§ 7.6) |
| v12 | 9 | 9 axes A de la série « L » lettrée, étiquettes en minuscules lues telles quelles (0,90), de la référence |
| v14 | 66 | les 59 axes A (étiquettes justes, 0,85) et les 7 axes B (0,60) de la référence |
| `n1_types_de_ligne` (fixture de G1) | 6 | les 6 axes de sa grille (A à C, 1 à 3 ; calque neutre, type de ligne au nom inconnu), 0,85 |

### 7.5 Balayage du corpus (94 fichiers)

* **62 inchangés** hors numéro de version : les 36 DXF d'exemple d'ezdxf,
  les 9 feuilles PDF (fabriquées et réelles : J3), les 10 sondes de texte et
  d'unité, le plan synthétique des cotes, et 6 DXF fabriqués où aucun critère
  n'est vu (une grille sans bulle ni trait-point, la grille rayonnante
  refusée, un cercle sans unité, deux plans de texte, le refus).
* **24 changés sans axe ajouté ni retiré** : 11 plans fabriqués nommés des
  tests, le plan réel et sa copie de l'audit, ses variantes v00, v03, v06 à
  v10, et 4 DXF riches en N1. Mêmes axes, étiquettes, droites, nœuds,
  propositions ; seuls changent `classified_by` (→ `geometrie`), les
  confiances (+ 0,05 sur l'axe et ses propositions, plafond 0,90) et
  `evidence.signature`. Deux fichiers
  (`sans_calques_m`, `n1_hachures_couleurs`) ne gagnent que
  `evidence.signature` (signature partielle citée, règle et confiance
  inchangées).
* **8 changés avec des axes ajoutés** : v01, v02, v04, v05, v11, v12, v13 et
  `n1_types_de_ligne` (§ 7.4).

### 7.6 Ce que G2 ne résout pas, ou dégrade

1. **v11, blocs explosés : 9 axes hors référence**, aucun avant G2. Sept
   traits-points de l'arrière-plan architectural, parallèles à la grille et
   traversant la zone (B, sans étiquette, 0,60) ; un trait à bulle et famille
   sans étiquette (0,60) ; et **une étiquette déplacée** : un trait continu
   qui traverse la bulle « LF » reçoit l'étiquette (A, 0,85), tandis que le
   vrai axe « LF », en trait-point et finissant sur la même bulle, est trouvé
   sans étiquette. C'est la règle d'affectation d'aujourd'hui (§ 2.7 : un
   texte sert l'axe le plus proche), appliquée telle que conçue. Remède
   proposé, hors G2 : deux droites qui réclament la même bulle ne reçoivent
   l'étiquette ni l'une ni l'autre, et un doute est dit — à concevoir avec
   les candidats de G6.
2. **Poteaux sur les variantes sans nom.** La grille retrouvée porte les
   poteaux « forme au nœud » ; sans nom de pieu, les cercles des pieux aux
   nœuds deviennent des poteaux ronds. v04 : 0 → 132 poteaux, dont 59 aux
   positions de référence ; v14 : 0 → 158 (59) ; v13 : 52 → 164 (64) ;
   v05 : 27 → 73 (64). Les propositions de section rectangulaire retrouvent
   des valeurs du plan réel ; de nouveaux `column_diameter` faux apparaissent
   à 0,6 (63 — le diamètre des pieux —, 50, 40, 90,3012), absents du plan
   réel. Risque 3 de l'audit, déjà présent avant G2 sur v01 (103 poteaux en
   trop) : c'est l'objet de G3 (pieux par la géométrie) et G4 (poteaux).
3. **Cibles du § 5 non atteintes.** v14 : 66 axes (cible ≥ 66, atteinte),
   0 hors référence (atteinte), mais **59 étiquettes** au lieu de 61 : les
   deux axes à bulle isolée n'ont qu'une signature partielle, qui sans nom ne
   donne rien (J2). v04 : **59 axes** au lieu de ≥ 61 : sans aucun motif de
   ligne, B est impossible ; la cible contredisait la mesure de faisabilité du
   § 1 (bulles et famille seules : 59 / 71). v15 : 68 (cible ≥ 61, atteinte).
4. **Axes sans aucune signature** : les 3 axes en tirets sans bulle du plan
   réel ne tiennent qu'à leur nom de calque (N3) ; perdus dès que le calque est
   renommé, comme avant G2.
5. **Identifiants ordinaux** des axes sans étiquette : renumérotés quand un axe
   s'insère dans leur famille (variantes seulement ; 0 sur le plan réel). Règle
   de nommage inchangée (§ 2.9).

### 7.7 Coût

Plan réel, lecture et extraction complètes, trois mesures alternées sur la
même machine : `0.4.0` 17,49 / 18,28 / 18,57 s (moyenne 18,11 s), `0.5.0`
18,66 / 17,76 / 18,22 s (moyenne 18,21 s) — **+ 0,6 %**, dans l'écart entre
deux mesures. Les signatures seules : moins de 0,5 s.
