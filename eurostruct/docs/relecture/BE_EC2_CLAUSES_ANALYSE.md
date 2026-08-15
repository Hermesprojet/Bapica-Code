# Analyse des clauses EC2 belges — §6.2 et §9.2

**Document dépouillé** : `NBN EN 1992-1-1 ANB:2010 (F)`, 1re éd., août 2010,
31 pages, exemplaire `NBN_EN_1992-1-1_ANB_2010(F).pdf`,
SHA-256 `3a19536221aef69b16435b88bc05d7aee05cebe823e98cb292e49e48fe68dcdd`.

> Cet exemplaire **n'est pas** celui déjà enregistré au catalogue
> (`7951964092a4…`). Même édition, rendu différent — et ce rendu-ci a un
> tableau 7.1N-ANB lisible, ce que l'autre n'avait pas. Voir §8.

## Convention de pagination

Les références de page du jeu de données actuel sont **ambiguës et parfois
fausses** : `§6.2.2(1)` et `§7.2(2)` y portent tous deux « p. 17 », alors
qu'ils sont sur deux pages différentes. La couverture FR + la couverture NL
décalent le folio imprimé de deux rangs par rapport à l'index PDF.

Ce document donne donc **les deux**, systématiquement :

| repère | signification |
|---|---|
| `folio 15` | le numéro **imprimé en bas de page**, celui qu'un ingénieur cite |
| `PDF 17` | l'index de page dans le fichier, celui qu'un script ouvre |

Relation vérifiée sur six pages : `folio = PDF − 2`.

---

## Le point méthodologique qui commande tout le reste

Les six clauses demandées disent toutes la même chose, sous une forme ou une
autre :

> « **NOTE** La valeur recommandée (Formule 6.6N) est normative. »

L'Annexe Nationale belge **ne réimprime pas** l'expression. Elle la *désigne*
et la rend normative. Il faut donc distinguer deux choses que le jeu de
données actuel confond :

1. **La décision** — « en Belgique, c'est cette formule qui s'applique ».
   Elle est documentée, datée, paginée, traçable à l'ANB. Provenance :
   `NATIONAL_ANNEX`.
2. **Le contenu de l'expression** — le texte de la Formule 6.6N elle-même.
   Il est dans la **norme de base** `NBN EN 1992-1-1:2005`.

**Le catalogue ne contient aucun Eurocode de base. Aucun. Zéro sur les
quatre pays.**

Conséquence directe et sans échappatoire : pour ces six clauses, la décision
belge est traçable, **le contenu ne l'est pas**. Les valeurs actuellement
portées dans `be.json` (0,6 ; 250 ; 0,08 ; 0,75 ; 0,75 ; 1,0) ne proviennent
d'aucun document détenu — elles ont été semées depuis la recommandation EN,
de mémoire. Sous l'interdiction n° 2 du projet, ce sont des valeurs
**non sourcées**.

Elles ne sont pas pour autant de simples `EUROCODE_DEFAULT` en attente de
promotion : la Belgique **a déjà décidé** qu'elles s'appliquent. L'état exact
est `NATIONAL_ANNEX_PENDING` — nationalement adoptée, texte non encore
transcrit depuis la norme de base.

---

## 1. `alpha_cw` — §6.2.3(3)

| rubrique | contenu |
|---|---|
| **Clause** | `NBN EN 1992-1-1 ANB:2010`, §6.2.3(3), NOTE 3 |
| **Page** | folio 15 · PDF 17 |
| **Texte ANB** | « NOTE 3 : L'expression de α<sub>cw</sub> recommandée (Formules 6.11aN à cN) est normative. » |

**Valeur ou formule.** Ce n'est **pas** le scalaire `1,0` que porte
aujourd'hui `be.json`. L'ANB rend normative une expression à **quatre
branches** (6.11aN, 6.11bN, 6.11cN), fonction de σ<sub>cp</sub>/f<sub>cd</sub>.
La branche « 1,0 » n'est que le cas non précontraint.

Le texte des trois formules est dans `NBN EN 1992-1-1:2005`, **non détenue**.
Il n'est pas recopié ici : ce serait le citer de mémoire.

