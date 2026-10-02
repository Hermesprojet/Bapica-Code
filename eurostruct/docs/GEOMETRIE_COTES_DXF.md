# Les cotes DXF : ce qu'AutoCAD affiche, ce que le produit lit

> Audit écrit **avant** le code (§ 0 à 5), puis la mesure, après (§ 6 et
> suivants). Le plan de fondations réel n'est pas commité : il a été enregistré
> par AutoCAD (AC1027) et porte, pour chaque cote de l'espace objet, le texte
> qu'AutoCAD affiche et la mesure qu'il a calculée. C'est la vérité terrain.
> S'y ajoutent les 24 plans fabriqués, les 36 DXF d'exemple d'ezdxf et un plan
> synthétique qui porte chaque type de cote, valeur connue par construction.

## 0. Deux lecteurs, une même mesure

| chemin | où il lit | ce qu'il fait de la cote |
|---|---|---|
| propositions (`lecteurs/dxf.py` → `extracteurs/dxf_entites.py`) | espace objet, entités `DIMENSION` | propose `dimension` (ou `grid_spacing` sur un calque d'axes) : mesure × `DIMLFAC`, ou le nombre du texte forcé |
| géométrie (`geometrie/primitives.py` → `geometrie/cotes.py`) | espace objet **et** blocs insérés | cotes linéaires et alignées seulement ; rattachées, elles corroborent une proposition géométrique |

Les deux mesurent par ezdxf, `Dimension.get_measurement()`.

## 1. La vérité terrain

* **le texte affiché** : celui du bloc de la cote (`*D…`), rendu par AutoCAD,
  arrondi selon `DIMRND` et `DIMDEC`. Un exposant empilé après un nombre est
  lu comme ses décimales : « 3 037⁵ » vaut 3 037,5 (cotes en cm, millimètres
  en exposant) ;
* **le code 42** : la mesure qu'AutoCAD a calculée et enregistrée — en radians
  pour un angle ; −1 pour les cotes des références externes liées.

Une valeur extraite est **juste** si elle tombe dans l'arrondi d'affichage de
la cote : la moitié du dernier chiffre affiché, ou de `DIMRND`.

## 2. Ce que la mesure dit

**Plan de fondations** : 1 519 occurrences de cotes — 1 017 dans l'espace
objet, 502 dans des blocs insérés —, aucune en espace papier.

| type (code 70) | occurrences | lues par le produit | affiché (exemples) | extrait | hors arrondi d'affichage | écart |
|---|---|---|---|---|---|---|
| linéaire (0) | 1 343 | 819 | 880 ; 2538.5 | 880 ; 2 538,563 | **0** | — (`DIMRND` 0,5) |
| **alignée (1)** | 151 | 106 | 617.5 ; 757.5 ; 810 | 77,877 ; 741,010 ; 803,533 | **82** | médiane −79 %, de −0,6 % à **−100 %** |
| rayon (4) | 4 | 2 | R710 ; R305 | 710 ; 305 | 0 | — (« R » non dit) |
| diamètre (3) | 3 | 1 | ∅63 | 63 | 0 | — (« ∅ » non dit) |
| angulaire 3 points (5) | 2 | 1 | « 504 » (texte forcé) | proposé « dimension 504 » | — | un angle de 94,6° proposé comme longueur |
| angulaire 2 lignes (2) | 13 | 0 (blocs non lus) | 90° ; 115° ; 82° | — | — | — |
| `ARC_DIMENSION` | 3 | 0 (entité non lue) | 258 (longueur d'arc) | — | — | — |
| ordonnée (6) | 0 | — | — | — | — | — |

Les cotes « non lues » des blocs sont sur des calques ou des insertions
invisibles : le plan imprimé ne les montre pas.

Ce que l'erreur des cotes alignées atteint :

* **36 propositions** viennent de cotes alignées : **29 sont fausses**
  (564 proposé 551,675 ; 30 proposé 6,237 ; 100 proposé **0**) ;
* dans le modèle, 113 cotes alignées : **62 rattachées mais discordantes**
  (la mesure fausse contredit la géométrie), 1 concordante, 50 non rattachées.

**Contre AutoCAD lui-même** (code 42, espace objet) : la distance entre les
points 13 et 14 égale la mesure d'AutoCAD pour **110 cotes alignées sur 110**
(écart ≤ 2,5·10⁻¹²) ; la mesure d'ezdxf égale celle d'AutoCAD pour les 905
cotes linéaires, rayons et diamètres.

**Plan synthétique** (ezdxf, cm ; les cotes alignées y sont écrites comme
AutoCAD les écrit — voir § 3) :

| cote | attendu | extrait | écart |
|---|---|---|---|
| linéaires horizontale, verticale, tournée de 30° | 3 000 ; 2 500 ; 1 366,025 | idem | 0 |
| alignée 3-4-5 | 500 | 300 | −40 % |
| alignée verticale | 700 | **0** | −100 % |
| alignée à 45° | 1 414,214 | 1 000 | −29,3 % |
| alignée, `DIMLFAC` 0,1 | 500 | 300 | −40 % |
| texte forcé « 500 » sur une alignée de 500 | concordant | **discordant** (`forced_mismatch`) | confiance plafonnée à tort |
| rayon 40 ; diamètre 63 | R40 ; ∅63 | 40 cm ; 63 cm | nature perdue |
| angle 90° ; angle 60° | 90° ; 60° | **« 90 cm » ; « 60 cm »** | un angle proposé comme longueur |
| ordonnées X, Y | 1 200 ; 300 | rien, sans le dire | — |
| longueur d'arc | 157,08 | rien (entité non lue) | — |
| bloc en mm (`DIMLFAC` 0,1) inséré au 1/10 : linéaire, alignée | 600 ; 600 | **60 ; 36** | −90 % ; −94 % |

Les 24 plans fabriqués et les 36 DXF d'exemple n'ont que des cotes linéaires
(lues justes) : **aucun test ne contenait de cote alignée**, d'angle, de rayon
ou de bloc mis à l'échelle.

## 3. Les causes, exactes

1. **Cote alignée mesurée comme sa projection horizontale.** Dans ezdxf 1.4.4,
   `MEASUREMENT_TOOLS[DIM_ALIGNED]` est `measure_linear_distance`, la mesure
   d'une cote **tournée** : la projection des points 13 et 14 sur l'angle
   `dxf.get("angle", 0)`. Or le code 50 n'appartient qu'aux cotes tournées,
   horizontales ou verticales : AutoCAD ne l'écrit pas pour une cote alignée
   (151 sur 151 dans le plan réel). L'angle vaut alors 0, et la « mesure » est
   |Δx|. Les seules alignées justes du plan sont horizontales. ezdxf, lui,
   écrit une cote « alignée » comme une cote tournée (type 0, code 50 = sa
   direction) : ses propres allers-retours ne voient jamais le défaut — ni les
   plans fabriqués du produit.
2. **Cote d'un bloc mis à l'échelle.** Le texte d'une cote de bloc est calculé
   dans les coordonnées du bloc (mesure du bloc × `DIMLFAC`) et ne change pas
   avec l'échelle de l'insertion. Le chemin géométrique multiplie par
   `DIMLFAC` la mesure de la copie déjà mise à l'échelle. Dans le plan réel,
   les 338 copies concernées (référence externe en mm, `DIMLFAC` 0,1, insérée
   au 1/10) sont invisibles : aucun effet mesuré ; sur un plan où elles sont
   visibles, la valeur est fausse du facteur d'échelle.
3. **Un angle proposé comme une longueur.** Le chemin des propositions
   propose toute `DIMENSION` dont la mesure est un nombre : un angle (en
   degrés) devient une « dimension » dans l'unité du dessin ; une cote
   angulaire au texte forcé (« 504 » sur un angle de 94,6°) devient
   « dimension 504 ».
4. **Rayon et diamètre sans leur nature.** La valeur est juste ; la
   proposition dit « cote 40 » là où le plan dit « R40 ».
5. **Texte forcé jugé contre la mauvaise mesure.** Sur une cote alignée, la
   discordance d'un texte forcé se juge contre |Δx| : fausse alarme (« 500 »
   sur une alignée de 500), confiance plafonnée à 0,4.

Ce qui n'est **pas** un défaut : la proposition porte la mesure, le plan
l'arrondi (`DIMRND`, `DIMDEC`) — 2 538,563 contre « 2538.5 ». La mesure est
la géométrie ; l'arrondi est celui de l'affichage.

## 4. La règle

1. **Une mesure par type, la même pour les deux lecteurs**
   (`lecteurs/dxf_cotes.py`) :
   * linéaire (tournée, horizontale, verticale) : la projection sur l'angle de
     la cote — inchangée ;
   * **alignée : la distance entre les points 13 et 14** ;
   * rayon, diamètre : la distance des points 10 et 15 — inchangée ;
   * angulaire : un angle, en degrés — **jamais une longueur** ;
   * ordonnée et autres types : non mesurées.
2. **Une cote de bloc affiche sa mesure dans le bloc** × `DIMLFAC` ; la mesure
   de la copie placée sert seulement à la géométrie (rattachements).
3. **Ne sont proposées que des longueurs** : linéaires, alignées, rayons,
   diamètres. Un rayon dit « R », un diamètre « ∅ ». Chaque proposition cite
   son type (`dimension_type`).
4. **La mesure d'AutoCAD est citée, et une contradiction est signalée** : si
   le fichier porte le code 42 (≥ 0) et qu'il diffère de la mesure calculée
   (au-delà d'un millionième), la proposition le dit
   (`measurement_conflict`) et sa confiance est plafonnée à 0,4 — rien n'est
   arrondi, rien n'est choisi entre les deux.
5. **Ce qui n'est pas proposé est compté** : le compte rendu d'analyse donne
   les cotes lues par type (`dimension_types`), angles, ordonnées et
   `ARC_DIMENSION` compris.

Ce qui ne change pas : la mesure des cotes linéaires, rayons et diamètres ;
`DIMLFAC` dans l'espace objet ; les textes forcés ; la logique des
rattachements ; les cotes des feuilles PDF ; la forme du modèle structurel.
Les propositions changent : la version de l'extracteur passe à
`eurostruct-extraction/0.4.0`.

## 5. Attendu, et comment c'est validé

Attendu sur le plan de fondations : les 82 alignées hors arrondi tombent à 0 ;
les 29 propositions fausses deviennent justes ; les alignées rattachées
deviennent concordantes là où la géométrie l'est ; « 504 » n'est plus proposé
comme une longueur ; R et ∅ sont dits. Attendu sur le plan synthétique : chaque
longueur égale sa valeur de construction ; aucun angle proposé.

Validation, avant tout commit du code : l'audit rejoué (avant, après) sur le
plan réel et le plan synthétique ; les 63 plans du balayage habituel ; les
suites d'extraction et d'API ; le harnais des documents.

## 6. Mesure, après

**Plan de fondations**, chaîne complète du produit ; avant = `ff2f886`.

| | avant | après |
|---|---|---|
| cotes alignées lues, hors arrondi d'affichage | 82 sur 106 | **0** sur 106 |
| linéaires, rayons, diamètres hors arrondi | 0 | 0 — mêmes valeurs |
| propositions | 354 | 335 |
| — tirées de cotes alignées | 36, toutes de la mauvaise mesure (29 fausses de plus d'une demi-unité) | 36 justes : 18 sous leur poignée, 18 fusionnées avec une proposition de même valeur (doublons : 633 → 651) |
| — tirées d'un angle | 1 (« dimension 504 ») | 0 ; l'angle est compté |
| rayon, diamètre | « cote 710 », « cote 63 » | « cote R710 », « cote ∅63 » |
| cotes du modèle | 1 041 | 1 041 ; 111 alignées changent de mesure et d'affichage |
| cotes rattachées : concordantes / discordantes | 93 / 65 | **155 / 3** |
| entraxes corroborés par une cote concordante | — | 4, confiance + 0,05 |
| axes, poteaux, pieux, voiles, unité | — | identiques |
| compte rendu | « 1 016 cote(s) » | et par type : 902 linéaires, 110 alignées, 2 rayons, 1 diamètre, 1 angle, 1 longueur d'arc |

Les 3 cotes rattachées qui restent discordantes sont des linéaires (5, 15,
15) accrochées à un côté de poteau dont elles mesurent un décalage : un
défaut de rattachement, antérieur, que la mesure ne touche pas.

**Ailleurs** : les 62 autres plans du balayage (24 plans fabriqués, 36 DXF
d'exemple d'ezdxf, deux feuilles PDF) donnent les mêmes modèles et les mêmes
propositions, textes compris ; l'audit des cotes des 55 DXF du corpus lit
chaque cote à l'identique. **Plan synthétique** : chaque longueur égale sa
valeur de construction (alignées 500, 700, 1 414,214, 1 000 ; `DIMLFAC`
500 ; bloc au 1/10 : 600 et 600) ; « 450 » sur une alignée de 450 n'est plus
discordant ; aucun angle n'est proposé ; ordonnées et longueur d'arc sont
comptées.

## 7. Ce qui reste

* **Ordonnées** : non mesurées — aucun plan d'AutoCAD n'en porte pour
  valider la mesure ; comptées (`dimension_types`), jamais proposées.
* **`ARC_DIMENSION`, `LARGE_RADIAL_DIMENSION`** : non lues ; comptées
  (`longueur_arc`, `rayon_raccourci`). Le plan réel porte une longueur d'arc
  (258), que le produit ne propose pas.
* **Angles** : jamais proposés (aucune catégorie d'angle). La mesure d'ezdxf
  d'une cote angulaire peut être l'angle rentrant (270° pour 90°) : elle ne
  sert à rien ici.
* **Cotes de blocs** : jamais proposées (le chemin des propositions ne lit que
  l'espace objet) ; dans le modèle, elles corroborent. **Espace papier** : non
  lu (aucune cote dans le plan réel).
* **L'arrondi d'affichage** : la proposition porte la mesure (2 538,563), le
  plan l'arrondi (« 2538.5 », `DIMRND` 0,5) — voulu : la mesure est la
  géométrie.
* **Cote miroir** (extrusion −Z) : la direction d'une cote linéaire, dans le
  modèle, ignore le repère de l'objet ; aucune dans le corpus, non éprouvé.
* **Code 42 et `DIMLFAC` ≠ 1** : aucun cas dans les plans d'AutoCAD lus ; la
  garde accepte la mesure brute ou mise à l'échelle. La garde ne porte que
  sur les propositions, pas sur le modèle.
* **Lecture de réparation** : sur un fichier aux poignées en double
  (`duplicate_handles.dxf` d'ezdxf), la réparation perd les 7 cotes avant
  toute mesure — défaut de lecture, pas des cotes.

## 8. Tests

`test_cotes_dxf.py` (15), sur `dxf_cotes_de_tous_types`, dont les alignées
sont écrites comme AutoCAD les écrit : la mesure (alignée sans code 50 : 500,
700, 1 000, 1 000 ; code 42 rendu, −1 ignoré) ; les propositions (alignées
justes, linéaires inchangées, « R » et « ∅ », aucun angle, ordonnées et arc
comptés, code 42 cité, mesure contredite signalée et plafonnée) ; le modèle
(alignées justes, texte forcé jugé contre la vraie mesure, cote de bloc au
1/10). Sur le code d'avant, 13 des 15 échouent ; les deux autres sont l'alignée
horizontale (qu'ezdxf mesurait juste) et les linéaires inchangées — vrais
avant comme après. Le plan rejoint les tests de traçabilité.

## 9. Risques en production

* **Les analyses déjà enregistrées** gardent leurs valeurs fausses, sous
  `eurostruct-extraction/0.3.0` ou avant ; une valeur confirmée l'est pour
  toujours (décision immuable). Une proposition d'avant ne dit pas le type de
  sa cote : seule une nouvelle analyse (0.4.0) les distingue. À faire avant
  tout usage : relancer l'analyse des DXF déposés, et revoir chaque
  `dimension` ou `grid_spacing` « dxf » confirmée dont la position (points de
  définition, enregistrés) n'est ni horizontale ni verticale.
* **Moins de propositions** : les angles ne sont plus proposés ; des valeurs
  corrigées rejoignent des propositions identiques.
* **La garde du code 42** plafonne la confiance d'une cote dont le fichier se
  contredit (code 42 périmé, écrit par un autre logiciel) : voulu — signalé,
  pas caché.
* **ezdxf** : la mesure d'une alignée ne passe plus par `get_measurement()` ;
  une correction en amont ne changera rien ici.
