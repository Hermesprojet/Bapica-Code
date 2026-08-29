# La séparation migrateur / plan de contrôle — cartographie mesurée

**Mesure du 29/08, décor confondu** : un seul rôle joue le migrateur *et* le
plan de contrôle ; le rôle de service est distinct ; la relaxation de phase 1
de `0015` est active. Les trois couches connues sont neutralisées dans les sept
combinaisons non vides.

## Le résultat

| couches neutralisées | état final | ce qui refuse ensuite |
|---|---|---|
| aucune | `PENDING` | **1** — exception procédurale |
| 1 | `PENDING` | **2** — CHECK `finalization_intent_separates_roles` |
| 2 | `PENDING` | 1 |
| 3 | `PENDING` | 1 |
| 1+2 | `PENDING` | **3** — assertion de capacité résiduelle |
| 1+3 | `PENDING` | 2 |
| 2+3 | `PENDING` | 1 |
| **1+2+3** | `PENDING` | **5** — `normative_record_activation()` |

**L'état n'atteint jamais `ACTIVE`.** Aucune des sept combinaisons ne fait
perdre l'invariant.

## Ce que la matrice a corrigé dans ma propre carte

J'annonçais trois couches. Il y en a **cinq**, et les deux que j'ignorais
encadrent les trois autres.

### Couche 4 — la plus précoce, en phase 1

`assert_authority_backend_membership()`, dans
`0013_authenticated_actor.sql`, refuse **avant même la finalisation** lorsque le
rôle confondu est aussi le backend d'autorité déclaré :

> frontière d'autorité : appartenance non déclarée — le login déclaré
> « … » détient l'ADMIN OPTION sur le backend d'autorité : il peut enrôler un
> tiers, et la liste déclarée cesse alors de décrire qui agit.

Le premier décor de cette matrice déclarait le rôle confondu comme backend
d'autorité, et se heurtait donc à cette couche : **la finalisation n'était
jamais atteinte**. Le décor a été corrigé — service distinct — pour que la
confusion porte sur migrateur/plan **seulement** et que les trois couches
visées soient réellement exercées.

### Couche 5 — la dernière, juste avant d'écrire

`normative_record_activation()`, dans le sceau :

> le migrateur « … » détient encore % capacité(s) sur les rôles d'autorité

Son commentaire dit exactement ce qu'elle fait : *« le migrateur ne doit plus
rien détenir. C'est la propriété que la finalisation achète, et elle est
constatée ICI, juste avant d'écrire. »* C'est elle qui refuse quand les trois
autres sont retirées.

## Conséquence pour la relaxation de `0015`

`0015` rabat `@MIGRATEUR` et `@PLAN` sur `@DEPLOIEMENT` quand les deux symboles
se confondent. Cette relaxation n'est acceptable que si l'état confondu ne peut
jamais atteindre `ACTIVE`.

**C'est établi, et plus solidement que je ne l'avais écrit** : non pas par une
garde, mais par cinq, dont une en phase 1 et une au dernier instant avant
l'écriture. Retirer les trois couches nommées ne suffit pas.

## Ce que la matrice n'établit pas

Elle n'a pas produit de contre-exemple complet. Obtenir `ACTIVE` à tort
exigerait de neutraliser **les cinq** couches, ce qui n'a pas été fait : la
mutation combinée `1+2+3` reste refusée, et le test permanent correspondant
n'existe donc pas encore. C'est un travail ouvert, pas un résultat.

Trois défauts de mon propre banc, corrigés en chemin et notés ici parce qu'ils
ont chacun produit un diagnostic sans rapport avec la cause :

1. **l'ordre du teardown** — supprimer les rôles avant les bases échoue en
   silence ; les rôles canoniques survivaient et la phase 0 suivante refusait
   sur « permission denied to grant role eurostruct_normative_activator » ;
2. **une variable hors portée** (`$SVC`, locale d'une autre fonction) tuait le
   teardown sous `set -u` après la première combinaison ;
3. **le rôle confondu déclaré comme backend d'autorité** faisait buter le
   décor sur la couche 4 au lieu des couches visées.
