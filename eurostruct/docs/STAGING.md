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
| adresses | boucle locale, http | **https publiques**, servies par le **mandataire TLS de la composition** (`mandataire`, Caddy, `deploy/Caddyfile`, ports 80 et 443, certificats ACME) — ou par celui de l'hôte si `EUROSTRUCT_MANDATAIRE=non` ; `api` et `web` sur la boucle locale |
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
| `EUROSTRUCT_PUBLIC_API_URL`, `EUROSTRUCT_PUBLIC_WEB_URL` | publiques | **deux noms distincts**, en `https://`, sans port ni chemin (p. ex. `https://api.eurostruct.exemple.org` et `https://eurostruct.exemple.org`) ; le mandataire de la composition les sert sur 80 et 443 |

Et quatre conditions qui ne sont pas des variables :

* **deux enregistrements DNS** (A/AAAA) pour ces deux noms, vers l'adresse
  publique de l'hôte ; `prerequis` vérifie qu'ils se résolvent depuis l'hôte ;
* **les ports 80 et 443 de l'hôte libres et joignables d'Internet** : c'est là
  que Caddy obtient ses certificats (ACME, défi HTTP) et sert les deux noms ;
  `prerequis` vérifie qu'ils sont libres. Si l'hôte a déjà nginx ou Traefik :
  `EUROSTRUCT_MANDATAIRE=non`, et c'est lui qui termine TLS vers
  `127.0.0.1:3000` et `127.0.0.1:8000` ;

* **les clés de signature du projet Supabase sont asymétriques** (Project
  Settings → JWT Keys → *JWT signing keys*, RSA ou P-256). L'API refuse
  HS256 ; `EUROSTRUCT_JWT_ALGORITHMS` vaut `RS256` ou `ES256` selon la clé,
  et `prerequis` lit le JWKS pour comparer ;
* **le plan de contrôle a `CREATEROLE`** sur l'instance, et le migrateur est
  **propriétaire** de la base : c'est la première question, et
  `deploy/staging.sh privileges` y répond sans rien modifier.

Facultatif : un courriel de contact ACME (`EUROSTRUCT_CADDY_TLS="tls
contact@exemple.org"`, qui recevra les avis d'expiration) ; un mandat
d'amorçage (`EUROSTRUCT_BOOTSTRAP_ACTOR`, uuid d'un compte réel de Supabase
Auth, et `_MANDATE`) pour poser la racine d'autorité ; deux comptes d'essai
et leurs jetons pour la recette (§F du gabarit) ; les DSN de sauvegarde et de
restauration pour son étape 6.

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
CORS, le stockage, **joint le JWKS** pour compter les clés compatibles avec
l'algorithme déclaré, puis le mandataire : la forme des deux URL (deux noms,
sans port ni chemin), leur résolution DNS depuis l'hôte, la ligne de
certificat, les ports 80 et 443. `migrer` exige
`EUROSTRUCT_STAGING_CIBLE=staging` parce qu'il écrit ; chacun de ses pas est
idempotent. `up` refuse un arbre de travail modifié (un staging sert un
commit) sauf `EUROSTRUCT_STAGING_ARBRE_MODIFIE=oui` ; il construit les deux
images, monte `api`, `web` et `mandataire`, attend `/ready` sur la boucle
locale, puis **attend les deux URL publiques par le mandataire** — certificat
vérifié, jamais `-k`.

### 3.1 Le mandataire TLS et les contrôles des URL publiques

Le service `mandataire` (`caddy:2.8-alpine`, configuration versionnée dans
`deploy/Caddyfile`) sert `EUROSTRUCT_PUBLIC_WEB_URL` → `web:3000` et
`EUROSTRUCT_PUBLIC_API_URL` → `api:8000` par le réseau de la composition,
redirige http vers https, et obtient ses certificats par ACME (Let's Encrypt,
puis ZeroSSL en repli) sur les ports 80 et 443 de l'hôte. Certificats et
configuration vivent dans deux volumes nommés : un redémarrage ne redemande
rien. Aucune réécriture de chemin, aucun cache, aucun en-tête
d'authentification ajouté : l'API vérifie chaque jeton elle-même.

`deploy/staging.sh status` fait ensuite ce qu'un navigateur ferait, et met
son code de sortie à 1 au premier contrôle raté :

| contrôle | ce qui est attendu |
|---|---|
| `https://<api>/ready` par le nom public | 200, et un JSON qui dit `ready: true` |
| `https://<web>/` | 200, une page HTML, **sans** le bandeau de démonstration |
| CORS : `OPTIONS /v1/projects` avec `Origin: <web>` | `access-control-allow-origin: <web>` — sinon l'écran reste vide à la première requête |
| certificat, sur chaque nom | vérifié par `curl` (autorité, nom) ; émetteur et date d'expiration affichés si `openssl` est là |
| `http://<web>/` | redirection 30x vers https (constat, pas un échec) |

