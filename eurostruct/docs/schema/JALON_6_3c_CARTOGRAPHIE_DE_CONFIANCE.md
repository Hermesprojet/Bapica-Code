# 6.3c — cartographie de la frontière de confiance

Ce document précède toute correction. Il dit **où l'identité de l'acteur est
dérivée, où elle est affirmée par l'appelant, et où se situe la première
frontière non falsifiable** — pour chaque chemin qui peut créer, confirmer,
déléguer, révoquer ou utiliser une autorité.

**Statut des affirmations ci-dessous.** Elles proviennent de la *lecture* du
code (ACL, policies RLS, corps des fonctions), pas encore de l'exécution. Les
contre-exemples rouges qui suivront les transformeront en faits mesurés, ou les
corrigeront. Aucune correction n'a été écrite à ce stade.

---

## 0. Ce qui n'existe pas

La consigne mentionne `PostgresConfirmationProvider`, des routes API, des
services et une CLI éventuelle. **Aucun n'existe dans ce dépôt.** L'inventaire
réel :

| couche | présence |
|---|---|
| `ConfirmationProvider` (Protocol) | `engine/src/eurostruct_engine/ndp/confirmation.py` |
| `InMemoryConfirmationProvider` | idem |
| `PostgresConfirmationProvider` | **absent** |
| routes API / HTTP | **absentes** |
| services applicatifs | **absents** |
| CLI d'autorité | **absente** (la seule CLI est `tools/ndp_import`, hors autorité) |
| SQL | `db/migrations/0010_normative_confirmation.sql`, `db/control_plane/0001_normative_seal.sql` |

Conséquence directe pour 6.3c : **la seule frontière de confiance réellement
implémentée est PostgreSQL.** Les §23 et §24 (suite contractuelle commune
mémoire/Postgres, providers de test trop permissifs) portent sur un provider
Postgres qui reste à écrire ; ils ne peuvent pas être fermés en comparant deux
implémentations dont une seule existe.

---

## 1. Les deux chemins qui créent une autorité

### A. Amorçage — `bootstrap_normative_administrator(p_grantee, p_grantee_name, p_reason)`

| question | réponse |
|---|---|
| qui fournit l'identité de l'acteur ? | **le moteur PostgreSQL** : appartenance au rôle `eurostruct_deployment` |
| dérivée ou paramètre ? | **dérivée** — `REVOKE ALL FROM PUBLIC`, `GRANT EXECUTE TO eurostruct_deployment` |
| qui fournit le bénéficiaire ? | **l'appelant**, via `p_grantee` — valeur entièrement libre |
| permission vérifiée | aucune autre : le droit d'exécuter EST la permission |
| première frontière non falsifiable | l'ACL `EXECUTE` de la fonction, plus `owner = eurostruct_normative_bootstrap` (NOLOGIN) et la policy RLS `with check (origin = 'bootstrap') to eurostruct_normative_bootstrap` |
| unicité | `pg_advisory_xact_lock` + index partiel `normative_bootstrap_is_singular` |

**Ce qui est déjà solide.** L'autorité déclenchante *est* authentifiée — par
appartenance de rôle PostgreSQL, pas par un paramètre. Ce n'est pas un UUID
transmis. Un rôle applicatif ne peut pas appeler la fonction, et ne peut pas
non plus insérer une ligne `origin = 'bootstrap'` : la policy le réserve à
`eurostruct_normative_bootstrap`, et `normative_backend` a
`with check (origin = 'delegated')`.

**Ce qui ne l'est pas — et c'est le Q6 réel.** `p_grantee` est libre. Le
détenteur de `eurostruct_deployment` choisit qui devient le **premier
administrateur normatif**, y compris lui-même ou un complice. Rien dans la
chaîne ne distingue :

- *racine de confiance **technique*** — le droit d'initialiser un référentiel ;
- *responsabilité **professionnelle*** — le droit d'engager une signature
  d'ingénieur sur une règle normative.

Le §38 de la consigne nomme exactement cette confusion. L'amorçage la crée :
une identité de déploiement se transforme en autorité normative fondatrice par
le seul choix d'un paramètre.

> **Reformulation du rouge initial.** La consigne le formule « autorité
> déclenchante non authentifiée et `p_grantee` libre ». La première moitié est
> inexacte au vu du code : le déclencheur *est* authentifié par appartenance de
> rôle. La seconde moitié est exacte et suffit à elle seule. Le rouge doit donc
> viser **le choix libre du bénéficiaire par une identité technique**, pas
> l'absence d'authentification du déclencheur.

### B. Délégation — `insert into normative_authorisation_grants` + trigger `check_normative_grant()`

