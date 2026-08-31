# Rapport de lot — constater, revenir de la perte, et le PDF

> Ce lot reprend les **trois replis** prévus après la fermeture des blocs
> autorisation / magasin objet / entrée dans l'application. Il n'ouvre aucune
> campagne théorique, ne touche à aucune Annexe Nationale, et ne revendique ni
> `PRODUCTION_READY`, ni compatibilité Supabase, ni validation humaine réelle.
> Le registre national reste à **0 / 29**, `SUPABASE_UNVERIFIED` reste vrai, et
> tout document tiré d'un calcul non strict porte « PROJET — NON SIGNABLE ».

---

## 1. Les SHAs

| SHA | Ce qu'il ferme |
|---|---|
| `5b1831f` | Un refus 422 ordinaire laissait un objet **définitif** dans le magasin |
| `0b7a645` | Le rapprochement base / magasin — le magasin peut enfin dire ce qu'il contient |
| `19b7928` | Sauvegarde, destruction totale, restauration — et la moitié seule ne suffit pas |
| `a0334d4` | La note de calcul en PDF, écrite à la main et déterministe |

---

## 2. Le défaut trouvé en cherchant autre chose

Le premier repli devait outiller un constat. En écrivant sa preuve rouge, une
question s'est posée : **est-ce qu'un orphelin peut seulement apparaître ?** La
documentation affirmait que le seul chemin connu était une panne entre le dépôt
et le `commit`.

C'était faux, et la mesure l'a montré.

```
POST …/deliverables/{id}/revision   avec un id qui n'est pas un livrable
                                    de ce projet

1 failed, 50 passed
LE REFUS A LAISSE DES OCTETS DERRIERE LUI:
['<org>/<projet>/96f0da06…c913d.html']
```

`supersedes_id` n'était contrôlé **nulle part** avant `creer_livrable`. La route
composait, **déposait**, relisait, puis appelait la primitive — qui refusait à
juste titre. Résultat : `422`, aucune ligne, et un objet abandonné.

**Ce n'est pas un détail de propreté.** La politique du magasin interdit toute
suppression par le produit — `ClientS3` n'a aucune méthode de suppression, et
c'est une bonne règle. Sa contrepartie est que tout objet abandonné l'est
**définitivement**. Se tromper d'identifiant de livrable — une page rouverte,
une URL recopiée — est l'erreur la plus banale qui soit, et elle coûtait une
fuite permanente.

Le contrôle a été remonté **avant le dépôt**, en relisant le livrable remplacé
par `project_deliverable_read` : une fonction déjà déclarée au backend, même
borne de projet, même exigence de capacité. **Aucune primitive ajoutée** — une
fonction d'existence aurait élargi la surface SQL du backend pour un contrôle
que celle-ci fait déjà.

L'autre refus tardif connu — un calcul étranger au projet — a été mesuré aussi :
il refuse **déjà** avant le dépôt. Le cas ajouté ne corrige rien ; il verrouille
cet ordre.

**La leçon vaut plus que le correctif.** Une politique « on ne supprime jamais »
n'est tenable que si l'on sait aussi **ne pas produire** ce qu'on ne pourra pas
reprendre.

---

## 3. Repli 1 — le rapprochement, strictement en lecture seule

`docs/STOCKAGE.md` §5 écrivait noir sur blanc ce qui manquait : « un
rapprochement en lecture seule … **il n'existe pas encore** ». Il existe.

    EUROSTRUCT_RECONCILIATION_DSN=… python3 -m eurostruct_api.reconciliation \
        [--empreintes] [--json]

**Quatre verdicts, parce qu'ils ne se valent pas.**

| Verdict | Ce que ça veut dire | Qui ça réveille |
|---|---|---|
| `absent` | une ligne promet un document que le magasin n'a pas | **une promesse rompue** : le téléchargement rendra 503 |
| `divergent` | l'objet est là, taille ou empreinte différentes | une corruption, vue avant qu'un client la découvre |
| `orphelin` | un objet que plus aucune ligne ne nomme | du gaspillage tracé — personne n'attend ce document |
| `intact` | ils s'accordent | — |

Un rapprochement qui rendrait un seul nombre mélangerait une promesse rompue et
quelques kilo-octets perdus.

### Il ne peut pas écrire, et ce n'est pas une promesse

Trois cas le tiennent, et aucun ne repose sur la discipline de l'auteur :

