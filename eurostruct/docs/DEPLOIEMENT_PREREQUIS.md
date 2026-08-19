# EUROSTRUCT — déployer la chaîne normative

> **Ce document décrit le code présent, pas l'histoire des versions
> précédentes.** Chaque prérequis listé ici a été **rencontré** par un harnais
> qui échoue quand il n'est pas tenu — jamais déduit d'une lecture du code.

## 0. Le chemin officiel

```sh
export ESC_PLAN_URL='postgresql://plan:…@hote:5432/base'
export ESC_MIGRATOR_URL='postgresql://migrateur:…@hote:5432/base'

tools/deploy_eurostruct.sh --dry-run     # les deux connexions, rien d'appliqué
tools/deploy_eurostruct.sh               # les dix étapes, postconditions vérifiées
```

La commande orchestre les trois phases, **vérifie** ses postconditions et
refuse plutôt que de dégrader. Elle ne crée ni ne détruit aucun rôle et aucune
base : provisionner est un geste d'exploitation, décrit au §2.

Les identifiants passent par l'**environnement**, jamais par `argv` — qui est
lisible par tout processus de la machine. Les deux URL sont découpées puis
effacées.

**Relancer la commande est sûr.** Si `psql` échoue sur une coupure réseau, on
ne sait pas si la transaction a été validée : relancez. La phase 0 rend
`SEAL_ALREADY_INSTALLED` sans rien muter, les migrations sont idempotentes, une
base déjà `ACTIVE` saute les étapes 3 à 7, et la finalisation rend « ACTIVE
(déjà finalisé) » **si et seulement si** le manifeste présenté est celui qui a
été approuvé. Ce qu'il ne faut pas faire : rejouer une étape à la main, ou
réaccorder les emprunts « pour être sûr ».

## 1. Quatre acteurs, et ils ne se confondent pas

| Acteur | Ce que c'est | Ce qu'il peut | Ce qu'il ne peut pas |
|---|---|---|---|
| **Plan de contrôle** | un rôle de connexion, **non superutilisateur**, distinct du migrateur | poser le sceau (phase 0), prêter les emprunts, **approuver** et finaliser (phase 2) | écrire une confirmation normative |
| **Migrateur** | le rôle qui applique `db/migrations/` | appliquer le schéma | approuver, activer, posséder une preuve |
| **`eurostruct_deployment`** | un rôle canonique `NOLOGIN`, **accordé au plan de contrôle** | ouvrir la chaîne de confiance (amorçage), lire l'état, exercer la phase 2 | être membre d'un rôle d'autorité |
| **Rôles applicatifs** | `authenticated`, `normative_backend`, `normative_governance` | ce que leurs politiques RLS permettent | tout le reste |

**Les rôles canoniques sont globaux au cluster.** `eurostruct_normative_writer`,
`…_bootstrap`, `…_activator`, `normative_backend`, `normative_governance` et
`eurostruct_deployment` ne sont pas confinés à une base : plusieurs bases
EUROSTRUCT du même cluster **partagent la même topologie de rôles**. Deux
conséquences directes :

* prêter les emprunts pour déployer la base B les prête aussi vis-à-vis de la
  base A — la finalisation de B les rend, et rétablit les deux ;
* deux bases du même cluster ne peuvent pas avoir deux plans de contrôle
  différents sans une **stratégie de nommage** distincte (préfixer les six
  rôles par base). Cette stratégie n'est pas implémentée : à ce jour, un
  cluster porte **un** jeu de rôles canoniques.

### `eurostruct_deployment` : ce qu'il détient réellement

Il ne reçoit **pas** « `EXECUTE` sur l'amorçage et rien d'autre ». Il porte
toute la surface d'exploitation :

* **la phase 2** — `normative_finalize_deployment(manifeste)`, et les deux
  primitives `normative_prepare_activation(manifeste)` /
  `normative_record_activation()` ;
* **la lecture d'état** — `normative_activation_state()`,
  `normative_deployment_readiness()`, `normative_seal_version()`,
  `normative_seal_assurance()`, `normative_control_plane()` /
  `…_oid()`, `normative_pending_migrator()` ;
