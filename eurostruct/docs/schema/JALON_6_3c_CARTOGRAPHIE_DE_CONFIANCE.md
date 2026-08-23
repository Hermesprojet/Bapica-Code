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

## 3. La cartographie exhaustive des chemins d'autorité

**Statut : mesuré.** Les colonnes « ACL » et « propriétaire » proviennent de la
matrice que `db/test/authority_root_of_trust.sh` produit lui-même sur une base
réellement déployée (section 0 de sa sortie), pas d'une lecture du code. Une
matrice recopiée à la main dans un rapport n'est qu'une affirmation de plus.

### 3.1 Les huit chemins

| # | chemin | primitive | identité de l'acteur | valeurs contrôlées par l'appelant |
|---|---|---|---|---|
| A | amorçage | `bootstrap_normative_administrator(uuid,text,text)` | **appartenance de rôle** `eurostruct_deployment` | `p_grantee`, `p_grantee_name`, `p_reason` — **tous libres** |
| B | délégation | `INSERT normative_authorisation_grants` → `check_normative_grant()` | `auth.uid()` | `grantee_id`, `permission`, les 4 axes de portée, `reason` |
| C | révocation d'octroi | `INSERT normative_authorisation_revocations` → `check_normative_grant_revocation()` | `auth.uid()` | `grant_id`, `reason` |
| D | confirmation | `INSERT normative_rule_confirmations` → `check_normative_confirmation()` | `auth.uid()` | les 4 payloads canoniques et leurs empreintes |
| E | révocation de confirmation | `INSERT normative_confirmation_revocations` → `check_normative_confirmation_revocation()` | `auth.uid()` | `confirmation_id`, `reason` |
| F | résolution | `resolve_normative_authorisation(...)` | **aucune** — `p_user` est un paramètre | les 6 paramètres |
| G | consommation | `consume_normative_authorisation(...)` | **aucune** — `p_actor` est un paramètre | les 6 paramètres |
| H | journal normatif | `log_normative_event(...)` | **aucune** — `p_user` est un paramètre | les 5 paramètres |

**F, G et H ne dérivent aucune identité.** Ils reçoivent un UUID et le
croient. Ce n'est pas un défaut en soi : ils ne sont atteignables que depuis
les déclencheurs B à E, qui, eux, dérivent l'acteur. Leur sûreté repose donc
**entièrement sur leur ACL** — vérifiée ci-dessous — et non sur leur logique.

### 3.2 Transaction, verrouillage, audit

| # | transaction | verrous consultatifs pris | audit produit |
|---|---|---|---|
| A | celle de l'appelant | `administration` | `normative.authorisation.bootstrap`, avec `session_user` **et** `current_user` |
| B | celle de l'appelant | `grant:<grantee>:<permission>`, puis `administration` si la permission octroyée est l'administration, puis (via G) `grantrow:<id>` en **partagé** | `normative.authorisation.granted`, avec `granted_under` = snapshot de l'habilitation consommée |
| C | celle de l'appelant | `administration`, puis `grantrow:<grant_id>` en **exclusif** | oui |
| D | celle de l'appelant | via G, `grantrow:<id>` en **partagé** | oui |
| E | celle de l'appelant | via G | oui |
| F | — (`stable`, aucune écriture) | aucun | aucun |
| G | celle de l'appelant | `grantrow:<id>` en **partagé**, puis **relecture** de `normative_grant_is_active` | aucun |
| H | celle de l'appelant | aucun | c'est lui, l'audit |

**La vérification d'autorité et l'écriture sont bien dans la même
transaction** (§13 de la consigne) : B, C, D et E sont des déclencheurs
`BEFORE INSERT`, donc par construction dans la transaction de l'écriture. Le
motif « résoudre → verrouiller → relire » est centralisé dans G, et le test 14
l'a **observé fonctionner** : la session consommatrice a été vue bloquée sur le
verrou d'une révocation en vol, puis refusée après relecture.

### 3.3 La matrice de permissions SQL, mesurée

Rôles : `svc` = rôle de service applicatif (LOGIN, membre de
`normative_backend`) ; `deploy` = `eurostruct_deployment`.

