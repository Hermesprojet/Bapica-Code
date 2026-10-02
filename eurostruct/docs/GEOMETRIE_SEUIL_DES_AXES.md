# Le seuil de longueur d'un axe, et les axes courts à bulle — conception

> Conception écrite **avant** le code (§ 0 à 4), à partir du plan de
> fondations réel (non commité) ; puis la mesure, après (§ 5 à 7). Elle
> prolonge
> [`GEOMETRIE_BULLES_LETTRES_CHIFFRES.md`](GEOMETRIE_BULLES_LETTRES_CHIFFRES.md),
> dont le § 5 laissait « L6 » et « L8 » sans axe.

## 0. Le défaut, reproduit

Les bulles « L6 » et « L8 » existent, et un trait de rôle `axe` finit sur
chacune (996 et 1 010 unités). Aucun des deux n'est un axe du modèle.

## 1. La règle actuelle

`axes._lignes_candidates` garde un trait de rôle `axe` si sa longueur atteint
un seuil, **avant** de fusionner les morceaux colinéaires :

| règle qui a classé le trait | seuil |
|---|---|
| calque ou bloc nommé (`AXES`, `S-GRID`…) | max(10 tolérances, **0,1 × diagonale de l'emprise**) |
| type de ligne d'axe sur un calque qui ne dit rien | 0,3 × diagonale |
| style appris d'une feuille PDF | 10 tolérances |

L'emprise est celle de **tous les traits** du dessin (`PrimitivesDxf.emprise` :
traits, contours, cercles ; pas les textes).

## 2. Ce que la mesure dit

Sur le plan de fondations :

