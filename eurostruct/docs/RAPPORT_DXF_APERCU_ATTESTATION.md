# Le plan de ferraillage devient une pièce ; l'aperçu montre ce qu'on télécharge

> **Compte rendu historique.** Ce document décrit l'état du dépôt **au SHA
> de son époque** et n'est pas mis à jour. Pour l'état courant du produit,
> voir le `README.md` à la racine de `eurostruct/`.

Rapport de lot — 1er septembre 2026, branche
`claude/wip-6.3c-racine-de-confiance`, dépôt `Hermesprojet/Bapica-Code`.
Point de départ validé par l'utilisateur : `b206753`, puis `3c23d47`.

---

## 1. HEAD distant

```
24f2a5a  Un rapport citait des empreintes sans pouvoir montrer les fichiers
```

## 2. Les sept commits poussés

| SHA | Objet |
|---|---|
| `24562fb` | Le plan de ferraillage s'évaporait au rechargement de la page |
| `808810a` | L'ingénieur choisissait son ferraillage sans jamais le voir |
| `ccf2c58` | La licence AutoCAD figurait comme blocage produit ; elle ne l'est pas |
| `1a4ca58` | La politique de sauvegarde n'était écrite nulle part |
| `d992c28` | Attester la note laissait croire que le plan l'était aussi |
| `7b43a52` | Un objet orphelin ressemble à un déchet ; il peut être une pièce |
| `24f2a5a` | Un rapport citait des empreintes sans pouvoir montrer les fichiers |

---

## 3. Ce qui est réellement terminé

### 3.1 Le DXF est un livrable de projet — les dix points, tenus

1. **Créé depuis un calcul persisté et un ferraillage vérifié.** La
   vérification tourne avant le dessin et lève avant qu'un octet existe.
2. **Dimensions, matériaux, efforts, contexte normatif et identités viennent du
   serveur** — relus dans `calculations.request`, la requête exacte que le
   moteur a reçue et que la base a gelée.
3. **Le navigateur n'envoie que le choix des barres** — nombre, diamètre,
   enrobage, cadres : une décision d'ingénieur, pas une valeur dérivable.
   `As_required` dit combien d'acier il faut, jamais comment le disposer. Tout
   champ supplémentaire reçoit 422.
4. **Les octets exacts sont stockés**, à un chemin qui dérive de leur SHA-256.
5. **La ligne porte** projet, calcul, genre, format et type de média, SHA-256,
   taille, version et build du moteur, identité d'exécution, empreinte des
   entrées, `ndp_as_of`, date de production, état.
6. **Téléchargeable après F5 et après redémarrage de l'API.** `client_neuf`
   rebâtit l'application entière — fabrique de connexion, magasin, caches — et
   les octets reviennent avec la même empreinte.
7. **Présent dans la liste des livrables et dans le dossier de revue.**
8. **Le manifeste ne déclare plus `calculation_note_pdf` absent** — corrigé au
   lot précédent (`3c23d47`), la liste étant désormais dérivée des formes
   réellement produites.
9. **Un ferraillage insuffisant ne produit ni ligne ni octet.**
10. **En exploratoire, le dessin existe et porte « PROJET — NON SIGNABLE »**
    dans le fichier lui-même, pas seulement dans la ligne.

**Aucune migration n'a été nécessaire.** `deliverables` portait déjà toutes les
colonnes exigées et `rebar_drawing_dxf` figurait déjà dans l'énumération
`deliverable_kind`. La surface SQL du backend authentifié reste à
**27 fonctions**.

### 3.2 Un seul modèle géométrique, deux rendus

```
    BeamSectionSpec ──► construire_modele() ──► ModeleSection (gelé)
                        drawing/modele.py           ╱        ╲
                        aucune bibliothèque        ▼          ▼
                        de dessin             rendre_dxf   rendre_svg
                                               (fichier)    (aperçu)
```

Ce n'est pas une élégance d'architecture. Un aperçu écrit à côté du générateur
DXF est un **second calcul de la même géométrie** : les deux concordent le jour
où on les écrit et divergent à la première correction de l'un des deux, sans
que rien ne le signale. L'ingénieur validerait alors ce qu'il voit à l'écran et
téléchargerait autre chose.