| rubrique | contenu |
|---|---|
| **Conditions d'application** | Bielles comprimées, §6.2.3. Le découpage en branches se fait sur σ<sub>cp</sub> rapporté à f<sub>cd</sub> |
| **Variables** | `sigma_cp` (contrainte moyenne de compression), `f_cd` |
| **Type de règle** | `conditional_rule` — quatre branches sur un même seuil continu |
| **Représentation** | `ConditionalRule` avec bornes sur `sigma_cp / f_cd`, chaque branche portant soit un scalaire soit une `Formula` |
| **Test** | Continuité aux bornes (0,25 f<sub>cd</sub> et 0,5 f<sub>cd</sub>) ; le cas non précontraint rend exactement 1,0 ; refus explicite hors domaine (σ<sub>cp</sub> ≥ f<sub>cd</sub>) |
| **Confiance** | **`NATIONAL_ANNEX_PENDING`** — décision belge lue et citée ; texte des formules 6.11aN–cN non traçable. Bloquant : `NBN EN 1992-1-1:2005` |

> ⚠️ Le scalaire `1,0` actuellement en base est juste **pour une poutre non
> précontrainte et faux dès qu'il y a précontrainte**. Il est présenté sans
> condition : c'est la même classe d'erreur que `v_min` côté français.

---

## 2 et 3. `nu1_coeff` et `nu1_fck_divisor` — §6.2.2(6)

| rubrique | contenu |
|---|---|
| **Clause** | `NBN EN 1992-1-1 ANB:2010`, §6.2.2(6) |
| **Page** | folio 15 · PDF 17 |
| **Texte ANB** | « **6.2.2 (6)** Éléments pour lesquels aucune armature d'effort tranchant n'est requise — NOTE La valeur recommandée (formule 6.6N) est normative. » |

**Valeur ou formule.** L'ANB adopte la Formule 6.6N sans la réimprimer. Cette
formule est **une** expression de ν en f<sub>ck</sub>. Le jeu de données
actuel la découpe en **deux scalaires indépendants** (`nu1_coeff = 0,6` et
`nu1_fck_divisor = 250`), ce qui est une reconstruction : rien dans l'ANB ne
nomme deux paramètres ici, et deux scalaires séparés autorisent des
combinaisons qui n'existent dans aucun texte.

**Anomalie de désignation à lever.** §6.2.3(3) NOTE 1 écrit :

> « La valeur de ν₁ recommandée (ν₁ = ν, Formule **6.6N-ANB**) est normative. »

Le suffixe `-ANB` suggère une formule 6.6N *modifiée par l'annexe*. Or la
chaîne « 6.6N-ANB » apparaît **une seule fois dans les 31 pages** et aucune
formule portant ce nom n'y est imprimée. Deux lectures restent possibles —
coquille éditoriale, ou renvoi à une formule absente du document — et **le
document en main ne permet pas de trancher**. Question à porter au NBN.

| rubrique | contenu |
|---|---|
| **Conditions** | §6.2.2(6), éléments sans armatures d'effort tranchant. §6.2.3(3) rappelle ν₁ = ν pour les éléments avec armatures |
| **Variables** | `f_ck` (MPa) |
| **Type de règle** | `formula` — **une** formule, pas deux constantes |
| **Représentation** | Une `Formula` unique nommée `nu_strength_reduction(f_ck)`. Les deux entrées actuelles fusionnent |
| **Test** | Décroissance monotone en f<sub>ck</sub> ; borne haute atteinte à f<sub>ck</sub> → 0 ; refus hors domaine des classes de béton couvertes |
| **Confiance** | **`NATIONAL_ANNEX_PENDING`** — décision lue ; texte de 6.6N non traçable ; désignation « 6.6N-ANB » non résolue |

---

## 4. `rho_w_min_coeff` — §9.2.2(5)

**C'est la clause la plus importante des six : l'ANB ne se contente pas
d'adopter, elle MODIFIE.**

| rubrique | contenu |
|---|---|
| **Clause** | `NBN EN 1992-1-1 ANB:2010`, §9.2.2(5) |
| **Page** | folio 20 · PDF 22 |
| **Texte ANB** | « NOTE La valeur de ρ<sub>w,min</sub> recommandée (Formule 9.5N) est normative. **Dans la formule 9.5N, lire f<sub>ywk</sub> à la place de f<sub>yk</sub>, exprimé en MPa.** » |

