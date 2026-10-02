# Géométrie d'abord — G4 : les poteaux par leur signature

> **Statut : conception (avant le code).** Phase G4 de `GEOMETRIE_D_ABORD.md`
> (§ 11 : « Poteaux C1 (exclusions géométriques), C2 » ; sortie mesurée :
> « v01/v04/v14 : 64 ± 2 »), selon les règles du § 5 (poteaux) et de l'échelle
> de preuves du § 1.4. Elle s'appuie sur G1 (remplissages, définitions de
> blocs), G2 (grille, bulles, zone structurelle) et G3 (pieux). Les mesures
> citées ont été faites hors du dépôt, sur `0.6.0` (`60f4b4a`) et sur un
> prototype de mesure (§ 5) ; aucune ligne du produit n'est écrite avant la
> validation de ce document.

## 0. Ce que G4 fait, et ce qu'il garantit

**Objet.** Reconnaître un poteau par ce qu'il EST — une **section** (rectangle,
cercle, polygone inscrit) **coupée** (remplie : N1), de taille plausible,
posée **sur un nœud** de la grille, dans la **zone structurelle**, qui n'est
ni un pieu, ni un contenant, ni une trémie, ni un bout de voile — avant de
regarder les noms ; que les cercles d'annotation, les dessins de pieux, les
cartouches, les symboles et la géométrie décorative ne soient plus des
poteaux ; et qu'aucune proposition de section ne soit tirée d'eux.

**Garanties.**

| # | Garantie | Comment |
|---|---|---|
| L1 | **Tout vrai poteau trouvé aujourd'hui sur le plan réel le reste** : les 63 poteaux préfabriqués, avec le même identifiant, le même centre, la même section, le même angle, le même nœud, le même repère ; les valeurs de leurs propositions sont inchangées. | Les 63 ont la signature C1 complète (§ 5, mesuré). |
| L2 | Un poteau est décidé par une **signature complète** (C1, ou C2 sans grille), ou par une signature partielle **complétée** (nom, bloc répété, repère de poteau) ; la signature partielle seule ne donne rien. | § 3 ; les candidats exportés sont en G6. |
| L3 | Un nom ne fait que **compléter** (un poteau que la géométrie ne décide pas seule) ou **confirmer** (+ 0,05) ; un nom d'un autre rôle sur une signature complète est un **conflit dit** (0,4), jugé sur le contour de la section, pas sur son remplissage. | § 3.6 ; § 1.4 du plan, cas 5. |
| L4 | **Sur le plan réel nommé, aucune valeur proposée ne change**, sauf le retrait de la seule proposition fausse (`column_diameter` 28,3945, le faux poteau connu). Les confiances qui changent sont listées (§ 5). | Mesuré (§ 5). |
| L5 | Rien n'est inventé : une section est un contour LU, ses côtés et son diamètre sont lus ; aucun axe n'est inventé (C2 donne des poteaux, pas des axes). | Interdictions 2 et 5. |
| L6 | Tout changement de sortie est cité : poteaux ajoutés, retirés, confiances, propositions, sur le plan réel, ses variantes et tout le corpus. | § 10. |

**Hors de G4.** Les voiles (V1, V2 : G5) — G4 n'en tire qu'une exclusion
(bout de voile) ; les candidats exportés, les partitions apprises et
`names_agree` (G6) ; le recoupement de `$INSUNITS` (D1) ; les poteaux composés
(en L, en croix) et non sectionnels (hors domaine, § 10 du plan).

## 1. Point de départ mesuré (`0.6.0`)

### 1.1 Le plan réel

**64 poteaux, tous par la forme, aucun par un nom.** Le calque des poteaux
préfabriqués ne contient pas de mot de rôle « poteau » : la règle actuelle les
trouve comme formes au nœud, sur un calque qui ne dit rien.

| Poteaux | Nombre | Règle actuelle | Nature |
|---|---|---|---|
| Rectangles **hachurés**, sur le calque des préfabriqués coupés, aux nœuds | **63** | `forme`, 0,65 | **les vrais poteaux** : 50 × 50 (30, dont 29 tournés), 30 × 30 (18), 30 × 60 (8, dans les deux sens), 30 × 50 (2), 30 × 90 (2), 40 × 40, 30 × 65, 35 × 50 |
| Cercle Ø 28,39, **vide**, calque d'annotation, à un nœud | 1 | `forme`, 0,6 | **le faux poteau connu** (`GEOMETRIE_PIEUX_GAINES_UNITE.md` § 10) ; sa proposition `column_diameter` 28,3945 est fausse |

Chaque vrai poteau est dessiné quatre fois : contour et hachure, sur la feuille
et dans la xréf. Le même calque porte **16 autres sections hachurées** que la
règle ne trouve pas : 2 à un nœud mais d'élancement 4,33 (130 × 30 : des
voiles courts ?) et 14 hors de tout nœud. Personne ne les a vérifiées ; elles ne
sont pas dans la référence (§ 1.4) et G4 ne les ajoute pas (§ 3.3).

**Ce qui fait la précision aujourd'hui, ce sont les exclusions** : sur le plan
réel, 107 pieux, 59 dessins de pieux, 13 socles (contenants) et 1 chevron de
gaine (non compact) sont écartés aux nœuds ; le § 5.1 du plan comptait
303 contours hachurés compacts de 10 à 200 cm aux nœuds.

### 1.2 Les réponses demandées

