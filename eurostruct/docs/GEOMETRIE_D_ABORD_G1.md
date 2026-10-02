# Géométrie d'abord — G1 : l'information DXF standard, lue sans rien décider

> **Statut : réalisé (`068fc3b`), mesuré au § 6.** Phase G1 de `GEOMETRIE_D_ABORD.md`
> (§ 11) : lire et exposer, dans les primitives, l'information DXF standard
> (niveau N1, § 1.1) dont les phases G2 à G6 auront besoin — **sans changer
> une seule décision**. Le résultat de G1 est invisible dans les sorties : il
> se prouve par un balayage du corpus, octet par octet, avant et après.

## 0. Ce que G1 garantit

| # | Garantie | Comment |
|---|---|---|
| I1 | Aucune décision ne change : aucun détecteur, aucune règle, aucun seuil ne lit un champ nouveau en G1. | Les champs ne sont consommés qu'à partir de G2 ; le balayage le prouve. |
| I2 | **Sorties identiques octet pour octet** : `DocumentAnalyse` (hors `octets` et `primitives_dxf`, internes) et `ResultatExtraction` (propositions, confiances, modèle structurel, comptes rendus), sur tout le corpus. | Balayage canonique avant/après (§ 5). |
| I3 | Égalité, hachage et construction positionnelle des primitives inchangés. | Tout champ nouveau d'une primitive est `kw_only` et `compare=False`. |
| I4 | Compte rendu inchangé : une `MLINE` reste comptée « entité non lue » (`entities_not_read`), car **aucun détecteur ne l'interprète** avant G5 ; sa géométrie est lue à côté. | Le compte `ecartees` est écrit avant la lecture N1, comme aujourd'hui. |
| I5 | Bornes inchangées : `PrimitivesDxf.nombre()` ne compte pas les listes nouvelles ; la liste des multilignes a sa propre borne. | Même `tronquee`, même statut `partiel`. |
| I6 | Aucune exception nouvelle ne remonte : un champ N1 illisible vaut `None`, l'incident est compté dans `n1_incidents` (interne, non exporté en G1). Une entité lisible aujourd'hui ne devient jamais « illisible ». | Lecture N1 isolée dans ses propres `try`. |
| I7 | Ni contrat, ni migration, ni version : aucune sortie ne change, donc `VERSION_EXTRACTEUR` reste `0.4.0` (règle du dépôt : la version change quand les propositions peuvent changer) et `export_contracts.py --check` doit passer sans écart. | Exposition par l'API Python interne de `PrimitivesDxf`, lue par `geometrie/*` à partir de G2. |

**Pourquoi rien n'est exporté en G1.** Ajouter un champ au modèle structurel
ou au compte rendu changerait les sorties (I2) et le contrat fermé
(`engine/schemas/structure.py`). L'exposition publique — `classified_by`,
`signature`, `names_agree`, candidats, compte rendu N1 — est en G6, avec le
contrat, l'écran et la version `0.5.0` (`GEOMETRIE_D_ABORD.md` § 8).

## 1. Les champs

Tous sont lus par `geometrie/primitives.py` dans la même ouverture du fichier
que la géométrie actuelle. Une feuille PDF n'a pas d'information DXF : ses
champs N1 restent vides (`None`, listes vides) ; elle a déjà ses styles
appris (`GEOMETRIE_PDF.md`).

### F1 — Motif des types de ligne

* **Champ** : `PrimitivesDxf.types_de_ligne : dict[str, MotifDeLigne]`, clé =
  nom en MAJUSCULES (comme `Primitive.type_ligne`), et
  `PrimitivesDxf.motif_de(type_ligne) -> MotifDeLigne | None`.
* **`MotifDeLigne`** : `nom` (tel qu'écrit), `elements` (longueurs signées,
  code 49 : > 0 trait, < 0 blanc, 0 point), `longueur` (code 40), `complexe`
  (un élément porte un texte ou une forme, code 74 ≠ 0), `classe`.
* **Source** : table `LTYPE`, une fois par fichier. Le type de ligne effectif
  d'une primitive est déjà résolu (`BYLAYER` → calque, `BYBLOCK` → `INSERT`) ;
  le motif se lit par ce nom effectif.