| fonction | svc | backend | deploy | propriétaire | SECURITY DEFINER |
|---|---|---|---|---|---|
| `bootstrap_normative_administrator` | ✗ | ✗ | **✓** | `eurostruct_normative_bootstrap` | oui |
| `consume_normative_authorisation` | ✗ | ✗ | ✗ | `eurostruct_normative_writer` | oui |
| `log_normative_event` | ✗ | ✗ | ✗ | `eurostruct_normative_writer` | oui |
| `resolve_normative_authorisation` | ✗ | ✗ | ✗ | **le migrateur** | **non** |
| `normative_finalize_deployment` | ✗ | ✗ | **✓** | le plan de contrôle | non |

Tables (33 avec RLS activée, 23 en `FORCE`) : le rôle applicatif détient
`INSERT` et `SELECT` sur les tables d'autorité, **jamais `UPDATE` ni
`DELETE`** — mesuré par le test 10, qui reçoit « permission denied » sur les
deux. C'est le fondement de l'immuabilité, et c'est aussi pourquoi le code
verrouille par verrou consultatif plutôt que par `SELECT ... FOR UPDATE` :
`FOR UPDATE` exigerait le privilège `UPDATE` que ces tables n'accordent jamais.

> **Observation O-1, mesurée, à trancher pendant la correction.**
> `resolve_normative_authorisation` reste la propriété du **migrateur** : la
> migration ne transfère jamais sa propriété, alors qu'elle le fait pour
> `consume_normative_authorisation` et `log_normative_event`. Elle est
> `SECURITY INVOKER` et son `EXECUTE` n'est accordé qu'à
> `eurostruct_normative_writer`, donc aucun rôle applicatif ne l'atteint — mais
> elle est **dans la chaîne d'appel** du définisseur, et son propriétaire peut
> la remplacer par `CREATE OR REPLACE`. C'est du code privilégié détenu par un
> rôle non-autorité (§8 de la consigne). Ce n'est pas un rouge démontré : c'est
> un fait mesuré dont l'exploitabilité n'a pas été établie, et qui doit l'être
> avant la correction.

---

## 4. Les dix invariants

Nommés ici pour que les correctifs et les tests s'y réfèrent, et pour que
chaque assertion sache **quelle propriété elle défend**.

| id | invariant | état mesuré |
|---|---|---|
| **I-1** | Une racine de confiance **technique** ne se convertit pas en autorité **professionnelle** sans une décision tracée hors du système. | **VIOLÉ** — test 1 |
| **I-2** | L'identité de l'acteur provient d'un contexte que l'appelant ordinaire **ne peut pas substituer**. | **VIOLÉ** — test 4 |
| **I-3** | Deux « regards » exigent deux principals **authentifiés** distincts, pas deux valeurs déclarées. | **VIOLÉ** — tests 6 et 12 |
| **I-4** | Nul ne s'attribue un pouvoir à soi-même (`actor ≠ grantee`). | tenu — test 5 |
| **I-5** | `granted_scope ⊆ grantor_scope` : aucune amplification de portée. | tenu — test 7 |
| **I-6** | La portée se compare sur les **quatre** axes : pays, famille, partie, édition. | tenu — test 13 |
| **I-7** | Une autorité révoquée ne délègue plus. | tenu — test 8 |
| **I-8** | Une autorité est vérifiée et consommée **dans la transaction de l'écriture**, sous verrou, avec relecture. | tenu — test 14 |
| **I-9** | L'historique d'autorité est **immuable** pour les rôles ordinaires ; l'audit `normative.*` n'est produit que par le chemin réservé. | tenu — tests 9 et 10 |
| **I-10** | L'amorçage est **unique**, transactionnel et non rejouable ; une décision d'autorité ne se rejoue pas en doublon. | tenu — tests 2, 3 et 11 |

**Trois violés, sept tenus.** Et les trois violés n'en font qu'un et demi :
I-2 est la cause, I-3 en est la conséquence directe (le décompte à quatre yeux
compte des identifiants issus de la source falsifiable), et I-1 est un défaut
distinct — il ne dépend pas de `auth.uid()` mais du fait que `p_grantee` est
libre pour le porteur d'une identité de déploiement.

> **L'unicité n'est pas la suffisance** (§7 de la consigne). I-10 est tenu :
> l'amorçage est unique, et le test 3 l'a vérifié sous concurrence réelle. Cela
> ne dit **rien** de I-1. Un amorçage unique dont le bénéficiaire est choisi
> librement reste un amorçage arbitraire — simplement, il n'a lieu qu'une fois.

---

