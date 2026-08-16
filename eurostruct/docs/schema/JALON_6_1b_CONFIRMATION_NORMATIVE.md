# Jalon 6.1b — Confirmation normative : architecture révisée

**Statut : proposition révisée. Aucune migration, aucune canonicalisation, aucun
code structurel.** Remplace le §3 à §7 du jalon 6.1 ; l'inventaire de
l'existant (6.1 §1) reste valable et n'est pas répété.

---

## 0. Ce qui change par rapport à 6.1, et pourquoi

| # | 6.1 disait | 6.1b dit | nature |
|---|---|---|---|
| 1 | `STALE` = une édition plus récente existe | `STACK_MISMATCH`, **relatif à un contexte demandé** | **erreur conceptuelle corrigée** |
| 2 | un `rule_hash` | **trois** empreintes distinctes | erreur de conception |
| 3 | citation et page dans le hash normatif | dans l'**empreinte de preuve** | arbitrage D1/D2 |
| 4 | AST = hash sémantique | AST = **contribution** à l'empreinte d'implémentation, avec fermeture | arbitrage D3 |
| 5 | JSON versionné comme seconde autorité | `ConfirmationProvider`, jamais de JSON éditable | **refus justifié** |
| 6 | `authorisations_at_signature` en contrainte | c'est une **preuve d'audit**, pas un contrôle | **faille** |
| 7 | révocation = ligne de confirmation | **table séparée** | modélisation |
| 8 | `unique (rule_id, rule_hash, revokes)` | inopérante (`NULL` distincts) | **bug SQL** |
| 9 | tableaux de chaînes pour la pile | **snapshot structuré et versionné** | modélisation |

**L'erreur n° 1 était la plus grave** : elle aurait rendu périmée une
confirmation parfaitement valide dès qu'un document plus récent entrait au
catalogue. `NBN EN 1992-1-1:2023` est déjà détenue et `not_yet_applicable` :
le schéma de 6.1 l'aurait fait invalider les six règles belges.

---

## 1. `STALE` corrigé : un état relatif, jamais intrinsèque

### 1.1 Le principe

**La nouveauté d'un document ne périme rien.** Une confirmation de l'édition
2010 reste pleinement valide pour un calcul dont la pile normative demandée
*est* celle de 2010 — ce qui reste le cas courant, un projet étant régi par le
référentiel en vigueur à sa date contractuelle, parfois pour dix ans.

L'état ne se lit donc jamais sur la confirmation seule. Il se calcule en
confrontant **la confirmation** et **le contexte demandé**.

### 1.2 D4 corrigée

- Le **catalogue ou la couche applicative** détermine la pile applicable à un
  projet. C'est là que vivent la connaissance des éditions, l'homologation au
  Moniteur belge, le `not_yet_applicable` et le retrait officiel.
- **Le moteur ne consulte jamais le catalogue.** Il n'a ni la connaissance ni
  la légitimité de décider qu'une pile est applicable.
- Le moteur **reçoit** un `NormativeContext` portant le `stack_digest` demandé.
- Il **compare** ce digest à celui de la confirmation.
- Une édition seulement *connue* ne suffit jamais à faire basculer un état.

### 1.3 Trois situations à ne pas confondre

| situation | qui le décide | ce que fait le moteur |
|---|---|---|
| **A — pile différente, toujours légitime ailleurs**<br>La confirmation atteste la pile 2010 ; le contexte demande la pile 2018. Les deux sont valides, pour des projets différents. | personne : c'est un simple écart | refuse **pour ce calcul**, en disant que la confirmation vaut pour une autre pile — qui reste valide en soi |
| **B — pile officiellement retirée ou non applicable**<br>`NBN EN 1992-1-1:2023` est publiée et sans force ; ou une édition a été retirée. | **couche applicative**, depuis le catalogue | refuse de **construire le contexte**. Le moteur ne l'apprend pas : on ne lui demande jamais un calcul sur une pile retirée |
| **C — confirmation incompatible avec la règle**<br>La règle a changé : formule, variable, unité, domaine, branche, autorité. | le moteur, par comparaison de digests | refuse, et distingue *spec* et *implémentation* |

