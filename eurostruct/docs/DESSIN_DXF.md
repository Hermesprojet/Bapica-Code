# Les dessins : format, licences, et ce qui reste à vérifier à la main

## 1. Ce qui est tranché, et n'est plus à discuter

| Statut | Signification |
|---|---|
| `AUTOCAD_LICENSE_NOT_REQUIRED` | Aucune licence AutoCAD n'est nécessaire, ni pour développer, ni pour exploiter le produit. |
| `DXF_R2018_GENERATED_WITH_EZDXF_MIT` | Les dessins sont des **DXF R2018**, produits par `ezdxf` (licence MIT). |
| `USER_MAY_OPEN_DXF_WITH_OWN_AUTOCAD_OR_COMPATIBLE_CAD` | L'utilisateur ouvre ces fichiers avec son propre AutoCAD s'il en a un, ou avec un logiciel libre — LibreCAD, QCAD, BricsCAD en évaluation. |
| `NATIVE_DWG_NOT_OFFERED` | Le DWG natif n'est pas offert. Le produit ne le promet nulle part. |
| `ODA_REALDWG_DECISION_DEFERRED_UNTIL_NATIVE_DWG_IS_REQUIRED` | La décision ODA / RealDWG est **différée** jusqu'au jour où un DWG natif deviendrait une exigence réelle. |

**La licence AutoCAD n'est plus un blocage du produit.** Elle figurait comme
tel dans les rapports antérieurs à cette décision ; ces lignes sont corrigées.

Ce que le produit s'interdit en conséquence : aucune intégration ODA File
Converter, RealDWG ou AutoCAD serveur dans le SaaS commercial, et aucune
prévisualisation obtenue par conversion. **L'aperçu est produit depuis notre
propre modèle géométrique**, en SVG — voir §3.

Un point de méthode qui vaut d'être dit : les dessins ne sont **jamais**
produits par un modèle de langage (interdiction n° 1). Ils sortent d'une
bibliothèque déterministe, à partir des résultats du moteur de calcul.

## 2. Le déterminisme des octets, et pourquoi il n'est pas négociable

Le chemin de stockage d'un livrable dérive de son SHA-256
(`docs/STOCKAGE.md` §2). Un fichier dont les octets bougent d'une exécution à
l'autre se dépose donc **deux fois, sous deux chemins**, et plus aucune
relecture ne peut prouver qu'il s'agit du même dessin.

`ezdxf` estampille quatre valeurs volatiles à l'écriture. Mesure faite sur deux
rendus successifs d'une même section — tailles identiques, 63 994 octets, huit
lignes différentes :

```
-{519CC0F6-828B-4982-9AC4-6C13FD7FBCE4}      $FINGERPRINTGUID
+{FDA97C7E-8F29-489D-8FBA-885ECF5F7232}
-{7E13FDF5-4415-4F9A-83B7-EAAC59418340}      $VERSIONGUID
+{DB5681C2-676A-4857-B418-D9EF7CD0E489}
-1.4.4 @ 2026-09-01T07:14:25.870408+00:00    marqueur ezdxf
+1.4.4 @ 2026-09-01T07:14:25.895330+00:00
```

plus les dates juliennes `$TDCREATE` et `$TDUPDATE`.

`beam_section.py` fige ces métadonnées au chargement du module. La date réelle
de production et l'identité du moteur ne vivent pas dans l'en-tête DXF mais
dans la ligne de livrable (`created_at`, `engine_version`, `engine_build_sha`,
`execution_identity`), qui est la seule source opposable.

C'est la même leçon que la compression zlib du PDF, mesurée au lot précédent.

## 3. Un seul modèle géométrique, deux rendus

```
    BeamSectionSpec
          │
          ▼
    construire_modele()          drawing/modele.py — aucune bibliothèque de rendu
          │
     ModeleSection  (gelé)
        ╱      ╲
       ▼        ▼
  rendre_dxf   rendre_svg        beam_section.py / svg.py — aucune coordonnée
   (fichier)    (aperçu)
```

**Il n'y a pas deux implémentations de la géométrie, et c'est délibéré.** Un
aperçu écrit à côté du générateur DXF concorderait le jour où on l'écrit et
divergerait à la première correction de l'un des deux, sans que rien ne le
signale — l'ingénieur validerait alors ce qu'il voit à l'écran et
téléchargerait autre chose.

