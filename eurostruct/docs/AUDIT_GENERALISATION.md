# Audit de généralisation du moteur d'extraction

> Question posée : le moteur d'extraction dépend-il d'hypothèses propres à UN
> bureau d'études ou à UNE convention de dessin ? Réponse courte : **oui, pour
> toute la chaîne géométrique** (axes, grille, poteaux, pieux, voiles), qui
> repose sur des NOMS de calques, de blocs et de types de ligne ; **non, pour
> la mesure des cotes**, qui suit la norme DXF ; **en partie, pour le texte et
> les unités**, écrits pour le français, le néerlandais et l'anglais.
>
> Version auditée : `eurostruct-extraction/0.4.0` (branche
> `claude/eurostruct-saas-platform-js2o49`, `4f85eca`). Aucun code n'a été
> modifié pour cet audit. Les plans réels, leurs variantes et les sorties
> restent hors du dépôt.

## 0. Résumé

| | |
|---|---|
| **Niveau de maturité hors de la source actuelle** | **Niveau 1 sur 5** — validé sur une seule source de dessins (un bureau belge : un DXF de fondations, deux feuilles PDF). Non prêt pour un déploiement hors de cette source sans durcissement ni campagne (§ 7, § 9). |
| **Ce qui se généralise** | La mesure des cotes DXF (norme DXF : 1 041 cotes identiques dans 13 variantes sur 14), l'unité par la présentation (« 1/100 » + fenêtre), l'invariance à la rotation, les règles de texte FR/NL/EN. |
| **Ce qui ne se généralise pas** | La détection des axes (0 axe sur 71 sans convention de nom), donc des nœuds, des poteaux par la forme (0 sur 64), des pieux (0 sur 477 dès que les calques sont neutres), et l'exclusion des formes parasites (101 dessins de pieux et 2 cercles de cartouche deviennent des poteaux quand les calques ne sont plus nommés). |
| **Ce qui est dangereux** | Trois chemins produisent une valeur FAUSSE avec une confiance élevée, et pas seulement une absence : `$INSUNITS` faux (×10 / ÷10 à 0,9), séparateur de milliers anglo-saxon (« 1,250 mm » lu 1,25 mm à 0,7), fond d'architecture visible (85 poteaux, 329 voiles, 80 poutres d'architecture). |
| **Recommandation** | Ne pas proposer la géométrie hors de la source actuelle avant les durcissements D1–D6 (§ 9) ; la mesure des cotes et les règles de texte FR/NL/EN peuvent être proposées, toujours sous confirmation humaine (interdiction 5). Lancer la campagne du § 7 avant toute promesse de couverture. |

## 1. Méthode, et ce qu'elle ne prouve pas

**Trois sources d'éléments :**

1. **Lecture du code**, module par module (`geometrie/*`, `lecteurs/*`,
   `extracteurs/*`, `nombres.py`, `registre.py`) : chaque seuil, chaque
   expression régulière, chaque liste de mots. Inventaire au § 2.
2. **Sondes sur le plan réel** (§ 3) : 14 variantes du DXF de développement,
   produites hors du dépôt avec ezdxf, chacune changeant UNE convention
   (noms de calques, noms de blocs, types de ligne, langue des calques,
   `$INSUNITS`, rotation, blocs explosés, casse des étiquettes) et gardant
   la géométrie, les textes et les cotes. Chaque variante passe par la
   chaîne du produit (`parse_document` → `extract_engineering_data`), arbre
   gelé, empreinte vérifiée avant et après.
3. **Sondes de texte** (§ 3.3) : 33 notations courantes en Belgique, France,
   Allemagne, Espagne, Royaume-Uni et États-Unis, et 8 déclarations d'unité,
   chacune isolée (une valeur unique par texte, pour que le registre ne
   fusionne rien).

**Ce que l'audit ne prouve pas.** Le corpus réel compte UN bureau : un DXF
et deux feuilles PDF. Les 26 plans fabriqués de la suite de tests suivent les
conventions que le code attend (ils ont été écrits pour lui) ; les 36 DXF
d'exemple d'ezdxf éprouvent le format, pas le dessin de structure. Les
variantes isolent les NOMS ; elles ne simulent pas une autre MANIÈRE DE
DESSINER (bulles hexagonales, voiles en `MLINE`, cotes en espace papier).
**Les probabilités du § 4 sont donc des estimations d'ingénieur, fondées sur
le code et les sondes, pas des mesures** ; la campagne du § 7 est faite pour
les remplacer.

**Classement des hypothèses.**

| Code | Classe | Sens |
|---|---|---|
| **DXF** | standard DXF | défini par la référence DXF d'Autodesk : codes de groupe, `$INSUNITS`, `BYLAYER`/`BYBLOCK`, calque `0`, calques éteints/gelés, blocs `*D`. |
| **IND** | courant dans le métier | pratique répandue d'un bureau et d'un pays à l'autre : axes en trait mixte, bulles rondes, lettres dans un sens et chiffres dans l'autre, poteaux aux nœuds, « 1:100 » au cartouche. |
| **BUR** | propre au bureau | change d'un bureau à l'autre : vocabulaire des calques, forme exacte des bulles, casse et format des étiquettes, cotes en cm, voile dessiné en rectangle plein, préfixes de repères. |
| **PROJ** | propre au projet | calibré sur le plan de développement : seuils réglés sur un cas observé, nom d'une référence externe liée, conventions vues une seule fois. |

## 2. Inventaire, sous-système par sous-système