L'aperçu ne dépose rien, n'enregistre rien, ne conserve aucune empreinte — et
c'est vérifié. Un objet déposé pour un simple coup d'œil serait **définitif**,
la politique du magasin interdisant au produit toute suppression. L'image porte
« APERÇU NON CONTRACTUEL — le fichier DXF fait foi » **dans le dessin**, parce
qu'une image se copie et se transmet sans le bouton qui l'a produite.

Un ferraillage qui ne vérifie pas n'a pas plus d'aperçu que de fichier : un
dessin faux ressemble trait pour trait à un dessin juste, à l'écran comme sur
le papier.

Côté écran, « Plan de ferraillage… » ouvre un formulaire (barres, diamètre,
enrobage, cadres, espacement) avec deux actions : **« Prévisualiser »**, qui ne
crée rien, et **« Télécharger le plan DXF »**, qui écrit un livrable.

### 3.3 Le dossier de revue dit ce que l'attestation couvre — et ce qu'elle ne couvre pas

Manifeste en **version 2**, deux sections nouvelles :

* `review_snapshot` — l'inventaire de ce qui existait **pour ce calcul** au
  moment où le dossier a été pris : genre, nom, type de média, empreinte,
  taille, état, indice, et lequel est celui qu'on relit. Il ne ratisse pas plus
  large que le calcul : mélanger les livrables des autres calculs du projet
  serait aussi faux qu'un oubli.
* `attestation.covers` / `attestation.does_not_cover` — la portée, des deux
  côtés. Valider le PDF ne valide pas le DXF, et le dossier l'écrit au lieu de
  le laisser supposer.

L'instantané **se date lui-même**, seul champ non déterministe du dossier. Un
inventaire sans date ne dirait pas *de quand* il parle : un plan produit après
coup n'y figurerait pas et rien ne permettrait de s'en apercevoir. Le test de
déterminisme exclut ce champ et exige que tout le reste coïncide.

### 3.4 Statuts AutoCAD / ODA, et stratégie DXF

`docs/DESSIN_DXF.md` porte les cinq statuts arbitrés
(`AUTOCAD_LICENSE_NOT_REQUIRED`, `DXF_R2018_GENERATED_WITH_EZDXF_MIT`,
`USER_MAY_OPEN_DXF_WITH_OWN_AUTOCAD_OR_COMPATIBLE_CAD`,
`NATIVE_DWG_NOT_OFFERED`,
`ODA_REALDWG_DECISION_DEFERRED_UNTIL_NATIVE_DWG_IS_REQUIRED`), la mesure du
déterminisme des octets, le schéma du modèle partagé, et la **grille de
contrôle manuelle** avec les valeurs attendues tirées du code. Les trois
documents qui présentaient encore la licence ODA/RealDWG comme un blocage sont
corrigés.

### 3.5 Sauvegarde, et proposition d'orphelins

`docs/SAUVEGARDE_ET_REPRISE.md` — RPO 15 min, RTO 4 h, PITR par archivage WAL,
sauvegarde nocturne chiffrée, versionnement et réplication hors site du magasin
objet, 30 quotidiennes / 12 mensuelles / archives annuelles à dix ans, exercice
de restauration mensuel avec confrontation d'empreintes, clés détenues par
l'infrastructure. **Le document dit en tête qu'il décrit une politique voulue,
pas un service fourni**, et liste ce qu'il reste à faire pour le rendre vrai.

`api/src/eurostruct_api/orphelins.py` — deux scans séparés de 24 h, âge de
grâce de 30 jours, mêmes octets aux deux scans, manifeste versionné à empreinte
stable qui nomme aussi ce qu'il écarte et pourquoi. Le module **ne sait pas
supprimer**, et un test lit son propre texte source pour que cela le reste.

---

## 4. Les tests ajoutés, et ce qui les rend décisifs

