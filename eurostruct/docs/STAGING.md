# Mise à disposition sur staging — base hébergée, authentification réelle

Ce document dit **ce qui est prêt** pour installer EUROSTRUCT sur
l'hébergement cible, **ce qui a été répété** ici, et **les seules
informations externes qui manquent** pour l'exécuter pour de vrai. Il
complète [`DEPLOIEMENT_BASE_HEBERGEE.md`](DEPLOIEMENT_BASE_HEBERGEE.md)
(qui provisionne quoi, avec quels droits) et
[`RECETTE_SUPABASE.md`](RECETTE_SUPABASE.md) (la recette en sept étapes) ;
il ne les répète pas.

**Statut : `SUPABASE_UNVERIFIED`.** Aucune commande de ce document n'a
tourné contre une instance Supabase. Ce qui a tourné est la **répétition
locale** du §5 : la même composition, la même commande, la même recette,
contre une base et un émetteur extérieurs à la composition.

---

## 1. Démonstration locale et staging : deux configurations, séparées

| | démonstration (`deploy/demo.sh`) | staging (`deploy/staging.sh`) |
|---|---|---|
| composition | `compose.yaml` + `compose.demo.yaml` | `compose.yaml` + `compose.staging.yaml` |
| base | conteneur `db`, initialisée par `init` | **hébergée** (Supabase) ; `db`, `init`, `objets` sous un profil jamais activé |
| migrations | par `init`, au démarrage | par `deploy/staging.sh migrer`, **avant** `up`, sous deux rôles distincts |
| émetteur de jetons | `demo-auth`, comptes d'essai générés | **Supabase Auth**, comptes réels, JWKS du projet |
| `EUROSTRUCT_ENVIRONNEMENT` | `demonstration` (bandeau, `/health`) | **vide** |
| adresses | boucle locale, http | **https publiques**, servies par le mandataire TLS de l'hôte ; conteneurs sur la boucle locale |
| livrables | volume `livrables` | volume `livrables` (`local`) ou compartiment S3 du fournisseur (`s3`) |
| secrets | générés dans `deploy/demo.env` | **renseignés** par l'exploitant dans `deploy/staging.env` (0600, ignoré par Git) |
| nom Docker | `eurostruct-demo` | `eurostruct-staging` |

Rien n'est généré côté staging : chaque valeur est une information externe.
La surcouche refuse de monter si l'une des valeurs marquées `:?` manque
(`docker compose config` le dit, variable par variable).

## 2. Les seules informations externes encore nécessaires

Tout le reste est dans le dépôt. Ces valeurs se renseignent dans
`deploy/staging.env` (copie de `deploy/staging.env.example`, `chmod 600`) :

| variable | nature | où la prendre |
|---|---|---|
| `ESC_PLAN_URL` | secret | DSN du **plan de contrôle** : Supabase → Project Settings → Database → Connection string, avec le rôle `plan` provisionné selon `DEPLOIEMENT_BASE_HEBERGEE.md` §2 ; `sslmode=verify-full` (ou `require`) |
| `ESC_MIGRATOR_URL` | secret | DSN du **migrateur**, propriétaire de la base |
| `EUROSTRUCT_DATABASE_URL` | secret | DSN du **login applicatif** (ni createrole, ni createdb, ni bypassrls) |
| `EUROSTRUCT_SUPABASE_JWKS_URL` | publique | `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| `EUROSTRUCT_SUPABASE_ISSUER` | publique | `https://<ref>.supabase.co/auth/v1` |
| `EUROSTRUCT_PUBLIC_SUPABASE_URL` | publique | `https://<ref>.supabase.co` |
| `EUROSTRUCT_PUBLIC_SUPABASE_ANON_KEY` | publique | Project Settings → API → clé `anon` (jamais `service_role`) |
| `EUROSTRUCT_PUBLIC_API_URL`, `EUROSTRUCT_PUBLIC_WEB_URL` | publiques | les deux URL https que le mandataire de l'hôte sert, vers `127.0.0.1:8000` et `127.0.0.1:3000` |

Et deux conditions qui ne sont pas des variables :

* **les clés de signature du projet Supabase sont asymétriques** (Project
  Settings → JWT Keys → *JWT signing keys*, RSA ou P-256). L'API refuse
  HS256 ; `EUROSTRUCT_JWT_ALGORITHMS` vaut `RS256` ou `ES256` selon la clé,
  et `prerequis` lit le JWKS pour comparer ;