* un magasin qui **n'a pas** de méthode `deposer` — une tentative lèverait ;
* une **photo du disque** (chemins, tailles, empreintes) avant et après ;
* **PostgreSQL lui-même** refuse un `update` dans la transaction du
  rapprochement, contre un vrai serveur.

### Deux pièges qui feraient mentir le rapport

Les lignes portant un **autre** `storage_backend` sont écartées, jamais
déclarées absentes : un déploiement qui a migré du disque vers S3 les verrait
toutes rouges. Et plusieurs lignes peuvent partager une clé — les clés dérivent
du contenu — donc un objet n'est orphelin que si **aucune** ligne ne le nomme.

### L'énumération, qui n'existait pas

`ClientS3.enumerer` — `ListObjectsV2`, signée et paginée. Le produit n'en avait
jamais eu besoin : il connaît le chemin d'un livrable avant de le lire. Le
**préfixe déclaré est retiré** des chemins rendus ; sans cela, le rapprochement
déclarerait tout le compartiment orphelin dès qu'un préfixe est configuré —
c'est-à-dire dans la composition de production.

### Ce que le premier rapprochement a trouvé

Un orphelin **réel**, du premier coup, dans le décor du harnais MinIO : l'objet
que le cas du refus d'écrasement dépose sans ligne. Mon assertion initiale
exigeait un magasin parfait ; c'est elle qui était fausse, et la corriger valait
mieux que nettoyer le décor pour la faire passer.

### Ce n'est pas une route de l'API, délibérément

Le rapprochement traverse **toutes** les organisations : geste d'exploitation,
comme une sauvegarde. L'exposer exigerait d'élargir la surface SQL du backend
authentifié à une lecture transverse de `deliverables` — exactement ce que la
frontière des rôles interdit.

---

## 4. Repli 2 — revenir de la perte des deux moitiés

`stockage_s3.sh` établit que les octets survivent à un **redémarrage**. Un
redémarrage ne perd rien. Une panne de disque, une suppression accidentelle, une
région qui brûle — voilà ce contre quoi une sauvegarde existe.

**Un livrable vit dans deux systèmes, et c'est tout le piège.** La ligne est dans
PostgreSQL ; les octets sont dans le magasin. Sauvegarder l'un sans l'autre ne
donne pas une demi-sauvegarde : cela donne une base qui promet des documents
introuvables, ou un compartiment que plus rien ne sait nommer.

`db/test/sauvegarde_restauration.sh`, huit étapes :

| Étape | Ce qu'elle fait |
|---|---|
| 1–3 | volume neuf, compartiment, un livrable déposé par les routes réelles |
| 4 | **sauvegarde des deux moitiés** — `pg_dump -Fc`, et les objets tirés du compartiment **par le client du produit** |
| 5 | **destruction totale** — base supprimée, conteneur et volume détruits, et on le constate |
| 6 | **restauration des deux moitiés** |
| 7 | **les mêmes octets par la route réelle** — mêmes cas que la relecture après redémarrage ; ce qui change n'est pas ce qu'on vérifie, c'est ce qu'on a détruit avant |
| 8 | **la moitié seule ne suffit pas** |

**L'étape 8 est celle qui donne sa valeur au harnais.** Un exploitant qui ne
sauvegarde que PostgreSQL verrait un dump qui se restaure parfaitement, une base
saine, des lignes complètes — et découvrirait au premier téléchargement que les
documents n'existent plus. Mesure du produit à cette étape :

```
503 stockage_indisponible / ObjetIntrouvable
    « aucun octet a l'emplacement <org>/<projet>/e2c3cea1…897b.html »
rapprochement --json : absent ≥ 1, orphelin = 0
```

La sauvegarde des objets passe par `enumerer` et `lire`, pas par `mc mirror` :
ce qui nous intéresse est de savoir si **ce que le produit expose suffit** à
écrire une procédure de sauvegarde.

### Mon premier garde-fou était faux, et le resserrer l'a montré

L'étape 8 acceptait **n'importe quel** échec de `pytest`. Un nodeid mal écrit,
un import cassé ou un décor absent auraient tous été lus comme « le produit
refuse » — sans que rien ne soit exercé. Elle branche maintenant sur le **code
de sortie documenté** de `pytest` (1 = des cas ont tourné et échoué ; 5 = aucun
cas collecté) et exige que le motif soit un objet manquant.

---

## 5. Repli 3 — le PDF

**Pourquoi pas une bibliothèque**, dans cet ordre :