## 5. La sémantique de révocation A → B → C

### Ce que le code fait aujourd'hui, mesuré

```sql
create or replace function normative_grant_is_active(p_grant_id uuid)
returns boolean language sql stable as $$
  select not exists (
    select 1 from normative_authorisation_revocations r
     where r.grant_id = p_grant_id
  );
$$;
```

Un octroi est actif si **et seulement si** aucune révocation ne le vise
**lui**. Il n'existe donc **aucune transitivité** : si A délègue à B et que
l'habilitation de A est révoquée, l'habilitation de B **reste active**. Le
test 8 confirme l'autre moitié — B révoqué ne délègue plus — mais ne dit rien
de C.

Ce comportement n'est écrit nulle part comme une décision. C'est un effet de la
formulation la plus simple, pas un choix documenté.

### La sémantique retenue : **révocation non transitive, avec obligation de couverture**

Décidée ici, et ouverte à révision :

1. **Révoquer A ne révoque pas B.** Ce qui a été délégué reste valide.
2. **Raison.** Une confirmation normative déjà signée par C doit rester
   *explicable* dix ans plus tard (rétention décennale). Une cascade
   rétroactive invaliderait des signatures qui étaient régulières au moment où
   elles ont été apposées — et rendrait indéchiffrable la question « cet
   ingénieur était-il habilité ce jour-là ? », qui est exactement celle qu'un
   litige pose. La cascade détruirait la propriété que le modèle existe pour
   défendre.
3. **Contrepartie obligatoire.** Puisqu'il n'y a pas de cascade, retirer une
   autorité exige de **retirer explicitement ce qu'elle a délégué**. Cela ne
   peut pas rester à la charge de l'opérateur : il faut une **vue de
   couverture** qui, pour un octroi donné, énumère la descendance encore
   active, et un refus de révoquer tant que la descendance n'est pas traitée
   ou explicitement conservée.
4. **Ce n'est pas encore implémenté.** Aucune colonne ne relie un octroi à
   celui sous lequel il a été consenti : `granted_by` nomme la *personne*, pas
   l'*octroi*. La descendance n'est donc pas calculable aujourd'hui. Le
   snapshot `granted_under` existe dans l'audit — pas dans la table.

### Les cycles de délégation

Un cycle A → B → A est **structurellement possible** : I-4 interdit
`actor = grantee` mais rien n'interdit à B de rendre à A ce que A lui a donné.
Il n'est cependant pas *dangereux* en l'état, parce qu'aucune autorité ne se
dérive transitivement : chaque octroi est évalué seul, contre la portée de son
consentant au moment de l'octroi. Un cycle ne crée donc pas de pouvoir
supplémentaire.

Il le deviendrait dès que la couverture du point 3 existerait : une descendance
cyclique ne se parcourt pas. La prévention des cycles est donc une
**précondition de la couverture**, pas un correctif indépendant.

---

## 6. Ce que 6.3c peut fermer, et ce qui reste `BLOCKED_BY_REAL_AUTH`

Quatre notions, délibérément séparées :

| notion | qui la porte aujourd'hui | statut |
|---|---|---|
| **identité authentifiée** | rien — `auth.uid()` lit une déclaration de session | **`BLOCKED_BY_REAL_AUTH`** |
| **autorité détenue** | `normative_authorisation_grants` + portée à quatre axes | implémenté, invariants I-4 à I-7 tenus |
| **opération autorisée** | déclencheurs B–E, via `consume_normative_authorisation` | implémenté, I-8 tenu |
| **responsabilité professionnelle** | `grantee_name`, figé à l'octroi | **présent mais non distingué** de l'autorité technique — c'est I-1 |

**Ce que 6.3c ne peut pas fermer sans authentification réelle :** toute
garantie de la forme « c'est bien *cette personne* qui a signé ». La couche qui
la porterait — vérificateur de jeton, service applicatif, provider Postgres —
**n'existe pas dans ce dépôt**. Le produit doit le dire, et rester `false` en
production plutôt que simuler une authentification qu'il n'a pas.

**Ce que 6.3c peut fermer :** I-1, et la partie de I-2/I-3 qui ne dépend pas de
l'authentification — à savoir que le schéma **déclare** sa dépendance, refuse
de fonctionner quand la propriété n'est pas garantie, et ne présente jamais un
`auth.uid()` non vérifié comme une preuve d'identité.