**Valeur ou formule.** Le coefficient de la formule est adopté, mais **le
dénominateur change de variable** : la Belgique divise par f<sub>ywk</sub>
— limite d'élasticité des **armatures d'effort tranchant** — là où l'EN
divise par f<sub>yk</sub>, celle des armatures longitudinales.

Ce n'est pas cosmétique. Dès que les étriers sont d'une nuance différente des
barres longitudinales, les deux formules donnent des sections minimales
différentes. Un moteur qui applique 9.5N telle quelle calcule **faux en
Belgique**, silencieusement, exactement comme `v_min` côté français.

Le jeu de données actuel stocke `rho_w_min_coeff = 0,08` : le coefficient
seul, sans la formule et donc **sans la substitution de variable**. La
modification belge est intégralement perdue.

| rubrique | contenu |
|---|---|
| **Conditions** | Poutres, section minimale d'armatures d'effort tranchant. f exprimé en MPa (l'ANB le précise) |
| **Variables** | `f_ck`, **`f_ywk`** (et non `f_yk`) |
| **Type de règle** | `formula` |
| **Représentation** | `Formula` prenant explicitement `f_ywk` en argument. Le nom de l'argument est la spécification — un `f_yk` renommé serait le même bug sous un autre nom |
| **Test** | Un cas où f<sub>ywk</sub> ≠ f<sub>yk</sub> doit donner un résultat **différent** de la formule EN. Un test qui passe avec f<sub>ywk</sub> = f<sub>yk</sub> ne prouve rien : c'est le seul cas où les deux formules coïncident |
| **Confiance** | **`NATIONAL_ANNEX_PENDING`** — la modification belge est lue et citée ; le texte de 9.5N reste à transcrire depuis la norme de base |

---

## 5. `s_l_max_coeff` — §9.2.2(6)

| rubrique | contenu |
|---|---|
| **Clause** | `NBN EN 1992-1-1 ANB:2010`, §9.2.2(6) |
| **Page** | folio 20 · PDF 22 |
| **Texte ANB** | « **9.2.2 (6)** Armatures d'effort tranchant – Espacement longitudinal maximum entre les cours d'armatures — NOTE La valeur de s<sub>l,max</sub> recommandée (Formule 9.6N) est normative. » |
| **Valeur ou formule** | Formule 9.6N adoptée telle quelle. C'est une expression en `d` et en l'inclinaison α des armatures, pas un scalaire |
| **Conditions** | Poutres, espacement longitudinal des cours d'armatures d'effort tranchant |
| **Variables** | `d` (hauteur utile), `alpha` (inclinaison des armatures d'effort tranchant) |
| **Type de règle** | `formula` |
| **Représentation** | `Formula s_l_max(d, alpha)`. Le `0,75` seul ne dit pas quoi multiplier |
| **Test** | Le cas α = 90° (étriers droits) doit être couvert explicitement ; monotonie en `d` |
| **Confiance** | **`NATIONAL_ANNEX_PENDING`** — décision lue ; texte de 9.6N non traçable |

---

## 6. `s_t_max_coeff` — §9.2.2(8)

| rubrique | contenu |
|---|---|
| **Clause** | `NBN EN 1992-1-1 ANB:2010`, §9.2.2(8) |
| **Page** | folio 21 · PDF 23 |
| **Texte ANB** | « **9.2.2 (8)** Armatures d'effort tranchant – Espacement transversal des brins verticaux — NOTE La valeur de s<sub>t,max</sub> recommandée (Formule 9.8N) est normative. » |
| **Valeur ou formule** | Formule 9.8N adoptée. Elle comporte un terme en `d` **et un plafond absolu en millimètres** — le scalaire `0,75` perd le plafond |
| **Conditions** | Poutres, espacement transversal des brins verticaux |
| **Variables** | `d` |
| **Type de règle** | `formula` — expression avec plafond, donc un `min()` |
| **Représentation** | `Formula s_t_max(d)` retournant `min(coeff·d, plafond)`. Le plafond est la partie que le modèle scalaire ne peut pas porter |
| **Test** | Un cas de grande hauteur utile où le **plafond** gouverne, et non le terme en `d` — sans quoi le plafond n'est jamais exercé |
| **Confiance** | **`NATIONAL_ANNEX_PENDING`** — décision lue ; texte de 9.8N non traçable |

---

## 7. `cot_theta_max` — §6.2.3(2)

**Seule des sept à être entièrement lisible et entièrement belge.** L'ANB ne
renvoie à rien : elle imprime sa propre formule.

| rubrique | contenu |
|---|---|
| **Clause** | `NBN EN 1992-1-1 ANB:2010`, §6.2.3(2) |
| **Page** | folio 15 · PDF 17 |

**Texte ANB, relevé mot pour mot :**

> **6.2.3 (2)** Limitation de l'inclinaison des bielles pour les éléments avec
> armatures d'effort tranchant
>
> NOTE Les valeurs limites de cot θ sont : 1,0 ≤ cot θ ≤ cot θ<sub>max</sub>
>
> $$\cot\theta_{max} = \left(2 + \frac{k_1 \cdot \sigma_{cp} \cdot b_w \cdot d \cdot s}{A_{sw} \cdot z \cdot f_{ywd}}\right) \le 3$$
>
> où σ<sub>cp</sub> ≤ 0,2 f<sub>cd</sub>

**Ce que cela veut dire, et pourquoi c'est grave.**

L'Eurocode recommande `1 ≤ cot θ ≤ 2,5`. La Belgique **remplace la borne
supérieure** par cette expression, plafonnée à 3.

Pour une poutre **non précontrainte**, σ<sub>cp</sub> = 0, donc :

$$\cot\theta_{max} = 2$$

**et non 2,5.** La règle belge est donc **plus sévère** que la recommandation
européenne dans le cas le plus courant. Un moteur qui, faute de mieux,
retomberait sur 2,5 produirait des armatures d'effort tranchant
**insuffisantes** — et le ferait sans rien signaler.

C'est la démonstration la plus nette de la règle que vous avez posée : ne
jamais déduire une valeur manquante depuis l'Eurocode quand l'Annexe
Nationale donne une règle différente. Ici, la déduction serait
non-conservative.

| rubrique | contenu |
|---|---|
| **Conditions** | Éléments **avec** armatures d'effort tranchant. Domaine de validité explicite : σ<sub>cp</sub> ≤ 0,2 f<sub>cd</sub>. Hors domaine → refus, pas d'extrapolation |
| **Variables** | `k_1` (0,15, §6.2.2(1)), `sigma_cp`, `b_w`, `d`, `s`, `A_sw`, `z`, `f_ywd`, `f_cd` |
| **Type de règle** | `function` — elle dépend de variables de calcul (géométrie **et** ferraillage), pas seulement de constantes normatives |
| **Représentation** | `NormativeFunction` recevant le contexte de calcul. À noter : elle dépend de `A_sw` et `s`, c'est-à-dire du **résultat** du dimensionnement — donc itérative, ou vérifiée a posteriori. Le modèle doit l'admettre |
| **Test** | (1) σ<sub>cp</sub> = 0 rend exactement 2,0 — le test qui aurait attrapé un repli sur 2,5 ; (2) le plafond 3 est atteint pour une précontrainte forte ; (3) σ<sub>cp</sub> > 0,2 f<sub>cd</sub> lève un refus explicite ; (4) cot θ_min = 1,0 est respecté |
| **Confiance** | **`NATIONAL_ANNEX`** — formule imprimée dans l'annexe, lue, transcrite. Reste à confirmer par un vérificateur nommé. Aucun document ne manque |

---

## 8. Deux découvertes hors périmètre demandé

### 8.1 Le tableau `w_max` est lisible sur cet exemplaire

Le blocage « page illisible » signalé dans l'audit **tombe**. Tableau 7.1N-ANB,
folio 18 · PDF 20, extrait :

| Classe d'exposition | Classe d'environnement | BA + précontraint non adhérent<br>(quasi-permanente) | Précontraint adhérent<br>(fréquente) |
|---|---|---|---|
| X0, XC1 | EI | 0,4 <sup>(note 1)</sup> | 0,2 |
| XC2, XC3, XC4 | EE1, EE2, EE3 | 0,3 | 0,2 <sup>(note 2)</sup> |
| XD1, XD2, XD3, XS1, XS2, XS3 | EE4, ES1, ES2, ES3, ES4 | 0,3 | Décompression |

L'ANB dit ce qu'elle change : « Le tableau 7.1N devient (**ajout de la mention
des classes d'environnement** associées aux classes d'exposition) ». Les
valeurs sont donc celles de l'EN, adoptées ; l'apport belge est la
**correspondance classe d'exposition ↔ classe d'environnement** (NBN B 15-001),
que le moteur ne porte pas du tout.

**Réserve à lever par un œil humain.** L'extraction colle les appels de note
aux valeurs : `0,4` + note 1 ressort en `0,41`, `0,2` + note 2 en `0,22`. La
séparation retenue ci-dessus est cohérente avec les notes 1 et 2 imprimées
sous le tableau, mais elle résulte d'une lecture d'artefact, pas d'une
certitude typographique. Statut : `NATIONAL_ANNEX_PENDING` jusqu'à
confirmation visuelle.

### 8.2 Une règle conditionnelle belge enregistrée sur un seul paramètre sur trois

§6.2.2(1), folio 15 · PDF 17 :

> « Les valeurs recommandées de C<sub>Rd,c</sub> (0,18/γ<sub>C</sub>),
> v<sub>min</sub> (0,035·k<sup>3/2</sup>·f<sub>ck</sub><sup>1/2</sup>) et
> k<sub>1</sub> (0,15) sont normatives. **Pour les dalles appuyées sur les
> bords, il faut multiplier ces valeurs par 1,25.** »

La majoration ×1,25 porte sur **les trois** paramètres. Dans `be.json` elle
n'est mentionnée que dans la note de `C_Rd_c_coeff` ; `v_min_coeff` et
`k1_shear` ne la portent pas. Un calcul de dalle appuyée sur les bords est
donc aujourd'hui faux sur deux termes sur trois.

C'est un `conditional_rule` sur le type d'élément — le même mécanisme que
`alpha_cc`, déjà en place.

### 8.3 §9.3.1.1(3) — des valeurs belges qui n'existent pas dans l'EN

Folio 21 · PDF 23. L'ANB **écrit ses propres valeurs**, sans renvoyer à l'EN :

- armatures principales : `s_max = 2,5 h ≤ 400 mm`
- armatures secondaires : `s_max = 3 h ≤ 450 mm`
- en zone de charge concentrée ou de moment maximal :
  principales `1,5 h ≤ 250 mm`, secondaires `2,5 h ≤ 400 mm`

Quatre branches, aucune dans la liste des paramètres attendus. C'est un
`conditional_rule` complet à ajouter, et un exemple direct de votre point 7 :
une exigence de calcul, pas un paramètre.

---

## Récapitulatif des sept fiches

| paramètre | type de règle | confiance | ce qui bloque |
|---|---|---|---|
| `alpha_cw` | `conditional_rule` | `NATIONAL_ANNEX_PENDING` | texte 6.11aN–cN (norme de base) |
| `nu1_coeff` + `nu1_fck_divisor` | `formula` (à fusionner) | `NATIONAL_ANNEX_PENDING` | texte 6.6N + désignation « 6.6N-ANB » non résolue |
| `rho_w_min_coeff` | `formula` | `NATIONAL_ANNEX_PENDING` | texte 9.5N ; **substitution f_ywk ← f_yk à préserver** |
| `s_l_max_coeff` | `formula` | `NATIONAL_ANNEX_PENDING` | texte 9.6N |
| `s_t_max_coeff` | `formula` | `NATIONAL_ANNEX_PENDING` | texte 9.8N (plafond mm) |
| `cot_theta_max` | `function` | `NATIONAL_ANNEX` | rien — vérificateur nommé seulement |
| `w_max` | `conditional_rule` | `NATIONAL_ANNEX_PENDING` | séparation des appels de note, à l'œil |

**Aucune des six clauses « à lire » n'était une simple constante.** Le modèle
scalaire ne pouvait en représenter aucune correctement — ce qui explique
qu'elles soient restées au stade de la recommandation EN.

**Un seul document lèverait cinq des sept blocages** : `NBN EN 1992-1-1:2005`,
la norme de base. Le catalogue n'en contient aucune, pour aucun des quatre
pays.