| Module | Cas | Le cas décisif |
|---|---|---|
| `api/tests/test_livrable_dxf.py` | 11 | `test_la_section_dessinee_est_exactement_la_section_calculee` relit le DXF **servi** avec `ezdxf`, mesure l'étendue du calque `COFFRAGE` et la confronte à `calculations.request.section` à 0,1 mm près. Il tombe si le dessin diverge du calcul — ce qu'aucune vérification de format ne verrait. |
| `engine/tests/test_modele_partage.py` | 9 | `test_le_modele_ne_connait_aucune_bibliotheque_de_rendu` lit le texte du module et refuse `import ezdxf` comme une balise SVG ; `test_le_dxf_est_rendu_depuis_le_modele` compare octet pour octet les deux chemins de construction. |
| `api/tests/test_apercu_svg.py` | 9 | `test_l_apercu_et_le_dxf_decrivent_la_section_du_calcul_conserve` confronte **trois** sources et pas deux : la section gelée en base, le contour mesuré dans le DXF téléchargé, et ce que le SVG affiche. Comparer seulement les deux rendus laisserait passer deux dessins faux de la même façon ; c'est le calcul conservé qui arbitre. |
| `api/tests/test_dossier_instantane.py` | 5 | `test_l_attestation_nomme_ce_qu_elle_couvre_et_ce_qu_elle_ne_couvre_pas` exige que le plan DXF apparaisse dans `does_not_cover`. |
| `api/tests/test_orphelins.py` | 14 | `test_le_module_ne_contient_aucun_appel_de_suppression` — grossier exprès : il ne peut pas être contourné par inadvertance. |

**48 cas ajoutés.** Chacun a été mesuré rouge avant d'être vert. Pour les deux
modules dont le code n'existait pas encore, le rouge a pris la forme d'un échec
à l'import — la même chose, dite plus brutalement.

Aucun `pytest.skip` conditionnel ne transforme un échec en succès : les
modules qui dépendent du décor portent un `skipif` de **collecte préservée**
(et non `importorskip`), et `run_tests.sh` compare collectés et exécutés
précisément pour repérer des cas qui disparaîtraient.

---

## 5. Les cinq défauts produits trouvés en construisant ce lot

1. **Deux dessins du même calcul ne donnaient pas les mêmes octets.** Mesure sur
   deux rendus successifs : tailles identiques (63 994), huit lignes
   différentes — `$FINGERPRINTGUID`, `$VERSIONGUID`, le marqueur `ezdxf`
   horodaté, les dates juliennes. L'adressage par contenu l'exige : un fichier
   instable se dépose deux fois, sous deux chemins, et plus aucune relecture ne
   peut prouver qu'il s'agit du même dessin. Même leçon que la compression zlib
   du PDF.
2. **Le nom servi finissait en `.html` pour un DXF** — l'extension était écrite
   une seconde fois dans `_nom_de_fichier` au lieu d'être lue dans la table des
   formes.
3. **Recomposer le dessin rejouait la vérification sans fournisseur de
   confirmations** — un calcul strict pourtant abouti rendait
   `national_annex_incomplete`.
4. **`_exiger_capacite` avait une branche « sinon ».** Elle lisait « REDACTEURS
   si `redaction`, sinon VALIDATEURS » : n'importe quel nom mal orthographié
   tombait silencieusement du côté des validateurs, en vérifiant autre chose
   que ce que son appelant croyait. Un contrôle d'autorisation ne doit pas
   avoir de branche qui accorde quoi que ce soit par défaut.
5. **Le dossier de revue taisait les autres artefacts du calcul.** Le silence
   sur un artefact se lit comme son approbation.

---

## 6. Commandes exécutées, et résultats

| Commande | Résultat |
|---|---|
| `./db/test/livrable_validation.sh <préfixe>` | **10 failed, 61 passed** (preuve rouge D2) → **71 passed** → **80 passed** (D3) → **5 failed, 80 passed** (preuve rouge D4) → **85 passed** |
| `engine$ pytest` | **1023 passed** |
| `api$ pytest tests/test_orphelins.py` | **14 passed** |
| `./run_tests.sh --require-db` | **VERDICT : COMPLET — les 6 surfaces ont tourné, toutes vertes** |
| `engine/scripts/export_contracts.py` | 64 types, contrat TypeScript inchangé et vérifié vert par la surface « cohérence » |
| `web$ npx tsc --noEmit` | aucune erreur |
| `ruff check` (fichiers touchés) | aucune régression ; les fichiers nouveaux passent sans exception |

Campagne canonique finale, sur l'arbre de `24f2a5a` :