La différence entre **A** et **C** commande l'action : **A** demande une
relecture de l'annexe pour une autre édition ; **C** demande de comprendre
pourquoi le code a changé. Les confondre, comme le faisait 6.1, ferait
chercher un défaut de code là où il faut ouvrir un document.

### 1.4 États révisés

Tous relatifs à un `NormativeContext`.

| état | déclencheur | mode strict |
|---|---|---|
| `ABSENT` | aucune confirmation pour ce `rule_id` | refusé |
| `VALID_FOR_CONTEXT` | les trois empreintes concordent avec le contexte | **autorisé** |
| `SPEC_MISMATCH` | `normative_spec_digest` différent : la règle normative a changé | refusé |
| `IMPLEMENTATION_MISMATCH` | spec identique, `implementation_digest` différent : le **code** a changé | refusé |
| `STACK_MISMATCH` | la confirmation atteste une autre pile que celle demandée (cas **A**) | refusé, sans invalider la confirmation |
| `REVOKED` | retrait explicite par un vérificateur autorisé | refusé |

`IMPLEMENTATION_MISMATCH` est nouveau et il est indispensable : sans lui, un
développeur modifiant `_nu()` sans toucher aux métadonnées laisserait la
règle `strict-ready`. C'est le risque n° 1 identifié en 6.1 §10.

---

## 2. Trois empreintes, trois objets distincts

Un seul hash mélangeait trois questions différentes.

### 2.1 `normative_spec_digest` — *quelle règle*

Ce que le pays prescrit, indépendamment de tout code.

**Inclus** : `rule_id` · `rule_type` · entrées (nom + dimension Pint, ordre
déclaré) · unité de sortie · domaine (variable, bornes, inclusivité, bornes
relatives) · branches (bornes, inclusivité, valeurs, `value_rule_id`) ·
`selector_rule_id` · `value_provenance` · **sources d'expression
structurées** (référence, couche, clause, label, effet, digest du document) ·
**autorité normative structurée** (pays, référence, édition, clause, digest) ·
**digests exacts des règles internes dont elle dépend** (D5).

**Exclus** : `description`, `notes`, `tests`, `display_unit`, `page_pdf`,
citations, pages imprimées.

### 2.2 `implementation_digest` — *quel code l'exécute*

**D3 corrigée : l'AST du seul corps de fonction est insuffisant.** Il ignore
tout ce qui l'entoure et qui change pourtant le résultat.

La **fermeture** couverte doit inclure, transitivement :

| dépendance | pourquoi elle change le résultat |
|---|---|
| AST du corps de l'implémentation | la mathématique elle-même |
| constantes de module référencées | `_COT_CAP = 3.0` → `3.5` |
| fonctions auxiliaires appelées | une aide partagée modifiée |
| **règles internes** (`selector`, branches) via leur propre `implementation_digest` | D5 : digests exacts, pas `rule_id` |
| valeurs importées d'autres modules | une constante d'unités |
| valeurs par défaut des paramètres | un défaut déplacé |
| décorateurs et mécanismes altérant l'évaluation | un cache, une conversion |

**Méthode proposée** : parcourir l'AST, collecter les noms globaux résolus,
récurser sur les fonctions et constantes atteintes, et **refuser de calculer
l'empreinte** si le parcours rencontre quelque chose qu'il ne peut pas
résoudre statiquement — appel indirect, attribut dynamique, fermeture non
statique.

Ce refus est le point important : une fermeture incomplète produirait une
empreinte qui *paraît* couvrir le code sans le couvrir, ce qui est pire que
pas d'empreinte du tout.