Pour chaque sous-système : heuristiques (H), noms de calques (C), noms de
blocs (B), formats de texte (T), conventions de DAO (D). Les noms de calques
et de blocs sont lus par **une seule table** (`classification.py`) : un nom
est normalisé (sans accents, en majuscules) et cherché, mot par mot, dans
l'ordre `cote, fondation, pieu, texte, niveau, armature, cadre, trémie,
poteau, poutre, voile, dalle, axe, hachure` ; le premier rôle trouvé gagne ;
**un bloc l'emporte sur son calque** (le plus intérieur qui se reconnaît) ;
un calque sans rôle laisse décider le type de ligne (axe en trait mixte),
puis la forme.

### 2.1 Classification commune (calques, blocs, types de ligne)

| # | Hypothèse | Classe |
|---|---|---|
| C1 | Le rôle d'un élément est écrit dans le nom de son calque ou de son bloc, en FR/NL/EN/DE ou selon l'AIA (`S-COLS`, `S-GRID`…). | BUR |
| C2 | Vocabulaire espagnol, italien, portugais absent : `EJES`, `PILARES`, `MUROS`, `VIGAS`, `FORJADO`, `COTAS`, `ZAPATAS`, `ENCEPADO`, `CAJETIN` ne disent rien. `PILOTES` est reconnu par coïncidence (mot français). | BUR (pays) |
| C3 | Cartouche reconnu par `CARTOUCHE|CADRE|FRAME|TITLE|TITRE|KADER|RAHMEN|VIEWPORT` ; `PLANKOPF` (DE), `CAJETIN` (ES), `TITELBLOK` (NL) ne le sont pas. `CADRE` désigne aussi un cadre d'armature en français. | BUR |
| C4 | `TRAME` est un axe ; en français c'est aussi le nom courant d'un motif de hachure. `FRAME` sans borne finale reconnaît `FRAMEWORK`. | BUR |
| C5 | Le premier rôle de l'ordre fixe gagne : `S-ANNO-TTLB` (cartouche AIA) et `S-ANNO-PATT` (hachures AIA) sont des « textes » ; `AXES POTEAUX` est un poteau. | BUR |
| C6 | Un bloc l'emporte sur son calque, le plus intérieur d'abord ; un bloc d'architecture nommé `…Column…` ou `…Wall…` (exports ArchiCAD/Revit) est un poteau ou un voile de structure. | BUR |
| C7 | Types de ligne d'axe : `CENTER`, `CENTRE`, `DASHDOT`, `AXE`, `AXIS`, `MITTE`, `ACAD_ISO04–14W100` ; tirets = retombée (`HIDDEN`, `DASHED`…). | IND |
| C8 | La couleur, l'épaisseur de trait et la table de styles de tracé ne sont jamais lues : un bureau qui distingue la structure par la couleur n'est pas compris. | BUR |
| C9 | Calque éteint ou gelé = non lu ; l'élément d'un bloc sur `0` prend le calque de l'`INSERT` ; `BYBLOCK`/`BYLAYER` résolus. | DXF |
| C10 | Les gels par fenêtre (VP freeze) et les états de calques ne sont pas lus : seul l'état global du calque compte. | DXF (partiel) |

### 2.2 Axes (traits d'axe et étiquettes)

| # | Hypothèse | Classe |
|---|---|---|
| A1 | Un trait n'est candidat axe que si son calque ou son bloc le nomme (C1), ou si son type de ligne est un trait mixte (C7). **Aucune règle ne reconnaît un axe par sa seule géométrie.** | BUR |
| A2 | Seuil de longueur : 1/10 de la diagonale de l'emprise pour un trait nommé, **3/10** pour un trait reconnu par son seul type de ligne ; l'emprise inclut cartouche, légendes, détails dessinés dans l'espace objet. | PROJ |
| A3 | Un trait nommé plus court que le seuil reste un axe s'il finit sur une bulle étiquetée, mesure au moins 10 rayons de bulle et partage sa direction (`RAYONS_MIN_AXE_COURT = 10`, calibré sur deux axes du plan de développement). | PROJ |
| A4 | Morceaux colinéaires fusionnés : même direction à 0,2° près, même décalage à 2 tolérances près. | IND |
| A5 | **Bulle = `CIRCLE`** centré sur le prolongement (à 0,25 r près), entre −r et 4 r au-delà de l'extrémité, texte à moins d'un rayon du centre. Bulle hexagonale, carrée, en polyligne, en arc, ou déportée par un trait de rappel : non reconnue. | BUR |
| A6 | Bulle-bloc : seulement si le NOM du bloc est un axe (`AXE`, `GRID`, `BULLE`, `BUBBLE`…) ; l'attribut doit avoir la forme d'une étiquette. | BUR |
| A7 | **Étiquette = `[A-Z]{1,2}'?` ou `\d{1,3}'?`**, en majuscules. `a`, `A.1`, `1a`, `A-1`, `1/2`, `A1.5`, `X-03` sont refusés ; `L1`…`L10` seulement dans une bulle, en complément. | BUR |
| A8 | Texte libre candidat seulement entre 0,5 et 2 fois la hauteur médiane des étiquettes en bulle (`_HAUTEUR_LIBRE`, réglé sur une lettre de noyau d'ascenseur d'une feuille de développement). | PROJ |
| A9 | Bulle ou bloc > texte libre ; deux preuves de même force qui se contredisent : axe sans étiquette. Affectation globale, un texte sert un seul axe. | IND |
| A10 | Un cercle de pieu, de massif ou de cartouche n'est jamais une bulle — ce qui suppose les pieux et le cartouche NOMMÉS (C1, C3). | BUR |
| A11 | PDF : le style des axes est APPRIS des traits qui partent des bulles (cercles), aucune couleur en dur ; il faut donc des bulles rondes. | IND |

### 2.3 Détection de la grille (familles, nœuds, repère)

| # | Hypothèse | Classe |
|---|---|---|
| G1 | Familles = directions égales à 0,2° près ; deux familles se croisent si elles font au moins 10°. | IND |
| G2 | Grille droite seulement ; trois directions ou plus d'UN axe concourantes = grille rayonnante, écartée et dite. Grilles courbes : non prises en charge. | IND |
| G3 | Ordre de lecture : de gauche à droite pour des axes verticaux, de bas en haut pour des horizontaux ; repère X = famille la plus proche de l'horizontale. | IND |
| G4 | Nœud = intersection de deux axes à moins de 10 tolérances de leurs étendues. | IND |
| G5 | La grille est UNE grille : plusieurs bâtiments, joints de dilatation, grilles décalées dans le même dessin se mêlent en familles communes. | BUR |
| G6 | Invariance à la rotation : vérifiée (variante tournée de 30°, § 3). | — |

### 2.4 Nommage des nœuds

| # | Hypothèse | Classe |
|---|---|---|
| N1 | Lettre + chiffre → `A1` (lettre d'abord) ; deux lettres ou deux chiffres → `A/B` ; étiquette lettres-chiffres → `L10/3`. | IND |
| N2 | Axe sans étiquette → identifiant positionnel `grid:<famille>.<rang>` et nœud `node:<axe>x<axe>` : il CHANGE si un axe est ajouté ou retiré, ou si l'ordre des familles change. | BUR |
| N3 | Deux axes de même étiquette : le second devient `grid:A#2`, signalé. | IND |

### 2.5 Poteaux

| # | Hypothèse | Classe |
|---|---|---|
| P1 | Par le nom (calque/bloc poteau) : confiance 0,85, nœud non exigé. | BUR |
| P2 | **Par la forme : seulement s'il contient un nœud de grille** (ou y est centré, à une demi-section près) ; confiance 0,6 (0,65 plein). Sans grille, aucun poteau par la forme ; un poteau hors nœud n'est jamais trouvé. | IND |
| P3 | Section : contour fermé, élancement ≤ 4, compacité ≥ 0,5, côté entre 100 et 2 000 mm (unité connue), au plus 0,3 entraxe médian (unité inconnue). | IND |
| P4 | Exclusions par la forme (diagonales = trémie, contour contenu = socle, texte « gaine/asc. »…), **et par le nom** (pieu, massif, hachure, cartouche) : sans ces noms, les formes parasites aux nœuds deviennent des poteaux. | BUR |
| P5 | Rectangle reconstitué depuis quatre `LINE` à angle droit ; cercles, polylignes, `SOLID`, hachures lus ; `ELLIPSE` et `SPLINE` non lues (poteaux ovales, voiles courbes). | DXF/IND |
| P6 | Côtés exprimés dans le repère de la grille (G3). | IND |

