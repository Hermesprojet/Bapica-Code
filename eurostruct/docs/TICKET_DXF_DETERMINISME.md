# Le DXF n'est pas stable d'un processus à l'autre

**Mesuré le 01/09/2026. Non corrigé — la cause est dans `ezdxf` 1.4.4, et le
correctif touche une bibliothèque tierce : il mérite son propre lot et sa
propre preuve rouge.**

---

## Le fait

Deux rendus du **même** `BeamSectionSpec`, dans deux processus Python
distincts, produisent deux fichiers DXF de **taille identique** et de contenu
différent.

```
$ for i in 1..8; do python3 rendre.py; done | sort | uniq -c
   4 c1ffa143113ec2d429a74a2b7a59b89686038149787e0f3576a67029561192aa  63993
   4 7d2d548843c05e9dab37968294ef9875fc710829963480dd3964582256c9d355  63993
```

Deux valeurs, tirées au hasard à chaque lancement. À l'intérieur d'un même
processus, en revanche, deux rendus successifs sont **byte-identiques** — c'est
ce que `parcours_verification.mjs` constate en reproduisant le plan après un
rechargement complet du navigateur, l'API étant restée le même processus.

## Ce que cela coûte

**LE CHEMIN DE STOCKAGE D'UN LIVRABLE DÉRIVE DE SON SHA-256.** Un fichier dont
les octets bougent d'une exécution à l'autre :

1. **se dépose deux fois, sous deux chemins.** La politique du magasin
   (`docs/STOCKAGE.md` §5) interdit toute suppression par le produit : chaque
   variante est **définitive** ;
2. **casse la comparaison d'empreintes.** Un auditeur qui compare le SHA-256 de
   deux plans identiques conclut qu'ils diffèrent. C'est le contraire de ce que
   l'adressage par contenu existe pour donner ;
3. **contredit un commentaire du dépôt.** `drawing/beam_section.py` explique,
   au-dessus de `ezdxf.options.write_fixed_meta_data_for_testing = True`, que
   ce réglage sert précisément à obtenir des octets stables. Le réglage est
   nécessaire — sans lui, quatre valeurs volatiles s'ajoutent — mais il
   **n'est pas suffisant**, et le commentaire laissait croire qu'il l'était.

## La cause, exactement

Le diff entre les deux variantes fait **huit lignes**, toutes dans la section
`CLASSES` : les enregistrements `LAYOUT` et `ACDBPLACEHOLDER` échangent leur
place.

```
1330c1330            1346c1346
< LAYOUT              < ACDBPLACEHOLDER
> ACDBPLACEHOLDER     > LAYOUT
1332c1332            1348c1348
< AcDbLayout          < AcDbPlaceHolder
> AcDbPlaceHolder     > AcDbLayout
```

Le document est en **R2018**. Dans `ezdxf/sections/classes.py`,
`REQUIRED_CLASSES` ne contient que deux entrées — `DXF2000 -> REQ_R2000` et
`DXF2004 -> REQ_R2004` — si bien que toute version postérieure retombe sur
`REQ_R2004`, **qui ne cite ni `LAYOUT` ni `ACDBPLACEHOLDER`** (alors que
`REQ_R2000` cite les deux, dans cet ordre).

Ces deux classes ne sont donc enregistrées que par la boucle finale de
`add_required_classes` :

```python
dxf_types_in_use = self.doc.entitydb.dxf_types_in_use()   # entitydb.py:297
...
for dxftype in dxf_types_in_use:
    self.add_class(dxftype)
```

et `dxf_types_in_use` rend un **`set[str]`** :

```python
def dxf_types_in_use(self) -> set[str]:
    return set(entity.dxftype() for entity in self.values())
```

L'ordre d'itération d'un ensemble de chaînes dépend de `PYTHONHASHSEED`, que
CPython tire au hasard à chaque démarrage. D'où deux ordres possibles, et deux
fichiers.

`add_required_classes` est appelée **pendant** `Drawing.write()`
(`document.py:601`, puis de nouveau depuis `update_all()` en `document.py:655`)
: trier la section `CLASSES` avant d'appeler `write()` serait défait par
`write()` elle-même.

## Trois correctifs possibles, et ce que chacun coûte

**A. Normaliser `EntityDB.dxf_types_in_use` au chargement du module**, à côté
de `write_fixed_meta_data_for_testing`, en rendant un conteneur ordonné
(`dict.fromkeys(sorted(...))`) plutôt qu'un ensemble.
*Pour :* une seule ligne, au seul endroit qui produit le désordre ; le seul
appelant de cette méthode dans `ezdxf` 1.4.4 ne fait que des tests
d'appartenance et une itération, tous deux préservés.
*Contre :* c'est un remplacement de méthode d'une bibliothèque tierce, global
au processus, et l'annotation de retour devient fausse. Une version ultérieure
d'`ezdxf` qui ferait `.union(...)` du résultat casserait.

**B. Écrire nous-mêmes la séquence d'export** au lieu d'appeler
`Drawing.write()`, en intercalant un tri de `doc.classes.classes` entre
`add_required_classes` et l'export.
*Pour :* rien de tiers n'est modifié.
*Contre :* recopie des rouages internes d'`ezdxf` ; se casse en silence à
chaque montée de version, c'est-à-dire exactement au moment où personne ne
regarde.

**C. Corriger `ezdxf` en amont** — `REQ_R2018` explicite, ou `sorted()` sur la
boucle — et remonter le correctif.
*Pour :* la seule correction qui tienne pour tout le monde.
*Contre :* elle ne nous protège qu'après publication et montée de version.

**Recommandation :** A, avec la mesure ci-dessus recopiée en commentaire, ET C
remonté en amont. B ne vaut pas sa dette.

## La preuve rouge à écrire d'abord

Un test qui rend **N fois la même coupe dans N sous-processus** et exige **une
seule empreinte**. Il doit tourner en sous-processus : dans un seul processus,
`PYTHONHASHSEED` est fixé une fois pour toutes et le test passerait toujours —
il ne mesurerait rien.

```
N rendus, N processus  ->  len({sha256}) == 1
```

Aujourd'hui : **rouge** (2 empreintes sur 8 rendus).

## Ce qui reste vrai en attendant

* le plan **décrit toujours la bonne section** : le désordre porte sur l'ordre
  de deux déclarations de classe, pas sur la géométrie, ni sur les barres, ni
  sur le cartouche ;
* tout logiciel de CAO lit les deux variantes de la même façon — la section
  `CLASSES` n'impose aucun ordre ;
* à l'intérieur d'une exécution, l'aperçu SVG et le fichier DXF sortent du même
  modèle gelé, et le plan reproduit après un rechargement est byte-identique.

Ce qui n'est pas vrai : que deux plans du même dessin portent la même
empreinte.
