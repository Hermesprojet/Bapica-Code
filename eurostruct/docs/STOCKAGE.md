# Le magasin d'objets — où vivent les octets d'un livrable

*Version du 31/08/2026. Ce document décrit un état vérifié, et il nomme
explicitement ce qui ne l'est pas.*

---

## 1. Le problème

`deliverables.storage_path` est une colonne `not null` depuis la première
migration, et pendant longtemps personne n'y avait écrit d'octets. Une ligne
pouvait nommer un chemin vide, le chemin d'un autre fichier, ou un chemin qui
n'a jamais existé — la table était exactement aussi convaincante dans les trois
cas.

Le premier magasin réel a été le **disque local** de l'API. Il a fermé le
défaut principal — une ligne enregistrée désigne désormais des octets qu'on
peut produire — mais il en a laissé un autre ouvert, et il faut le nommer :

> **Deux instances d'API derrière un répartiteur ne partagent pas un disque.**
> La moitié des téléchargements rendrait 503 sur des livrables parfaitement
> enregistrés, et le comportement dépendrait de l'instance qui a répondu.

Un volume nommé repousse le problème d'un cran ; il ne le ferme pas. Et un
document conservé **dix ans** au titre de la responsabilité décennale ne peut
pas dépendre du disque d'une machine.

---

## 2. Les deux magasins, et rien d'autre

`EUROSTRUCT_STORAGE_BACKEND` vaut `local` ou `s3`. Vide vaut `local`.

**Une valeur inconnue est refusée**, pas ramenée au défaut. Un « s4 », un
« S3 » mal recopié, un espace de trop : les ramener au disque local ferait
écrire les livrables d'une production sur un disque éphémère, sans un mot.

| | `local` | `s3` |
|---|---|---|
| Ce que c'est | un répertoire du système de fichiers | un compartiment S3-compatible, **privé** |
| Pour qui | poste de travail, machine unique | tout déploiement à plus d'une instance |
| Sa limite | ne se partage pas, ne se réplique pas | dépend d'un service externe joignable |
| Éprouvé par | `db/test/livrable_validation.sh` | `db/test/stockage_s3.sh` (MinIO réel) |

### Aucun repli de `s3` vers le disque

Dans aucune circonstance. Une configuration S3 incomplète, un endpoint
injoignable, un compartiment absent : la création d'un livrable **refuse par un
503 explicite**, qui nomme les variables manquantes — jamais leurs valeurs.

Écrire sur le disque du conteneur « en attendant » produirait des lignes en
base qui promettent des documents introuvables, découverts dix ans plus tard.
Un refus au moment de créer est infiniment préférable.

Les **calculs**, eux, continuent : produire un document et enregistrer un
calcul sont deux choses différentes.

---

## 3. Ce qui est établi, et ce qui ne l'est pas

**Établi.** Le protocole S3 tel que **MinIO** l'implémente : signature SigV4
calculée à la main sur `urllib` (aucune dépendance ajoutée), dépôt, relecture,
lecture en flux, taille, idempotence du second dépôt, refus d'écraser un objet
divergent. Éprouvé localement **et en intégration continue**, contre un serveur
réel, sur un volume neuf, avec redémarrage entre le dépôt et la relecture.

**Non établi.** AWS S3, Supabase Storage, ou tout autre fournisseur nommé.
Aucun n'a été joint depuis ce dépôt. Un serveur qui parle le même protocole
n'est pas une promesse de compatibilité avec un service qu'on n'a pas essayé.
**`SUPABASE_UNVERIFIED` reste vrai.**

---

## 4. Les clés dérivent du contenu

```
<préfixe>/<org_id>/<project_id>/<sha256>.<extension>
```

* **L'adressage par contenu n'est pas une élégance.** La contrainte SQL
  `storage_path_derives_from_sha` exige que le chemin contienne l'empreinte :
  aucune ligne ne peut désigner un emplacement sans rapport avec le contenu
  qu'elle annonce.
* **Deux dépôts des mêmes octets écrivent au même endroit**, ce qui rend le
  second idempotent au lieu d'être une seconde copie qui pourrait diverger.
* **Le cloisonnement est dans le chemin aussi.** Une erreur de configuration
  qui exposerait le magasin exposerait au moins une arborescence où les
  organisations sont séparées, plutôt qu'un seul répertoire plat.
* **Aucun segment ne vient d'un humain.** Identifiants et empreinte sont
  contrôlés ; le nom de fichier choisi par l'utilisateur ne traverse jamais
  jusque-là. Un nom de projet contenant `../` n'a aucun chemin pour sortir de
  la racine.

