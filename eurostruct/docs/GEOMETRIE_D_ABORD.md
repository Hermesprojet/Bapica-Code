# Extraction « géométrie d'abord » — conception

> **Statut : conception ; phases G1 et G2 réalisées (§ 11), G3 à G6 à
> faire.** Ce document décrit comment
> reconnaître les axes, les poteaux, les pieux et les voiles d'un DXF sans
> dépendre des noms de calques et de blocs, dans l'ordre de preuve demandé :
> **1. information DXF standard, 2. géométrie, 3. noms**. Il fait suite à
> `AUDIT_GENERALISATION.md` (risques 2, 3, 6 et durcissements D3, D5, D7, D10).
>
> Les mesures citées ont été faites hors du dépôt, sur le plan de
> développement (DXF de fondations, un bureau belge) **en ignorant tout nom** ;
> la référence est le modèle du produit sur ce plan (`0.4.0`), vérifié lors des
> campagnes précédentes. Ni le plan ni les scripts de mesure ne sont dans le
> dépôt.

## 0. Résumé

| | Aujourd'hui sans noms | Avec ce plan (mesuré ou estimé sur le plan réel, sans aucun nom) |
|---|---|---|
| Axes | 0 / 71 | **66 / 71, 0 faux** (mesuré : bulles + motif trait-point) |
| Étiquettes | 0 / 61 | **61 / 61** (mesuré : lues dans les bulles) |
| Pieux | 0 / 477 | **475 / 477, 0 faux** (mesuré : répétition d'un diamètre) |
| Poteaux | 0 / 64 (et +103 faux poteaux dès que les pieux ne sont plus nommés) | ≈ 64, ≈ 2 faux (estimé : exclusion géométrique des pieux) |
| Voiles | 25 hachures, 0 voile nommé retrouvé | non mesurable sur ce plan (§ 6.5) ; règle durcie, candidats montrés |

**Principe.** Une détection est décidée par une **signature** : un ensemble de
critères DXF standard (N1) et géométriques (N2) propre à chaque objet. Une
signature complète décide seule ; une signature partielle fait un
**candidat**, montré à la revue et jamais proposé, sauf si un nom (N3) ou une
partition apprise la complète. Un nom ne contredit jamais une signature
complète : le désaccord est dit (`unresolved`) et la confiance baisse.

**Ce qui ne change pas.** Les interdictions : aucune valeur sans source
tracée (2), aucune dimension utilisée sans confirmation humaine (5), refus
explicite hors du domaine validé (6). Un plan dont les noms sont reconnus et
concordent avec la géométrie doit donner le même modèle qu'aujourd'hui ;
chaque écart sera expliqué.

## 1. Les trois niveaux de preuve

### 1.1 N1 — information DXF standard

Ce que la référence DXF définit, et qu'aucun renommage ne change :

| Information | Codes / source | Usage |
|---|---|---|
| Type d'entité | `CIRCLE`, `LWPOLYLINE` fermée (code 70), `HATCH`, `SOLID`, `DIMENSION`, `INSERT`/`ATTRIB`, `MLINE` | Forme de base ; `MLINE` = voile candidat explicite. |
| **Motif du type de ligne** | table `LTYPE` : longueurs des éléments (code 49), nombre (73), longueur totale (40) ; résolution `BYLAYER`/`BYBLOCK` | Classes : `continu`, `tirets`, `mixte` (trait-point, ligne d'axe d'ISO 128), `points`. **Le motif, pas le nom** : renommer `CENTER` en `LT07` ne change rien. |
| Remplissage | `HATCH` : drapeau plein (code 70) ; nom de motif (code 2) de la bibliothèque standard ; `SOLID` | Coupe (élément tranché par le plan) vs vu. |
| Cotes | points d'attache (13, 14), type (70), mesure | Corroboration : cote d'axe à axe, cote d'épaisseur. |
| Structure des blocs | une définition insérée N fois, ses attributs (présence, pas l'étiquette), imbrication | Répétition = même objet ; bloc « cercle + un attribut » = bulle. |
| Références externes | drapeaux de bloc (xréf, superposée), drapeau 16 « dépendant d'une xréf » des calques | Repérer un fond lié (risque 4 de l'audit). |
| États des calques | éteint, gelé, non imprimable | Déjà appliqués. |
| **Partition anonyme** | identité d'un calque, d'un bloc, d'un type de ligne, d'une couleur | Clé de REGROUPEMENT, jamais un mot : des entités d'un même calque sont dessinées selon une même convention, quel que soit son nom. |
| Unité | `$INSUNITS` recoupé (durcissement D1), présentation | Bornes de plausibilité en mm. |

Les noms de motif de hachure (`SOLID`, `AR-CONC`, `ANSI31`…) viennent de la
bibliothèque standard, pas du bureau ; seul le drapeau « plein » est un
critère, le nom du motif est cité.

**Mesuré sur le plan réel** : 46 types de ligne, classés par motif en 24
`mixte`, 14 `tirets`, 4 `points`, 4 `continu` (règle du produit, G1 ; la
mesure de faisabilité comptait un motif sans blanc en `tirets`). Parmi les traits longs (≥ 5 %
de la diagonale), **67 traits d'axe sur 71 ont un motif `mixte`, et un seul
trait `mixte` n'est pas un axe**. Hachures : 177 `AR-SAND`, 166 pleines,
17 `ANSI32`.

### 1.2 N2 — géométrie

Forme (cercle, rectangle, polygone régulier, contour fermé), taille relative,
topologie (contenu, contact, jonction), alignement, parallélisme, répétition,
régularité, et relations entre objets : bulle au bout d'une droite, poteau
au nœud, pieu dans un massif, voile le long d'un axe.

### 1.3 N3 — noms

La table actuelle (`classification.py`), inchangée : vocabulaire FR/NL/EN/DE/AIA,
bloc avant calque, type de ligne par son nom.

### 1.4 Combinaison : l'échelle de preuves

Pour chaque objet candidat, et pour chaque sous-système :

1. **Signature complète (N1 + N2)** → décidé par la géométrie
   (`classified_by = "geometrie"`) ; si un nom N3 concorde, il est cité et la
   confiance gagne 0,05 (plafond 0,90).
2. **Signature partielle + nom concordant** → décidé par le nom, comme
   aujourd'hui (`calque`, `bloc`), les critères géométriques vus étant cités.
3. **Signature partielle + partition apprise** (§ 1.5) → décidé
   (`classified_by = "appris"`), confiance plafonnée en dessous de la
   signature complète.
4. **Nom seul, géométrie neutre** → comme aujourd'hui (non-régression).
5. **Nom contredit par une signature complète** → la signature décide ; le
   conflit va dans `unresolved` avec ses deux preuves ; confiance plafonnée
   à 0,4.
6. **Signature partielle seule** → **candidat** : montré, compté, jamais
   proposé ; la raison du manque est écrite.

L'ordre N1 → N2 → N3 est aussi l'ordre d'évaluation : les critères DXF,
normatifs et bon marché, d'abord ; les noms en dernier, seulement pour
compléter.

### 1.5 Partitions apprises

Généralisation au DXF du « style appris » des feuilles PDF (`GEOMETRIE_PDF.md`
§ 3) : quand **au moins trois** objets d'une même partition anonyme (calque,
type de ligne ou couleur) ont une signature complète du même rôle, et
qu'aucun objet de cette partition n'a une signature complète d'un autre
rôle, la partition est **apprise** pour ce rôle. Elle complète ensuite la
signature partielle de ses autres membres — **jamais seule** : un trait du
calque appris doit encore satisfaire les critères partiels du rôle (§ 3–6).
Un seul passage, sans cascade.

