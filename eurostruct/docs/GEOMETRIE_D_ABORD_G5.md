# Géométrie d'abord — G5 : les voiles par leur signature

> **Statut : conception, avant le code.** Phase G5 de `GEOMETRIE_D_ABORD.md`
> (§ 11 : « Voiles V1/V2, `MLINE` » ; sortie mesurée : « feuilles PDF,
> fixtures »), selon le § 6 (voiles) et l'échelle de preuves du § 1.4. Elle
> s'appuie sur G1 (remplissages, multilignes), G2 (grille, zone
> structurelle), G3 (pieux) et G4 (poteaux). Toutes les mesures ont été faites
> hors du dépôt : sur `0.7.0` (export gelé de `805ff7e`, dont les sorties sont
> celles de la campagne G4 — 94 / 94 octet pour octet, 17 / 17 variantes hors
> durée), et sur un **prototype** qui remplace la détection des voiles le
> temps d'une extraction complète (voiles, poutres, travées, dalles, repères,
> propositions mesurés de bout en bout). Le prototype n'est pas le code de
> production ; il valide la conception.
>
> **Contre-mesure avant le code (§ 10) : la vérification échoue.** Telle que
> conçue, G5 retire de vrais voiles parce qu'ils ne sont pas sur un axe
> (V1.6) ou pas butés à un bout (V1.7) : 7 voiles (14 contours) sur chaque
> variante sans noms, 1 voile en béton armé sur la feuille B. La conception
> est à revoir avant toute implémentation.

## 0. Ce que G5 fait, et ce qu'il garantit

**Objet.** Reconnaître un voile par ce qu'il EST — une **bande coupée**
(pleine), droite, d'**élancement au moins 4**, d'**épaisseur plausible**,
**posée sur un axe** de la grille et **butée à un bout** contre un poteau ou
contre un autre élément plein qui la croise — avant de regarder les noms ; que
les hachures isolées, les échantillons de légende, les cloisons et les
vitrages des plans d'architecte, les « murs » trop minces d'un modèle
d'architecte et les poteaux allongés ne soient plus des voiles ; et qu'aucune
épaisseur ne soit proposée à partir d'eux.

**Garanties.**

| # | Garantie | Comment |
|---|---|---|
| L1 | **Les 4 voiles du plan réel nommé restent identiques** (identifiant, contour, axe, épaisseur, longueur, confiance, preuve, repère), et **ses 334 propositions aussi**, les 4 épaisseurs de voile (25, 0,8) comprises. | Ce sont des paires de traits VIDES sur un calque de voile : une signature partielle que le nom complète, la règle d'aujourd'hui (§ 3.4). Mesuré (§ 5). |
| L2 | Un voile est décidé par une **signature complète** (V1), ou par un **nom de voile** qui complète une signature partielle (paire de traits, contour vide, multiligne) — jamais par une forme seule, jamais par le nom d'un autre rôle. | § 3 |
| L3 | Un nom ne fait que **compléter** ou **confirmer** (+ 0,05) ; une V1 complète sur un contour nommé d'un autre rôle est un **conflit dit** (0,4). | § 3.5 |
| L4 | Sur le plan réel et ses variantes nommées, **aucune proposition ne change** ; sur les variantes sans noms, **seules disparaissent les 19 épaisseurs** tirées des bandes hachurées. | Mesuré (§ 5). |
| L5 | Rien n'est inventé : une épaisseur est LUE (bande, paire de traits, multiligne) ; aucun voile n'est déduit d'un repère, d'une cote ou d'une légende. | Interdictions 2 et 5 |
| L6 | Tout changement de sortie est cité : voiles ajoutés, retirés, confiances, propositions, poutres, sur le plan réel, ses variantes et tout le corpus. | § 5 ; nature de chaque voile retiré au § 10 ; résultats au § 11 (à venir) |
| L7 | **Chaque dépendance aux noms qui reste est écrite**, avec ce qui la lèverait. | § 3.6 |

**Hors de G5.** Les partitions apprises, les candidats exportés et
`names_agree` (G6) ; les voiles composés d'un seul polygone (en L, en T), courbes
ou d'épaisseur variable (hors domaine, § 10 du plan) ; le recoupement de
`$INSUNITS` (D1) ; l'affectation des repères (`libelles.py`, inchangée) ; le
vocabulaire des noms (inchangé : FR, NL, EN, DE, AIA).

## 1. Point de départ mesuré (`0.7.0`)

### 1.1 Les règles d'aujourd'hui

`voiles.py` connaît trois règles, et lit les multilignes sans les interpréter :

| Règle | Ce qu'elle prend | Contrôle géométrique | Confiance |
|---|---|---|---|
| R1 — nom | tout contour fermé (sauf un cercle) d'un calque ou d'un bloc de **voile** ; ou d'un calque de **poteau** s'il est un rectangle d'élancement > 4 | **aucun** (ni épaisseur, ni forme) | 0,8 |
| R2 — forme | un contour **sans rôle** (`inconnu`), plein, rectangle d'élancement ≥ 4, épaisseur 80–600 mm (sans unité : ≤ 0,1 entraxe) ; une hachure d'un calque nommé (« hachure », « texte »…) n'en est pas | élancement, épaisseur | 0,55 |
| R3 — paire nommée | deux traits parallèles d'un calque de voile, écart 80–600 mm (sans unité : 0,5 à 10 % de l'entraxe), recouvrement ≥ 2 écarts | écart, longueur | 0,8 |
| Multilignes | lues depuis G1, comptées « entité non lue » | — | — |

R2 décide **sans regarder où** est la bande (ni zone, ni axe, ni appui) ; R1
décide **sans regarder ce qu'est** le contour ; un remplissage blanc d'une
feuille PDF est « plein ».

### 1.2 Le plan réel

**4 voiles, tous par R3 (le nom du calque), aucun dessiné coupé.**

| Voile | Repère | Épaisseur × longueur (cm) | Dessin | Axe | Jonction | Cote d'épaisseur |
|---|---|---|---|---|---|---|
| `wall:1` | VP3 | 25 × 2 485 | deux traits (`LINE`, polyligne ouverte), vides | centré | en L avec `wall:2` | 2 |
| `wall:2` | VP4 | 25 × 800 | deux traits, vides | à 0,7 épaisseur | en L avec `wall:1` | 1 |
| `wall:3` | S38 | 25 × 584,5 | deux traits, vides | centré | aucune (interrompu par des massifs) | 0 |
| `wall:4` | S36 | 25 × 482 | deux traits, vides | centré | aucune | 0 |

Les 4 donnent 4 propositions `wall_thickness` 25 (0,8), une par repère. Les
repères des deux morceaux du voile de droite sont ceux de **massifs voisins**
(S38, S36) — la valeur est juste, le repère probablement pas ; c'est
l'affectation des repères, hors de G5 (et L1 exige ces propositions
inchangées).

**25 bandes hachurées longues et minces ne sont pas des voiles** : elles sont
sur des calques nommés « hachure », que R2 exclut. Chacune est dessinée comme
un élément coupé — une hachure pleine doublée d'une hachure à motif (de la
bibliothèque standard), parfois aussi dans la xréf : **14 bandes**, de 15 à
30 cm d'épaisseur et de 81 à 290 cm de longueur.

| Bandes (groupes) | Position | Repères écrits à côté (lus sur v01) | Nature |
|---|---|---|---|
| 10 | hors de tout axe, dans trois zones du plan, certaines en T entre elles | série V… (VA…, VB…, VC…), mais aussi L… | non vérifiée ; peut-être des voiles |
| 1 | hors de tout axe, prolongée au-dessus par une autre plage | VO1 | non vérifiée ; peut-être un voile |
| 2 | 130 × 30 sur un axe, à un nœud, dans un massif | repères de poteaux préfabriqués (C03…) | **probablement des poteaux préfabriqués de section allongée** (élancement 4,33) |
| 1 | 290 × 30 au nu d'un axe, morceau hachuré d'une bande plus longue (droite puis courbe) | — | non vérifiée |

Aucune n'a de poteau à ses bouts, aucune ne contient de pieu ; 5 ont une cote
d'épaisseur. Elles ne sont pas dans la référence (§ 1.7) et G5 ne les ajoute
pas (§ 3.2).

**Ce que le plan dit et que le modèle ne sait pas.** Le dessin porte
**34 textes** de la forme V + lettre + numéro (séries VA, VB, VC, VL, VO, VP),
dont les deux repères des voiles nommés : vraisemblablement des repères de
voiles, dont la plupart sont dessinés en **paires de traits vides sur des
calques qui ne disent pas « voile »**. La référence nommée (R4, § 1.7) est donc
**certainement incomplète**, et le rappel contre les vrais voiles du dessin
n'est pas mesurable sans un relevé d'ingénieur. Le plan ne définit aucune
épaisseur de trait (`DEFAULT` partout) — rien à lire de ce côté.

