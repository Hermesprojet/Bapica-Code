# Pile normative EC2 Belgique — quelle version de chaque formule fait foi

Établi le 2026-08-15 **uniquement sur documents détenus**. Chaque affirmation
porte sa source, page comprise. Ce qui n'est pas établi est dit tel quel.

---

## Ce qui est établi, et par quoi

### F1 — L'ANB:2010 se lie explicitement à `2005 + AC:2008`

`NBN EN 1992-1-1 ANB:2010 (F)`, avant-propos national, **p. 3** puis
introduction **p. 4**, la même phrase deux fois :

> « La norme NBN EN 1992-1-1:2005 « Eurocode 2 : Calcul des structures en
> béton - Partie 1-1 : Règles générales et règles pour les bâtiments
> **(+ AC:2008)** » comprend l'annexe nationale NBN EN 1992-1-1 ANB:2010 qui a
> un caractère normatif en Belgique. »

et, **p. 3** :

> « Le corrigendum **NBN EN 1992-1-1/AC:2008**, tel que publié par le CEN, est
> ajouté à cette [norme] »

### F2 — L'ANB applique AC:2008 nommément dans deux clauses, et deux seulement

Recherche exhaustive sur les 31 pages. La mention `[Corrigendum EN 1992-1-1
:2008]` apparaît **deux fois** :

| page | clause | objet |
|---|---|---|
| p. 14 | §4.4.1.3(4) | enrobage |
| p. 17 | §6.2.5(2) | valeurs de c et µ, reprise de bétonnage |

**Aucune des cinq formules qui nous intéressent n'y figure.** Cela ne prouve
pas qu'AC:2008 les laisse intactes — l'ANB ne signale que ce qu'elle a besoin
de reformuler — mais c'est le seul indice disponible, et il est faible.

### F3 — L'ANB ne mentionne jamais AC:2010 ni A1:2015

Recherche exhaustive : zéro occurrence sur 31 pages. C'est attendu —
autorisation de publication **19 février 2010**, édition **août 2010** — et
cela veut dire que **l'ANB n'a pu prendre en compte ni l'un ni l'autre**.

### F4 — La pile complète de 1re génération, nommée par un document détenu

`NBN EN 1992-1-1:2023` (2e génération), **page 1**, mention « Replaces » :

> « Replaces NBN EN 1992-2/AC:2008, **NBN EN 1992-1-1/AC:2008**, **NBN EN
> 1992-1-1/AC:2010**, NBN EN 1992-3:2006, NBN EN 1992-2:2005, **NBN EN
> 1992-1-1/A1:2015**, **NBN EN 1992-1-1:2005** »

Cette ligne **confirme votre hypothèse sur les quatre documents** :
`AC:2008`, `AC:2010` et `A1:2015` existent tous les trois, tous publiés par le
NBN. `AC:2010` n'était pas une supposition à écarter.

### F5 — La 1re génération reste en vigueur

Même page 1 du document de 2023 :

> « This document **does not replace** the existing standard NBN EN
> 1992-1-1:2005 and its amendment NBN EN 1992-1-1/A1:2015 »

C'est l'état `not_yet_applicable` : publié, numéroté, authentique, sans force,
en attente de son Annexe Nationale. Le triage l'attrape déjà.

### F6 — Aucun `NBN EN 1992-1-1+A1 ANB` n'est connu

Ni sur disque, ni au catalogue, ni cité par aucun document détenu. Or le NBN
**a** rééedité l'ANB EC6 en `NBN EN 1996-1-1+A1 ANB:2016` précisément parce
que la base avait reçu son A1. Deux lectures de cette asymétrie, et le
document ne tranche pas :

- soit `A1:2015` n'a touché aucune clause à NDP, et aucune réédition n'était
  nécessaire ;
- soit une réédition existe et nous l'ignorons ;
- soit l'ANB:2010 reste formellement liée au texte pré-A1.

**Question à porter au NBN.** Elle n'est pas théorique : elle décide si
l'annexe détenue couvre, ou non, la base telle qu'amendée.