* **les manifestes** — `normative_settings_manifest()`,
  `normative_approved_manifest()`, `normative_exiger_manifeste_approuve()` ;
* **l'audit** — `assert_normative_topology()`, `normative_topology_digest(…)`,
  `normative_effective_setting(…)` ;
* **l'amorçage** — `bootstrap_normative_administrator(…)`, une seule fois, un
  index d'unicité y veille.

Il n'est membre d'**aucun** rôle d'autorité, et les prérequis de la phase 1
refusent l'installation s'il le devenait. Ouvrir la chaîne et forger une preuve
restent deux pouvoirs distincts.

## 2. Ce que l'exploitant provisionne, avant la commande

```sql
-- les deux acteurs, NON superutilisateurs et DISTINCTS
CREATE ROLE migrateur LOGIN PASSWORD '…' CREATEROLE CREATEDB;
CREATE ROLE plan      LOGIN PASSWORD '…' CREATEROLE;

CREATE DATABASE base OWNER migrateur;

\connect base
GRANT CREATE ON DATABASE base TO migrateur;
GRANT USAGE  ON SCHEMA auth   TO migrateur WITH GRANT OPTION;
GRANT SELECT, INSERT, REFERENCES ON auth.users TO migrateur WITH GRANT OPTION;
GRANT EXECUTE ON FUNCTION auth.uid()           TO migrateur WITH GRANT OPTION;

GRANT CREATE ON SCHEMA public TO plan WITH GRANT OPTION;
GRANT USAGE  ON SCHEMA auth   TO plan;

-- les déclarations que la finalisation figera
ALTER DATABASE base SET eurostruct.approved_deployment_roles = 'migrateur,plan';
ALTER DATABASE base SET eurostruct.token_roles               = 'authenticated,anon';
-- si un rôle connectable doit atteindre un rôle de service (cas Supabase) :
ALTER DATABASE base SET eurostruct.approved_service_logins   = 'authenticator';
```

Puis, **après le premier appel de la commande** — `eurostruct_deployment`
n'existe pas avant la phase 0 :

```sql
GRANT eurostruct_deployment TO plan WITH INHERIT TRUE;
```

### Les cinq droits du plan de contrôle, et leur raison

| Droit | Pourquoi |
|---|---|
| `CREATE` sur la base | il y crée les tables de confiance |
| `CREATE` sur `public` **`WITH GRANT OPTION`** | il doit **retransmettre** ce droit à `eurostruct_normative_activator`, qui devient propriétaire de ces objets — PostgreSQL l'exige du nouveau propriétaire |
| `USAGE` sur `auth` | les fonctions scellées le référencent |
| `CREATEROLE` | il crée les six rôles canoniques, s'ils n'existent pas déjà |
| `eurostruct_deployment` (**après** la phase 0) | c'est ce rôle qui porte la phase 2 |

## 3. Les trois phases, et qui exerce quoi

| Phase | Ce qui est appliqué | Par | Résultat |
|---|---|---|---|
| **0** | `db/control_plane/0001_normative_seal.sql` | **plan de contrôle** | les six rôles canoniques, la racine de confiance (cinq tables possédées par `eurostruct_normative_activator`, RLS **forcée**), et l'identité du sceau |
| **1** | `db/migrations/*.sql` | **migrateur** | le schéma applicatif ; se termine en `PENDING` |
| **2** | `normative_finalize_deployment(<manifeste>)` | **plan de contrôle** | manifeste comparé, emprunts **révoqués**, activation inscrite → `ACTIVE` |

`db/migrations/` ne contient **que** ce que le migrateur applique. Aucun outil
n'a à y faire d'exception : la frontière est celle des répertoires.

### Pourquoi deux rôles, et pas un

PostgreSQL n'accepte `ALTER FUNCTION … OWNER TO r` que si le rôle courant peut
faire `SET ROLE r`. La phase 1 doit donc **endosser** les rôles dont elle rend
ses fonctions propriétaires. Tant que la racine de confiance appartenait à un
rôle emprunté par le migrateur, elle était **à sa portée** — mesuré : un
`SET ROLE eurostruct_normative_activator` puis un `INSERT` suffisaient à rendre
l'état `ACTIVE` sans finalisation, sans manifeste, sans restitution.

