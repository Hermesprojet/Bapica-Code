# 6.3c — phase de correction : rapport

Ce document fait suite à `JALON_6_3c_LOT_ROUGE.md`. Il rend compte de la phase
de correction : ce qui a été fermé, comment, et **ce qui ne l'est pas**.

---

## 1. La base Git réellement validée

Le premier rapport ne comparait que `5d77933..3d1bd56` et présentait ce
résultat comme la validation de la base de 6.3c. C'était insuffisant : la
branche ne part pas de `3d1bd56` mais de `e11a62a`, et deux commits séparent
les deux.

```
$ git merge-base --is-ancestor 3d1bd56 e11a62a     →  code 0
$ git diff --name-status 3d1bd56..e11a62a
M  eurostruct/docs/schema/JALON_6_3b6e_BARRIERE_DE_VIVACITE.md
A  eurostruct/docs/schema/JALON_6_3c_CARTOGRAPHIE_DE_CONFIANCE.md
$ git log --oneline 3d1bd56..e11a62a
e11a62a docs(6.3c): cartographie de la frontiere de confiance…
d04abf0 docs: les deux verifications de cloture…
$ git log --merges 5d77933..HEAD                   →  vide
```

| segment | fichiers | classement |
|---|---|---|
| `5d77933..3d1bd56` | 1 | documentaire |
| `3d1bd56..e11a62a` | 2, tous deux sous `docs/schema/` | documentaire |
| `e11a62a..…` | harnais, migrations, câblage | **fonctionnel — introduit par 6.3c** |

Chaîne linéaire, sans fusion. Aucun exécutable, script, test, workflow ou
configuration **préexistant** ne diffère entre le SHA de campagne 6.3b6e et
l'ouverture de 6.3c. Le verdict « pas de rejeu de la matrice de clôture »
tient — mais il est désormais établi sur les **deux** segments.

---

## 2. L'incohérence arithmétique, et l'invariant qui l'empêche de revenir

Quatorze attaques annonçaient « 4 rouges et 11 sûres » — quinze. L'attaque 10
bouclait sur `update` puis `delete` et **émettait un verdict par tour**. Le
compteur additionnait des *appels*, pas des *attaques*.

Un compteur qui peut mentir sur son propre total n'atteste rien du produit. Le
registre vit maintenant dans `lib_harnais.sh`, **partagé par tous les harnais**,
et il est structurel :

- les contrôles sont **déclarés d'avance** ;
- `verdict <id> <statut>` en enregistre **un seul** — un second verdict pour le
  même identifiant est une **faute** ;
- un contrôle déclaré sans verdict est une **faute** ;
- l'égalité `déclarés == exécutés == rouges + sûrs + non_parcourus` est
  **vérifiée en fin de course** ;
- toute faute force la sortie en échec.

Il a immédiatement prouvé son utilité : passé sous la migration de filiation,
le harnais a déclaré **sept chemins NON PARCOURUS** au lieu de les rendre
« sûrs ».

---

## 3. La falsification complète de l'attaque 10

Deux causes se cachaient l'une derrière l'autre.

**a) L'attaque mesurait le mauvais privilège.** Elle visait une ligne précise
(`where id = …`). La matrice mesurée dit `select=false` : `normative_backend`
n'a pas `SELECT` sur cette table, et un `UPDATE … WHERE` doit **lire** la
colonne du prédicat. Le « permission denied » venait du `SELECT` implicite, pas
de la garde d'immuabilité — le test serait resté vert si `UPDATE` avait été
accordé par mégarde. Les deux ordres sont désormais **sans `WHERE`**.

**b) La neutralisation échouait en silence.** Son `GRANT` était émis par le
migrateur alors que la table appartient à `eurostruct_normative_writer`, et
PostgreSQL répond à un `GRANT` sans droit par un **WARNING**. Une neutralisation
non vérifiée ne prouve rien — c'est le même faux vert, appliqué à la
falsification elle-même. Le harnais **affiche** donc les privilèges de table
réels à chaque exécution.

