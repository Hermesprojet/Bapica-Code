# Lecture géométrique des PDF vectoriels — conception

> Conception écrite **avant** le code. Elle prolonge
> [`GEOMETRIE_DXF.md`](GEOMETRIE_DXF.md) : la même chaîne géométrique (axes,
> poteaux, voiles, poutres, graphe, travées, cotes, repères, dalles), une
> nouvelle **entrée** — les traits d'un PDF exporté d'un logiciel de DAO.

## 0. Point de départ mesuré

Sur deux plans d'architecte **réels** (non commités, désignés ici « feuille A »
et « feuille B ») — une page chacun, 1 474 × 900 mm, exportés de Vectorworks
par le moteur PDF de macOS :

| ce que le PDF contient | mesuré |
|---|---|
| traits | 16 047 et 33 666 segments, 3 745 et 6 919 chemins, 69 et 373 rectangles |
| texte | 3 696 et 3 920 mots — une vraie couche texte, l'OCR est inutile |
| calques | **aucun** : pas de groupes de contenu optionnel (OCG), l'export les a aplatis. Restent la couleur, l'épaisseur et le motif de tirets |
| axes | trait mixte rouge **découpé en segments** de 1 à 4 pt (le motif n'est pas un attribut, il est dessiné) |
| bulles d'axes | cercle pointillé, lui aussi découpé (~40 segments), étiquette rouge au centre |
| texte | tourné avec le plan (8 à 12°) : l'extraction par lignes horizontales le coupe en morceaux (« 01 », « 10 ») |
| cotes | lignes bleues, traits d'attache bleus qui les coupent, nombre bleu parallèle au-dessus du milieu |
| échelle | « 1/50 » écrit au cartouche, loin du mot « échelle - schaal » |
| concordance | **494 cotes sur 668** (feuille B) et **232 sur 277** (feuille A) appariées à leur ligne concordent à 1/50 lues en **cm** (± 1 %) |

Aujourd'hui, ces feuilles donnent : aucun modèle, une valeur (un niveau).

## 1. Ce que ce lot fait, et ce qu'il ne fait pas

**Il fait** :

* lire la géométrie d'un PDF **d'une seule page** portant des traits (un plan
  est une feuille) ;
* reconstituer ce que l'export a découpé : **mots tournés** depuis les
  caractères, **bulles** depuis leurs arcs, **cotes** depuis leur ligne, leurs
  traits d'attache et leur nombre ;
* **apprendre les conventions de la feuille** au lieu de les supposer : le
  style des axes est celui des traits qui partent des bulles ; le style des
  cotes, celui des lignes qui portent un nombre parallèle. Rien n'est écrit en
  dur — ni « rouge = axe », ni « bleu = cote » ;
* **établir l'échelle par deux sources** (§4) et convertir en millimètres
  réels ;
* passer le résultat dans **la même chaîne** que le DXF, et proposer avec la
  méthode `geometrie`, la page et la **boîte** de l'élément sur la feuille.

**Il ne fait pas** (et le dit dans le compte rendu) :

* un PDF de plusieurs pages, un PDF numérisé (pixels), plusieurs échelles sur
  une même feuille (détails au 1/20 dans un plan au 1/50 : seule l'échelle
  dominante est établie, les cotes qui ne la suivent pas restent non
  rattachées) ;
* les calques OCG (absents des feuilles mesurées) ;
* les murs dessinés en hachures : une hachure n'est pas une face ;
* **les poutres** : aucun style n'en est appris, et deux traits parallèles
  d'un plan d'architecte sont aussi des murs, des marches ou du mobilier.
  Aucune poutre n'est tirée de la seule forme sur une feuille ; le refus est
  inscrit dans `unresolved` (`poutres`) ;
* les hauteurs, épaisseurs de dalle, niveaux : ils restent des textes.

## 2. Architecture

```
octets PDF ──> lecteurs/pdf.py (texte, inchangé)
          └──> geometrie/pdf_vectoriel.py
                  traits, contours, mots tournés      (pdfplumber, une ouverture)
                  bulles reconstituées                (cercle ajusté sur les arcs)
                  styles appris : axes, cotes
                  cotes reconstituées
                  geometrie/echelle.py : échelle écrite × cotes concordantes
               ──> PrimitivesDxf en mm réels (nom historique de la structure)
               ──> construire_modele (inchangé) ──> propositions (page, boîte)
```

Les primitives d'un PDF portent un **cadre** : page, points par millimètre
réel, hauteur de page — de quoi rendre à chaque proposition sa boîte sur la
feuille (origine en haut à gauche, comme les boîtes de texte).

## 3. Reconstitution

**Traits.** Chaque morceau droit d'un chemin est un segment ; un rectangle
donne ses quatre côtés et un contour ; un chemin fermé et rempli donne un
contour plein ; une courbe de Bézier est aplatie. Le « calque » d'un trait
est son **style** — couleur de trait, épaisseur, motif — nommé lisiblement
(`pdf:#DE0000:1.5`). Il ne dit rien du rôle tant qu'un style n'est pas appris.

**Mots.** Les caractères de même matrice (rotation), même corps et même
couleur, contigus le long de leur ligne de base, forment un mot ; sa rotation
est celle de la matrice, sa boîte celle de ses caractères. **Le corps** ne se
lit pas dans la matrice d'un caractère (pdfminer en retire `Tf`) : un
exporteur écrit `1 Tf` et met l'échelle dans `Tm`, un autre `10 Tf` et une
rotation seule. Il se retrouve depuis la boîte : la glyphe est un rectangle
« avance × corps » que la matrice transforme.

**Bulles.** Pour chaque mot qui a la forme d'une étiquette d'axe (`A`, `12`,
`B'`) : les segments courts dans un rayon de 2,5 hauteurs ; un cercle ajusté
par moindres carrés (deux passes) ; une bulle si le centre est à moins de
0,35 r du centre du texte, l'écart moyen sous 6 % de r, et si **au moins huit
morceaux TANGENTS** au cercle couvrent la moitié du tour. Mesuré : sans la
tangence, l'amas des traits d'attache et des tirets autour d'un nombre de
cote (« 10 ») s'ajuste aussi sur un cercle — ses traits sont radiaux ou
obliques.

**Style des axes et axes.** Candidats : les styles des morceaux qui partent
radialement d'au moins deux bulles. Pour chaque candidat, l'axe est
**reconstitué depuis sa bulle** : direction des morceaux qui en partent,
droite réajustée sur tous les morceaux de son couloir, de proche en proche
jusqu'au premier trou de plus de dix rayons. Retenu : le style dont les axes
partent du plus grand nombre de bulles. Mesuré : l'axe passe à 0,2 rayon du
centre de sa bulle — la droite est celle des morceaux, pas celle du centre.
Une bulle d'où ne part aucun axe (repère de local, numéro de marche) n'en est
pas une pour la grille.

**Style des cotes et cotes.** Le style des lignes qui portent des nombres
parallèles (à 3° près, à moins de 2,5 hauteurs), chaque nombre comptant une
fois par style ; parmi les trois plus fréquents, celui dont les cotes
confirment une échelle écrite. **Le style des nombres** s'apprend aussi (la
majorité de ceux posés sur ces lignes) : un numéro de marche noir posé sur
une ligne de cote bleue n'est pas une cote. **Les marques** (tirets obliques,
d'un autre style que la ligne) s'apprennent aux bouts des lignes de cote. Une
ligne de cote est **prolongée** par ses morceaux colinéaires du même style
(les dépassements au-delà des marques) ; ses **coupes** sont ses marques et
les traits d'attache qui **s'arrêtent** près d'elle — pas ceux d'une chaîne
voisine qui la traversent de part en part. Un nombre posé vers le milieu d'un
intervalle en est la cote.