Trois contrôles tiennent cette règle :

* `test_le_modele_ne_connait_aucune_bibliotheque_de_rendu` — le texte de
  `modele.py` ne contient ni `import ezdxf` ni balise SVG ;
* `test_le_dxf_est_rendu_depuis_le_modele` — le document construit depuis le
  modèle et celui construit depuis la spec portent les mêmes octets ;
* `test_l_apercu_et_le_dxf_decrivent_la_section_du_calcul_conserve` — la
  section **gelée en base**, le contour mesuré dans le DXF téléchargé et ce que
  le SVG affiche sont confrontés tous les trois. C'est le calcul conservé qui
  arbitre, pas la ressemblance des deux rendus.

L'aperçu porte, **dans le dessin lui-même**, « APERCU NON CONTRACTUEL — le
fichier DXF fait foi ». Une image se copie et se transmet sans le bouton qui
l'a produite.

## 4. Ce qui reste à vérifier, et que le code ne peut pas prouver seul

Ouvrir **quelques DXF représentatifs** dans un AutoCAD réel — celui d'un futur
utilisateur — **et** dans LibreCAD, puis contrôler ce que l'œil voit. Un
fichier peut être parfaitement conforme à la spécification et s'afficher mal.

Cela ne demande d'acheter aucun logiciel.

### 4.1 Unités

`$INSUNITS = 4` — **millimètres**. À l'ouverture, une cote de 300 doit se lire
300 mm, et une mesure faite à la main dans le logiciel doit rendre la même
valeur. Si le logiciel propose une conversion à l'import, c'est un signal.

### 4.2 Calques — sept, nommés, avec couleur et épaisseur

| Calque | Couleur | Type de ligne | Épaisseur |
|---|---|---|---|
| `COFFRAGE` | 7 | CONTINUOUS | 0,35 mm |
| `FERR-PRINCIPAL` | 1 | CONTINUOUS | 0,50 mm |
| `FERR-TRANSVERSAL` | 3 | CONTINUOUS | 0,35 mm |
| `COTATION` | 5 | CONTINUOUS | 0,18 mm |
| `TEXTE` | 7 | CONTINUOUS | 0,18 mm |
| `CARTOUCHE` | 7 | CONTINUOUS | 0,25 mm |

`TEXTE` était en couleur 2 (jaune) et `COTATION` en 4 (cyan) jusqu'au 16/09 :
sur l'impression **couleur** de LibreCAD, les repères de barres et le titre
sortaient jaunes sur fond blanc, illisibles, et les valeurs de cotes cyan
pâle. Ce sont des couleurs d'écran sombre, pas de tirage : sur blanc, le
contraste du jaune est de 1,07:1 et celui du cyan de 1,25:1, là où le bleu
fait 8,6:1. La couleur 7 est celle que tout logiciel CAO inverse selon le fond
(noire sur papier, blanche sur un espace de travail sombre) ; `COFFRAGE` et
`CARTOUCHE` la portaient déjà, `TEXTE` la rejoint ; les cotes passent au bleu,
leur couleur usuelle. `test_no_text_or_dimension_is_written_on_a_pale_layer`
interdit qu'un texte ou une cote retombe sur un calque jaune, vert ou cyan.
| `AXES` | 5 | **CENTER** | 0,13 mm |

À vérifier : les sept existent, aucun objet n'est sur le calque `0`, et `AXES`
s'affiche bien en **trait d'axe** — c'est le seul type de ligne non continu, et
celui qui casse le plus souvent d'un logiciel à l'autre.

**Les épaisseurs ne se voient qu'à l'affichage activé.** Dans AutoCAD, il faut
que « Afficher/masquer l'épaisseur de ligne » soit actif ; sinon tout paraît
identique et le contrôle ne dit rien. Le test décisif est l'**impression** (ou
l'aperçu avant impression) : le ferraillage principal doit ressortir plus gras
que la cotation.

### 4.3 Textes

Style de texte **`Standard`**, délibérément — c'est celui que tous les
logiciels possèdent. Aucune police n'est embarquée, et aucune substitution ne
devrait être proposée à l'ouverture. **Si un logiciel annonce « police
introuvable », c'est un défaut à remonter.**

À vérifier aussi : les accents. Les textes sont en français ; `é`, `è`, `à` et
les guillemets doivent s'afficher, pas devenir des carrés.

