# Le seuil de longueur d'un axe, et les axes courts à bulle — conception

> Conception écrite **avant** le code, à partir du plan de fondations réel
> (non commité). Elle prolonge
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
bulle**, sinon il est retiré (une bulle prise par un autre axe ne fait pas un
axe). Un axe gardé ainsi le dit dans `label_source.admitted` (règle, longueur,
seuil).

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
