# Jalon 6.1 — Confirmation normative des `NormativeRule` : analyse et schéma

**Statut : proposition. Aucune modification structurelle n'a été faite.**
Livraison d'analyse uniquement, en attente de contrôle.

---

## 1. Ce qui existe déjà, et qu'il faut réutiliser

L'architecture porte déjà l'essentiel. Rien de ce qui suit n'est à inventer.

### 1.1 Les trois niveaux sont déjà codifiés

`validation_levels.py` et les commentaires de `0009_validation_authorisation.sql`
disent la même chose, indépendamment :

| niveau | question | acteur | table / type |
|---|---|---|---|
| 1 NORMATIVE | la valeur est-elle celle du pays ? | `NormativeVerifier` | `national_annex_parameters.verified_by`, `ndp_review_decisions` |
| 2 ENGINEERING | qui répond du calcul ? | `ProjectValidatingEngineer` | `validations` + `check_validator_is_authorised()` |
| 3 ISSUANCE | le document peut-il sortir ? | machine à états | `deliverable_state_transitions` |

**Le niveau 1 existe déjà pour les *paramètres*. Il n'existe pas pour les
*règles*.** C'est exactement le trou à combler.

### 1.2 Précédents directement transposables

**`ndp_review_decisions` (0006)** — la forme d'une confirmation normative,
déjà écrite :

```sql
verified_by      uuid not null references auth.users(id),
verified_by_name text not null,   -- « pas seulement son identifiant technique »
verified_at      timestamptz not null default now(),
source_page      integer,         -- la page RÉELLEMENT lue
constraint accepted_decision_carries_its_evidence check (...)
```

Le commentaire de la colonne dit pourquoi le nom est stocké en clair :
*« c'est lui qui engage sa responsabilité, et le nom doit rester lisible dix
ans plus tard »*. La même logique s'applique ici.

**`national_annex_parameters.confirmed_ndp_is_signed` (0004)** — le motif de
contrainte :

```sql
constraint confirmed_ndp_is_signed check (
  validation_status <> 'confirmed'
  or (verified_by is not null and verified_at is not null
      and source_type = 'national_annex')
)
```

Confirmer exige de dire **qui**, **quand**, et que la valeur vienne **de
l'annexe**. Transposable tel quel.

**`forbid_mutation()` + `validations_are_immutable` (0003)** — l'immuabilité
est déjà un trigger générique. Une confirmation s'y branche sans nouveau
mécanisme.

**`organization_members.is_active` / `deactivated_at` (0009)** — le précédent
exact pour « les confirmations passées restent lisibles, on n'en produit plus » :
la ligne survit, le droit disparaît.

**`audit_log`** — `action / entity / entity_id / payload / occurred_at`.
Une confirmation, une révocation et une invalidation y écrivent.

### 1.3 Une asymétrie qu'il faut nommer

| | définition | confirmation |
|---|---|---|
| `NationalParameter` | **donnée** (`be.json`, table SQL) | donnée |
| `NormativeRule` | **code** (`rules_be_ec2.py`) | donnée |

Un paramètre et sa confirmation vivent au même endroit. **Une règle est du
code**, et sa confirmation sera de la donnée. C'est voulu — c'est la
conséquence directe du « pas d'`eval` » — mais cela déplace le problème :
rien n'empêche un développeur de modifier `_nu()` et de laisser la
confirmation en base.

**C'est précisément ce que le hash sémantique doit rendre impossible**, et
c'est pourquoi il doit couvrir la mathématique elle-même, pas seulement les
métadonnées. Voir §5.

---

## 2. Séparation entre confirmation normative et validation projet

Elle est déjà acquise dans les types ; ce schéma ne doit pas la desserrer.

| | confirmation normative | validation projet |
|---|---|---|
| **objet** | une règle, une édition | une étude, un projet |
| **acteur** | `NormativeVerifier` | `ProjectValidatingEngineer` |
| **autorisation** | `can_validate_normative_reference` | rôle `validating_engineer` |
| **organisation** | **aucune** | celle du projet, obligatoire |
| **portée d'une erreur** | toutes les études de la juridiction, tous les locataires | une étude |
| **table** | `normative_rule_confirmations` (nouvelle) | `validations` (existante) |
| **jamais** | ne signe un projet | ne confirme le référentiel |

