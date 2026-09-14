# Le DXF n'est pas stable d'un processus à l'autre — **FERMÉ le 02/09/2026**

**Ouvert le 01/09, corrigé le 02/09.** La correction est
`engine/src/eurostruct_engine/drawing/ezdxf_determinisme.py` ; la preuve est
`engine/tests/test_dxf_determinisme.py`.

---

## Le fait, tel qu'il a été mesuré

Deux rendus du **même** `BeamSectionSpec`, dans deux processus Python
distincts, produisaient deux fichiers DXF de **taille identique** et de contenu
différent.

```
AVANT   4 c1ffa143113ec2d429a74a2b7a59b89686038149787e0f3576a67029561192aa  63993
        4 7d2d548843c05e9dab37968294ef9875fc710829963480dd3964582256c9d355  63993

APRÈS  10 03c0d9e243a7374f027a0b7e3301df692fd40c3c52973205b0b3b146083602ea  63993
```

Taille inchangée : le fichier porte le même contenu, dans un ordre désormais
canonique.

À l'intérieur d'un même processus, deux rendus successifs étaient déjà
byte-identiques — c'est pourquoi le défaut a survécu à tous les tests
existants, qui tournent tous dans le processus de pytest, où
`PYTHONHASHSEED` est fixé une fois pour toutes.

## Ce que cela coûtait

**LE CHEMIN DE STOCKAGE D'UN LIVRABLE DÉRIVE DE SON SHA-256.** Un fichier dont
les octets bougent d'une exécution à l'autre :

1. **se déposait deux fois, sous deux chemins.** La politique du magasin
   (`docs/STOCKAGE.md` §5) interdit toute suppression par le produit : chaque
   variante était **définitive** ;
2. **cassait la comparaison d'empreintes.** Un auditeur comparant le SHA-256 de
   deux plans identiques concluait qu'ils diffèrent.

## La cause, exactement

Huit lignes de diff, toutes dans la section `CLASSES` : les enregistrements
`LAYOUT` et `ACDBPLACEHOLDER` échangeaient leur place.

Le document est en **R2018**. Dans `ezdxf/sections/classes.py`,
`REQUIRED_CLASSES` ne contient que `DXF2000 -> REQ_R2000` et
`DXF2004 -> REQ_R2004`, si bien que toute version postérieure retombe sur
`REQ_R2004`, **qui ne cite ni `LAYOUT` ni `ACDBPLACEHOLDER`** (alors que
`REQ_R2000` cite les deux). Ces deux classes n'étaient donc enregistrées que
par la boucle finale de `add_required_classes` :

```python
dxf_types_in_use = self.doc.entitydb.dxf_types_in_use()   # entitydb.py:297
...
for dxftype in dxf_types_in_use:
    self.add_class(dxftype)
```

et `dxf_types_in_use` rend un **`set[str]`**. L'ordre d'itération d'un ensemble
de chaînes dépend de `PYTHONHASHSEED`, que CPython tire au hasard à chaque
démarrage.

## La correction retenue

`ezdxf_determinisme.appliquer()`, appelé au chargement de
`drawing/beam_section.py`, **enveloppe** `ClassesSection.add_required_classes` :
l'originale est appelée telle quelle, puis `self.classes` est remis dans un
ordre canonique (tri sur la clé `(name, cpp_class_name)`).

Le correctif ne dépend donc **pas** de la façon dont `ezdxf` décide d'ajouter
ses classes — seulement du fait que l'export suit l'ordre de ce dictionnaire.

### Ce qui a été écarté, et pourquoi

| Écarté | Raison |
|---|---|
| `PYTHONHASHSEED` fixé au déploiement | Déplace la garantie hors du code, dans une variable qu'un opérateur, un conteneur ou un ordonnanceur peut ne pas poser. Le jour où elle manque, le produit redevient non déterministe **sans que rien ne le dise**. |
| Un nouvel exporteur DXF | Échangerait un défaut connu contre une surface entière à maintenir, pour un problème d'ordre. |
| Réimplémenter `add_required_classes` | Nous ferions décider au produit **quelles** classes le format exige — un choix qui change avec le format et dont ce n'est pas le rôle. |
| Patcher `EntityDB.dxf_types_in_use` | Plus proche de la cause, mais rend un `set[str]` par contrat : une version ultérieure qui ferait `.union(...)` du résultat casserait en silence. |

### Le garde-fou

`verifier_signature()` refuse — `EzdxfIncompatible`, levée **au chargement du
module**, donc avant tout rendu — si l'un de ces quatre faits n'est plus vrai :

1. `add_required_classes` existe et est une fonction ;
2. sa signature est `(self, dxfversion)` ;
3. `ClassesSection.classes` est un dictionnaire ;
4. **l'export suit l'ordre de ce dictionnaire** — vérifié en exportant
   réellement une section inversée, pas en lisant la source.

Le quatrième est le fait porteur : réordonner ne servirait à rien si l'export
triait de son côté.

Versions éprouvées : **ezdxf 1.4.4**. Le numéro sert au **message** d'un refus,
pas à le déclencher : refuser sur le seul numéro ferait échouer le produit à la
première montée corrective alors que la structure n'a pas bougé.

## Les preuves

`engine/tests/test_dxf_determinisme.py`, neuf contrôles :

| Contrôle | Ce qu'il ferme |
|---|---|
| 10 rendus, 5 germes (`0`, `1`, `12345`, `98765`, `random`), sous-processus neufs | **une seule empreinte** |
| le rendu du processus de test = celui d'un processus neuf | un correctif qui ne s'appliquerait qu'aux sous-processus |
| 8 rendus concurrents (`ThreadPoolExecutor`) | un correctif passant par un état global mutable |
| relecture `ezdxf` + `Auditor` | un fichier déterministe qui ne s'ouvrirait plus |
| géométrie relue depuis les octets : 4 cercles Ø20, contour 300×600 | un correctif qui déplacerait quelque chose |
| méthode absente / signature changée / export indifférent à l'ordre | le garde-fou se falsifie sur ses trois branches |
| double `appliquer()` | l'enveloppe ne s'empile pas |

Et à la frontière HTTP,
`api/tests/test_verification_complete.py::test_deux_demandes_du_meme_plan_ne_font_qu_un_objet` :
deux demandes du même plan → **deux lignes de livrable** (deux gestes
horodatés et attribués) mais **un seul objet** dans le magasin.

## Remonté en amont ?

Non — pas encore. La correction juste pour tout le monde est dans `ezdxf` :
soit un `REQ_R2018` explicite, soit un `sorted()` sur la boucle finale de
`add_required_classes`. Notre enveloppe reste utile même après : elle ne
dépend pas de la version, et son garde-fou dira si elle devient inutile.