Un déploiement où **un seul** rôle privilégié existe s'installe (phase 1) mais
**ne se finalise pas** : la phase 2 refuse en nommant la séparation manquante.
Ce n'est pas une dégradation silencieuse, c'est un refus.

### Qui accorde les emprunts, qui les révoque, et quand

C'est le point que ce document énonçait de deux façons contradictoires.

| Geste | Par | Quand |
|---|---|---|
| `GRANT eurostruct_normative_writer, …_bootstrap TO migrateur WITH ADMIN OPTION` | **plan de contrôle** (étape 3 de la commande) | après la phase 0, avant la phase 1 |
| révocation de ces deux appartenances | **plan de contrôle**, à l'intérieur de `normative_finalize_deployment()` | phase 2 |

**La phase 1 ne rend rien.** Elle emprunte, elle s'en sert, elle laisse la base
en `PENDING` — emprunts encore détenus. C'est la **phase 2** qui les révoque,
constate que la révocation a pris, et n'inscrit l'activation qu'ensuite. Toute
exception annule l'ensemble : il n'existe pas d'état intermédiaire où les
emprunts seraient rendus sans que l'activation soit inscrite, ni l'inverse.

Pourquoi le plan de contrôle et pas un autre : PostgreSQL n'accorde d'effet à
un `REVOKE` d'appartenance que s'il est exercé par le **donneur** de l'octroi.
Un `REVOKE` par un tiers, même détenteur de l'`ADMIN OPTION`, émet un simple
*warning* et ne retire rien.

`eurostruct_normative_activator` n'est **jamais** prêté : il possède la racine.

### Le poseur du sceau est celui qui finalise

Le sceau enregistre qui l'a posé — OID **et** nom. La finalisation exige la
même identité et refuse par `SEAL_INSTALLER_MISMATCH` sinon. Le plan de
contrôle d'une base est celui qui a posé sa racine : il ne se transfère pas par
un `GRANT`. Aucune procédure de délégation n'existe à ce jour ; si elle est
voulue, ce devra être un événement explicite et audité.

**Exception mesurée** : un sceau posé par un **superutilisateur** ne porte pas
cette liaison. PostgreSQL enregistre les octrois d'un superutilisateur au nom
du superutilisateur *d'amorçage* (`postgres`, oid 10), jamais du rôle qui les a
exécutés — le donneur dérivé n'est donc jamais le poseur. La garantie n'est pas
perdue pour autant : elle n'existait pas, un superutilisateur endossant qui il
veut de toute façon. La base le **dit**, voir §4.

## 4. Niveau d'assurance : deux formes, et elles ne s'équivalent pas

La phase 0 inscrit dans `normative_seal_metadata` un niveau que la readiness
relit — il ne vit pas seulement dans une sortie console.

| Niveau | Quand | Ce que ça vaut |
|---|---|---|
| `CONTAINED_NON_SUPERUSER` | phase 0 posée par un rôle non superutilisateur | la forme qui obtient les garanties du modèle de menace |
| `UNCONTAINED_SUPERUSER` | phase 0 posée par un superutilisateur (ou depuis une session superutilisateur) | déploiement **auto-hébergé, explicitement dégradé** |

`tools/deploy_eurostruct.sh` **refuse** `UNCONTAINED_SUPERUSER` par défaut.
`--auto-heberge` l'accepte, et l'annonce. Il ne doit jamais être présenté comme
offrant la même assurance.

```sql
SELECT * FROM normative_deployment_readiness();
--  etat | sceau | assurance | plan_de_controle | topologie | motif
```

## 5. Faire évoluer le sceau

Le sceau porte une version — `esc-normative-seal/1` — inscrite à
l'installation. La phase 1 exige une version d'une **liste explicite et
fermée** : une comparaison « supérieure ou égale » accepterait par construction
toutes les versions futures, c'est-à-dire celles dont on ne sait rien.

Réappliquer le fichier du sceau a une sémantique décidée, portée par des
SQLSTATE dédiés pour qu'un orchestrateur branche sur le **code** et jamais sur
le texte :