### 2.6 Pieux

| # | Hypothèse | Classe |
|---|---|---|
| Q1 | **Un pieu n'est reconnu que par le nom** de son calque ou de son bloc (`PIEU`, `PILE`, `PILING`, `PILOTE`, `PAAL…`, `PFAHL…`) ; aucune règle de forme. | BUR |
| Q2 | Doublons à 5 % près ; dessin absorbé si ≥ 50 % de ses sommets sont sur le bord du pieu ; hachure orpheline si compacité ≥ 0,9 et élancement ≤ 1,5. | PROJ |
| Q3 | Repère de pieu : texte d'un calque pieu, ou texte qui NOMME un pieu (`PIEU 12`, `Paal 4`). | BUR |
| Q4 | Rien n'est proposé (diamètre, cote de pieu) : le pieu sert la revue et l'exclusion des faux poteaux. | — |

### 2.7 Voiles

| # | Hypothèse | Classe |
|---|---|---|
| V1 | Par le nom (calque/bloc voile) : 0,8. | BUR |
| V2 | Sans nom : **rectangle plein** (hachuré ou `SOLID`) d'élancement ≥ 4, épaisseur 80–600 mm (unité connue) ou ≤ 0,1 entraxe médian. Toute hachure allongée de cette taille devient un voile. | BUR |
| V3 | Deux traits parallèles appariés : seulement sur un calque de voile. | BUR |
| V4 | `MLINE` (voiles en multiligne), `SPLINE`, objets d'architecture (`ACAD_PROXY_ENTITY`) : non lus. | DXF |
| V5 | Épaisseur > 600 mm (parois moulées, murs de soutènement épais) : refusée quand l'unité est connue. | IND |

### 2.8 Cotes

| # | Hypothèse | Classe |
|---|---|---|
| K1 | Mesure par type DXF (`GEOMETRIE_COTES_DXF.md`) : linéaire selon le code 50, alignée = distance vraie, rayon, diamètre ; code 42 recoupé. | DXF |
| K2 | Seules les cotes de l'ESPACE OBJET, au premier niveau, sont proposées ; celles des blocs et des références liées ne servent qu'au rattachement géométrique ; celles de l'ESPACE PAPIER ne sont lues par aucun chemin. | BUR |
| K3 | Cotes d'ordonnée, d'arc, de rayon raccourci : comptées, non proposées. | DXF |
| K4 | `DIMLFAC` appliqué ; texte forcé discordant signalé. | DXF |
| K5 | Cote « d'axes » (`grid_spacing` du chemin texte) si son calque contient `axe|axes|axis|grid|grille|stramien|raster|trame`. | BUR |
| K6 | Produits non-AutoCAD (Revit, ArchiCAD, Allplan, BricsCAD) : bloc `*D` et code 42 parfois absents ou différents — non éprouvé. | DXF (non vérifié) |

### 2.9 Unités

| # | Hypothèse | Classe |
|---|---|---|
| U1 | **`$INSUNITS` non nul est cru sans recoupement** (1 in, 2 ft, 4 mm, 5 cm, 6 m) : ni la présentation, ni les mentions, ni les cotes ne le contredisent. Le gabarit métrique courant d'AutoCAD déclare le mm ; un bureau qui dessine en cm sur ce gabarit obtient des longueurs dix fois trop petites. | DXF (mais souvent faux dans la pratique) |
| U2 | `$INSUNITS = 0` : unité attachée si une mention écrite ET deux cotes rattachées concordent, ou si une échelle écrite « 1/n » ET une fenêtre de présentation donnent mm/cm/m/in/ft à 0,5 % près. | IND |
| U3 | Mentions reconnues : `cotes/dimensions/mesures/maten/maatvoering/afmetingen/all dimensions` + `en/in` + `mm|cm|m`. **Allemand (`Maße`, `Bemaßung`), espagnol (`cotas`, `medidas`), italien (`quote`) : non reconnus** (sonde § 3.3). | BUR (pays) |
| U4 | Échelle écrite « 1/n » ou « 1:n », n ≤ 4 chiffres ; mot-clé (`ECH`, `SCALE`, `SCHAAL`, `MASSSTAB`) seulement en préférence. Pied-pouce (`1/4" = 1'-0"`) : non lu. | IND |
| U5 | Pas de présentation (tracé depuis l'espace objet) et pas de mention FR/NL/EN : aucune unité, confiance −0,2 sur toute la géométrie. | IND |
| U6 | PDF : échelle écrite ET confirmée par au moins 5 cotes (60 %) ; unités mm/cm/m. | IND |

### 2.10 Textes : repères d'éléments et règles de texte

| # | Hypothèse | Classe |
|---|---|---|
| L1 | Repère = `lettres{1,3} [sep] chiffres{1,3}[a-z]? [section a×b]` ; défaut connu : « C03-68 » lu « C03 ». | BUR |
| L2 | **Préfixe → genre** : `P/B/BM/PT/POU/L/R…` = poutre, `C/K/CO/COL/PO/POT/PC/ST` = poteau, `V/VO/M/MU/W/WA` = voile. En Espagne `P` = pilar (poteau) ; en Allemagne `U` = Unterzug, `St` = Stütze ; `L` = linteau ou ligne selon les bureaux. | BUR (pays) |
| L3 | Repère affecté à l'élément le plus proche, à moins de 6 hauteurs de texte. | PROJ |
| L4 | Nombres : virgule OU point = décimale ; le point n'est jamais un séparateur de milliers ; l'espace en est un seulement devant une unité. **« 1,250 mm » (anglo-saxon) est lu 1,25 mm** ; « 1.234,5 » (allemand) n'est pas lu. | BUR (pays) |
| L5 | Vocabulaire des règles : FR/NL/EN complet ; DE partiel (`Wand d=`, `Beton`, niveaux par le signe) ; ES quasi nul (`Pilar`, `Forjado canto`, `Muro e=` non lus). | BUR (pays) |
| L6 | Classes de béton EN 206 seulement : la désignation du Code structural espagnol (`HA-25/B/20/IIa`) et les classes BS 8500 (`C32/40`) ne sont pas lues — sans erreur, mais sans le dire. | IND (EN) |
| L7 | Section sans unité (« 30x30 ») : proposée SANS unité à 0,4, sauf déclaration du dessin. | — (sûr) |
| L8 | Niveau = signe + 1–3 chiffres + 2–3 décimales, en mètres ; un niveau en mm (« +3450 »), sans signe (« NGF 35.20 ») ou « ±0.00 » n'est pas lu. | BUR |
| L9 | Ouvertures nommées en FR/NL/EN/DE (`gaine`, `koker`, `Schacht`…) ; ES (`hueco`, `patinillo`) absent. | BUR (pays) |

### 2.11 Génération des propositions

| # | Hypothèse | Classe |
|---|---|---|
| R1 | Plafond 0,90 (DXF), 0,85 (PDF) ; −0,2 sans unité ; confiances fixes par règle (axes 0,85/0,75/0,6, poteaux 0,85/0,65/0,6, voiles 0,8). Ces nombres sont indicatifs et **non calibrés** sur un corpus. | PROJ |
| R2 | Valeurs identiques fusionnées par le registre (corroboration, plafond 0,9) ; au-delà de 1 000 candidats, rien n'est enregistré de plus (et c'est compté). | IND |
| R3 | Lecture partielle au-delà de 50 000 entités (texte) ou 200 000 primitives (géométrie) ; blocs imbriqués au-delà de 8 niveaux non lus. | IND |
| R4 | Une confiance élevée ne dépend jamais de la cohérence avec un autre chemin : une unité fausse (U1) ne baisse aucune confiance. | BUR |