### 4.4 Cotations

Style **`EUROSTRUCT`**, rattaché au style de texte `Standard`.

* hauteur de texte **2,5**, taille de flèche **2,5** ;
* **zéro décimale** (`dimdec = 0`) : les cotes sont en millimètres entiers ;
* unités décimales (`dimlunit = 2`) ;
* texte de cote **horizontal**, y compris sur les cotes verticales.

À vérifier : les cotes sont **associatives et lisibles**, ne se chevauchent
pas, et leur valeur correspond à la géométrie. Une cote qui affiche « 300 » sur
un segment qui en mesure 299 est un défaut grave — c'est exactement ce qu'un
ingénieur ne doit jamais avoir à re-mesurer.

### 4.5 Cartouche et mention obligatoire

Le cartouche porte la **mention de validation obligatoire** : aucun document
n'est un livrable signé tant qu'un ingénieur habilité ne l'a pas relu et
attesté. Elle doit être **lisible à l'impression**, pas seulement présente.

Si le calcul n'était pas en mode strict, le dessin porte en plus
**« PROJET — NON SIGNABLE »**. Cette mention ne doit jamais manquer sur un
dessin tiré d'un calcul exploratoire.

### 4.6 Comment rendre le résultat

Pour chaque fichier ouvert, et pour chacun des deux logiciels :

1. le nom du fichier et le cas qu'il représente ;
2. le logiciel et sa version exacte ;
3. **une capture d'écran** de l'ouverture, et **une de l'aperçu avant
   impression** — c'est là que les épaisseurs se jugent ;
4. la grille ci-dessus, point par point : conforme / écart, et lequel ;
5. tout message affiché à l'ouverture, **même anodin** — une substitution de
   police, un avertissement d'unités, une conversion proposée. Ce sont ces
   messages-là qui trahissent un problème de format.

Trois à cinq fichiers représentatifs suffisent, à condition qu'ils couvrent des
cas différents : une section simple, une poutre avec beaucoup d'armatures, et
un cas avec des cotes serrées.

### 4.7 Ce qu'il ne faut pas conclure de cette vérification

Qu'elle passe ne rendra pas le produit signable. Aucune validation par deux
ingénieurs nommés n'a encore été enregistrée, et tout document tiré d'un calcul
non strict reste marqué « PROJET — NON SIGNABLE ». Cette vérification porte sur
**le format des fichiers et leur lisibilité**, rien d'autre.

Le nombre de paramètres réellement confirmés ne se lit pas ici : il dépend de
l'instance, et se demande à `GET /v1/ndp/{pays}/couverture`. Un compte écrit
dans un document décrirait le dépôt, où il vaut zéro par construction — le
dépôt n'écrit jamais `confirmed`.

## 5. Ce qui a été essayé, et avec quoi

**LibreCAD a tourné ici, sans écran (§5.5) : il a ouvert et imprimé le plan
du parcours de démonstration, et il a trouvé trois défauts, corrigés depuis.
AutoCAD et BricsCAD n'ont toujours pas été ouverts**, et la grille du §4 à
l'écran — épaisseurs à l'impression, cotes serrées, trait d'axe — reste à
faire sur un poste, à l'œil.

### 5.1 Relecture par `ezdxf` — `test_dxf.py`, `test_dxf_determinisme.py`

Fichier R2018 valide, audit sans erreur, aller-retour sauvegarde/relecture,
calques normalisés, cotation liée à une police présente dans le fichier,
géométrie à l'échelle vraie, octets identiques d'une exécution à l'autre.

**Sa limite, qui est réelle.** C'est ezdxf qui écrit et ezdxf qui relit : une
convention que la bibliothèque applique en écriture, elle la comprend en
lecture. Les défauts qui font *refuser* un fichier par un logiciel tiers sont
justement ceux qu'un aller-retour dans une seule implémentation ne voit pas.

### 5.2 Relecture indépendante d'`ezdxf` — `test_dxf_lecture_independante.py`

Un analyseur de paires code/valeur écrit dans le dépôt, qui **n'importe pas
ezdxf** et ne partage aucune ligne avec lui. Huit constats, sur les octets :

