# Lecture géométrique des DXF — du dessin au modèle structurel

> Conception écrite **avant** le code. Elle prolonge
> [`LECTURE_DES_PLANS.md`](LECTURE_DES_PLANS.md) : même circuit (proposition →
> décision nommée → report → contrôle au calcul), une nouvelle **source** de
> propositions — la géométrie du dessin.
>
> **Réalisée ensuite.** Le §14 dit ce qui a été fait, ce qui l'a mesuré, et où
> le code s'écarte de ce plan ; le §9 montre une sortie réelle.

## 0. Point de départ mesuré

Le lot précédent lit un DXF comme un texte : les `TEXT`, `MTEXT`, `ATTRIB`
passent par les règles d'écriture, chaque `DIMENSION` devient une « cote », un
texte court sur un calque d'axes devient une « file ». Les traits ne sont pas
lus.

Mesuré sur un plan de coffrage fictif (`S-101` : trois files A–C, deux files
1–2, six poteaux, cinq poutres, deux dalles, une coupe au 1/20, unité du dessin
cm), le dépôt du DXF rend **43 propositions** et :

| ce que le dessin contient | ce qui est proposé aujourd'hui |
|---|---|
| poutres P1 (A→B) et P2 (B→C), entre-axes 600 et 450 cm, dessinées en rectangles | **aucune portée** : aucun texte ne l'écrit |
| six poteaux 30×30 dessinés pleins aux nœuds | une seule largeur/profondeur, tirée du texte « C1 30x30 » |
| cotes A–B 600, B–C 450, A–C 1050 sur le calque `COTES` | trois « cotes » non classées : le calque n'est pas un calque d'axes |
| cotes de la coupe au 1/20 (`DIMLFAC = 0,4`), affichées 30 et 60 | **75 et 150 cm** — le facteur d'échelle des cotes est ignoré (défaut corrigé dans ce lot) |
| la poutre P5 appuyée sur deux poteaux | rien ne relie une poutre à ses appuis |

Ce lot fait du dessin la source principale d'un DXF : les éléments sont
**reconnus dans les traits**, reliés en **graphe**, et les portées sont
**mesurées entre appuis** — sans qu'aucun texte ne les écrive.

## 1. Architecture

```mermaid
flowchart LR
  O[octets DXF] --> L[lecteurs/dxf.py<br/>un seul ezdxf.Document]
  L --> T[EntiteDxf<br/>textes, cotes]
  L --> P[geometrie/primitives.py<br/>explosion des blocs,<br/>calque effectif, poignées]
  P --> C[classification.py<br/>calques, blocs, types de ligne]
  C --> D[détection<br/>axes · poteaux · voiles · poutres<br/>dalles · trémies · cotes · niveaux]
  D --> E[libelles.py<br/>repères ↔ éléments]
  E --> G[graphe.py<br/>appuis, travées, consoles,<br/>appuis poutre-sur-poutre]
  G --> M[modèle structurel JSON]
  G --> X[propositions<br/>méthode « geometrie »]
  T --> R[règles de texte<br/>méthode « dxf »]
  X --> F[registre.py<br/>géométrie d'abord,<br/>corroboration, désaccords]
  R --> F
```

**Un module séparé, sans dépendance nouvelle.** `eurostruct_extraction/geometrie/`
ne connaît ni la base, ni le réseau, ni le moteur de calcul. Il n'utilise
qu'`ezdxf` (déjà présent, MIT) et la géométrie plane écrite ici — pas de
`shapely`, pas de bibliothèque native de plus dans l'image.

| fichier | rôle |
|---|---|
| `primitives.py` | parcours de l'espace objet, explosion récursive des `INSERT` (transformation, `MINSERT`), calque et type de ligne **effectifs**, poignées d'origine |
| `noyau.py` | vecteurs, segments, polygones, projections, découpe par une bande, tolérances, quantification |
| `classification.py` | rôle d'un calque, d'un bloc, d'un type de ligne — table multilingue FR/NL/EN/DE, normes AIA (`S-COLS`…) |
| `axes.py` | files, bulles, familles parallèles, entraxes, nœuds de grille |
| `poteaux.py`, `voiles.py` | contours fermés, cercles, hachures, solides, rectangles reconstitués |
| `poutres.py` | bandes (paires de traits parallèles, rectangles allongés), fusion à travers les appuis, poutres filaires |
| `dalles.py` | panneaux entre porteurs, marqueurs en croix, contours sur calque de dalle, trémies |
| `cotes.py` | mesure, texte affiché, `DIMLFAC`, cote forcée, chaînes, rattachement aux éléments |
| `libelles.py` | boîtes orientées des textes, analyse des repères, affectation par coût |
| `graphe.py` | appuis le long de chaque poutre, travées, consoles, poutre sur poutre, nœuds et arêtes |
| `modele.py` | dataclasses gelées du modèle, export JSON (`eurostruct.structure/1`) |
| `propositions.py` | modèle → `Candidat` (méthode `geometrie`), regroupements, confiance |
| `extracteur.py` | `ExtracteurGeometrieDxf` : l'entrée dans la chaîne d'extraction |

**Une seule lecture du fichier.** `lire_dxf` ouvre le document une fois et rend
à la fois les entités de texte (inchangées) et les primitives géométriques.
`DocumentAnalyse` porte les primitives hors représentation (`repr=False`),
comme les octets.

## 2. Lecture des entités

**Espace objet seulement.** Les présentations (cartouche, fenêtres) ne sont
pas un plan.

