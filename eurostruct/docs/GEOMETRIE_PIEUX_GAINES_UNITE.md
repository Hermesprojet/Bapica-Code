# Pieux, gaines, étiquettes d'axes, unité — conception

> Conception écrite **avant** le code, à partir de ce qu'un plan de structure
> réel a montré. Elle complète [`GEOMETRIE_DXF.md`](GEOMETRIE_DXF.md) et
> [`GEOMETRIE_PDF.md`](GEOMETRIE_PDF.md) : mêmes modules, quatre défauts
> mesurés, quatre règles. Le plan réel n'est pas commité ; il est désigné ici
> « plan de fondations » (DXF R2013, 16 Mio, sous-sol d'un bâtiment sur pieux).
> Les § 8 à 10, écrits après, disent ce que l'implémentation a ajouté, ce que
> les plans réels ont donné, et ce qui reste. Une vérification depuis un
> dépôt propre a ensuite corrigé ce document ; chaque correction le dit.

## 0. Point de départ mesuré

| ce que le plan de fondations contient | mesuré |
|---|---|
| espace objet | 3 205 entités, dont 1 016 cotes, 506 cercles, 436 textes ; une xréf liée (« feuille voisine ») dont une partie des calques est gelée |
| pieux | **475**, chacun dessiné **deux fois** : `Pr_Pieux_coupe` (continu) et le même calque dans la xréf (caché) ; 455 × Ø 63, 20 × Ø 60 ; une paroi de **pieux sécants** (cercles qui se chevauchent), remplis par des hachures sur un calque qui ne dit pas « pieu » (`Pr_Hach_Beton_Cache`), les lentilles de chevauchement sur `Pr_Hach_Pieux_Coupe` |
| poteaux réels | 62 poteaux préfabriqués coupés (`Pr_Béton_préfab_coupé`, hachurés) : 50 × 50, 30 × 30, 60 × 30 |
| socles | 13 carrés cachés 170 × 170 (`Pr_Beton_Cache`), **concentriques** à un poteau préfabriqué |
| gaine d'ascenseur | un chevron plein (`Ombre`) dans une cage ; le même symbole sur les deux feuilles PDF d'architecte, où la cage elle-même (1,9 × 1,8 m) contient la cabine, la machinerie, la lettre de l'ascenseur |
| unité | `$INSUNITS = 0` ; aucune mention « cotes en cm » ; mais la présentation « H » écrit **« 1/100 »** au cartouche, et sa fenêtre montre **8 400 unités sur 840 mm de papier** |

**Avant ce lot**, le modèle lu donnait **175 poteaux, dont 62 vrais** :

| « poteau » | nombre | ce que c'est |
|---|---|---|
| cercles `Pr_Pieux_coupe` aux nœuds | 44 | pieux |
| polygones de hachures (`Pr_Hach_Beton_Cache`, `Pr_Hach_Pieux_Coupe`) | 54 | remplissages et lentilles des pieux sécants |
| carrés cachés 170 × 170 | 13 | socles autour des poteaux préfabriqués |
| chevron plein (`Ombre`) | 1 | symbole de gaine d'ascenseur |
| cercle Ø 28 sur un calque d'annotation (`T_COTEX`) | 1 | annotation |

Sur les feuilles PDF étaient des « poteaux » : feuille B, la cage d'ascenseur
(rectangle de 1,96 × 1,87 m hors tout), le chevron d'ombre de la gaine, deux
chevrons de gaines techniques (`TB1`, `TB3`) et un polygone de masquage blanc
en L ; feuille A, le chevron d'ombre de la gaine, un chevron de gaine
technique et un nuage de révision. *(Précisé à la vérification : la première
rédaction disait « quatre chevrons pleins ».)* Quatre axes restaient
sans étiquette, chacun entre une **bulle** à un bout et une **lettre de 54 pt**
(l'identifiant d'un noyau, « A », « B », « C ») à l'autre — 3,4 fois la hauteur
des étiquettes de bulle (15,8 pt).

## 1. Les pieux

### 1.1 Un rôle, nommé dans les quatre langues du produit (et l'espagnol)

Le rôle **`pieu`** reconnaît, dans un nom de calque ou de bloc :

| langue | formes reconnues |
|---|---|
| FR | `PIEU`, `PIEUX`, `MICROPIEU(X)` |
| EN | `PILE`, `PILES`, `PILING` |
| NL | `PAAL`, `PALEN`, et les composés courants `HEIPAAL`, `BOORPAAL`, `SCHROEFPAAL`, `PREFABPAAL`, `VIBROPAAL`, `FUNDERINGSPALEN` ; la tête `PAALKOP(PEN)` |
| DE | `PFAHL`, `PFÄHLE`, et `BOHRPFAHL`, `RAMMPFAHL`, `MIKROPFAHL`, `GRÜNDUNGSPFAHL` ; la tête `PFAHLKOPF`, `PFAHLKÖPFE` |
| ES | `PILOTE(S)` — jamais `PILOTIS`, qui en français désigne des poteaux |

Les composés sont **listés**, pas devinés : « paal » est une sous-chaîne de
`BEPAALD` (néerlandais, « déterminé »).

Le rôle **`fondation`** reconnaît les éléments de fondation qui ne sont pas des
pieux : `SEMELLE(S)`, `MASSIF(S)`, `PILE CAP`, `PILECAP`, `FOOTING(S)`,
`POER(EN)`, `EINZEL-` / `STREIFENFUNDAMENT(E)`, `PFAHLKOPFPLATTE(N)`,
`PFAHLROST`. Il est lu **avant** `pieu` (« PILE_CAP » est un massif, pas un
pieu) ; un massif n'est jamais un poteau ni un pieu, et n'est pas compté.
*(Corrigé à l'implémentation : cette liste rangeait d'abord ici `PAALKOP` et
`PFAHLKOPF`, qui désignent la tête du pieu — § 8.)*

Ordre de priorité : `cote`, `fondation`, `pieu`, puis les rôles existants
(`texte`, `niveau`… `axe`, `hachure`). Conséquences voulues : les textes de
`PIEUX_TEXTE` sont des **repères de pieux** ; les niveaux de `PIEUX_NIVEAUX` ne
sont pas des niveaux de plancher ; `Pr_Pieux_axe` n'est **pas** un axe de grille.

### 1.2 Les pieux deviennent des éléments du modèle

1. **Germes** : les cercles et les contours fermés (hors hachures) dont le
   rôle est `pieu` ; un bloc de pieu inséré donne les siens.
2. **Doublons** : même centre et même taille à 5 % près → un seul pieu, deux
   preuves (le dessin et sa copie dans la xréf).
3. **Dessin du pieu** : un contour fermé, de n'importe quel calque, est absorbé
   par un pieu s'il **coïncide** avec lui, ou si la moitié au moins de ses
   sommets sont **sur le bord** d'un ou deux pieux et que son centre est dedans
   — remplissages, lentilles de pieux sécants, croissants. Un poteau posé sur
   un pieu n'a pas ses sommets sur le bord du pieu : il n'est pas absorbé.
4. **Hachures orphelines** de rôle `pieu` : un pieu si elles sont compactes
   (≥ 0,9 de leur enveloppe convexe) ; sinon comptées comme fragments.
5. **Repère** : un texte de rôle `pieu`, ou qui nomme un pieu (« PIEU 12 »,
   « pile P3 »), rattaché au pieu le plus proche ; **jamais** à un poteau, un
   voile ou une poutre.

Un pieu porte : centre, diamètre (ou côtés), nœud de grille éventuel, repère,
preuve. **Aucune valeur n'en est proposée** : le dimensionnement des
fondations profondes est hors du domaine validé du moteur (interdiction 6) ;
le modèle les montre et les compte (`counts.piles`).

### 1.3 Ce qui ne devient plus jamais un poteau

Une forme de rôle `pieu` ou `fondation` ; une forme absorbée par un pieu ; un
cercle de pieu comme **bulle** d'axe ; un texte de pieu comme repère d'élément.

## 2. Gaines, trémies, socles : une section de poteau est pleine et compacte

Mesuré sur les candidats « par la forme » (aucun calque ni bloc ne dit
« poteau ») :

| candidat | contours fermés **dedans** | aire / enveloppe convexe |
|---|---|---|
| 62 poteaux préfabriqués (vrais) | 0 | 1,00 |
| 13 socles 170 × 170 | 3 (le poteau, sa hachure) | 1,00 |
| cage d'ascenseur (PDF) | 25 (cabine, machinerie) | 1,00 |
| chevrons de gaine (DXF, PDF) | — | **0,25 à 0,34** |

Quatre règles — une cinquième est venue à l'implémentation (§ 8) — pour les
seuls candidats reconnus **par la forme** (un poteau nommé par son calque ou
son bloc garde la règle existante) :

* **contenant** — une forme qui contient strictement un autre contour fermé
  (ou un cercle) plus petit que 90 % de son petit côté n'est pas une section :
  c'est un socle, un massif, une gaine, une pièce ;
* **compacité** — une forme dont l'aire est inférieure à la moitié de son
  enveloppe convexe n'est pas une section (chevron, flèche, symbole) ; un
  poteau en L courant reste au-dessus (≈ 0,7) ;
* **croix** — un rectangle barré de ses deux diagonales est une trémie, comme
  la détection des dalles le dit déjà : la règle est partagée ;
* **nom** — un texte posé dans la forme qui la nomme (`GAINE`, `ASC.`,
  `ASCENSEUR`, `MONTE-CHARGE`, `TRÉMIE`, `VIDE`, `RÉSERVATION`, `SHAFT`,
  `LIFT`, `VOID`, `OPENING`, `KOKER`, `SCHACHT`, `AUFZUG`, `SPARING`,
  `AUSSPARUNG`, `DURCHBRUCH`) ;
* **enceinte** *(ajoutée à l'implémentation, § 8)* — un contour **vide** posé
  dans une enceinte continue, vide, de la taille d'un poteau n'est pas une
  section : c'est la cabine dans sa cage.

Chaque candidat écarté est compté par raison dans le compte rendu du modèle
(`column_candidates_rejected`) : `non_compact`, `contenant`,
`ouverture_barree`, `ouverture_nommee`, `dans_une_enceinte`, et, avant ces
règles, `pieu`, `fondation`, `dessin_de_pieu`.

**Ce qui reste, et pourquoi** : le cercle Ø 28 sur `T_COTEX` est seul à son
nœud, compact, vide ; rien de mesurable ne le distingue d'un poteau rond. Il
reste un faux positif connu (confiance 0,6), plutôt qu'une règle sur un sigle
de bureau d'études.

## 3. Étiquettes d'axes

Des dix-sept axes du plan de fondations restés sans étiquette, dix n'en ont
pas de dessinée : neuf finissent sur des pieux (files de pieux `D_AXE_*`), le
dixième n'a aucun texte à moins de 120 unités de ses bouts. Ils restent sans
étiquette.

*Corrigé à la vérification* (la première rédaction disait que les dix-sept
n'avaient pas d'étiquette) : les **sept autres** (calque `…C_AXES` d'une autre
référence externe liée) finissent exactement sur une bulle de rayon 40 dont le
texte, « L1 » à « L10 », est au centre. L'étiquette existe ; elle n'est pas
lue. Ce défaut est antérieur à ce lot (la base lit ces axes de la même façon) ;
il n'est pas corrigé ici (§ 10). *Corrigé ensuite*, avec sa vraie cause, dans
[`GEOMETRIE_BULLES_LETTRES_CHIFFRES.md`](GEOMETRIE_BULLES_LETTRES_CHIFFRES.md) :
le calque de la bulle (`…_TITRE_COMMUN-SSOL`) est bien lu `cadre` par son nom,
comme on l'avait écrit, mais la bulle est classée `axe` par son bloc, et ce
classement n'empêchait rien ; c'est le motif des étiquettes qui refusait des
lettres suivies de chiffres.

Les quatre conflits des feuilles PDF opposent une bulle à une lettre libre de
54 pt. Deux règles, sûres parce qu'elles comparent des preuves de force
différente :

* **hauteur** — quand le dessin a des étiquettes en bulle, un texte libre n'est
  candidat que si sa hauteur est entre la moitié et le double de leur hauteur
  médiane. Sans bulle, rien ne change (les grilles étiquetées en texte seul
  restent lues) ;
* **rang** — une bulle ou un bloc l'emporte sur un texte libre. Le texte écarté
  est cité dans `label_source.discarded`. **Deux preuves de même force qui se
  contredisent restent un conflit** : l'axe reste sans étiquette, et la raison
  est dite.

Et un cercle de rôle `pieu` ou `fondation` n'est jamais une bulle : un pieu
numéroté « 12 » au bout d'une file de pieux n'étiquette pas un axe.

## 4. L'unité d'un DXF qui ne la déclare pas

Ce que chaque indice dit, sur le plan de fondations :

| indice | ce qu'il dit |
|---|---|
| `$INSUNITS = 0` | rien |
| `$MEASUREMENT = 1` | métrique — ni mm, ni cm, ni m |
| cotes : `DIMLFAC = 1`, aucun suffixe | les nombres affichés sont des unités du dessin, sans unité |
| notes (« diamètre de 6 à 16 mm ») | l'unité d'un diamètre de barre, pas celle du dessin |
| tailles (poteaux 50, pieux 63, entraxes 880) | plausibles en cm — une plausibilité n'est pas une source |
| hauteurs de texte (30, 25) | cohérentes avec cm au 1/100, mais aussi avec mm au 1/10 |
| **présentation « H »** | **échelle écrite « 1/100 » ; fenêtre : 8 400 unités du modèle sur 840 mm de papier, soit 10 unités par mm ; papier en mm** |

**La règle : deux sources, et une unité exacte.** Pour chaque présentation
(papier en mm ou en pouces, à l'échelle de traçage citée) : les échelles
écrites `1/n` ou `1:n` (textes et attributs de la présentation, un niveau de
bloc) et chaque fenêtre (rapport `r` = hauteur de vue / hauteur sur le papier).
Une paire donne `n × mm de papier / r` millimètres par unité ; elle désigne une
unité si ce nombre est celui de `mm`, `cm`, `m`, `in` ou `ft` **à 0,5 % près**.
L'unité est établie si toutes les fenêtres qu'une échelle écrite explique
désignent **la même** unité, et une seule. Ici : 100 × 1 / 10 = 10 → **cm**,
écart 0 %.

Refus, dits dans `unresolved` (`unite`) : aucune échelle écrite ; aucune paire
qui tombe sur une unité ; deux unités possibles (ambiguïté) ; deux fenêtres qui
se contredisent ; et une mention écrite (« cotes en mm », règle existante) qui
contredit la présentation. Quand les deux règles concordent, les deux sources
sont citées.

Mesuré sur 36 DXF réels d'exemple (dépôt d'ezdxf) : un seul a des fenêtres, et
n'écrit aucune échelle — refus ; **aucune unité déduite à tort**.

## 5. Contrat, écran

* modèle (`eurostruct.structure/1`, champs ajoutés, **facultatifs** pour les
  modèles déjà enregistrés) : `piles` (id, repère, forme, centre, diamètre ou
  côtés, contour hors cercle, nœud, confiance, preuve), `counts.piles` ;
  `units.source = echelle_de_presentation` et ses preuves ; `label_source.discarded` ;
* compte rendu : `piles` (nombre, diamètres, fragments) et
  `column_candidates_rejected` (par raison) ;
* écran : les pieux dessinés (cercles fins) et comptés ; l'origine de l'unité
  dite (« échelle 1/100 écrite dans la présentation H, fenêtre à 10 unités par
  mm ») ;
* aucune migration : aucune catégorie de proposition n'est ajoutée.

## 6. Tests

Des DXF et PDF **fabriqués** : paroi de pieux sécants dessinée deux fois avec
remplissages et lentilles ; pieux par bloc ; repère de pieu ; massif nommé
`PILE_CAP` ; socles concentriques ; cage d'ascenseur avec cabine et chevron ;
rectangle barré ; « GAINE » écrite ; grande lettre au bout d'un axe ; deux
bulles contradictoires (le conflit reste) ; présentation 1/100 à 10 unités
par mm (cm), 1/50 à 10 (refus), 1/100 et 1/10 écrits pour une fenêtre
(ambiguïté), sans échelle écrite (refus), `$INSUNITS` déclaré (la déclaration
prime). Le vocabulaire : chaque forme reconnue, `PILOTIS` et `BEPAALD` refusés.

## 7. Ce qui sera mesuré

Sur le plan de fondations et les deux feuilles PDF, avant / après : poteaux
(vrais, faux par catégorie), pieux, axes et axes étiquetés, entraxes et leur
unité, propositions ; ce qui reste faux, et pourquoi.

## 8. Ce que l'implémentation a ajouté à la conception

* **Têtes de pieux.** `PAALKOP` et `PFAHLKOPF` désignent la tête du pieu, pas
  un massif : elles sont lues `pieu`. Le massif de tête est `POER` en
  néerlandais, `PFAHLKOPFPLATTE` en allemand (`fondation`).
* **Une cinquième règle de section, « dans une enceinte ».** Une cage
  d'ascenseur fabriquée, dessinée avec une cabine fermée, a rendu la cabine
  « poteau » : un contour VIDE posé dans une enceinte CONTINUE, vide, de la
  taille d'un poteau n'est pas une section. Une enceinte CACHÉE (un socle, sous
  la coupe) ne compte pas : le poteau qu'elle porte reste un poteau ; et le
  contour d'un poteau hachuré, qui a un jumeau plein (sa hachure), reste sa
  preuve.
* **Les candidats écartés sont comptés par contour**, une fois, même dessinés
  deux fois (la polyligne et ses traits, le calque et la copie de la xréf).
* **L'échelle citée est le champ du cartouche** (« 1/100 » seul, ou précédé
  de « Éch. », « Schaal », « Scale ») plutôt qu'un modèle de titre qui la
  répète.

## 9. Ce que les plans réels ont donné, avant et après

Mesuré sur le code commité, en local ; ni les plans ni leurs sorties ne sont
dans le dépôt.

**Plan de fondations (DXF)**

| | avant | après |
|---|---|---|
| poteaux | 175, dont 62 vrais | **63** : les 62 poteaux préfabriqués — 50 × 50 (30), 30 × 30 (18), 60 × 30 (7), 30 × 50 (2), 30 × 90 (2), 30 × 65, 40 × 40, 35 × 50 — et le cercle d'annotation (§ 10) |
| faux poteaux | 113 | **1** |
| pieux | — | **477** : 455 × Ø 63, 20 × Ø 60, et 2 dessinés par leur seule hachure ; 1 660 contours absorbés comme dessin de pieu, 1 fragment |
| voiles | 22 | **4**, de 25 cm : les 18 autres étaient les échantillons d'épaisseur de trait d'une légende, que l'unité connue rend implausibles (1,9 à 10,2 mm). C'est l'unité qui les écarte, pas une règle : l'échelle écrite retirée, l'unité n'est plus établie et ils redeviennent des voiles (mesuré à la vérification) |
| unité | non déclarée | **cm** : « 1/100 » écrit au cartouche, fenêtre de 8 400 unités sur 840 mm de papier, soit 10 mm par unité ; écart 0 % |
| axes (étiquetés) | 60 (43) | 60 (43), les mêmes étiquettes — des 17 autres, 10 n'ont pas d'étiquette dessinée et 7 ont une bulle qui n'est pas lue (§ 3, corrigé à la vérification ; lues depuis : 50 étiquetés, voir `GEOMETRIE_BULLES_LETTRES_CHIFFRES.md`) |
| entraxes | 47 mesurés, sans unité | 47 mesurés, **en cm**, dont 28 entre deux axes étiquetés (880, 500, 400, 800, 800 · 617,5, 540, 617,5 · 622,5 · 4 × 810 · 750, 500, 750, 750, 750, 850 · 629, 190, 209 · 757,5, 760, 810 · 617,5, 540, 617,5) ; 45 propositions distinctes |
| propositions géométriques | 146 | **109** : largeurs et profondeurs de poteaux 39 → 11 (2 pour le socle 170 × 170, 26 par le regroupement des repères décrit plus bas), diamètres 4 → 1, épaisseurs de voile 10 → 4 |

Candidats écartés, comptés par contour (166) : 98 de rôle `pieu` aux nœuds —
les cercles de 50 pieux, chacun dessiné sur son calque et dans la xréf, et 48
hachures du calque des pieux ; 54 dessins de pieux (les remplissages des pieux
sécants, sur un calque de béton caché de la xréf) ; 13 contenants (les
socles) ; 1 non compact (le chevron de la gaine).

**Deux effets que le premier relevé ne disait pas** (mesurés à la
vérification) :

* **Repères de poteaux.** Dans la base, chaque socle 170 × 170 (faux poteau)
  prenait le texte « C03-xx » posé dessus, et le poteau préfabriqué qu'il
  entoure prenait le texte « S## » du socle, à 189 unités. Sans les socles,
  chaque poteau prend son propre texte « C03-xx », à 49 unités ; le lecteur de
  repères, inchangé, lit « C03-50 » comme « C03 ». Les 62 poteaux préfabriqués
  portent donc tous le repère « C03 » (49 l'avaient déjà dans la base), et les
  13 groupes « S## » rejoignent les groupes « C03 » : ce regroupement retire 26
  des 28 propositions de section ; les valeurs proposées ne changent pas.
* **Confiance.** L'unité établie lève la pénalité « unité non déclarée »
  (0,2) : chaque proposition géométrique du plan gagne 0,2 (poteaux 0,45 →
  0,65), 0,15 pour les 34 lignes d'axe qui atteignent le plafond de 0,9.

**Feuilles PDF d'architecte**

| | feuille B (avant → après) | feuille A (avant → après) |
|---|---|---|
| poteaux | 7 → **2** | 4 → **1** |
| axes étiquetés | 18 / 20 → **20 / 20** | 8 / 10 → **10 / 10** |
| conflits d'étiquettes | 2 → **0** | 2 → **0** |

Écartés. Feuille B : la cage d'ascenseur, 1,96 × 1,87 m hors tout
(contenant : elle contient la cabine) ; son chevron d'ombre, un polygone de
masquage blanc en L le long du mur de la gaine (*corrigé à la vérification* :
la première rédaction disait « un masque en chevron ») et deux chevrons de
gaines techniques, `TB1` et `TB3` (non compacts, 0,28 à 0,34). Feuille A : le
chevron d'ombre de la gaine d'ascenseur et un chevron de gaine technique (non
compacts) ; un **nuage de révision** rouge de 1,92 × 1,42 m (contenant).
Chaque forme est dessinée deux fois (remplissage et trait) : 9 et 5 contours
écartés.

Les quatre axes sont étiquetés par leur bulle ; la lettre de 54 pt n'est plus
candidate : feuille B, « 6 » (contre « C ») et « 2 » (contre « B ») ;
feuille A, « D » (contre « A ») et « 2 » (contre « B »). Aucune autre
étiquette n'a changé. Les nœuds de ces axes portent désormais leur nom
(« Q6 » au lieu de « 0.3xQ »).

**Unité, sur un corpus.** Le code commité, sur les 36 DXF d'exemple d'ezdxf
lus comme le produit les lit (lecteur de réparation) : 35 n'ont aucune
présentation qui parle d'échelle, 1 a trois fenêtres et aucune échelle écrite
— refus. Aucune unité n'est déduite, à tort ou à raison : le corpus ne contient
aucun exemple positif ; la règle n'est validée positivement que sur le plan de
fondations et les plans fabriqués.

**Suites.** Sur le commit de l'implémentation, la suite canonique
(`./run_tests.sh --require-db`, PostgreSQL 16 jetable) : **COMPLET**, sept
surfaces vertes — moteur 1 138, importeur 113, extraction 313 réussis ; API
259 réussis, 340 ignorés, aucun échec ; 30 barrières de harnais, toutes
refusées ; 15 groupes de garanties SQL ; cohérence des artefacts. Le harnais
des documents, relancé seul : 34 réussis, dont le plan de fondations fabriqué
(11 pieux, 4 poteaux, unité cm lue dans la présentation, aucun diamètre de
poteau proposé). Résultat local : rien n'en est affirmé pour Supabase.

**Vérification.** Tous les chiffres de ce § ont été reproduits depuis des
extractions propres de la base (4615291) et de la branche (74e245a), sans
cache, en relisant les fichiers bruts par la chaîne du produit. Chaque poteau
disparu correspond à un rejet enregistré ; aucun poteau n'apparaît qui
manquait à la base. Les 18 plans fabriqués antérieurs donnent les mêmes
résultats avant et après (seule la clé `counts.piles` s'ajoute), comme 35 des
36 DXF d'exemple (le dernier gagne la raison du refus d'unité). La suite
canonique, relancée depuis un clone propre du dépôt distant au commit
74e245a : **COMPLET**, mêmes comptes.

## 10. Ce qui reste, et pourquoi

* le cercle Ø 28 sur un calque d'annotation, au bord de la paroi de pieux :
  rond, vide, seul à son nœud — rien de mesurable ne le distingue d'un poteau
  rond ; il garde la confiance 0,6 et son diamètre est proposé ;
* feuille B : deux contours non remplis de 32,4 × 17,6 cm, autour de tronçons
  de mur en béton au droit de l'axe Q — peut-être de vrais poteaux, non
  vérifiés (*corrigé à la vérification* : 30 × 22 cm était leur boîte alignée
  sur la feuille, 29,6 × 22 cm ; 32,4 × 17,6 cm est leur rectangle minimal) ;
* feuille A : une barre rouge pleine de 1,20 × 0,11 m à un nœud (élancement
  10,6) — sans doute pas un poteau. Elle passe la borne d'élancement de 4
  parce qu'un contour qui n'est pas reconnu comme rectangle est mesuré par sa
  boîte alignée sur la feuille (1,20 × 0,36 m, rapport 3,3) : logique
  antérieure à ce lot (*corrigé à la vérification* : la première rédaction
  donnait ces dimensions de boîte pour celles de la barre) ;
* deux pieux dessinés par leur seule hachure n'ont pas de diamètre (contour en
  croissant) ;
* le nuage de révision de la feuille A n'est écarté que parce qu'il contient
  d'autres contours : un nuage vide, à un nœud, serait encore un candidat
  (vérifié : vidé en mémoire de ce qu'il contient, il redevient un poteau) ;
* la cabine d'ascenseur n'est écartée (« dans une enceinte ») que si la cage a
  elle-même la taille d'un poteau plausible : 2,0 m au plus quand l'unité est
  connue, 0,3 fois l'entraxe médian sinon. Sans unité (plan fabriqué sans
  présentation, ou échelle refusée), ou avec une cage de 2,3 × 2,2 m (essai à
  la vérification), la cabine de 1,2 × 1,0 m reste un poteau ;
* sept axes du plan de fondations restaient sans étiquette alors que leur
  bulle (« L1 » à « L10 ») est lisible — défaut antérieur à ce lot, corrigé
  depuis (§ 3) : la cause était le motif des étiquettes, pas le cartouche ;
* six entraxes de 10 à 44 cm (cinq valeurs proposées) séparent un axe de file
  de pieux (`D_AXE_*`) d'un axe du bâtiment, ou deux files de pieux : ce ne
  sont pas des entraxes de grille, et ils sont proposés — comportement
  antérieur à ce lot ;
* une unité ne se déduit que d'une présentation qui écrit son échelle : un DXF
  sans présentation, ou sans échelle écrite, reste sans unité — et le dit.