## 3. Sondes empiriques

### 3.1 Variantes du plan de développement

Le DXF de développement (fondations, AutoCAD 2013, `$INSUNITS = 0`, unité
établie par la présentation « 1/100 ») porte ses rôles ainsi : 313 calques
dont 135 reconnus, 271 blocs nommés dont 206 reconnus. 63 de ses 71 axes
sont reconnus par le NOM DU BLOC d'une référence externe liée (et, à défaut,
par les calques qu'elle a apportés : v02), 8 par le nom de leur calque ; ses
pieux par le nom de leurs calques ; ses 64 poteaux par la FORME aux nœuds
(aucun n'y est reconnu par son nom) ; ses 4 voiles par le nom de leur calque.

| Variante | Axes | Étiq. | Nœuds | Poteaux | Pieux | Voiles | Cotes | Unité | Propositions (géom.) | Valeurs identiques à l'origine |
|---|---|---|---|---|---|---|---|---|---|---|
| origine | 71 | 61 | 299 | 64 | 477 | 4 | 1 041 | cm (présentation) | 335 (142) | 335/335 |
| v00 réenregistré par ezdxf (témoin) | 71 | 61 | 299 | 64 | 477 | 4 | 1 041 | cm | 335 (142) | 335/335 |
| v01 calques neutres (`C001`…) | 65 | 61 | 252 | **167** | **0** | **25** | 1 041 | cm | 350 (157) | 321/335 |
| v02 blocs neutres (`B001`…) | 60 | 43 | 263 | 64 | 477 | 4 | 1 041 | cm | 313 (109) | 299/335 |
| v03 sans types de ligne | 71 | 61 | 299 | 64 | 477 | 4 | 1 041 | cm | 335 (142) | 335/335 |
| v13 calques + blocs neutres, types gardés | 19 | 16 | 81 | 52 | 0 | 25 | 1 041 | cm | 257 (61) | 231/335 |
| **v04 aucune convention** (v01+v02+v03) | **0** | **0** | **0** | **0** | **0** | 25 | 1 041 | cm | 216 (19) | 193/335 |
| v05 calques et blocs en espagnol | 19 | 16 | 81 | 27 | 477 | 25 | 1 041 | cm | 256 (60) | 231/335 |
| v06 calques et blocs en allemand | 71 | 61 | 299 | 71 | 477 | 4 | 1 041 | cm | 338 (145) | 335/335 |
| v07 calques et blocs AIA (`S-GRID`…) | 71 | 61 | 299 | 64 | 477 | 4 | 1 041 | cm | 335 (142) | 335/335 |
| v08 `$INSUNITS = 4` (mm, faux) | 71 | 61 | 302 | **3** | 477 | 0 | 1 041 | **mm (`$INSUNITS`)** | 322 (128) | **73/335** |
| v09 `$INSUNITS = 6` (m, faux) | 72 | 62 | 302 | 0 | 477 | 20 | 1 041 | **m (`$INSUNITS`)** | 327 (133) | **73/335** |
| v10 tourné de 30° | 71 | 61 | 299 | 64 | 477 | 4 | 1 041 | cm | 400 (142) | 303/335 ¹ |
| v11 `INSERT` de l'espace objet explosés | 23 | 23 | 80 | 87 | 477 | **334** | 1 376 | cm | 681 (417) | 241/335 ² |
| v12 étiquettes en minuscules | 62 | **23** | 272 | 64 | 477 | 4 | 1 041 | cm | 279 (85) | 275/335 |

¹ Les 142 propositions géométriques sont IDENTIQUES ; les 65 cotes de plus
viennent de la sonde : ezdxf ne pose pas d'angle (code 50) sur une cote
linéaire qui n'en avait pas quand il la tourne, la cote mesure alors la
projection horizontale. Artefact de la variante, pas du produit.

² L'explosion libère le fond d'architecture, qui était posé sur un calque
GELÉ et donc, à juste titre, ignoré : ses blocs nommés « Column » et « Wall »
(export d'un logiciel d'architecture) deviennent 85 poteaux « par le bloc »,
329 voiles, 80 poutres, 65 travées et 48 consoles. C'est la preuve du risque
C6 : un fond d'architecture laissé visible est lu comme de la structure.

### 3.2 Ce que les variantes établissent

1. **La géométrie est commandée par les noms.** Sans convention reconnue
   (v04) : 0 axe, 0 nœud, 0 poteau, 0 pieu ; il reste 25 « voiles » trouvés
   par la forme, tous sur des calques de hachures, au lieu des 4 voiles
   nommés. Avec le seul trait mixte (v13, v05), 19 axes
   sur 71 : les axes courts tombent sous le seuil de 3/10 de la diagonale.
2. **Les pieux dépendent à 100 % du nom** (v01 : 477 → 0), et leur
   disparition fait passer les poteaux de 64 à 167 : **58 polygones hachurés
   de pieux, 43 cercles de pieux, 2 cercles de cartouche** deviennent des
   poteaux par la forme (solde +103) : l'exclusion des formes
   parasites repose sur les noms autant que la détection.
3. **Le vocabulaire couvre FR/NL/EN/DE/AIA, pas l'espagnol.** L'allemand
   (v06) et l'AIA (v07) donnent le même modèle, à 7 faux poteaux près en
   allemand : le cartouche nommé `PLANKOPF` n'est pas reconnu. L'espagnol
   (v05) perd 52 axes, 45 étiquettes, 37 poteaux.
4. **Les types de ligne ne portent rien sur ce plan** (v03 identique) parce
   que les noms suffisent ; ils sont le seul recours quand les noms manquent.
5. **Un `$INSUNITS` faux est cru** : 262 valeurs sur 335 changent (« entraxe
   880 mm » à 0,9 au lieu de 880 cm), aucune réserve n'est émise, alors que
   la présentation du même fichier dit le contraire. Les bornes de
   plausibilité retiennent les poteaux (64 → 3), pas les entraxes ni les
   cotes.
6. **Étiquettes sensibles à la casse** (v12) : 61 → 23 étiquettes, 9 axes
   courts perdus (ils n'étaient gardés que par leur bulle étiquetée).
7. **Ce qui ne bouge jamais** : les 1 041 cotes (sauf v11, qui en ajoute),
   l'unité par la présentation, les propositions de texte, la grille sous
   rotation.

### 3.3 Sondes de texte et d'unité

Un DXF par sonde, sans géométrie ; valeurs toutes différentes.

| Pays | Texte | Attendu | Lu |
|---|---|---|---|
| FR | `Béton C30/37 XC1` | C30/37, XC1 | C30/37, XC1 ✔ |
| FR | `Dalle pleine ép. 21 cm` | 210 mm | 21 cm ✔ |
| FR | `Poteau 31x32` | 31×32 (unité ?) | 31×32 sans unité, 0,4 ✔ |
| FR | `Niv. +3,41` | +3,41 m | 3,41 m (0,4) ✔ |
| BE-NL | `Beton C25/30 EE2` | C25/30 | C25/30 ✔ |
| BE-NL | `Vloerdikte 18 cm` | 180 mm | **rien** |
| BE-NL | `Peil +2,82` / `Kolom 33x34` | +2,82 m / 33×34 | ✔ / ✔ |
| DE | `Beton C35/45` / `Betonstahl B500A` | C35/45 / B500A | ✔ / ✔ |
| DE | `Decke d = 22 cm` | 220 mm | **rien** |
| DE | `Stütze 35/36` | 35×36 | **rien** |
| DE | `Wand d=26 cm` | 260 mm | 26 cm ✔ |
| DE | `OK FFB +4,450` | +4,450 m | 4,45 m (0,4) ✔ |
| DE | `Spannweite 1.234,5 mm` | 1 234,5 mm | **rien** |
| DE | `Bewehrung Ø14/150` | Ø14 e=150 | **rien** |
| ES | `Hormigón HA-25/B/20/IIa` | HA-25 (Code structural) | rien (sûr, mais muet) |
| ES | `Acero B500S` | B500S | ✔ |
| ES | `Forjado canto 31 cm` / `Pilar 37x38` / `Muro e=27 cm` | 310 / 37×38 / 270 | **rien** / **rien** / **rien** |
| ES | `Cota +5,45` | +5,45 m | 5,45 m (0,4) ✔ |
| EN | `Concrete C40/50` / `Slab thickness 250 mm` | ✔ | ✔ / ✔ |
| EN | `Column 400x450` | 400×450 (mm au R.-U.) | 400×450 sans unité, 0,4 ✔ |
| EN | `Wall 300 thk` | 300 mm | **rien** |
| US | **`Span 1,250 mm`** | **1 250 mm** | **1,25 mm à 0,7 — FAUX** |
| US | `f'c = 4000 psi`, `#5 @ 12" o.c.`, `W14x30` | hors EN | rien ✔ (aucun faux poteau) |

Déclarations d'unité : `Toutes les cotes sont en cm` ✔, `Maten in cm` ✔,
`All dimensions in mm` ✔ ; **`Alle Maße in cm`, `Bemaßung in cm`, `Cotas en
cm`, `Medidas en cm`, `Quote in cm` : non reconnues.**

## 4. Probabilités d'échec estimées

**Définition de l'échec** (par plan et par sous-système) : le sous-système
manque au moins 20 % des éléments que l'ingénieur y voit, OU propose au moins
une valeur fausse avec une confiance ≥ 0,6. **Estimations d'ingénieur**
(§ 1), en fourchettes ; « autre bureau » = même pays, mêmes langues ; « autre
pays » = Espagne surtout, Allemagne et Royaume-Uni mieux couverts ; « sans
convention » = calques et blocs sans nom de rôle reconnu.

| Sous-système | Autre bureau | Autre pays | Sans convention de calques | Fondement principal |
|---|---|---|---|---|
| Axes (traits) | 40–60 % | 50–85 % (ES haut, DE/UK bas) | 85–95 % | A1, A2 ; v04 0/71, v13 19/71 |
| Étiquettes d'axes | 40–60 % | 45–85 % | 90–100 % | A5–A7 ; v12 23/61 |
| Détection de la grille | 40–60 % | 50–85 % | 90–100 % | suit les axes ; G5 |
| Nommage des nœuds | 40–60 % | 50–85 % | 90–100 % | suit les étiquettes ; N2 |
| Poteaux | 55–75 % | 60–85 % | 95–100 % | P2, P4 ; v01 +103, v04 0 |
| Pieux | 35–55 % | 40–70 % | 100 % | Q1 ; v01 477 → 0 |
| Voiles | 50–70 % | 55–75 % | 85–95 % | V2–V4 ; v04 : 25 hachures, 0 voile nommé |
| Cotes (mesure) | 5–15 % | 10–20 % | 5–15 % | K1 normatif ; risque K2, K6 |
| Unités | 25–40 % | 35–55 % | 25–40 % | U1 (gabarit mm), U3, U5 |
| Textes (repères + règles) | 20–35 % | 55–80 % (ES/DE) | 20–35 % | L2, L4, L5 ; § 3.3 |
| Génération des propositions | suit l'amont | suit l'amont | suit l'amont | R1 non calibré, R4 |

Lecture : hors de la source actuelle, **un plan sur deux environ** n'aura
pas de grille exploitable sans intervention ; sur un plan sans convention,
la géométrie ne propose presque rien — ce qui est sûr — mais elle propose
alors des voiles qui sont des hachures, ce qui ne l'est pas.

## 5. Les 20 hypothèses les plus susceptibles de casser l'extraction

Rang = probabilité × gravité ; une valeur fausse proposée avec confiance
pèse plus qu'une absence.

| Rang | Hypothèse | Mode de défaillance | Dessin où elle échoue | Atténuation |
|---|---|---|---|---|
| 1 | U1 — `$INSUNITS` non nul est cru | Toutes les longueurs fausses d'un facteur 10, 100 ou 1 000, confiance 0,9, aucune réserve (v08, v09). | Plan dessiné en cm sur le gabarit métrique par défaut (`$INSUNITS = 4`). | Recouper `$INSUNITS` par la présentation, les mentions et les cotes, comme pour `$INSUNITS = 0` ; contradiction → aucune unité, et le dire. |
| 2 | A1 — axe reconnu seulement par un nom ou un trait mixte | Aucune grille ; donc aucun nœud, aucun poteau par la forme, aucun entraxe (v04 : 0/71). | Bureau qui range ses axes sur `STRUCTURE` ou `0`, en trait continu fin. | Règle géométrique : droites longues finissant sur des bulles étiquetées, familles régulières ; et correspondance calque → rôle confirmée par l'ingénieur (§ 9, D3). |
| 3 | Q1 — pieu reconnu seulement par le nom | 0 pieu ; les cercles et hachures de pieux deviennent des poteaux (v01 : +103). | Plan de fondations espagnol (`CIMENTACION`), italien (`PALI`), ou calque `FONDATIONS`. | Vocabulaire étendu en données ; candidat pieu par la forme (cercles répétés de même diamètre, hors nœud, en groupes) NON proposé, présenté à la revue. |
| 4 | L4 — virgule toujours décimale | « 1,250 mm » lu 1,25 mm à 0,7 ; « 12,500 » lu 12,5. | Plan anglais, américain, ou bureau qui écrit les milliers avec une virgule. | Une virgule suivie de trois chiffres exactement devant `mm` est AMBIGUË : refuser ou proposer sans valeur, et le dire ; profil de nombre par document. |
| 5 | C6 — un bloc d'architecture nommé « Column »/« Wall » est structurel | Poteaux, voiles, poutres, travées et consoles d'architecture proposés (v11 : 85 / 329 / 80 / 65 / 48). | Fond d'architecture lié et laissé visible (export ArchiCAD/Revit). | Repérer les références liées (préfixe `xref$0$`, bloc d'origine externe) et demander à l'ingénieur lesquelles sont de la structure ; par défaut, ne rien proposer d'une référence externe. |
| 6 | P2 — poteau par la forme seulement à un nœud | Sans grille, aucun poteau ; un poteau hors trame, jamais. | Bâtiment sans grille dessinée, ou poteaux décalés de la trame. | Candidats hors nœud présentés à la revue (jamais proposés seuls) ; exiger nom OU nœud OU repère « Pxx » voisin. |
| 7 | P4/V2 — exclusion des parasites par le nom | Faux poteaux (hachures, pieux, cartouche) et faux voiles (hachures allongées) quand les noms manquent (v01, v04, v06). | Plan dont les hachures sont sur `0` ou `HATCH_1`. | Une hachure n'est un élément que si son contour est aussi un contour fermé non hachure ; compter et afficher la part « par la forme ». |
| 8 | A5 — bulle = cercle | Étiquettes perdues ; axes courts retirés (gardés seulement par une bulle étiquetée). | Bulles hexagonales ou carrées (courant en Allemagne et dans certains gabarits), bulles en polyligne. | Bulle = contour fermé compact (cercle, polygone régulier) centré sur le prolongement. |
| 9 | A7 — étiquette `[A-Z]{1,2}` ou `\d{1,3}`, majuscules | Étiquettes refusées (v12 : 61 → 23) ; nœuds non nommés. | Grilles `A.1`, `1a`, `A-1`, `X1/Y1`, lettres minuscules. | Formes composées admises DANS une bulle seulement, normalisation de la casse dans une bulle ; refus toujours cité. |
| 10 | C2/C3 — vocabulaire sans espagnol, cartouche à trois langues | Rôles perdus (v05 : 19/71 axes), cartouche lu comme structure (v06 : +7 poteaux). | Tout plan espagnol ; cartouche `PLANKOPF`, `CAJETIN`, `TITELBLOK`. | Tables de vocabulaire versionnées par pays, testées ; profils de calques par bureau. |
| 11 | U3/U5 — mention d'unité FR/NL/EN, ou présentation | Aucune unité : confiance −0,2, bornes de plausibilité inactives. | Plan allemand « Alle Maße in cm » tracé depuis l'espace objet. | Mots DE/ES/IT ; l'échelle d'impression et le gabarit ne suffisent jamais seuls. |
| 12 | A2 — seuil relatif à la diagonale de l'emprise | Axes courts écartés quand l'emprise est gonflée par des détails, une légende, un deuxième plan dans l'espace objet. | Feuille avec plan, coupes et détails dans le même espace objet. | Emprise calculée sur la zone de la grille (ou de la fenêtre de présentation), pas sur tout l'espace objet. |
| 13 | L5 — vocabulaire des règles de texte | Épaisseurs, sections, niveaux non lus (§ 3.3). | Notes générales en espagnol ou en allemand ; notations `d =`, `canto`, `e =`, `Stütze 35/36`. | Vocabulaire par pays, en données, chaque règle testée par une sonde comme celle du § 3.3. |
| 14 | L2 — préfixe de repère → genre | Repère affecté au mauvais genre : `P1` = pilar (poteau) en Espagne, poutre en France. | Plan espagnol de pilares `P1…P40`. | Préfixes par profil de pays/bureau ; un préfixe en conflit avec la forme ne décide rien. |
| 15 | K2 — cotes hors espace objet non proposées | Cotes perdues. | Bureau qui cote en espace papier, cotes dans des blocs ou une référence liée. | Lire les cotes de l'espace papier à travers la fenêtre (transformation et échelle), en le disant. |
| 16 | V3/V4 — voiles en `MLINE`, traits parallèles hors calque de voile | Voiles absents. | Architecture ou structure dessinée en multilignes. | Lire `MLINE` (géométrie explicite) ; paires de traits sur calque inconnu = candidates, pas propositions. |
| 17 | G5 — une seule grille | Familles mêlées, entraxes entre axes de deux bâtiments, noms de nœuds en double. | Deux bâtiments sur un sous-sol commun, grilles décalées par un joint. | Partition de la grille par composantes (axes qui se croisent), une grille par composante. |
| 18 | L8 — format des niveaux | Niveaux non lus ou lus faux. | « +3450 » (mm), « NGF 35.20 », « ±0.00 », « OKRD 3,45 » sans signe. | Formats par pays ; un niveau sans signe ni mot-clé reste sans proposition. |
| 19 | C8/C10 — ni couleur, ni gel par fenêtre | Rôle ignoré quand il est porté par la couleur ; éléments gelés dans la fenêtre lus quand même. | Bureau « tout sur `0`, couleur = rôle » ; plan dont la fenêtre gèle le fond. | Lire les gels de fenêtre (`VPLAYER`) de la présentation imprimée ; la couleur reste hors règle (trop variable) mais est montrée à la revue. |
| 20 | N2 — identifiants positionnels des axes non étiquetés | Un axe ajouté renumérote les nœuds `0.3x1.2` : une confirmation d'une révision ne correspond plus. | Révision B d'un plan qui ajoute un axe sans étiquette. | Identifiant stable par la géométrie (décalage arrondi), jamais par le rang. |

## 6. Confiance par sous-système

Confiance que le sous-système se comporte, hors de la source actuelle,
comme sur elle. Élevée = fondé sur la norme ou vérifié par les sondes ;
faible = dépend d'un nom ou d'un seuil calibré sur un cas.

| Sous-système | Confiance | Raison |
|---|---|---|
| Cotes (mesure) | **Élevée** | Norme DXF, invariante dans toutes les variantes ; reste à éprouver sur des exports non-AutoCAD (K6). |
| Unités | **Moyenne** si `$INSUNITS = 0` ; **faible** si `$INSUNITS` est posé | La présentation et les mentions FR/NL/EN se généralisent ; le cru-sans-recoupement de U1 non. |
| Génération des propositions | **Moyenne** | Mécanique saine (traçabilité, fusion, plafonds) ; confiances non calibrées, et aucune ne baisse quand l'amont se trompe. |
| Textes FR/NL/EN | **Moyenne** | Sondes vertes sauf `Vloerdikte`, `Wall 300 thk`, milliers anglo-saxons. |
| Textes DE/ES | **Faible** | Sondes : la plupart non lues ; une valeur fausse possible (milliers). |
| Détection de la grille et nommage des nœuds | **Moyenne si des axes sont trouvés**, faible sinon | Invariance à la rotation vérifiée ; tout dépend des axes et des étiquettes. |
| Étiquettes d'axes | **Faible à moyenne** | Bulles rondes et majuscules seulement. |
| Axes | **Faible** | Noms ou trait mixte ; 0/71 sans convention. |
| Voiles | **Faible** | Noms ou rectangles pleins ; hachures prises pour des voiles. |
| Poteaux | **Faible** | Dépend de la grille et des noms d'exclusion ; +103 sans noms de pieux. |
| Pieux | **Très faible** hors vocabulaire | Nom seulement. |

## 7. Campagne de validation, sans changer le code

**But** : remplacer les estimations du § 4 par des mesures, sur l'arbre
publié tel quel (SHA gelé), et décider des durcissements par les chiffres.

### 7.1 Taille

* Pour estimer un taux de réussite par sous-système à ±10 points avec 90 %
  de confiance, il faut environ **70 plans indépendants** (1,645² × 0,25 /
  0,1² ≈ 68). Les plans d'un même bureau ne sont pas indépendants : on
  plafonne à **6 plans par bureau**, et l'on vise **≥ 15 bureaux**.
* **Cible : 96 plans de 16 bureaux** ; minimum acceptable : **72 plans de
  12 bureaux**.
* Répartition par pays : Belgique 24, France 24, Espagne 24, Allemagne 24
  (4 bureaux chacun). En option, 12 plans d'exports AIA/NCS (Royaume-Uni,
  Revit) pour éprouver C5.