| | constat | le défaut qu'il ferme |
|---|---|---|
| 1 | le flux se termine par `0/EOF` | fichier tronqué, lu en partie et sans message |
| 2 | les six sections s'ouvrent et se ferment, sans imbrication | idem, en silence |
| 3 | `$ACADVER = AC1032`, `$INSUNITS = 4`, lus dans l'en-tête | 300 unités lues en pouces |
| 4 | aucun handle en double | refus net côté AutoCAD |
| 5 | `$HANDSEED` dépasse tout handle utilisé | le premier objet créé écrase un objet existant |
| 6 | tout calque cité par une entité existe dans la table `LAYER` | tout retombe sur le calque `0`, sans couleur ni épaisseur |
| 7 | `DIMSTYLE EUROSTRUCT` → (code 340) → un `STYLE` présent | cote sans texte, ou à la police du poste |
| 8 | toute `DIMENSION` cite un `DIMSTYLE` déclaré | présentation différente d'un lecteur à l'autre |

**Chacun des huit a été mis en échec** en injectant son défaut dans les octets
d'un fichier sain : troncature, `ENDSEC` retiré, version R2013, `$INSUNITS = 1`,
calque renommé côté entité, handle `340` pointant dans le vide, style de cote
fantôme, handle d'entité recopié sur un autre. Aucun contrôle n'a survécu à son
propre défaut.

### 5.3 Identification par `libmagic`