| question | réponse |
|---|---|
| qui fournit l'identité de l'acteur ? | `auth.uid()`, appelé **dans le trigger** |
| dérivée ou paramètre ? | **dérivée du contexte de session** ; la colonne `granted_by` fournie par l'appelant est **écrasée** : `new.granted_by := acteur` |
| qui fournit le bénéficiaire ? | l'appelant, via `grantee_id` |
| permission vérifiée | l'acteur doit détenir un octroi actif ; `origin` est forcé à `'delegated'` ; `grantee_id = acteur` → refus |
| première frontière non falsifiable | **aucune, au sens strict** — voir §2 |

**Ce qui est déjà solide.** `granted_by` n'est pas cru. L'auto-attribution est
refusée. `origin = 'bootstrap'` depuis une session authentifiée est refusé, et
la RLS le réserve au rôle d'amorçage.

---

## 2. La frontière réelle : `auth.uid()` est un GUC de session

```sql
create or replace function auth.uid() returns uuid
language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;
```

`request.jwt.claim.sub` est un **paramètre de configuration applicatif**. En
PostgreSQL, un GUC à nom qualifié est positionnable par **tout rôle** via `SET`
ou `SET LOCAL`. Il n'existe aucun contrôle d'écriture dessus.

Donc, précisément :

| détenteur | peut-il fixer `request.jwt.claim.sub` ? | conséquence |
|---|---|---|
| PostgREST, après vérification du JWT | oui — c'est l'usage prévu | identité réelle |
| tout code tenant une connexion brute, quel que soit son rôle | **oui** | **identité choisie** |
| `normative_backend` (qui a `INSERT` sur les octrois) | **oui** | peut se nommer n'importe qui avant d'insérer |

**`auth.uid()` n'authentifie donc pas un utilisateur métier. Il rapporte ce que
la session a déclaré.** Sa fiabilité dépend entièrement d'une propriété qui
n'est pas dans la base : *que seul le vérificateur de JWT détienne la
connexion*. Cette propriété n'est ni testée ni testable ici, puisque la couche
qui la porterait n'existe pas.

C'est exactement la mise en garde de la consigne §4, et la contrainte que vous
aviez déjà posée : *ni GUC de session comme preuve de confiance.*

### Ce que PostgreSQL peut réellement authentifier ici

| mécanisme | authentifie | ne dit rien de |
|---|---|---|
| `session_user` | le rôle **connecté** | l'utilisateur métier |
| `current_user` | le rôle **effectif** (vaut le propriétaire dans un `SECURITY DEFINER`) | l'appelant |
| appartenance de rôle (`pg_has_role`) | une capacité **de déploiement/service** | une personne |
| `auth.uid()` | **rien** — une déclaration de session | tout le reste |

Les trois premiers sont non falsifiables depuis SQL. Le quatrième ne l'est pas
du tout. **Toute garantie 6.3c reposant sur l'identité d'une personne est donc
`BLOCKED_BY_REAL_AUTH`** (§41) : elle ne pourra être close qu'avec une
authentification réelle, absente du produit.

Ce que 6.3c *peut* fermer sans elle : que le modèle d'autorisation soit correct
et **non contournable par les interfaces prévues**, et que le passage d'une
identité technique à une autorité professionnelle soit impossible sans une
décision explicitement tracée.

---

## 3. Ce qu'un appelant contrôlant ses paramètres peut forger aujourd'hui

Lecture du code, à confirmer par les rouges :

| acteur | ce qu'il contrôle | ce qu'il obtiendrait | statut |
|---|---|---|---|
| `eurostruct_deployment` | `p_grantee` | **se nommer premier administrateur normatif** | à démontrer — rouge n° 1 |
| tout rôle tenant une connexion | `SET request.jwt.claim.sub` | **agir sous l'identité de n'importe quel administrateur** | à démontrer — rouge n° 2 |
| `normative_backend` | idem + `INSERT` sur les octrois | déléguer au nom d'autrui | à démontrer — rouge n° 3 |
| un porteur d'octroi | `grantee_id`, `permission`, portée | amplification de portée ? | à vérifier — le trigger contrôle-t-il `granted_scope ⊆ grantor_scope` ? |
| un porteur d'octroi | rejouer une décision | doublon d'octroi ? | à vérifier — clé d'idempotence ? |

Les deux dernières lignes sont des **questions ouvertes**, pas des accusations :
je n'ai pas encore lu la totalité de `check_normative_grant()` ni les contrôles
de portée. Elles seront tranchées avant le premier correctif.

---

## 4. Ce que la cartographie ne couvre pas encore

- le corps complet de `check_normative_grant()` au-delà de l'auto-attribution ;
- `check_normative_confirmation()` et le lien confirmation ↔ hash/version de la
  règle (§22) ;
- la sémantique de révocation transitive (§15) et les cycles (§16) ;
- `resolve_normative_authorisation` / `consume_normative_authorisation` — le
  chemin d'**usage** d'une autorité, distinct du chemin de création ;
- les quatre-yeux (Q1) : je n'ai pas encore identifié où `proposer`/`approver`
  sont modélisés, ni s'ils le sont.

Ces points sont la suite immédiate de la cartographie, avant tout correctif.