### 7.2 Types de plans (par bureau, 6 plans)

| Type | Nombre | Ce qu'il éprouve |
|---|---|---|
| Plan de fondations sur pieux ou semelles | 1 | Pieux, massifs, semelles, exclusion des faux poteaux. |
| Plan de coffrage d'étage courant (poteaux, voiles, poutres, dalles) | 2 | Axes, grille, poteaux, voiles, poutres, travées, repères. |
| Plan de coffrage d'un niveau irrégulier (biais, deux grilles, joint) | 1 | G2, G5, A2. |
| Plan d'implantation des axes, ou plan de charpente (acier/bois) | 1 | Axes sans éléments, poutres filaires. |
| La même feuille en PDF vectoriel | 1 | Chemin PDF, échelle par cotes. |

Diversité à couvrir dans l'ensemble (à cocher à la collecte) : logiciel
producteur (AutoCAD, Revit, ArchiCAD, Allplan, Tekla, BricsCAD,
MicroStation → DXF) ; version DXF (R2000 à R2018) ; unité (mm, cm, m) et
`$INSUNITS` (0, juste, faux) ; présence d'une présentation ; références
externes liées, non liées, fond visible ; bulles rondes/hexagonales/blocs ;
étiquettes simples/composées ; cotes en espace objet/papier.