**Mesuré** : propager naïvement « tout trait long du même calque que deux
axes à bulle » donne 129 droites dont **65 fausses** ; la partition seule
n'est pas une preuve. D'où la règle : apprise, elle complète ; elle ne
décide pas.

## 2. Ce qui dépend des noms aujourd'hui

| Sous-système | Points d'appel | Dépendance | Effet mesuré sans noms (audit) |
|---|---|---|---|
| Axes | `axes._lignes_candidates` (`classer` → rôle `axe` ou type de ligne nommé), `_courtes_a_bulle`, bulles-blocs (`role_du_nom(bloc) == "axe"`), exclusion des cercles `pieu`/`fondation`/`cadre` | **Totale** : aucun trait n'est candidat sans nom de rôle ou nom de type de ligne | 0 axe sur 71 ; 19 avec le seul nom de type de ligne |
| Poteaux | `formes_fermees` (classement de chaque forme), `detecter_poteaux` (`_JAMAIS`, rôle `poteau`), `_Controle` (`_CONTENU_IGNORE`, rôle `inconnu`), `construction._segments_pour_rectangles` | Indirecte mais forte : la forme exige un nœud (donc des axes), et les exclusions (pieu, massif, hachure, cartouche) sont des noms | 0 poteau (pas de grille) ; +103 faux quand les pieux ne sont plus nommés |
| Pieux | `pieux.detecter_pieux` (germes de rôle `pieu`), `_reperes` (`nomme_un_pieu`), `libelles` | **Totale** pour les germes ; l'absorption du dessin du pieu est déjà géométrique | 477 → 0 |
| Voiles | `voiles.detecter_voiles` (rôle `voile`, ou `inconnu` + plein + allongé), paires de traits seulement sur calque de voile | Forte : la règle de forme ne s'applique qu'aux formes de rôle `inconnu` ; une hachure nommée est exclue, une hachure anonyme devient voile | 4 voiles nommés → 25 hachures |

