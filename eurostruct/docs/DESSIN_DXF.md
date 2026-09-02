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
| `COTATION` | 4 | CONTINUOUS | 0,18 mm |
| `TEXTE` | 2 | CONTINUOUS | 0,18 mm |
| `CARTOUCHE` | 7 | CONTINUOUS | 0,25 mm |
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

Qu'elle passe ne rendra pas le produit signable. Le registre des Annexes
Nationales officielles est à **0 sur 29**, aucune validation par un ingénieur
réel n'a eu lieu, et tout document tiré d'un calcul non strict reste marqué
« PROJET — NON SIGNABLE ». Cette vérification porte sur **le format des
fichiers et leur lisibilité**, rien d'autre.

**Aucun test AutoCAD réel n'a été exécuté à ce jour.** Ce que le dépôt prouve,
c'est une relecture indépendante par `ezdxf` — fichier R2018 valide, audit sans
erreur, aller-retour sauvegarde/relecture, calques normalisés, cotation liée à
une police présente dans le fichier, géométrie à l'échelle vraie. Le produit ne
prétend rien de plus.