### F7 — L'ANB fixe TOUS les NDP

**p. 5** : « Tous les NDP sont fixés par la présente ANB ». Aucun choix n'est
laissé au projet individuel. Le moteur n'a donc jamais à demander un NDP EC2
à l'utilisateur en Belgique.

### F8 — L'ANB rend l'Annexe C normative

**p. 27** : Annexe C **normative** en Belgique ; annexes A, B, D, E, F, G, H,
I, J restent informatives. Point 7 de vos décisions : l'annexe C est une
exigence de calcul, pas une option.

### F9 — L'ANB introduit les symboles f<sub>ywk</sub> / f<sub>ywd</sub>

**p. 6** : « Ajouter dans la liste des symboles f<sub>ywk</sub> et
f<sub>ywd</sub> qui sont respectivement la limite d'élasticité caractéristique
et de calcul de l'acier des **étriers** ».

Corroboration directe de la substitution de §9.2.2(5) : la Belgique
**introduit le symbole** avant de s'en servir. Ce n'est pas une coquille.

---

## La matrice

Pour chaque formule : ce qui la rend applicable en Belgique, quelle version
fait foi, et par quoi c'est établi.

| formule | clause | rendue normative par | version faisant foi | établi ? |
|---|---|---|---|---|
| **6.6N** | §6.2.2(6) | ANB §6.2.2(6), folio 15 : « la valeur recommandée (formule 6.6N) est normative » | texte de `2005`, tel que modifié par `AC:2008` + `AC:2010` + `A1:2015` | **liaison : oui** (F1)<br>**contenu : NON** |
| **6.11aN–cN** | §6.2.3(3) | ANB §6.2.3(3) NOTE 3, folio 15 : « l'expression de α<sub>cw</sub> recommandée (Formules 6.11aN à cN) est normative » | idem | **liaison : oui**<br>**contenu : NON** |
| **9.5N** | §9.2.2(5) | ANB §9.2.2(5), folio 20, **+ modification belge** : « lire f<sub>ywk</sub> à la place de f<sub>yk</sub> » | texte de `2005` amendé, **puis** substitution belge appliquée par-dessus | **liaison : oui**<br>**modification belge : oui** (F9)<br>**contenu de base : NON** |
| **9.6N** | §9.2.2(6) | ANB §9.2.2(6), folio 20 | idem 6.6N | **liaison : oui**<br>**contenu : NON** |
| **9.8N** | §9.2.2(8) | ANB §9.2.2(8), folio 21 | idem 6.6N | **liaison : oui**<br>**contenu : NON** |

### Ce que « contenu : NON » veut dire exactement

**Aucun document détenu ne contient le texte de ces cinq formules**, ni dans
sa version 2005, ni amendée. Et **savoir si `AC:2008`, `AC:2010` ou `A1:2015`
les modifie ne peut être établi par aucun document en main.**

Votre crainte est donc entièrement fondée et je ne peux pas la lever :
**rien ne permet aujourd'hui d'affirmer que le texte de 2005 est encore le
texte applicable pour ces cinq formules.** Trois documents postérieurs ont pu
les toucher, et deux d'entre eux (`AC:2010`, `A1:2015`) sont postérieurs à
l'ANB elle-même, donc invisibles depuis elle.

L'ordre d'application est en revanche établi et sans ambiguïté :

```
EN 1992-1-1:2005                      texte de base
      + AC:2008                       corrigendum, incorporé par l'ANB (F1)
      + AC:2010                       corrigendum, postérieur à l'ANB (F4)
      + A1:2015                       amendement, postérieur à l'ANB (F4)
      + ANB:2010                      choix belges, modifications, ajouts
                                      -> §9.2.2(5): f_ywk remplace f_yk
                                      -> §6.2.2(1): ×1,25 dalles sur bords
                                      -> §6.2.3(2): cot θ_max propre
```

Une seule exception dans tout le lot : **`cot_theta_max`**. L'ANB ne renvoie à
rien — elle imprime sa propre formule. Aucun corrigendum, aucun amendement du
texte de base ne peut la modifier. Elle est intégralement établie, folio 15.