## 3. Axes

### 3.1 Ce qui identifie un axe

Un axe est une **droite longue**, d'une **famille** de droites parallèles,
terminée à un bout au moins par une **bulle** (contour fermé compact centré
sur son prolongement, avec UNE étiquette courte), dessinée en **trait-point**
(ISO 128), traversant la zone des éléments, souvent cotée d'axe à axe. Aucun
de ces critères n'est un nom.

| Critère | Niveau | Mesuré sur le plan réel (sans noms) |
|---|---|---|
| Bulle : cercle autour d'une seule étiquette courte | N2 | 69 cercles ; **61 bulles d'axe**, 8 autres ; rayon modal 40 (62 sur 69) |
| Droite finissant sur une bulle, longueur ≥ 20 rayons | N2 | 62 droites, 61/71 axes, **0 autre** (≥ 5 rayons : 66 droites, 4 autres) |
| Famille : ≥ 2 parallèles à bulle de même rayon (5 %) | N2 | 60 droites, 59/71, 0 autre |
| Motif `mixte`, ≥ 10 % de la diagonale, parallèle à une famille établie | N1 | +7 droites → **67 droites, 66/71, 0 autre** |
| Point d'attache d'une cote sur la droite | N1 | 49/71 axes touchés — corroboration seulement (les cotes touchent aussi d'autres traits) |

Non retrouvés : 3 axes sans étiquette en `tirets` (axes auxiliaires, que la
règle des noms prenait) et 2 axes étiquetés isolés dans leur direction.

**Détectable sans calques : oui**, dès que le dessin a des bulles OU des
traits-points. Sans l'un ni l'autre (axes en trait continu, sans bulle,
étiquettes en texte libre), non : refus explicite, et N3.

### 3.2 Pipeline

1. **N1** — classer chaque type de ligne par son motif ; lire les bulles-blocs
   par leur STRUCTURE (une définition qui contient un cercle ou un polygone
   régulier et UN attribut), quel que soit leur nom.
2. **N2, signature A (complète)** — droites (traits colinéaires fusionnés,
   comme aujourd'hui) finissant sur une bulle, longueur ≥ 20 rayons, dans une
   famille d'au moins deux droites dont les bulles ont le même rayon à 5 %
   près. La bulle est un cercle **ou un polygone régulier** (hexagone,
   octogone, carré) ; l'étiquette est le seul texte court qu'elle contient.
3. **N1 + N2, signature B (complète)** — droite au motif `mixte`, longueur
   ≥ 10 % de la diagonale de la **zone structurelle** (enveloppe des familles
   à bulles, élargie d'un entraxe médian — pas l'emprise de tout l'espace
   objet, qui contient cartouche et détails : risque 12 de l'audit), parallèle
   à 0,2° près à une famille établie par A.
4. **Signature partielle → candidat** : motif `mixte` seul, bulle seule,
   droite coupant une chaîne de cotes régulière. Complétée par un nom (N3)
   ou une partition apprise (§ 1.5) : alors axe.
5. Familles, repère, nœuds, nommage : inchangés ; grille rayonnante : refus
   inchangé.

**Désambiguïsation des cercles étiquetés.** Les cercles sont regroupés par
diamètre AVANT toute décision (§ 5.2) : une classe dont les membres sont au
bout de droites, hors de la zone des éléments, alignés en rangées, est une
classe de bulles ; une classe nombreuse, dans la zone, sans droite qui en
parte, est une classe de pieux ou de repères. Une bulle d'où ne part aucun
axe n'en est pas une (règle déjà appliquée au PDF).

### 3.3 Confiance

| Décision | Confiance |
|---|---|
| A, étiquetée | 0,85 (comme un axe nommé et étiqueté) |
| B (motif `mixte` + famille), étiquetée par une bulle | 0,85 ; sans étiquette 0,6 |
| Partielle complétée par un nom | règle actuelle |
| Partielle complétée par une partition apprise | 0,6 |

### 3.4 Précision et rappel attendus

| Scénario | Précision | Rappel | Fondement |
|---|---|---|---|
| Plan réel, tous noms retirés, motifs gardés | **100 %** (0/67) | **93 %** (66/71) | mesuré |
| Plan réel, ni noms ni motifs (tout en continu) | 100 % | 86 % (61/71) | mesuré (signature A seule) |
| Autre bureau, bulles rondes ou polygonales | ≥ 95 % | 80–95 % | estimé |
| Grille sans bulles ni trait-point | — | 0 % (refus, puis N3) | par construction |

### 3.5 Modes d'échec

* **Repères de coupe** : un trait-point épais terminé par deux cercles
  numérotés ressemble à un axe. Parade : la famille exige deux droites
  parallèles de même rayon de bulle ; une coupe isolée échoue A ; une coupe
  parallèle à la grille peut passer B → la bulle d'une coupe porte souvent une
  flèche ou un triangle (contour attaché) : critère d'exclusion à mesurer.
* **Bulles déportées** par un trait de rappel : non reconnues (comme
  aujourd'hui).
* **Repères de locaux, numéros de pieux dans des cercles** : écartés si
  aucune droite n'en part, et par la statistique de classe (§ 5.2).
* **Plusieurs grilles** dans un même dessin : inchangé (risque 17 de l'audit).
* **Étiquettes hors format** (`A.1`, minuscules) : DANS une bulle, l'étiquette
  est le seul texte court (≤ 4 caractères, lettres, chiffres, point, prime,
  tiret), lu tel quel ; hors bulle, la règle actuelle reste.

### 3.6 Validation

* Fixtures : grille à bulles rondes sur calque `0` ; bulles hexagonales ;
  grille en trait-point sans bulles d'un côté ; repère de coupe parallèle à la
  grille ; repères de locaux et pieux numérotés dans des cercles ; grille sans
  bulle ni motif (refus attendu).
* Plan réel : variantes de l'audit (v01, v02, v04, v13) et deux nouvelles —
  **v14 tout renommé** (calques, blocs ET types de ligne renommés, motifs
  gardés) et **v15 tout sur `0`** (une seule partition). Cibles : v14 ≥ 66 axes,
  61 étiquettes, 0 axe hors référence ; v04/v15 ≥ 61 axes.
* Feuilles PDF : inchangées (elles apprennent déjà le style par les bulles).

## 4. Pieux

### 4.1 Ce qui identifie un pieu

Un pieu, en plan, est un **cercle** (parfois hachuré, souvent en tirets :
sous le plan de coupe) d'un **diamètre répété** sur tout le plan, **sans
étiquette dedans**, **pas au bout d'une droite**, groupé (2 à 6 sous un
massif, en file sous un voile), plus nombreux que les nœuds de la grille.

| Critère | Niveau | Mesuré sur le plan réel (sans noms) |
|---|---|---|
| Classe de diamètre : ≥ 10 cercles de même diamètre (1 %) | N2 | D = 63 : 910 cercles (pieux dessinés deux fois), D = 60 : 40 — **tous des pieux** ; D = 80 : 62 bulles ; aucune autre classe ≥ 10 |
| Sans étiquette dedans (pas une bulle) | N2 | élimine la classe D = 80 |
| Après dédoublonnage par centre | N2 | **475 candidats, 475 pieux de référence, 0 autre** |
| Motif `tirets`, hachure, massif contenant | N1/N2 | corroborations |

Les 2 pieux de référence restants ne sont pas dessinés par un cercle (hachures
orphelines, que la règle actuelle reprend après les germes).

**Détectable sans calques : oui** sur un plan de fondations d'au moins une
dizaine de pieux d'un même diamètre. Non pour quelques pieux isolés.

### 4.2 Pipeline

1. **N1** — cercles (`CIRCLE`, blocs répétés dont la définition est un
   cercle) ; motif de ligne ; remplissage.
2. **N2, signature P (complète)** — classe de diamètre d'au moins 10 cercles
   (après dédoublonnage), diamètre plausible (250 à 2 000 mm si l'unité est
   connue, sinon ≤ 0,3 entraxe médian), aucun membre avec une étiquette
   dedans au bout d'une droite (sinon : classe de bulles), et **pas une classe
   de poteaux ronds** : si au moins 80 % des membres sont seuls dans leur
   cellule de grille, centrés sur un nœud et pleins, la classe est remise aux
   poteaux (§ 5).
3. Les membres de la classe sont les **germes** ; dédoublonnage, absorption
   du dessin (remplissages, lentilles), hachures orphelines : étapes 2–4
   actuelles, déjà géométriques.
4. **N3** — les germes nommés s'ajoutent (petits plans, pieux isolés) ; un
   germe nommé hors de toute classe reste un pieu « par le nom ».
5. Repères : texte court le plus proche (≤ 6 hauteurs), seulement s'il n'est
   le repère d'aucun autre élément ; le mot « pieu » n'est plus requis quand le
   pieu est géométrique.

Rien n'est proposé, comme aujourd'hui : le pieu sert la revue et l'exclusion
des faux poteaux.

### 4.3 Précision et rappel attendus

| Scénario | Précision | Rappel | Fondement |
|---|---|---|---|
| Plan réel, sans noms | **100 %** (0/475) | **99,6 %** (475/477) | mesuré |
| Autre bureau, ≥ 10 pieux d'un diamètre | 90–98 % | 85–95 % | estimé |
| Moins de 10 pieux, ou diamètres tous différents | — | faible (N3 seul) | par construction |

### 4.4 Modes d'échec

* **Poteaux ronds répétés** sur un plan de fondations : départagés par la
  statistique de classe (un par nœud, pleins) ; un poteau rond posé sur un
  pieu de même diamètre reste ambigu → candidat, dit.
* **Regards, avaloirs, réservations rondes** répétés : diamètre hors bornes
  (souvent < 250 mm) ; sinon faux pieux → mesure de campagne.
* **Pieux numérotés DANS le cercle** : ils ressemblent à des bulles ; la
  classe est décidée par la position (bout de droite ou non), pas par
  l'étiquette.
* **Pieux carrés préfabriqués** : hors de cette signature (les petits carrés
  répétés sont aussi des poteaux) → N3.

### 4.5 Validation

* Fixtures : plan de pieux sur calque `0` ; poteaux ronds aux nœuds + pieux
  sous massifs de même diamètre ; pieux numérotés dans le cercle ; regards
  ronds répétés ; 6 pieux seulement (rappel par N3).
* Plan réel : v01, v04, v14, v15 → 475 pieux au moins, 0 hors référence ;
  aucun faux poteau tiré d'un dessin de pieu.

## 5. Poteaux

### 5.1 Ce qui identifie un poteau

Une **section** : contour fermé compact (rectangle, cercle, polygone
régulier), **coupé** (hachuré ou `SOLID` : N1), de taille plausible, posé
**sur un nœud** de la grille, répété avec quelques sections types, qui ne
contient rien (sinon socle ou massif), n'est pas barré (trémie), n'est pas
le dessin d'un pieu, et se trouve dans la zone structurelle.

**Mesuré** : 63 des 64 poteaux de référence sont des rectangles hachurés
(sections 50×50 : 30, 30×30 : 18, 60×30 : 5…) ; mais **303 contours hachurés
compacts de 10 à 200 cm sont à un nœud, et 1 584 hors nœud**. La forme seule
ne suffit pas : ce sont les exclusions qui font la précision, et elles sont
aujourd'hui des noms.

**Détectable sans calques : oui, si la grille l'est** (§ 3) et si les pieux
le sont (§ 4) ; sans grille, seulement pour des sections répétées et
alignées (signature C2), sinon non.

### 5.2 Pipeline

1. **N1** — remplissage (`HATCH` plein ou à motif, `SOLID`) ; blocs répétés
   (même définition insérée ≥ 3 fois, à l'échelle 1) dont la définition est
   un contour fermé compact.
2. **Classes de cercles et de sections** (commun aux § 3–5) : chaque classe
   (même diamètre, ou mêmes côtés à 1 %) reçoit ses statistiques —
   proportion au bout de droites (bulles), au nœud et seule dans sa cellule
   (poteaux), en grappes ou hors nœud (pieux).
3. **N2, signature C1 (complète)** — la règle de forme actuelle, mais avec des
   **exclusions géométriques** au lieu des rôles nommés : dessin d'un pieu
   géométrique (§ 4), contenant, barré, nommé ouverture par son texte, dans
   une enceinte, **hors de la zone structurelle** (cartouche, légende,
   détails), et hachure appartenant à une plage allongée (voile, § 6).
4. **N2, signature C2 (complète, sans grille)** — au moins 3 sections
   identiques dont les centres s'alignent dans deux directions (≥ 3 par file) :
   une **grille implicite** ; elle donne des poteaux, pas des axes (aucun axe
   n'est inventé).
5. **Partielle → candidat** : contour non hachuré au nœud, section isolée
   hors nœud. Complétée par un nom (N3), un repère voisin de forme poteau
   (`P1`, `C3`), ou une partition apprise.
6. **N3** — un contour sur calque ou bloc de poteau reste un poteau (0,85),
   sauf si une signature complète d'un autre rôle le contredit (§ 1.4, cas 5).

### 5.3 Précision et rappel attendus

| Scénario | Précision | Rappel | Fondement |
|---|---|---|---|
| Plan réel, sans noms | ≈ 97 % (≈ 2 faux : cercles du cartouche, que la zone structurelle doit écarter) | ≈ 100 % (64/64) | **estimé** à partir de la variante v01 (167 = 64 + 101 dessins de pieux + 2 cercles de cartouche) et de la détection géométrique des pieux mesurée au § 4 ; à mesurer à l'implémentation |
| Autre bureau, grille trouvée | 85–95 % | 80–95 % | estimé |
| Sans grille, sections répétées alignées (C2) | 80–90 % | 50–80 % | estimé |
| Sans grille, sections non répétées | — | 0 % (candidats) | par construction |

### 5.4 Modes d'échec

* **Bouts de voile** (élancement ≤ 4) au nœud : pris pour poteaux ;
  parade : contact avec une plage de voile (§ 6).
* **Noyaux et gaines** (contour plein de 1,9 × 1,8 m à un nœud, feuille PDF
  B) : borne de 2 m et contrôle « contenant » ; reste un risque.
* **Poteaux dessinés non hachurés** (plans de fondations où le poteau est
  au-dessus) : candidats, sauf nom ou répétition de bloc.
* **Hachures de sol, de béton de propreté** (`AR-SAND` ici) découpées en
  carrés aux nœuds : exclues si leur plage dépasse la section (contenant) ;
  à mesurer.

### 5.5 Validation

* Fixtures : poteaux hachurés sur calque `0` sans noms ; poteaux en blocs
  renommés ; plan de fondations pieux + massifs + poteaux ; cartouche dans
  l'espace objet avec cercles et carrés ; grille implicite sans axes dessinés.
* Plan réel : v01, v04, v14, v15 → 64 ± 2 poteaux, chacun au même nœud que
  la référence ; aucun poteau tiré d'un pieu.
* Feuilles PDF : le faux poteau du noyau (feuille B) doit rester un
  candidat ou disparaître.

## 6. Voiles

### 6.1 Ce qui identifie un voile

Une **plage longue et mince**, **coupée** (hachurée ou `SOLID`, N1), d'une
épaisseur plausible et **constante**, souvent égale à une épaisseur type du
dessin, **reliée** à d'autres voiles ou à des poteaux (jonctions en L, en T),
**le long d'un axe** (centrée ou à nu d'axe), parfois cotée en épaisseur ; ou
une `MLINE` ; ou deux traits continus parallèles à écart constant entre
lesquels la coupe est hachurée.

Ce qui la distingue d'une poutre : la poutre est vue (tirets, motif `tirets`
en N1, ou contour vide) ; d'une cloison : rien de sûr en géométrie seule —
l'épaisseur (< 80 mm) et l'absence de lien aux axes et aux poteaux
l'écartent souvent, pas toujours.

**Détectable sans calques : en partie.** La signature est la moins
discriminante des quatre ; le porteur ne se distingue pas toujours de la
cloison.

### 6.2 Pipeline

1. **N1** — `MLINE` (à lire : décalages du style, longueur) ; remplissage ;
   motif de ligne ; cotes dont les deux points d'attache tombent sur deux
   faces parallèles (épaisseur cotée).
2. **N2, signature V1 (complète)** — contour rempli, rectangle d'élancement
   ≥ 4, épaisseur plausible (80–600 mm), **et au moins un** de : un axe dans
   la plage ou à écart constant ≤ l'épaisseur ; une jonction avec un autre
   voile ou un poteau ; épaisseur égale (1 mm) à une épaisseur type du dessin
   (classe d'au moins 3 voiles) ; épaisseur cotée.
3. **N2, signature V2 (partielle)** — paire de traits continus parallèles
   (`appariement.py`) sur **n'importe quel** calque, écart plausible,
   recouvrement ≥ 2 épaisseurs → candidat ; devient voile si la coupe entre
   les traits est hachurée, ou par un nom, ou par une partition apprise
   (≥ 3 voiles V1 sur ce calque).
4. Exclusions : motif `tirets` (vu → bandes et poutres), plage contenant des
   pieux en file (longrine ou paroi de pieux : dite, pas tranchée), marches
   (≥ 4 traits parallèles équidistants courts).
5. **N3** — inchangé.

### 6.3 Précision et rappel attendus

| Scénario | Précision | Rappel | Fondement |
|---|---|---|---|
| Plan de coffrage, voiles hachurés reliés aux axes | 80–90 % | 60–80 % | estimé |
| Plan d'architecte (feuilles PDF : 66 et 85 « voiles » cloisons comprises avec la règle actuelle) | 60–75 % avec V1 (lien aux axes, épaisseur type) | 60–80 % | estimé ; à mesurer sur les feuilles |
| Voiles non hachurés, sans `MLINE` | — | faible (candidats V2) | par construction |

### 6.4 Modes d'échec

* Cloisons hachurées comme les voiles (plans d'architecte).
* Longrines, semelles filantes, béton de propreté hachurés : plages longues
  et minces non porteuses en élévation.
* Voiles courbes ou à épaisseur variable : refus (hors domaine).
* Voiles dessinés en traits sans hachure : rappel faible sans nom.

### 6.5 Pourquoi le plan réel ne mesure pas les voiles

Ses 4 voiles nommés sont des contours vides (`LINE`, `LWPOLYLINE`) ; ses 20
plages hachurées longues et minces (épaisseurs 15 à 45) ne sont pas des voiles
de référence et leur nature n'a pas été vérifiée. Les voiles se mesureront
sur des plans de coffrage d'étage (campagne de l'audit, § 7) et sur les deux
feuilles PDF.

### 6.6 Validation

* Fixtures : voiles hachurés reliés en L et T sur calque `0` ; cloisons de
  70 mm hachurées ; poutre vue en tirets entre deux poteaux ; `MLINE` ;
  escalier ; longrine sur pieux.
* Feuilles PDF : comparer 66 / 85 voiles actuels à V1 ; relevé manuel des
  voiles porteurs d'une feuille comme vérité.

## 7. Le pipeline complet

```
lecture DXF ──► N1 : motifs de types de ligne, remplissages, MLINE,
                     définitions et compte d'insertions des blocs,
                     drapeaux xréf, partitions anonymes
          ──► zone structurelle provisoire (emprise des cercles étiquetés
                     au bout de droites ; à défaut, emprise)
          ──► classes de cercles et de sections (statistiques de classe)
          ──► axes      : A ─► B ─► candidats ─► N3      ─► familles, nœuds
          ──► zone structurelle (familles à bulles + un entraxe)
          ──► pieux     : P ─► absorption ─► N3 (germes nommés)
          ──► poteaux   : C1 ─► C2 ─► candidats ─► N3
          ──► voiles    : V1 ─► V2 ─► N3
          ──► partitions apprises (un passage) : complètent les candidats
          ──► comparaison noms / géométrie : accords, désaccords (unresolved)
          ──► bandes, graphe, cotes, repères, dalles, niveaux : inchangés
```

**Réglages inchangés** : tolérances, unité, bornes de plausibilité,
fusion des doublons, identifiants stables par nœud.

**Coût** : appariement cercle–texte et droite–bulle par index spatial
(`IndexSpatial`), comme aujourd'hui ; classes de diamètre en O(n log n).
Cible : moins de 10 % de temps en plus sur le plan réel (≈ 24 s d'analyse aujourd'hui).

## 8. Traçabilité, contrats, version

* **`evidence.classified_by`** gagne trois valeurs : `geometrie` (signature
  complète N1+N2), `appris` (partition apprise), `dxf` (décidé par une entité
  normative seule : `MLINE`, bulle-bloc par structure). Le contrat est fermé
  (`engine/schemas/structure.py`, `Literal`) : changement du schéma, du JSON
  exporté (`packages/contracts`), des types générés, de l'étiquette dans
  `web/lib/documents.ts`, des tests de l'API. Aucune migration : le modèle
  structurel est un JSON, sans contrainte SQL sur ces valeurs (vérifié).
* **`evidence.signature`** (nouveau, liste) : les critères satisfaits
  (`bulle`, `famille`, `motif_mixte`, `classe_de_diametre`, `rempli`,
  `au_noeud`, `jonction`…), et **`evidence.names_agree`** (`true`, `false`,
  `null` si aucun nom reconnu).
* **Candidats** : nouvelle liste `candidates` du modèle (objet, critères vus,
  critère manquant) ; jamais de proposition.
* **Compte rendu** : part des éléments par niveau de décision, partitions
  apprises, désaccords — l'indicateur de dépendance aux noms (D5 de l'audit).
* **Version** : `eurostruct-extraction/0.5.0` (les propositions changent).
* Les confiances restent indicatives et non calibrées jusqu'à la campagne.

## 9. Validation d'ensemble

1. **Tests d'invariance (métamorphiques)** — pour chaque plan fabriqué de
   la suite : renommer au hasard calques, blocs et types de ligne (motifs
   gardés), traduire les noms en espagnol, ou tout poser sur `0` doit donner
   le **même modèle**, à `classified_by` et `matched_name` près. C'est le test
   direct de l'objectif.
2. **Non-régression** — plans fabriqués actuels : modèle identique, ou
   chaque écart expliqué et accepté ; plan réel d'origine : 71 axes,
   61 étiquettes, 64 poteaux, 477 pieux, 4 voiles, 335 propositions, ou écart
   expliqué.
3. **Plan réel sans noms** — variantes v01, v02, v04, v05, v13, v14, v15 :
   cibles des § 3.6, 4.5, 5.5 ; zéro objet hors référence.
4. **Précision sur des dessins qui ne sont pas des plans de structure** — les
   36 DXF d'exemple d'ezdxf : aucun axe, poteau, pieu ni voile attendu.
5. **Feuilles PDF** — inchangées pour les axes ; voiles et poteaux comparés.
6. **Campagne** (audit § 7) — par sous-système et par signature : précision,
   rappel, part décidée par chaque niveau, taux de désaccord noms/géométrie,
   et le seuil de passage : **0 objet faux à confiance ≥ 0,6 décidé par la
   géométrie seule** sur les 12 premiers bureaux.

## 10. Hors du domaine

Grilles rayonnantes et courbes (refus actuel) ; voiles courbes, à épaisseur
variable ; pieux non circulaires ; poteaux composés (en L, en croix) par la
seule géométrie ; éléments en 3D, IFC ; plans numérisés. Un dessin sans
bulle, sans trait-point, sans hachure et sans noms n'a pas de signature : il
est dit illisible par la géométrie, pas deviné.

## 11. Phases d'implémentation (après validation de ce document)

| Phase | Contenu | Sortie mesurée |
|---|---|---|
| G1 | N1 dans les primitives : motif de ligne, remplissage plein/motif, `MLINE`, compte d'insertions, drapeaux xréf ; **aucun changement de détection** — conception détaillée : `GEOMETRIE_D_ABORD_G1.md` | **fait** (`068fc3b`) : 94 / 94 sorties identiques octet pour octet ; suites, contrat et harnais verts |
| G2 | Classes de cercles, bulles par structure, axes A et B, zone structurelle — conception détaillée : `GEOMETRIE_D_ABORD_G2.md` (première phase qui change des sorties : `classified_by = geometrie`, version 0.5.0) | **fait** (`5b86e2c`) : plan réel 71 / 71 (0 ajouté, 0 retiré, 66 axes décidés par la signature) ; tout renommé 0 → 66 axes, précision 1,000, rappel 0,930 ; blocs explosés : 9 axes hors référence ; suites, contrat et harnais verts |
| G3 | Pieux P — conception détaillée : `GEOMETRIE_D_ABORD_G3.md` (signature P, échelle de preuves des pieux, poteaux écartés du dessin des pieux, version 0.6.0) | v01/v04/v14 : 475 pieux, 0 faux poteau de pieu |
| G4 | Poteaux C1 (exclusions géométriques), C2 | v01/v04/v14 : 64 ± 2 |
| G5 | Voiles V1/V2, `MLINE` | feuilles PDF, fixtures |
| G6 | Partitions apprises, désaccords, candidats ; contrat (`appris`, `dxf`, candidats), écran, version suivante | tests d'invariance, suites, harnais |

Chaque phase : conception déjà écrite ici, tests de régression, mesure
avant/après sur le plan réel, ses variantes, les feuilles PDF et le corpus,
commit séparé.
