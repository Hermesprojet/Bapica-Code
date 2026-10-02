# Géométrie d'abord — G2 : les axes par leur signature

> **Statut : conception (avant le code).** Phase G2 de `GEOMETRIE_D_ABORD.md`
> (§ 11 : « classes de cercles, bulles par structure, axes A et B, zone
> structurelle »), selon les règles du § 3 (axes) et de l'échelle de preuves
> du § 1.4. Elle s'appuie sur l'information N1 lue par G1
> (`GEOMETRIE_D_ABORD_G1.md`). C'est la **première phase qui change des
> sorties** : chaque changement sera mesuré et cité (§ 7).

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

À écrire après l'implémentation.
