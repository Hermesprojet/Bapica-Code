# Pieux, gaines, étiquettes d'axes, unité — conception

> Conception écrite **avant** le code, à partir de ce qu'un plan de structure
> réel a montré. Elle complète [`GEOMETRIE_DXF.md`](GEOMETRIE_DXF.md) et
> [`GEOMETRIE_PDF.md`](GEOMETRIE_PDF.md) : mêmes modules, quatre défauts
> mesurés, quatre règles. Le plan réel n'est pas commité ; il est désigné ici
> « plan de fondations » (DXF R2013, 16 Mio, sous-sol d'un bâtiment sur pieux).

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

Sur les feuilles PDF : la cage d'ascenseur (rectangle 1,9 × 1,8 m) et quatre
chevrons pleins (`TB1`, `TB3`…) étaient des « poteaux ». Quatre axes restaient
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
| NL | `PAAL`, `PALEN`, et les composés courants `HEIPAAL`, `BOORPAAL`, `SCHROEFPAAL`, `PREFABPAAL`, `FUNDERINGSPALEN` |
| DE | `PFAHL`, `PFÄHLE`, et `BOHRPFAHL`, `RAMMPFAHL`, `MIKROPFAHL`, `GRÜNDUNGSPFAHL` |
| ES | `PILOTE(S)` — jamais `PILOTIS`, qui en français désigne des poteaux |

Les composés sont **listés**, pas devinés : « paal » est une sous-chaîne de
`BEPAALD` (néerlandais, « déterminé »).

Le rôle **`fondation`** reconnaît les éléments de fondation qui ne sont pas des
pieux : `SEMELLE(S)`, `MASSIF(S)`, `PILE CAP`, `PILECAP`, `FOOTING(S)`,
`POER(EN)`, `PAALKOP(PEN)`, `PFAHLKOPF`, `EINZEL-` / `STREIFENFUNDAMENT`. Il est
lu **avant** `pieu` (« PILE_CAP » est un massif, pas un pieu) ; un massif n'est
jamais un poteau ni un pieu, et n'est pas compté.

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

Quatre règles, pour les seuls candidats reconnus **par la forme** (un poteau
nommé par son calque ou son bloc garde la règle existante) :

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
  `AUSSPARUNG`, `DURCHBRUCH`).

Chaque candidat écarté est compté par raison dans le compte rendu du modèle
(`column_candidates_rejected`).

**Ce qui reste, et pourquoi** : le cercle Ø 28 sur `T_COTEX` est seul à son
nœud, compact, vide ; rien de mesurable ne le distingue d'un poteau rond. Il
reste un faux positif connu (confiance 0,6), plutôt qu'une règle sur un sigle
de bureau d'études.

## 3. Étiquettes d'axes

Les dix-sept axes sans étiquette du plan de fondations n'en ont pas : axes de
files de pieux (`D_AXE_*`, terminés sur un pieu) et axes communs terminés par
une bulle **vide**. Ils restent sans étiquette.

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