| Question | Mesure |
|---|---|
| Poteaux trouvés **seulement par un nom** | **0** sur le plan réel et 15 de ses 16 variantes : aucun poteau n'y est nommé. **v11** (blocs explosés) : 85 poteaux reconnus par le nom d'un bloc imbriqué ; 62 ont aussi la signature C1, **23 ne tiennent qu'au nom** (2 vrais, 21 faux). Corpus fabriqué : `charpente_mm`, 8 nommés, qui ont aussi C1 ; `grande_grille`, **400 qui ne tiennent qu'au nom** (sections vides) |
| Poteaux trouvés **parce que des axes existent** | **64 / 64** (forme au nœud) ; 5 d'entre eux (H/P, I/P, J/P, K/P, N/P) sont sur l'axe oblique isolé « P », que G2 ne trouve pas sans nom : perdus sur v04 et v14 |
| **Faux poteaux après G3** | le cercle Ø 28 partout ; v01, v15 : + 2 cercles d'annotation Ø 50 ; v13, v14 : + 2 Ø 50, 1 cercle Ø 90,3 d'un calque d'axes, 1 polygone ; v05 : + 7 cercles Ø 50 et Ø 40, le Ø 90,3, 1 polygone ; v06 : + 7 ; v02 : + 1 polygone ; v08 (unité fausse) : 3 ; v11 (blocs explosés) : + 27 — 24 rectangles et 2 cercles polygonaux remplis aux nœuds de faux axes, 1 triangle |
| **Cercles d'annotation** encore poteaux | le Ø 28 (toutes les variantes), Ø 50 et Ø 40 posés sur des pieux (v01, v05, v06, v13, v14, v15) — **tous vides** |
| **Propositions fausses dues aux poteaux** | `column_diameter` 28,3945 partout ; 50 (v01, v05, v06, v13, v14, v15) ; 40 (v05, v06) ; 90,3012 (v05, v13, v14) ; v08 : 235 × 310 ; v11 : six valeurs (100, 37,09, 45, 70, 41,15, 90) ; propositions manquantes 40 × 40 sur v04 et v14 (le poteau de l'axe P) |

**Hormis v08 (unité fausse) et v11 (blocs explosés), tous les faux poteaux
restants sont VIDES**, sur le plan réel comme sur ses variantes ; tous les
vrais sont remplis. C'est la clef de G4 (§ 3.2, critère C1.2).

### 1.3 Le corpus

| Fichiers | Poteaux `0.6.0` | Ce qu'ils sont |
|---|---|---|
| 56 fichiers | 0 | — |
| Plans fabriqués (fondations, s101, N1) | 4 à 9 par plan, remplis, `forme` 0,65 | vrais (tests) |
| Plans de fondations 1/50 et sans présentation | + 1 rectangle **vide** 120 × 100 | la **cabine d'ascenseur** dans sa cage : faux (sans unité, la cage n'est pas une enceinte plausible) |
| `charpente_mm` | 8, par **bloc** nommé, remplis | vrais |
| `grande_grille` | **400**, par **bloc** nommé, **vides** | vrais (nommés) |
| Feuilles PDF fabriquées | 5 à 6, remplis | vrais |
| Feuille PDF réelle A | 1 polygone rempli | la **barre rouge** de 1,20 × 0,11 m (élancement 10,6, mesuré 3,3 sur sa boîte alignée) : faux |
| Feuille PDF réelle B | 2 polygones (contour vide sur une coupe de béton) | non vérifiés (`GEOMETRIE_PIEUX_GAINES_UNITE.md` § 10) |
| v07 (noms AIA) | 64, tous **vides** | les hachures des poteaux sont sur des calques `…-ANNO-PATT…`, que le vocabulaire range en « texte » : écartées par leur nom, elles ne remplissent plus le contour |

### 1.4 La référence des précisions et rappels

**R63** : les 63 poteaux préfabriqués hachurés du plan réel (sortie `0.6.0`).
Le cercle Ø 28 n'est pas un poteau. Un poteau d'une sortie est **apparié** s'il
est à 5 unités (cm) d'un poteau de R63 (v10 : R63 tourné de 30°). Précision =
appariés / poteaux de la sortie ; rappel = appariés / 63.

## 2. Ce qu'il faut distinguer, et ce qui le distingue

| Confusion | Exemple mesuré | Ce qui l'écarte en G4 (niveau) |
|---|---|---|
| **Pieux** | 102 dessins de pieux sur v01 avant G3 ; 125 hachures de pieux sur un calque rangé « texte » (v07) | G3 : germe ou dessin de pieu (N2, fait) ; et tout contour de même centre et de même taille qu'un pieu, quel que soit son calque (N2, C1.6) |
| **Cercles d'annotation** | Ø 28, Ø 50, Ø 40 posés sur des pieux | **vides** : pas coupés (N1, C1.2) |
| **Massifs, socles** | 13 socles 170 × 170 autour des poteaux | **contenant** (N2, C1.7) ; plus de 2 m : hors bornes (C1.3) |
| **Cartouche, légendes, détails** | échantillons de traits d'une légende | **hors de la zone structurelle** (N2, C1.5) ; sans nœud (C1.4) |
| **Bouts de voile** | aucun dans le corpus (mesuré) | **dans le prolongement d'une plage remplie allongée de même épaisseur** (N2, C1.10) |
| **Symboles d'architecte** | chevron de gaine (compacité 0,28), cabine d'ascenseur, triangle de repère de niveau, barre rouge | **section** : rectangle, cercle, polygone inscrit (N2, C1.1) ; vide (C1.2) ; élancement (C1.3) ; enceinte, ouverture nommée (C1.8–C1.9) |
| **Géométrie décorative répétée** | carreaux, repères de nœud, hachures découpées | **au nœud** (C1.4), taille plausible (C1.3) ; sans grille : C2 exige un entraxe implicite d'au moins 4 sections (§ 3.3) |
| **Trémies, gaines** | trémie barrée, « GAINE » | barrée (C1.8), nommée par son texte (C1.9) |