## 4. L'échelle : écrite ET confirmée

* **écrite** : un mot `1/n` ou `1:n` sur la feuille (`n` ≤ 1 000), cité avec
  sa boîte ;
* **confirmée** : pour chaque échelle écrite et chaque unité possible des
  nombres (mm, cm, m), les cotes reconstituées dont le nombre égale la longueur
  mesurée à cette échelle, à une demi-unité du dernier chiffre près (et 0,5 %) ;
* **établie** si au moins **cinq** cotes concordent et qu'elles sont au moins
  **60 %** des cotes reconstituées. L'unité des nombres est alors celle qui
  concorde, et elle est citée (« 494 cotes sur 668 concordent à 1/50 lues en
  cm ») ;
* **sinon, rien n'est converti** : les longueurs restent en points-papier, sans
  unité, et rien ne se reporte. Une échelle que seules les cotes suggèrent,
  sans être écrite, est dite dans `unresolved`, pas appliquée.

Une cote reconstituée porte un facteur d'affichage (le `DIMLFAC` du DXF) égal
à l'inverse de l'unité de ses nombres : sa concordance se juge comme pour un
DXF, et elle se rattache aux axes de la même manière.

## 5. Précision, confiance, traçabilité

* **tolérance** : 1 mm réel ou deux centièmes de point à l'échelle, le plus
  grand ; **pas de quantification** : 0,1 mm (sous la précision des
  coordonnées, 0,01 pt ≈ 0,18 mm au 1/50), valeur brute conservée ;
