# Déployer sur une base hébergée — provisionner, migrer, exécuter

Ce document sépare **trois gestes que la composition locale enchaîne en un
seul**, parce qu'une base hébergée — Supabase ou un autre PostgreSQL managé —
ne les confie pas à la même personne ni au même rôle. Il dit, pour chacun,
**qui** le fait, avec **quels privilèges**, et **ce qui n'est pas requis**.

Il complète [`DEPLOIEMENT_PREREQUIS.md`](DEPLOIEMENT_PREREQUIS.md), qui reste
la référence de la commande officielle et de ses codes de sortie ; il ne le
répète pas.

**Statut : `SUPABASE_UNVERIFIED`.** Rien de ce qui suit n'a été exécuté sur
une instance Supabase réelle. Ce qui a été exécuté est l'**auto-test** de la
recette, sur un PostgreSQL local provisionné comme une base hébergée le
serait — trois rôles non superutilisateurs, aucun accès superutilisateur
pendant la recette. Voir §6.

---

## 1. Trois gestes, trois acteurs

| geste | qui | avec quoi | outil du dépôt |
|---|---|---|---|
| **Provisionner** | l'exploitant, une fois, avec le compte que le fournisseur lui donne | créer trois rôles de connexion, la base, le schéma `auth` (Supabase le fournit), les droits et les réglages du §2 | `deploy/verifier_privileges.sh` constate, en lecture seule, que c'est fait |
| **Migrer** | le **plan de contrôle** et le **migrateur**, deux rôles distincts | `ESC_PLAN_URL`, `ESC_MIGRATOR_URL` | `tools/deploy_eurostruct.sh`, puis `db/seed/0001_ndp.sql` par le migrateur |
| **Exécuter** | l'API, sous le **login applicatif** | `EUROSTRUCT_DATABASE_URL`, `EUROSTRUCT_SUPABASE_*` | `uvicorn eurostruct_api.app:app` — ou l'image `api/Dockerfile` |

La composition locale (`compose.yaml`) fait les trois dans `init`, avec le
superutilisateur de l'image PostgreSQL pour le premier. **C'est le seul endroit
où un superutilisateur intervient**, et il n'existe pas sur une base hébergée.

### Ce que les harnais font, et qu'il ne faut pas transposer

Les harnais de `db/test/` créent leur migrateur avec `createrole createdb`,
prennent un superutilisateur pour poser le décor, et détruisent tout à la
sortie. Ce sont des commodités de cluster jetable. **Aucune n'est une exigence
du produit** :

* le migrateur n'a pas besoin de `createrole` ni de `createdb` : il lui faut
  être **propriétaire de la base** (ce qui lui donne `CREATE` sur `public`
  depuis PostgreSQL 15) et détenir les droits du §2 ;
* le login applicatif n'a besoin d'**aucun** privilège global — ni
  `createrole`, ni `createdb`, ni `bypassrls`, et surtout pas superutilisateur,
  pour qui RLS ne s'applique pas. Il atteint les primitives `SECURITY DEFINER`
  par sa seule appartenance à `eurostruct_authority_backend`, accordée après
  le déploiement.

`deploy/verifier_privileges.sh` marque ces attributs **interdits** sur le login
applicatif, et **sans objet** sur le migrateur.

---

## 2. Provisionner : ce que l'exploitant fait une fois

Le SQL de référence est au §2 de `DEPLOIEMENT_PREREQUIS.md`. Ce qui s'y ajoute
pour une base hébergée :

* le schéma `auth`, `auth.users` et `auth.uid()` sont **fournis** par Supabase.
  `EUROSTRUCT_LOCAL_AUTH_STUB` reste à `non` — le poser à `oui` créerait un
  schéma fictif par-dessus le vrai ;
* les quatre réglages de base (`eurostruct.approved_deployment_roles`,
  `token_roles`, `approved_service_logins`, `authority_backend_logins`) se
  posent par `ALTER DATABASE … SET` — ce qui exige d'être propriétaire de la
  base ou de disposer du compte administrateur du fournisseur ;
* le **mandat d'amorçage** (`eurostruct.bootstrap_mandate`) se pose de la
  même façon. Sans lui, aucune racine d'autorité n'est amorcée, et c'est le
  comportement correct : désigner la première personne habilitée est une
  décision, pas un démarrage.

Vérifier avant d'aller plus loin, sans rien modifier :

```
ESC_PLAN_URL='postgresql://plan:…@hote:5432/base?sslmode=verify-full' \
ESC_MIGRATOR_URL='postgresql://migrateur:…@hote:5432/base?sslmode=verify-full' \
EUROSTRUCT_DATABASE_URL='postgresql://app:…@hote:5432/base?sslmode=verify-full' \
deploy/verifier_privileges.sh
```