```
 SURFACE              ETAT    DETAIL
 moteur               VERT    collectes 1023 | executes 1023 | reussis 1023 | ignores 0 | echoues 0
 importeur            VERT    collectes   88 | executes   88 | reussis   88 | ignores 0 | echoues 0
 API                  VERT    collectes  396 | executes  396 | reussis  181 | ignores 215 | echoues 0
 securite des harnais VERT    30 barriere(s) mise(s) en echec, toutes ont refuse
 garanties SQL        VERT    13 groupe(s) de garanties verifie(s)
 coherence            VERT    seed NDP: ok, contrat TypeScript: ok, dependances: ok, moteur sans avertissement: ok
 VERDICT: COMPLET
```

Les 215 cas « ignorés » de la surface API sont les modules qui exigent le décor
complet ; ils sont **collectés** et lancés par
`db/test/livrable_validation.sh`, qui rend 85 passed.

**Une campagne intermédiaire a été rouge, et de mon fait.** La surface
« isolation de la matrice de mutation » a échoué parce que j'éditais l'arbre de
travail pendant que `mutation_isolation_selftest.sh` vérifiait précisément que
le dépôt principal n'avait pas bougé. Relancée seule, elle passe ; la campagne
finale, menée sans aucune édition concurrente, est verte. C'est exactement la
raison d'être de la consigne « aucune édition pendant les exécutions », et je
ne l'ai pas respectée à ce moment-là.

**CI GitHub Actions** — `eurostruct — tests` : succès sur `24562fb`, `1a4ca58`,
`d992c28` et `7b43a52`. `808810a` et `ccf2c58` n'ont pas de run propre : ils
ont été poussés dans la même poussée que `1a4ca58`, et GitHub n'exécute le
workflow que sur la tête. `24f2a5a` est poussé après la campagne locale.

---

## 7. Preuve de persistance après redémarrage

Trois niveaux, du plus faible au plus fort :

1. **F5** — un second appel dans le même processus. Ne prouve rien de plus
   qu'un cache chaud.
2. **`client_neuf`** — l'application entière est reconstruite : nouvelle
   fabrique de connexion, nouveau magasin, aucun cache. C'est ce qui distingue
   « les octets sont conservés » de « ils sont encore en mémoire ».
   `test_le_dxf_revient_apres_un_rechargement_complet` confronte l'empreinte
   des octets rendus à celle enregistrée en base.
3. **`db/test/sauvegarde_restauration.sh`** — sauvegarde, destruction totale de
   la base et du magasin, restauration, puis confrontation des empreintes. Son
   étape 8 exige un code de sortie **exactement 1** avec un motif
   503/`ObjetIntrouvable` sur le magasin détruit : un échec quelconque n'y
   passe pas pour une preuve.

---

## 8. Échantillons, avec leurs empreintes

Ces fichiers sont les octets que les routes ont **réellement déposés, relus et
enregistrés** lors d'une exécution de `db/test/livrable_validation.sh` — pas
des documents recomposés pour l'illustration. Dans le magasin, **le nom d'un
objet est son empreinte** : vérifier `SHA256SUMS` confirme du même geste que
l'adressage par contenu tient.

| Forme | SHA-256 | Taille |
|---|---|---|
| DXF (plan de ferraillage) | `17c1676a26eda1f7dede68907b3793e9a8548c0b5635a8041d1e6a8cbdf57ddf` | 64 025 o |
| DXF (autre projet, autre cartouche) | `a94146066fcad6f482a0c49bb5663ac711695e65d82f2c9b31a512c8406a3715` | 64 213 o |
| PDF (note de calcul) | `c4cc1f566498fbce6d261fd0c6ad94a85f4f736c4812562596bdbf96237bc844` | 35 328 o |
| PDF (autre calcul) | `c4f8d260d6a26649374a19e38dedbe0ea96e9e06bc485bad2f6161a068f7ef85` | 34 286 o |
| HTML (note de calcul) | `378bd07febd195354e9dbd223435066cdbab0f4b710f66f21c883ad5d0bfdf1f` | 17 539 o |
| SVG (aperçu, hors magasin) | `a2711a55e904da5ff9048fd090de99de72ad313d99d7aa23f83d6bedb0d419e7` | 3 728 o |

`sha256sum -c SHA256SUMS` : **toutes les lignes OK**.

Pour reproduire :

