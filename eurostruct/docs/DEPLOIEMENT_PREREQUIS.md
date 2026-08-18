# EUROSTRUCT — prérequis de déploiement de la chaîne normative

> **État de la vérification.** Ce document décrit ce qu'un déploiement doit
> fournir pour que les migrations `0000` à `0010` s'appliquent et que la chaîne
> de confiance normative fonctionne. Les prérequis listés ne sont pas déduits
> d'une lecture du code : chacun a été **rencontré** par
> `db/test/nonsuperuser_install.sh`, qui applique les migrations sous un rôle
> de migration non superutilisateur.

## 0. Trois phases, et **deux acteurs distincts** (6.3b6c)

Le déploiement n'est plus « appliquer les migrations ». Il a **trois phases**,
et les deux premières sont exercées par **deux rôles différents** :

| Phase | Fichier | Exercée par | Ce qu'elle fait |
|---|---|---|---|
| **0** | `db/migrations/0000_sceau_normatif.sql` | **plan de contrôle** | crée les six rôles canoniques et la **racine de confiance** — les quatre tables de confiance et les fonctions qui les écrivent, possédées par `eurostruct_normative_activator` |
| **1** | `0001` … `0010` | **migrateur** | applique le schéma applicatif ; termine en `PENDING` |
| **2** | `select normative_finalize_deployment(<manifeste>)` | **plan de contrôle** | compare le manifeste, restitue les emprunts, inscrit l'activation → `ACTIVE` |

### Pourquoi deux rôles, et pas un

PostgreSQL n'accepte `ALTER FUNCTION … OWNER TO r` que si le rôle courant peut
faire `SET ROLE r`. La phase 1 doit donc pouvoir **endosser** les rôles dont
elle rend ses fonctions propriétaires. Tant que la racine de confiance
appartenait à un rôle emprunté par le migrateur, elle était **à sa portée** :
un `SET ROLE` puis un `insert` suffisaient à rendre l'état `ACTIVE` sans
finalisation. C'est mesuré, et c'est la raison d'être de la phase 0.

Un déploiement où **un seul** rôle privilégié existe s'installe (phase 1) mais
**ne se finalise pas** : la phase 2 refuse en nommant la séparation manquante.
Ce n'est pas une dégradation silencieuse, c'est un refus.

Voir `docs/schema/MODELE_DE_MENACE_NORMATIF.md`.

### Ce que le plan de contrôle doit détenir

En plus d'être un rôle **distinct** du migrateur et **non superutilisateur** :

| Droit | Pourquoi |
|---|---|
| `CREATE` sur la base | il y crée les tables de confiance |
| `CREATE` sur le schéma `public` **`WITH GRANT OPTION`** | il doit **retransmettre** ce droit à `eurostruct_normative_activator`, qui devient propriétaire de ces objets — PostgreSQL l'exige du nouveau propriétaire |
| `USAGE` sur le schéma `auth` | les fonctions scellées le référencent |
| `CREATEROLE` | il crée les six rôles canoniques |
| `eurostruct_deployment` (accordé **après** la phase 0) | c'est ce rôle qui porte `EXECUTE` sur la finalisation |

Il conserve, après la phase 0, un **ADMIN résiduel** irrévocable sur les rôles
qu'il a créés — fait `F1` de PostgreSQL 16. C'est la seule exemption du modèle,
et elle est figée à l'installation par **OID et par nom**.

### Si le plan de contrôle est un superutilisateur

C'est légitime — forme auto-hébergée — mais la phase 0 émet alors un `notice`
explicite : le sceau est posé, il ne contient pas celui qui l'a posé, et aucun
sceau ne le peut. `pg_has_role(superutilisateur, …, 'SET')` rend `true` quoi
qu'il arrive. Le superutilisateur est **hors modèle de menace**.

## 1. Ce qui est vérifié, et ce qui ne l'est pas

La distinction est la raison d'être de ce document.

| Question | État |
|---|---|
| Les migrations s'appliquent sous un rôle **non superutilisateur** | **Vérifié** en CI |
| Le rôle de migration n'a **ni `SUPERUSER` ni `BYPASSRLS`** | **Vérifié** en CI |
| La RLS s'applique réellement (pas contournée par un superutilisateur) | **Vérifié** en CI |
| Amorçage, octroi, confirmation, révocation sous les rôles réels | **Vérifié** en CI |
| Compatibilité **Supabase** | **NON vérifié** |

### Pourquoi la compatibilité Supabase n'est pas acquise

`db/test/nonsuperuser_install.sh` reproduit le **modèle de privilèges** de
Supabase — rôle de migration avec `CREATEROLE` et `CREATEDB` mais sans
`SUPERUSER`, schéma `auth` qui ne lui appartient pas, rôles applicatifs
`NOLOGIN` endossés par un rôle connectable — sur un PostgreSQL 16 ordinaire.

Il ne reproduit **pas** : les extensions préinstallées de Supabase, ses
politiques par défaut, PgBouncer, ses *event triggers*, ni le contenu réel de
son schéma `auth`.

Une exécution en CI, même sous un rôle non superutilisateur, ne peut donc pas
établir la compatibilité Supabase. Elle sera établie par une exécution sur une
**instance de staging réelle**, et pas avant. Jusque-là, la mention
« compatible Supabase » ne doit apparaître nulle part.

## 2. Les prérequis, et l'obstacle qui les a révélés

Chacun de ces points a fait **échouer** la migration sous un rôle non
superutilisateur. Aucun n'était visible en CI superutilisateur.

### 2.1 `REFERENCES` sur `auth.users`

Le schéma déclare des clés étrangères vers `auth.users`. PostgreSQL exige
`REFERENCES`, et non `SELECT`, pour en créer une.