**Limite assumée** : la fermeture statique ne couvre pas un comportement
dépendant de l'environnement (variable d'environnement, horloge, aléa). Le
moteur est déterministe par construction et les tests le vérifient déjà
(`test_determinism`) ; c'est cette propriété-là qui rend la fermeture
suffisante, et elle doit être citée comme prémisse.

**D3, noms locaux** : pas de normalisation en première version. Un renommage
`fck` → `f` cassera l'empreinte inutilement ; c'est le faux positif accepté,
préférable au risque de masquer une permutation de deux variables.

### 2.3 `evidence_digest` — *ce que le vérificateur a lu*

**D1 corrigée** : la citation n'appartient pas à la spécification. Corriger
une virgule dans une transcription ne change pas la mathématique — mais
modifier la preuve après signature doit rester détectable. Elle appartient
donc ici.

**D2 corrigée** : `page_printed` appartient ici, **avec le document auquel
elle se rapporte**. `pages_read: tuple[int, ...]` était ambigu dès que
plusieurs documents sont ouverts — et ils le sont toujours : base, corrigenda,
amendement, annexe.

Structure remplaçant les entiers nus :

```python
@dataclass(frozen=True, slots=True)
class EvidenceItem:
    document_digest: str        # sha256 du fichier ouvert
    document_role: str          # base | corrigendum | amendement | annexe | reglement
    reference: str              # 'NBN EN 1992-1-1 ANB'
    edition: str                # '2010'
    clause: str                 # '§6.2.2(6)'
    page_printed: int           # le folio, ce qu'un ingenieur rouvre
    page_pdf: int | None        # aide de navigation, sans autorite
    quote: str                  # ce qu'il declare avoir lu
    quote_digest: str           # pour detecter une retouche apres signature
```

### 2.4 Ce que chaque empreinte protège

| empreinte | protège contre |
|---|---|
| `normative_spec_digest` | qu'une règle change de sens sans nouvelle lecture |
| `implementation_digest` | qu'un développeur change le calcul sans que rien ne le signale |
| `evidence_digest` | qu'une preuve soit retouchée après signature |

Le mode strict exige **les trois**.

### 2.5 Enveloppe commune à toute empreinte

```python
@dataclass(frozen=True, slots=True)
class Digest:
    algorithm: str                 # 'sha256'
    canonicalization_version: str  # 'esc-canon/1'
    canonical_payload: str         # conservé, pas seulement hashé
    digest: str
```

*« Un hash seul ne suffit pas pour comprendre, dix ans plus tard, ce qui a été
signé. »* Le payload canonique est **conservé ou référencé durablement**. Une
version de canonicalisation permet de faire évoluer la méthode sans rendre
illisibles les confirmations anciennes.

---

## 3. `NormativeContext` — ce que le moteur reçoit

```python
@dataclass(frozen=True, slots=True)
class NormativeStackComponent:
    role: str                   # base | corrigendum | amendement | annexe | reglement
    reference: str
    edition: str
    application_order: int      # l'ordre EST normatif
    document_digest: str

@dataclass(frozen=True, slots=True)
class NormativeStack:
    """Snapshot structuré et versionné. §9 de la demande."""
    schema_version: str                      # 'esc-stack/1'
    country_code: str
    standard_family: str
    part: str
    components: tuple[NormativeStackComponent, ...]   # ordonnés
    # Calculé DEPUIS cette structure, jamais depuis des tableaux de chaînes
    # dont le sens dépendrait de la position.
    digest: Digest

@dataclass(frozen=True, slots=True)
class NormativeContext:
    """Fourni au calcul par la couche applicative. Le moteur ne le fabrique pas.

    Il ne porte NI project_id NI org_id: la pile applicable est une propriété
    de la juridiction et de la date, pas du client.
    """
    stack: NormativeStack
    as_of: date
    strict: bool
```

Le moteur reçoit ce contexte, compare `context.stack.digest.digest` au
`stack_digest` de la confirmation, et n'interroge jamais le catalogue.

---

## 4. `ConfirmationProvider` — D7 corrigée