**Aucun projet client n'intervient.** La table proposée n'a ni `project_id`
ni `org_id` — non par omission, mais pour que la question ne puisse pas se
poser.

---

## 3. États d'une confirmation

Cinq états, et chacun a un déclencheur distinct.

| état | signification | déclencheur | mode strict |
|---|---|---|---|
| `ABSENT` | aucune confirmation pour ce `rule_id` | — | refusé |
| `VALID` | confirmation dont le hash **égale** celui de la règle courante | — | **autorisé** |
| `INCOMPATIBLE` | confirmation existante, hash **différent** | la règle a changé : formule, variable, unité, domaine, branche, source, autorité, édition | refusé |
| `STALE` (périmée) | hash inchangé, mais la **pile documentaire** a bougé | une édition postérieure de l'annexe ou d'une source est connue au catalogue | refusé |
| `REVOKED` | retirée explicitement par un vérificateur autorisé | un relecteur découvre une erreur de lecture | refusé |

### Pourquoi `STALE` n'est pas redondant avec `INCOMPATIBLE`

`INCOMPATIBLE` est **interne** : la règle a changé, donc son hash a changé.
`STALE` est **externe** : la règle n'a pas bougé, le monde si.

Le cas réel est déjà dans le dépôt : `NBN EN 1993-1-1 ANB:2018` remplace
l'édition de décembre 2010. Le jour où cela vaudra pour l'EC2, la règle
déclarera toujours `edition="2010"` — hash inchangé — alors que la
confirmation atteste d'une édition remplacée. Une relecture est due, mais
**aucune ligne de code n'a changé** : confondre les deux ferait chercher un
défaut de code là où il faut acheter et lire un document.

### `REVOKED` — pourquoi la prévoir

Un vérificateur peut découvrir qu'il a mal lu. Sans révocation, la seule
sortie serait de modifier la règle pour casser le hash — c'est-à-dire de
falsifier la règle pour corriger une signature.

**Aucune confirmation n'est jamais supprimée.** Une révocation est une
nouvelle ligne qui référence l'ancienne ; l'historique reste entier, comme
pour un livrable final erroné qui reste en base.

---

## 4. Schéma proposé

### 4.1 Côté moteur (Python)

```python
# ndp/confirmation.py — NOUVEAU

class ConfirmationState(str, Enum):
    ABSENT = "absent"
    VALID = "valid"
    INCOMPATIBLE = "incompatible"
    STALE = "stale"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class NormativeRuleConfirmation:
    """Immuable. Une correction est une nouvelle ligne, jamais une mutation."""

    confirmation_id: str
    # --- ce qui identifie la règle confirmée -------------------------------
    country_code: str                  # 'BE'
    standard_family: str               # 'EN 1992'
    part: str                          # '1-1'
    annex_edition: str                 # '2010'
    rule_id: str                       # 'be.ec2.nu_strength_reduction'
    rule_hash: str                     # sha256 canonique, §5
    # --- la pile documentaire attestée ------------------------------------
    expression_source_digests: tuple[str, ...]   # sha256, ordre déclaré
    normative_authority_digest: str
    stack_digest: str                  # hash des deux ci-dessus, pour STALE
    # --- qui, quand -------------------------------------------------------
    verifier_id: str
    verifier_name: str                 # lisible dans dix ans
    verified_at: str                   # ISO 8601
    authorisations_at_signature: frozenset[str]  # figées, comme validator_role
    # --- ce que le vérificateur déclare avoir fait -------------------------
    pages_read: tuple[int, ...]        # folios réellement ouverts
    statement: str                     # sa phrase, pas un gabarit
    # --- révocation -------------------------------------------------------
    revokes: str | None = None         # confirmation_id révoquée
    revocation_reason: str | None = None
```

### 4.2 Côté base (SQL)