```sql
GRANT USAGE ON SCHEMA auth TO <migrateur>;
GRANT SELECT, REFERENCES ON auth.users TO <migrateur>;
```

### 2.2 `GRANT OPTION` sur les objets de `auth`

La migration **retransmet** l'accès à `auth` aux rôles d'autorité. Sans
`GRANT OPTION`, PostgreSQL **n'échoue pas** : il émet un simple *warning* et
n'accorde rien. La chaîne casse alors bien plus tard, à la première
confirmation, sur un `permission denied for schema auth` que rien ne relie à sa
cause.

La migration vérifie désormais le résultat de ses propres `GRANT` et refuse si
la retransmission n'a pas eu lieu.

```sql
GRANT USAGE ON SCHEMA auth TO <migrateur> WITH GRANT OPTION;
GRANT SELECT ON auth.users TO <migrateur> WITH GRANT OPTION;
GRANT EXECUTE ON FUNCTION auth.uid() TO <migrateur> WITH GRANT OPTION;
```

### 2.3 `ADMIN OPTION` sur les rôles d'autorité, s'ils préexistent

`ALTER FUNCTION … OWNER TO r` exige d'être **membre** de `r`. La migration
emprunte donc temporairement l'appartenance aux deux rôles d'autorité, puis la
**rend** avant la fin du fichier — et vérifie qu'elle l'a rendue.

Si la migration crée elle-même ces rôles, PostgreSQL 16 lui donne l'`ADMIN
OPTION` automatiquement et il n'y a rien à faire. S'ils **préexistent**, créés
par un tiers, le déploiement doit l'accorder :

```sql
GRANT eurostruct_normative_writer     TO <migrateur> WITH ADMIN OPTION;
GRANT eurostruct_normative_bootstrap  TO <migrateur> WITH ADMIN OPTION;
```

> **À retirer après la migration.** La migration ne rend que ce qu'elle a
> emprunté : une appartenance accordée par le déploiement n'est pas retirée par
> elle, et sa dernière étape émet un `WARNING` le rappelant. Tant que le
> migrateur reste membre, `current_user` cesse d'être une preuve d'origine.
>
> ```sql
> REVOKE eurostruct_normative_writer, eurostruct_normative_bootstrap
>   FROM <migrateur>;
> ```

### 2.4 `CREATE` sur le schéma `public`

Depuis PostgreSQL 15, `public` n'accorde plus `CREATE` à `PUBLIC`. Or le
**nouveau propriétaire** d'une fonction doit avoir `CREATE` sur le schéma qui
la contient. La migration accorde donc ce droit aux rôles d'autorité
elle-même — ils sont `NOLOGIN` et sans aucun membre, personne ne peut s'en
servir.

Rien à faire côté déploiement ; le point est documenté parce que l'octroi est
visible dans la migration et pourrait surprendre.

### 2.5 `COMMENT ON ROLE` retiré

Commenter un rôle exige l'`ADMIN OPTION`. La migration échouait donc sur une
ligne de **documentation**. Les rôles sont par ailleurs des objets de
**cluster** : les commenter depuis une migration de base écrirait dans un
espace partagé par toutes les bases de l'instance.

## 3. Le rôle de déploiement

L'amorçage n'est pas exécutable par un rôle applicatif. Il est réservé à un
rôle **nommé**, auquel le déploiement rattache son rôle de migration :

```sql
GRANT eurostruct_deployment TO <migrateur>;
```

`eurostruct_deployment` reçoit `EXECUTE` sur
`bootstrap_normative_administrator()` et **rien d'autre**. Il n'est membre
d'aucun rôle d'autorité, et les prérequis de la migration refusent l'installation
s'il le devenait. Il peut donc **ouvrir** la chaîne de confiance — une fois, un
index d'unicité y veille — sans pouvoir fabriquer une trace normative ni
emprunter la branche `bootstrap` d'une insertion brute.

Ouvrir la chaîne et forger une preuve restent deux pouvoirs distincts.

## 4. Rôles de service : déclarations attendues

La migration refuse **par défaut** qu'un rôle connectable atteigne
`normative_backend` ou `normative_governance`. C'est le chemin normal d'un
déploiement Supabase (`authenticator` endosse `service_role`), il doit donc être
**déclaré** :

```sql
ALTER DATABASE <base> SET eurostruct.approved_service_logins = 'authenticator';
```

Une déclaration absente refuse ; elle n'est jamais déduite.

Deux refus n'ont en revanche **aucun recours** :

- un rôle **privilégié** (`BYPASSRLS`, `CREATEROLE`, `CREATEDB`) qui atteint un
  rôle de service — il contourne déjà la RLS ;
- un rôle **porteur de jeton** qui l'atteint. Quels rôles un JWT endosse n'est
  pas dérivable du catalogue : c'est une convention de déploiement, déclarée par
  `eurostruct.token_roles` (défaut `authenticated,anon`).

## 5. Modèle de menace

Ces garanties visent les **rôles applicatifs**. Un superutilisateur PostgreSQL
peut désactiver les déclencheurs, changer le propriétaire d'une fonction et
écrire dans les catalogues : ce n'est pas un adversaire que la base peut
contenir, et prétendre le contraire donnerait une fausse assurance.

## 6. Reste à faire avant toute mise en production

- [ ] Exécuter `nonsuperuser_install.sh` contre une **instance Supabase de
      staging**, et consigner le résultat ici.
- [ ] Vérifier le comportement derrière **PgBouncer** en mode transaction : les
      verrous consultatifs de session et `SET LOCAL ROLE` s'y comportent
      différemment.
- [ ] Confirmer que le schéma `auth` réel de Supabase expose bien
      `auth.uid()` et `auth.users` avec les droits supposés ici.