* **confiance** : plafond 0,85 pour une feuille PDF (0,90 pour un DXF) ; une
  forme sans style appris garde les bases du DXF ;
* **source** : la revue et la provenance du report disent « Géométrie du
  PDF » (« Géométrie du DXF » pour un DXF) ;
* **trace** : page, boîte de l'élément sur la feuille, style des traits
  (couleur, épaisseur), règle (`style_appris_des_bulles`, `forme`…),
  échelle et ses deux sources.

Aucune migration : la méthode `geometrie` existe (0029), et `extraction_is_traced`
admet boîte et position ensemble — le harnais `db/test/documents_extractions.sh`
le vérifie contre un PostgreSQL réel (point 9).

## 6. Tests

Des PDF **fabriqués par les tests**, écrits opérateur par opérateur (pas de
dépendance nouvelle) : un plan tourné, axes en trait mixte découpé, bulles
pointillées, cotes en chaîne en cm, échelle « 1/50 » au cartouche, poteaux
pleins aux nœuds, poutres en rectangles. Variantes : sans échelle écrite ;
« 1/50 » écrit mais dessiné au 1/100 ; tirets par attribut plutôt que découpés ;
deux pages ; un PDF sans traits. Les deux feuilles réelles servent à la mesure
du §7, jamais au dépôt.

## 7. Ce qui sera mesuré

Sur les deux feuilles réelles : l'échelle établie et ses deux sources, les
axes et leurs étiquettes, les entraxes mesurés comparés aux cotes écrites,
les poteaux, voiles et poutres reconnus — et ce que la feuille ne contient pas.
Un plan d'architecte ne dessine pas les poutres : n'en trouver aucune est le
résultat juste, pas un échec.

## 8. Ce que les deux feuilles réelles ont donné

Mesuré sur le code commité, en local ; ni les feuilles ni leurs sorties ne
sont dans le dépôt.

| | feuille A (étage) | feuille B (étage) |
|---|---|---|
| analyse complète (lecture + modèle) | 11,8 s | 23,5 s |
| traits lus | 32 434 | 63 561 |
| cercles autour d'une étiquette / bulles d'axe | 56 / 15 | 114 / 24 |
| style des axes appris | rouge, 1,5, tirets | rouge, 1,5, tirets |
| axes reconstitués (étiquetés) | 10 (8) | 20 (18) |
| style des cotes appris | bleu, 1,5 | bleu, 2,1 |
| cotes reconstituées / concordantes à 1/50 en cm | 280 / 219 (78 %) | 629 / 514 (82 %) |
| échelle | **1/50 établie**, écrite au cartouche | **1/50 établie**, écrite au cartouche |
| propositions | 45 | 84 |

Avant ce lot, ces feuilles donnaient : aucun modèle, une valeur (un niveau).

**Ce qui est juste.** L'échelle et ses deux sources ; la grille, étiquetée par
ses bulles, superposée aux axes dessinés ; les entraxes en mm (5 499,1 ;
6 676,5 ; 1 112,2…) ; aucune poutre, et le refus est dit.

**Ce qui ne l'est pas, ou pas encore** :

* sur la feuille B, un contour de 1,9 × 1,8 m du noyau central, à un nœud
  de la grille, est pris pour un poteau par la règle de forme du DXF
  (confiance 0,6) et sa « section » est proposée ; les autres « poteaux » sont
  des polygones pleins, dont aucune section n'est proposée ;
* les murs pleins (hachurés) deviennent des voiles par la même règle : 66 et
  85, de 98 à 450 mm — cloisons comprises ; une feuille ne dit pas lesquels
  portent ;
* deux axes par feuille restent sans étiquette : une bulle à un bout, une
  lettre isolée dans le prolongement de l'autre — la règle refuse de choisir ;
* les entraxes ne sont corroborés par aucune cote : l'architecte cote les
  murs et les baies, presque jamais d'axe à axe (2 cotes sur 629 touchent un
  axe) ;
* 18 % à 22 % des cotes ne concordent pas : des cotes écrites qui ne sont pas
  celles du trait (« 90 » écrit, à plusieurs endroits, sur un intervalle
  mesuré à 78 cm), et des coupes encore mal placées dans les chaînes denses.

## 9. Limites

Une page seulement ; une échelle dominante ; ni OCG, ni PDF numérisé ; aucune
poutre ; le texte de la page reste lu par le lecteur de texte (lignes
horizontales), indépendamment des mots tournés que lit la géométrie.
