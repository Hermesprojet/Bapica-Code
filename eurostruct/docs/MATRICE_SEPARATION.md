# La séparation migrateur / plan de contrôle — cinq couches, contre-exemple complet

**Mesure du 29/08, harnais permanent `db/test/separation_layers.sh`.** Décor
confondu : un seul rôle joue le migrateur *et* le plan de contrôle, et il est
**aussi** déclaré backend d'autorité — c'est ce qui met la couche 1 sur le
chemin. Sans cela elle ne s'exprimerait jamais, et l'on croirait le système
défendu par quatre couches.

## Les cinq couches, dans l'ordre où elles s'exécutent

| # | garde | où | quand |
|---|---|---|---|
| 1 | `assert_authority_backend_membership()` | `0013_authenticated_actor.sql` | phase 1 |
| 2 | exception procédurale de `normative_finalize_deployment` | sceau | finalisation |
| 3 | contrainte `finalization_intent_separates_roles` | sceau | finalisation |
| 4 | assertion de capacité résiduelle | sceau | finalisation |
| 5 | `normative_record_activation()` | sceau | juste avant d'écrire |

## Le résultat mesuré

| cas | état | étape | refus attribué à |
|---|---|---|---|
| baseline | REFUS | phase 1 | **1** |
| seule‑1 | PENDING | finalisation | 2 |
| seule‑2 | REFUS | phase 1 | *masqué par 1* |
| seule‑3 | REFUS | phase 1 | *masqué par 1* |
| seule‑4 | REFUS | phase 1 | *masqué par 1* |
| seule‑5 | REFUS | phase 1 | *masqué par 1* |
| laissée‑1 | REFUS | phase 1 | **1** |
| laissée‑2 | PENDING | finalisation | **2** |
| laissée‑3 | PENDING | finalisation | **3** |
| laissée‑4 | PENDING | finalisation | **4** |
| laissée‑5 | PENDING | finalisation | **5** |
| cumul‑1 | PENDING | finalisation | 2 |
| cumul‑12 | PENDING | finalisation | 3 |
| cumul‑123 | PENDING | finalisation | 4 |
| cumul‑1234 | PENDING | finalisation | 5 |
| **cumul‑12345** | **ACTIVE** | finalisation | **— aucun** |

## Le cas décisif

**`ACTIVE` est atteint quand, et seulement quand, les cinq couches tombent.**

C'est le contre-exemple complet que le lot L4 n'avait pas produit. Il établit
deux choses que « l'état n'atteint jamais `ACTIVE` » ne disait pas :

1. **il n'y a pas de sixième défense** — retirer les cinq suffit, donc la
   cartographie est close ;
2. **aucune des cinq n'est redondante** — chaque cas « laissée‑N » montre que
   la couche N refuse seule, les quatre autres étant retirées.

## Le masquage est nommé, pas subi

Neutraliser la seule couche 3 ne dit **rien** sur la couche 3 : la couche 1
refuse avant elle, en phase 1. Un harnais qui lirait ce refus comme « la 3
tient » se tromperait de garantie — c'est exactement la faute qui a produit
les onze survivants de `3d0acc2`, attribuer un refus à autre chose que sa
cause. Les quatre cas `seule‑N` sont donc marqués **masqués**, et ne concluent
rien.

## Ce que la mesure a corrigé dans la cartographie

### La couche 1 n'est pas une garde, c'est une fonction à trois branches

Première version du harnais : on neutralisait la branche H1 — l'ADMIN OPTION
en ligne directe. La phase 1 refusait **encore**, avec une signature inconnue.
C'était **H2**, la fermeture transitive :

> « … » peut ENRÔLER dans le backend d'autorité par une chaîne
> d'appartenances, sans y figurer en ligne directe. L'ADMIN se transmet : le
> borner ligne à ligne ne le borne pas.

H3 en ajoute une troisième (pluralité de porteurs de l'ADMIN). Neutraliser une
branche ne neutralise pas la couche, et cela aurait fait passer H2 pour une
sixième défense qui n'existe pas. Le harnais vise donc le **point de décision**
de la fonction — là où les écarts deviennent un refus.

### Conséquence pour la relaxation de `0015`

`0015` rabat `@MIGRATEUR` et `@PLAN` sur `@DEPLOIEMENT` quand les deux symboles
se confondent. Cette relaxation n'est acceptable que si l'état confondu ne peut
jamais atteindre `ACTIVE`. **C'est établi, et la mesure dit à quel prix** : il
faut retirer les cinq couches, dont une en phase 1 et une au dernier instant
avant l'écriture.

## Ce que le harnais prouve pour chaque cas

* la mutation demandée est **réellement active** — ancre trouvée une seule
  fois, et texte effectivement changé ;
* le décor atteint l'étape annoncée (phase 0, puis phase 1, puis finalisation),
  de sorte qu'un refus précoce n'est jamais lu comme un refus tardif ;
* l'état final est **mesuré**, pas supposé ;
* le refus est attribué à la couche exacte, **par la signature de son
  message** — pas par son rang.

## Trois défauts de banc, corrigés en chemin

Chacun a produit un diagnostic sans rapport avec la cause :

1. **l'ordre du teardown** — supprimer les rôles avant les bases échoue en
   silence ; les rôles canoniques survivaient et la phase 0 suivante refusait
   sur « permission denied to grant role eurostruct_normative_activator » ;
2. **une base de diagnostic laissée derrière** — `drop owned by` ne porte que
   sur la base *courante*, donc les rôles canoniques devenaient
   indestructibles et **seize cas** ont rougi pour une cause étrangère à ce
   qu'ils mesurent. Le harnais refuse désormais de démarrer sur un cluster qui
   porte déjà les rôles canoniques, plutôt que de nettoyer largement ;
3. **une variable hors portée** (`$SVC`, locale d'une autre fonction) tuait le
   teardown sous `set -u` après la première combinaison.