**Le JSON éditable dans le dépôt est refusé.** Vos cinq objections sont
retenues, et la cinquième est décisive : un environnement lancé par erreur
sur la mauvaise source rendrait des règles réelles `strict-ready`.

```python
class ConfirmationProvider(Protocol):
    """Le moteur ignore d'où viennent les confirmations."""

    def confirmations_for(self, rule_id: str) -> tuple[NormativeRuleConfirmation, ...]:
        ...

    @property
    def provider_identity(self) -> str:
        """Inscrit dans la trace du calcul: on doit savoir qui a répondu."""
```

| environnement | provider | autorité |
|---|---|---|
| production SaaS | `PostgresConfirmationProvider` | **PostgreSQL** |
| tests | `InMemoryConfirmationProvider` | fixtures **explicitement fictives** |
| hors ligne, plus tard | `SignedManifestProvider` | manifeste **immuable et signé**, exporté depuis l'autorité, avec digest, signature, date d'export et identité de l'émetteur |

**Deux règles non négociables :**

1. **Aucune sélection implicite.** La présence simultanée de deux providers
   est un refus de configuration, pas un arbitrage automatique.
2. **Aucun fichier éditable du dépôt ne peut rendre une règle réelle
   `strict-ready`.** Les fixtures de test portent des identités visiblement
   fictives, et un test le vérifie.

---

## 5. Autorisation du vérificateur — la faille, et sa correction

Vous avez raison, et c'est bloquant : `authorisations_at_signature` fourni
par l'appelant, avec une contrainte SQL qui vérifie seulement que le tableau
contient la chaîne attendue, laisse **l'acteur se déclarer lui-même
autorisé**. C'est une preuve d'audit présentée comme un contrôle.

### 5.1 Source d'autorité

```sql
create table normative_authorisations (
  id            uuid primary key default gen_random_uuid(),
  grantee_id    uuid not null references auth.users(id),
  authorisation text not null,        -- 'can_validate_normative_reference'

  -- Portée. NULL = toutes les valeurs de cet axe.
  country_code    country_code,
  standard_family text,
  part            text,
  edition         text,

  granted_by    uuid not null references auth.users(id),
  granted_at    timestamptz not null default now(),
  revoked_by    uuid references auth.users(id),
  revoked_at    timestamptz,

  constraint revocation_is_dated check (
    (revoked_by is null) = (revoked_at is null)
  )
);
```

La portée par pays / norme / partie / édition est prévue dès maintenant : un
relecteur habilité sur l'EC2 belge ne l'est pas nécessairement sur l'EC8
espagnol.

### 5.2 Le contrôle est côté serveur, la copie est une conséquence

Trigger `before insert` sur les confirmations :

1. **résout** l'autorisation dans `normative_authorisations` pour
   `verifier_id`, active au moment de l'insertion, et couvrant la portée de
   la règle confirmée ;
2. **lève** si elle est absente, révoquée ou hors portée ;
3. **écrit lui-même** `authorisations_at_signature` et
   `authorisation_scope_at_signature` depuis ce qu'il a résolu.

**Le client ne fournit jamais ces colonnes.** Elles sont en écriture serveur,
comme `validator_role` l'est déjà dans `check_validator_is_authorised()`
(0009). Le précédent existe, et son avertissement aussi : cette fonction doit
être réécrite **en entier** si elle est remplacée, sous peine de perdre en
silence des comportements existants — c'est déjà arrivé une fois.

**Côté moteur, sans base** : le `ConfirmationProvider` est la frontière. Le
moteur ne vérifie pas une autorisation, il consomme des confirmations dont le
provider garantit qu'elles ont été produites sous contrôle. Le provider
PostgreSQL le garantit par le trigger ; le provider mémoire ne produit que du
fictif ; le manifeste signé le garantira par sa signature.

---

## 6. Révocation — table séparée, D7 §7

Une révocation n'est pas une confirmation. Exiger d'elle des pages lues et une
citation serait absurde.