1. **Le déterminisme.** La clé d'un livrable dérive de son contenu. La plupart
   des générateurs inscrivent une date de création, un identifiant aléatoire,
   un producteur versionné — trois façons de faire changer l'empreinte sans
   qu'aucun chiffre n'ait bougé. Le magasin porterait deux objets et la base
   deux lignes pour un seul et même calcul.
2. **La surface.** Une note de calcul est du texte mis en page. Les quatorze
   polices standard suffisent, et n'ont pas à être embarquées.
3. **L'auditabilité.** Un document opposable dix ans ne devrait pas dépendre
   d'un arbre de dépendances que personne ne relit.

**Aucun caractère ne disparaît en silence.** WinAnsi ne porte pas le grec, et
une note en porte : `μ`, `ξ`, `ε` sont des **grandeurs**. Ils sont écrits avec
la police `Symbol`, dans un segment distinct. Un caractère sans glyphe dans
aucune des deux fait **lever**.

**Le lecteur est indépendant.** `pypdf` relit ce que l'écrivain produit. Il
n'est **pas** une dépendance du produit — `pdf.py` n'importe rien — mais une
dépendance de **test** : vérifier un PDF avec le code qui l'a écrit ne
prouverait que sa cohérence avec lui-même.

**Ce qui est éprouvé** : 16 cas unitaires et 6 cas bout-en-bout par les routes
réelles. Le fichier s'ouvre, il pagine sans perdre sa dernière section, chaque
page porte « page N sur T » et le titre, deux compositions rendent des octets
identiques, ni `/CreationDate` ni `/ModDate` ni `/Producer` n'y figurent, la
mention obligatoire et le filigrane sont lisibles, les lettres grecques
survivent au transport, les paramètres non confirmés sont nommés, et un
idéogramme fait lever au lieu de disparaître.

**Deux boutons là où il y en avait un**, et le parcours navigateur produit
désormais les deux formes en constatant que leurs empreintes diffèrent — parce
qu'une suite d'API verte n'a jamais prouvé qu'un bouton est atteignable.

### La duplication assumée, et sa garde

HTML et PDF sont composés par deux fonctions distinctes depuis les mêmes données
relues : convertir le HTML exigerait un moteur de rendu.
`test_les_deux_rendus_portent_les_memes_faits` nomme ce que **les deux** doivent
affirmer — organisation, projet, référence, identifiant de calcul, build,
empreinte des entrées, identité d'exécution, filigrane, paramètres non
confirmés, taux de travail.

---

## 6. Ce que ce lot n'établit pas

* **Aucun plan de reprise.** Le harnais montre que la matière d'une restauration
  est accessible et suffit. Ni sauvegarde continue, ni journal de transactions,
  ni point de reprise dans le temps, ni site distant, ni chiffrement des
  sauvegardes, ni mesure de durée sur un volume réel.
* **Aucun fournisseur nommé.** Ni AWS S3, ni Supabase Storage n'a été joint.
* **Aucune reprise d'orphelin.** L'outil les **nomme**. Les supprimer se fait
  hors du produit, par une personne, sur des clés nommées une à une.
* **Aucun rôle PostgreSQL dédié** n'est créé pour le rapprochement. La variable
  de DSN est distincte et documentée ; le rôle reste à décider.
* **Aucune identité visuelle** sur le PDF : pas de logo, pas de page de garde.

---

## 7. Les commandes, et leurs codes de sortie

| Commande | Sortie | Mesure |
|---|---|---|
| `./run_tests.sh --require-db` | **0** | `COMPLET`, 6 surfaces, API 348 collectés / 348 exécutés |
| `db/test/livrable_validation.sh` | **0** | 58 cas (52 avant ce lot) |
| `db/test/stockage_s3.sh` | **0** | **10** étapes (8 avant), MinIO réel |
| `db/test/sauvegarde_restauration.sh` | **0** | 8 étapes, destruction totale et retour |
| `db/test/parcours_entree.sh` | **0** | 14 points, Chromium |
| `db/test/parcours_livrable.sh` | **0** | HTML **et** PDF par les boutons |
| `api && pytest tests/test_reconciliation.py` | **0** | 11 cas |
| `api && pytest tests/test_note_pdf.py` | **0** | 16 cas, lecteur `pypdf` témoin |
| `web && npm run typecheck` / `build` | **0** / **0** | Next.js 16.3.3 |
| `engine/scripts/export_contracts.py` | **0** | 64 types |