### Un objet divergent n'est jamais écrasé en silence

La clé dérive du contenu. Un objet **déjà présent** sous cette clé avec une
**autre taille** est donc une contradiction : la clé ne désigne plus son
contenu. C'est le signe d'une corruption ou d'une collision, et l'écraser
effacerait la seule trace du problème. Le dépôt refuse (`OctetsAlteres` → 503).

---

## 5. Politique des objets orphelins

Un **orphelin** est un objet du compartiment qu'aucune ligne de `deliverables`
ne référence.

### La règle

> **Rien n'est jamais supprimé du magasin par le produit.**
> `ClientS3` **n'a aucune méthode de suppression**, et ce n'est pas un oubli.

Il n'existe donc pas de chemin de code, pas d'option de configuration et pas de
tâche planifiée capable de supprimer un objet encore référencé — parce qu'il
n'en existe aucun capable de supprimer un objet **tout court**.

### Pourquoi cette règle plutôt qu'un ramasse-miettes

1. **La rétention est de dix ans, et elle est immuable.** Un ramasse-miettes
   qui se trompe sur un livrable attesté détruit une pièce dont la conservation
   est une obligation légale. Le coût d'un objet inutile est quelques dizaines
   de kilo-octets ; le coût d'une pièce manquante n'a pas de borne.
2. **« Non référencé » se lit dans une base qui change.** Une transaction en
   cours, une restauration en cours, une réplique en retard : les trois
   présentent un objet parfaitement légitime comme orphelin. Un balayage
   correct exigerait un instantané cohérent des deux systèmes au même instant,
   ce que rien ici ne garantit.
3. **L'adressage par contenu borne le gaspillage.** Deux documents identiques
   occupent une seule clé. Un orphelin est le résidu d'une tentative refusée
   après dépôt, et une note de calcul pèse quelques dizaines de kilo-octets.

### Comment un orphelin apparaît

La forme est toujours la même : les octets sont déposés, puis l'enregistrement
de la ligne échoue.

**Cette section a affirmé qu'une panne en était le seul chemin. C'était faux, et
la mesure l'a montré.** Un refus parfaitement ordinaire en produisait un autre :

> `POST …/deliverables/{id}/revision` avec un `id` qui n'est pas un livrable de
> ce projet. `supersedes_id` n'était contrôlé **nulle part** avant
> `creer_livrable` : la route composait, **déposait**, relisait, puis appelait
> la primitive — qui refusait à juste titre. Résultat : `422`, aucune ligne, et
> un objet définitivement abandonné dans le compartiment.

Se tromper d'identifiant de livrable — une page rouverte, une URL recopiée — est
l'erreur la plus banale qui soit. Elle coûtait une fuite permanente, puisque
rien ici ne supprime jamais.

Le contrôle a été **remonté avant le dépôt**, dans
`api/src/eurostruct_api/routes/livrables.py`, en relisant le livrable remplacé
par `project_deliverable_read` — une fonction déjà déclarée au backend, qui
porte la même borne de projet. Deux cas le tiennent :

| Cas | Ce qu'il verrouille |
|---|---|
| `test_une_revision_refusee_ne_laisse_pas_d_objet_que_rien_ne_reference` | le chemin qui fuyait — mesuré rouge, puis vert |
| `test_un_calcul_d_un_autre_projet_ne_laisse_pas_d_octets` | l'autre refus tardif, qui lui refusait **déjà** avant le dépôt |

**Ce qui reste, et qui est irréductible** : une panne entre le dépôt et le
`commit`. Elle laisse un objet inutile plutôt qu'une ligne menteuse, et c'est le
bon compromis. C'est précisément ce résidu que le rapprochement en lecture seule
existe pour rendre visible.

**La leçon vaut plus que le correctif.** Une politique « on ne supprime jamais »
n'est tenable que si l'on sait aussi **ne pas produire** ce qu'on ne pourra pas
reprendre. Tout refus prononcé après un dépôt est une fuite définitive : l'ordre
des opérations n'est pas un détail de propreté, c'est la condition de la
politique.

### Ce qu'on fait à la place

* **Constater**, jamais supprimer : un rapprochement en **lecture seule** entre
  les clés du compartiment et les `storage_path` de la base. Il n'existe pas
  encore ; quand il existera, il produira un rapport, pas une suppression.
* **Supprimer se fait hors du produit**, par une personne, avec une décision
  écrite, sur des clés nommées une à une. Aucune suppression par motif large.
* **Les harnais font exception, et de la seule façon acceptable** :
  `db/test/stockage_s3.sh` détruit le **volume Docker qu'il a créé**,
  c'est-à-dire un objet dont il peut prouver la création. Il ne supprime
  jamais un objet dans un compartiment qu'il n'a pas créé.