## 3. La signature

### 3.1 N1 — l'information DXF standard

* **Coupé = rempli** : le contour est une `HATCH` (pleine ou à motif) ou un
  `SOLID`, **ou un contour rempli de même centre et de même taille (5 %) le
  double — quel que soit son calque**. Le remplissage est une preuve N1 : le
  nom de son calque n'entre pas en compte (v07 : 63 / 63 retrouvés).
* **Bloc répété** (complète une section vide, § 3.4) : une définition insérée
  au moins **3 fois à l'échelle 1** (|x| = |y| = 1), qui ne contient **qu'un
  contour fermé de section** (et éventuellement sa hachure), **sans attribut ni
  texte**. *(Mesuré : la seule définition répétée du plan réel qui aurait
  complété une section vide est un repère de niveau — un triangle, une ligne et
  un attribut, inséré six fois à l'échelle ± 5 : les trois conditions
  l'écartent.)*

### 3.2 N2 — la signature C1 (complète, avec grille)

Un contour est un poteau **C1** si les dix critères sont vrais. Pour chacun :
pourquoi, rappel et précision — **mesurés** sur le plan réel, ses variantes et
le corpus, **attendus** (estimés) ailleurs — et modes d'échec. Le rappel d'un
critère est la part des vrais poteaux qui le satisfont ; sa précision, ce
qu'il écarte de faux.

| # | Critère | Pourquoi | Rappel (mesuré ; attendu) | Précision (mesuré ; attendu) | Modes d'échec |
|---|---|---|---|---|---|
| C1.1 | **Section** : rectangle (4 angles droits, `rectangle_de`), cercle, ou polygone **inscrit** — au moins 5 sommets, tous à la même distance de leur centre (5 %) : hexagone, octogone, bord polygonal d'une hachure de cercle ; un polygone reste un polygone (il ne propose rien, comme aujourd'hui) | une section de poteau est une de ces formes ; triangles, chevrons, barres, nuages, contours irréguliers ne le sont pas | 63 / 63 (tous rectangles) ; attendu 97–99 % | écarte tous les polygones irréguliers qui sont poteaux en `0.6.0` : le triangle d'un repère de niveau (v02, v05, v11, v13, v14), la barre rouge (feuille A), les 2 contours de la feuille B (non vérifiés, risque 6), les 2 de v08 — aucun n'est dans la référence ; attendu + 0 à + 3 points une fois C1.2 appliqué | poteaux composés (L, croix) : hors domaine ; rectangle à sommets parasites non reconnu ; un disque plein (repère de nœud) est une section : risque 3 |
| C1.2 | **Coupé** (N1, § 3.1) | un poteau en plan est tranché par le plan de coupe : hachuré ; une annotation, un symbole, un objet vu ne le sont pas | les 63 sont coupés sur le plan réel et toutes ses variantes, v07 compris (grâce au jumeau sans nom) ; attendu 85–95 % (bureaux qui dessinent leurs poteaux vides) | écarte tous les faux poteaux vides : le Ø 28 partout, les cercles d'annotation Ø 50 et Ø 40 (v01, v05, v06, v13, v14, v15), le Ø 90,3 (v05, v13, v14), la cabine des plans fabriqués ; rien contre les faux remplis de v08 et v11 ; attendu + 5 à + 30 points selon le bureau | **poteaux dessinés vides** (plan de fondations où le poteau est au-dessus, dessin au trait) : partiels, complétés seulement par un nom, un bloc répété ou un repère (§ 3.4) ; remplissage fortuit de même taille sous un symbole |
| C1.3 | **Taille plausible** : côtés 100–2 000 mm, élancement ≤ 4 (unité connue) ; sinon côté ≤ 0,3 entraxe médian | règle actuelle, inchangée (côtés du rectangle, diamètre du cercle, boîte alignée sur la feuille pour un polygone) ; la barre rouge, qui la passait par sa boîte alignée (3,3 au lieu de 10,6), est écartée par C1.1 | 63 / 63 ; attendu ≈ 99 % si l'unité est juste, 0 si elle est fausse d'un facteur 10 (v09) | écarte les 2 sections hachurées 130 × 30 au nœud (élancement 4,33, non vérifiées), les massifs de plus de 2 m ; attendu : inchangé | unité fausse (v08, v09) ; noyaux de moins de 2 m (C1.7) |
| C1.4 | **Au nœud** : un nœud de la grille dans le contour, ou à moins d'un demi-côté de son centre | règle actuelle : un poteau porte la grille | 63 / 63 de R63 (par construction) ; 58 / 63 sur v04 et v14 (axe P absent) ; attendu 80–95 % (poteaux hors grille : C2 ou candidats G6) | écarte les 1 584 contours hachurés compacts hors nœud du plan réel (§ 5.1 du plan) : c'est lui qui fait l'essentiel de la précision ; attendu : idem | axe non trouvé → poteau perdu ; poteau excentré de plus d'un demi-côté |
| C1.5 | **Dans la zone structurelle** : la zone de G2 (enveloppe des axes à bulle et famille, élargie d'un entraxe médian) ; à défaut (feuille PDF, grille nommée sans signature A), l'enveloppe des axes étiquetés élargie d'un entraxe ; sans axe étiqueté, critère non applicable (dit) | le cartouche, les légendes, les détails de l'espace objet sont hors de la grille du bâtiment | 63 / 63 et 58 / 58 ; attendu ≈ 100 % | 0 faux écarté : aucun faux poteau du corpus n'est hors zone ; attendu + 0 à + 5 points (détails munis d'axes à bulles hors du bâtiment) | un détail à grille propre, assez proche pour entrer dans la zone ; zone sous-estimée si les axes à bulle ne couvrent pas tout le bâtiment |
| C1.6 | **Pas un pieu** (G3) : ni germe, ni dessin de pieu ; et, sans regarder le nom, aucun contour de **même centre et même taille (5 %) qu'un pieu** de G3, quel que soit son calque | un pieu n'est jamais un poteau ; G3 n'absorbe dans le dessin d'un pieu que les contours de rôle inconnu, hachure ou pieu | 63 / 63 (aucun vrai poteau n'est un pieu) ; attendu ≈ 100 % | v01 : 102 dessins de pieux écartés (G3) ; v07 : 125 hachures de pieux sur un calque rangé « texte », que G3 n'absorbe pas et qui seraient sans lui des conflits (cas 5) ; attendu : celle de G3 | ceux de G3 ; un poteau rond centré sur un pieu de même diamètre (le même objet dessiné deux fois) est écarté |
| C1.7 | **Pas un contenant** : règle actuelle (un contour fermé plus petit dedans, hors annotations nommées) | socles, massifs, cages | 63 / 63 ; attendu 95–99 % | 13 socles sur le plan réel, 17 sur les variantes sans noms ; attendu : inchangé | armatures ou repères dessinés dans un poteau d'un dessin anonyme : le poteau devient contenant (risque 2) |
| C1.8 | **Pas barré** de ses deux diagonales | trémie | 63 / 63 ; ≈ 100 % | 1 trémie (v01, v04 à v06, v13 à v15 ; nommée sur le plan réel) ; inchangé | — |
| C1.9 | **Pas nommé ouverture** par un texte dedans (« GAINE », « ASC. ») | gaine, ascenseur | 63 / 63 ; ≈ 100 % | fixtures ; inchangé | texte d'une autre langue |
| C1.10 | **Pas un bout de voile** : un côté égal (5 %) à l'épaisseur d'une plage remplie allongée (élancement ≥ 4, épaisseur plausible de voile), centre sur l'axe de la plage (5 % de l'épaisseur), et la touchant à son extrémité (2 tolérances) | § 5.4 du plan : un bout de voile au nœud est pris pour un poteau ; un vrai poteau en bout de voile est en général plus large que le voile | 63 / 63 (0 cas) ; attendu 95–99 % | **0 cas** dans le corpus et les variantes (mesuré) ; attendu + 0 à + 10 points sur les plans de coffrage à voiles | poteau de même largeur que le voile qu'il termine : perdu ; voile non rempli : rien à prolonger |