---

## Documents à acquérir — liste exacte

### Indispensables (4)

| # | référence exacte | pourquoi |
|---|---|---|
| 1 | `NBN EN 1992-1-1:2005` (version FR) | texte des cinq formules |
| 2 | `NBN EN 1992-1-1/AC:2008` | l'ANB l'incorpore explicitement (F1) — sans lui, la base détenue ne serait pas celle que l'ANB vise |
| 3 | `NBN EN 1992-1-1/AC:2010` | postérieur à l'ANB. Effet sur les cinq formules **inconnu** |
| 4 | `NBN EN 1992-1-1/A1:2015` | postérieur à l'ANB. Effet **inconnu** |

**À demander au NBN avant de commander les quatre séparément** : existe-t-il
une **version consolidée** `NBN EN 1992-1-1:2005+A1:2015` intégrant les
corrigenda ? C'est la pratique de plusieurs organismes, et cela réduirait
l'achat à un document. Je ne l'affirme pas pour le NBN : je n'ai pas son
catalogue.

### Question à poser en même temps

> L'annexe nationale `NBN EN 1992-1-1 ANB:2010` s'applique-t-elle à la norme
> de base telle qu'amendée par `A1:2015` ? Une annexe nationale rééditée
> (`NBN EN 1992-1-1+A1 ANB` ou équivalent) existe-t-elle ?

Motif : le NBN a rééedité l'ANB EC6 en `+A1` dans la situation analogue (F6).

### Non nécessaires à l'achat

- **Parties 1-2, 2 et 3** : les normes de base sont **déjà sur disque**
  (`NBN_EN_1992-1-2_2005(E)+AC`, `NBN_EN_1992-2_2005(E)`,
  `NBN_EN_1992-3_2006(E)`), ainsi que `NBN EN 1992-1-2:2004/A1:2019`.
- **`NBN EN 1992-1-1:2023`** : détenue, et sans force (F5). À cataloguer comme
  `not_yet_applicable`, pas à utiliser.

---

## Un défaut de catalogue révélé au passage

Le catalogue enregistre **zéro Eurocode de base**, pour les quatre pays. Or au
moins sept normes de base sont sur disque, non cataloguées :

```
NBN_EN_1992-1-2_2005(E)+AC.pdf          NBN_EN_1992-2_2005(E).pdf
NBN_EN_1992-3_2006(E).pdf               NBN EN 1992-1-2_2004_A1_2019_en.pdf
nbn_en_1992-1-1_2023_en.pdf             nbn_en_1992-1-2_2023_en.pdf
```

Elles ont été triées, correctement refusées comme sources de NDP — une norme
de base ne porte que des recommandations — **puis oubliées**. C'est une erreur
de raisonnement de ma part : « ne peut pas confirmer un NDP » a été traité
comme « sans intérêt », alors que ces documents portent le **texte des
formules** que les annexes rendent normatives.

Il faut un rôle de document distinct : `base_eurocode` détenu, jamais
autorisé à fixer un NDP, mais **autorisé à fournir le texte d'une expression**
qu'une annexe nationale désigne. C'est le chaînon qui manquait au modèle.

---

## Conséquence sur la suite

- **Transcription des cinq formules : bloquée**, en attente des 4 documents.
  Aucune ne sera écrite depuis la mémoire.
- **`cot_theta_max` : peut être préparé** — formule intégralement lue,
  provenance `NATIONAL_ANNEX`, statut non confirmé jusqu'à validation humaine.
- **`w_max` : reste `NATIONAL_ANNEX_PENDING`** jusqu'à confirmation visuelle
  des appels de notes.
- **Étapes 1 à 3** (rôles, `value_provenance`, types de règles) : indépendantes
  de tout document, peuvent démarrer.

**Le projet reste non compatible Belgique.** Sur les cinq formules, la
documentation elle-même n'est pas complète : la liaison est établie, le
contenu ne l'est pas.