* **Classe** (`classe_de_motif(elements)`, fonction pure) :
  * aucun élément, ou aucun blanc → `continu` ;
  * un trait est « ponctuel » s'il est nul ou au plus 0,2 fois le plus long
    blanc ; sinon il est « long » ;
  * aucun trait long, au moins un ponctuel → `points` ;
  * des traits longs et (un ponctuel, ou un trait de moins de la moitié du
    plus long) → `mixte` (trait-point, trait-deux-points : ligne d'axe
    d'ISO 128, mais aussi bordure, fantôme) ;
  * sinon → `tirets`.

  Exemples (bibliothèque standard) : `CENTER` (3,175 ; −0,635 ; 0,635 ;
  −0,635) → `mixte` ; `DASHDOT` → `mixte` ; `PHANTOM`, `DIVIDE`, `BORDER` →
  `mixte` ; `DASHED`, `HIDDEN`, `ACAD_ISO02W100` → `tirets` ; `DOT`,
  `ACAD_ISO07W100` (0,5 ; −3) → `points` ; `Continuous` → `continu`.
* **La classe ne dépend jamais du nom** : renommer `CENTER` en `LT07` sans
  toucher au motif donne `mixte`.
* **Servira à** : signature B des axes (`mixte` parallèle à une famille,
  § 3.2), corroboration des pieux (`tirets` : sous le plan de coupe, § 4.1),
  exclusion des poutres vues dans les voiles (`tirets`, § 6.2), partitions
  apprises (§ 1.5).

### F2 — Remplissage des contours

* **Champs** : `Contour.remplissage : "plein" | "motif" | None` et
  `Contour.motif_hachure : str | None`.
* **Source** : `HATCH` et `MPOLYGON` — drapeau plein (code 70 ; 71 pour une
  `MPOLYGON`) → `plein` ; sinon lignes de motif présentes (codes 53 et
  suivants) → `motif` ; ni l'un ni l'autre (une `MPOLYGON` non remplie) →
  `None`. Le nom du motif (code 2, bibliothèque standard : `SOLID`, `ANSI31`,
  `AR-CONC`…) est lu tel quel : une `MPOLYGON` non remplie porte souvent le
  nom `SOLID`. `SOLID` et `TRACE` → `plein`, sans nom de motif. Les autres contours (polylignes
  fermées, bandes de polyligne épaisse, rectangles de traits) : `None`.
  `Contour.rempli` garde son sens actuel (le contour est rempli d'une façon
  ou d'une autre).
* **Servira à** : « coupé » des poteaux (C1) et des voiles (V1), où le plein
  et le motif seront cités ; le nom du motif n'est qu'une citation, jamais un
  critère (§ 1.1).

### F3 — Multilignes

* **Champ** : `PrimitivesDxf.multilignes : list[Multiligne]` (primitive :
  calque, type de ligne, source, couleur).
* **`Multiligne`** : `sommets` (code 11), `ferme` (code 71, bit 2),
  `justification` (code 70 : `haut`, `zero`, `bas`), `echelle` (facteur
  d'échelle effectif, code 40), `decalages` (décalage de chaque élément du
  style par rapport à la ligne des sommets, en unités du dessin :
  (décalage du style − décalage de justification) × échelle — le décalage de
  justification est le plus grand décalage pour `haut`, le plus petit pour
  `bas`, 0 pour `zero`), `elements` (le tracé de chaque élément : sommet +
  direction d'onglet × premier paramètre de l'élément, codes 12, 13, 41),
  `remplie` (style, drapeau de remplissage), et la propriété `epaisseur`
  (écart entre décalages extrêmes).
* **Une multiligne de bloc** : ezdxf (1.4.4) transforme les sommets d'une
  copie de bloc mais **ne met pas à l'échelle les décalages quand l'insertion
  est tournée** (il compare les composantes d'un vecteur tourné). Le lecteur
  corrige : échelle effective = échelle d'origine × échelle uniforme de
  l'insertion ; si l'insertion n'est pas à échelle uniforme, `decalages`,
  `elements` et `echelle` valent `None` (les sommets restent).
* **Compte rendu inchangé** (I4) : la multiligne reste comptée « entité non
  lue: MLINE » jusqu'à ce qu'un détecteur l'interprète (G5).
* **Borne** : au plus `PRIMITIVES_MAX` multilignes ; au-delà, l'incident est
  compté (I5).
* **Servira à** : voiles explicites (G5, § 6.2 : `MLINE` = voile candidat,
  épaisseur = `epaisseur`).

### F4 — Définitions de blocs et comptes d'insertions

* **Champ** : `PrimitivesDxf.definitions : dict[str, DefinitionDeBloc]`, clé
  = nom de la définition, pour chaque définition placée par au moins un
  `INSERT` lu (calque visible).
* **`DefinitionDeBloc`** : `nom`, `anonyme` (code 70, bit 1 : `*U`, `*X`…),
  `xref` et `superposee` (bits 4 et 8), `types` (nombre d'entités de chaque
  type DANS la définition), `attributs` (nombre d'`ATTDEF`), `fermes`
  (polylignes fermées), `insertions` (nombre d'`INSERT` lus qui la placent,
  référence externe et profondeur dépassée comprises), `copies` (nombre de
  copies dont le contenu a été lu : lignes × colonnes d'un `MINSERT`, 0 pour
  une référence externe ou au-delà de la profondeur).
* **Servira à** : bulle-bloc reconnue par sa STRUCTURE (une définition qui
  contient un cercle ou une polyligne fermée et UN attribut, § 3.2) ; bloc
  répété (poteaux C1, pieux, § 4.2 et § 5.2) ; repérage des fonds liés non
  chargés (`xref`, `superposee`).

### F5 — Échelle d'insertion

* **Champ** : `Insertion.echelle : (x, y)` (codes 41, 42) ; pour une copie
  imbriquée, l'échelle composée que donne la transformation d'ezdxf.
* **Servira à** : « même définition insérée à l'échelle 1 » (sections
  répétées, C1) ; échelle uniforme des multilignes de bloc (F3).

### F6 — Calques : dépendance d'une référence externe, couleur

* **Champs** : `InfoCalque.depend_xref : bool` (code 70, bit 16 : calque
  apporté par une référence externe non liée) et `InfoCalque.couleur`
  (couleur du calque, même codage que F7).
* **Servira à** : fond lié repérable (risque 4 de l'audit) ; résolution
  `BYLAYER` de F7.

### F7 — Couleur résolue de chaque primitive

* **Champ** : `Primitive.couleur : str | None` — `aci:N` (1 à 255) ou
  `rvb:#RRGGBB` (couleur vraie, code 420, qui l'emporte sur le code 62).
* **Résolution** (les règles du DAO, comme le calque et le type de ligne) :
  `BYLAYER` (256) → couleur du calque EFFECTIF (un élément de bloc sur `0` a
  pris le calque de l'`INSERT`) ; `BYBLOCK` (0) → couleur résolue de
  l'`INSERT` qui place l'entité ; hors bloc, `BYBLOCK` → `aci:7` (AutoCAD
  dessine ainsi un objet `BYBLOCK` hors bloc, comme le type de ligne
  `BYBLOCK` hors bloc est déjà lu `CONTINUOUS`) ; couleur d'un calque éteint
  (négative) → sa valeur absolue ; calque absent de la table → `aci:7` (il
  est créé à la lecture avec ses valeurs par défaut, comme son type de ligne
  est déjà lu `CONTINUOUS`) ; information illisible → `None`.
* **Servira à** : partitions anonymes (§ 1.5) — la couleur est une clé de
  regroupement, jamais un sens.

### Incidents de lecture N1

`PrimitivesDxf.n1_incidents : dict[str, int]` — table des types de ligne
illisible, multiligne illisible, couleur illisible, définition illisible,
multilignes au-delà de la borne. Interne en G1 (I2) ; exporté en G6.

## 2. Ce que G1 ne fait pas, et pourquoi

| Exclu | Raison |
|---|---|
| Recouper `$INSUNITS` (D1 de l'audit) | C'est une DÉCISION : elle change l'unité, donc les sorties. Phase à part. |
| Lire le préfixe `XREF$0$` des calques et blocs liés | Convention de nommage d'AutoCAD à la liaison, pas une information DXF ; relève du durcissement D4. |
| Épaisseur de trait (code 370) | Aucune signature de `GEOMETRIE_D_ABORD.md` ne l'utilise. |
| Classes de diamètre, bulles par structure, zone structurelle | Décisions de G2–G4. |
| Toute sortie nouvelle (modèle, compte rendu, contrat, écran) | G6, avec la version 0.5.0. |
| N1 d'une feuille PDF | Un PDF n'a ni table `LTYPE` ni hachure DXF ; il a ses styles appris. |

## 3. Tests de régression

Dans `extraction/tests/test_geometrie_n1.py`, sur des DXF fabriqués
(`fabrique_geometrie.dxf_information_n1`), un test au moins par champ :

* **F1** : classe de chaque motif de la bibliothèque standard et des motifs
  ISO ; motif renommé → même classe ; motif complexe (texte) → `complexe` ;
  résolution `BYLAYER` / `BYBLOCK` puis `motif_de` ; nom absent → `None`.
* **F2** : hachure pleine, hachure `ANSI31`, `SOLID`, polyligne fermée,
  `MPOLYGON`.
* **F3** : multiligne ouverte en haut / zéro / bas ; fermée ; dans un bloc
  tourné et mis à l'échelle (décalages corrigés) ; échelle non uniforme
  (`None`) ; sur calque gelé (rien) ; **toujours comptée « entité non lue »**.
* **F4** : comptes d'insertions et de copies (`INSERT`, imbriqué, `MINSERT`) ;
  `ATTDEF` ; polylignes fermées ; référence externe et superposée ; bloc
  anonyme.
* **F5** : échelle (2, −1) ; échelle composée d'un bloc imbriqué.
* **F6** : bit 16 ; couleur de calque éteint.
* **F7** : ACI, couleur vraie, `BYLAYER`, `BYLAYER` d'un élément sur `0`
  dans un bloc, `BYBLOCK` dans un bloc, `BYBLOCK` hors bloc.
* **Invariance** : une primitive ne diffère pas par sa couleur
  (`compare=False`) ; `nombre()` n'inclut pas les multilignes ; le modèle
  structurel et les propositions d'un plan fabriqué riche en N1 sont
  identiques à ceux du même plan sans N1 (couleurs, motifs et multilignes
  retirés).

## 4. Documentation

`GEOMETRIE_DXF.md` § 2 (ce que la lecture tire de chaque entité) ;
`GEOMETRIE_D_ABORD.md` § 11 (G1 : fait, et ce qu'il a mesuré) ; ce document,
§ 6 (résultats).

## 5. Validation : le balayage octet par octet

1. **Arbre de référence** : `git archive` du commit de cette conception
   (code identique à `5bfb90b`), copié hors du dépôt, empreinte notée.
2. **Corpus** (hors dépôt) : les 63 fichiers des campagnes précédentes (plans
   fabriqués, 36 DXF d'exemple d'ezdxf, DXF réel, deux feuilles PDF réelles),
   les 14 variantes de l'audit et le DXF réel, le plan synthétique des cotes,
   les 10 sondes de texte et d'unité, et des DXF **riches en N1** (multilignes
   à plat et en bloc, types de ligne complexes et renommés, hachures pleines
   et à motif, références externes, couleurs `BYBLOCK`/`BYLAYER`/vraies).
3. **Sortie canonique** par fichier : `parse_document` puis, si le statut le
   permet, `extract_engineering_data` ; tous les champs de `DocumentAnalyse`
   sauf `octets` et `primitives_dxf`, tous ceux de `ResultatExtraction`, en
   JSON trié ; une exception est une sortie (type et message). Empreinte
   SHA-256 par fichier.
4. **Après** : même chose sur l'arbre de travail gelé. Critère : **toutes les
   empreintes égales**. Un seul écart arrête la phase.
5. **Suites** : extraction, API, harnais des documents (base jetable),
   `export_contracts.py --check` — depuis l'arbre gelé.
6. **Preuve que N1 est lu** : un relevé des champs nouveaux sur le corpus
   (classes de motifs, remplissages, multilignes, définitions, couleurs),
   en § 6.

## 6. Résultats

Mesuré sur le commit du code `068fc3b`, contre l'arbre de référence `c8f1db1`
(commit de cette conception, code d'extraction identique à `5bfb90b`), copié
hors du dépôt par `git archive` et vérifié identique au commit. L'arbre de
travail est resté gelé pendant toutes les exécutions (empreinte identique
avant et après) ; les fichiers commités sont ceux qui ont été mesurés
(empreintes SHA-256 relevées avant la campagne, revérifiées au commit).

### 6.1 Balayage octet par octet — aucune sortie ne change

| Corpus (94 fichiers, hors dépôt) | Nombre |
|---|---|
| plans fabriqués des campagnes précédentes (DXF et feuilles PDF) | 24 |
| DXF d'exemple d'ezdxf (format, versions, fichiers à réparer) | 36 |
| fichiers réels (un DXF, deux feuilles PDF) | 3 |
| variantes du DXF réel de l'audit (noms neutres, langues, `$INSUNITS`, rotation, blocs explosés…) | 15 |
| sondes de texte et de déclarations d'unité | 10 |
| plan synthétique de tous les types de cote | 1 |
| DXF riches en N1 (multilignes, types de ligne complexes et renommés, hachures, xréfs, couleurs ; dont le plan fabriqué des tests) | 5 |

| Mesure | Résultat |
|---|---|
| Fichiers analysés sans exception, avant / après | 94 / 94 et 94 / 94 |
| **Sorties canoniques identiques octet pour octet** (`DocumentAnalyse` hors `octets` et `primitives_dxf`, `ResultatExtraction` entier, ordre des clés compris) | **94 / 94 — 0 différente** |
| Durée du balayage (4 processus) | 2 min 14 s avant, 2 min 10 s après |

### 6.2 Suites, contrat, harnais

| Validation | Résultat |
|---|---|
| Suite d'extraction | **417 tests, 0 échec** (374 existants + 43 nouveaux, `test_geometrie_n1.py`) |
| Suite de l'API | 599 tests, 0 échec, 340 ignorés — les mêmes 599 / 340 sur l'arbre de référence (tests conditionnés par l'environnement, indépendants de G1) |
| `export_contracts.py --check` | 0 : contrat régénéré identique, aucun fichier de contrat modifié |
| Harnais des documents (`db/test/documents_extractions.sh`, base jetable) | 0 : dépôt, analyse, propositions, décisions, calcul — inchangés |
| `VERSION_EXTRACTEUR` | inchangée (`0.4.0`) : aucune proposition ne peut changer |

### 6.3 Ce que G1 lit désormais (relevé sur le corpus)

| Champ | Sur les 94 fichiers |
|---|---|
| Types de ligne classés (F1) | 1 432 : 703 `mixte`, 313 `tirets`, 145 `points`, 271 `continu` ; 54 complexes |
| Primitives DXF par classe de motif | 155 655 `continu`, 16 659 `tirets`, 1 982 `mixte`, 75 `points` |
| Contours par remplissage (F2) | 11 924 `plein`, 20 005 `motif`, 11 809 sans (polylignes fermées, bandes, contours des feuilles PDF) |
| Multilignes (F3) | 12, dont 2 sans épaisseur (insertion non uniforme, voulue) |
| Définitions de blocs (F4) | 406 : 5 références externes (liées ou superposées), 31 anonymes, 18 à un seul `ATTDEF` |
| Insertions hors échelle 1 (F5) | 455 |
| Calques dépendant d'une xréf (F6) | 2 |
| Primitives DXF sans couleur (F7) | **0** (les 107 382 primitives sans couleur sont celles des feuilles PDF, qui n'ont pas d'information N1) |
| Incidents N1 | **1** : un `ACAD_TABLE` d'un DXF d'exemple d'ezdxf, dont ezdxf ne donne pas la couleur — entité que la géométrie ne lit pas (« entité non lue ») ; sans effet |

**Sur le plan réel** : 46 types de ligne — 24 `mixte`, 14 `tirets`, 4
`points`, 4 `continu` (la mesure de faisabilité de `GEOMETRIE_D_ABORD.md`
§ 1.1 comptait un motif sans blanc en `tirets` ; la règle du produit le dit
`continu`, il ne découpe pas le trait). Parmi les traits longs (≥ 5 % de la
diagonale), **67 des 71 axes de référence ont la classe `mixte`, et un seul
trait `mixte` n'est pas un axe** — la mesure de faisabilité est retrouvée par
le produit. Contours : 708 `plein`, 1 246 `motif`, 278 sans ; aucune
multiligne ; 8 définitions placées, dont 1 à un seul attribut ; aucun
incident.

**Coût** (plan réel, trois mesures alternées, machine au repos) : lecture
9,37 s → 9,65 s en moyenne, lecture et extraction 18,67 s → 19,19 s :
environ **+3 %**.

### 6.4 Ce qui reste hors de G1

Tout ce que dit le § 2. Les champs N1 ne sont lus par aucun détecteur :
G2 (bulles par structure, axes A et B) sera la première phase à changer des
sorties, avec sa propre conception, sa mesure avant/après et le changement
de version.