`file` — implémentation tierce, sans rapport avec ce dépôt — reconnaît le
fichier produit comme `AutoCAD Drawing Exchange Format, version 2018`. C'est
une confirmation faible (elle lit l'en-tête, pas la géométrie), et elle est
citée pour ce qu'elle vaut.

### 5.4 Ce que tout cela ne dit toujours pas

Qu'un plan s'affiche **correctement**. L'échelle de tracé, la lisibilité des
cotes serrées, le rendu du trait d'axe sur `AXES`, et la hiérarchie des
épaisseurs à l'impression se jugent à l'œil, sur un poste, avec un vrai
logiciel. Le §5.5 en fait une partie ; la compatibilité AutoCAD et BricsCAD
**n'est pas établie** et ne doit être annoncée nulle part.

### 5.5 LibreCAD 2.2.0.2 — ouverture réelle, sans écran (16/09)

**Ce qui a été fait.** Le plan DXF du parcours de démonstration (`Démonstration
— poutre belge`, coupe 300 × 600, 4 HA20, cadres HA10 e = 150, exploratoire)
a été ouvert par LibreCAD 2.2.0.2 (paquet Ubuntu 24.04, `librecad`) en mode
console, sur un poste sans affichage, et **imprimé** par lui :

```
QT_QPA_PLATFORM=offscreen librecad dxf2pdf -a -p 297x210 plan-de-ferraillage.dxf
pdftoppm -png -r 110 -singlefile plan-de-ferraillage.pdf plan     # poppler
```

C'est le chemin d'impression de LibreCAD — celui que le §4.2 désigne comme le
test décisif — et non son écran : ce qui suit vaut pour l'impression.

**Ce qui a été constaté, point par point du §4.**

| | constat |
|---|---|
| ouverture | aucune erreur, aucun message ; `Printing … DONE` |
| 4.1 unités | la section se lit 300 × 600 sur les cotes, une fois le défaut 1 corrigé |
| 4.2 calques | les sept sont dans le fichier ; couleurs rendues (coffrage noir, barres rouges, cadres verts, cotes cyan, textes jaunes, cartouche noir). `AXES` ne porte aucune entité sur une coupe : son trait d'axe **n'a pas été jugé**. Les épaisseurs **n'ont pas été jugées** non plus (tracé à 110 dpi) |
| 4.3 textes | style `Standard`, rendu avec la police vectorielle de LibreCAD, sans substitution annoncée ; les textes sont sans accent par construction. **Défaut 2** ci-dessous |
| 4.4 cotations | **Défaut 1** ci-dessous ; corrigées, elles s'impriment « 300 » et « 600 », flèches comprises, à leur place |
| 4.5 cartouche | la mention de validation obligatoire est présente et lisible ; le filigrane de brouillon « PROJET - NON VALIDE » est en travers de la coupe. **Défaut 3** ci-dessous |

**Trois défauts, tous corrigés et mesurés à nouveau dans LibreCAD.**

1. **Les deux cotes s'imprimaient sans valeur ni flèches** — les lignes
   d'attache seules. LibreCAD redessine une cote avec les variables `$DIM*`
   de l'**en-tête**, pas avec la table `DIMSTYLE` que l'entité cite ; et
   `ezdxf.new(setup=True)` laissait dans l'en-tête ses valeurs par défaut :
   `$DIMTXT 0.25` (un texte de 0,25 mm sur une section de 600), `$DIMLFAC
   100` (une cote de 300 se serait lue « 30000 »), `$DIMSCALE 1`. L'en-tête
   porte désormais les mêmes valeurs que le style, et
   `test_header_dimension_variables_match_the_dimstyle` l'exige.
2. **Le tiret cadratin (U+2014) s'affichait « ◊ »** — dans « PROJET — NON
   VALIDE », dans « 300 x 600 mm — enrobage 40 mm » et dans « Date: — » : la
   police de LibreCAD n'a pas ce glyphe, et les polices SHX d'AutoCAD ne
   l'ont pas davantage. Le DXF ne porte plus que le tiret ASCII ; le modèle,
   la note et l'aperçu SVG gardent leur typographie.
   `test_no_typographic_dash_reaches_the_dxf` l'exige.
3. **Le cartouche du plan d'une étude exploratoire ne portait pas « PROJET —
   NON SIGNABLE »** — seulement le filigrane de brouillon et la notice : le
   plan se lisait « il ne manque qu'une signature », ce qui est faux. La coupe
   gelée avec l'étude ne porte que la géométrie ; la mention se lit sur le
   mode du calcul, et le chemin qui redessine la coupe gelée ne l'appliquait
   pas (le chemin de la flexion seule, lui, l'appliquait). Corrigé dans
   `_modele_du_dessin` ; `test_dessin_mention_gelee.py` l'exige, jusqu'aux
   octets du DXF.

**Seconde passe (16/09, après les trois corrections), sur le DXF livré par le
parcours de démonstration** (`plan-de-ferraillage.dxf`, 64 141 o, SHA-256
`2e3930cb…`), imprimé en A3 et en **monochrome** (`dxf2pdf -m -a -p 420x297`,
puis `pdftoppm -r 110`), cartouche relu à 220 dpi :

| point | constat |
|---|---|
| géométrie | section 300 × 600, cadre à 40 mm, quatre barres en lit inférieur, à leur place |
| cotes | deux cotes, valeurs « 600 » et « 300 » lisibles, flèches présentes |
| barres et textes | « COUPE POUTRE P1 », « 300 x 600 mm - enrobage 40 mm », « C1: cadre HA10 e = 150 mm », « A1: 4 HA20 (inf.) » |
| unités | « Cotes en mm » dans le cartouche, cotes en mm |
| cartouche | élément, indice, béton, acier, exposition, échelle 1:20, moteur ; **« PROJET - NON SIGNABLE » lisible** ; notice de validation sur deux lignes |
| caractères | aucun losange ; les lettres accentuées, « · », « Ø » et « × » s'affichent (mesuré en les injectant dans le cartouche) — seul le tiret cadratin manquait à la police, et il est transcrit |
| couleurs | en impression couleur, les textes du calque `TEXTES` sortent **jaunes** sur blanc (couleur de calque prévue pour un fond sombre) : imprimer en monochrome (`-m`) ou en niveaux de gris (`-k`), ce que l'écran d'impression de LibreCAD propose aussi |

Un **quatrième défaut** y a été vu et corrigé : la première ligne du
cartouche — le dossier — s'imprimait « — ». La coupe gelée avec l'étude ne
porte pas le nom du projet ; il vient désormais de la ligne du projet relue
(« Démonstration — poutre belge (DEMO-BE-001) »), replié à 50 caractères et
borné à deux lignes, parce qu'un libellé de 80 caractères sortait du cadre
par la droite. `test_dessin_mention_gelee.py` l'exige, jusqu'aux octets.

**Ce que cela n'établit pas.** L'écran de LibreCAD (seule l'impression a
tourné) ; la hiérarchie des épaisseurs et le trait d'axe (§4.2) ; les cotes
serrées d'une poutre très armée (§4.6, un seul fichier a été ouvert) ; et rien
sur AutoCAD ni BricsCAD. Les images produites ne sont pas versionnées : les
commandes ci-dessus les refont en une minute sur le DXF du parcours.