### 1.3 Les variantes

| Variante | Voiles `0.7.0` | Règle | Dans R4 | Hors R4 | Épaisseurs proposées |
|---|---|---|---|---|---|
| **plan réel** ; v00, v02, v03, v06 (allemand), v07 (AIA), v10, v12 | 4 | R3 (le nom traduit compris) | 4 | 0 | 4 (25) |
| **v01, v04, v05 (espagnol), v13, v14, v15** | **25** | R2 (forme, 0,55) | **0** | **25** | **19** (30, 20, 15), toutes hors référence ; les 4 de 25 perdues |
| v08 (unité mm, fausse) | 0 | — | 0 | 0 | 0 |
| v09 (unité m, fausse) | 20 | R2 | 0 | 20 : les **échantillons d'épaisseur de trait de la légende** (polylignes épaisses de 0,13 à 0,57 unité, lues comme des mètres) | 5 |
| v11 (blocs explosés) | **334** | R1 et R3 : 329 par le nom d'un **bloc imbriqué**, 5 par le calque | 4 | 330 | 72 |

Sur v05, le vocabulaire ne connaît pas le calque espagnol des voiles : les 4
voiles nommés sont perdus et les 25 bandes deviennent des voiles, comme sur
les variantes sans noms. Sur v11, l'explosion fait monter d'un niveau les
blocs d'un modèle d'architecte, dont le nom dit « mur » pour tout mur : 120
« voiles » sans épaisseur (polygones composés), **28 de moins de 80 mm**
(dont 25 de 4 cm), **6 par un nom de POTEAU** (les
deux poteaux préfabriqués allongés du tableau précédent, trois contours
chacun, devenus voiles par R1) ; 75 de ses 82 poutres prennent appui sur un
de ces voiles.

### 1.4 Les feuilles PDF réelles