Falsification obtenue, toutes protections pertinentes retirées — privilège,
RLS, déclencheur d'immuabilité, et la clé étrangère `on delete restrict`
retirée explicitement, son nom **résolu dans le catalogue** et non deviné :

```
10. update -> REECRIT (6 reecrite(s)) ; delete -> REECRIT (6 -> 0)
ROUGE ATTENDU (a fermer): 10.
```

La garantie a été **vue échouer**. La mention « moitié non falsifiée » est
retirée.

---

## 4. Le modèle de confiance implémenté

### Ce qui n'a pas été fait, et pourquoi

**Le GUC n'a pas été « durci ».** Qu'il s'appelle `request.jwt.claim.sub` ou
`app.actor_id`, un paramètre de session reste positionnable par quiconque tient
la connexion. Le renommer ou le vérifier « mieux » ne change rien : il est
**déclaré**.

### La frontière posée

| pièce | rôle |
|---|---|
| `eurostruct_authority_backend` | rôle d'**exécution** privilégié, NOLOGIN, **seul** à détenir `INSERT` sur les quatre tables d'autorité |
| `eurostruct.authority_backend_logins` | les logins qui le reçoivent, **déclarés** puis **figés** — lus dans `pg_db_role_setting`, jamais par `current_setting()` |
| `normative_authenticated_actor()` | l'acteur, lu du contexte **seulement si** la session atteint le rôle privilégié |
| `normative_authenticated_actor_or_null()` | même chose sans lever, pour les déclencheurs qui lisent l'acteur avant de savoir s'il s'agit d'un amorçage |

**La défense est structurelle, pas déclarative** : un rôle applicatif qui
falsifie le GUC n'atteint plus la table — il n'a plus `INSERT`. L'ordre est
refusé par le moteur, avant tout déclencheur.

### Fail-closed, et dit plutôt que masqué

Sans authentificateur déclaré : `BLOCKED_BY_REAL_AUTH`. Sans mandat
d'amorçage : `BOOTSTRAP_AUTHORITY_NOT_CONFIGURED`. **C'est l'état de ce dépôt** :
aucun vérificateur de jeton ni mandat externe n'y existe, et aucun n'a été
inventé. La garantie « c'est bien *cette personne* » reste
`BLOCKED_BY_REAL_AUTH` — et le schéma le **dit** désormais, au lieu de laisser
croire que `auth.uid()` l'établissait.

---

## 5. Le modèle d'amorçage

`p_grantee` cesse d'être un choix : la primitive le **confronte** au mandat
déclaré, sous la forme `<uuid-du-principal>:<empreinte-du-mandat>`. L'empreinte
n'est pas vérifiable par la base — le document vit hors du système — mais elle
est **inscrite dans l'audit**, ce qui rend la décision opposable.

La consommation passe par une **clé primaire** sur l'empreinte : un rejeu se
heurte à la contrainte, pas à un contrôle applicatif qu'une course
traverserait. Deux amorçages concurrents portant le même mandat : l'un reçoit
une violation d'unicité, et c'est **structurel**.

Le détenteur de `eurostruct_deployment` déclenche toujours l'amorçage — c'est
son travail — mais il **exécute** une décision prise ailleurs.

---

## 6. Le modèle de filiation et de révocation

La décision « révocation non transitive » consignée dans le lot rouge est
**abandonnée**. Elle confondait la conservation des *preuves* — garantie par
l'immuabilité, et intacte — avec la survie du *pouvoir*. Et la contrepartie
promise était inimplémentable : aucune colonne ne reliait un octroi à celui
sous lequel il avait été consenti. `granted_by` nomme la **personne**, pas le
**pouvoir**. La non-transitivité n'était pas un choix, c'était une
impossibilité déguisée en décision.

| pièce | règle |
|---|---|
| `parent_grant_id` | toute délégation nomme l'habilitation **précise** qui l'autorise |
| grantor | doit **détenir** ce parent, et le parent doit être efficace |
| portée | incluse dans celle du parent **sur les quatre axes** ; un axe `NULL` sous un parent borné est un **élargissement**, refusé |
| permission | ne s'élève pas : une vérification ne délègue pas |
| `expires_at` | borné par le terme du parent ; un enfant sans terme sous un parent à terme est refusé |
| `normative_grant_is_effective()` | remonte la chaîne : révoqué ou expiré **à tout niveau** ⇒ inefficace |
| `normative_grant_descendants()` | rend « que perd-on en révoquant ceci ? » répondable **avant** |

