# Géométrie d'abord — G3 : les pieux par leur signature

> **Statut : réalisé (`473b6b6`), mesuré au § 8.** Phase G3 de `GEOMETRIE_D_ABORD.md`
> (§ 11 : « Pieux P » ; sortie mesurée : « v01/v04/v14 : 475 pieux, 0 faux
> poteau de pieu »), selon les règles du § 4 (pieux) et de l'échelle de
> preuves du § 1.4. Elle s'appuie sur l'information N1 lue par G1 (motif des
> types de ligne, remplissages) et sur les bulles et la grille de G2. Chaque
> changement de sortie est mesuré et cité (§ 8).

## 0. Ce que G3 fait, et ce qu'il garantit

**Objet.** Reconnaître les pieux d'un DXF par ce qu'ils SONT — des cercles
d'un **diamètre répété**, qui ne sont ni des bulles d'axes ni des poteaux
ronds — avant de regarder les noms, pour qu'un plan de fondations dont les
calques et les blocs sont renommés, dans une langue inconnue ou sans
convention, donne ses pieux ; et que les dessins de ces pieux ne deviennent
plus des « poteaux » aux nœuds de la grille.

**Garanties.**

| # | Garantie | Comment |
|---|---|---|
| K1 | **Tout pieu reconnu aujourd'hui par son nom le reste**, avec le même représentant, donc le même centre, le même diamètre, le même nœud, le même repère ; et le même identifiant tant qu'aucun pieu n'est ajouté (un pieu hors nœud est nommé par son rang, comme les axes sans étiquette de G2). | Les germes nommés sont regroupés d'abord, dans l'ordre d'aujourd'hui ; les germes géométriques ne font que les rejoindre ou former des pieux nouveaux (§ 2.7). Un repère reste au pieu le plus proche : il ne change que si un pieu nouveau est plus près de son texte. |
| K2 | Un pieu ajouté l'est par une **signature P complète**, jamais par la géométrie partielle seule. | § 2.2 à 2.6 ; une classe de moins de 10 cercles sans nom ne donne rien (les candidats sont en G6). |
| K3 | Une **feuille PDF ne change pas**. | La signature n'est évaluée que sur un DXF (§ 2.1). |
| K4 | Rien n'est inventé : un pieu est un cercle LU, son diamètre un rayon LU ; **rien n'est proposé** d'un pieu (fondations profondes hors du domaine validé, interdiction 6). | Interdictions 2 et 6, comme aujourd'hui. |
| K5 | Tout changement de sortie est cité : pieux ajoutés, retirés, confiances, preuves, poteaux, propositions, sur le plan réel, ses variantes et tout le corpus. | § 5 et § 8. |

**Hors de G3.** Les poteaux par la géométrie (C1, C2 : G4) — G3 ne fait
qu'écarter des poteaux les dessins des pieux qu'il reconnaît ; les voiles
(G5) ; les candidats, partitions apprises et `names_agree` (G6) ; les pieux
non circulaires (N3 seul, `GEOMETRIE_D_ABORD.md` § 4.4).

## 1. Point de départ mesuré (`0.5.0`, `52dc3af`)

| Variante du plan réel | Pieux | Poteaux (dont aux positions de référence) | Propositions (dont poteau) |
|---|---|---|---|
| origine | **477** (475 cercles : 455 × Ø 63, 20 × Ø 60 ; 2 hachures orphelines), tous par le **nom** de calque, 0,85 | 64 (64) | 335 (12) |
| v02 blocs neutres ; v05 espagnol ; v06 allemand ; v07 AIA ; v11 blocs explosés | 477 | 65 / 73 / 71 / 64 / 91 | 324 / 351 / 338 / 335 / 734 |
| v01 calques neutres | **0** | **168** (64) | 352 (16) |
| v04 aucune convention | **0** | **132** (59) | 409 (11) |
| v13 calques et blocs neutres, types de ligne gardés | **0** | **164** (64) | 352 (17) |
| v14 tout renommé | **0** | **158** (59) | 418 (15) |
| v15 tout sur le calque `0` | **0** | **168** (64) | 345 (16) |
| v08 / v09 `$INSUNITS` mm / m | 477 | 3 / 0 | 322 / 327 |

Dès que le nom du calque des pieux disparaît, les 477 pieux disparaissent, et
leurs dessins (cercles, remplissages, lentilles de la paroi de pieux sécants)
deviennent des poteaux aux nœuds : 104 poteaux de trop sur v01.