Deux plans d'étage d'architecte (`GEOMETRIE_PDF.md`). **Relevé d'après la
légende des matériaux de la feuille** (un texte de la feuille, pas un relevé
d'ingénieur) : gris foncé = **béton armé** ; blanc = blocs de plâtre
(**cloisons**) ; bleu, rose, vert hachuré = blocs silico-calcaires ; gris
clair = béton architectonique ; les petites bandes rouges et les bandes brunes
ne sont pas légendées.

| Voiles `0.7.0` par remplissage | Feuille A | Feuille B |
|---|---|---|
| blanc (couleur du papier) : cloisons, **vitrages** des façades (étiquetés comme des baies), mobilier ; hors zone, des éléments de légende | 46 (dont 24 hors zone) | 51 (dont 2 hors zone) |
| brun (lames de terrasse) | 10 | 14 |
| rouge (petites bandes, non légendées) | 0 | 6 |
| motif | 5 (dont 4 hors zone) | 5 (dont 4 hors zone) |
| **gris foncé : béton armé** | 1 (l'échantillon de la légende) | **5** : **4 bandes dans la zone** (3 voiles, l'un dessiné deux fois) + l'échantillon |
| autres couleurs : échantillons de la légende | 4 | 4 |
| **total** | **66** | **85** |
| épaisseurs proposées (98 à 450 mm) | 28 | 46 |

Les vrais voiles en béton de ces feuilles sont surtout des **polygones**
(murs à angles, à baies) : feuille B, 16 remplissages « béton armé » dont 10
polygones, qu'aucune règle de bande ne lit.

### 1.5 Le corpus (94 fichiers)

Ont des voiles en `0.7.0` : les 5 feuilles PDF fabriquées (1 chacune, R2 : le
voile plein de 200 mm sur l'axe 2, entre deux poteaux ; épaisseur bornée par
l'entraxe sur les deux feuilles sans unité) ; `charpente_mm` (1, R1 : une
polyligne fermée VIDE sur `S-WALL`, qui porte une poutre) ; les deux feuilles
réelles ; 15 des 16 copies du plan réel et de ses variantes (v08 n'en a pas).
**71 fichiers n'ont aucun voile**, dont les 36 DXF d'exemple. Les 12 multilignes du corpus (deux
plans N1 fabriqués) sont comptées « non lues ».

### 1.6 Les réponses demandées

| Question | Mesure (`0.7.0`) |
|---|---|
| Voiles trouvés **seulement par un nom** | **Tous les voiles nommés** : le plan réel et ses variantes nommées (4 / 4, R3) ; `charpente_mm` (1, R1) ; v11 (334, R1 et R3). **Aucun n'est dessiné coupé**, sauf sur v11 (219 hachures) ; aucun n'aurait de signature complète (§ 3.2). v05 : 0 — le nom espagnol n'est pas reconnu. |
| Trouvés **parce que des axes existent** | **2** : les feuilles PDF fabriquées sans unité, dont l'épaisseur n'est bornée que par l'entraxe. Ailleurs l'unité est connue et R2 ignore la grille. |
| Trouvés **parce que des poteaux existent** | **6** (v11) : deux poteaux préfabriqués allongés, nommés « poteau », faits voiles par R1. Inversement, un contour pris par un poteau n'est jamais un voile. |
| **Faux voiles après G4** | v01, v04, v05, v13, v14, v15 : 25 hors référence (14 bandes de nature non vérifiée) ; v09 : 20 ; v11 : 330 hors référence ; feuille A : 66, feuille B : 81 hors béton armé (85 − 4). |
| **Murs d'architecte devenus voiles** | feuilles : **97 remplissages blancs** (dont 26 hors zone ; dans la zone, des cloisons en blocs de plâtre selon la légende, des vitrages, du mobilier), 24 lames de terrasse brunes, 6 bandes rouges ; v11 : **329** murs d'un modèle d'architecte nommés par leurs blocs, dont 25 de 4 cm. |
| **Graphisme de cartouche** devenu voile | v09 : les **20 échantillons d'épaisseur de trait** de la légende ; feuilles : **44** éléments hors de la zone structurelle (33 sur A, 11 sur B : échantillons et éléments de la légende). |
| **Géométrie d'annotation** devenue voile | feuilles : les vitrages des façades (bandes blanches au nu des axes : 23 sur B, 8 sur A), les petites bandes rouges non légendées (6). |
| **Erreurs de propositions dues aux voiles** | v01… : **19 épaisseurs hors référence** par variante, et les 4 de 25 perdues ; v09 : **5** (0,13 à 0,57 m) ; v11 : **72** épaisseurs, et ses 82 poutres dont 75 prennent appui sur un voile (105 largeurs, 67 portées, 67 nus, 50 consoles proposés) ; feuilles : **46 + 28** épaisseurs, tirées pour l'essentiel de vitrages, de cloisons et de terrasses (199 mm est l'épaisseur des voiles en béton armé de la feuille B) ; plan réel : 2 des 4 épaisseurs portent le repère d'un massif (valeur juste, repère faux, hors de G5). |

### 1.7 La référence

* **R4** : les 4 voiles du plan réel nommé (`0.7.0`) — ce que le nom donne,
  **incomplet** (§ 1.2). Un voile d'une sortie est apparié s'il est sur l'axe
  d'un voile de R4 (à une demi-épaisseur) sur au moins la moitié de sa longueur
  (v10 : R4 tourné de 30°). Les 14 bandes hachurées et les 330 voiles en plus
  de v11 sont **hors référence, de nature non vérifiée** : ils ne comptent ni
  comme vrais ni comme faux dans le rappel ; ils sont comptés à part.
* **Relevé de légende** (feuilles PDF, § 1.4) : positifs = les 4 bandes
  « béton armé » de la feuille B dans la zone (3 voiles) ; négatifs = toutes
  les autres bandes pleines.
* **Fixtures** : les 5 voiles des feuilles fabriquées, celui de `charpente_mm`,
  les multilignes nommées des plans N1 — vrais par construction.

## 2. Ce qu'il faut distinguer, et ce qui le distingue

| Confusion | Exemple mesuré | Ce qui l'écarte en G5 (niveau, critère) |
|---|---|---|
| **Poteaux** | les 63 préfabriqués ; deux sections de 130 × 30 sur un axe, à un nœud ou tout près | élancement < 4 (N2, V1.1 : la frontière poteau / voile de l'EN 1992-1-1) ; au-delà, pas d'appui à un bout (V1.7) ; un contour pris par un poteau n'est jamais candidat |
| **Pieux, massifs** | 477 pieux, massifs carrés ou de 5 × 2,5 m (v11) | cercles exclus ; massif : pas une bande (V1.1), pas un appui (épaisseur traversée implausible, V1.7) ; une bande sur une file de pieux est dite, pas tranchée (V1.5) |
| **Poutres** | paires de traits du plan réel, bandes provisoires | **pas coupées** (V1.3) : une poutre est vue ; une paire de traits reste partielle (V2) et reste candidate aux bandes de poutre, comme aujourd'hui |
| **Bords de dalle** | — (aucun cas mesuré) | pas coupés ; une plage qui contient la bande n'est pas un appui (V1.7) ; risque 9 |
| **Cloisons d'architecte** | 97 remplissages blancs, feuilles A et B | remplissage de la couleur du papier : pas une coupe (N1, V1.3) ; hors d'un axe (V1.6) ; moins de 80 mm (V1.2) |
| **Lignes de cote** | — | une `DIMENSION` n'est pas un trait ; une cote d'épaisseur n'est qu'une corroboration (§ 3.1) |
| **Graphisme de cartouche** | 20 échantillons (v09), 44 éléments (feuilles) | hors de la zone structurelle (N2, V1.4) ; hors d'un axe (V1.6) |
| **Contours de hachure** | grandes plages remplies (sols, fosses) | pas une bande (V1.1) ; une plage qui contient la bande n'est pas son appui (V1.7) |
| **Géométrie répétée décorative** | 24 lames de terrasse, connectées entre elles | hors d'un axe (V1.6) — l'appui mutuel ne suffit pas |
| **Bouts de voile** | (G4 : 0 cas) | élancement < 4 : pas un voile (V1.1), et pas un poteau (G4, C1.10) ; ils ne prolongent pas le voile (risque 11) |
| **Vitrages, mobilier, petites bandes non légendées** | 31 vitrages au nu d'un axe, 6 bandes rouges | fond de feuille (V1.3) ; hors d'un axe (V1.6) ; sans appui à un bout (V1.7) |
| **Morceau hachuré d'un élément plus long** | la bande de 290 × 30 du plan réel | le prolongement de même largeur n'est pas un appui (V1.7) |

## 3. La signature

### 3.1 N1 — l'information DXF standard

* **Coupé = rempli** : `HATCH` (pleine ou à motif), `SOLID`, polyligne épaisse,
  **ou un contour doublé d'un remplissage de même centre et de même taille
  (5 %), quel que soit son calque** (le jumeau de G4, C1.2). Le nom du motif
  est cité, jamais un critère.
* **Le fond de la feuille n'est pas une coupe** : sur une feuille PDF, un
  remplissage de la couleur du papier (blanc) masque — vitrages, cloisons en
  blocs de plâtre selon la légende, fonds de textes ; il ne dit pas qu'un
  élément est tranché. *(Mesuré : 97 des 151 voiles des deux feuilles.)* Un tel
  remplissage peut en revanche être l'élément qui croise un voile (V1.7).
* **Multiligne (`MLINE`)** : deux faces parallèles données par le dessin
  lui-même (G1, F3) ; épaisseur = écart des décalages du style, à
  l'échelle de l'insertion. **G5 la lit** : elle n'est plus « entité non
  lue ». Nommée voile : un voile (§ 3.4) ; sinon : partielle (V2), comptée.
  Aucune multiligne remplie dans le corpus.
* **Motif de ligne** : un trait en trait-point (axe) ou en tirets (vu) n'est
  jamais une face de voile dans une paire (V2).
* **Cote d'épaisseur** : une `DIMENSION` dont les deux attaches tombent sur les
  deux faces et qui mesure l'épaisseur — corroboration citée, jamais décisive.
  *(Mesuré : 3 sur les voiles nommés, mais aussi sur 5 des 14 bandes hors
  référence : elle ne départage pas.)*
* **Épaisseur de trait** : non lue (le plan réel n'en porte aucune).

### 3.2 N2 — la signature V1 (complète)

Une bande est un voile **V1** si les sept critères sont vrais. Le rappel d'un
critère est la part des voiles coupés de la référence qui le satisfont (9
bandes : les 5 des feuilles fabriquées, les 4 « béton armé » de la feuille B) ;
sa précision, ce qu'il écarte — **mesuré** sur les bandes pleines plausibles
des feuilles réelles (137 négatives), de v09 (20), du plan réel (14 hors
référence par variante) et de v11 (65 hors référence), **attendu** ailleurs.

| # | Critère | Pourquoi | Rappel (mesuré ; attendu) | Précision (mesuré ; attendu) | Modes d'échec |
|---|---|---|---|---|---|
| V1.1 | **Bande** : un rectangle (`rectangle_de`), d'**élancement ≥ 4** | un voile est droit et long ; l'EN 1992-1-1 (§ 5.3.1(7), une définition géométrique, sans paramètre national) appelle voile ce qui dépasse 4 fois son épaisseur, poteau le reste : la borne des poteaux du produit (G4) est la même | 9 / 9 ; R4 4 / 4 (s'ils étaient coupés) ; attendu 90–98 % des voiles droits | écarte les poteaux (sections de 30 × 30 à 30 × 90), les bouts de voile, les massifs, les plages ; attendu : inchangé | voile composé d'un seul polygone (en L, en T, à baies : 10 des 16 « béton armé » de la feuille B), courbe ; rectangle à sommets parasites ; poteau allongé (4 à 5) : passe, écarté par V1.7 |
| V1.2 | **Épaisseur plausible** : 80–600 mm (unité connue) ; sans unité, ≤ 0,1 entraxe ; sans unité ni grille : pas de V1 (refus dit) | règle d'aujourd'hui ; une cloison de 7 cm, une couche de finition ne portent pas | 9 / 9 ; R4 4 / 4 ; attendu 95–99 % | rien de plus sur les bandes mesurées (déjà bornées par R2) ; v11 : 27 des 28 voiles nommés de moins de 80 mm (§ 3.4 ; le 28ᵉ, une paire de 79,0 mm, passe la tolérance d'appariement) ; attendu : cloisons minces | unité fausse (v08, v09) ; voile de soutènement de plus de 600 mm : refusé, dit |
| V1.3 | **Coupée** (N1, § 3.1) : remplie, ou doublée d'un remplissage — **qui n'est pas le fond de la feuille** | un voile en plan est tranché par le plan de coupe ; un élément vu ou masqué ne l'est pas | 9 / 9 des voiles coupés ; **0 / 4 de R4 et 0 / 1 de `charpente_mm`, dessinés VIDES** : ce sont les voiles qui restent au nom (§ 3.6) ; attendu 60–90 % des voiles d'un plan de coffrage | **écarte 87 des 137 bandes négatives des feuilles** (le blanc) ; attendu : les vitrages et cloisons des plans d'architecte | **voile dessiné vide (R4)** ; voile structurel peint en blanc sur une feuille ; remplissage fortuit sous un symbole |
| V1.4 | **Dans la zone structurelle** (G2 ; à défaut, les axes étiquetés élargis d'un entraxe ; sans axe, non applicable, dit) | le cartouche, la légende, les détails ne sont pas le bâtiment | 9 / 9 ; attendu ≈ 100 % | **écarte les 20 échantillons de v09 et 18 éléments des feuilles** (après V1.3) ; v11 : 5 ; attendu : idem | un détail muni de sa propre grille ; zone sous-estimée |
| V1.5 | **Pas sur des pieux** : aucun centre de pieu (G3) dans la bande | une longrine ou une paroi de pieux est une plage longue sur une file de pieux : dite, pas tranchée (§ 6.2 du plan) | 9 / 9 ; attendu ≈ 100 % hors fondations | **0 cas mesuré** ; attendu : les longrines sur pieux | un vrai voile de fondation posé sur une file de pieux : perdu (candidat) |
| V1.6 | **Sur un axe** : un axe de la grille parallèle (1°) à au plus une épaisseur de l'axe de la bande, sur au moins la moitié de sa longueur (centrée, au nu, ou proche) | un voile porteur est dans la trame (§ 6.1 du plan : centré ou à nu d'axe) ; une cloison, une lame de terrasse, un radiateur n'y sont pas | **8 / 9** (la 9ᵉ : un voile de 7,3 m de la feuille B, hors axe) ; R4 4 / 4 ; attendu 70–90 % | **écarte les 32 dernières bandes négatives des feuilles** (brunes, rouges, motif) et **11 des 14 bandes du plan réel** ; v11 : 44 de 60 ; attendu : l'essentiel de la précision avec V1.7 | voile hors trame (noyau, mur de refend décalé) : perdu ; axe non trouvé (G2) ; grille partielle |
| V1.7 | **Butée à un bout** : le point situé quatre tolérances au-delà d'un bout, SUR l'axe de la bande, est (à deux tolérances près) dans un **poteau** (G4), ou dans un **élément plein qui la croise** — de n'importe quelle couleur, fond de feuille compris : une bande de biais (≥ 30°, élancement ≥ 2) d'épaisseur plausible, ou un autre contour plein qui déborde la bande sur le côté (à une épaisseur de son axe) et que l'axe de la bande traverse en moins de l'épaisseur maximale d'un voile (600 mm ; sans unité, 0,1 entraxe) ; ni la bande elle-même ou son jumeau, ni une plage qui contient son centre, ni son prolongement de même largeur | un voile porte et se contrevente : il rencontre un poteau ou un autre mur ; une bande isolée sur un axe — un poteau allongé à un nœud, le morceau hachuré d'une bande — n'est pas un voile | **8 / 9** (5 par un poteau, 3 par un mur qui les croise ; la 9ᵉ est la même que V1.6) ; R4 2 / 4 (les deux en L) ; attendu 85–95 % | **écarte les 3 bandes du plan réel posées sur un axe** (les deux poteaux allongés, le morceau de bande) ; v11 : 10 de 16 ; attendu : bandes isolées, symboles | voile qui s'arrête sur une baie, voile libre ; mur qui le croise dessiné vide ou en polygone sans débord ; élément plein non porteur d'épaisseur de mur (relevé, bord de dalle) pris pour appui |

**V1 complète** (les sept) : **précision 8 / 8 = 1,000** sur ce qui est
étiqueté (aucune des 157 bandes négatives) ; **rappel 8 / 9 = 0,889** des
bandes coupées de la référence (7 / 8 voiles distincts). Hors référence : **0
des 14 bandes du plan réel**, sur toutes ses variantes ; 6 des 65 de v11 (des
voiles nommés, confirmés).

**Entonnoir** (critères appliqués dans l'ordre, groupes de jumeaux) :

| Bandes pleines plausibles | Départ | Coupée | Zone | Pas de pieux | Sur un axe | Butée |
|---|---|---|---|---|---|---|
| référence coupée (+) | 9 | 9 | 9 | 9 | **8** | **8** |
| négatives des feuilles réelles (−) | 137 | 50 | 32 | 32 | **0** | 0 |
| échantillons de légende de v09 (−) | 20 | 20 | **0** | 0 | 0 | 0 |
| plan réel, par variante (hors réf.) | 14 | 14 | 14 | 14 | 3 | **0** |
| v11 (hors réf.) | 65 | 65 | 60 | 60 | 16 | 6 |

**Pourquoi « sur un axe ET butée », et pas « au moins un lien » comme au § 6.2
du plan.** Le plan proposait : rempli, allongé, plausible, et **au moins un**
de : un axe, une jonction, une épaisseur type (classe d'au moins 3), une
épaisseur cotée. **Mesuré**, cette règle garde **les 14 bandes du plan réel**
(leurs épaisseurs de 15, 20 et 30 cm font chacune une classe) et 27 des 32
bandes négatives des feuilles qui passent la zone : elle ne retirerait aucun
faux voile des variantes sans noms. Chaque critère seul laisse passer : l'axe,
3 bandes du plan réel (les deux poteaux allongés, le morceau de bande) — et,
sans le critère du fond, les 31 vitrages au nu d'un axe ; l'appui, 8 bandes du
plan réel (celles qui se croisent en T) et 20 des 32 bandes négatives des
feuilles (lames de terrasse, motifs) ; leur **conjonction** n'en laisse passer
aucune, et garde 8 des 9 voiles de la référence.

**Corroborations citées, jamais décisives** : une cote d'épaisseur (§ 3.1) ;
l'épaisseur type (classe de bandes de même épaisseur).

### 3.3 N2 — la signature V2 (partielle)

* **Paire de traits** : deux traits continus parallèles (ni trait-point, ni
  tirets, ni sur une droite d'axe de G2), écart plausible, recouvrement d'au
  moins 2 écarts, appariés mutuellement (`appariement.py`), **sur n'importe quel
  calque** ;
* **contour vide en bande** (rectangle d'élancement ≥ 4, plausible) sans jumeau
  rempli ;
* **multiligne** non remplie.

**V2 ne décide pas.** Une poutre vue (dessin de coffrage), une semelle filante,
une longrine et un voile non hachuré se dessinent de la même façon ; le
produit traite déjà les paires sans nom comme des **bandes de poutre
provisoires** (`poutres.py`) : en faire des voiles leur volerait leurs
poutres. *(Mesuré sur le plan réel et ses variantes sans noms : 71 paires
plausibles dans la zone, dont les 4 de R4 ; 18 sur un axe, dont les 4 ; 13 sur
un axe et touchant quelque chose à un bout, dont 2. Une paire sur un axe est un
voile de R4 une fois sur 4,5.)*

**Complétions en G5** : un **nom de voile** (R3 et R1 d'aujourd'hui, et les
multilignes nommées, § 3.4). Une hachure entre les deux traits en fait une
bande coupée : c'est alors la hachure, V1, qui décide. Les partitions apprises
(au moins 3 voiles V1 sur un calque) complèteront en G6, et les paires
partielles y seront exportées comme candidats.

### 3.4 N3 — les noms

* **Nom de voile + V2** (paire de traits, contour vide, multiligne) : voile,
  **comme aujourd'hui**, 0,8 — les 4 voiles du plan réel, celui de
  `charpente_mm`.
* **Nom de voile + V1 complète** : **confirmé**, `geometrie`, le nom cité,
  **0,90** (v11 : 6).
* **Nom de voile, forme composée** (un polygone qui n'est pas un rectangle) :
  voile sans épaisseur, comme aujourd'hui (v11 : 120) ; rien n'en est proposé.
* **Nouveau — plausibilité** : un rectangle d'un calque ou d'un bloc de voile
  dont l'épaisseur n'est pas plausible (unité ou grille connue) n'est **pas un
  voile** : doute dit (`unresolved`), comme un contour de poteau hors des
  dimensions plausibles (G4). *(Mesuré : v11, 27 — des couches de 4 à 7,7 cm ;
  ailleurs, 0.)* Une paire nommée garde la tolérance d'appariement d'aujourd'hui
  (1 mm : une paire de 79,0 mm reste sur v11).
* **Nouveau — un nom de poteau ne fait plus un voile** : un contour d'un calque
  ou d'un bloc de **poteau**, trop allongé pour un poteau (élancement > 4), est
  un voile seulement si V1 est complète — avec le conflit dit (le nom dit
  poteau, cas 5, 0,4) ; sinon c'est un **doute** : ni poteau (G4 l'écarte), ni
  voile. *(Mesuré : v11, 6 contours — les deux poteaux préfabriqués allongés,
  repérés comme poteaux sur le plan ; ailleurs, 0.)*
* **Nouveau — multiligne nommée** : une multiligne d'un calque ou d'un bloc de
  voile, d'épaisseur plausible, est un voile (0,8), chaque segment un voile,
  le critère `multiligne` cité. *(Mesuré : les deux plans N1 fabriqués, 3 et
  1.)*
* **Cas 5** : V1 complète sur un contour nommé d'un autre rôle (texte, cadre,
  fondation…) : voile à 0,4, conflit dit. Le nom qui compte est celui du
  contour de la bande ; une bande dessinée par sa seule hachure prend le nom
  de la hachure. *(Mesuré : 0 cas.)*
* **Vocabulaire** : inchangé. Le calque espagnol des voiles de v05 n'est pas
  reconnu (§ 3.6).

### 3.5 L'échelle de preuves, pour les voiles

| Cas | Décision | `classified_by` | Confiance |
|---|---|---|---|
| 1. V1 complète, contour nommé voile | voile | `geometrie` (nom cité) | **0,90** |
| 1'. V1 complète, contour sans rôle (`inconnu`, `hachure`) | voile | `geometrie` | **0,85** |
| 2. V2 + nom de voile (paire, contour vide, multiligne) ; 4. nom de voile, forme composée | voile, comme aujourd'hui | la règle du nom | 0,8 |
| 4'. Nom de voile, épaisseur implausible | doute, pas de voile | — | — |
| 5. V1 complète, contour nommé d'un **autre** rôle (poteau allongé compris) | voile, **conflit dit** | `geometrie` | **≤ 0,4** |
| 5'. Nom de poteau, allongé, V1 partielle | doute (ni poteau, ni voile) | — | — |
| 6. Partielle seule (bande hors axe ou sans appui, paire, multiligne sans nom) | rien (candidat : G6), comptée | — | — |

**Pourquoi 0,85** : comme G2, G3 et G4, une signature complète vaut un nom ;
R2 (0,55) prenait toute bande pleine. Les confiances restent indicatives et
non calibrées (§ 8 du plan). Les propositions suivent, inchangées dans leur
règle : un groupe de voiles de même repère et même épaisseur propose son
épaisseur à la plus faible confiance du groupe.

### 3.6 Les dépendances aux noms qui restent

| Dépendance | Mesuré | Pourquoi la géométrie ne suffit pas | Ce qui la lèverait |
|---|---|---|---|
| **Voiles dessinés vides** (paires de traits, contours vides) | les 4 du plan réel, `charpente_mm` | une poutre vue, une semelle, une longrine se dessinent pareil (§ 3.3) ; aucune épaisseur de trait | partitions apprises (G6), candidats montrés à la revue ; un relevé d'ingénieur sur des plans de coffrage |
| **Voiles d'un seul polygone** (en L, en T, à baies, courbes) | v11 : 120 ; feuille B : 10 polygones « béton armé » | V1 exige une bande droite | décomposition des polygones en bandes (hors G5) |
| **Sans grille** | aucun cas dans le corpus | V1.6 exige un axe | une grille implicite de voiles (à concevoir) |
| **Multilignes** | 4 (plans N1) | deux faces, aucune coupe | multiligne de style rempli : V1 (aucune mesurée) |
| **Vocabulaire** | v05 : les 4 voiles perdus | — | un nom ne fait que compléter : un vocabulaire plus large ne change que les voiles vides |
| **Noms trompeurs** | v11 : **290 voiles par le nom d'un bloc** d'un modèle d'architecte (cloisons, doublages) | la règle du nom est gardée (non-régression, cas 2 et 4) ; seuls l'épaisseur implausible et le nom de poteau sont écartés | partitions apprises et désaccords (G6) |

## 4. Pipeline et ordre d'évaluation

```
axes (G2) ─► zone (G2) ─► formes fermées ─► pieux (G3) ─► poteaux (G4)
   ─► voiles :
        jumeaux : une bande et son remplissage (même centre, même taille) n'en font qu'une
        pour chaque bande pleine (ou doublée) —
          nommée voile ─► plausible ? sinon doute ─► V1 ? confirmée (0,90) : règle du nom (0,8)
          nommée poteau, allongée ─► V1 ? voile, conflit (0,4) : doute
          d'un autre rôle ─► V1 ? voile, conflit (0,4) : ignorée, comptée si plausible
          sans rôle ─► élancement, épaisseur, coupe (fond de feuille), zone, pieux,
                       axe, appui ─► V1 : voile (0,85) ; sinon comptée par raison
        contours nommés voile non rectangles ─► voile sans épaisseur (comme aujourd'hui)
        paires de traits d'un calque de voile ─► voile (comme aujourd'hui)
        multilignes ─► nommées voile : voiles ; sinon comptées
   ─► bandes, graphe, cotes, repères, dalles (inchangés)
```

**Compte rendu.** `report.walls` (`by_rule`, `structural_zone`) et
`report.wall_candidates_rejected` — `fond_de_feuille`, `hors_zone`,
`file_de_pieux`, `sans_grille`, `hors_axe`, `sans_appui`,
`epaisseur_implausible`, `poteau_allonge`, `multiligne_partielle` — présents
dès que le dessin a un voile ou une bande pleine plausible écartée. Une bande
comptée l'est une fois, jumeaux compris, **quel que soit le nom de son
calque** (les variantes nommées et anonymes comptent pareil). Les doutes
(épaisseur implausible, poteau allongé) et les conflits vont dans
`unresolved`.

**Coût.** Un index des remplissages (jumeaux, appuis), un des poteaux, un des
pieux ; la grille et la zone sont déjà calculées. Prototype non optimisé :
détection des voiles 0,05 → 0,5 s sur le plan réel (extraction 9,2 → 9,6 s,
en processus) ; cible : ≤ + 5 % de bout en bout (A10).

## 5. Attendu : avant / après

Mesuré par le prototype, de bout en bout, sur l'export gelé de `805ff7e`.

### 5.1 Le plan réel et ses variantes

| Variante | Voiles `0.7.0` → G5 | Dans R4 | Hors R4 | Précision | Rappel | Épaisseurs proposées | Propositions |
|---|---|---|---|---|---|---|---|
| **plan réel** | 4 → **4** (identiques) | 4 | 0 | 1,000 | 1,000 | 4 → 4 (identiques) | 334 → **334** (identiques) |
| v00, v02, v03, v06, v07, v10, v12 | 4 → 4 (identiques) | 4 | 0 | 1,000 | 1,000 | identiques | identiques |
| **v01** calques neutres | 25 → **0** | 0 | 25 → **0** | 0 → — | 0 → 0 | 19 → **0** | 347 → 328 |
| **v04** aucune convention | 25 → **0** | 0 | 25 → **0** | 0 → — | 0 → 0 | 19 → **0** | 338 → 319 |
| v05 calques espagnols | 25 → 0 | 0 | 25 → 0 | 0 → — | 0 → 0 | 19 → 0 | 346 → 327 |
| **v13** noms neutres, types gardés | 25 → **0** | 0 | 25 → **0** | 0 → — | 0 → 0 | 19 → **0** | 346 → 327 |
| **v14** tout renommé | 25 → **0** | 0 | 25 → **0** | 0 → — | 0 → 0 | 19 → **0** | 343 → 324 |
| **v15** tout sur `0` | 25 → **0** | 0 | 25 → **0** | 0 → — | 0 → 0 | 19 → **0** | 340 → 321 |
| v08 (unité mm, fausse) | 0 → 0 | 0 | 0 | — | 0 | 0 | identiques |
| v09 (unité m, fausse) | 20 → **0** | 0 | 20 → 0 | 0 → — | 0 | 5 → 0 | 327 → 322 |
| v11 (blocs explosés) | 334 → **301** | 4 | 330 → 297 | 0,012 → 0,013 | 1,000 | 72 → 65 | 733 → 720 |

« — » : aucun voile, donc aucun faux. **Sur les six variantes sans noms, G5
retire tous les voiles hors référence et toutes leurs épaisseurs ; il ne
retrouve pas les 4 voiles nommés** (dessinés vides : § 3.6) — le rappel reste
celui d'aujourd'hui, 0. Seules autres sorties qui bougent sur ces variantes :
18 repères ne sont plus affectés (ceux que prenaient les bandes, dont trois
repères de poteaux et trois de poutres) et, sur v01, v05, v13 et v15, une bande
candidate de poutre de plus est écartée (deux morceaux qu'un voile retiré
reliait). Aucune autre proposition ne change (grille, entraxes, poteaux,
cotes : identiques, confiances comprises).

**v11** : 27 voiles nommés de 4 à 7,7 cm et les 6 contours de poteaux allongés
deviennent des doutes (33) ; 6 voiles nommés sont confirmés par V1 (0,90). En
aval, des poutres perdent un appui (65 travées au lieu de 67) ; **23
propositions retirées** — 7 épaisseurs implausibles, celle du poteau allongé
(30), une épaisseur dont le repère change, 14 propositions de poutre — et **10
ajoutées** : 2 épaisseurs aux repères réaffectés, 8 propositions de poutre.

### 5.2 Les feuilles PDF

| | Feuille A | Feuille B |
|---|---|---|
| voiles | 66 → **0** | 85 → **3** (les trois bandes « béton armé » sur un axe et butées) |
| écartées : fond de feuille / hors zone / hors axe / sans appui | 36 / 9 / 11 / 0 | 51 / 9 / 22 / 0 |
| épaisseurs proposées | 28 → **0** | 46 → **1** (199 mm, 0,55 → 0,85) |
| précision (relevé de légende) | 0 / 66 → — | 4 / 85 → **3 / 3** |
| rappel des bandes « béton armé » | — | 4 / 4 → 3 / 4 |

Contre l'estimation du plan (§ 6.3 : précision 60–75 %, rappel 60–80 % sur un
plan d'architecte) : la précision mesurée est meilleure (1,000), le rappel
moindre — 3 des 4 bandes « béton armé », mais **3 des 16 remplissages « béton
armé »** de la feuille, presque tous des polygones (§ 3.6).

Les cinq feuilles fabriquées gardent leur voile (`geometrie`, appui sur les
poteaux) ; leur épaisseur proposée garde sa valeur, sa confiance passe de
0,55 à 0,85 (de 0,35 à 0,65 sur les deux feuilles sans unité).

### 5.3 Les propositions

* **Plan réel nommé** : 334 → 334, **identiques** (valeur, unité, repère,
  confiance, texte) ; de même sur ses 7 variantes nommées.
* **`wall_thickness` hors référence** : v01, v04, v05, v13, v14, v15 :
  19 → 0 chacune ; v09 : 5 → 0 ; feuille A : 28 → 0 ; feuille B : 46 → 1 ;
  v11 : 72 → 65.
* **Nouvelles** : 2 (`wall_thickness` des multilignes nommées des plans N1).
* Aucune proposition de grille, de poteau ou de cote ne change ailleurs que
  sur v11.

### 5.4 Le corpus (94 fichiers)

* **69 fichiers identiques** à `0.7.0` (la version mise à part) : aucun voile,
  aucune bande pleine plausible.
* **10 ne changent que par le compte rendu** (`report.walls`,
  `report.wall_candidates_rejected`) : les 9 copies nommées du plan réel
  (`hors_axe` 11, `sans_appui` 3) et `charpente_mm`.
* **15 voient leurs voiles changer**, tous prévus ici : les 5 feuilles
  fabriquées (règle et confiance) ; les 2 feuilles réelles ; les 4 copies de
  variantes sans noms (v01, v04, v05, v13) ; v09 ; v11 ; les 2 plans N1
  (multilignes nommées : + 3 et + 1 voiles, et le compte « entité non lue :
  MLINE » qui disparaît).

### 5.5 Estimation demandée

| Dessin | Voiles G5 | Précision | Rappel | Ce qui reste dépendant des noms |
|---|---|---|---|---|
| **plan réel** | 4 (R4, par le nom) | 1,000 contre R4 | 1,000 contre R4 ; **inconnu contre le dessin** (34 repères V…) | les 4 : vides |
| **v01, v04, v13, v14, v15** | 0 | — (0 faux) | 0 contre R4 | les 4 de R4, perdus comme aujourd'hui |
| **corpus** | 36 (R4 × 9 copies) + 1 + 5 + 3 + 4 + 301 (v11) | hors v11 : 49 / 49 ; v11 : 4 dans R4, 297 hors référence | fixtures : 100 % ; feuille B : 3 / 4 bandes « béton armé » | les voiles vides, les polygones, v11 |
| autre bureau, plan de coffrage à voiles hachurés sur la trame | — | **attendu 90–98 %** | **attendu 60–85 %** | les voiles vides, hors trame, libres |
| plan d'architecte (feuille PDF) | — | attendu 85–100 % | attendu 15–40 % | polygones, voiles hors trame |

## 6. Critères d'acceptation

| # | Critère | Seuil |
|---|---|---|
| A1 | Plan réel : les 4 voiles identiques à `0.7.0` (identifiant, contour, axe, épaisseur, longueur, confiance, preuve, repère) ; **334 propositions identiques** ; axes, pieux, poteaux, poutres, dalles identiques ; aucun voile ajouté | exact |
| A2 | Variantes nommées (v00, v02, v03, v06, v07, v10, v12) : comme A1 | exact |
| A3 | v01, v04, v05, v13, v14, v15 : **0 voile**, **0 `wall_thickness`** ; aucune autre proposition ne change | exact |
| A4 | v09 : 0 voile, 0 `wall_thickness` ; v08 : inchangé | exact |
| A5 | v11 : aucun voile nommé de moins de 80 mm (hors tolérance d'appariement) ; les 6 contours de poteaux allongés sont des doutes ; 301 voiles ; chaque changement d'aval listé | exact, listé |
| A6 | Feuilles réelles : A 0 voile ; B 3 voiles, tous « béton armé » selon la légende ; épaisseurs 28 → 0 et 46 → 1 | exact |
| A7 | Corpus : seuls changent les 25 fichiers du § 5.4 (15 par leurs voiles, 10 par le compte rendu) | exact, listé |
| A8 | Fixtures du § 7 : chacune donne l'issue écrite | toutes |
| A9 | Suites d'extraction et d'API, harnais des documents, `export_contracts.py --check` ; les tests d'invariance de G1–G4 passent **sans modification**, sauf les trois tests G1 dont la prémisse expire à G5 (« aucun détecteur ne lit les multilignes avant G5 », § 9) | verts |
| A10 | Coût sur le plan réel, de bout en bout | ≤ + 5 % |

## 7. Plan de validation

**Fixtures** (`fabrique_geometrie`, `fabrique_pdf_vectoriel`), une par
confusion du § 2 :

* voiles hachurés sur calque `0`, en L et en T sur la trame, butés sur des
  poteaux (V1, 0,85) ; les mêmes sur un calque `VOILES` (0,90, mêmes
  identifiants) ; leurs hachures sur un calque « texte », le contour sur `0`
  (jumeau : toujours des voiles, aucun conflit) ;
* un voile hachuré hors trame, un voile libre sur un axe : aucun voile
  (`hors_axe`, `sans_appui`) ;
* un poteau allongé (130 × 30) à un nœud, plein : aucun voile, aucun poteau ;
  le même sur un calque `POTEAUX` : un doute ;
* le morceau hachuré d'une bande vide plus longue : aucun voile ;
* une cloison hachurée de 70 mm sur un axe : aucun voile ;
* une poutre en tirets entre deux poteaux : une poutre, pas un voile ;
* une bande hachurée sur une file de pieux : aucun voile (`file_de_pieux`) ;
* une légende d'échantillons hachurés hors de la grille : `hors_zone` ;
* une bande dans une grande plage hachurée : la plage n'est pas un appui ;
* un voile vide (deux traits) sur un calque `VOILES` : voile, 0,8, comme
  aujourd'hui ; le même sur `0` : rien ;
* une multiligne sur `VOILES` : voile, `multiligne` cité ; sur `0` :
  `multiligne_partielle` ; plus aucune « entité non lue » ;
* un contour de `VOILES` de 40 mm : un doute ;
* sans grille : des voiles hachurés ne sont pas des voiles (`sans_grille`) ;
  nommés, ils le restent ;
* la feuille PDF fabriquée : son voile reste (V1, appui sur les poteaux) ; des
  bandes **blanches** sur les axes, butées : aucun voile (`fond_de_feuille`) ;
* l'invariance (K1 de G5) : sur `charpente_mm`, sur les feuilles fabriquées et
  sur un plan nommé, la signature désactivée puis activée — chaque voile nommé
  garde son identifiant, son contour, son axe, son épaisseur, sa longueur et
  son repère ; seules la règle, la confiance et les critères cités changent.

**Mesures** : le plan réel et ses 16 variantes (§ 5.1), voiles ajoutés et
retirés un à un, précision et rappel contre R4 ; les deux feuilles contre le
relevé de légende ; les propositions (catégorie, valeur, repère, confiance) ;
le balayage des 94 fichiers, chaque changement classé.

**Campagne** : comme G4 — conception commitée, code commité sur l'arbre
mesuré (empreinte vérifiée), balayage et variantes refaits sur le commit et
comparés octet pour octet au prototype et à `0.7.0`, suites, contrat et harnais
sur l'arbre gelé, résultats écrits ici (§ 10).

## 8. Risques

1. **Voiles dessinés vides** : sans nom, aucun (R4 sur les variantes sans
   noms). C'est la limite principale de G5, assumée : la géométrie seule ne
   sépare pas un voile vide d'une poutre vue (§ 3.3).
2. **Voiles hors trame** (noyaux décalés, refends hors axe) et **voiles
   libres** (sans poteau ni mur à leurs bouts) : perdus. Mesuré : 1 des 4
   bandes « béton armé » de la feuille B.
3. **Voiles composés ou courbes** : hors de V1 ; sur les plans d'architecte, la
   plupart (feuille B : 10 polygones « béton armé » sur 16).
4. **Poteaux allongés** (élancement 4 à 5) : ni poteaux (G4), ni voiles (G5) :
   doutes s'ils sont nommés poteau, rien sinon. Mesuré : 2 sur le plan réel ;
   aucun modèle ne les porte.
5. **Les 14 bandes du plan réel** : certaines sont peut-être de vrais voiles
   (repères V… voisins) ; G5 ne les ajoute pas ; la revue ne les verra qu'en
   G6 (candidats).
6. **Noms trompeurs** (v11) : 290 voiles par le nom d'un bloc d'architecte
   restent, et leurs poutres ; G5 n'écarte que l'implausible et le poteau.
7. **Remplissage blanc** : sur une feuille, un voile structurel peint en blanc
   n'est pas coupé (perdu) ; en DXF, la règle ne s'applique pas.
8. **Cas 5 sur des calques de motifs** : la convention AIA range les calques de
   hachures (`…-PATT`) en « texte » ; une bande dessinée par sa seule hachure
   sur un tel calque, V1 complète, est un voile à 0,4 avec conflit. Mesuré :
   0 (les bandes de v07 n'ont pas V1).
9. **Faux appuis** : un élément plein d'épaisseur de mur qui n'est pas porteur
   (relevé, bord de dalle hachuré, appui de fenêtre) au bout d'une bande sur un
   axe en fait un voile.
10. **Doublons** : une même paroi dessinée deux fois, de longueurs différentes,
    donne deux voiles qui se recouvrent (feuille B : 1 cas, une seule
    proposition).
11. **Bouts de voile** : non fusionnés au voile qu'ils terminent ; ils ne sont
    ni voiles ni poteaux.
12. **Unité fausse** (v08, v09) : épaisseurs fausses ; seule la zone écarte la
    légende de v09.
13. **Confiance** : 0,55 → 0,85 pour les voiles V1, non calibrée.
14. **Repères** : un repère qu'un voile retiré prenait reste libre (v01 : 18) ;
    sur v11, deux sont réaffectés à d'autres voiles.

## 9. Impact de migration

* **Base de données : aucune migration.** Le modèle structurel est un JSON ;
  `classified_by = "geometrie"` existe ; les critères (`evidence.signature` :
  `bande`, `coupe`, `sur_axe`, `appui_poteau`, `appui_jonction`, `zone`,
  `multiligne`), le compte rendu (`report.walls`,
  `report.wall_candidates_rejected`) et les doutes (`unresolved`) sont des
  valeurs libres.
* **Contrat** : aucune forme nouvelle ; les descriptions de `classified_by`
  (« voile : bande coupée sur un axe, butée ») et de `signature` citent les
  critères des voiles ; contrat régénéré ; étiquette de l'écran
  (`web/lib/documents.ts`) étendue.
* **Lecture** : les multilignes ne sont plus comptées « entité non lue » (le
  compte disparaît des plans N1) ; une multiligne illisible le reste.
* **Tests existants mis à jour par conception** : les trois tests G1 qui
  vérifient que « rien ne lit les multilignes » (le compte « non lue », aucune
  preuve qui cite une multiligne, la neutralisation des multilignes sans effet)
  — leur prémisse, écrite « avant G5 », expire ; ils deviendront : une
  multiligne nommée voile est lue et citée ; une multiligne illisible reste
  « non lue » et ne fait rien.
* **Version `0.8.0`** : des voiles et des propositions changent.
* **Documents déjà analysés** : leurs extractions restent en `0.7.0`, avec leurs
  décisions ; seules les nouvelles analyses passent par G5. Une décision prise
  sur une épaisseur retirée reste attachée à l'extraction qui l'a proposée.
* **Écran, API, calcul** : inchangés ; le pré-remplissage reçoit moins
  d'épaisseurs de voile fausses.
* **Aval** : un voile retiré n'est plus un appui de poutre, de dalle ni
  d'attache de cote ; mesuré : aucun effet hors de v11 (65 travées au lieu de
  67 ; 14 propositions de poutre retirées, 8 ajoutées) et des variantes sans
  noms (une bande candidate de poutre de plus écartée).

## 10. Contre-mesure avant le code : ce que G5 retire, voile par voile

> Demandée avant l'implémentation : classer chaque voile `0.7.0` que G5
> retire — certainement faux, probablement faux, incertain, probablement
> réel —, dire pourquoi il est retiré, par quel critère, et si un ingénieur
> structure y verrait un voile ; vérifier que G5 ne retire pas de vrais voiles
> seulement parce qu'ils ne sont pas sur un axe ou ne touchent pas un poteau.
> **Résultat : la vérification échoue** (§ 10.6).

### 10.1 Méthode

* **Voile par voile** : les sorties `0.7.0` (export gelé) contre celles du
  prototype final (celles du § 5) ; chaque voile retiré est rapproché de son
  entrée d'audit, où les neuf critères sont évalués indépendamment. Le critère
  cité est le premier qui manque ; tous ceux qui manquent sont donnés.
* **Chaque voile retiré est regardé dans son contexte**, sur un rendu fidèle
  du DXF (hachures, couleurs, textes, cotes) ou de la feuille PDF, fait hors
  du dépôt. Sa nature est lue sur le dessin lui-même : repère de voile, cote
  d'épaisseur, flèche de repère d'élévation, hachure identique à celle des
  voiles voisins, légende des matériaux des feuilles. C'est le relevé d'un
  lecteur du dessin, pas celui de l'ingénieur du projet ; les catégories le
  disent.
* **Catégories.** *Certainement faux* : ce n'est pas un mur (baie, vantail,
  lame de platelage, échantillon de légende, mobilier). *Probablement faux* :
  un élément réel qui n'est pas un voile structurel (cloison non porteuse selon
  la légende, poteau repéré comme tel). *Incertain* : le dessin seul ne permet
  pas de trancher. *Probablement réel* : le dessin le donne pour un voile
  (repère de voile, épaisseur cotée, hachure de coupe des voiles voisins, ou
  « béton armé » de la légende).
* **Plan réel nommé** : G5 n'y retire rien ; ses 4 voiles restent identiques.

### 10.2 Variantes sans noms — 25 voiles retirés sur chacune

Les mêmes 25 sur v01, v04, v05, v13, v14 et v15 (identifiants, contours et
critères identiques).

| Catégorie | Contours (voiles) | Ce que c'est | Retiré par | Un ingénieur y verrait un voile ? |
|---|---|---|---|---|
| probablement réel | 6 (3) | les **voiles intérieurs de trois noyaux d'ascenseur** (VA2a, VB2a, VC3a) : bande de 20 cm (épaisseur cotée), hachurée comme les voiles du noyau, d'un voile du noyau à l'autre, repérée et munie de sa flèche d'élévation ; chacun dessiné deux fois (remplissage et motif) | **V1.6 seul** (hors axe) ; butés aux deux bouts | oui |
| probablement réel | 4 (2) | les **trumeaux** des voiles VA5 et VB5 entre deux baies (20 × 100 et 20 × 112,5) : des morceaux du voile du noyau, même hachure | V1.6 et V1.7 (les bouts donnent sur des baies) | oui : le voile du noyau, interrompu par les portes |
| probablement réel | 2 (1) | le **voile VO1** (30 × 238, épaisseur et longueur cotées), dans le prolongement d'un poteau préfabriqué que G4 ne voit pas | V1.6 et V1.7 | oui |
| probablement réel | 2 (1) | le **tronçon droit de 290 cm du voile de rampe VL1** (30 cm coté), qui continue droit puis courbe (le reste n'est pas une bande) | **V1.7 seul** : il est sur un axe ; ses bouts sont son propre prolongement | oui, mais l'objet n'en est qu'un morceau |
| incertain | 7 | des **secondes hachures de 30 cm** (une pièce, ou deux ou quatre morceaux de 15 cm) superposées aux trois voiles intérieurs, décalées de 10 cm : le voile à un autre niveau, ou un doublon de dessin | V1.6 seul | la zone est un voile ; ces objets, non : ils doubleraient trois voiles avec une épaisseur fausse |
| probablement faux | 4 (2) | les **poteaux préfabriqués** repérés C03…, de 130 × 30 (élancement 4,33), seuls dans un massif, à un nœud | **V1.7 seul** | non : des poteaux de section allongée (au-delà de la limite poteau de l'EN 1992-1-1, § 5.3.1(7)) ; ils ne sont ni poteaux (G4) ni voiles |
| certainement faux | 0 | — | — | — |

**14 des 25 sont probablement réels (7 voiles)**, 7 incertains, 4 probablement
faux, aucun certainement faux ; tous ne doivent leur retrait qu'à V1.6 et à
V1.7. Sur le plan réel et ses variantes nommées, les mêmes bandes sont
candidates et rejetées pour les mêmes raisons (elles n'y étaient pas des
voiles en `0.7.0` non plus : leurs calques disent « hachure »).

### 10.3 v11 — 33 voiles retirés

| Catégorie | Contours | Ce que c'est | Retiré par | Un ingénieur y verrait un voile ? |
|---|---|---|---|---|
| certainement faux | 27 | 25 **vantaux de porte** (4 × 98 cm, arc d'ouverture, porte de 98 cm) ; un élément de 7,7 cm dans une baie de porte ; un élément de 4,5 cm le long d'un escalier | la plausibilité des voiles nommés (80–600 mm, N3) : mis en doute | non |
| probablement faux | 6 | les deux **poteaux préfabriqués** de 130 × 30, trois contours chacun, nommés poteau | « poteau allongé » : V1 partielle, **V1.7** manque ; mis en doute, « ni poteau ni voile » | non : des poteaux |

Aucun incertain, aucun probablement réel.

### 10.4 Feuille A — 66 voiles retirés

| Catégorie | Contours | Ce que c'est | Retiré par | Un ingénieur y verrait un voile ? |
|---|---|---|---|---|
| certainement faux | 33 | hors de la zone : 10 échantillons de la légende des matériaux, 21 lames d'une toiture-terrasse, une case du cartouche, un cadre d'annotation de surface | V1.4 (et V1.3 pour les blancs) | non |
| certainement faux | 13 | **baies de fenêtre** (remplissage blanc, menuiserie repérée, allège et hauteur) | V1.3 (fond de feuille) ; V1.7 aussi pour 12, V1.6 pour 2 | non : l'absence de mur |
| certainement faux | 10 | **lames de platelage** d'un balcon (brun) | **V1.6 seul** | non |
| certainement faux | 1 | une **bande d'isolant** (motif de la légende) devant un trumeau | **V1.6 seul** | non |
| certainement faux | 1 | un îlot de cuisine (blanc) | V1.3, V1.6, V1.7 | non |
| probablement faux | 8 | **cloisons et doublages** de 10 à 15 cm en blocs de plâtre (le blanc de la légende), non porteurs | V1.3 ; V1.6 et/ou V1.7 en plus pour 7 | non : des cloisons |

Aucun incertain, aucun probablement réel.

### 10.5 Feuille B — 82 voiles retirés

| Catégorie | Contours | Ce que c'est | Retiré par | Un ingénieur y verrait un voile ? |
|---|---|---|---|---|
| certainement faux | 11 | hors de la zone : 10 échantillons de la légende, une case du cartouche | V1.4 (et V1.3 pour les 2 blancs) | non |
| certainement faux | 37 | **baies de fenêtre** | V1.3 ; V1.7 aussi (et V1.6 pour 3) | non |
| certainement faux | 14 | **lames de platelage** de balcons et de terrasses | **V1.6 seul** pour 8 ; V1.6 et V1.7 pour 6 | non |
| certainement faux | 6 | petits **barreaux rouges isolés** dans les pièces, non légendés (radiateurs ?) | V1.6 et V1.7 | non |
| certainement faux | 2 | îlots de cuisine | V1.3, V1.6, V1.7 | non |
| certainement faux | 1 | une bande d'isolant devant un trumeau | **V1.6 seul** | non |
| probablement faux | 10 | cloisons et doublages en blocs de plâtre, non porteurs | V1.3 ; V1.6 et/ou V1.7 en plus pour 9 | non |
| **probablement réel** | **1** | un **voile en béton armé** (gris foncé de la légende), 20 cm coté, 7,29 m d'une façade à l'autre, entre deux logements, doublé d'un isolant et d'une cloison | **V1.6 et V1.7** : hors axe ; ses bouts touchent la maçonnerie des façades, pas un élément plein qui le croise | oui |

Des trois voiles « béton armé » en bande de la feuille, G5 en garde deux (dont
un dessiné deux fois : 3 contours) et perd celui-ci.

### 10.6 La vérification : elle échoue

* **Probablement réels retirés seulement par V1.6 et/ou V1.7** : 14 contours
  (7 voiles) sur chacune des six variantes sans noms ; 1 voile sur la
  feuille B ; aucun sur v11 ni sur la feuille A. Sur une variante et la
  feuille B : V1.6 seul en retire 6 (les trois voiles intérieurs de noyaux,
  pourtant butés aux deux bouts), V1.7 seul 2 (VL1, pourtant sur un axe),
  les deux 7 (les deux trumeaux, VO1, le voile de la feuille B).
* **Ce que V1.6 et V1.7 sont seuls à écarter** : 24 lames de platelage,
  6 barreaux rouges, 2 bandes d'isolant, les 4 contours de poteaux allongés
  (et, sur v11, les 6 contours nommés poteau). Tout le reste — les blancs, le
  hors zone, les éléments minces — l'est par V1.3, V1.4 ou la plausibilité.
  Bilan sur une variante sans noms et les deux feuilles : **15 contours
  probablement réels (8 voiles) perdus pour 36 contours faux écartés**.
* **Pourquoi.** Un voile n'est pas toujours sur un axe (voiles intérieurs de
  noyau, voile entre logements) ni toujours buté contre un élément plein qui
  le croise (trumeau entre deux baies, voile hachuré en plusieurs contours,
  voile qui finit contre un poteau dans son prolongement ou contre une façade
  en maçonnerie). Le § 3.2 justifiait V1.6 et V1.7 par les négatifs mesurés en
  tenant les 14 bandes pour « hors référence, de nature non vérifiée » ;
  vérifiées, la moitié sont de vrais voiles.
* **Énoncés de ce document que la contre-mesure contredit.** § 1.2 : « 25
  bandes hachurées […] ne sont pas des voiles » — 14 en sont. § 1.6 : « faux
  voiles après G4 : 25 » et « 19 épaisseurs hors référence » — des 19
  épaisseurs que G5 retire sur chaque variante sans noms, **11 viennent
  seulement de voiles probablement réels et ont la bonne valeur** (20 ou
  30 cm cotés), sous le bon repère pour 4 et sous un repère faux pour 7
  (étiquette d'ascenseur, voile voisin, aucun) ; 5 viennent des hachures
  incertaines (15 ou 30 cm, valeur fausse pour le voile) ; 2 mêlent un poteau
  allongé et un voile ; 1 vient d'un poteau seul. § 3.2 : « hors référence :
  0 des 14 bandes » et la précision de V1.6 et V1.7. § 5.1 et L4 : le
  « 25 → 0 » des variantes retire 14 vrais contours de voile. § 8, risque 5 :
  avéré.

### 10.7 Variantes mesurées, sans code de production

Calculées sur les entrées d'audit (critères indépendants) et sur une sonde
des bouts et des rangées, hors du dépôt. « Rendus » : contours probablement
réels qui redeviendraient des voiles.

| Variante de V1 | Rendus : variante sans noms ; feuille B | Incertains rendus (doublons) | Faux réadmis |
|---|---|---|---|
| G5 tel que conçu | 0 / 14 ; 0 / 1 | 0 | 0 |
| sans V1.6 | 6 / 14 ; 0 / 1 | 7 | A : 11 (10 lames, 1 isolant) ; B : 9 (8 lames, 1 isolant) |
| sans V1.7 | 2 / 14 ; 0 / 1 | 0 | variantes : 4 (poteaux allongés) ; v11 : 6 (poteaux nommés, conflit 0,4) |
| sans V1.6 ni V1.7 | 14 / 14 ; 1 / 1 | 7 | variantes : 4 ; v11 : 6 ; A : 11 ; B : 21 (14 lames, 6 barreaux, 1 isolant) |
| sans V1.6 ; V1.7 réduite à « quelque chose touche un bout » | 10 / 14 ; 1 / 1 | 7 | A : 11 ; B : 20 — les trumeaux, sans rien à leurs bouts, restent perdus |
| feuilles : même remplissage qu'un voile V1 de la feuille (style appris, N1) | 0 / 14 ; 1 / 1 | 0 | 0 |

* **Filtres essayés pour écarter les faux sans V1.6 ni V1.7 (premier jet).**
  « Rien à aucun bout » prend les 4 contours de poteaux allongés, mais aussi
  les 4 des deux trumeaux, et 1 barreau rouge sur 6. « Rangée de lames »
  (bandes de même largeur côte à côte, quelle que soit leur forme) prend 12
  des 24 lames de platelage et aucun voile. Aucun ne sépare encore les classes.
* **Le repère de voile** les séparerait sur le DXF mesuré (aucun poteau
  allongé n'en porte), mais c'est une convention du projet — les séries VA,
  VB, VC… ne sont pas dans le vocabulaire des repères — et l'affectation des
  repères est bruitée (7 des 11 bonnes épaisseurs perdues portent un repère
  faux) : ce serait une dépendance nommée de plus, à écrire.
* **Toute variante qui rend les voiles de noyau les ajoute aussi au plan réel
  nommé** et à ses variantes nommées (mêmes bandes candidates) : L1 (« aucun
  voile ajouté ») tomberait — à juste titre, mais c'est un changement à
  décider.

### 10.8 Conséquence

* **G5 ne doit pas être implémenté tel que conçu** : V1.6 (sur un axe) et
  V1.7 (butée à un bout) ne peuvent pas être des conditions nécessaires d'un
  voile.
* **Pistes, à décider avant le code** (aucune n'est retenue ici) :
  (a) V1.6 et V1.7 deviennent des indices de confiance et non des filtres,
  avec des exclusions propres aux faux mesurés (rangées de lames, éléments
  isolés, couches d'isolant) — à concevoir et à mesurer ; (b) les bandes
  coupées à qui seuls V1.6 ou V1.7 manquent deviennent des **candidats montrés
  à la revue** — ni voiles, ni silence ; les 15 vrais et les 36 faux y
  passeraient ; (c) le style appris (même remplissage qu'un voile V1) sur les
  feuilles : 1 / 1 sans faux, sans effet sur les DXF (aucun voile V1 dont
  apprendre) ; (d) le repère de voile comme corroboration nommée (N3) : il
  sépare les classes du DXF mesuré, au prix d'une dépendance écrite à une
  convention de repérage.
* Les relevés (rendus, tables par contour) restent hors du dépôt.