Le script rend une ligne par exigence, avec `requis` / `interdit` / `souhaité`
et ce qui est **constaté** — et « sans objet » pour ce que les harnais posent
sans que le produit le lise (`createrole`/`createdb` sur le migrateur, `CREATE`
sur la base pour le plan de contrôle). Les lignes « souhaité » (appartenance à
`eurostruct_deployment`, à `eurostruct_authority_backend`) ne peuvent être
satisfaites qu'après la phase 0 : elles ne font pas échouer avant.

---

## 3. Migrer : la commande officielle, puis le référentiel

```
tools/deploy_eurostruct.sh            # dix étapes, postconditions vérifiées
psql -f db/seed/0001_ndp.sql          # par le MIGRATEUR, idempotent
```

**Le seed fait partie du déploiement.** Mesuré le 16/09 en suivant la
procédure de démonstration : la base sortait `ACTIVE`, l'API répondait, la
session s'ouvrait — et la création d'un projet belge rendait 422, « aucune
annexe nationale en vigueur pour BE ». `db/seed/0001_ndp.sql` n'était appliqué
que par la campagne de tests. Il l'est désormais par `deploy/initialiser.sh`
(composition) et par l'étape 1 de la recette (base hébergée).

Ce qu'il pose : le **miroir informatif** des annexes et de leurs paramètres,
tous en `pending_verification`. Il n'écrit jamais `confirmed` ; le moteur lit
les JSON du dépôt, et les confirmations viennent de la base par le quatre-yeux.

Après la commande, et seulement après — les rôles n'existent pas avant la
phase 0 :

```sql
GRANT eurostruct_deployment       TO plan WITH INHERIT TRUE;   -- si non déjà tenu
GRANT eurostruct_authority_backend TO app;
```

---

## 4. Exécuter : l'API sous le login applicatif

L'API ne lit que l'environnement. Ce qu'elle exige dépend du **scénario**, et
un scénario ne doit jamais réclamer ce dont il ne se sert pas. Sur
l'hébergement cible, c'est `compose.staging.yaml` qui porte les deux images
avec cet environnement, et `deploy/staging.sh` qui enchaîne les trois gestes
de ce document dans l'ordre — voir [`STAGING.md`](STAGING.md).

### Secrets, valeurs publiques, choix de configuration

| variable | nature | scénario | usage précis |
|---|---|---|---|
| `EUROSTRUCT_DATABASE_URL` | **secret** | toujours | la DSN du login applicatif ; jamais celle du migrateur ni d'un superutilisateur |
| `EUROSTRUCT_SUPABASE_JWKS_URL` | publique | toujours | d'où l'API lit les clés de vérification |
| `EUROSTRUCT_SUPABASE_ISSUER` | publique | toujours | la chaîne `iss` que chaque jeton doit porter |
| `EUROSTRUCT_SUPABASE_AUDIENCE` | publique | toujours | `authenticated` sur un projet Supabase standard |
| `EUROSTRUCT_JWT_ALGORITHMS` | choix | toujours | asymétriques seulement ; `HS256` est refusé par la configuration |
| `EUROSTRUCT_CORS_ORIGINS` | choix | toujours | les origines de l'interface, une à une ; `*` est refusé |
| `EUROSTRUCT_BUILD_SHA` | publique | toujours | l'identité du code qui a produit chaque calcul conservé ; sans elle, l'API sert l'exploratoire et refuse d'enregistrer |
| `EUROSTRUCT_ENVIRONNEMENT` | choix | démonstration | `demonstration` fait dire à l'instance ce qu'elle est ; vide sinon |
| `EUROSTRUCT_STORAGE_BACKEND` | choix | toujours | `local` ou `s3` — décide de ce qui suit |
| `EUROSTRUCT_STORAGE_DIR` | choix | `local` | le répertoire des livrables ; un volume, jamais `/tmp` |
| `EUROSTRUCT_S3_ENDPOINT`, `_REGION`, `_BUCKET`, `_PREFIX`, `_PATH_STYLE` | publique / choix | `s3` seulement | où et comment joindre le compartiment |
| `EUROSTRUCT_S3_ACCESS_KEY_ID`, `EUROSTRUCT_S3_SECRET_ACCESS_KEY` | **secret** | `s3` seulement | **jamais requis en `local`** |
| `EUROSTRUCT_S3_VERIFY_TLS`, `_CA_BUNDLE`, `_SSE`, `_SSE_KMS_KEY_ID` | choix | `s3` seulement | TLS et chiffrement au repos, selon le fournisseur |