| entité | ce qui en est tiré |
|---|---|
| `LINE` | un segment |
| `LWPOLYLINE`, `POLYLINE` 2D | des segments ; si fermée, un **contour** ; un arrondi (bulge) devient un arc, jamais une corde |
| `CIRCLE`, `ARC` | cercle (poteau rond, bulle d'axe), arc (non porteur) |
| `SOLID`, `TRACE` | contour rempli (poteau dessiné plein) |
| `HATCH` | contours des chemins polylignes ; un chemin d'arêtes est rendu en segments |
| `TEXT`, `MTEXT`, `ATTRIB` | texte, point d'ancrage, rotation, hauteur, **boîte réelle** (`ezdxf.bbox`, métrique des polices) |
| `DIMENSION` | points de définition, direction, mesure, `DIMLFAC`, texte affiché, texte forcé |
| `INSERT` | nom du bloc, transformation, attributs ; son contenu est **explosé** dans le repère du dessin |

**Les règles du DAO, appliquées.**

* un élément de bloc sur le calque `0` prend le calque de l'`INSERT` ; un type
  de ligne `BYBLOCK` prend celui de l'`INSERT`, `BYLAYER` celui du calque ;
* un calque **éteint ou gelé** n'est pas lu — le plan imprimé ne le montre pas ;
  le compte rendu nomme les calques écartés ;
* la poignée tracée est celle de l'entité **source** dans le bloc
  (`source_of_copy`) **et** celle de l'`INSERT` qui l'a placée : un poteau
  inséré cinquante fois se retrouve cinquante fois ;
* profondeur d'imbrication bornée (8), nombre de primitives borné (200 000) ;
  au-delà, la lecture s'arrête et le statut est `partiel`.

**Refus explicites** (interdiction 6) : une référence externe (`XREF`) n'est
pas dans le fichier — elle est nommée, pas devinée ; les solides 3D, régions
ACIS et entités proxy sont comptés et ignorés ; une grille polaire ou une
poutre courbe est signalée « non prise en charge » au lieu d'être approchée.

## 3. Unités et tolérances

**L'unité de la géométrie est celle du dessin**, `$INSUNITS` (mm, cm, m, in,
ft), citée comme déclaration — exactement la règle déjà suivie pour les cotes.
Le texte « P1 30x60 » n'en hérite toujours pas : `$INSUNITS` dit en quoi les
traits sont tracés, pas en quoi les annotations sont écrites.

**Dessin sans unité (`$INSUNITS = 0`).** L'unité n'est attachée que si deux
sources concordent : une déclaration écrite (« Cotes en cm ») **et** au moins
deux cotes rattachées dont la valeur affichée est la mesure géométrique
(rapport 1, aucune contradiction). La proposition cite les deux. Sinon, les
longueurs sont proposées **sans unité** et ne se reportent qu'après correction.

**Tolérances** (en unités du dessin) : 1 mm réel si l'unité est connue
(0,1 cm ; 0,001 m), sinon 10⁻⁵ de la diagonale de l'emprise. Angles : 0,2°
pour le parallélisme, 1° pour l'équerrage.

**Quantification, pas arrondi** (interdiction 9). Une distance calculée en
flottants (`600.0000000001`) est ramenée au micromètre réel (10⁻⁴ cm) ; la
valeur brute est conservée dans le fondement. Aucune valeur n'est arrondie à
la cote « attendue ».

## 4. Classification : calques, blocs, types de ligne

Chaque primitive reçoit un **rôle** : `axe`, `poteau`, `poutre`, `voile`,
`dalle`, `tremie`, `cote`, `texte`, `armature`, `cadre`, `hachure`, `inconnu`.

| rôle | calques (extraits, insensibles à la casse et aux accents) |
|---|---|
| axe | `axe(s)`, `grid`, `grille`, `trame`, `stramien`, `raster`, `achse(n)`, `S-GRID` |
| poteau | `poteau(x)`, `colonne`, `column`, `col(s)`, `kolom(men)`, `stütze(n)`, `S-COLS` |
| poutre | `poutre(s)`, `retombée`, `linteau`, `beam(s)`, `balk(en)`, `unterzug`, `S-BEAM` |
| voile | `voile(s)`, `mur(s)`, `refend`, `wall(s)`, `wand(en)`, `S-WALL` |
| dalle | `dalle(s)`, `plancher`, `hourdis`, `prédalle`, `slab`, `vloer`, `plaat`, `decke`, `S-SLAB` |
| trémie | `trémie`, `réservation`, `ouverture`, `opening`, `sparing`, `aussparung` |
| cote, texte | `cote(s)`, `cotation`, `dim`, `maatvoering`, `bemassung` ; `texte`, `anno`, `repère`, `légende` |
| armature, cadre | `ferraillage`, `armature`, `wapening`, `bewehrung` ; `cartouche`, `cadre`, `title`, `kader` |

* **Le plus spécifique l'emporte** : un calque `S-BEAM-TEXT` est un calque de
  texte, pas de poutre.
* **Un bloc parle aussi** : `POT30x30`, `COL-400x400`, `AXE`, `BUBBLE`, `NIV` ;
  le rôle d'un bloc prime sur celui de son calque d'insertion.
* **Le type de ligne aussi** : `CENTER`, `DASHDOT`, `ACAD_ISO04W100`… signale un
  axe ; `HIDDEN`, `DASHED` une retombée de poutre vue par-dessous.
* **Un calque générique** (`COFFRAGE`, `STRUCTURE`, `0`) ne classe rien : les
  éléments y sont reconnus par leur **forme et leur position** (§5), avec une
  confiance plus basse, et le fondement le dit.

## 5. Détection des éléments

Chaque élément détecté porte : identifiant stable, géométrie, poignées et
calques sources, **règle de classement** (`calque`, `bloc`, `forme`) et
confiance. Les ordres de parcours sont triés par coordonnées puis poignée : le
résultat ne dépend d'aucun hasard.

### 5.1 Axes (files)

1. **Candidats** : segments de rôle `axe`, ou de type de ligne d'axe sur un
   calque non classé, d'une longueur ≥ 30 % de l'emprise dans leur direction.
   Les segments colinéaires qui se recouvrent sont fusionnés.