```sql
-- db/migrations/0010_normative_rule_confirmations.sql — NOUVEAU

create table normative_rule_confirmations (
  id            uuid primary key default gen_random_uuid(),

  country_code  country_code not null,
  standard_family text not null,
  part          text not null,
  annex_edition text not null,
  rule_id       text not null,
  rule_hash     text not null,

  expression_source_digests text[] not null,
  normative_authority_digest text not null,
  stack_digest  text not null,

  verifier_id   uuid not null references auth.users(id),
  verifier_name text not null,
  verified_at   timestamptz not null default now(),
  authorisations_at_signature text[] not null,

  pages_read    integer[] not null,
  statement     text not null,

  revokes           uuid references normative_rule_confirmations(id),
  revocation_reason text,

  created_at    timestamptz not null default now(),

  -- Motif repris de confirmed_ndp_is_signed (0004): confirmer exige de dire
  -- qui, quand, et sur quelle preuve.
  constraint confirmation_carries_its_evidence check (
    length(btrim(verifier_name)) > 0
    and length(btrim(statement)) > 0
    and array_length(pages_read, 1) >= 1
    and 'can_validate_normative_reference' = any(authorisations_at_signature)
  ),

  -- Une révocation dit pourquoi; une confirmation ne révoque rien par défaut.
  constraint revocation_is_motivated check (
    (revokes is null and revocation_reason is null)
    or (revokes is not null and length(btrim(revocation_reason)) > 0)
  ),

  -- Deux confirmations valides pour le même (règle, hash) n'ont pas de sens.
  unique (rule_id, rule_hash, revokes)
);

-- Immuabilité: réutilise forbid_mutation() de 0003, sans nouveau mécanisme.
create trigger normative_confirmations_are_immutable
  before update or delete on normative_rule_confirmations
  for each row execute function forbid_mutation();
```

Pas de `project_id`, pas de `org_id` : la séparation est structurelle.

---

## 5. Périmètre du hash — proposition, à arbitrer

### 5.1 Inclus (change le sens ou l'applicabilité)

| champ | pourquoi |
|---|---|
| `rule_id`, `rule_type` | identité |
| `inputs` : nom + dimension Pint | changer une unité change la règle |
| `output_unit` | idem |
| `domain` : variable, bornes, inclusivité, bornes relatives | rétrécir un domaine change ce qui est refusé |
| `branches` : bornes, inclusivité, valeurs, `value_rule_id` | une branche déplacée est une autre règle |
| `selector_rule_id` | — |
| `expression_sources` : référence, couche, clause, label, effet, **digest du document** | changer de source change la règle |
| `normative_authority` : pays, référence, édition, clause, **citation**, digest | l'autorité fait l'applicabilité |
| `value_provenance` | `COMPOSED` vs `NATIONAL_ANNEX` change ce qu'on affirme |
| **AST de l'implémentation** | voir 5.3 |

### 5.2 Exclus (aucun effet normatif)

`description`, `notes`, `tests`, `display_unit`, `page_pdf`.

### 5.3 La mathématique — le point délicat

La formule est du Python. Hasher le texte source ferait changer le hash à
chaque reformatage ou correction de commentaire ; ne pas le hasher du tout
laisserait changer `0,6` en `0,61` sans invalider la confirmation.

**Proposition : hasher l'AST normalisé du corps de l'implémentation**
(`ast.dump(ast.parse(source))` après retrait du docstring).

- `0.6` → `0.61` : **change** l'AST ✓
- reformatage, commentaire, renommage d'une variable locale : **ne change
  pas** l'AST si l'on normalise aussi les noms locaux (à décider — voir D3)
- changement d'ordre d'opérations : **change** ✓

C'est un compromis assumé, et il doit être testé dans les deux sens.

---

## 6. Fichiers à modifier

| fichier | nature | jalon |
|---|---|---|
| `engine/src/eurostruct_engine/ndp/confirmation.py` | **nouveau** — états, dataclass, canonicalisation, hash | 6.2 / 6.3 |
| `engine/src/eurostruct_engine/ndp/rules.py` | ajout : `semantic_hash`, `confirmation_state()`, sans toucher à l'évaluation | 6.2 |
| `engine/src/eurostruct_engine/ndp/__init__.py` | exports | 6.2 |
| `engine/src/eurostruct_engine/validation_levels.py` | réutilisé tel quel — `NormativeVerifier`, `verifier_may_validate_reference` | — |
| `engine/src/eurostruct_engine/exceptions.py` | nouvelles erreurs structurées du mode strict | 6.5 |
| `engine/src/eurostruct_engine/ec2/beam_shear.py` | mode strict : dépendances réellement utilisées | 6.5 |
| `engine/src/eurostruct_engine/ndp/readiness.py` | **nouveau** — readiness calculée | 6.6 |
| `db/migrations/0010_normative_rule_confirmations.sql` | **nouveau** | 6.3 |
| `engine/tests/test_rule_confirmation.py` | **nouveau** | 6.2 → 6.4 |
| `engine/tests/test_readiness.py` | **nouveau** | 6.6 |

