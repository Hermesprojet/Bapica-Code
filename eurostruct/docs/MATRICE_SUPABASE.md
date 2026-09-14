# Matrice Supabase — ce que le dépôt démontre, et ce qu'il ne démontre pas

**Statut : `BLOCKED_BY_REAL_AUTH — SUPABASE_UNVERIFIED`.**

Cette matrice est établie **uniquement à partir du dépôt**. Aucune ligne n'est
complétée par une hypothèse sur ce que Supabase fait probablement. Là où la
preuve manque, la case dit ce qui manque et ce que cela coûte.

## La question que cette matrice existe pour trancher

`auth.uid()` apparaît 25 fois dans les migrations et le sceau. La tentation est
de la lire comme « l'utilisateur authentifié ». **Le dépôt ne le démontre pas.**
Ce que le dépôt contient est ceci, dans `db/test/00_supabase_stub.sql` :

```sql
create or replace function auth.uid() returns uuid
language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;
```

`auth.uid()` lit un **réglage de session**. Un réglage de session est posé par
quelqu'un. Tant que le dépôt ne montre pas *qui* le pose, ni *sur quelle
vérification*, `auth.uid()` est une **variable**, pas une authentification.

## La matrice

| # | Propriété | Preuve dans le dépôt | Fichier / symbole | Ce qui est démontré | Ce qui manque | Conséquence |
|---|---|---|---|---|---|---|
| 1 | **Validation de la signature JWT** | aucune | — | rien | aucun code du dépôt ne vérifie une signature ; aucune clé, aucun algorithme, aucune bibliothèque JWT | un jeton non signé ou signé par un tiers n'est distingué par rien **dans ce dépôt** |
| 2 | **Issuer (`iss`)** | aucune | — | rien | aucun `iss` attendu n'est déclaré nulle part | un jeton d'un autre projet Supabase serait indiscernable |
| 3 | **Audience (`aud`)** | aucune | — | rien | aucun `aud` attendu | idem |
| 4 | **Expiration (`exp`)** | aucune | — | rien | aucune lecture de `exp`, aucune horloge de référence | un jeton expiré reste utilisable **du point de vue du dépôt** |
| 5 | **Subject (`sub`)** | `current_setting('request.jwt.claim.sub', true)` | `00_supabase_stub.sql:33` | que la valeur est **lue** depuis un réglage de session | qui l'écrit, et après quelle vérification | le `sub` est une donnée d'entrée, pas une identité prouvée |
| 6 | **Mapping vers l'acteur interne** | `normative_authenticated_actor()` | `0013_authenticated_actor.sql:250` | que l'acteur est **dérivé** de `auth.uid()` et refusé s'il est absent (fail-closed) | la chaîne amont : rien ne relie `auth.uid()` à une preuve | le fail-closed est réel ; ce qu'il laisse passer dépend d'un maillon absent du dépôt |
| 7 | **Rôle PostgreSQL de connexion** | `eurostruct.token_roles`, `approved_service_logins`, `authority_backend_logins` | `0013`, sceau | que les logins admis sont **déclarés et figés à la finalisation** | quel rôle Supabase utilise réellement en production | déclaré, non confronté à une instance |
| 8 | **GUC modifiables par le client** | mesuré : `alter role ... set eurostruct.authority_backend_logins` → `permission denied to set parameter` | `authority_sql_hardening.sh` (auto-enrôlement) | qu'un login ordinaire **ne peut pas** se déclarer backend d'autorité | rien : cette ligne est démontrée | l'auto-enrôlement par GUC est fermé, et c'est mesuré |
| 9 | **Accès client direct** | RLS + `FORCE ROW LEVEL SECURITY` sur les cinq tables d'autorité, aucun privilège de table au login de service | `0011`–`0014`, `provider_contract.py` | que le client direct **n'écrit pas** dans les tables de preuve : tout passe par trois primitives `SECURITY DEFINER` | que le client direct soit bien celui qu'on croit (voir 1–5) | la surface est fermée ; l'identité qui la franchit ne l'est pas |
| 10 | **Backend de confiance** | `PostgresConfirmationProvider` refuse d'exister sans authentificateur ; `creer_provider_de_production` refuse un authentificateur fictif | `postgres_provider.py`, `provider_factory.py` | que la composition est fail-closed | **aucun authentificateur concret n'existe** dans le dépôt | il n'y a pas de backend de confiance à ce jour, seulement sa place |
| 11 | **Secrets / `service_role`** | aucune | — | rien | aucun secret, aucune URL, aucun `service_role` n'est présent — **et c'est voulu** | ne peut pas être vérifié ici ; ne doit pas l'être |
| 12 | **Rejeu (*replay*)** | consommation unique d'une décision : `state = CONSUMED`, transition contrôlée par déclencheur | `0014`, `check_normative_decision_transition` | qu'une **décision** ne peut pas être consommée deux fois | qu'un **jeton** ne peut pas être rejoué : hors du dépôt | rejeu applicatif fermé, rejeu d'authentification non traité |
| 13 | **Révocation de session** | aucune | — | rien | aucune liste de révocation, aucune durée de vie | une session compromise reste valide du point de vue du dépôt |

## Ce que la matrice permet de conclure

**Fermé et mesuré :** l'auto-enrôlement par GUC (8), l'accès direct aux tables
de preuve (9), la double consommation d'une décision (12), et le caractère
fail-closed de la composition du provider (10).

**Non démontré :** tout ce qui précède `auth.uid()` — signature, issuer,
audience, expiration, et donc l'identité elle-même (1–5, 13).

La conclusion n'est pas « Supabase est incompatible ». Elle est plus étroite et
plus utile : **le dépôt ne contient pas la moitié amont de la chaîne
d'authentification**, et rien de ce qu'il contient ne peut la remplacer. Le
sous-système d'autorité reste donc `BLOCKED_BY_REAL_AUTH`, et la compatibilité
Supabase `SUPABASE_UNVERIFIED` jusqu'à validation du cycle complet sur un
staging réel.

## Ce qu'il ne faut pas écrire

> « `auth.uid()` identifie l'utilisateur authentifié. »

C'est faux tant que le dépôt ne montre pas qui valide le claim et qui pose le
réglage. La formulation exacte est : *`auth.uid()` rend la valeur d'un réglage
de session que le dépôt ne vérifie pas.*
