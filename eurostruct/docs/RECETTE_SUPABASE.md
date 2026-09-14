# Recette sur un staging Supabase — état, étapes, accès manquants

**Statut : `SUPABASE_UNVERIFIED`. Aucune des sept étapes n'a été exécutée sur
une instance Supabase réelle.** Tout ce qui suit décrit ce qu'il faut faire et
avec quoi ; rien ici n'atteste d'un essai.

Le préflight exécutable est `db/test/recette_supabase_staging.sh`. Lancé sans
accès, il rend **4** et nomme chaque variable manquante, ce qu'elle désigne et
qui peut la fournir. Lancé avec les accès mais sans consentement, il rend **2**
sans joindre quoi que ce soit. Les deux refus ont été exercés ; le chemin
nominal, par construction, ne l'a pas été.

## 1. Ce que « Supabase compatible » voudrait dire, et pourquoi ce n'est pas acquis

Le produit est implémenté et mesuré sur **PostgreSQL 16.13**. Supabase sert du
PostgreSQL, mais un projet Supabase n'est pas un cluster dont on est
propriétaire : le rôle applicatif n'y a ni `SUPERUSER`, ni nécessairement
`CREATEROLE`, et c'est exactement ce dont dépend le déploiement en deux phases.

**Le blocage principal n'est pas un secret : c'est un droit.** Les harnais du
dépôt — `parcours_authentifie.sh`, `decision_vers_strict.sh`,
`parcours_livrable.sh`, `sauvegarde_restauration.sh` — créent leur propre rôle
migrateur avec `createrole createdb`. Les repointer vers un staging ne suffira
pas : il faut d'abord savoir si le rôle connecté peut obtenir ces capacités.

C'est la question que `db/test/supabase_probe.sh` pose, et la seule à poser en
premier.

## 2. Les sept étapes, dans l'ordre

| | étape | ce qu'elle doit établir | bloquée par |
|---|---|---|---|
| 0 | plan de contrôle | `CREATEROLE`, précréation d'un rôle d'autorité, octroi en restant le **donneur**, révocation intégrale | `EUROSTRUCT_PROBE_DATABASE_URL`, `EUROSTRUCT_PROBE_TARGET` |
| 1 | migrations et rôles | le schéma s'installe, les rôles canoniques existent, RLS `FORCE` en place | `EUROSTRUCT_STAGING_MIGRATION_DSN` — et l'étape 0 verte |
| 2 | authentification | un jeton GoTrue **réel** est accepté : signature, émetteur, audience, expiration | `EUROSTRUCT_SUPABASE_JWKS_URL`, `_ISSUER`, `_AUDIENCE` |
| 3 | confirmations à quatre yeux | deux ingénieurs **distincts** proposent, approuvent, consomment | `EUROSTRUCT_STAGING_COMPTE_A`, `..._COMPTE_B` |
| 4 | étude stricte belge | les 19 paramètres sont utilisables, la vérification part et aboutit | rien de plus — dépend de 1 à 3 |
| 5 | livrables PDF et DXF | les octets sont écrits, relus, et leur empreinte concorde | `EUROSTRUCT_STORAGE_BACKEND`, `EUROSTRUCT_S3_*` |
| 6 | sauvegarde et restauration | une restauration rend le même état, empreintes comprises | `EUROSTRUCT_STAGING_RESTORE_DSN` — voir §4 |
| 7 | relecture après redémarrage | le calcul survit, la session **ne survit pas** | rien de plus |

## 3. L'accès qui ne peut venir d'aucune configuration

L'étape 3 exige **deux ingénieurs nommés et distincts**. PostgreSQL le refuse
autrement, par contrainte de table :

```sql
constraint decision_two_distinct_principals
  check (approver_id is null or approver_id <> proposer_id)
```

Ce n'est pas un accès que ce dépôt peut fabriquer, et il ne doit pas essayer.
Créer deux identités de complaisance rendrait la recette verte et ne
prouverait rien : le dispositif existe précisément pour qu'une valeur nationale
porte le nom de deux personnes qui l'ont lue.

C'est le même manque que celui consigné dans
[`relecture/DECLARATION_VALIDATION_BE_EC2.md`](relecture/DECLARATION_VALIDATION_BE_EC2.md)
sous le point **S1**.

## 4. Une décision à prendre avant l'étape 6, et elle n'est pas technique

`sauvegarde_restauration.sh` restaure **dans le même cluster** — le refus d'une
restauration inter-cluster est le sujet d'un autre harnais, délibérément. Sur
un staging Supabase, cela signifie écrire une base restaurée à côté de la base
de travail.

Qui l'autorise, et où elle atterrit, se tranche avant de lancer la recette, pas
pendant. `EUROSTRUCT_STAGING_RESTORE_DSN` existe pour rendre ce choix explicite
plutôt que de laisser un script le faire à la place de quelqu'un.

## 5. Ce qui, aujourd'hui, tient lieu de preuve — et ce que cela vaut

| | ce qui est établi | sa limite |
|---|---|---|
| base | tout le comportement SQL, sur PostgreSQL 16.13 en cluster jetable | ce n'est pas Supabase, et la différence porte sur les **droits**, pas sur le SQL |
| authentification | `web/e2e/supabase_local.mjs` — un émetteur GoTrue local, clés RSA générées au démarrage, vérification par l'authentificateur **de production** | prouve le comportement de notre code face à un émetteur conforme ; ne dit rien de celui de Supabase |
| magasin | MinIO en conteneur, API S3 | Supabase Storage expose une API S3, mais son comportement exact reste à constater |

Aucune de ces trois lignes ne permet d'écrire « compatible Supabase ».

## 6. Comment lancer, le jour où les accès existent

Depuis un environnement sécurisé, avec les secrets fournis par la
configuration — **jamais collés dans un échange, jamais passés en `argv`** :

```
db/test/recette_supabase_staging.sh          # diagnostic: 0, 2 ou 4
EUROSTRUCT_RECETTE_CIBLE=staging \
  db/test/recette_supabase_staging.sh        # enchaîne les sept étapes
```

Le préflight ne lit aucune valeur : il constate qu'une variable est **définie**,
et rien d'autre. Aucune URL de connexion, aucun fragment de secret ne passe par
sa sortie.

## 7. Quand pourra-t-on retirer `SUPABASE_UNVERIFIED`

Quand les sept étapes auront été traversées sur une instance réelle, et que le
compte rendu de cette traversée sera dans le dépôt — avec, pour chacune, ce qui
a été observé. Pas avant, et pas parce que les étapes 1 à 7 « devraient »
passer.
