# Étiquettes d'axes en lettres et chiffres (« L1 »… « L10 »)

> Un défaut trouvé à la vérification de la lecture des pieux et des gaines
> ([`GEOMETRIE_PIEUX_GAINES_UNITE.md`](GEOMETRIE_PIEUX_GAINES_UNITE.md)) :
> sept axes du plan de fondations finissaient sur une bulle lisible et
> restaient sans étiquette. Le plan réel n'est pas commité ; ses mesures sont
> refaites ici, avant et après, sur la chaîne du produit.

## 1. Le défaut, reproduit

Sur le plan de fondations : 60 axes, 43 étiquetés. Sept axes finissent
exactement sur une bulle — un cercle de rayon 40, le bout de l'axe sur le
cercle, le texte au centre — qui porte « L1 », « L2 », « L3 », « L4 », « L5 »,
« L7 » ou « L10 » : les axes d'une seconde grille, dessinée par une autre
référence externe liée. Ils restaient sans étiquette.

## 2. La cause, exacte

La vérification l'avait attribuée au cartouche. C'était inexact ; mesuré :

| étape | ce qu'elle fait de la bulle « L10 » |
|---|---|
| nom du calque `…C_AXES_TITRE_COMMUN-SSOL` | lu `cadre` : le motif du cartouche (`TITRE`) est essayé avant celui des axes (`AXES`) |
| classement de la bulle (cercle et texte) | `axe` : la bulle est dans le bloc de la référence externe (`AXES_…`), et un bloc prime sur son calque |
| bulles admises (`detecter_axes`) | admise : seuls les pieux et les fondations sont écartés |
| étiquettes candidates (`ETIQUETTE_AXE`) | **refusée** : le motif n'admettait qu'une ou deux lettres, ou un à trois chiffres — jamais des lettres puis des chiffres |

Deux essais en mémoire le prouvent : relire les calques `…AXES_TITRE…` comme
`axe` ne change aucune étiquette (43) ; élargir le motif en rend sept. Le
classement `cadre` du nom de calque est réel mais n'empêche rien ici : les
neuf calques `…C_AXES_TITRE…` du plan sont lus `cadre`, y compris ceux des
43 axes étiquetés.

## 3. La règle

Une étiquette en lettres et chiffres (`[A-Z]{1,2}\d{1,3}'?` : « L1 », « L10 »,
« AB12 », « L1' ») :

* n'est lue que **dans une bulle** (un cercle centré sur le prolongement de
  l'axe, le texte dedans) ou dans l'attribut d'un bloc de bulle — jamais comme
  texte libre ;
* jamais dans un cercle ou un texte classé `cadre` (cartouche) ;
* seulement à une extrémité qui n'a **aucune** étiquette de forme courante :
  elle complète, elle ne remplace rien ;
* face à une étiquette courante à l'autre bout, elle cède et elle est citée
  (`label_source.discarded`, « lettres et chiffres ») ; deux étiquettes en
  lettres et chiffres qui se contredisent restent un conflit, dit dans
  `unresolved` ;
* lue, elle porte `label_source.form = lettres_et_chiffres`.

Un nœud nommé par une telle étiquette garde le séparateur : « L1/1 », jamais
« L11 », qui se lirait comme un autre axe.

**Pourquoi pas élargir le motif partout.** Mesuré : la ligne « 10 » du plan
porte aussi, à l'autre bout, la bulle « L9 » de la seconde grille. Un motif
élargi en ferait un conflit de même force, et l'axe « 10 » perdrait son
étiquette. Et un texte libre « L6 » ou « C03 » posé au bout d'un axe n'est pas
une étiquette.

## 4. Mesure sur le plan de fondations

Chaîne complète du produit, fichier brut relu ; avant = `3a36f5c`.

| | avant | après |
|---|---|---|
| axes | 60 | 60, les mêmes droites |
| axes étiquetés | 43 | **50** |
| étiquettes nouvelles | — | L1, L2, L3, L4, L5, L7, L10, toutes par leur bulle |
| étiquettes changées | — | aucune ; l'axe « 10 » cite « L9 », écartée |
| conflits d'étiquettes | 0 | 0 |
| entraxes entre deux axes étiquetés | 28 sur 47 | 31 sur 47 (mêmes distances) |
| propositions géométriques | 109 | **119** : 7 files ; 1 entraxe de plus (739,5 cm, désormais L3-L2 et L7-L5) ; 2 dimensions entre axes extrêmes (L10–L4 1 870 cm, L3–L1 1 407 cm) ; aucune confiance changée |
| poteaux, pieux, voiles | 63, 477, 4 | identiques |
| repères de poteaux | — | identiques, position par position |
| nœuds | 263 | 263, dont 56 renommés (« H/L1 »…) ; 4 identifiants de poteaux suivent : `1.2xLI` → `L7/LI`, `1.2xN` → `L7/N`, `Hx11.1` → `H/L3`, `Hx11.4` → `H/L1` |

Faux positifs nouveaux : aucun. Ailleurs, rien ne change : les 24 plans
fabriqués, les deux feuilles PDF et les 36 DXF d'exemple d'ezdxf donnent les
mêmes résultats avant et après.

## 5. Ce qui reste

* **« L6 » et « L8 »** : leurs bulles existent, et un trait de rôle `axe`
  (≈ 1 000 unités) y finit. Mais ces traits sont plus courts que le seuil d'un
  axe nommé par son calque — 10 % de la diagonale du dessin, ici 1 763 unités,
  parce qu'une légende éloignée agrandit l'emprise : ils ne sont pas des axes
  du modèle. Défaut de détection d'axes, antérieur, non traité ici — traité
  depuis par [`GEOMETRIE_SEUIL_DES_AXES.md`](GEOMETRIE_SEUIL_DES_AXES.md).
* **« L9 »** cède à « 10 » sur la ligne que les deux grilles partagent : le
  modèle ne porte qu'une étiquette par axe ; l'autre est citée.
* Une bulle en lettres et chiffres sur un calque nommé `…TITRE…` **hors** de
  tout bloc d'axes reste classée `cadre` et n'est pas lue : choix prudent (le
  cartouche reste exclu), sans plan réel pour le mesurer.
* **Repères de poteaux** : non touchés. Les textes « L1 »… n'étaient le repère
  d'aucun élément ; lus comme étiquettes d'axes, ils sont absorbés et ne
  pourront plus le devenir.

## 6. Tests

`test_geometrie_bulles_lettres_chiffres.py`, sur un plan fabriqué
(`dxf_bulles_lettres_chiffres`) qui reprend la forme du plan réel — une
seconde grille dans le bloc d'une référence externe liée, bulles sur un calque
`…C_AXES_TITRE` : le motif (admis, refusés) ; la cause (calque `cadre`, bloc
`axe`) ; une bulle seule, lue ; une ligne partagée, l'étiquette courante gardée
et l'autre citée ; deux bulles qui se contredisent, un conflit ; un texte libre
« L6 », non lu ; un cercle et un texte « L7 » de cartouche, non lus ; les
étiquettes courantes inchangées ; les nœuds avec séparateur ; la file
proposée. Le même plan rejoint les tests de traçabilité.