---

## 6. Le téléchargement

Les octets partent **en flux**, par blocs, et l'empreinte est calculée **au fil
de l'eau**.

Le premier bloc est lu **hors du générateur** : un objet absent ou un magasin
injoignable devient un 503 **avant** que le moindre en-tête ne parte. Une fois
la réponse commencée, il n'y a plus de code de statut à corriger.

**Ce que le flux ne peut pas faire, et qui est dit ici.** L'empreinte n'est
connue qu'à la fin : les premiers blocs sont déjà partis quand une altération
se révèle. Le générateur **lève** alors plutôt que de conclure, et le client
reçoit une réponse **interrompue** — un corps tronqué, détectable — au lieu
d'un document complet et faux. L'empreinte attendue reste par ailleurs lisible
sur la fiche du livrable et dans le manifeste du dossier de revue : un
destinataire peut la vérifier lui-même.

### Le nom du fichier, sous les deux formes

`Content-Disposition` porte `filename` (repli ASCII) **et**
`filename*=UTF-8''…` (RFC 5987). Un nom accentué n'est pas représentable dans
la forme simple, et un octet non ASCII dans un en-tête HTTP est au mieux
ignoré, au pire tronqué.

Les guillemets et retours à la ligne sont **retirés** du repli, pas échappés :
un nom de fichier contenant `"` refermerait le paramètre et permettrait d'en
injecter un autre.

### Un livrable déposé sur S3 ne se lit pas sur le disque local

La route compare le magasin configuré à `deliverables.storage_backend` et
**refuse** si les deux diffèrent. Servir « ce qu'on trouve là où on regarde
aujourd'hui » rendrait un document d'un autre déploiement, ou rien du tout,
sans que la différence se voie.

---

## 7. Aucun secret ne sort

* Les messages d'erreur nomment les **variables** absentes, jamais leurs
  valeurs. `S3Refuse` est construite pour ne porter ni clé ni identifiant.
* `/health` et `/ready` se lisent **sans jeton** : tout ce qu'elles disent est
  public par construction. Deux cas de `test_stockage_s3.py` vérifient qu'aucune
  réponse HTTP — succès, refus, sonde — ne contient la clé d'accès, le secret
  ou l'endpoint.
* Dans les harnais, les identifiants passent par un **fichier d'environnement
  en 0600** ou par `MC_HOST_*`, jamais par `argv` : une commande qui porte un
  secret le montre à `docker inspect` et à tout `ps`.
* Le compartiment est **privé**. La composition pose explicitement
  `mc anonymous set none` : un compartiment public exposerait des notes de
  calcul nominatives à qui devine une URL.

---

## 8. Le compartiment n'est pas créé par le produit

`StockageS3` ne crée aucun compartiment dans le chemin de service. Un service
qui créerait le sien au démarrage masquerait une erreur de configuration : il
écrirait dans un compartiment **neuf** au lieu de refuser parce que celui qu'on
a nommé n'existe pas, et les livrables partiraient dans le vide, sans un mot.

Le provisionnement est fait :

* par la composition, service `objets-init` (`mc mb` + `mc anonymous set none`) ;
* par le harnais de test, via `ClientS3.creer_compartiment()` — une méthode
  **réservée aux harnais**, qu'aucune route n'appelle.

---

## 9. Les huit étapes que la CI exécute

`db/test/stockage_s3.sh`, contre un MinIO réel :

1. un **volume neuf**, créé par le harnais et constaté vide ;
2. le **compartiment**, créé par notre propre signature SigV4 — pas par un
   outil tiers ;
3. le **dépôt** d'un livrable par les routes réelles, depuis un calcul strict ;
4. l'**arrêt de l'API** (le processus est détruit) et le **redémarrage** du
   serveur MinIO ;
5. le **téléchargement** dans un processus neuf, qui ne crée rien ;
6. la **comparaison du SHA** — et, hors du produit, la recherche des octets
   servis **verbatim** dans le volume copié par `docker cp` ;
7. le **refus inter-organisations** : le témoin lit l'objet dans le
   compartiment, et le membre du bureau voisin est refusé. C'est ce qui
   distingue « on ne vous le donne pas » de « il n'y est pas » ;
8. la **destruction** du conteneur et du volume, tous deux créés ici, et rien
   d'autre.

Le harnais vérifie aussi, à chaque étape, que le **disque local reste vide** :
`EUROSTRUCT_STORAGE_DIR` pointe sur un répertoire jetable, et un seul fichier
qui y apparaîtrait révélerait un repli silencieux.