### 7.3 Sources

1. **Bureaux pilotes** sous accord de confidentialité (source principale) :
   plans d'exécution réels, avec l'accord écrit du maître d'ouvrage si
   nécessaire.
2. **Dossiers de marchés publics** téléchargeables (Belgique : e-Procurement ;
   France : plateformes de DCE ; Espagne : Plataforma de Contratación del
   Sector Público ; Allemagne : portails Vergabe) — seulement si la licence
   des pièces permet cet usage.
3. **Écoles d'ingénieurs et d'architecture** : projets d'étudiants dessinés
   selon les gabarits de bureaux partenaires.
4. **Projets d'exemple des éditeurs** (exports DXF des projets d'exemple
   Revit, ArchiCAD, Allplan) : pour la diversité des producteurs, pas pour
   la vérité métier.

Règles : aucun plan dans le dépôt, aucun nom de client, de projet ou de
bureau dans les résultats publiés (identifiants `BUR01…BUR16`, `PL01…`) ;
stockage hors dépôt, effacement à la fin de la campagne ; aucune
confirmation réelle, aucune base non jetable (les décisions de la revue ne
servent pas à la campagne).

### 7.4 Vérité de terrain

Pour chaque plan, un ingénieur relève, sans voir les sorties du produit :
le nombre d'axes, leurs étiquettes et les entraxes ; les poteaux (nœud ou
position, section) ; les pieux (nombre, diamètre) ; les voiles (épaisseur) ;
30 cotes tirées au hasard avec la valeur AFFICHÉE ; l'unité du dessin ; les
niveaux ; les classes de matériaux ; les repères. Un second ingénieur relit
10 % des plans (accord inter-annotateurs).