**Faisabilité, sans aucun nom** (mesures hors du dépôt, sur le plan réel et
sur v14) : les cercles se rangent en trois classes d'au moins 10 cercles
distincts (diamètre à 1 % près, doublons de même centre réunis) :

| Classe | Cercles | Distincts | Ce que c'est |
|---|---|---|---|
| Ø 63 | 910 | 455 | **les 455 pieux Ø 63** (dessinés deux fois : la feuille, en continu, et sa xréf, en tirets) |
| Ø 60 | 40 | 20 | **les 20 pieux Ø 60** |
| Ø 80 | 62 | 62 | les bulles d'axes (62 sur 62 sont des bulles de G2) |

Aucune autre classe d'au moins 10 cercles. **Les 475 cercles-pieux sont
retrouvés, et rien d'autre** ; les 2 pieux restants sont des hachures
orphelines, que seul leur nom désigne (§ 2.7).

**Le reste du corpus** (les 94 fichiers de G1) : aucune classe d'au moins
10 cercles distincts hors du plan réel et de ses variantes, **sauf sur les
deux feuilles PDF réelles** — 22 et 13 cercles de Ø 499 mm, qui ne sont pas
des pieux. D'où K3.

## 2. Les règles

Les seuils sont ceux de `GEOMETRIE_D_ABORD.md` § 4 ; les choix que G3 ajoute
sont signalés « **choix G3** », avec leur raison mesurée.

### 2.1 Les cercles (N1)

Les `CIRCLE` du dessin, de l'espace objet et des blocs insérés (un bloc
répété dont la définition est un cercle donne un cercle par insertion,
placé). Ni arcs, ni polylignes. **Choix G3** : un DXF seulement ; une feuille
PDF n'a ni motif de ligne, ni remplissage, ni blocs, et ses cercles répétés
(Ø 499 mm sur les deux feuilles réelles) ne sont pas des pieux (K3).

### 2.2 Les classes de diamètre (N2)

Les cercles sont rangés par diamètre croissant ; un cercle rejoint la classe
courante si son diamètre ne dépasse pas de **plus de 1 %** celui du plus
petit cercle de la classe (classe de largeur bornée, pas de chaîne). Dans une
classe, les **doublons** sont réunis : même centre à `max(5 tolérances,
5 % du diamètre)` près — la règle des doublons de `pieux.py`. Les **membres
distincts** sont les groupes ainsi formés.

### 2.3 La signature P (complète)

Une classe a la signature P si :

1. elle a **au moins 10 membres distincts** ;
2. son diamètre est **plausible** (§ 2.4) ;
3. ce n'est **pas une classe de bulles** (§ 2.5) ;
4. ce n'est **pas une classe de poteaux ronds** (§ 2.6).

Tous ses cercles sont alors des **germes géométriques**.

### 2.4 Diamètre plausible

* Unité connue : **250 à 2 000 mm**.
* Sinon, grille connue : au plus **0,3 entraxe médian**.
* **Choix G3** : ni unité ni grille — le diamètre n'est pas vérifiable, la
  signature n'est pas complète ; seuls les pieux nommés restent (N3).

Sur le plan réel, l'unité est établie par la présentation (cm) : Ø 63 cm =
630 mm, Ø 60 cm = 600 mm. Sur v08 (`$INSUNITS` = mm, à tort) et v09 (m, à
tort), les diamètres sont hors bornes : aucun germe géométrique, les pieux
nommés restent (§ 5).

### 2.5 Pas une classe de bulles

Un membre est une **bulle** s'il est une bulle d'une classe de bulles de G2
(la moitié au moins de ses membres au bout d'une droite de 20 rayons,
`GEOMETRIE_D_ABORD_G2.md` § 2.1), **ou** s'il a la forme d'une bulle (un seul
texte court dedans) et qu'**un axe de la grille finit sur lui** — dans la
fenêtre de G2 (centre sur le prolongement à 0,25 rayon près, entre un rayon
avant le bout et quatre au-delà), quelle que soit la règle qui a reconnu
l'axe. Une classe dont **la moitié au moins** des membres distincts sont des
bulles est une classe de bulles : aucun germe.