2. **Étiquette** : à chaque extrémité, un cercle (bulle) centré sur le
   prolongement de l'axe et contenant un texte court (`A`, `AA`, `A'`, `1`, `12`),
   ou un bloc de bulle avec attribut, ou un texte court posé dans le
   prolongement à moins de trois hauteurs de texte. Une étiquette sert une fois.
   Une étiquette en lettres et chiffres (`L1`, `L10`) n'est lue que dans une
   bulle ou un bloc de bulle, en complément
   ([`GEOMETRIE_BULLES_LETTRES_CHIFFRES.md`](GEOMETRIE_BULLES_LETTRES_CHIFFRES.md)).
3. **Familles** : directions égales à 0,2° près (modulo 180°). Une grille
   tournée de 30° est traitée comme une grille droite.
4. **Entraxes** : dans une famille, les axes triés par décalage ; l'entraxe de
   deux axes voisins est la **distance entre droites parallèles** — exacte.
5. **Nœuds** : intersection d'un axe de chaque famille (`A1` ; `L1/1` quand
   une étiquette mêle lettres et chiffres). Grille polaire ou courbe : non
   prise en charge, signalée.

### 5.2 Poteaux

* **Contours** : polylignes fermées, `SOLID`/`TRACE`, chemins de hachure,
  cercles, et rectangles **reconstitués** à partir de quatre `LINE` (cycle de
  quatre segments à angles droits).
* **Classés par calque ou bloc** (confiance 0,85) : contour fermé,
  élancement ≤ 4, côté entre 15 cm et 2 m si l'unité est connue.
* **Classés par forme** (0,6) sur un calque générique : contour fermé
  **contenant un nœud de grille** (ou centré à moins d'un demi-côté), plein
  (hachure, solide) ou non, côté ≤ 30 % de l'entraxe médian. Hors nœud, un
  rectangle isolé n'est pas un poteau : c'est souvent une coupe ou un détail.
* **Doublons fusionnés** : un poteau dessiné en contour **et** en hachure est un
  seul poteau, avec deux preuves.
* **Dimensions** : rectangle → deux côtés dans le repère de la grille
  (largeur selon la première famille, profondeur selon la seconde), angle
  noté ; cercle → diamètre ; polygone quelconque → emprise dans le modèle,
  aucune dimension proposée.

### 5.3 Voiles

Contours fermés sur calque de voile, ou paires de traits parallèles sur ce
calque, d'élancement ≥ 4 et d'épaisseur ≤ 60 cm si l'unité est connue.
Épaisseur = petit côté ; axe = ligne médiane. Un contour de voile composite
(en L, en T) reste un **appui** — l'intersection d'un polygone quelconque avec
une bande se calcule — mais aucune épaisseur n'en est proposée.

### 5.4 Poutres

1. **Bandes** : deux segments parallèles (0,2°), en recouvrement (≥ 30 % du
   plus court, ou ≥ deux largeurs), écartés d'une largeur plausible (10 cm à
   1,5 m si l'unité est connue ; sinon ≤ 25 % de l'entraxe médian). Chaque
   trait s'apparie à son **plus proche** voisin parallèle de chaque côté :
   deux poutres voisines ne fusionnent pas. Un rectangle fermé allongé
   (élancement ≥ 3) est une bande à lui seul.
2. **Rôle** : bande sur calque de poutre → 0,8 ; sur calque générique → poutre
   **seulement si elle touche au moins deux appuis** (poteaux, voiles) → 0,6.
   Une bande de calque de voile est un voile.
3. **Fusion** : deux bandes colinéaires, de même largeur, séparées par un
   intervalle **entièrement couvert par un appui** sont une seule poutre
   (dessinée interrompue aux poteaux). Le fondement dit « fusion à travers
   l'appui ».
4. **Poutre filaire** : un trait seul sur calque de poutre (plans de charpente)
   est un axe de poutre de largeur inconnue — utilisable pour les portées,
   jamais pour une largeur.

### 5.5 Dalles et trémies

* **Panneaux** : cellules de la grille dont l'intérieur ne contient ni poteau
  ni voile, et dont les côtés sont portés (poutre ou voile sur ≥ 80 % du côté).
  Chaque côté est dit « porté par P1 » ou « bord libre ». Dimensions : entre
  axes et entre nus.
* **Contours de dalle** sur calque de dalle : repris tels quels.
* **Marqueur en croix** couvrant la cellule (diagonales d'angle à angle) :
  confirme le panneau ; une croix dans un **petit** rectangle est une
  **trémie** (comme un contour sur calque de trémie).
* **Épaisseur** : le texte « Dalle pleine ép. 20 » lu par les règles de texte
  est **rattaché** au panneau qui le contient ; la géométrie d'un plan ne
  montre pas une épaisseur, elle ne l'invente pas.

### 5.6 Cotes

* **Mesure** : `get_measurement()` (distance projetée sur la direction de la
  cote) ; **valeur affichée** = mesure × `DIMLFAC` (style et surcharges), sauf
  texte forcé.
* **Cote forcée discordante** : un texte numérique qui diffère de la valeur
  affichable (au demi-dernier chiffre près) est signalé — c'est le piège
  classique d'un plan « hors échelle ». La mesure est citée à côté.
* **Rattachement** : chaque point de définition est accroché (tolérance) à un
  axe, un centre d'appui, une face d'appui, une face de poutre, une face de
  poteau. La paire de crochets dit ce que la cote mesure : entraxe, entre-axes
  d'une travée, nu à nu, largeur de poutre, côté de poteau.
* **Chaînes** : cotes de même direction et même ligne de cote ; la somme des
  partielles est comparée à la cote globale quand elle existe.
* Une cote rattachée **corrobore** (ou contredit) la valeur géométrique ; elle
  ne devient pas une proposition de plus. Une cote non rattachée reste une
  « cote » comme aujourd'hui — avec `DIMLFAC` appliqué.

### 5.7 Niveaux

Textes de niveau (« Niv. +3,20 », « +3.20 », « ±0,00 ») et blocs de niveau
avec attribut. Le modèle les situe ; les propositions de niveau restent celles
des règles de texte (convention du mètre, déjà en place).

### 5.8 Repères (labels)

* **Boîte orientée** de chaque texte : ancrage, alignement, rotation, hauteur,
  largeur réelle. Un texte vertical (90°, 270°) est une étiquette comme une
  autre — le PDF le perdait, le DXF le lit.
* **Analyse** : `P1`, `PT3`, `B12`, `L1` (poutres), `C1`, `PO2`, `K4`
  (poteaux), `V1`, `M3`, `W2` (voiles), suivis éventuellement d'une section
  `30x60`, `(30/60)`, `30×60`.
* **Affectation par coût** : distance de la boîte à l'élément rapportée à la
  hauteur de texte, + pénalité si l'orientation n'est pas parallèle à la
  poutre, + pénalité si le préfixe suggère un autre type, − bonus si la section
  écrite concorde avec la largeur mesurée. Seuil : quatre hauteurs de texte ou
  1,5 largeur d'élément. Appariement glouton par coût croissant ; un repère
  sert une fois.
* **Un repère par travée** quand le dessin en porte plusieurs sur une même
  bande (P1 de A à B, P2 de B à C — même rectangle, retombées différentes) ;
  un repère unique sur une poutre continue s'étend à toutes ses travées, et le
  fondement le dit.
* **Sans repère**, un élément reçoit un repère de grille : `1:A-B` (poutre sur
  la file 1 de A à B), `A1` (poteau au nœud A1). Jamais `None` pour une valeur
  propre à un élément : une proposition sans repère serait préremplie pour
  **tous** les éléments.

## 6. Graphe et calcul des portées

### 6.1 Le graphe

```mermaid
graph LR
  A1((C1 · A1)) -- "P1 · travée 1/2<br/>entre-axes 600 · nu à nu 570" --- B1((C1 · B1))
  B1 -- "P2 · travée 2/2<br/>450 · 420" --- C1((C1 · C1))
  B1 -- "P5 · 600 · 570" --- B2((C1 · B2))
  A2((C1 · A2)) -- "P3" --- B2
  B2 -- "P4" --- C2((C1 · C2))