```sql
create table normative_rule_confirmation_revocations (
  id              uuid primary key default gen_random_uuid(),
  confirmation_id uuid not null unique
                  references normative_rule_confirmations(id) on delete restrict,
  revoked_by      uuid not null references auth.users(id),
  revoked_by_name text not null,
  revoked_at      timestamptz not null default now(),
  authorisations_at_revocation text[] not null,   -- écrit par le trigger
  reason          text not null,
  created_at      timestamptz not null default now(),

  constraint revocation_is_motivated check (length(btrim(reason)) > 0)
);
```

`unique (confirmation_id)` : une confirmation se révoque une fois.
`on delete restrict` : la confirmation révoquée **reste en base**, lisible,
comme un livrable final erroné le reste (0003).

Immuabilité par `forbid_mutation()` (0003), sans nouveau mécanisme.

---

## 7. Unicité — le bug, et la question qu'il ne faut pas verrouiller

### 7.1 Le bug

`unique (rule_id, rule_hash, revokes)` **n'empêche rien** : `revokes` valait
`NULL` sur toute confirmation ordinaire, et PostgreSQL traite les `NULL`
comme distincts dans une contrainte unique. Deux confirmations identiques
passaient.

### 7.2 La question à ne pas trancher par accident

EuroStruct exigera-t-il un jour **un seul** vérificateur, ou une validation
**à quatre yeux** — plusieurs confirmations indépendantes de la même règle ?

Le domaine plaide pour la seconde : une valeur nationale erronée se propage à
toutes les études de la juridiction, et le double contrôle est l'usage dans
les bureaux d'études. Mais **je ne tranche pas**, et surtout je ne veux pas
que le schéma le tranche en silence.

### 7.3 Proposition

Un index partiel qui empêche le **doublon** sans interdire le **second
regard** :

```sql
create unique index normative_confirmation_one_per_verifier
  on normative_rule_confirmations (rule_id, normative_spec_digest, verifier_id)
  where id not in (select confirmation_id
                   from normative_rule_confirmation_revocations);
```

*(la sous-requête n'est pas admise dans un index ; l'implémentation réelle
passera par une colonne `is_revoked` maintenue par trigger — détail à régler
en 6.3, la propriété visée étant celle-ci.)*

**La même personne ne signe pas deux fois la même règle. Deux personnes le
peuvent.** Le nombre de confirmations *exigé* devient alors une **politique**,
lue par le mode strict, et non une contrainte de schéma :

```python
@dataclass(frozen=True, slots=True)
class ConfirmationPolicy:
    minimum_independent_confirmations: int = 1   # 2 = quatre yeux
```

Le schéma reste ouvert ; la décision se prend ailleurs et peut changer.

---

## 8. Schéma de confirmation révisé

```python
@dataclass(frozen=True, slots=True)
class NormativeRuleConfirmation:
    confirmation_id: str

    # --- quelle règle, dans quelle pile ----------------------------------
    country_code: str
    standard_family: str
    part: str
    rule_id: str

    # --- les trois empreintes, payload conservé ---------------------------
    normative_spec: Digest
    implementation: Digest
    evidence: Digest

    # --- la pile attestée, structurée --------------------------------------
    stack: NormativeStack          # porte son propre Digest

    # --- qui, quand -------------------------------------------------------
    verifier_id: str
    verifier_name: str             # lisible dans dix ans
    verified_at: str
    # Écrits par le serveur depuis normative_authorisations. JAMAIS fournis
    # par l'appelant. Preuve d'audit, pas contrôle d'accès.
    authorisations_at_signature: frozenset[str]
    authorisation_scope_at_signature: str
    verifier_affiliation: str | None   # audit seulement, jamais une validation projet

    # --- ce qui a été lu ---------------------------------------------------
    evidence_items: tuple[EvidenceItem, ...]
    statement: str                 # sa phrase, pas un gabarit
```