Sur un hôte qui ne résout pas les noms publics ou ne connaît pas l'autorité
(la répétition locale), `EUROSTRUCT_STAGING_RESOLVE` et
`EUROSTRUCT_STAGING_CA_BUNDLE` (§H du gabarit) donnent à `curl` la résolution
forcée et l'autorité locale du mandataire, que `up` copie hors du conteneur.
Vides sur un staging réel.

La sauvegarde de la base est celle du fournisseur (rôle `BYPASSRLS`,
`DEPLOIEMENT_BASE_HEBERGEE.md` §4) ; celle des livrables en `local` est celle
du volume `eurostruct-staging_livrables` de l'hôte ; celle des certificats,
le volume `eurostruct-staging_mandataire_donnees`.

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

### 4 bis. Mettre à jour un staging qui sert déjà

`migrer` **installe** : sur une base déjà en service à qui il manque des
migrations, la commande officielle sort en `ACTIVE_SCHEMA_UPGRADE_REQUIRED`
sans rien appliquer. Mettre à jour est une autre commande :

```bash
deploy/staging.sh diagnostic          # annonce, ne modifie rien

deploy/staging.sh sauvegarder         # si EUROSTRUCT_SAUVEGARDE_URL est déclarée

EUROSTRUCT_STAGING_CIBLE=staging \
ESC_UPGRADE_SAUVEGARDE=<archive ou fournisseur:<texte>> \
  deploy/staging.sh mettre-a-niveau   # construit, arrête, migre, redémarre

deploy/staging.sh reprendre           # si l'opération a été interrompue
```

C'est **la même implémentation** que partout ailleurs :
`tools/deploy_eurostruct.sh --mettre-a-niveau`, décrite en entier dans
`docs/MISE_A_NIVEAU.md`. Ce que `staging.sh` ajoute autour : la construction
des images pendant que le staging sert encore, l'arrêt de l'API et de
l'interface, puis le redémarrage **avec les contrôles publics de `up`**.

Deux différences avec la démonstration, et elles sont voulues :