```

* **Nœuds** : appuis (poteaux, voiles), nœuds de grille de référence.
* **Arêtes** : travées (poutre, de l'appui `i` à l'appui `i+1`) ; « porte »
  (poutre secondaire **portée par** une poutre principale) ; « croisement »
  (deux poutres continues qui se croisent — aucune ne porte l'autre).
* Chaque travée connaît ses deux appuis, leurs nus, leurs largeurs, son nœud
  de grille de départ et d'arrivée.

### 6.2 Les appuis d'une poutre

Pour une bande d'axe `o + t·u`, de normale `n`, de largeur `b`, d'intervalle
`[t₀, t₁]` :

1. **Candidats** : poteaux, voiles et autres poutres dont le contour
   intersecte la bande prolongée de `e = max(tolérance, 0,1·b)` à chaque bout
   (un trait qui s'arrête à 1 cm du nu touche son appui).
2. **Nus** : le contour est découpé par la bande `|n·(x − o)| ≤ b/2` ; sa
   projection sur `u` donne l'intervalle `[a, c]` occupé par l'appui le long de
   la poutre. **Largeur d'appui** `t = c − a`. **Centre** : projection du
   centre du poteau ; pour un voile traversant, milieu de `[a, c]` (son axe).
3. **Poutre sur poutre** : pour une poutre `Q` non parallèle (≥ 30°), le point
   `J` d'intersection des axes est un appui de la poutre **si `J` est à une
   extrémité de la poutre et à l'intérieur de `Q`** (jonction en T : `Q`
   continue, la poutre s'y arrête). Intérieur aux deux : croisement, aucun
   appui. Extrémité des deux : angle sans appui — signalé.
4. **Fusion** : deux appuis qui se recouvrent le long de la poutre (poteau et
   poutre au même nœud) n'en font qu'un ; le poteau prime, la poutre est notée.
5. **Tri** par centre.

### 6.3 Travées, consoles, refus

Entre deux appuis consécutifs `Sᵢ`, `Sᵢ₊₁` :

```
entre-axes   L  = centre(Sᵢ₊₁) − centre(Sᵢ)
nu à nu      Lₙ = a(Sᵢ₊₁) − c(Sᵢ)
largeurs     tᵢ = c(Sᵢ) − a(Sᵢ),  tᵢ₊₁ = c(Sᵢ₊₁) − a(Sᵢ₊₁)
```

* **Console** : si la poutre dépasse le premier (ou dernier) appui de plus que
  la tolérance, la partie en porte-à-faux est une console : longueur depuis le
  centre de l'appui et depuis son nu.
* **Refus** (aucune valeur inventée) : poutre sans aucun appui → « aucun
  appui trouvé », aucune portée ; `Lₙ ≤ 0` (appuis qui se recouvrent) →
  signalé ; extrémité sans appui ni prolongement plausible → « appui non
  trouvé à l'extrémité x = … ». Ces cas vont dans `unresolved`, avec la raison.

### 6.4 Exemple : S-101, poutre P1/P2

La bande de la file 1 (rectangle `x ∈ [−15, 1065]`, `y ∈ [−15, 15]`, cm) coupe
trois poteaux pleins 30×30 centrés en A1, B1, C1 :

| appui | nus `[a, c]` | centre | largeur |
|---|---|---|---|
| C1 · A1 | [−15, 15] | 0 | 30 |
| C1 · B1 | [585, 615] | 600 | 30 |
| C1 · C1 | [1035, 1065] | 1050 | 30 |

* travée 1 (repère **P1**, texte au-dessus de A–B) : entre-axes **600**, nu à
  nu **570** ; la cote `600` du calque `COTES` est accrochée aux axes A et B, qui
  passent par les centres : **concordante** ;
* travée 2 (repère **P2**) : **450**, **420** ;
* aucune console : la bande s'arrête aux nus extérieurs de A1 et C1.

Aucun texte du dessin n'écrit « portée ». Les deux valeurs sont mesurées.

## 7. Correspondance géométrie → champs d'ingénierie

| mesure géométrique | catégorie | champ de l'étude |
|---|---|---|
| largeur de bande | `beam_width` | **b** |
| entre-axes d'une travée | `beam_span` | **l_eff**, avec l'avertissement existant (§5.3.2.2) |
| nu à nu d'une travée | `beam_clear_span` (nouvelle) | revue seulement |
| porte-à-faux | `cantilever_length` (nouvelle) | revue seulement |
| côtés d'un poteau rectangulaire / diamètre | `column_width`, `column_depth`, `column_diameter` | revue seulement (largeurs d'appui) |
| épaisseur de voile | `wall_thickness` | revue seulement |
| entraxe de deux files voisines | `grid_spacing` | revue seulement |
| axes extrêmes d'une famille (≥ 3 axes) | `building_dimension` | revue seulement |
| étiquette d'axe | `grid_line` | revue seulement |
| hauteur de poutre, épaisseur de dalle | — | **jamais géométriques** en plan : elles viennent du texte (« P1 30x60 », « ép. 20 ») ou d'une coupe |

**Pourquoi l_eff n'est pas calculée ici.** `l_eff = Lₙ + a₁ + a₂`,
`aᵢ = min(h/2 ; tᵢ/2)` (EN 1992-1-1 §5.3.2.2, figure 5.4) demande la hauteur `h`
— un texte, pas un trait — et une hypothèse sur la nature de l'appui. Calculer
une proposition à partir d'autres propositions **non confirmées** ferait
entrer dans une valeur « tracée » des entrées que personne n'a retenues ; et la
règle d'Eurocode appartient au moteur. Le module rend donc les **faits
géométriques** (`L`, `Lₙ`, `t₁`, `t₂`) ; la revue les montre côte à côte, et
l'entre-axes se reporte dans `l_eff` avec l'avertissement. (Pour mémoire :
quand `tᵢ/2 ≤ h/2` aux deux appuis — poteaux plus étroits que la retombée,
centrés sur les axes — la formule redonne `L` ; c'est à l'ingénieur de le
constater, pas à la lecture du plan.)

**Regroupements.** Les poteaux de même repère et mêmes dimensions forment
**une** proposition (« C1 30×30 — 6 occurrences »), avec la liste des
instances dans `position`. Une travée, une largeur de poutre, un entraxe : une
proposition chacun.

## 8. Priorité de la géométrie, et confrontation avec le texte

* **Ordre de la chaîne pour un DXF** : géométrie → règles de texte → entités
  (cotes et étiquettes non absorbées). Les cotes et les étiquettes d'axes que
  la géométrie a rattachées ne sont plus proposées une seconde fois.
* **Corroboration** : une proposition de texte identique (catégorie, valeur,
  unité, repère) à une proposition géométrique n'est pas dupliquée ; elle
  s'ajoute au fondement de la proposition géométrique (`corroborated_by` :
  méthode, texte, position), confiance + 0,05 (plafond 0,90).
* **Désaccord** : même catégorie et même repère, valeurs différentes (largeur
  mesurée 30, texte « P1 25x60 ») : les **deux** propositions restent, chacune
  porte `conflicts_with`. L'ingénieur tranche ; rien n'est choisi pour lui.
* **Entre documents** (un PDF et le DXF du même plan) : au préremplissage, les
  candidats d'un même champ sont ordonnés géométrie → texte DXF → texte PDF →
  vision → OCR ; à valeurs égales, la provenance retenue est celle de la
  géométrie. Un conflit reste un conflit : la priorité **ordonne**, elle ne
  tranche pas.

## 9. Le modèle structurel (sortie)

Stocké dans `documents.analysis_report.structure` — figé avec les
propositions, comme le reste du compte rendu — et servi par une route dédiée.
Extrait **réel** de la lecture de S-101 (un élément par liste ; le modèle
complet compte 5 axes, 6 poteaux, 3 poutres, 5 travées, 2 dalles, 6 cotes) :

```json
{
  "schema": "eurostruct.structure/1",
  "units": {
    "drawing": "cm", "basis": "declaration", "source": "$INSUNITS",
    "insunits": 5, "tolerance": 0.1, "quantum": 0.0001
  },
  "grid": [
    {
      "id": "grid:A", "label": "A", "name": "A", "family": 1,
      "line": [[0, -90], [0, 700]], "confidence": 0.85,
      "label_source": {"via": "bulle", "handle": "93"},
      "evidence": {
        "handles": ["91"], "layers": ["AXES"], "classified_by": "calque"
      }
    }
  ],
  "columns": [
    {
      "id": "column:A1", "mark": "C1", "shape": "rectangle", "centre": [0, 0],
      "width": 30, "depth": 30, "grid_node": "A1", "filled": true,
      "confidence": 0.65,
      "evidence": {
        "handles": ["E4"], "layers": ["COFFRAGE"], "classified_by": "forme"
      }
    }
  ],
  "beams": [
    {
      "id": "beam:1", "marks": ["P1", "P2"], "width": 30,
      "axis": [[-15, 0], [1065, 0]], "drawn_as": "rectangle",
      "supports": ["column:A1", "column:B1", "column:C1"],
      "spans": ["span:1.1", "span:1.2"], "supported_by_beams": [],
      "merged_through": [], "confidence": 0.6
    }
  ],
  "spans": [
    {
      "id": "span:1.1", "beam": "beam:1", "kind": "span", "mark": "P1",
      "index": 1, "count": 2,
      "from": {
        "support": "column:A1", "kind": "poteau", "centre": 0,
        "faces": [-15, 15], "width": 30, "grid_node": "A1",
        "touching_only": false, "gap": 0
      },
      "to": {
        "support": "column:B1", "kind": "poteau", "centre": 600,
        "faces": [585, 615], "width": 30, "grid_node": "B1",
        "touching_only": false, "gap": 0
      },
      "line": [[0, 0], [600, 0]], "axis_length": 600, "clear_length": 570,
      "dimensions": [
        {
          "handle": "A1", "measures": "axis_length", "measured": 600,
          "displayed": "600", "measure_agrees": true, "forced_mismatch": false
        }
      ],
      "confidence": 0.65
    }
  ],
  "slabs": [
    {
      "id": "slab:A-B/1-2", "kind": "panneau",
      "edges": [
        {"side": "A", "supported_by": null},
        {"side": "2", "supported_by": "P3"},
        {"side": "B", "supported_by": "P5"},
        {"side": "1", "supported_by": "P1"}
      ],
      "lx": 600, "ly": 600, "cross_marker": true, "crossed_by": [],
      "label": "Dalle pleine ép. 20", "confidence": 0.7
    }
  ],
  "levels": [
    {
      "value": 3.2,
      "mentions": [
        {
          "text": "Niv. +3,20 — Échelle 1/50", "point": [1165, -460],
          "handle": "131"
        }
      ]
    }
  ],
  "graph": {
    "edges": [
      {
        "id": "span:1.1", "type": "beam_span", "beam": "beam:1", "mark": "P1",
        "from": "column:A1", "to": "column:B1", "axis_length": 600,
        "clear_length": 570
      }
    ]
  },
  "unresolved": [],
  "counts": {
    "grid_axes": 5, "grid_nodes": 6, "columns": 6, "walls": 0, "beams": 3,
    "spans": 5, "cantilevers": 0, "slabs": 2, "openings": 0, "dimensions": 6,
    "levels": 1, "unresolved": 0
  }
}
```

Les clés sont en anglais, comme le reste du contrat d'API ; les valeurs sont
en unités du dessin, l'unité dite une fois en tête.

## 10. Base, API, écran

**Migration 0029** — la 0028 n'est pas modifiée :

* `extraction_is_traced` est remplacée à l'identique, avec une méthode de plus,
  `geometrie` (`not valid`, comme l'originale) ;
* le commentaire de `extractions.method` le dit ;
* aucune table, aucune primitive, aucun rôle nouveau : les catégories sont déjà
  libres (`^[a-z][a-z0-9_]{1,63}$`), le compte rendu est déjà un `jsonb`.

**API**

| route | ce qu'elle rend |
|---|---|
| `GET /v1/projects/{id}/documents/{doc}/structure` (nouvelle) | le modèle structurel typé (`StructureDuDocument`, contrat fermé `ModeleStructurel`), ou un refus 404 s'il n'y en a pas |
| `GET …/documents` | `has_structure` et un résumé (`structure_summary` : nombres d'axes, poteaux, poutres, travées, éléments non résolus) ; le modèle complet n'y voyage pas |
| `GET …/extractions` | `source_type` par proposition : `text`, `ocr`, `cad_text`, `geometry`, `vision` |
| `GET …/extractions/prefill` | candidats ordonnés par source (§8) ; `source_type` et `source_label` sur chaque champ et chaque candidat d'un conflit |

Le contrôle de provenance au calcul est **inchangé** : une valeur géométrique
confirmée s'y vérifie comme les autres — égalité exacte avec la décision
enregistrée.

**Écran de revue**

* une **pastille de source** par ligne — Géométrie DXF, Texte DXF, Texte PDF,
  OCR, Vision — et un filtre par source ;
* pour une ligne géométrique : la dérivation (« appuis C1 · A1 → C1 · B1 ;
  entre-axes 600 ; nu à nu 570 ; largeurs 30/30 ; cote 600 concordante ») ;
* « corroborée par … » et « en désaccord avec … » écrits sur la ligne ;
* un panneau **Modèle structurel** pour un DXF : la grille, les poteaux, les
  voiles, les poutres et leurs repères, les travées et leurs longueurs, les
  dalles, les éléments non résolus en rouge ; la ligne de revue sélectionnée
  est surlignée sur le dessin. L'ingénieur voit **ce qui a été compris** avant
  de confirmer ce qui en est tiré.

## 11. Confiance

Indicative, jamais une probabilité ; strictement inférieure à 1 (contrainte de
0028), plafonnée à 0,90 comme la vision.

| élément | base | ajustements |
|---|---|---|
| axe étiqueté (calque/type de ligne d'axe) | 0,85 | sans étiquette 0,6 |
| poteau | calque/bloc 0,85, forme 0,6 | section écrite concordante + 0,05 ; discordante : `conflicts_with` |
| poutre (largeur) | calque 0,8, forme 0,6 | idem |
| travée (entre-axes, nu à nu) | min(poutre, appuis) | cote concordante + 0,05 ; appui poutre-sur-poutre × 0,9 ; cote forcée discordante : plafond 0,4 |
| unité absente | − 0,2 | |

## 12. Plan de réalisation

1. **Ce document.**
2. **Base** — `0029_extraction_geometrie.sql`, garanties SQL (méthode admise,
   inconnue refusée), mise à niveau 28 → 29.
3. **Module** — `geometrie/` complet ; correction de `DIMLFAC` dans
   l'extracteur d'entités ; chaîne DXF géométrie d'abord, corroboration,
   désaccords. Tests sur des DXF **fabriqués par les tests** : S-101 (calque
   générique, formes), plan à calques normés (blocs de poteaux tournés, bulles
   à attributs, poutres en paires de traits, poutre sur poutre, voile porteur,
   poutre continue, console, cote forcée), dessin sans calques (type de ligne
   d'axe, hachures), grille tournée de 30°, `$INSUNITS = 0` avec et sans
   déclaration, cas refusés (XREF, poutre courbe, grille polaire), grand plan
   (20 × 20 files) en temps borné.
4. **API et contrats** — route du modèle, `source_type`, ordre de priorité,
   schémas exportés en TypeScript ; tests sans base et harnais PostgreSQL
   (dépôt du DXF S-101, travée confirmée, report de `l_eff`, calcul accepté).
5. **Écran** — pastilles, filtre, dérivation, panneau du modèle ; parcours
   Chromium avec un DXF.
6. **Documentation, campagne sur SHA gelé, recette de mise à niveau, push.**

## 13. Ce que ce lot ne fait pas, et le dit

* **Il ne lit toujours pas le DWG** : exporter en DXF.
* **Il ne lit pas la géométrie d'un PDF** vectoriel : le chemin existe
  (pdfplumber rend les traits), il n'est pas dans ce lot.
* **Il ne calcule pas l_eff** (§7) et ne déduit aucun schéma statique (continu,
  isostatique) de la géométrie.
* **Il ne voit pas la troisième dimension** : hauteurs de poutre, épaisseurs
  de dalle et niveaux restent des textes.
* **Domaine reconnu** : grilles droites (éventuellement tournées), poutres
  rectilignes en paires de traits ou rectangles, poteaux en contours fermés,
  cercles, hachures ou blocs. Le reste — courbes, grilles polaires, références
  externes — est signalé, pas approché.
* **Le rappel n'est pas mesuré sur des plans réels** : les plans éprouvés sont
  fabriqués par les tests, et les conventions des bureaux varient.

### Interdictions concernées

| interdiction | où elle est tenue |
|---|---|
| 1 — aucun résultat par un LLM | aucun modèle de langage ; règles géométriques déterministes, triées |
| 2 — aucune valeur non tracée | poignées sources et d'insertion, calques, règle de classement, unité citée (`$INSUNITS` ou déclaration + cotes concordantes) |
| 5 — aucune cote extraite sans confirmation | méthode `geometrie` entre `proposed` comme les autres ; même décision nommée, même contrôle au calcul |
| 6 — rien hors du domaine | refus nommés : XREF, courbes, grilles polaires, poutre sans appui |
| 7 — pas de « DWG natif » | inchangé |
| 9 — aucun arrondi complaisant | quantification au micromètre réel, valeur brute conservée ; cote forcée discordante signalée, jamais « corrigée » |

## 14. Ce qui a été réalisé, et ce qui l'a mesuré

Les commits, dans l'ordre du §12 :

| commit | contenu |
|---|---|
| `3eb7ecb` | ce document, avant le code |
| `ad95fea` | migration `0029` et ses garanties SQL (`07_extraction_geometrie.sql`) |
| `cfd4e52` | module `geometrie/` ; chaîne DXF « géométrie d'abord », corroboration et confrontation ; `DIMLFAC` ; extracteur en version 0.2.0 ; tests sur plans fabriqués |
| `3b125dc` | API : modèle enregistré avec l'analyse, route `/structure`, `source_type`, priorité au préremplissage ; contrats TypeScript ; harnais PostgreSQL |
| `6937e7e` | le tracé de chaque travée dans le plan (`line`), pour l'écran |
| `9f436e0` | écran : pastilles et filtre de source, dérivation, confrontations, modèle dessiné, désignation croisée ; quatrième parcours Chromium |
| `1b26ef8` | refus nommé d'une grille polaire (promis au §13, d'abord écrit seulement en commentaire) |
| `a6711ed` | le préremplissage dit la source de chaque champ et de chaque candidat d'un conflit (promis au §10) |

### 14.1 Ce que les plans fabriqués établissent

Aucun plan réel : chaque DXF est produit par `extraction/tests/fabrique_geometrie.py`.

| plan | ce qui en est lu |
|---|---|
| **S-101** (coffrage, cm, tout sur le calque générique `COFFRAGE`) | 5 axes par leurs bulles, 6 poteaux 30 × 30 aux nœuds, 3 poutres, **5 travées : P1 600/570, P2 450/420, P3 600/570, P4 450/420, P5 600/570 cm** (entre-axes / nu à nu), chacune confirmée par la cote du dessin ; 2 dalles portées sur leurs bords ; la coupe au 1/20 reste hors du modèle. **Aucun texte du plan n'écrit une portée.** 26 propositions géométriques, 7 corroborées par le texte (« P1 30x60 », « C1 30x30 ») |
| S-101 tourné de 30° | les mêmes portées, les mêmes sections |
| S-101 sans `$INSUNITS` | avec « Toutes les cotes sont en cm » : l'unité est attachée (mention **et** cotes concordantes), portées en cm ; sans la mention : longueurs sans unité, confiance − 0,2, rien ne se reporte |
| S-101 + « Portée P1 : 6,00 m » | le texte **corrobore** la mesure (600 cm = 6,00 m, confiance + 0,05) |
| S-101 + « Portée P1 : 6,50 m » | les deux propositions restent, chacune nomme l'autre (`conflicts_with`) |
| **charpente AIA** (mm, `S-GRID`, `S-COLS`, `S-BEAM`…) | poteaux en blocs, dont un tourné de 90° (500 × 300) ; bulles à attribut ; poutres en paires de traits **interrompues au poteau** et réunies à travers lui ; **console** de 1 500 mm au-delà du nu ; poutre **sur voile** 6 000 / 5 700 ; **solive portée par deux poutres** 5 000 / 4 700 (« B1 → B3 ») ; une cote forcée « 6000 » sur un entraxe de 5 800 **plafonne la confiance à 0,4** et le dit |
| calque `0`, en mètres | axes reconnus par leur type de ligne, poteaux hachurés par leur forme et leur position ; portées 6 m ; axes non étiquetés nommés `famille.rang` — aucune lettre inventée |
| refus | référence externe, poutre courbe, poutre sans appui : nommées dans `unresolved`, **aucune proposition** ; une grille de six axes rayonnants : nommée « grille polaire », ni files ni nœuds, ses étiquettes restent des textes lus |
| grille 20 × 20 | 400 poteaux, 760 travées, 361 dalles en **0,5 s** |

### 14.2 Mesures

| surface | résultat |
|---|---|
| module d'extraction (`pytest`) | **219 tests verts**, dont 66 unitaires de géométrie (noyau, classification en quatre langues, repères) et 27 sur les plans fabriqués |
| suite SQL complète sur `ad95fea` | verte, `07_extraction_geometrie.sql` compris (arbre isolé) |
| `db/test/documents_extractions.sh` | **32 cas verts**, dont : un DXF qui n'écrit aucune portée est déposé, son modèle lu par la route, la portée P1 mesurée (600 cm) confirmée, reportée en `l_eff` = 6 000 mm, et le calcul l'accepte avec une provenance « géométrie du dxf » |
| API sans base, moteur | API sans base : 256 tests verts ; moteur 1 138 ; audit de dépendances du moteur vert ; contrat TypeScript à jour |
| `db/test/parcours_livrable.sh` | **quatre parcours Chromium verts sur une même pile** — livrable, vérification complète, lecture des plans, **géométrie d'un DXF** : 26 valeurs mesurées et 28 lues dans le texte du DXF, séparées et comptées comme en base ; modèle dessiné ; P1 A1 → B1, 600 / 570 cm ; `l_eff` = 6 000 mm reporté et accepté au calcul avec l'origine « géométrie du dxf » |

### 14.3 Écarts au plan, et pourquoi

* **Une cote à `DIMLFAC ≠ 1` n'hérite plus de `$INSUNITS`.** Le plan prévoyait
  seulement de multiplier la mesure par `DIMLFAC`. Mais un dessin en mètres coté
  en centimètres (`DIMLFAC = 100`) et un détail au 1/20 (`DIMLFAC = 0,4`) ne se
  distinguent pas : le nombre affiché n'est pas dans l'unité du dessin. Seule
  une mention écrite (« Cotes en cm ») lui en donne une ; sinon il reste sans
  unité et ne se reporte pas.
* **Seuil des repères : six hauteurs de texte**, non quatre — une étiquette
  posée sous un poteau, décalée d'un trait de rappel, n'était pas lue ; pour un
  poteau, la porte est aussi deux fois sa plus grande dimension.
* **Un groupe de poteaux sans repère garde un repère nul.** Le §5.8 voulait un
  repère de grille pour chaque élément ; un groupe couvre plusieurs nœuds, il
  n'en a pas un seul. Sans effet sur le report : aucune catégorie de poteau ne
  renseigne un champ de l'étude.
* **Une poutre sans appui ne propose rien**, pas même sa largeur : elle est
  dans `unresolved`, et un élément non résolu ne fournit aucune valeur.
* **Un panneau traversé par une poutre n'est pas subdivisé** : il la cite
  (`crossed_by`).
* **Un niveau écrit plusieurs fois est un niveau** (`levels[].mentions`).
* **Le pas de quantification est décimal** (1 µm réel ramené au pas décimal
  inférieur : 1e-5 in, 1e-6 ft ; sans unité, 1e-8 de la diagonale ramené de
  même) : sans cela, l'entre-axes 450 d'un dessin sans unité s'écrivait
  450,00001.
* **Clés des cotes** : `measure_agrees` (les points de définition mesurent
  l'élément) et `forced_mismatch` (le texte forcé contredit la mesure), au lieu
  d'un seul `agrees` qui confondait les deux.
* **Chaque travée porte son tracé** (`line`) : l'écran dessine sans refaire de
  géométrie.
* **Performance** : la première mesure sur la grille 20 × 20 était de 5,7 s
  (détection des poteaux et réunion des poutres quadratiques) ; un index
  spatial la ramène à 0,5 s.

### 14.4 Campagne sur SHA gelé : `3c5638f`

Dans un arbre isolé (worktree détaché), avec son propre environnement Python
installé depuis cet arbre, et rien d'autre sur la base pendant la campagne :

| surface | résultat |
|---|---|
| `run_tests.sh --require-db` | **COMPLET — 7 surfaces vertes** : moteur 1 138, importeur 113, extraction 219, API 594 collectés (256 réussis ici, 338 exécutés par les harnais de la surface SQL), 30 barrières de harnais toutes refusantes, **15 groupes de garanties SQL** (un de plus : `07_extraction_geometrie.sql`), cohérence (seed, contrat TypeScript, dépendances du moteur, moteur sans avertissement) |
| `mise_a_niveau_active.sh` depuis `da01259` | **TENU** — 26 → 29 : installation ancienne peuplée par son propre produit, diagnostic sans modification, quatre refus, concurrence refusée, relance idempotente, restauration isolée identique ligne pour ligne, interruption reprise, études et livrables relus aux mêmes empreintes et aux mêmes octets |
| `mise_a_niveau_active.sh` depuis `fb39867` | **TENU** — 28 → 29, mêmes pas ; 10 tables métier identiques ligne pour ligne, 3 livrables aux mêmes octets |
| `parcours_livrable.sh` | **quatre parcours Chromium verts**, dont la géométrie d'un DXF (26 valeurs mesurées, 28 lues dans le texte du DXF ; `l_eff` = 6 000 mm accepté au calcul) ; capture de la revue et du modèle dessiné prise par le parcours, non commitée |
| intégration continue sur `3c5638f` | « eurostruct — tests » **vert** (push et PR). « EUROSTRUCT » rouge sur les **quatre mêmes travaux, aux mêmes pas**, qu'avant ce lot sur `fb39867` : image MinIO refusée par le registre (deux travaux), tests du moteur, « Migrations et garanties structurelles » — non causé par ce lot, non diagnostiqué ici |

**Ce que la recette de mise à niveau n'exerce pas.** Elle peuple l'ancienne base
par l'ancien produit — projets, études, variantes, livrables —, pas par des
documents ni des propositions. Le passage à 0029 de propositions **déjà
décidées** n'est donc pas mesuré par elle ; il repose sur la forme de 0029
(contrainte remplacée à l'identique plus une méthode, `not valid`, aucune ligne
relue ni réécrite) et sur sa postcondition.

**Après le SHA gelé** : `682d91c` corrige un libellé de la revue (« unité
celle du dessin », non « unité unité du dessin »), vu sur la capture ;
vérifié par le typage seulement. Puis ce compte rendu.

### 14.5 Sur des fichiers réels : robustesse, pas encore un plan de structure

Aucun plan de structure réel n'est disponible dans cet environnement. Les 36
DXF réels des tests d'intégration d'`ezdxf` 1.4.4 (exports AutoCAD R12 à
R2018, ASCII et binaires, un relevé Leica Disto, fichiers volontairement
abîmés : poignées dupliquées ou vides, données après EOF, blocs sans nom) ont
été lus par toute la chaîne. Ce ne sont **pas** des plans de structure : ils
éprouvent qu'un vrai fichier de DAO ne fait ni planter la lecture ni inventer
d'élément.

* **aucun plantage, aucun élément inventé** : 0 poteau, 0 poutre, 0 travée,
  0 proposition sur les 36 ;
* **un défaut trouvé** : 27 s pour 419 traits, 11 s pour 25, 31 s pour un
  fichier de 144 octets portant un seul cercle. Dans un dessin sans unité ni
  grille, les cases de l'index spatial valent 1e-5 de la diagonale et une
  recherche les parcourait toutes. Corrigé par `c771cc5` (une recherche est
  bornée par les cases occupées ; une boîte trop grande est rangée à part) :
  **1,4 s pour les 36 fichiers**, 0,3 s au plus ; tests de non-régression
  ajoutés. Vérifié par le module d'extraction (221 tests), l'API sans base et
  `documents_extractions.sh` (32 cas) — pas par une nouvelle campagne entière.

### 14.6 Non mesuré, et à ne pas annoncer

Le **rappel sur des plans réels** de bureau d'études : tous les plans éprouvés
sont fabriqués par les tests, et les conventions de dessin varient. La lecture
dans la composition Docker et sur Supabase (`SUPABASE_UNVERIFIED`), comme pour
la lecture des plans en général.