### 7.5 Mesures

| Mesure | Par | Seuil de passage proposé |
|---|---|---|
| Rappel et précision par type d'élément (axe, étiquette, nœud, poteau, pieu, voile, poutre) | plan, bureau, pays, logiciel | Rappel ≥ 80 %, précision ≥ 95 % pour les éléments proposés |
| **Taux de valeurs fausses avec confiance ≥ 0,6** | proposition | **< 1 %** ; 0 pour l'unité |
| Unité : juste / absente / **fausse** | plan | Fausse = 0 |
| Écart des cotes à la valeur affichée | cote | 100 % exactes à 10⁻⁶ relatif (hors textes forcés) |
| Part des éléments décidés par le nom / le bloc / le type de ligne / la forme | plan | Indicateur de dépendance aux noms |
| Plans sans grille, sans unité, partiels, refusés, et leurs raisons (`unresolved`, `report`) | plan | Décrit, pas seuillé |
| Étiquettes d'axes justes, nœuds nommés justes | axe, nœud | ≥ 90 % |
| Faux poteaux / faux voiles par plan | plan | ≤ 1 |
| Règles de texte : rappel par catégorie et par langue | texte annoté | ≥ 80 % FR/NL/EN |
| Calibration : taux de justesse par tranche de confiance | proposition | Croissant avec la confiance |
| Temps d'analyse, mémoire | plan | < 120 s, < 2 Go |
| Temps de revue humaine (minutes par plan) | plan | Mesuré, comparé à la saisie manuelle |