Pour l'**interface**, trois valeurs publiques par nature, lues à chaque
requête et jamais figées dans l'image : `EUROSTRUCT_API_URL`,
`EUROSTRUCT_SUPABASE_URL`, `EUROSTRUCT_SUPABASE_ANON_KEY` — et
`EUROSTRUCT_ENVIRONNEMENT` pour le bandeau de démonstration.

### Ce que « sauvegarde » veut dire sur une base hébergée

Les tables de confiance sont sous RLS **forcée** : leur propriétaire même y est
soumis, et `pg_dump` **refuse** plutôt que de rendre une sauvegarde partielle.
Seul un rôle doté de `BYPASSRLS` par le fournisseur peut sauvegarder — c'est
le rôle du fournisseur, pas l'un des trois du produit. La recette le nomme
explicitement (`EUROSTRUCT_STAGING_BACKUP_URL`) et, sans lui, rend l'étape 6
**échouée avec cette raison** au lieu d'un faux vert. La sauvegarde complète
d'une base hébergée est celle de son fournisseur.

La même chose vaut pour **relire une copie restaurée** : la restauration pose
les politiques avec les tables, et le rôle qui a restauré — propriétaire de la
copie, avec `--no-owner` — y reste soumis. Vérifier que la copie porte le
contenu de la source exige donc un lecteur qui contourne RLS
(`EUROSTRUCT_STAGING_RESTORE_URL` : le rôle du fournisseur sur une base vide).
Sans lui, la recette ne restaure pas et le dit.

---

## 5. La recette, étape par étape

`db/test/recette_supabase_staging.sh` enchaîne sept étapes et rend pour chacune
**EXECUTEE**, **ECHOUEE** ou **NON EXECUTEE**, avec la raison. Le code de sortie
suit : `0` complète, `1` une étape a échoué, `5` partielle, `2` refusée (pas de
consentement), `4` non exécutable.

| étape | ce qu'elle établit | ce qu'elle exige |
|---|---|---|
| 0 plan de contrôle | les quatre capacités de `supabase_probe.sh` | `ESC_PLAN_URL` |
| 1 migrations | base `ACTIVE`, référentiel des annexes posé | `ESC_MIGRATOR_URL` |
| 2 authentification | l'API locale, contre la base hébergée, `/ready` vert | `EUROSTRUCT_DATABASE_URL`, `EUROSTRUCT_SUPABASE_*` |
| 3 quatre-yeux | un paramètre proposé par A, relu, approuvé et consommé par B ; A ne peut pas s'approuver | `EUROSTRUCT_STAGING_JETON_A`, `_B` **et** `EUROSTRUCT_RECETTE_JETONS_D_ESSAI=oui` |
| 4 étude belge | stricte : refus ou aboutissement **cohérent** avec la couverture ; exploratoire : 201 | jeton A |
| 5 livrables | PDF et DXF créés, téléchargés, empreintes concordantes | jeton A ; stockage du scénario |
| 6 sauvegarde | `pg_dump` par le rôle de sauvegarde ; `pg_restore` vers une base **vide** distincte, par un rôle qui **contourne RLS** (`BYPASSRLS` ou superutilisateur — sur Supabase, celui du fournisseur) ; puis `db/test/comparer_contenu.sh` : pour neuf tables essentielles (`organizations`, `projects`, `calculations`, `results`, `deliverables`, `national_annexes`, `normative_authorisation_grants`, `normative_authority_decisions`, `normative_rule_confirmations`), une **empreinte de toutes les lignes** — rendues en texte sous des réglages de session fixés, triées, hachées — identique entre la source et la copie. Une valeur modifiée à nombre de lignes égal la change ; un compte de lignes, exact ou estimé, ne la verrait pas. Les politiques du produit restent posées sur la copie : c'est le lecteur qui est privilégié, par attribut, et le script refuse un lecteur qui ne l'est pas plutôt que de comparer deux vues partielles. Au moins une ligne, sinon rien n'est prouvé. **Si le rôle de restauration ne contourne pas RLS** : la sauvegarde est faite, la restauration et la vérification ne sont pas tentées, l'étape est NON EXECUTEE avec le nom du rôle, et le verdict est PARTIELLE | `EUROSTRUCT_STAGING_BACKUP_URL`, `EUROSTRUCT_STAGING_RESTORE_URL` |
| 7 redémarrage | l'API redémarrée relit l'étude, même empreinte | jeton A |