**Les cycles de filiation sont structurellement impossibles** :
`parent_grant_id` ne peut désigner qu'une ligne déjà existante et aucun
`UPDATE` n'est accordé — le graphe est un DAG. Ce qui reste possible est le
cycle de *personnes* (A délègue à B, B rend à A) ; il ne crée aucun pouvoir
supplémentaire, et un test l'établit au lieu de le supposer.

---

## 7. Le piège qui s'est présenté trois fois

`GRANT` et `REVOKE` exigent d'être propriétaire de l'objet. Quand on ne l'est
pas, PostgreSQL émet un **WARNING**, pas une erreur. Dans ce seul jalon, ce
comportement a :

1. fait échouer **en silence** une neutralisation de falsification — le test
   se lisait « la garde tient » alors que la garde n'avait pas été touchée ;
2. refusé deux migrations sur « permission denied for schema public », parce
   que `0010` retire `CREATE on public` aux rôles d'autorité après ses propres
   transferts ;
3. laissé la frontière d'autorité **non posée** : les révocations d'`INSERT`
   ne retiraient rien, et deux attaques restaient rouges — non parce que la
   frontière était mal conçue, mais parce qu'elle n'existait pas.

Le sceau documente ce piège depuis 6.3b6d. La leçon retenue : **une opération
de privilège qui peut échouer sans erreur doit être suivie d'une assertion**.
`0013` vérifie donc, en fin de migration, que `normative_backend` a bien perdu
`INSERT` et que le backend authentifié l'a bien reçu — et refuse de se déclarer
appliquée sinon.

Deux autres pièges du même genre, mesurés et documentés dans les fichiers :

- **`FORCE ROW LEVEL SECURITY` sans policy n'est pas « très fermé »** : c'est
  fermé à tout le monde, y compris à la fonction `SECURITY DEFINER` censée
  remplir la table. `0013` se refusait à son propre constat.
- **Une policy ne remplace pas un privilège.** Les deux sont nécessaires et ne
  disent pas la même chose : le privilège ouvre la table, la policy filtre les
  lignes.

---

## 7 bis. État mesuré des suites ciblées

Cluster jetable, quatre harnais, chacun avec son propre décor mené jusqu'à
`ACTIVE`, chacun rendant son invariant de comptabilité.

| harnais | déclarés | sûrs | rouges | non parcourus | code |
|---|---|---|---|---|---|
| `authority_root_of_trust.sh` | 14 | **14** | 0 | 0 | **0** |
| `authority_sql_hardening.sh` | 14 | **14** | 0 | 0 | **0** |
| `authority_delegation_lineage.sh` | 15 | **15** | 0 | 0 | **0** |
| `authority_bootstrap_contract.sh` | 8 | **8** | 0 | 0 | **0** |
| **total** | **51** | **51** | **0** | **0** | — |

`déclarés == exécutés == rouges + sûrs + non_parcourus` tenu dans les quatre.

### Les quatre ouvertures du lot rouge, fermées

| # | ce qui était mesuré avant | ce qui est mesuré maintenant |
|---|---|---|
| 1 | un membre de `eurostruct_deployment` nommait librement la première autorité | l'amorçage n'aboutit qu'au principal **désigné par le mandat**, et le consomme |
| 4 | le serveur inscrivait dans `granted_by` la valeur déclarée par la session | un rôle applicatif **ordinaire** qui déclare une identité **n'écrit rien** |
| 6 | deux paternités distinctes depuis une connexion, par deux `SET` | deux identités déclarées depuis une connexion ordinaire ne produisent **aucune** paternité |
| 12 | la même chose en concurrence | deux sessions ordinaires concurrentes, **observées bloquées** puis relâchées ensemble, n'aboutissent pas |