**Corroboration citée, jamais décisive** : `section_repetee` — la section
appartient à une classe d'au moins 2 sections identiques (côtés triés à 1 %).
Plan réel : 60 / 63 (trois sections uniques : 40 × 40, 30 × 65, 35 × 50) ; en
faire un critère aurait perdu ces trois poteaux.

**Hors de C1** : la règle de l'**enceinte** (un contour VIDE dans une enceinte
vide) ne concerne plus que les sections vides, qui sont partielles ; elle est
gardée telle quelle pour elles.

### 3.3 N2 — la signature C2 (complète, sans grille)

Seulement quand le dessin **n'a aucune grille** (aucune famille d'axes) : au
moins 3 sections **identiques** (côtés triés à 1 %), C1.1–C1.3 et C1.6–C1.10
vrais, **unité connue** (sans grille, pas d'entraxe pour borner la taille),
dont les centres s'alignent dans deux directions perpendiculaires (celle de la
section et sa normale, à 1°) avec **au moins 3 sections par file** dans chaque
direction, et un **entraxe implicite** (médiane des écarts entre sections
voisines d'une file) **d'au moins 4 fois le plus grand côté**, et d'au plus
20 m. Elle donne des poteaux, pas des axes (L5), sans nœud (identifiant par
rang).

* **Pourquoi** : un plan de coffrage sans axes dessinés garde ses poteaux
  alignés ; la géométrie décorative répétée (carreaux, places de parking,
  symboles d'une légende) a un pas de l'ordre de sa taille.
* **Mesuré** : **aucun cas** dans le corpus — des 52 fichiers sans grille,
  aucun n'a de section remplie plausible d'unité connue. C2 ne change donc
  aucune sortie mesurée ; elle sera validée sur fixtures (§ 6).
* **Attendu** (§ 5.3 du plan) : précision 80–90 %, rappel 50–80 %.
* **Modes d'échec** : motifs décoratifs à grand pas (lampadaires, plots) ;
  poteaux de sections toutes différentes (rappel nul) ; une grille partielle
  trouvée empêche C2 sur le reste du dessin.

### 3.4 Partielle, et ce qui la complète

Une section **vide** qui satisfait C1.1 et C1.3 à C1.10 est **partielle**. Elle
devient un poteau seulement si :

1. **un nom** la complète : son contour est de rôle `poteau` (calque ou bloc) —
   la règle nommée d'aujourd'hui, 0,85 (`grande_grille` : 400 poteaux) ;
2. **un bloc répété** la complète (§ 3.1) : 0,75 ;
3. **un repère de poteau** voisin la complète : un texte de la forme d'un
   repère de poteau (`P1`, `C3`, `POT12` : les préfixes de poteau du lecteur de
   repères) dans la section ou à moins d'un grand côté de son centre :
   `forme`, 0,6 (la confiance d'aujourd'hui d'une section vide).

Sinon : rien en G4 (candidat : G6), compté au compte rendu
(`partielle_vide`). **Mesuré** : 0 complétion par bloc répété ni par repère
dans le corpus et les variantes (une seule complétion par bloc était possible,
le repère de niveau, écarté par les conditions du § 3.1).

| Complétion | Pourquoi | Mesuré | Attendu | Modes d'échec |
|---|---|---|---|---|
| Nom (`poteau`) | le bureau dit ce que la géométrie ne montre pas (poteau au-dessus, dessin au trait) | 400 poteaux de `grande_grille`, inchangés | précision et rappel : ceux du calque, comme aujourd'hui (`grande_grille` : 400 / 400) | un calque de poteaux mal tenu |
| Bloc répété (N1) | un poteau-type inséré à chaque emplacement est un objet répété, pas un trait | 0 cas ; le seul candidat (repère de niveau) écarté par les conditions | précision 85–95 %, rappel des poteaux vides en blocs 70–90 % | repères de nœud en bloc à l'échelle 1, de forme carrée ou ronde |
| Repère de poteau voisin | un poteau dessiné vide porte souvent son repère (`P12`) | 0 cas | précision 70–85 % ; rappel non estimé (aucun cas : il dépend de l'habitude du bureau de repérer ses poteaux) | un cercle d'annotation repéré `C3` ; un repère d'une autre langue que les préfixes connus |

### 3.5 N3 — les noms

* Un contour de rôle `poteau` qui a C1 complète : **confirmé**, `geometrie`,
  le nom cité, **0,90** (`charpente_mm` : 8 poteaux ; v11 : 62).
* Un contour de rôle `poteau` sans C1 complète (vide, hors nœud, irrégulier,
  dessin de pieu) : **comme aujourd'hui**, la règle du nom, 0,85 — sauf s'il
  est un germe de pieu (G3 : le pieu est gardé, le conflit est dit avec lui).
* **Le nom qui compte est celui du contour de la section** ; une section
  dessinée par sa seule hachure prend le nom de la hachure. Un remplissage
  d'un autre rôle, **jumeau** d'une section retenue (même centre, même taille à
  5 %), n'est qu'une preuve N1 (C1.2) : ni confirmation, ni conflit. *(Mesuré :
  sur v07, juger le nom des hachures aurait fait 126 conflits sur des poteaux
  vrais — leurs 63 hachures, sur la feuille et dans la xréf.)*
* Un contour d'un **autre rôle** n'est évalué que pour le cas 5 (§ 3.6) : sans
  C1 complète, il est ignoré, non compté, comme aujourd'hui. **Mesuré : 0 cas 5**
  sur le plan réel, ses 16 variantes et le corpus, une fois C1.1, C1.6 et la
  règle du jumeau appliquées ; sans elles, v07 en aurait 251 (les 126 hachures
  de poteaux, et 125 hachures de pieux sur un calque rangé « texte ») et v11, 2
  (deux triangles qu'un bloc explosé nomme « mur »).

### 3.6 L'échelle de preuves, pour les poteaux

| Cas | Décision | `classified_by` | Confiance |
|---|---|---|---|
| 1. C1 complète, contour nommé `poteau` | poteau | `geometrie` (nom cité) | **0,90** |
| 1'. C1 complète, contour sans rôle (`inconnu`, `hachure`) | poteau | `geometrie` | **0,85** |
| 1''. C1 complète par un bloc répété (section vide) | poteau | `geometrie` | 0,75 |
| C2 complète (sans grille) | poteau | `geometrie` | 0,65 |
| 2. Partielle + nom `poteau` ; 4. nom seul | poteau, comme aujourd'hui | la règle du nom | 0,85 |
| 2'. Partielle + repère de poteau voisin | poteau | `forme` | 0,6 |
| 5. C1 complète, contour nommé d'un **autre** rôle (`fondation`, `voile`, `axe`, `cote`, `texte`, `cadre`…) | poteau ; **conflit dit** dans `unresolved` (mesuré : 0 cas, § 3.5) | `geometrie` | **≤ 0,4** |
| 6. Partielle seule | rien (candidat : G6) | — | — |

**Pourquoi 0,85 pour C1** : comme G2 (axe à bulle et famille) et G3 (pieu de
classe P), une signature complète vaut un nom ; la règle de forme
d'aujourd'hui (0,65) acceptait tout contour rempli au nœud, sans section, sans
zone, sans exclusion géométrique des pieux ; C1 est plus exigeante. Les
confiances restent indicatives et non calibrées (§ 8 du plan).

Les propositions suivent, inchangées dans leur règle (`propositions.py`) : un
groupe de poteaux de même repère et même section propose ses côtés (ou son
diamètre) à la plus faible confiance du groupe ; un polygone ne propose rien.

## 4. Pipeline et ordre d'évaluation

```
axes (G2) ─► zone structurelle (G2) ─► formes fermées ─► pieux (G3)
   ─► poteaux : pour chaque contour —
        nommé poteau ─► germe de pieu : rien (G3) ; C1 complète : confirmé (0,90) ;
                        sinon la règle du nom (0,85), comme aujourd'hui
        d'un autre rôle ─► C1 complète et pas jumeau d'une section retenue : cas 5 (0,4) ;
                        sinon comme aujourd'hui (ignoré ; `pieu`, `fondation` comptés)
        sinon ─► pieu ? (C1.6) ─► nœud (C1.4) et taille (C1.3) : sinon ignoré, non compté
             ─► exclusions d'aujourd'hui : non compact, contenant (C1.7), barré (C1.8),
                ouverture nommée (C1.9), enceinte (sections vides)
             ─► section (C1.1) ─► zone (C1.5) ─► bout de voile (C1.10)
             ─► coupé (C1.2 : lui-même, ou un jumeau rempli de n'importe quel calque)
             ─► complète : poteau (0,85)
             ─► partielle (vide) : nom / bloc répété / repère, sinon `partielle_vide`
      sans grille : C2
   ─► regroupement contour + hachure (inchangé) ─► identifiants par nœud (inchangés)
   ─► voiles, bandes, graphe, cotes, repères, dalles (inchangés)
```

Les raisons d'aujourd'hui (`pieu`, `fondation`, `dessin_de_pieu`, `non_compact`,
`contenant`, `ouverture_barree`, `ouverture_nommee`, `dans_une_enceinte`) sont
évaluées d'abord, sur les mêmes mesures qu'aujourd'hui : **leurs comptes ne
changent pas**. Les raisons nouvelles — `section_irreguliere`, `hors_zone`,
`bout_de_voile`, `partielle_vide` — ne comptent donc que des contours qui sont
des poteaux en `0.6.0` (plan réel : `partielle_vide` 1, le Ø 28). Coût
attendu : un index des contours remplis et un des pieux (O(n log n)) ; la zone
et les nœuds sont déjà calculés ; mesuré en campagne (A9).

## 5. Attendu : avant / après

Mesuré par un **prototype hors du dépôt** qui remplace la détection des
poteaux le temps d'une extraction complète (poteaux ET propositions de bout en
bout) : C1.2 à jumeau sans nom, C1.3–C1.9, zone, complétions ; puis corrigé de
ce que le prototype n'appliquait pas — C1.1, les conditions du bloc répété,
C1.6 sans nom et le cas 5 (il comptait les contours d'un autre rôle à C1
complète sans en faire des poteaux : § 3.5) — corrections vérifiées une à une
sur les sorties. (Le prototype mesurait aussi un polygone par son rectangle
minimal : seuls des comptes de rejets en différaient ; la conception garde la
mesure d'aujourd'hui, § 4.)

| Variante | Poteaux `0.6.0` → G4 | Vrais (R63) | Faux | Précision | Rappel | Propositions de poteau fausses (valeurs distinctes) |
|---|---|---|---|---|---|---|
| **plan réel** | 64 → **63** | 63 → 63 | 1 → **0** | 0,984 → **1,000** | 1,000 → 1,000 | 1 → **0** |
| **v01** calques neutres | 66 → **63** | 63 | 3 → **0** | 0,955 → **1,000** | 1,000 | 2 → **0** |
| **v04** aucune convention | 59 → **58** | 58 | 1 → **0** | 0,983 → **1,000** | 0,921 | 1 → **0** |
| **v13** noms neutres, types gardés | 68 → **63** | 63 | 5 → **0** | 0,926 → **1,000** | 1,000 | 3 → **0** |
| **v14** tout renommé | 63 → **58** | 58 | 5 → **0** | 0,921 → **1,000** | 0,921 | 3 → **0** |
| **v15** tout sur `0` | 66 → **63** | 63 | 3 → **0** | 0,955 → **1,000** | 1,000 | 2 → **0** |
| v00, v03, v07, v10, v12 | 64 → 63 | 63 | 1 → 0 | → 1,000 | 1,000 | 1 → 0 |
| v02 / v05 / v06 | 65 / 73 / 71 → 63 | 63 | 2 / 10 / 8 → 0 | → 1,000 | 1,000 | 1 / 4 / 3 → 0 |
| v08 (unité mm, fausse) | 3 → 1 | 0 | 3 → 1 | — | 0 | 2 → 2 (235 × 310 : un massif à l'unité fausse) |
| v09 (unité m, fausse) | 0 → 0 | 0 | 0 | — | 0 | 0 |
| v11 (blocs explosés) | 91 → 89 | 63 | 28 → 26 | 0,692 → 0,708 | 1,000 | 7 → 6 (sections préfabriquées aux nœuds de faux axes, § 8) |

**Propositions du plan réel nommé** : 335 → **334**. La seule retirée est
`column_diameter` 28,3945 (le faux poteau). Les 11 autres propositions de
section gardent **leurs valeurs, leurs repères et leurs groupes** ; leur
confiance passe de **0,65 à 0,85** (§ 3.6 ; de 0,6 à 0,85 sur v07, dont les
hachures étaient écartées par leur nom : ses 63 poteaux, identiques par
ailleurs, y deviennent `filled`). **Aucune autre proposition ne
change** (grille, entraxes, dimensions : identiques, confiances comprises) —
vérifié sur le plan réel et ses 16 variantes.

**`column_diameter`** : `0.6.0` en propose sur le plan réel et 14 de ses
16 variantes (toutes sauf v08 et v09) — 32 propositions, **toutes fausses** :
le plan réel n'a aucun poteau rond. G4 : **aucune, nulle part**. Les
propositions de poteau fausses qui restent sont des largeurs et des
profondeurs : 235 × 310 sur v08 (un massif lu à l'unité fausse), six valeurs
sur v11 (§ 8, risque 7).

**Corpus** (prototype, 94 fichiers) : 56 fichiers sans poteau inchangés ;
retirés : la cabine d'ascenseur des deux plans de fondations sans unité (et
ses propositions fausses 120 × 100), la barre rouge de la feuille A, les deux
polygones de la feuille B (non vérifiés ; vides sur une coupe, irréguliers), le
cercle Ø 28 des fichiers du plan réel ; la cage d'ascenseur de la feuille B
reste écartée (contenant), comme le demande le § 5.5 du plan ; tous les autres
poteaux gardés, à 0,85 (C1) ou 0,90 (`charpente_mm`, nom confirmé),
`grande_grille` inchangé (400 par le nom, 0,85).

**Cible du § 11 du plan** (« v01/v04/v14 : 64 ± 2 ») : v01 l'atteint (63 :
la cible comptait le cercle Ø 28) ; **v04 et v14 ne l'atteignent pas (58)** :
les 5 poteaux de l'axe P n'ont pas de nœud quand G2 ne trouve pas cet axe sans
nom (bulle isolée, aucune famille : `GEOMETRIE_D_ABORD_G2.md` § 7.6). G4 ne
les retrouve pas : C2 ne s'applique que sans grille, et une file oblique de
cinq sections différentes n'est pas une grille implicite. À traiter avec les
candidats (G6).

**Écart à l'estimation du plan** (§ 5.3) : il attendait ≈ 2 faux poteaux sur le
plan sans noms, des cercles du cartouche que la zone écarterait. Mesurés, ce
sont des cercles d'annotation vides posés sur des pieux : C1.2 les écarte, la
zone n'écarte rien.

## 6. Critères d'acceptation

| # | Critère | Seuil |
|---|---|---|
| A1 | Plan réel : les 63 vrais poteaux, identiques à `0.6.0` (identifiant, centre, section, angle, nœud, repère, rempli) ; le cercle Ø 28 retiré ; axes, pieux, voiles, poutres inchangés ; aucun conflit de poteau | exact |
| A2 | Plan réel : 334 propositions = les 335 de `0.6.0` moins `column_diameter` 28,3945 ; valeurs, repères, unités identiques ; seules les confiances des 11 propositions de section changent (0,65 → 0,85) | exact |
| A3 | v00–v03, v05–v07, v10, v12, v13, v15 : 63 poteaux, précision 1,000, rappel 1,000, 0 proposition de poteau fausse, aucun conflit de poteau (cas 5) | exact |
| A4 | v04, v14 : 58 poteaux, précision 1,000 ; les 5 manquants sont ceux de l'axe P | exact |
| A5 | v08, v09, v11 : aucun faux poteau de plus qu'en `0.6.0` | ≤ |
| A6 | Corpus : seuls changent les poteaux listés au § 5 et les confiances de l'échelle ; aucune proposition autre que de poteau ne change ; les comptes des raisons de rejet d'aujourd'hui sont inchangés (§ 4) | exact, listé |
| A7 | Fixtures du § 7 : chacune donne l'issue écrite | toutes |
| A8 | Suites d'extraction et d'API, harnais des documents, `export_contracts.py --check` ; les tests d'invariance de G1–G3 (J1, K1) passent **sans modification** | verts |
| A9 | Coût sur le plan réel | ≤ + 5 % |

## 7. Plan de validation

**Fixtures** (`fabrique_geometrie`), une par confusion du § 2 :

* poteaux hachurés sur calque `0` sans aucun nom (C1, 0,85) ; les mêmes nommés
  `POTEAUX` (0,90, mêmes identifiants) ; leurs hachures sur un calque « texte »
  (jumeau sans nom : toujours des poteaux, aucun conflit) ;
* cercles d'annotation vides posés sur des pieux et aux nœuds : aucun poteau ;
* hachures de pieux sur un calque rangé « texte » : aucun poteau, aucun
  conflit (C1.6 sans nom) ;
* un poteau rond dessiné par sa seule hachure (polygone inscrit de 64 sommets) :
  un poteau polygone, aucune proposition ;
* poteaux vides en blocs anonymes répétés à l'échelle 1 (0,75) ; un repère de
  niveau en bloc à l'échelle 5 avec attribut : aucun poteau ;
* poteaux vides avec repères `P1`, `C3` (`forme`, 0,6) ; sans repère : aucun ;
* massifs remplis contenant des pieux ; socles vides autour des poteaux :
  aucun poteau, raisons comptées ;
* cartouche et légende dans l'espace objet, avec cercles et carrés remplis,
  traversés par le prolongement d'un axe : hors zone ;
* voile rempli de 20 cm terminé à un nœud par un morceau de 20 × 25 : bout de
  voile ; poteau 40 × 40 au bout d'un voile de 20 : poteau ;
* triangle, chevron, barre allongée remplis aux nœuds : aucun poteau
  (`section_irreguliere`, `non_compact`) ;
* grille implicite sans axes dessinés, 3 × 4 sections pleines espacées de
  6 m (C2, 0,65) ; un carrelage de carrés pleins jointifs : aucun poteau ;
* un massif plein nommé `SEMELLES` au nœud, sans contenu : poteau à 0,4,
  conflit dit ;
* la feuille PDF fabriquée : ses poteaux restent (C1) ; une barre pleine
  allongée et un contour irrégulier aux nœuds : aucun poteau.

**Mesures** : le plan réel et ses 16 variantes (§ 5), précision et rappel
contre R63, poteaux ajoutés et retirés un à un, propositions (catégorie,
valeur, repère, confiance) ; balayage des 94 fichiers, chaque changement classé.

**Campagne** : comme G2 et G3 — conception commitée, code commité sur l'arbre
mesuré (empreinte vérifiée), balayage et variantes refaits sur le commit et
comparés octet pour octet, suites, contrat et harnais sur l'arbre gelé,
résultats écrits ici (§ 10).

## 8. Risques

1. **Poteaux dessinés vides** dans un dessin sans nom ni bloc répété ni
   repère (plans de fondations, dessins au trait) : perdus (candidats G6). Le
   choix est délibéré (§ 5.4 du plan) : ce sont les mêmes contours vides que
   les cercles d'annotation.
2. **Armatures ou repères dessinés DANS un poteau** d'un dessin anonyme : le
   poteau devient contenant (C1.7 ne les ignore que par leur nom).
3. **Repères de nœud pleins** (un disque plein d'au moins 100 mm à chaque
   nœud), ou un remplissage fortuit de même taille sous un symbole vide : des
   poteaux ; à mesurer en campagne.
4. **Semelles et massifs pleins sans contenu** au nœud, de moins de 2 m :
   nommés, un conflit dit (0,4) ; sans nom, des poteaux.
5. **Bouts de voile** : règle sans cas réel mesuré ; un poteau de la largeur du
   voile qu'il termine est perdu.
6. **Feuille PDF B** : ses deux contours, peut-être de vrais poteaux (coupés :
   un remplissage de béton les double), ne sont plus des poteaux (polygones à
   4 sommets sans angles droits, C1.1) ; ils ne donnaient déjà aucune
   proposition (un polygone ne propose rien).
7. **v11** (blocs explosés) : 26 faux poteaux restent sur les nœuds de faux
   axes (`GEOMETRIE_D_ABORD_G2.md` § 7.6) — 21 par le nom d'un bloc imbriqué
   (la règle du nom, inchangée, dont 2 polygones), 5 par la signature C1 : des
   sections préfabriquées hachurées, peut-être de vrais poteaux hors de la
   grille de référence ; leurs 6 propositions de section ne sont pas dans la
   référence.
8. **Confiance** : 0,65 → 0,85 pour les poteaux C1 du plan réel ; non calibrée
   (campagne du plan, § 9).
9. **C2** : aucun cas mesuré ; seule la fixture la valide.
10. **C1.6 sans nom** : un poteau rond centré sur un pieu de même diamètre (le
    même objet dessiné deux fois) n'est plus un poteau.
11. **Cas 5** : une section remplie dessinée sans contour sur un calque mal
    rangé (des hachures sur un calque « texte ») devient un poteau à 0,4 avec
    conflit, au lieu de 0,85 ; mesuré : 0 cas (§ 3.5).

## 9. Impact de migration

* **Base de données : aucune migration.** Le modèle structurel est un JSON ;
  `classified_by = "geometrie"` existe depuis G2 ; les critères
  (`evidence.signature`), les raisons de rejet
  (`report.column_candidates_rejected` : `partielle_vide`,
  `section_irreguliere`, `hors_zone`, `bout_de_voile`) et les conflits
  (`unresolved`) sont des valeurs libres ; les comptes des raisons
  d'aujourd'hui ne changent pas (§ 4).
* **Contrat** : aucune forme nouvelle ; les descriptions de `classified_by` et
  de `signature` citent les critères des poteaux (`section`, `coupe`,
  `au_noeud`, `zone`, `section_repetee`, `bloc_repete`, `repere`,
  `grille_implicite`) ; contrat régénéré, étiquette de l'écran
  (`web/lib/documents.ts`) étendue.
* **Version `0.7.0`** : des poteaux et des propositions changent.
* **Documents déjà analysés** : une analyse qui a produit des propositions ne
  peut pas être refaite (la base le refuse : les propositions et leurs
  décisions sont la trace de ce qui a été lu). Leurs extractions restent en
  `0.6.0`, avec leurs décisions ; seules les nouvelles analyses passent par
  G4. Une décision prise sur `column_diameter` 28,3945 reste attachée à
  l'extraction `0.6.0` qui l'a proposée.
* **Écran, API, calcul** : inchangés ; le pré-remplissage reçoit moins de
  propositions de poteau fausses ; les poteaux du plan réel passent à 0,85.
* **Aval** : sur les variantes, aucune proposition de poutre, d'entraxe ou de
  dimension ne change (mesuré) ; sur un plan où un faux poteau portait une
  poutre, sa travée peut changer (dite au § 10).

## 10. Résultats

À écrire après l'implémentation.