* **La sauvegarde n'est pas prise à votre place.** La base appartient à un
  hébergeur et l'accès d'administration n'est pas dans `staging.env`. Une
  archive prise par le *migrateur* serait **partielle** — RLS est forcée sur
  les tables d'autorité, et ce qu'il ne lit pas n'entre pas dans le dump, sans
  que rien ne le signale. Déclarez `EUROSTRUCT_SAUVEGARDE_URL` (le compte
  d'administration du fournisseur) pour que `sauvegarder` la prenne, ou
  prenez-la chez l'hébergeur et déclarez-la : `fournisseur:<texte>`.
* **Le magasin d'objets n'est couvert que s'il est local.** En `s3`, les
  octets sont chez le fournisseur : `sauvegarder` le dit et n'archive que la
  base.

## 5. Ce qui a été répété ici, et comment

`deploy/staging_repetition.sh` rejoue la procédure du §3 sur un cluster
PostgreSQL local **jetable** (prouvé tel par `db/test/lib_harnais.sh`),
provisionné comme au §2 de `DEPLOIEMENT_BASE_HEBERGEE.md` et **joint par les
conteneurs à travers le pont Docker** (`172.17.0.1`), avec l'émetteur de
jetons des parcours navigateur lancé **hors de la composition**, et le
**mandataire TLS de la composition** servant deux noms publics —
`staging.localhost` et `api.staging.localhost` — en https sur
`127.0.0.1:443` avec son autorité locale (`tls internal`) : les noms sont
résolus vers la boucle locale par `--resolve`, le certificat est **vérifié**
contre cette autorité, jamais ignoré. Douze pas, chacun EXÉCUTÉ / ÉCHOUÉ /
NON EXÉCUTÉ, et une postcondition de nettoyage vérifiée nom par nom.

**Résultat (17/09, sixième exécution, la première avec le mandataire :
TENUE, code 0)** — PostgreSQL 16 local jetable, Docker 29.3.1, Compose 5.1.1,
Caddy 2.8 (`caddy:2.8-alpine`), Ubuntu 24.04.4, sur l'arbre de travail du
commit qui porte ce document :

| pas | résultat |
|---|---|
| 0 base joignable des conteneurs | EXÉCUTÉ — `pg_isready` depuis un conteneur `postgres:16` vers `172.17.0.1:5432` |
| 1 provisionnement (exploitant) | EXÉCUTÉ — quatre rôles (plan, migrateur, applicatif, sauvegarde `BYPASSRLS`), deux bases, schéma `auth` fictif, réglages, **mandat posé par l'administrateur**, trois comptes dans `auth.users` ; base jointe de l'hôte par l'adresse du pont |
| 2 émetteur extérieur | EXÉCUTÉ — JWKS servi sur `127.0.0.1` et sur l'adresse du pont |
| 3 `prerequis` | EXÉCUTÉ — aucun MANQUE ; JWKS lu : 1 clé RSA, RS256 ; mandataire : Caddyfile présent, autorité locale admise (répétition), deux noms sans port, résolution forcée, ports 80 et 443 libres |
| 4 `privileges` | EXÉCUTÉ — aucun MANQUE sur un provisionnement conforme |
| 5 `migrer` | EXÉCUTÉ — base `ACTIVE`, 4 annexes, login admis, racine amorcée (1 habilitation, vérifiée hors du produit) |
| 6 `up` (mandataire compris) | EXÉCUTÉ — images api et web construites, base et JWKS extérieurs ; autorité locale du mandataire copiée hors du conteneur ; `https://api.staging.localhost/ready` et `https://staging.localhost/` **joints par le mandataire, certificat vérifié** |
| 7 `status` (URL publiques) | EXÉCUTÉ — `/ready` vert sur la boucle locale ; par le mandataire : `/ready` 200 `ready: true`, interface 200 sans bandeau de démonstration, **CORS** : l'API admet `https://staging.localhost`, certificat vérifié sur les deux noms (émetteur « Caddy Local Authority - ECC Intermediate »), `http://staging.localhost/` → **308** vers https |
| 8 parcours par les URL publiques | EXÉCUTÉ — bureau, projet, étude exploratoire `passed`, note PDF téléchargée **par `https://api.staging.localhost`** avec l'empreinte enregistrée, objet présent sur le volume `livrables`, `/health` sans « demonstration » |
| 9 redémarrage : `down`, `up`, relecture | EXÉCUTÉ — aucun conteneur en marche après `down` ; après `up`, l'étude relue par l'URL publique avec **la même empreinte de calcul**, la note PDF retéléchargée **aux mêmes octets**, l'interface servie par le même nom avec un certificat vérifié |
| 10 recette de bout en bout | EXÉCUTÉ — sept étapes EXÉCUTÉES, verdict COMPLÈTE : quatre-yeux (A propose, ne s'approuve pas, B relit, approuve et consomme), étude stricte 422 puis exploratoire 201, PDF et DXF, sauvegarde et restauration au **contenu identique**, relecture après redémarrage |
| 11 `down` | EXÉCUTÉ — conteneurs arrêtés, volumes gardés |

Postcondition de nettoyage vérifiée : aucun rôle, aucune base, aucun
conteneur, aucun volume résiduels (les volumes du mandataire compris).

La cinquième exécution (16/09, sans mandataire, onze pas) tenait déjà. Les
quatre exécutions rouges qui l'ont précédée nommaient chacune un défaut du
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
politiques d'une instance Supabase réelle ; un **certificat public** (la
répétition emploie l'autorité locale de Caddy : la délivrance ACME sous un
vrai nom, sur des ports 80/443 joignables d'Internet, n'a pas tourné) ; la
résolution DNS des noms publics ; un navigateur passant par le mandataire
(les contrôles du pas 7 sont ceux de `curl`, et le parcours du pas 8 est
celui de l'API) ; un compartiment S3 du fournisseur. Le blocage le plus
probable une fois les accès fournis n'est pas un secret mais un **droit**
(`CREATEROLE` du plan de contrôle) — `privileges` le dit avant tout le reste.

## 6. Ce qui a été exécuté ici, et ce qui l'a été sur Supabase

| | localement, sur ce poste | sur Supabase |
|---|---|---|
| migrations, référentiel, admission du login, racine mandatée | exécutés (pas 5), six fois | **jamais** |
| composition `api` + `web` + `mandataire`, TLS, URL publiques, CORS | exécutés (pas 6-7), certificat d'autorité locale | **jamais** |
| parcours par les URL publiques, redémarrage, relecture | exécutés (pas 8-9) | **jamais** |
| recette en sept étapes (quatre-yeux, PDF, DXF, sauvegarde, restauration) | exécutée (pas 10) | **jamais** |

Le statut du produit reste `SUPABASE_UNVERIFIED`. Rien de ce document ne
sera écrit autrement tant que la procédure du §3 n'aura pas tourné contre une
instance réelle, avec les informations du §2.