Le mode `diagnostic` (défaut) **ne mute rien** : attributs du rôle, `--dry-run`
de la commande, JWKS. Il rend `0` quand tous les accès sont là, `4` sinon, avec
la liste. L'étape 3 exige de déclarer que les jetons sont ceux de **comptes
d'essai** : elle consomme une décision réelle sur le staging.

---

## 6. Ce qui a été exécuté, et ce qui ne l'a pas été

**Exécuté** — `db/test/recette_supabase_staging_selftest.sh`, sur le cluster
PostgreSQL local et jetable de la campagne, avec un provisionnement fait comme
au §2 et **aucun superutilisateur pendant la recette** :

* diagnostic avec tous les accès : instantané du catalogue identique avant et
  après ; `executer` sans consentement : idem, code 2 ;
* `executer` sans jetons, avec un rôle de restauration qui ne contourne pas
  RLS : étapes 0, 1, 2 exécutées, 3 à 7 non exécutées avec leur raison —
  l'étape 6 nomme le rôle et `BYPASSRLS`, et aucune restauration n'est
  tentée — code 5 ;
* `executer` avec deux comptes d'essai et le rôle de sauvegarde du
  « fournisseur » sur une base vide : sept étapes exécutées, code 0 ; une
  décision consommée, une étude enregistrée, deux livrables, et le contenu de
  la copie identique à la source, table par table ;
* falsification de la preuve de restauration : une valeur modifiée sur la
  copie, à nombre de lignes égal, est détectée et la table nommée ; un lecteur
  soumis à RLS est refusé, avec le motif ;
* une DSN de sauvegarde factice et un échec provoqué de `pg_dump` : l'étape 6
  est ECHOUEE, et aucune sortie — de ce scénario ni d'aucun autre — ne porte
  un identifiant, un mot de passe ou une DSN.

L'auto-test a d'abord été rouge, et chaque rouge nommait un défaut réel de la
recette ou de son harnais — pas de l'instance :

* le message d'échec de `pg_dump` composait « le rôle de sauvegarde » avec
  `${VAR:-le migrateur}`, qui — la variable étant définie — développait la
  **DSN entière, mot de passe compris**. Le libellé est fixe, les fragments
  d'erreur repris de `pg_dump` sont masqués, et l'auto-test balaie toutes les
  sorties ;
* la première preuve de restauration comparait des comptes de lignes, dont
  `n_live_tup` — une **statistique**, pas une lecture. Remplacée par
  l'empreinte de contenu du §5, ligne 6 ;

* `psql -c` n'interpole pas les variables : l'admission du login applicatif
  dans `eurostruct_authority_backend` (`:"app"`) échouait en silence sur une
  erreur de syntaxe. Elle passe par l'entrée standard, et son erreur est
  rapportée ;
* l'amorçage de la racine était tenté **avant** l'insertion du principal dans
  `auth.users`, que `grantee_id` référence : refusé par la clé étrangère ;
* le rôle qui restaure est propriétaire de la copie et pourtant soumis à la
  RLS **forcée** : son `count(*)` rendait « 1 avant, 0 après » sur une
  restauration correcte — et « 0 = 0 » passait quand rien n'existait encore.
  D'où la comparaison du §5, ligne 6 ;
* `deploy/verifier_privileges.sh` exigeait du plan de contrôle `CREATE` sur la
  base, qu'aucun chemin du produit ne lit (la phase 0 ne crée aucun schéma) :
  la ligne est désormais « sans objet », comme `createrole`/`createdb` sur le
  migrateur.

**Non exécuté** — tout ce qui précède, sur une instance Supabase réelle. Ce
qui l'empêche est nommé par le diagnostic : les trois DSN, l'URL du JWKS et
l'émetteur du projet, deux comptes d'essai, une cible de restauration. Le
blocage le plus probable une fois ces accès fournis n'est pas un secret mais
un **droit** : le plan de contrôle a-t-il `CREATEROLE` sur cette instance ?
C'est la première question, et `supabase_probe.sh` y répond avant tout le
reste.

---

## 7. Deux constats faits en suivant la procédure

* **`minio/minio:RELEASE.2025-09-07T16-13-09Z` n'est pas résoluble** depuis
  l'environnement où la procédure a été suivie — ni aucune étiquette de ce
  dépôt, ni `quay.io/minio`. Le magasin objet reste dans `compose.yaml` ; la
  démonstration l'écarte par profil et écrit sur le volume `livrables`, ce qui
  est exactement le scénario `local`. Sur un poste avec accès ordinaire au
  registre, `--profile objets` le rend.
* **Le référentiel des annexes n'était appliqué par aucun chemin de
  déploiement** (§3). Corrigé dans `initialiser.sh` et dans la recette.