**Aucune règle n'est touchée. Aucune confirmation n'est créée.**

---

## 7. Décisions techniques restant à prendre

| # | question | proposition | enjeu |
|---|---|---|---|
| **D1** | La citation (`quote`) est-elle dans le hash ? | **oui** | la citation est la preuve ; la changer signifie que la lecture a changé |
| **D2** | `page_printed` dans le hash ? | **oui**, `page_pdf` non | le folio est ce qu'un ingénieur rouvre ; l'index PDF est un artefact de fichier |
| **D3** | Normaliser les noms de variables locales dans l'AST ? | **non** | renommer `fck` en `f` sans changer le calcul casserait le hash — mais normaliser masquerait un échange de deux variables. Le faux positif est le risque acceptable |
| **D4** | Qui déclare l'état `STALE` ? | le moteur, en comparant `stack_digest` au catalogue | crée un couplage moteur → catalogue qui n'existe pas encore. **Alternative** : état calculé hors moteur et fourni. À trancher |
| **D5** | Les règles internes (`alpha_cw_linear`, `sigma_cp_over_fcd`) sont-elles confirmables séparément ? | **non** : le hash d'`alpha_cw` inclut celui de ses branches | sinon 9 confirmations au lieu de 6, dont 3 sans existence normative propre |
| **D6** | Une confirmation porte-t-elle une date de fin ? | **non** | l'expiration viendrait d'un nouveau document, pas d'un calendrier. `STALE` couvre le besoin |
| **D7** | Où vit la confirmation en l'absence de base de données ? | fichier JSON versionné, `ndp/data/confirmations_be.json` | le moteur tourne aujourd'hui sans base ; les tests ne doivent pas exiger PostgreSQL |
| **D8** | Le hash inclut-il la version du moteur ? | **non** | un changement de moteur qui ne change pas la règle ne doit pas invalider une lecture d'annexe |

**D4 et D7 sont les deux qui engagent l'architecture.** Les autres sont
locales et réversibles.

---

## 8. Ce qui a été vérifié pour ce jalon

- Les 9 migrations SQL ont été lues ; 24 tables recensées.
- Les mécanismes réutilisés existent et ont été lus dans leur texte :
  `forbid_mutation()` (0003), `confirmed_ndp_is_signed` (0004),
  `check_validator_is_authorised()` (0009), `ndp_review_decisions` (0006),
  `audit_log` (0001), `organization_members.is_active` (0009).
- La séparation des trois niveaux est déjà écrite, deux fois et
  indépendamment : dans `validation_levels.py` et dans l'en-tête de 0009.
- **Aucune table ne porte aujourd'hui de `NormativeRule`** : les règles
  n'existent qu'en Python. C'est le fait qui commande le §5.

## 9. Hypothèses restantes

1. `auth.users` est le référentiel d'identité (Supabase). Le schéma le
   suppose, comme les tables existantes.
2. Les autorisations (`can_validate_normative_reference`) n'ont **pas encore
   de table**. Elles existent en Python (`NormativeVerifier.authorisations`)
   et sont figées à la signature dans la proposition. Une table
   d'autorisations sera nécessaire pour une application réelle — hors périmètre
   de ce jalon, à ouvrir séparément.
3. Le moteur tourne sans base de données. D7 en découle.

## 10. Risques

| risque | portée | atténuation proposée |
|---|---|---|
| Un développeur modifie une implémentation sans que le hash bouge | **grave** — une règle fausse serait strict-ready | AST dans le hash (§5.3), testé dans les deux sens en 6.2 |
| Le hash bouge à chaque reformatage | usure : les vérificateurs re-signent sans raison | AST plutôt que texte ; D3 |
| `STALE` jamais déclenché faute de couplage au catalogue | une édition remplacée resterait confirmée | D4 à trancher avant 6.5 |
| Deux sources de vérité (JSON et SQL) divergent | traçabilité | D7 : une seule source, la base quand elle existe, le JSON sinon, jamais les deux ensemble |

---

## En attente

Contrôle du schéma, et arbitrage de **D1 à D8** — en particulier **D4**
(qui déclare `STALE`) et **D7** (persistance sans base). Le jalon 6.2 ne
démarre pas avant.
