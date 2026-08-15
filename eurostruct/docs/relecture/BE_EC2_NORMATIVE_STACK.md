# Pile normative EC2 Belgique — quelle version de chaque formule fait foi

**Statut : RÉSOLU.** Établi le 2026-08-15 **uniquement sur documents détenus**.
Chaque affirmation porte sa source, page comprise.

> **Version du 15/08 au matin :** « le contenu des cinq formules n'est
> traçable à aucun document détenu ; quatre documents à acheter. »
> **Version après réception de `Gmail (7).zip` :** la pile complète est en
> main. **Aucun achat n'est nécessaire.** Le blocage est fermé.

---

## La pile, et où elle se trouve physiquement

| couche | référence | où |
|---|---|---|
| base | `NBN EN 1992-1-1:2005`, 1re éd. février 2005, indice B 15 | `NBN_EN_1992-1-1_2005(F)+AC.pdf`, **p. 7-253** |
| corrigendum | `EN 1992-1-1:2004/AC:2010` | même fichier, **p. 254-255** |
| corrigenda | « Modifications issues de l'`AC:2008` (et modifiées par l'`AC:2010`) » — **120 entrées** | même fichier, **p. 256-279** |
| amendement | `NBN EN 1992-1-1/A1` (1re éd. fév. 2015) = `EN 1992-1-1:2004/A1:2014` | `NBN_EN_1992-1-1_A1_2014(E).pdf`, 9 pages |
| annexe nationale | `NBN EN 1992-1-1 ANB:2010`, 1re éd. août 2010, indice B 15 | `NBN_EN_1992-1-1_ANB_2010(F).pdf`, 31 pages |

### ⚠️ Le piège de ce fichier

La couverture annonce **« (+AC:2010) »**, ce qui se lit spontanément comme
« corrigenda déjà intégrés ». **Ils ne le sont pas.** Ils sont **annexés** en
fin de volume et le corps porte toujours le texte de 2004.

**Vérification qui l'établit**, reproductible : §6.2.5(2) du corps (p. 109)
donne `c = 0,25 / 0,35 / 0,45` ; la **modification n° 29** du corrigendum
(p. 260) remplace exactement ces valeurs ; et l'ANB, p. 17, cite les valeurs
**corrigées** `0,025–0,10 / 0,20 / 0,40` sous la mention
`[Corrigendum EN 1992-1-1 :2008]`.

**Lire le corps sans lire les 120 modifications, c'est appliquer le texte de
2004.** C'est enregistré dans `contained_layers` au catalogue, et un test le
verrouille.

---

## Méthode de vérification des couches 2 et 3

**Corrigenda.** Les pages 256-279 sont une liste numérotée de **120
modifications**, chacune introduite par « *N. Modification(s) en X.Y.Z* ».
L'énumération complète a été extraite. Elle est l'inventaire exhaustif de ce
que les deux corrigenda changent.

**Amendement A1.** Neuf pages, lues intégralement. Son sommaire (p. 4)
énumère **sept** modifications : avant-propos, §3.3.2, §3.3.4, §6.4.5,
§11.6.4.2, §12.6.5.2, §H.1.2. Rien d'autre.

---

## Les cinq formules — résultat

### 1. `ν` — Expression (6.6N), §6.2.2(6)

| couche | verdict | preuve |
|---|---|---|
| **base** | `ν = 0,6·[1 − f_ck/250]`, f_ck en MPa | p. 102 du fichier. Reconstruite au caractère : `0,6` (x=106-114), crochet `[` (x=121,3), `1` (x=124,6), `−` (x=130,7), `f_ck` (x=141,8), **barre de fraction tracée x=138,5→156,5**, `250` en dessous, crochet `]` (x=157,2). Ce n'est donc pas « 0,61 » : le crochet sépare le 0,6 du 1 |
| **AC:2008 / AC:2010** | **non modifiée** | §6.2.2 est modifié (entrée n° 26) mais seulement au **paragraphe (1)**, reformulation sur N_Ed. L'Expression (6.6N) apparaît 6 fois dans les corrigenda : 2 fois comme « Tableau 9.6N » (autre objet), 2 fois comme « (11.6.6N) » (béton léger), 2 fois **citée** dans les modifications de §6.5.4. Jamais comme cible |
| **A1:2014** | **non modifiée** | absente des sept modifications |
| **ANB:2010** | adoptée telle quelle | §6.2.2(6), folio 15 : « La valeur recommandée (formule 6.6N) est normative » |

**➜ Règle belge : `ν = 0,6 · [1 − f_ck / 250]`, f_ck en MPa.**
Type : `formula`. Variable : `f_ck`.

> `nu1_coeff = 0,6` et `nu1_fck_divisor = 250` doivent **fusionner** en une
> formule unique. Deux scalaires séparés autorisent des combinaisons qui
> n'existent dans aucun texte.