**Choix G3** (lecture de « aucun membre avec une étiquette dedans au bout
d'une droite ») : la position décide, par classe, comme le veut le § 4.4 du
plan — « la classe est décidée par la position, pas par l'étiquette » ; la
fixture de G2 le montre : treize pieux numérotés dans leur cercle, dont un
touche le bout d'un axe, restent une classe de pieux. Plan réel : la classe
Ø 80 (62 bulles) est écartée.

*(Corrigé à l'implémentation : la première rédaction ne comptait que les
bulles de G2. La suite de tests l'a montré : les douze bulles de Ø 800 mm du
plan fabriqué « axes courts à bulle » finissent des axes nommés plus courts
que 20 rayons ; G2 ne les valide pas, et elles devenaient des pieux en
conflit. Une bulle au bout d'un axe trouvé, même court, est une bulle.)*

### 2.6 Pas une classe de poteaux ronds

Un membre distinct ressemble à un poteau rond s'il est à la fois :

* **au nœud** : un nœud de la grille est dans le cercle (la règle des poteaux
  par la forme) ;
* **seul** : aucun autre membre distinct de la classe à moins d'un
  demi-entraxe médian — **choix G3**, lecture de « seul dans sa cellule de
  grille » : un nœud est le coin de quatre cellules ; « un par nœud » est ce
  qui compte ;
* **plein** : un contour rempli (hachure pleine ou à motif, `SOLID`) coïncide
  avec lui (même centre et même taille à 5 % près).

Si **au moins 80 %** des membres distincts ressemblent à des poteaux ronds,
la classe est **remise aux poteaux** : aucun germe géométrique ; ses cercles
suivent la règle des poteaux d'aujourd'hui (et ceux qui sont nommés pieux
restent des pieux, N3). Sans grille, aucun membre n'est au nœud : la classe
n'est jamais remise aux poteaux.

**Choix G3 : la règle est de classe, pas de membre**, comme le § 4.2 l'écrit.
Mesuré sur le plan réel : la classe Ø 60 compte **1 pieu sur 20** plein et
seul à son nœud, la classe Ø 63 **0 sur 455** ; une règle par membre aurait
retiré ce pieu et en aurait fait un faux poteau.

### 2.7 Les germes, le dessin du pieu, les hachures orphelines

Les étapes 2 à 4 de `pieux.py`, déjà géométriques, sont inchangées ; seuls
les germes changent :

1. **Germes nommés d'abord** — les cercles et contours fermés (hors
   hachures) de rôle `pieu`, dans l'ordre d'aujourd'hui (le cercle avant le
   contour, le plus grand d'abord) : les groupes d'aujourd'hui se forment à
   l'identique (K1).
2. **Germes géométriques ensuite** — les cercles des classes P qui ne sont
   pas déjà germes nommés, dans le même ordre : chacun rejoint le groupe d'un
   pieu de même centre et même taille (5 %), ou en forme un nouveau.
3. **Dessin du pieu** (inchangé) : un contour fermé de rôle `inconnu`,
   `hachure` ou `pieu` qui coïncide avec un pieu, ou dont la moitié au moins
   des sommets sont sur son bord et le centre dedans (remplissages,
   lentilles).
4. **Hachures orphelines** (inchangé) : celles de rôle `pieu` seulement — les
   2 pieux du plan réel qui ne sont pas des cercles ne sont trouvés que par
   leur nom.

Un germe nommé hors de toute classe P reste un pieu **par le nom** (N3) :
petits plans, pieux isolés, pieux carrés.

### 2.8 L'échelle de preuves, pour les pieux

| Cas | Décision | `classified_by` | `matched_name` | Confiance |
|---|---|---|---|---|
| 1. Le groupe contient un germe géométrique, et un de ses germes est nommé `pieu` | pieu | `geometrie` | le nom concordant (celui du représentant s'il est nommé) | **0,90** |
| 1'. Germe géométrique, aucun nom de rôle (`inconnu`, `hachure`) | pieu | `geometrie` | — | **0,85** |
| 2 et 4. Germe nommé seulement (hors de toute classe P), ou hachure orpheline nommée | pieu, comme aujourd'hui | la règle du nom (`calque`, `bloc`) | le nom | 0,85 (inchangée) |
| 5. Un germe géométrique porte le nom d'un **autre rôle** (`poteau`, `fondation`, `axe`, `cote`, `voile`…) | pieu ; **conflit dit** dans `unresolved`, avec la classe et le nom | `geometrie` | — | **≤ 0,4** |
| 6. Classe de moins de 10 cercles, sans nom | rien en G3 (candidats : G6) | — | — | — |

Le cas 5 suit le § 1.4 du plan : un nom ne contredit jamais une signature
complète ; il fait baisser la confiance et le désaccord est dit. Un germe
géométrique en conflit **n'est pas un poteau**, même sur un calque de poteaux.
Le nom ne fait donc que **compléter** (cas 2 et 4 : des pieux que la géométrie
ne voit pas) ou **confirmer** (cas 1 : + 0,05).

### 2.9 Les critères cités (`evidence.signature`)

* **`classe_de_diametre`** : le pieu contient un germe d'une classe P — c'est
  la signature complète (classe, diamètre plausible, ni bulles ni poteaux
  ronds).
* Corroborations (N1), citées quand elles sont vues, jamais décisives (§ 4.1
  du plan) : **`motif_tirets`** — un de ses cercles est tracé en tirets (le
  motif, G1, pas le nom : « sous le plan de coupe ») ; **`rempli`** — un
  contour rempli fait partie de son dessin.
* Comme en G2, un pieu décidé par le nom cite les corroborations vues.
* **Choix G3** : la corroboration « massif contenant » du § 4.1 n'est pas
  calculée — le plan ne la définit pas, elle ne décide rien, et les massifs
  sont l'objet des contenants de G4.

### 2.10 Les repères

**Choix G3 : la règle d'aujourd'hui est gardée** — un texte de rôle `pieu`,
ou qui nomme un pieu (« PIEU 12 »), rattaché au pieu le plus proche. Le § 4.2
(étape 5) proposait, pour un pieu géométrique, « le texte court le plus
proche (≤ 6 hauteurs), seulement s'il n'est le repère d'aucun autre
élément ». **Mesuré sur le plan réel** : 30 des 477 pieux ont un texte court à
moins de 6 hauteurs — « VP1 », « VP2 », « VP3 » (21), « S44 », « S49 » (8),
et une étiquette d'axe (1) : les repères de **groupes** (la paroi de pieux, des
massifs), pas d'un pieu ; aujourd'hui, aucun de ces pieux n'en porte. La règle
du § 4.2 aurait donné à 29 pieux reconnus un repère de groupe (contre K1). Un
repère de pieu par la seule proximité demande de savoir à qui appartient
chaque texte (après les repères des poteaux, voiles et poutres) : à concevoir
avec G6.

### 2.11 Les poteaux

Un germe de pieu — nommé ou géométrique — n'est **jamais un poteau** : il
est écarté avec la raison `pieu` (aujourd'hui : `pieu` pour un germe nommé),
et le dessin qu'il absorbe avec la raison `dessin_de_pieu`, comme
aujourd'hui. Les autres règles des poteaux ne changent pas (G4). Un contour
plus petit posé DANS un pieu, sans sommet sur son bord, n'est pas son dessin
(un poteau posé sur un pieu) : il reste soumis aux règles des poteaux.

### 2.12 Ce qui ne change pas

Le vocabulaire des noms (`classification.py`), les étapes 3 et 4 du dessin
du pieu, les identifiants (`pile:<nœud>`, `pile:<rang>`), les repères, les
axes, les voiles, les poutres, les cotes ; **aucune proposition** n'est tirée
d'un pieu ; une feuille PDF.

## 3. Sorties et contrat

* `evidence.classified_by = "geometrie"` existe depuis G2 : aucune valeur
  nouvelle, **aucun changement de schéma** ; les descriptions
  (`classified_by`, `signature`) citent les critères des pieux. Contrat
  régénéré (`packages/contracts`), étiquette de l'écran
  (`web/lib/documents.ts`) étendue aux pieux.
* `evidence.signature` sur un pieu : `classe_de_diametre`, `motif_tirets`,
  `rempli`.
* `unresolved` : un conflit nom / signature (cas 5) est une entrée
  `pile:<id>`, avec le diamètre de la classe et le nom.
* `report.piles` gagne `by_rule` (pieux par `classified_by`) et
  `diameter_classes` : chaque classe d'au moins 10 cercles distincts, avec
  son diamètre, ses cercles, ses membres distincts et son **verdict** —
  `pieux`, `bulles`, `poteaux_ronds`, `diametre_hors_bornes`,
  `diametre_non_verifiable` — pour que chaque refus soit lisible.
* **Version `0.6.0`** : confiances et poteaux changent.

## 4. Tests

Fixtures nouvelles (`fabrique_geometrie.dxf_pieux_signatures`), § 4.5 du
plan : une grille à bulles A–D × 1–3 en cm (`$INSUNITS` = cm), des massifs à
deux pieux Ø 60 aux nœuds (pieux hors nœud), une paroi de pieux sécants Ø 60
remplis, des poteaux pleins aux nœuds.

* **sans aucun nom** (tout sur des calques neutres) : les pieux sont trouvés,
  `geometrie`, 0,85, `classe_de_diametre` ; aucun poteau tiré d'un pieu ;
* **nommés** (`PIEUX`) : mêmes pieux (identifiants, centres, diamètres,
  nœuds), 0,90, le nom cité ;
* **poteaux ronds** pleins, seuls aux nœuds, d'un même diamètre : classe
  remise aux poteaux (`poteaux_ronds`), les poteaux restent ;
* poteaux ronds d'un diamètre et pieux d'un autre : chacun le sien ;
* **pieux numérotés** dans leur cercle, l'un au bout d'un axe : des pieux ;
* **regards** ronds répétés de Ø 15 cm : `diametre_hors_bornes`, aucun pieu ;
* **6 pieux** seulement : aucun sans nom ; par le nom, 6 pieux (`calque`,
  0,85, sans `classe_de_diametre`) ;
* une classe de pieux sur un calque **`POTEAUX`** : pieux à 0,4, conflit dit,
  aucun poteau ;
* ni unité ni grille : `diametre_non_verifiable`, aucun pieu géométrique ;
* **K1** : sur chaque plan de pieux existant, sans puis avec la signature P :
  mêmes pieux, identifiants, centres, diamètres, nœuds, repères ;
* **K3** : la feuille PDF fabriquée ne change pas.

Les tests existants qui fixent une confiance ou une règle de pieu sont relus
un par un ; tout changement non voulu par § 2.8 est un défaut.

## 5. Validation

* Suites d'extraction et d'API, harnais des documents, `export_contracts.py
  --check`, depuis l'arbre gelé.
* **Balayage complet** des 94 fichiers : avant (`0.5.0`) / après ; chaque
  fichier changé est listé et chaque changement classé (pieu ajouté, retiré,
  déplacé, confiance, règle, poteau, proposition).
* **Plan réel et ses 17 variantes**, dont toutes les variantes de l'audit :
  calques renommés (v01, v05, v06, v07, v13, v15), blocs renommés (v02, v11),
  tous les noms retirés (v04, v14). Par variante : précision et rappel des
  pieux, effet sur les poteaux (nombre, aux positions de référence, autres),
  effet sur les propositions (catégorie, valeur, confiance).

**Précision et rappel des pieux.** Référence : les 477 pieux de la sortie
`0.5.0` du plan réel. Un pieu d'une sortie est **apparié** à un pieu de
référence si leurs centres sont à 5 % du diamètre près et leurs diamètres à
5 % près (pour v10, la référence est tournée de 30° autour de l'origine,
comme la variante). Rappel = pieux de référence appariés / 477 ; précision =
pieux appariés / pieux de la sortie.

## 6. Attendu (prototype de mesure, hors dépôt)

Un prototype qui donne le rôle de pieu aux cercles des classes Ø 60 et Ø 63
(sans le reste de G3) mesure :

| Variante | Pieux | Poteaux (aux positions de référence + autres) |
|---|---|---|
| plan réel | 477 (inchangés) | 64 (64 + 0) |
| v01 | 0 → **475** | 168 → **71** (64 + 7) |
| v04 | 0 → **475** | 132 → **62** (59 + 3) |
| v13 | 0 → **475** | 164 → **73** (64 + 9) |
| v14 | 0 → **475** | 158 → **68** (59 + 9) |
| v15 | 0 → **475** | 168 → **71** (64 + 7) |

Rappel attendu sur les variantes sans nom : **475 / 477 = 0,996**,
précision 1,000. Les poteaux en trop qui restent ne sont **pas des dessins de
pieu** (relevé sur v01 et v14) : 7 cercles d'annotation Ø 50 et Ø 40 posés
sur des pieux, aux nœuds (un calque que le plan nommé classe `cadre` ; sans
nom, rien ne les distingue d'un poteau posé sur un pieu) ; sur v14 en plus,
un cercle d'un calque d'axes et un contour d'un calque de cotes — l'objet des
exclusions de G4.

## 7. Risques connus

* **Pieux uniques pleins à chaque nœud** (un pieu par poteau, dessiné
  plein) : la classe ressemble à des poteaux ronds et leur est remise ; sans
  nom, ces pieux sont alors des poteaux.
* **Poteaux ronds non pleins** aux nœuds, d'un même diamètre plausible : la
  classe n'est pas remise aux poteaux (le critère « plein » manque) ; sans nom,
  ce sont des pieux ; nommés poteaux, des pieux à 0,4 avec le conflit dit.
* **Pieu-colonne** (un poteau rond nommé posé sur un pieu de même diamètre,
  même centre) : les deux cercles font un seul pieu, en conflit (0,4) ;
  aujourd'hui, un pieu et un poteau. Aucun fichier du corpus n'a ce cas.
* **Regards, avaloirs, réservations rondes** de Ø ≥ 250 mm répétés dix fois :
  des pieux (à mesurer en campagne).
* **Massifs ronds** répétés (Ø 1,2 m…) : une classe P ; nommés massifs, un
  conflit dit.
* **Unité fausse** (v08, v09) : diamètres hors bornes, aucun germe
  géométrique ; seuls les pieux nommés restent.

## 8. Résultats

Mesuré sur le commit du code `473b6b6` (version `0.6.0`), contre les sorties
de `0.5.0` (`52dc3af`, celles de la campagne G2). L'arbre de travail est resté
gelé pendant toutes les exécutions (empreinte identique avant et après) ; les
sorties du commit sont celles qui ont été analysées : balayage refait sur le
commit, **94 / 94 identiques octet pour octet** ; variantes refaites,
**17 / 17 identiques** (hors durée mesurée).

**En bref.** Sur le plan réel, rien n'est ajouté ni retiré : 477 pieux,
précision et rappel 1,000, les mêmes identifiants, centres, diamètres, nœuds
et repères ; 475 sont désormais décidés par leur signature (0,85 → 0,90, le
nom confirme). Quand **tous les noms disparaissent**, les pieux reviennent :
**0 → 475**, précision **1,000**, rappel **0,996** ; et les dessins de pieux ne
sont plus des poteaux : **168 → 66 poteaux** (v01), **132 → 59** (v04, tous aux
positions de référence). Aucun pieu n'est retiré nulle part ; aucune
proposition ne change sur le plan réel ni sur ses variantes nommées.

### 8.1 Suites, contrat, harnais, balayage

| Validation | Résultat |
|---|---|
| Suite d'extraction | **465 tests, 0 échec** (446 en G2 + 19 nouveaux) |
| Suite de l'API | **599 tests, 0 échec**, 340 ignorés — les mêmes 599 / 340 qu'en G1 et G2 |
| `export_contracts.py --check` | 0 : le contrat commité (descriptions de `classified_by` et `signature`) est celui que le schéma régénère |
| Harnais des documents (`db/test/documents_extractions.sh`, base jetable) | 0 : 34 tests réussis, comme en G1 et G2 |
| Balayage des 94 fichiers | 94 / 94 analysés sans exception ; **73 identiques à `0.5.0`** hors numéro de version, **21 changés** (§ 8.6) |
| Variantes du plan réel (17) | 17 / 17 analysées sans exception |
| `VERSION_EXTRACTEUR` | `0.6.0` |

Tests : `test_geometrie_pieux_signatures.py` (nouveau, 19 tests : chaque
fixture du § 4, et K1 sur six plans aux pieux nommés — sans la signature P
puis avec : mêmes pieux, identifiants, centres, diamètres, nœuds, repères,
mêmes poteaux). **Aucun test existant n'a été modifié** ; la suite existante a
trouvé le défaut de la première lecture du § 2.5 (bulles d'axes courts), corrigé
avant le commit et dit dans ce document.

### 8.2 Plan réel

| | `0.5.0` | `0.6.0` |
|---|---|---|
| Pieux | 477, tous par le nom de calque (0,85) | **477 : 0 ajouté, 0 retiré** ; 475 `geometrie` à **0,90** (le nom cité confirme), 2 hachures orphelines par le nom (0,85) |
| Identifiants, centres, diamètres, nœuds, repères | | **identiques** (477 sur 477) |
| Critères cités | | `classe_de_diametre` et `motif_tirets` sur les 475 (la copie de xréf est en tirets), `rempli` sur 297 ; `rempli` sur les 2 hachures |
| Classes de diamètre | | Ø 60 (40 cercles, 20 distincts) : pieux ; Ø 63 (910, 455) : pieux ; Ø 80 (62, 62) : **bulles** |
| Poteaux | 64 | 64, mêmes identifiants |
| Propositions | 335 | **335, identiques** (catégories, valeurs, repères, confiances) : un pieu ne propose rien, et aucun poteau ne change |
| `unresolved` | 0 | 0 : aucun conflit |

**Précision 477 / 477 = 1,000 ; rappel 477 / 477 = 1,000.** Par la seule
géométrie : **475 / 477** (les 2 hachures orphelines ne sont trouvées que par
leur nom).

### 8.3 Variantes : calques renommés, blocs renommés, tous les noms retirés

Précision et rappel des pieux contre les 477 pieux de référence (§ 5) ; v10
contre la référence tournée de 30°.

| Variante | Pieux | Précision | Rappel | Par la géométrie | Poteaux (aux positions de référence + autres) | Propositions poteau / poutre / toutes |
|---|---|---|---|---|---|---|
| plan réel, v00 | 477 → 477 | 1,000 → 1,000 | 1,000 → 1,000 | 475 | 64 (64 + 0) → 64 (64 + 0) | 12 / 0 / 335, inchangées |
| **Tous les noms retirés** | | | | | | |
| v04 aucune convention (calques, blocs neutres, tout en continu) | **0 → 475** | — → **1,000** | 0 → **0,996** | 475 | 132 (59 + 73) → **59 (59 + 0)** | 11 → 10 / **69 → 0** / 409 → 339 |
| v14 tout renommé (calques, blocs, types de ligne) | **0 → 475** | — → **1,000** | 0 → **0,996** | 475 | 158 (59 + 99) → **63 (59 + 4)** | 15 → 13 / **69 → 0** / 418 → 347 |
| **Calques renommés** | | | | | | |
| v01 calques neutres | **0 → 475** | — → 1,000 | 0 → 0,996 | 475 | 168 (64 + 104) → **66 (64 + 2)** | 16 → 14 / 0 / 352 → 350 |
| v13 calques et blocs neutres, types de ligne gardés | **0 → 475** | — → 1,000 | 0 → 0,996 | 475 | 164 (64 + 100) → **68 (64 + 4)** | 17 → 15 / 0 / 352 → 350 |
| v15 tout sur le calque `0` | **0 → 475** | — → 1,000 | 0 → 0,996 | 475 | 168 (64 + 104) → **66 (64 + 2)** | 16 → 14 / 0 / 345 → 343 |
| v05 espagnol / v06 allemand / v07 AIA | 477 → 477 | 1,000 | 1,000 | 475 | 73 / 71 / 64, inchangés | inchangées |
| **Blocs renommés** | | | | | | |
| v02 blocs neutres | 477 → 477 | 1,000 | 1,000 | 475 | 65, inchangés | inchangées |
| v11 blocs explosés | 477 → 477 | 1,000 | 1,000 | 475 | 91, inchangés | inchangées |
| **Autres** | | | | | | |
| v03 sans types de ligne ; v10 rotation de 30° ; v12 minuscules | 477 → 477 | 1,000 | 1,000 | 475 | inchangés | inchangées |
| v08 / v09 `$INSUNITS` mm / m (faux) | 477 → 477 | 1,000 | 1,000 | **0** (diamètres hors bornes : Ø 63 « mm », Ø 63 « m ») | inchangés | inchangées |

**Sur toutes les variantes où le nom des pieux reste lisible** (v02, v03,
v05–v07, v10–v12), les 477 pieux sont identiques un à un (identifiant, centre,
diamètre, nœud, repère) ; 475 passent à `geometrie` (0,85 → 0,90), les 2
hachures orphelines restent au nom ; poteaux et propositions inchangés.

**Calques renommés, tous les noms retirés.** Les 475 pieux dessinés par un
cercle reviennent sur chacune des cinq variantes, **sans aucun pieu hors
référence**, à 0,85 (aucun nom ne confirme). Les 2 pieux manquants sont les
hachures orphelines, que seul leur nom désigne.

**Blocs renommés.** Les pieux du plan réel ne sont pas des blocs : v02 et v11
ne changent que par la confiance.

### 8.4 L'effet sur les poteaux

**Aucun poteau n'est tiré du dessin d'un pieu** sur les variantes sans nom
(cible du § 11 du plan) : sur v01, les **102** faux poteaux qui étaient des
dessins de pieux — 58 remplissages et lentilles, 44 cercles Ø 63 — sont
écartés (raisons `pieu` 54, `dessin_de_pieu` 59 au compte rendu). Restent, hors
référence :

| Variante | Autres poteaux | Ce que c'est (rôle du calque dans le plan nommé) |
|---|---|---|
| v01, v15 | 2 | 2 cercles d'annotation Ø 50 posés sur des pieux (`cadre`) |
| v13, v14 | 4 | les mêmes 2, un cercle Ø 90,3 d'un calque d'axes (`axe`), un contour d'un calque sans rôle |
| v04 | 0 | — |

Ce ne sont pas des dessins de pieu (un contour plus petit posé dans un pieu,
sans sommet sur son bord : § 2.11) ; ils relèvent des exclusions de G4.
v05 et v06, dont les pieux sont nommés, gardent leurs 9 et 7 poteaux en trop
(7 cercles d'annotation sur des pieux ; sur v05, en plus, le cercle Ø 90,3 et
le contour) : G3 ne les touche pas.

Le prototype du § 6 attendait 71, 62, 73, 68, 71 poteaux ; la mesure donne
66, 59, 68, 63, 66 : le prototype donnait aux pieux le rôle de pieu, ce qui
désarmait la règle de l'enceinte des poteaux (un contour vide dans un contour
vide de rôle inconnu) ; sans nom, les pieux sont de rôle inconnu, et cette
règle — inchangée, déjà active avant G3 (5 rejets sur v01 avant comme après) —
écarte la plupart des cercles d'annotation posés dans un pieu.

### 8.5 L'effet sur les propositions

* **Plan réel et variantes nommées : aucune proposition ne change** (valeurs
  et confiances) — un pieu ne propose rien.
* **v04, v14 : 69 propositions de poutre disparaissent** (24 `beam_width`,
  21 `beam_span`, 21 `beam_clear_span`, 3 `cantilever_length`) : des « poutres »
  portées par des dessins de pieux pris pour des poteaux ; le plan nommé n'en a
  aucune.
* **`column_diameter` 63** (le diamètre des pieux) disparaît partout : 3
  propositions sur v01, v13, v14, v15, 1 sur v04.
* **Une proposition `column_diameter` 50 apparaît** sur v01, v13, v14, v15 :
  le même cercle d'annotation qu'avant, qui reçoit désormais le repère « VP2 »
  qu'un cercle de pieu pris pour un poteau prenait ; elle est fausse, comme
  avant, et relève de G4.

### 8.6 Balayage du corpus (94 fichiers)

* **73 inchangés** hors numéro de version : les 36 DXF d'exemple, les 9
  feuilles PDF (K3), les sondes, le plan synthétique des cotes, les plans
  fabriqués sans pieu, les 5 DXF riches en N1.
* **18 changés sans pieu ajouté ni retiré**, mêmes poteaux, **propositions
  identiques** : les 5 plans fabriqués aux pieux nommés (1 pieu, et 11 sur les
  quatre plans de fondations ; hors de toute classe P : seuls les critères
  cités et `report.piles.by_rule` s'ajoutent), le plan réel et sa copie, et ses variantes v00, v02, v03, v05 à
  v12 (475 pieux passent à `geometrie`, 0,90 ; v08 et v09 restent au nom).
* **3 changés avec des pieux ajoutés** : v01, v04, v13 (0 → 475), et leurs
  poteaux, poutres et propositions (§ 8.4, 8.5).

### 8.7 Ce que G3 ne résout pas

1. **Les pieux qui ne sont pas des cercles** (les 2 hachures orphelines du
   plan réel) ne sont trouvés que par leur nom : rappel 475 / 477 sans noms.
2. **Les cercles d'annotation posés sur des pieux** restent des poteaux sur
   les variantes sans nom (2 ; 9 sur v05, dont les pieux sont nommés) : G4.
3. **Une unité fausse** désarme la signature (v08, v09) : les diamètres sortent
   des bornes ; seuls les pieux nommés restent. Le recoupement de `$INSUNITS`
   (D1) le corrigerait.
4. **Les repères de pieu** ne sont lus que par un texte qui nomme un pieu
   (« PIEU 12 ») ou un calque de pieux (§ 2.10) ; sans nom de calque, un numéro
   seul n'est pas rattaché.
5. **Les risques du § 7**, non rencontrés dans le corpus : pieux uniques pleins
   à chaque nœud (remis aux poteaux), poteaux ronds non pleins d'un diamètre
   répété (pris pour des pieux), pieu-colonne nommé (un pieu en conflit),
   regards et massifs ronds répétés de diamètre plausible.
6. **Les feuilles PDF** n'ont pas de signature P (K3).

### 8.8 Coût

Plan réel, lecture et extraction complètes, cinq mesures alternées sur la
même machine : `0.5.0` 18,17 / 18,41 / 18,81 / 18,78 / 20,42 s (moyenne
18,92 s), `0.6.0` 18,26 / 20,06 / 20,54 / 19,26 / 19,56 s (moyenne 19,54 s) —
**+ 3,3 %** en moyenne, + 4,2 % en médiane, dans la cible du plan (moins de
10 %). La signature P seule : 0,1 à 0,2 s par construction (le plan réel est
construit deux fois, la seconde avec l'unité de sa présentation), bulles de G2
comprises.