* **le plan de contrôle a `CREATEROLE`** sur l'instance, et le migrateur est
  **propriétaire** de la base : c'est la première question, et
  `deploy/staging.sh privileges` y répond sans rien modifier.

Facultatif : un mandat d'amorçage (`EUROSTRUCT_BOOTSTRAP_ACTOR`, uuid d'un
compte réel de Supabase Auth, et `_MANDATE`) pour poser la racine
d'autorité ; deux comptes d'essai et leurs jetons pour la recette (§F du
gabarit) ; les DSN de sauvegarde et de restauration pour son étape 6.

## 3. La commande suivante, puis les autres, dans l'ordre

```bash
cp deploy/staging.env.example deploy/staging.env && chmod 600 deploy/staging.env
# remplir le §2, puis :
deploy/staging.sh prerequis                                   # ne lance rien ; nomme ce qui manque
deploy/staging.sh privileges                                  # lecture seule sur la base hébergée
EUROSTRUCT_STAGING_CIBLE=staging deploy/staging.sh migrer     # sceau, migrations, référentiel, admission, racine si mandat
deploy/staging.sh up                                          # images api et web, boucle locale
deploy/staging.sh status                                      # /ready local, puis les URL publiques
deploy/staging.sh recette diagnostic                          # puis « executer », avec des comptes d'essai
```

`prerequis` vérifie l'hôte (Docker, Compose ≥ 2.24, `psql`), les neuf
variables, trois rôles distincts, le TLS des DSN, le https des URL, l'origine
CORS, le stockage, et **joint le JWKS** pour compter les clés compatibles avec
l'algorithme déclaré. `migrer` exige `EUROSTRUCT_STAGING_CIBLE=staging`
parce qu'il écrit ; chacun de ses pas est idempotent. `up` refuse un arbre
de travail modifié (un staging sert un commit) sauf
`EUROSTRUCT_STAGING_ARBRE_MODIFIE=oui`.

Le mandataire TLS (nginx, Caddy, Traefik) est celui de l'hôte et n'est pas
dans ce dépôt : il termine TLS sur `EUROSTRUCT_PUBLIC_WEB_URL` →
`127.0.0.1:3000` et `EUROSTRUCT_PUBLIC_API_URL` → `127.0.0.1:8000`. La
sauvegarde de la base est celle du fournisseur (rôle `BYPASSRLS`,
`DEPLOIEMENT_BASE_HEBERGEE.md` §4) ; celle des livrables en `local` est celle
du volume `eurostruct-staging_livrables` de l'hôte.

## 4. Ce que `migrer` fait, et ce qu'il ne fait pas

1. `tools/deploy_eurostruct.sh` (sceau, migrations, activation) avec
   `ESC_PLAN_URL` et `ESC_MIGRATOR_URL` ; l'état doit être `ACTIVE` ;
2. `db/seed/0001_ndp.sql` par le migrateur : le référentiel des annexes,
   tout en `pending_verification` — jamais `confirmed` ;
3. `grant eurostruct_authority_backend` au login applicatif, par le plan de
   contrôle ;
4. si un mandat est déclaré : il **constate** que la base porte ce mandat
   (`eurostruct.bootstrap_mandate`, posé par le compte administrateur du
   fournisseur — un rôle ordinaire, même propriétaire, ne peut pas poser un
   paramètre `eurostruct.*`, mesuré) et que l'acteur existe dans
   `auth.users` (ce que seul Supabase Auth fait), puis appelle
   `bootstrap_normative_administrator` par le plan de contrôle ; la
   primitive dit elle-même si une racine existe déjà. Un mandat absent ou
   différent, ou un acteur inconnu : pas NON EXÉCUTÉ, nommé avec la ligne
   SQL à faire exécuter, code 5.

Il ne crée aucun rôle de connexion, ne touche pas au schéma `auth`, ne pose
aucune confirmation de paramètre national, et n'écrit aucun secret.

## 5. Ce qui a été répété ici, et comment