**Réserve subsistante.** §6.2.3(3) NOTE 1 de l'ANB écrit « Formule
**6.6N-ANB** ». Aucune formule de ce nom n'existe dans les 31 pages de
l'ANB ni dans la base. L'EN, lui, dit en §6.2.3(3) Note 1 que « la valeur
recommandée de ν₁ est ν (voir l'Expression (6.6N)) ». La lecture cohérente
est ν₁ = ν, mais le suffixe reste **inexpliqué** : question au NBN.

**Second point ouvert.** L'EN §6.2.3(3) Note 2 offre une **alternative** —
si la contrainte de calcul des armatures d'effort tranchant est < 80 % de
f_ywk, on peut prendre ν₁ = 0,6 (f_ck ≤ 60 MPa) ou 0,9 − f_ck/200 > 0,5
(f_ck > 60 MPa), Expressions (6.10.aN)/(6.10.bN). L'ANB **corrige la
rédaction** de cette Note 2 sans la supprimer, ce qui suggère qu'elle reste
ouverte en Belgique. À trancher avant implémentation.

---

### 2. `α_cw` — Expressions (6.11.aN) à (6.11.cN), §6.2.3(3)

| couche | verdict | preuve |
|---|---|---|
| **base** | quatre branches, ci-dessous | p. 104, reconstruites avec leurs indices (`cpcdcpcd`, `cdcpcd`, `cpcdcdcpcd`) |
| **AC:2008 / AC:2010** | **non modifiées** | §6.2.3 est modifié (entrée n° 27) aux paragraphes **(1), (5), (6) et (8)** — pas au **(3)**, où vivent les 6.11. La chaîne « 6.11 » n'apparaît **0 fois** dans les 24 pages de corrigenda |
| **A1:2014** | **non modifiées** | absentes des sept modifications |
| **ANB:2010** | adoptées telles quelles | §6.2.3(3) NOTE 3, folio 15 : « L'expression de α_cw recommandée (Formules 6.11aN à cN) est normative » |

**➜ Règle belge :**

| condition | α_cw |
|---|---|
| structures **non précontraintes** | `1` |
| `0 < σ_cp ≤ 0,25 f_cd` | `1 + σ_cp/f_cd` (6.11.aN) |
| `0,25 f_cd < σ_cp ≤ 0,5 f_cd` | `1,25` (6.11.bN) |
| `0,5 f_cd < σ_cp < 1,0 f_cd` | `2,5·(1 − σ_cp/f_cd)` (6.11.cN) |

Type : `conditional_rule`. Variables : `sigma_cp`, `f_cd`.

> Le scalaire `1,0` actuellement stocké est **la branche non précontrainte
> seule**, présentée sans sa condition.

---

### 3. `ρ_w,min` — Expression (9.5N), §9.2.2(5)

| couche | verdict | preuve |
|---|---|---|
| **base** | `ρ_w,min = (0,08·√f_ck)/f_yk` | p. 179. **Le radical est tracé en vecteurs, pas en caractères** : quatre segments à x=130,3→150,4 dont la barre horizontale x=137,2→150,4, qui couvre exactement le `f` (x=137,6) et son indice `ck`. Le radical porte donc sur f_ck seul |
| **AC:2008 / AC:2010** | **non modifiée** | §9.2.2 **absent** des 120 entrées (seuls §9.2.1.4 et §9.2.4 y figurent). « 9.5N » : 0 occurrence |
| **A1:2014** | **non modifiée** | absente des sept modifications |
| **ANB:2010** | **MODIFIÉE** | §9.2.2(5), folio 20 : « La valeur de ρ_w,min recommandée (Formule 9.5N) est normative. **Dans la formule 9.5N, lire f_ywk à la place de f_yk, exprimé en MPa.** » |

**➜ Règle belge : `ρ_w,min = (0,08 · √f_ck) / f_ywk`, en MPa.**
Type : `formula`. Variables : `f_ck`, **`f_ywk`**.

> **La seule des cinq où la Belgique modifie le texte.** Corroboration
> indépendante : l'ANB p. 6 **introduit** les symboles f_ywk et f_ywd,
> « acier des **étriers** », avant de s'en servir. Ce n'est pas une coquille.

---

### 4. `s_l,max` — Expression (9.6N), §9.2.2(6)

| couche | verdict | preuve |
|---|---|---|
| **base** | `s_l,max = 0,75 d (1 + cot α)` | p. 179, extraction propre. `α` = inclinaison des armatures d'effort tranchant sur l'axe longitudinal |
| **AC:2008 / AC:2010** | **non modifiée** | §9.2.2 absent des 120 entrées. Les 2 occurrences de « 9.6N » sont des « **Tableau** 9.6N » (p. 267), objet différent de l'**Expression** (9.6N) |
| **A1:2014** | **non modifiée** | — |
| **ANB:2010** | adoptée telle quelle | §9.2.2(6), folio 20 |

**➜ Règle belge : `s_l,max = 0,75 · d · (1 + cot α)`.**
Type : `formula`. Variables : `d`, `alpha`.

> Homonymie à ne pas confondre : l'EN a **à la fois** un Tableau 9.6N et une
> Expression (9.6N). Une recherche par chaîne les mélange.

---

### 5. `s_t,max` — Expression (9.8N), §9.2.2(8)

| couche | verdict | preuve |
|---|---|---|
| **base** | `s_t,max = 0,75 d ≤ 600 mm` | p. 179 |
| **AC:2008 / AC:2010** | **non modifiée** | §9.2.2 absent. « 9.8N » : 0 occurrence |
| **A1:2014** | **non modifiée** | — |
| **ANB:2010** | adoptée telle quelle | §9.2.2(8), folio 21 |

**➜ Règle belge : `s_t,max = min(0,75 · d ; 600 mm)`.**
Type : `formula`. Variable : `d`.

> Le scalaire `0,75` stocké seul perd le **plafond de 600 mm**.

---

## Récapitulatif

| formule | modifiée par AC ? | modifiée par A1 ? | modifiée par l'ANB ? | type |
|---|---|---|---|---|
| 6.6N | non | non | non — adoptée | `formula` |
| 6.11aN–cN | non | non | non — adoptées | `conditional_rule` |
| 9.5N | non | non | **OUI — f_ywk ← f_yk** | `formula` |
| 9.6N | non | non | non — adoptée | `formula` |
| 9.8N | non | non | non — adoptée | `formula` |

**Le texte de 2005 est bien le texte applicable pour les cinq.** La crainte
était légitime — §6.2.2 et §6.2.3 *sont* touchés par les corrigenda, et il a
fallu lire ces deux entrées pour constater qu'elles visent d'autres
paragraphes.

---

## Tests exigés par ces résultats

Écrits ou à écrire selon qu'ils portent sur le catalogue (faits) ou sur le
moteur (transcription à venir).

| # | test | état |
|---|---|---|
| T1 | un `base_eurocode` est détenu et n'est **jamais** `acquired` | ✅ écrit |
| T2 | corps et corrigenda occupent des plages de pages **disjointes** — la preuve qu'ils ne sont pas fondus | ✅ écrit |
| T3 | la 2ᵉ génération est détenue et `not_yet_applicable` | ✅ écrit |
| T4 | `ν(f_ck)` décroît strictement ; borne haute 0,6 en f_ck → 0 | à écrire avec la transcription |
| T5 | `α_cw` : continuité aux bornes 0,25 f_cd et 0,5 f_cd ; le cas non précontraint rend exactement 1,0 ; refus hors domaine σ_cp ≥ f_cd | idem |
| T6 | `ρ_w,min` : **un cas où f_ywk ≠ f_yk doit donner un résultat différent de la formule EN**. Un test avec f_ywk = f_yk ne prouve rien — c'est le seul cas où les deux coïncident | idem |
| T7 | `s_l,max` : cas α = 90° (étriers droits) explicite ; monotonie en `d` | idem |
| T8 | `s_t,max` : un cas de grande hauteur utile où **le plafond gouverne** — sans quoi il n'est jamais exercé | idem |
| T9 | `cot θ_max` : σ_cp = 0 rend exactement **2,0** (et non 2,5) ; plafond 3 atteint sous forte précontrainte ; refus si σ_cp > 0,2 f_cd | idem |

---

## Questions restant ouvertes au NBN

1. **« Formule 6.6N-ANB »** (ANB §6.2.3(3) NOTE 1) — désignation sans référent
   dans aucun des deux documents.
2. **L'alternative ν₁ des Expressions (6.10.aN)/(6.10.bN)** reste-t-elle
   ouverte en Belgique ? L'ANB corrige la rédaction de la Note 2 sans la
   supprimer.
3. **L'ANB:2010 s'applique-t-elle à la base amendée par A1:2015 ?** Aucun
   `NBN EN 1992-1-1+A1 ANB` n'est connu, alors que le NBN **a** réédité l'ANB
   EC6 en `+A1` dans la situation analogue.
4. **NDP nouveau non fixé.** A1 introduit `k_max` en §6.4.5(1), recommandé
   1,5. L'ANB:2010 lui est antérieure et affirme p. 5 que « tous les NDP sont
   fixés » — vrai en 2010, **plus vrai après 2015**. Qui fixe `k_max` en
   Belgique ?

Aucune de ces quatre questions ne bloque les cinq formules. Les trois
premières concernent ν₁ et la portée de l'annexe ; la quatrième concerne le
poinçonnement, hors périmètre actuel.

---

## Achat

**Aucun.** Les quatre documents jugés indispensables le 15/08 au matin sont
tous en main. La liste d'achat est vide.