| Situation | Résultat | SQLSTATE |
|---|---|---|
| aucun objet de la racine | installation | — |
| racine complète, **même** version | `SEAL_ALREADY_INSTALLED`, **aucune mutation** | `ES001` |
| racine complète, **autre** version | `SEAL_VERSION_MISMATCH` | `ES002` |
| racine **incomplète** | `SEAL_PARTIAL`, fail-closed | `ES003` |

Une racine à moitié posée ne se répare pas en relançant : on ne saurait plus
quelle version elle porte. Repartez d'une base neuve.

**Une future version** sera un fichier `db/control_plane/000N_….sql` appliqué
par le **poseur enregistré** — lui seul détient l'`ADMIN` résiduel sur
l'activateur, donc la seule capacité de le ré-emprunter — et ajoutera sa ligne
à `normative_seal_metadata`, qui est append-only : la version 1 reste inscrite,
la version 2 s'ajoute, la dernière fait foi. `normative_seal_assurance()` rend
en revanche le niveau de la **première** génération : une mise à niveau ne lave
pas une installation superutilisateur.

## 6. Restauration inter-cluster : non prise en charge

Un `pg_dump`/restore vers un autre cluster recrée les rôles avec de **nouveaux
OID**. L'identité figée du plan de contrôle porte l'ancien : la topologie
refuse, en diagnostiquant `RESTAURATION INTER-CLUSTER`.

**Ce refus est définitif pour cette base.** Il n'existe aucune procédure de
reprise. Exercé sur une restauration réelle entre deux clusters
(`db/test/cross_cluster_restore.sh`), le seul geste que le diagnostic pouvait
suggérer rend `MANIFEST_MISMATCH`, et vider la table d'activation est refusé
même au **propriétaire** de la base restaurée.

Le chemin supporté vers un autre cluster est un **déploiement neuf** — phases
0, 1 et 2 sur le cluster cible — suivi d'une reprise des données métier. Cette
procédure de reprise **n'existe pas encore** : tant qu'elle n'existe pas,
migrer une base EUROSTRUCT en service vers un autre cluster est un **blocage de
mise en production**.

L'OID n'est délibérément pas réinscriptible : le rendre modifiable « pour
réparer une restauration » rouvrirait exactement la substitution que 6.3b6b a
fermée.

## 7. Ce qui est vérifié, et où

| Question | Établi par | Sur quoi |
|---|---|---|
| Les trois phases s'enchaînent sous deux rôles non superutilisateurs | `nonsuperuser_install.sh`, `two_phase_deployment.sh` | **PostgreSQL 16 local / CI** |
| Le migrateur ne peut ni produire `ACTIVE`, ni effacer une preuve | `authority_closure.sh` | **PostgreSQL 16 local / CI** |
| La phase 2 ne se contourne pas | `finalisation_contract.sh` | **PostgreSQL 16 local / CI** |
| Le sceau est séparé, versionné, réexécutable ; le poseur finalise | `seal_contract.sh` | **PostgreSQL 16 local / CI** |
| La commande officielle tient ses postconditions | `official_deployment.sh` | **PostgreSQL 16 local / CI** |
| La restauration inter-cluster échoue fail-closed | `cross_cluster_restore.sh` (second cluster réel, `initdb`) | **PostgreSQL 16 local / CI** |
| Prérequis topologiques sur les rôles | `role_prerequisites.sh` | **PostgreSQL 16 local / CI** |
| **Compatibilité Supabase** | — | **NON VALIDÉ** |

La colonne de droite est le sujet de ce tableau. Tout ce qui précède est
**testé sur PostgreSQL 16**, en local et en CI. Rien n'est **validé sur un
staging Supabase**, et les deux ne sont pas la même chose.

### Pourquoi la compatibilité Supabase n'est pas acquise

`nonsuperuser_install.sh` reproduit le **modèle de privilèges** de Supabase —
rôle de migration avec `CREATEROLE` et `CREATEDB` mais sans `SUPERUSER`, schéma
`auth` qui ne lui appartient pas, rôles applicatifs `NOLOGIN` endossés par un
rôle connectable — sur un PostgreSQL 16 ordinaire.