Les intervalles sont donnés par la méthode de Wilson, par bureau puis
agrégés ; un résultat d'un bureau unique n'est jamais généralisé.

## 8. Risques de généralisation, classés

1. **Unité fausse crue** (U1) — faux à 0,9, toutes longueurs, fréquent.
2. **Grille introuvable sans convention de nom** (A1, A2) — tout l'aval tombe.
3. **Faux éléments quand les noms d'exclusion manquent** (P4, V2, Q1) —
   pieux, hachures et cartouche proposés comme poteaux et voiles.
4. **Fond d'architecture visible lu comme structure** (C6).
5. **Séparateur de milliers lu comme décimale** (L4) — faux à 0,7.
6. **Pieux introuvables hors vocabulaire** (Q1).
7. **Espagne : vocabulaire de calques, de textes, d'unités et préfixes
   absents** (C2, L2, L5, U3) — et le Code structural espagnol n'est pas
   l'EN (interdiction 4) : un plan espagnol doit être dit non pris en charge
   tant que ces tables n'existent pas.
8. **Bulles non rondes, étiquettes composées ou en minuscules** (A5, A7).
9. **Seuils calibrés sur un plan** (A2, A3, A8, Q2, L3, R1).
10. **Entités non lues** (`MLINE`, `SPLINE`, objets proxy) et **cotes hors
    espace objet** (V4, K2).
11. **Grilles multiples et identifiants positionnels** (G5, N2).
12. **Producteurs non-AutoCAD** non éprouvés (K6).

## 9. Durcissements recommandés avant la production

Par ordre de priorité. Chacun suit la règle du dépôt : conception écrite,
tests de régression, mesure avant/après sur le corpus, changement de
`VERSION_EXTRACTEUR`.

| Rang | Durcissement | Risques couverts | Effort |
|---|---|---|---|
| **D1** | Recouper `$INSUNITS` par la présentation, les mentions et les cotes ; contradiction → aucune unité, réserve écrite. | 1 | Faible |
| **D2** | Nombres ambigus : « d,ddd » devant une unité = ambigu, non proposé ; profil de séparateurs par document (si le document écrit « 1 250 » ou « 1.250,5 », le dire). | 5 | Faible |
| **D3** | **Correspondance calques → rôles confirmée par l'ingénieur** avant l'analyse géométrique, mémorisée par bureau (profil). C'est le levier le plus fort : il rend les plans « sans convention » lisibles sans deviner. | 2, 3, 6, 7 | Moyen (API + écran) |
| **D4** | Références externes liées et fonds : les repérer, les montrer, ne rien proposer d'une référence que l'ingénieur n'a pas désignée comme structure. | 4 | Faible à moyen |
| **D5** | Indicateur de dépendance aux noms dans le compte rendu : part des éléments par nom/forme, calques sans rôle, « aucune convention reconnue » affiché en tête de la revue ; aucun voile ni poteau par la forme quand aucun rôle d'exclusion n'est reconnu. | 2, 3 | Faible |
| **D6** | Tables de vocabulaire (calques, textes, unités, préfixes, ouvertures) en DONNÉES versionnées par pays, avec une sonde de texte par entrée ; ajouter ES et compléter DE/NL ; refus explicite des désignations non EN (`HA-25/…`). | 7, 10 | Moyen |
| D7 | Axes par la géométrie : longues droites finissant sur des bulles étiquetées, en familles régulières — comme candidats, confiance plafonnée. | 2 | Moyen |
| D8 | Bulles polygonales et étiquettes composées dans une bulle. | 8 | Faible |
| D9 | Emprise de référence = zone de la grille ou de la fenêtre imprimée, pas tout l'espace objet. | 9 | Faible |
| D10 | Pieux et poteaux hors nœud comme CANDIDATS de revue (jamais proposés seuls). | 3, 6 | Moyen |
| D11 | Lire `MLINE`, les cotes de l'espace papier à travers la fenêtre, les gels de fenêtre. | 10 | Moyen |
| D12 | Grilles multiples par composantes ; identifiants d'axes stables par la géométrie. | 11 | Moyen |
| D13 | Calibrer les confiances sur la campagne (§ 7) ; confiance abaissée quand deux chemins se contredisent. | 9 | Faible après campagne |

**Porte de production proposée** : D1, D2, D4, D5 faits ; D3 fait ou, à
défaut, géométrie désactivée pour tout bureau dont le profil n'est pas
confirmé ; campagne du § 7 passée sur au moins 12 bureaux avec 0 unité
fausse et moins de 1 % de valeurs fausses à confiance ≥ 0,6. Jusque-là, hors
de la source actuelle, seules la mesure des cotes et les règles de texte
FR/NL/EN devraient être proposées — toujours à confirmer par un ingénieur
(interdiction 5, mention obligatoire 8).

## 10. Reproduire

Les scripts de sonde vivent hors du dépôt (ils manipulent le plan réel).
Pour les refaire sur un autre plan :

1. Charger le DXF avec `ezdxf.recover.readfile`, appliquer UNE
   transformation (renommer les calques en créant des calques de mêmes
   propriétés ; renommer les blocs **en mettant aussi à jour le nom de
   chaque `INSERT`** — `BlocksSection.rename_block` ne le fait pas ; ne pas
   renommer les blocs de flèches des styles de cote ; types de ligne à
   `Continuous`/`BYLAYER` ; `$INSUNITS` ; rotation), enregistrer hors du
   dépôt.
2. Passer chaque variante par `parse_document` puis
   `extract_engineering_data`, arbre gelé, empreinte de l'arbre vérifiée
   avant et après.
3. Comparer `structure.counts`, les étiquettes, l'unité, et les
   propositions par (méthode, catégorie, valeur, unité).

Une variante tournée par ezdxf n'est pas probante pour les cotes linéaires
sans angle (§ 3.1, note 1).