```
EUROSTRUCT_ECHANTILLONS=/chemin/vers/echantillons \
  ./db/test/livrable_validation.sh <prefixe-jetable>
```

**Le SVG n'est pas dans le magasin, et c'est voulu** : l'aperçu ne dépose rien.
Son empreinte ci-dessus vient d'un rendu direct du modèle géométrique, stable
d'une exécution à l'autre.

**Le dossier de revue n'est pas listé ici avec une empreinte.** Il n'est pas
stocké : c'est une archive composée à la demande à partir des octets du magasin
et du manifeste. Son déterminisme et son contenu sont établis par les tests —
`test_le_dossier_reste_deterministe_avec_l_instantane` et
`test_le_dossier_de_revue_d_un_dxf_porte_le_dessin` — mais je n'ai pas extrait
de fichier `.zip` hors du harnais, et je ne cite donc pas d'empreinte que je ne
peux pas montrer.

---

## 9. Ce qui reste

### 9.1 Défauts logiciels et travaux non faits — de mon fait

**Le document émis séparé (`issued_calculation_note_pdf`) n'est pas fait.**
C'est la moitié de D4 qui manque, et voici précisément pourquoi je me suis
arrêté plutôt que de le livrer à moitié :

> L'émission est réservée au `validating_engineer`. Or ce rôle **ne porte pas**
> la capacité `redaction` (`project_exiger_capacite`, migration 0024), donc il
> ne peut pas appeler `project_deliverable_create`. Créer l'artefact
> automatiquement à l'émission exigerait donc une **28ᵉ fonction** au backend
> authentifié, ce que la consigne de ne pas élargir cette surface interdit.

Deux chemins possibles, à trancher :

* **A** — une route appelée par un **rédacteur après l'émission**, qui refuse
  tant que le livrable source n'est pas `final` et compose l'attestation
  entièrement depuis les données gelées. Pas de nouvelle primitive SQL ; une
  migration pour la valeur d'énumération. Le prix : ce n'est plus automatique
  à l'émission.
* **B** — assumer une 28ᵉ fonction `project_deliverable_issue_attestation`,
  qui insère la ligne directement à l'état `final`. Automatique, mais elle
  élargit la surface que tout le lot 6.3c a servi à figer.

**Je n'ai pas tranché seul** : c'est un arbitrage entre deux contraintes que
vous avez posées toutes les deux.

Autres points ouverts, tous documentés comme non faits là où ils comptent :

* **Rôle PostgreSQL `NOLOGIN` en lecture seule** pour le rapprochement :
  contrat écrit (`docs/STOCKAGE.md` §5 ter), **non implémenté**. La garantie du
  jour est `set transaction read only`, demandée par le programme — réelle,
  mais non structurelle. Les tests négatifs prouvant qu'`insert`/`update`/
  `delete` sont refusés par le serveur restent à écrire.
* **Outil de maintenance de suppression** : contrat écrit (programme séparé,
  double contrôle opérateur, vérification d'empreinte), **il n'existe pas**.
  Aucune ligne du dépôt ne supprime d'objet.
* **Identité visuelle sobre** et zone de logo optionnelle : non traitée. Le
  cartouche porte déjà titre, référence projet, indice, date, échelle, unités,
  identité du moteur et mention obligatoire ; il n'a ni pagination ni
  classification, et aucune zone de logo n'est prévue.
* **Recette manuelle AutoCAD / LibreCAD** : la grille est écrite
  (`docs/DESSIN_DXF.md` §4), **aucun test AutoCAD réel n'a été exécuté**. Elle
  ne demande d'acheter aucun logiciel.

### 9.2 Dépendances externes — inchangées

* **La revue par un ingénieur compétent.** Hors de ce dépôt. Aucune attestation
  produite par les harnais n'est une validation réelle : les comptes sont
  explicitement fictifs et vivent dans des bases jetables.
* **Les documents normatifs officiels.** Registre des Annexes Nationales à
  **0 sur 29**. Aucune valeur n'est inventée ; tout calcul non strict reste
  marqué « PROJET — NON SIGNABLE ».
* **L'infrastructure de staging réelle.** `SUPABASE_UNVERIFIED` reste vrai, et
  la politique de sauvegarde reste une intention.

**La licence AutoCAD n'est plus un blocage du produit.**