* **emprise** −4 634…5 334 × −1 026…13 519 : diagonale **17 633**, seuil
  **1 763**. Le corps du dessin (quantiles 1 %–99 % des points) ne mesure
  que 11 337 de diagonale : au-dessus de y = 9 000, une légende (198 points
  sur le calque de la xréf, les échantillons d'épaisseur de trait) et des
  cadres d'annotation agrandissent l'emprise de moitié ;
* **112 traits de rôle `axe`** (68 par bloc, 28 par calque, 16 par type de
  ligne). **33** traits nommés sont sous le seuil :
  * **12 finissent sur une bulle étiquetée** : « L6 », « L8 », et « LB », « LC »,
    « LD », « LF », « LG », « LH », « LJ », « LL », « LP » de la même seconde grille,
    plus un morceau de 832 colinéaire à l'axe « 10 », bulle « L9 » au bout.
    De 832 à 1 714 unités, soit 20,8 à 42,8 rayons de bulle ;
  * **21 ne finissent sur aucune bulle** : morceaux d'axes de files de pieux
    (`D_AXE_*`, jusqu'à 1 175 unités) et traits de travail de 45 unités.

**Aucun seuil de longueur ne sépare les deux groupes** : un morceau de file
de pieux sans bulle (1 175) est plus long que « L6 » (996). Les options
mesurées :

| option | seuil | traits admis en plus | dont sans bulle | « L6 » / « L8 » |
|---|---|---|---|---|
| actuelle (0,1 × diagonale de l'emprise) | 1 763 | 0 | 0 | non / non |
| A : légende exclue (0,1 × diagonale du corps) | 1 134 | 4 | **2** (files de pieux) | non / non |
| B : 0,1 × diagonale des seuls traits d'axe | 1 270 | 2 | 0 | non / non |
| B' : 0,1 × le plus long trait d'axe | 926 | 10 | **2** (files de pieux) | oui / oui |
| **D : le trait finit sur une bulle étiquetée** | — | **12** | **0** | **oui / oui** |

Exclure la légende est juste, mais ne suffit pas : même sans elle, le seuil
reste au-dessus de « L6 » et « L8 », et il fait entrer deux morceaux de files de
pieux sans étiquette. **Le seuil reste approprié comme filtre** (il écarte à
juste titre les 21 traits sans bulle) ; ce qui manque, c'est une preuve qui ne
soit pas une longueur.

## 3. La règle proposée (option D), et ses gardes

Un trait **nommé** axe (par son calque ou son bloc) plus court que le seuil est
gardé comme axe s'il remplit **les trois** conditions :

1. **il finit sur une bulle étiquetée** : un cercle centré sur son prolongement
   (à un quart de rayon près), à son bout (de −r à +4 r), contenant un texte
   d'étiquette — forme courante ou lettres et chiffres — ; ni le cercle ni le
   texte ne sont classés pieu, fondation ou cartouche (`cadre`) ;
2. **il mesure au moins 10 rayons de cette bulle** : un trait de rappel vers
   une bulle déportée (quelques rayons) n'est pas un axe ; mesuré, le plus
   court des douze en fait 20,8 ;
3. **sa direction est partagée** (tolérance de parallélisme du dessin) par un
   axe admis par le seuil, ou par un autre trait gardé de la même façon : pas
   de direction isolée. Mesuré : neuf des douze sont parallèles à une famille
   admise ; « LF », « LG », « LH » (88°) se soutiennent entre eux.

Et après l'étiquetage : **un trait gardé ainsi doit être étiqueté par une
bulle**, sinon il est retiré (une bulle prise par un autre axe, deux bulles
qui se contredisent, une étiquette venue d'ailleurs ne font pas un axe). Un
axe gardé ainsi le dit dans `label_source.admitted` (règle, longueurs des
traits, seuil).

*Ajouté à l'implémentation* : retirer ne suffit pas. Un trait retiré a pu
prendre, dans l'affectation globale, la bulle d'un autre axe ; **l'étiquetage
est relu sans lui**, et la bulle revient à l'axe qui la porte. Sans cette
relecture, l'axe « 3 » du plan fabriqué (§ 7) perdait son étiquette.

Ce qui ne change pas : le seuil lui-même, les traits classés par type de ligne
(seuil 0,3), les feuilles PDF (style appris), la fusion des morceaux
colinéaires — un morceau gardé qui prolonge un axe admis le prolonge.

## 4. Ce qui est attendu, et comment c'est validé

Attendu sur le plan de fondations : « L6 » et « L8 » deviennent des axes ;
onze axes nouveaux en tout, tous étiquetés par leur bulle (« L6 », « L8 », « LB »,
« LC », « LD », « LF », « LG », « LH », « LJ », « LL », « LP ») ; l'axe « 10 » prolongé
par son morceau ; aucun axe sans étiquette ajouté.

Validation, avant tout commit du code :

* le plan réel, chaîne complète : axes, axes étiquetés, chaque axe nouveau
  montré avec sa bulle ; aucun axe nouveau sans étiquette ; repères de
  poteaux inchangés ;
* les plans fabriqués existants et les 36 DXF d'exemple d'ezdxf, avant et
  après : identiques, ou chaque différence expliquée ;
* un plan fabriqué pour les gardes : un axe court à bulle gardé ; un morceau
  sans bulle, un trait de rappel de 3 rayons, un trait à bulle d'une direction
  isolée, refusés ;
* les suites d'extraction et d'API, et le harnais des documents.

## 5. Mesure sur le plan de fondations

Chaîne complète du produit, fichier brut relu ; avant = `557d324`.

| | avant | après |
|---|---|---|
| axes | 60 | **71** : les 60 mêmes droites, et 11 nouvelles |
| axes étiquetés | 50 | **61** |
| « L6 » / « L8 » | absents | **axes**, étiquetés par leur bulle (lettres et chiffres) ; traits de 996 et 1 010 unités, seuil 1 763, dans `admitted` |
| axes nouveaux | — | « L6 », « L8 », « LB », « LC », « LD », « LF », « LG », « LH », « LJ », « LL », « LP » : **tous** étiquetés par leur bulle ; aucun axe nouveau sans étiquette |
| axes existants | — | mêmes droites, mêmes étiquettes, mêmes sources ; « 10 » cite toujours « L9 », écartée ; 8 axes sans étiquette renommés (« 7.1 » → « 8.1 »…, voir plus bas) |
| conflits d'étiquettes | 0 | 0 |
| temps de lecture | 20,3 s ; 19,8 s | 20,0 s ; 17,9 s (deux passes à la suite) |

Contrairement à l'attente du § 4, l'axe « 10 » n'est pas prolongé : son
morceau de 832 est compris dans sa droite. Sa preuve cite un trait de plus
(celui de la seconde grille).

**Ce qui change par ricochet**, vérifié élément par élément :

* **un poteau de plus (63 → 64)** : une section 60 × 30 en béton préfabriqué
  coupé, hachurée, au centre (4 404 ; 6 474). Le nœud « L8/LP » tombe dedans,
  et un contour sans calque de poteaux n'est un poteau qu'à un nœud. C'est
  l'une des six sections 60 × 30 de la file x = 4 404 : trois étaient déjà
  des poteaux, de même calque, même hachure, même section ; les deux autres,
  sans nœud, restent hors du modèle. Un poteau retrouvé, pas un faux positif ;
* **deux poteaux renommés** : le nœud le plus proche de leur centre est
  désormais sur un axe nouveau — `column:M10` → `column:LJ10` (nœud à 11,2
  unités du centre au lieu de 21,1), `column:N10` → `column:LP10` (13 au lieu
  de 30).
  Positions, sections et repères inchangés ;
* **pieux** : 477, mêmes positions, mêmes diamètres. 26 changent seulement de
  nom de nœud — un axe sans étiquette se nomme « famille.rang », et une
  famille ou un rang de plus décale ces noms ; 4, sans nœud jusqu'ici, sont au
  nœud d'un axe nouveau ;
* **nœuds** 263 → 299 ; **familles** 13 → 14 (« LF », « LG », « LH ») ;
* **entraxes** 47 → 57 (étiquetés aux deux bouts : 31 → 41). Quatre entraxes
  sont coupés par un axe nouveau, en parts exactes : 190 = 111 + 79
  (LK–LL–LM), 629 = 270,8 + 358,2 (LI–LJ–LK), 739,5 = 559,5 + 180
  (L7–L6–L5), 423,5 = 17 + 406,5 (N–LP–un axe sans étiquette). L'entraxe
  médian, qui sert d'échelle à d'autres détecteurs, passe de 617,5 à 540 cm ;
  sur ce plan, rien d'autre n'en change ;
* **propositions** 342 → 354, aucune confiance changée : 11 files
  géométriques (0,85 pour « L6 » et « L8 », 0,9 pour les autres), qui
  remplacent 9 files lues par le seul texte (0,7) ; 10 entraxes de plus
  (14 nouveaux, 4 coupés) ; 2 dimensions entre axes extrêmes (LB–LE 823 cm,
  LF–LH 190 cm). Deux cotes du dessin, proposées seules jusqu'ici, se
  rattachent désormais à des axes nouveaux : la cote 190 mesure LB–LD
  (concordante) ; la cote lue 25,05 a ses deux points sur L6 et L5, et se
  rattache à l'entraxe L6–L5 (180) comme **non concordante** (voir § 6) ;
* **compte rendu** : candidats poteaux écartés comme pieu 98 → 107, comme
  dessin de pieu 54 → 59 — des formes de pieux qu'un nœud nouveau rend
  candidates, toutes écartées.

**Ailleurs, rien ne change** : les 24 plans fabriqués, les 36 DXF d'exemple
d'ezdxf et les deux feuilles PDF donnent les mêmes modèles et les mêmes
propositions, avant et après.

## 6. Ce qui reste

* **Les cotes alignées sont mal lues** (défaut antérieur, découvert ici) : sur
  ce plan, 108 des 110 cotes alignées sont lues comme leur projection
  horizontale (564 lu 551,675 ; 100 lu 0). Jusqu'à 37 des 202 propositions
  de cote du plan portaient une telle valeur avant (36 après : la cote 25,05
  se rattache désormais à L6–L5 au lieu d'être proposée seule). C'est la
  lecture des cotes, pas celle des axes : à traiter à part — corrigé depuis
  ([`GEOMETRIE_COTES_DXF.md`](GEOMETRIE_COTES_DXF.md)) ; la cote 25,05 se lit
  180 et concorde avec L6–L5.
* **Un entraxe de 17 cm, « N–LP »**, est proposé : une droite de chaque grille,
  parallèles, dans une même famille. Même nature que les entraxes de 10 à
  44 cm déjà proposés avant, entre droites presque confondues (une au moins
  sans étiquette, 0,6) ; nouveau : ses deux bouts sont étiquetés (0,85).
  Séparer deux grilles d'un même dessin n'est pas traité.
* **Les noms d'axes sans étiquette** (« famille.rang »), et les identifiants de
  nœuds, de poteaux et de pieux qui en dérivent, changent dès qu'un axe
  s'ajoute : défaut antérieur, montré ici par 26 pieux renommés.
* **L'entraxe médian** sert d'échelle à plusieurs détecteurs ; des axes
  rapprochés le font baisser (617,5 → 540 cm ici, sans effet mesuré sur ce
  plan).
* « L9 » cède toujours à « 10 » ; les deux sections sans nœud de la file
  x = 4 404 restent hors du modèle.

## 7. Tests

`test_geometrie_axes_courts.py`, sur un plan fabriqué
(`dxf_axes_courts_a_bulle`) qui reprend la forme du plan réel — une légende
éloignée qui porte le seuil à 9 140 mm, au-dessus de traits d'axe de 5 000 mm :

* gardés : un axe court à bulle (« 1' ») ; deux traits parallèles à 80° qui se
  soutiennent (« R1 », « R2 », lettres et chiffres) ; chacun avec `admitted` ;
* refusés, un cas par condition : sans bulle ; trait de rappel de 3 rayons ;
  direction isolée (le même trait devient un axe dès qu'un axe à 45° admis
  par le seuil partage sa direction) ; pointé vers la bulle d'un autre axe ;
  entre deux bulles qui se contredisent ; pieu numéroté au bout ; type de
  ligne d'axe hors calque nommé ;
* relu sans le trait retiré : l'axe « 3 » garde sa bulle, aucun conflit n'est
  signalé ;
* les axes admis par le seuil, inchangés ; les files proposées.

Les tests échouent là où ils le doivent : sur le code d'avant (`557d324`),
4 des 15 (les axes gardés) ; sur une variante qui retire sans relire, 3 des
15 (l'axe « 3 » perd son étiquette). Le plan rejoint les tests de
traçabilité.