Il ne reproduit **pas** : les extensions préinstallées de Supabase, ses
politiques par défaut, PgBouncer, ses *event triggers*, ni le contenu réel de
son schéma `auth`.

Une exécution en CI, même sous un rôle non superutilisateur, ne peut donc pas
établir la compatibilité Supabase. Elle sera établie par une exécution sur une
**instance de staging réelle**, et pas avant. Jusque-là, la mention
« compatible Supabase » ne doit apparaître nulle part.

## 8. Prérequis rencontrés, et l'obstacle qui les a révélés

Chacun de ces points a fait **échouer** un déploiement sous un rôle non
superutilisateur. Aucun n'était visible en CI superutilisateur.

### 8.1 `REFERENCES` sur `auth.users`

Le schéma déclare des clés étrangères vers `auth.users`. PostgreSQL exige
`REFERENCES`, et non `SELECT`, pour en créer une.

### 8.2 `GRANT OPTION` sur les objets de `auth`

La phase 1 **retransmet** l'accès à `auth` aux rôles d'autorité. Sans
`GRANT OPTION`, PostgreSQL **n'échoue pas** : il émet un *warning* et n'accorde
rien. La chaîne casse alors bien plus tard, à la première confirmation, sur un
`permission denied for schema auth` que rien ne relie à sa cause. La phase 1
vérifie désormais le résultat de ses propres `GRANT` et refuse.

### 8.3 `CREATE` sur le schéma `public`

Depuis PostgreSQL 15, `public` n'accorde plus `CREATE` à `PUBLIC`. Or le
**nouveau propriétaire** d'une fonction doit avoir `CREATE` sur le schéma qui
la contient. C'est la raison du `WITH GRANT OPTION` exigé du plan de contrôle :
il doit pouvoir retransmettre ce droit à l'activateur. Les droits sont retirés
en fin de phase.

### 8.4 `COMMENT ON ROLE` retiré

Commenter un rôle exige l'`ADMIN OPTION`. La migration échouait donc sur une
ligne de **documentation**. Les rôles sont par ailleurs des objets de
**cluster** : les commenter depuis une migration de base écrirait dans un
espace partagé par toutes les bases de l'instance.

### 8.5 Rôles de service : déclarations attendues

La phase 1 refuse **par défaut** qu'un rôle connectable atteigne
`normative_backend` ou `normative_governance`. C'est le chemin normal d'un
déploiement Supabase, il doit donc être **déclaré**
(`eurostruct.approved_service_logins`). Une déclaration absente refuse ; elle
n'est jamais déduite.

Deux refus n'ont en revanche **aucun recours** :

- un rôle **privilégié** (`BYPASSRLS`, `CREATEROLE`, `CREATEDB`) qui atteint un
  rôle de service — il contourne déjà la RLS ;
- un rôle **porteur de jeton** qui l'atteint. Quels rôles un JWT endosse n'est
  pas dérivable du catalogue : c'est une convention de déploiement, déclarée
  par `eurostruct.token_roles` (défaut `authenticated,anon`).

## 9. Modèle de menace

Voir `docs/schema/MODELE_DE_MENACE_NORMATIF.md`. En résumé : le migrateur est
fiable pour appliquer un schéma et pour rien d'autre ; le superutilisateur est
**hors modèle**.

## 10. Reste à faire avant toute mise en production

- [ ] Exécuter `nonsuperuser_install.sh` contre une **instance Supabase de
      staging**, et consigner le résultat ici.
- [ ] Vérifier le comportement derrière **PgBouncer** en mode transaction : les
      verrous consultatifs de session et `SET LOCAL ROLE` s'y comportent
      différemment.
- [ ] Confirmer que le schéma `auth` réel de Supabase expose bien `auth.uid()`
      et `auth.users` avec les droits supposés ici.
- [ ] Écrire et exercer la **reprise des données métier** vers un déploiement
      neuf (§6). Sans elle, aucune migration inter-cluster n'est possible.
- [ ] Décider si un cluster doit pouvoir porter **plusieurs bases EUROSTRUCT
      avec des plans de contrôle distincts** (§1) ; si oui, préfixer les six
      rôles canoniques par base.