`deploy/staging_repetition.sh` rejoue la procédure du §3 sur un cluster
PostgreSQL local **jetable** (prouvé tel par `db/test/lib_harnais.sh`),
provisionné comme au §2 de `DEPLOIEMENT_BASE_HEBERGEE.md` et **joint par les
conteneurs à travers le pont Docker** (`172.17.0.1`), avec l'émetteur de
jetons des parcours navigateur lancé **hors de la composition**. Onze pas,
chacun EXÉCUTÉ / ÉCHOUÉ / NON EXÉCUTÉ, et une postcondition de nettoyage
vérifiée nom par nom.

**Résultat (16/09, cinquième exécution : TENUE, code 0)** — PostgreSQL 16
local jetable, Docker 29.3.1, Compose 5.1.1, Ubuntu 24.04.4, sur l'arbre de
travail du commit qui porte ce document :

| pas | résultat |
|---|---|
| 0 base joignable des conteneurs | EXÉCUTÉ — `pg_isready` depuis un conteneur `postgres:16` vers `172.17.0.1:5432` |
| 1 provisionnement (exploitant) | EXÉCUTÉ — quatre rôles (plan, migrateur, applicatif, sauvegarde `BYPASSRLS`), deux bases, schéma `auth` fictif, réglages, **mandat posé par l'administrateur**, trois comptes dans `auth.users` ; base jointe de l'hôte par l'adresse du pont |
| 2 émetteur extérieur | EXÉCUTÉ — JWKS servi sur `127.0.0.1` et sur l'adresse du pont |
| 3 `prerequis` | EXÉCUTÉ — aucun MANQUE ; JWKS lu : 1 clé RSA, RS256 |
| 4 `privileges` | EXÉCUTÉ — aucun MANQUE sur un provisionnement conforme |
| 5 `migrer` | EXÉCUTÉ — base `ACTIVE`, 4 annexes, login admis, racine amorcée (1 habilitation, vérifiée hors du produit) |
| 6 `up` | EXÉCUTÉ — images api et web construites, base et JWKS extérieurs |
| 7 `status` | EXÉCUTÉ — `/ready` vert, 200 sur les deux URL « publiques » |
| 8 parcours par l'API des conteneurs | EXÉCUTÉ — bureau, projet, étude exploratoire `passed`, note PDF téléchargée avec l'empreinte enregistrée, objet présent sur le volume `livrables`, `/health` sans « demonstration » |
| 9 recette de bout en bout | EXÉCUTÉ — sept étapes EXÉCUTÉES, verdict COMPLÈTE : quatre-yeux (A propose, ne s'approuve pas, B relit, approuve et consomme), étude stricte 422 puis exploratoire 201, PDF et DXF, sauvegarde et restauration au **contenu identique**, relecture après redémarrage |
| 10 `down` | EXÉCUTÉ |

Postcondition de nettoyage vérifiée : aucun rôle, aucune base, aucun
conteneur, aucun volume résiduels.

Les quatre exécutions rouges qui ont précédé nommaient chacune un défaut du
harnais ou de la procédure, corrigé avant la cinquième :

* une valeur non citée dans l'env généré arrêtait bash à mi-fichier, et tout
  ce qui suivait restait vide — les guillemets sont exigés, et `staging.sh`
  refuse un env qu'il ne peut pas lire ;
* le bilan perdait ses pas joués dans un tube (sous-shell) ;
* le contrôle du JWKS déclarait « injoignable » un JWKS bien servi — l'analyse
  en une ligne était fautive ; lecture et analyse sont deux pas ;
* l'hôte joignait la base par l'adresse du pont avec une **adresse source**
  inattendue, sans entrée `pg_hba` — le harnais la nomme et donne la ligne ;
* `migrer` posait le mandat par le migrateur : « permission denied to set
  parameter » — un paramètre `eurostruct.*` se pose par l'administrateur ; et
  il déduisait « déjà amorcée » d'un compte que le plan de contrôle ne peut
  pas lire sous RLS forcée — il constate le mandat et laisse la primitive
  répondre ;
* la recette refusait la proposition de A : les comptes d'essai n'étaient
  pas habilités — le harnais pose leurs habilitations depuis la racine, comme
  `demo.sh` le fait, et le dit comme un geste de provisionnement.

**Ce que cela n'établit pas.** Les rôles, le JWKS, le réseau et les
politiques d'une instance Supabase réelle ; le mandataire TLS ; un
compartiment S3 du fournisseur. Le blocage le plus probable une fois les
accès fournis n'est pas un secret mais un **droit** (`CREATEROLE` du plan de
contrôle) — `privileges` le dit avant tout le reste.