Toujours **ni `project_id` ni `org_id`** (§10 de la demande, approuvé).
`verifier_affiliation` est conservée pour l'audit et n'ouvre aucun droit sur
un projet : elle n'est lue par aucun contrôle.

---

## 9. D5, D6, D8 — retenues, avec la précision demandée

**D5** — les règles internes (`sigma_cp_over_fcd`, `alpha_cw_linear`,
`alpha_cw_decreasing`) ne sont pas confirmées séparément. **Mais le digest du
parent inclut les digests exacts de ses dépendances**, pas leurs `rule_id` :
sans cela, modifier `alpha_cw_linear` laisserait `alpha_cw` confirmée.

**D6** — aucune expiration calendaire. L'invalidité vient d'une
incompatibilité, d'une révocation, ou du contexte demandé.

**D8** — la version du moteur n'entre dans aucune empreinte normative. Elle
apparaît **dans la trace de chaque calcul, avec l'`implementation_digest`**,
pour que l'exécution soit reproductible. `engine_versions` existe déjà en base
et `ENGINE_VERSION` dans le code.

---

## 10. Questions réellement ouvertes

| # | question | pourquoi elle n'est pas tranchée ici |
|---|---|---|
| **Q1** | Un seul vérificateur ou quatre yeux ? | décision produit et assurantielle. §7.3 laisse le schéma ouvert |
| **Q2** | La fermeture statique de l'`implementation_digest` peut-elle être complète en Python ? | à établir sur les six règles réelles en 6.2. Le refus explicite (§2.2) est la porte de sortie si elle ne l'est pas |
| **Q3** | Où sont archivés les payloads canoniques ? colonne, table dédiée, stockage objet ? | dépend du volume ; sans effet sur le modèle |
| **Q4** | Le manifeste hors ligne signé — quel format, quelle clé, quelle rotation ? | hors 6.x, à ouvrir quand un besoin hors ligne réel existera |
| **Q5** | La portée d'autorisation par édition est-elle utile en pratique ? | prévue au schéma, coût nul ; à confirmer avec un usage réel |
| **Q6** | Qui accorde `can_validate_normative_reference` en premier ? | amorçage : la première autorisation ne peut pas être accordée par un autorisé. À traiter en 6.3 |

**Q6 est le plus concret** et je n'y ai pas de bonne réponse : toute chaîne
d'autorisation a une racine, et elle sera posée par migration ou par un
administrateur de plateforme — ce qui touche à la frontière que nous avons
justement voulu étanche.

---

## 11. Risques restants

| risque | portée | atténuation |
|---|---|---|
| Fermeture d'implémentation incomplète | **grave** : une empreinte qui paraît couvrir le code sans le couvrir | refus explicite de calculer l'empreinte si un nœud n'est pas résoluble (§2.2) |
| Amorçage de l'autorisation (Q6) | contourne le contrôle qu'on vient d'établir | à traiter explicitement en 6.3, pas par défaut |
| Deux providers actifs | une règle réelle rendue `strict-ready` par erreur | refus de configuration, jamais d'arbitrage automatique (§4) |
| Payload canonique perdu | illisibilité à dix ans | conservation obligatoire, `canonicalization_version` |
| Le trigger d'autorisation réécrit sans reprendre l'existant | perte silencieuse de comportements | le précédent de 0009 est documenté ; à citer dans la migration |

---

## 12. Bilan du jalon 6.1b

- **Fichiers modifiés** : aucun. Un document ajouté.
- **Tests ajoutés** : aucun.
- **Résultat des tests** : inchangé — **727 moteur, 88 import**, tous verts.
- **Migration** : aucune.
- **Canonicalisation** : non commencée.

**En attente** : approbation du schéma révisé, et arbitrage de **Q1** (un
vérificateur ou quatre yeux) et **Q6** (amorçage de l'autorisation), qui
touchent tous deux 6.3. Le jalon 6.2 peut en revanche démarrer sans eux : la
canonicalisation ne dépend d'aucune des deux.