La non-vacuité de 4, 6 et 12 est établie par **contrôle positif** : la même
écriture, par le **backend authentifié**, aboutit. Ce n'est donc pas la valeur
qui est refusée — c'est la **session**.

### Un défaut trouvé par le harnais, et non par la lecture

`authority_delegation_lineage.sh` a déclaré trois contrôles **NON PARCOURUS**
là où un compteur moins strict les aurait rendus « sûrs ». La cause était un
défaut réel laissé par `0012` : le contrôle d'unicité de portée utilisait
encore `normative_grant_is_active` (« aucune révocation ne vise *cette* ligne »)
au lieu de `normative_grant_is_effective`. Un octroi devenu inefficace parce
qu'un **ancêtre** avait été révoqué bloquait donc un nouvel octroi de même
portée : la révocation éteignait le pouvoir **et** interdisait de le
reconstituer par une chaîne explicite — l'inverse de ce que `0012` promettait.

---

## 8. Ce qui reste ouvert

Cette section est la plus importante du rapport, et elle n'est pas une liste
d'intentions : c'est l'inventaire de ce qui **n'a pas été mesuré**.

### 8.1 Le quatre-yeux (§4) n'est que **partiellement** couvert

Ce qui est acquis, et mesuré :

- une connexion applicative **ordinaire** ne peut produire **aucune** écriture
  d'autorité — elle ne peut donc pas en produire deux ;
- `proposer == approver` est refusé au niveau transactionnel, sous la forme de
  l'interdiction d'auto-attribution (I-4) ;
- l'autorité est vérifiée **au moment de chaque action**, sous verrou et avec
  relecture (I-8), et la relecture porte désormais sur la **chaîne entière**.

Ce qui **manque** : un modèle explicite *décision → deux approbations*, avec
consommation unique et atomique de la décision, et conservation de la source
d'autorité utilisée **par chaque approbateur**. Le décompte à quatre yeux vit
aujourd'hui dans le domaine Python (`independent_regards`, sur des
`verifier_id` distincts) et non dans une table de décisions. Tant que ce
modèle n'existe pas, l'affirmation « deux regards indépendants » repose sur la
frontière d'authentification, pas sur une structure qui la porte.

### 8.2 Les étapes 7 à 12 de l'ordre d'exécution ne sont pas faites

| étape | état |
|---|---|
| 7 — falsifier **chaque** garde dans des copies du même SHA | faite pour I-4, I-5/I-6, I-9 ; **non faite** pour les gardes introduites par 0011, 0012 et 0013 |
| 9 — `db/test/run.sh` complet | **non exécuté** depuis les corrections |
| 10 — geler un SHA unique | **non fait** |
| 11 — campagne complète de mutations | **non lancée** |
| 12 — vérification finale des résidus | partielle (cluster et arbre Git vérifiés à chaque étape, pas en clôture) |

**Aucune de ces étapes ne doit être présumée.** Les suites ciblées passent ;
la suite complète n'a pas été rejouée, et une régression sur une surface
étrangère à 6.3c ne serait pas encore visible.

### 8.3 Ce qui reste hors de portée du dépôt

| attendu | état |
|---|---|
| vérificateur de jeton / fournisseur d'identité | **absent** — `BLOCKED_BY_REAL_AUTH` |
| mandat d'amorçage externe | **absent** — `BOOTSTRAP_AUTHORITY_NOT_CONFIGURED` |
| `PostgresConfirmationProvider`, routes, services, CLI d'autorité | **absents** |

Le contrat de provider (§2 : transaction explicite, authentification avant
toute opération, `SET LOCAL` après authentification, pas de fuite entre
requêtes du pool, disparition vérifiée après commit / rollback / erreur) est
**posé côté SQL** — le contexte est refusé à qui n'est pas le backend
authentifié, et `SET LOCAL` disparaît avec la transaction. Mais **le provider
lui-même n'existe pas** : il n'y a rien à faire fuiter entre deux requêtes d'un
pool qui n'existe pas. Ces contrôles ne pourront être écrits qu'avec lui.
