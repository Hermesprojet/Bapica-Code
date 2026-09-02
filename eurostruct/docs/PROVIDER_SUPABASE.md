# Provider et Supabase — cartographie en lecture seule

**Mesure du 29/08 sur le SHA gelé `acf107d`.** Aucun service lancé, aucun
secret, aucun fournisseur d'identité fictif branché. Ce document constate ; il
n'installe rien.

## Le provider

### Où la factory est appelée, et où elle devrait l'être

| question | réponse mesurée |
|---|---|
| appels à `creer_provider_de_production` hors de sa définition | **zéro** |
| routes utilisant `InMemoryConfirmationProvider` | **zéro** |
| constructions de `InMemoryConfirmationProvider` hors tests | **zéro** (seulement ses propres fabriques dans `confirmation.py`) |

**Il n'y a pas de couche de routes du tout.** Ni FastAPI, ni Flask, ni routeur :
`grep` sur `FastAPI|@app\.|APIRouter|flask|Blueprint|@router\.` ne rend rien
sous `eurostruct/`. Le seul point d'entrée déclaré du dépôt est
`tools/ndp_import/pyproject.toml`, un outil d'import, qui ne consomme pas de
provider.

La question « quelles routes utilisent encore le provider mémoire » a donc une
réponse exacte, et elle n'est pas « aucune, tout est câblé » : **aucune, parce
qu'il n'existe aucune route**. La frontière d'intégration n'est pas « brancher
la factory sur la route X » ; c'est que la couche appelante n'est pas écrite.

### Quel composant devrait fournir l'identité authentifiée

`Authentificateur` est un `Protocol` défini dans
`engine/src/eurostruct_engine/ndp/postgres_provider.py:135`, avec une propriété
`est_fictif`. La factory exige un authentificateur **concret et non fictif**.

| implémentation | où | fictive ? |
|---|---|---|
| `AuthentificateurFictif` | `db/test/provider_contract.py:82` | oui |
| double de `sans_pilote.py` | `db/test/sans_pilote.py:72` | non, mais c'est un test |

**Aucune implémentation non fictive n'existe dans le produit.**
`BLOCKED_BY_REAL_AUTH` n'est donc pas une prudence : c'est un constat.

### Quelle configuration manque

1. un authentificateur réel — vérificateur de jeton, absent du dépôt ;
2. les logins déclarés dans `eurostruct.authority_backend_logins`, lus depuis
   `pg_db_role_setting` (jamais depuis `current_setting()`) ;
3. une fabrique de connexion de production.

### Ce qui reste fail-closed

* la factory refuse : factory absente, authentificateur absent, authentificateur
  fictif, pilote absent, connexion non conforme ;
* `normative_authenticated_actor()` rend `insufficient_privilege` — pas une
  identité — à un rôle ordinaire qui aurait posé la GUC ;
* sans backend d'autorité déclaré, **aucune** opération d'autorité n'est
  possible : la fonction lève `BLOCKED_BY_REAL_AUTH`.

### Une opération privilégiée devient-elle accessible sans authentificateur réel ?

**Non, et la défense n'est pas le format de la valeur.** `0013` le dit
explicitement : durcir la GUC ne sert à rien, un paramètre de session reste
positionnable par quiconque tient la connexion. La défense est un **privilège** :
`eurostruct_authority_backend` est `NOLOGIN`, seul détenteur de `INSERT` sur les
tables d'autorité, et n'est tenu que par les logins déclarés au niveau base.

Réserve honnête : cela est établi **par le dépôt**, sur le stub. Contre une
instance Supabase réelle, rien n'a été exercé.

## Supabase — classement de chaque propriété

Rappel du montage : `auth.uid()` lit
`current_setting('request.jwt.claim.sub', true)`. Dans Supabase, cette GUC est
posée par PostgREST **après** vérification du jeton. Le dépôt ne contient aucun
vérificateur.

| propriété | classement | ce qui l'établit, ou ce qui manque |
|---|---|---|
| signature du jeton | **non démontrée** | aucun vérificateur dans le dépôt ; relève de GoTrue/PostgREST |
| `issuer` | **non démontrée** | jamais lu par le SQL |
| `audience` | **non démontrée** | jamais lu par le SQL |
| expiration | **non démontrée** | jamais lue par le SQL |
| révocation | **non démontrée** | aucun mécanisme dans le dépôt |
| rotation des clés | **dépendante d'une configuration externe** | propriété de l'émetteur, hors dépôt |
| un client ne peut pas fabriquer la valeur lue comme `auth.uid()` | **démontrée par le dépôt, au niveau privilège seulement** | un rôle ordinaire qui pose la GUC obtient `insufficient_privilege` ; la valeur reste *déclarée*, c'est le privilège qui la rend inopérante |
| isolation multi-tenant par RLS | **démontrée par le dépôt** | exercée par les harnais |
| séparation migrateur / plan de contrôle | **démontrée par le dépôt** | cinq couches, contre-exemple complet |
| compatibilité PostgreSQL 16 | **démontrée par le dépôt** | PostgreSQL 16.13 local |
| compatibilité Supabase | **non démontrée** | `SUPABASE_UNVERIFIED` : aucun script lancé sur une instance réelle |

**Aucune propriété n'est démontrée contre un environnement réel.** La colonne
« démontrée contre un environnement réel » est vide, et c'est le fait principal
de ce tableau.
