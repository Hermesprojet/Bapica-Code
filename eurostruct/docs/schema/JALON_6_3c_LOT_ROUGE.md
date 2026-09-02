# 6.3c — premier lot : cartographie et preuves rouges

Rapport de fin de lot. Il ne présente **aucun correctif** : le lot s'arrête,
comme demandé, après la cartographie et l'obtention des preuves rouges.

---

## 1. Point de départ

| élément | valeur |
|---|---|
| branche de travail | `claude/wip-6.3c-racine-de-confiance` |
| SHA de départ | `e11a62a` (cartographie initiale) |
| SHA de clôture 6.3b6e | `d04abf0` |
| SHA du checkpoint rouge | **`4c1966b`** |
| `git status --porcelain` au départ | vide |
| worktree adverse | `/tmp/esc-cablage`, jetable, détaché de `e11a62a` |

### La base réellement validée

**Correction de méthode.** Le premier rapport ne comparait que
`5d77933..3d1bd56` et présentait ce résultat comme la validation de la base de
6.3c. C'était insuffisant : la branche ne part pas de `3d1bd56` mais de
`e11a62a`, et deux commits séparent les deux. Le segment manquant est
maintenant vérifié.

```
$ git merge-base --is-ancestor 3d1bd56 e11a62a   →  code 0 (ancêtre confirmé)

$ git diff --name-status 5d77933..3d1bd56
M  eurostruct/docs/schema/JALON_6_3b6e_BARRIERE_DE_VIVACITE.md

$ git diff --name-status 3d1bd56..e11a62a
M  eurostruct/docs/schema/JALON_6_3b6e_BARRIERE_DE_VIVACITE.md
A  eurostruct/docs/schema/JALON_6_3c_CARTOGRAPHIE_DE_CONFIANCE.md

$ git log --oneline 3d1bd56..e11a62a
e11a62a docs(6.3c): cartographie de la frontiere de confiance…
d04abf0 docs: les deux verifications de cloture…
```

| segment | fichiers | classement |
|---|---|---|
| `5d77933..3d1bd56` | 1 | **documentaire** |
| `3d1bd56..e11a62a` | 2, tous deux sous `docs/schema/` | **documentaire** |
| `e11a62a..43bf497` | harnais + câblage `run.sh` + 2 docs | **fonctionnel — introduit par 6.3c lui-même** |

La chaîne est **linéaire, sans fusion** (`git log --merges 5d77933..HEAD` est
vide). Aucun fichier exécutable, script, test, workflow ou configuration
fonctionnelle **préexistant** ne diffère entre le SHA de campagne et
l'ouverture de 6.3c. Le seul endroit du dépôt qui cite le document modifié est
un commentaire d'en-tête (`db/test/gate_protocol_selftest.sh:32`), qui n'en
consomme pas le contenu.

**Conclusion : pas de rejeu de la matrice de clôture 6.3b6e.** La condition
posée n'est pas remplie sur les deux segments antérieurs à 6.3c.

---

## 2. Le modèle d'authentification réel

**Il n'y en a pas.** C'est le résultat central de ce lot, et il doit être dit
sans atténuation.

```sql
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;
```

`request.jwt.claim.sub` est un paramètre de configuration à nom qualifié.
PostgreSQL laisse **tout rôle** le positionner par un simple `SET`, sans
privilège. `auth.uid()` ne prouve donc rien : il **rapporte ce que la session a
déclaré**.

Ce que PostgreSQL peut réellement authentifier ici :

| mécanisme | authentifie | ne dit rien de |
|---|---|---|
| `session_user` | le rôle **connecté** | l'utilisateur métier |
| `current_user` | le rôle **effectif** (le propriétaire dans un `SECURITY DEFINER`) | l'appelant |
| appartenance de rôle (`pg_has_role`) | une capacité de **déploiement / service** | une personne |
| `auth.uid()` | **rien** | tout le reste |

**Modèle de connexion.** Une seule couche existe : PostgreSQL. Il n'y a dans ce
dépôt **ni route API, ni service applicatif, ni `PostgresConfirmationProvider`,
ni CLI d'autorité**. La couche qui vérifierait un jeton avant de poser le GUC
n'existe pas. La garantie repose donc entièrement sur une propriété **absente
du dépôt** : que seul un vérificateur de jeton détienne la connexion. Rien dans
le schéma ne la défend, et — c'est le point aggravant — rien ne la **déclare**.

---

## 3. Cartographie de l'autorité

Elle est dans `JALON_6_3c_CARTOGRAPHIE_DE_CONFIANCE.md`, §3 : les huit chemins,
avec pour chacun le point d'entrée, l'origine exacte de l'identité, les valeurs
contrôlables par l'appelant, la permission exigée, la portée, la transaction et
les verrous, la primitive PostgreSQL, l'audit produit et la frontière de
confiance effective. Les dix invariants **I-1 à I-10** y sont nommés, ainsi que
la sémantique de révocation A → B → C retenue.

**Résumé exécutif :** trois chemins (`resolve_`, `consume_`,
`log_normative_event`) ne dérivent **aucune** identité — ils reçoivent un UUID
et le croient. Leur sûreté repose entièrement sur leur ACL, mesurée ci-dessous,
et non sur leur logique.

---

## 4. Matrice de permissions SQL, **mesurée**

Produite par le harnais lui-même sur une base réellement déployée (section 0 de
sa sortie), pas recopiée d'une lecture du code.

| fonction | service | `normative_backend` | `eurostruct_deployment` | propriétaire | SEC. DEFINER |
|---|---|---|---|---|---|
| `bootstrap_normative_administrator` | ✗ | ✗ | **✓** | `eurostruct_normative_bootstrap` | oui |
| `consume_normative_authorisation` | ✗ | ✗ | ✗ | `eurostruct_normative_writer` | oui |
| `log_normative_event` | ✗ | ✗ | ✗ | `eurostruct_normative_writer` | oui |
| `resolve_normative_authorisation` | ✗ | ✗ | ✗ | **le migrateur** | **non** |
| `normative_finalize_deployment` | ✗ | ✗ | **✓** | le plan de contrôle | non |

Tables : le rôle applicatif détient `INSERT` et `SELECT` sur les tables
d'autorité, **jamais `UPDATE` ni `DELETE`** — mesuré, test 10.

---

## 5. Les quatorze attaques et leurs résultats exacts

Trois verdicts, et leur sens : **ROUGE** = l'attaque a abouti ; **sûr** = elle a
été refusée *et* le refus est attribué à la protection visée ; **ÉCHEC** = le
chemin n'a pas été atteint — ni rouge, ni assurance, un trou.

| # | attaque | verdict | résultat mesuré |
|---|---|---|---|
| 1 | auto-amorçage par l'identité de déploiement | **ROUGE** | un membre de `eurostruct_deployment` a nommé le premier administrateur normatif ; octroi créé, aucun mandat exigé |
| 2 | amorçage par un rôle sans `eurostruct_deployment` | sûr | `permission denied` — ACL. Non-vacuité : le même appel aboutit en 1 |
| 3 | deux amorçages concurrents | sûr | 0 des 2 concurrents aboutit ; total `origin='bootstrap'` = 1. Les deux sessions **observées bloquées** avant relâche |
| 4 | `SET request.jwt.claim.sub` | **ROUGE** | le serveur a inscrit `granted_by` = la valeur **déclarée par la session** |
| 5 | auto-attribution (`actor == grantee`) | sûr | « auto-attribution refusée » par `check_normative_grant()` |
| 6 | deux paternités depuis **une** connexion | **ROUGE** | deux `granted_by` **distincts** inscrits par le serveur, par deux `SET` successifs |
| 7 | délégation hors de la portée du grantor | sûr | refusée ; **contrôle positif** : le même acteur délègue sur BE (1 octroi) |
| 8 | délégation par une autorité révoquée | sûr | refusée ; non-vacuité : l'octroi porte bien une révocation |
| 9 | appel direct de `log_normative_event` | sûr | `permission denied` ; aucune trace `normative.*` forgée |
| 10 | `UPDATE` / `DELETE` directs sur les octrois | sûr | les deux refusés, privilège de table absent |
| 11 | rejeu d'un octroi identique | sûr | 1 ligne après deux envois ; non-vacuité : le premier envoi a bien créé |
| 12 | deux approbations **concurrentes** | **ROUGE** | 2 octrois aboutis sous **une seule** identité déclarée |
| 13 | confusion de portée (édition non détenue) | sûr | refusée ; **contrôle positif** : la même délégation dans l'édition détenue aboutit |
| 14 | consommation pendant la révocation (TOCTOU) | sûr | B **observée bloquée** par la révocation en vol, puis refusée après relecture sous verrou |

**Bilan corrigé : 14 attaques = 4 rouges + 10 sûres + 0 non parcourue.**

> **Correction d'une incohérence arithmétique.** Le premier rapport annonçait
> « 4 rouges et 11 sûres » pour quatorze attaques — quinze verdicts. La cause :
> l'attaque 10 bouclait sur `update` puis `delete` et **émettait un verdict par
> tour**. Le compteur additionnait des *appels*, pas des *attaques*, et
> l'arithmétique le disait à chaque exécution.
>
> Un compteur qui peut mentir sur son propre total n'atteste rien du produit.
> La comptabilité est désormais **structurelle et partagée**
> (`lib_harnais.sh`) : chaque contrôle est déclaré d'avance, rend **un** statut
> — un second verdict pour le même identifiant est lui-même une faute — un
> contrôle déclaré sans verdict est une faute, et l'égalité
> `déclarés == exécutés == rouges + sûrs + non_parcourus` est **vérifiée en fin
> de course**. Aucune de ces fautes n'est un avertissement : chacune force la
> sortie en échec.
>
> Statut par attaque, tel que le harnais l'imprime désormais :
>
> | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
> |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
> | **R** | S | S | **R** | S | **R** | S | S | S | S | S | **R** | S | S |

Les quatre rouges ne sont pas quatre défauts indépendants :

- **1** est distinct — il ne dépend pas de `auth.uid()` mais du fait que
  `p_grantee` est libre pour le porteur d'une identité de déploiement (**I-1**).
- **4** est la cause (**I-2**) ; **6** et **12** en sont la conséquence directe
  (**I-3**), 12 étant la forme concurrente de 6. Elle est conservée parce
  qu'elle établit en plus que **la concurrence n'ajoute aucune protection**.

### Trois faux verts trouvés dans le harnais avant de le figer

C'est la leçon de 6.3b6e appliquée au harnais lui-même. Les trois mesuraient
une ACL en croyant mesurer un invariant :

| test | ce qu'il lisait | pourquoi c'était faux | correction |
|---|---|---|---|
| 4 | `permission denied for schema auth` | `normative_backend` n'a pas `USAGE` sur `auth`, mais les déclencheurs, eux, appellent `auth.uid()` en `SECURITY DEFINER`. **Au même instant, le test 5 recevait le UUID falsifié dans son message d'erreur** | mesure l'**effet** : la valeur que le serveur inscrit dans `granted_by` |
| 13 | `permission denied for function resolve_…` | la migration ne l'accorde qu'à `eurostruct_normative_writer`, rôle NOLOGIN | passe par le chemin atteignable : l'insertion d'octroi, avec un acteur dont la portée **fixe** une édition |
| 14 | `permission denied for function consume_…` | idem — la matrice §4 le disait déjà : `svc=✗`, `backend=✗` | course construite sur le chemin atteignable (voir §6) |

Un décor défectueux avait par ailleurs **vidé quatre chemins** : l'administrateur
amorcé portait le même UUID qu'un des délégataires, et 6, 7, 8 et 12 se
refusaient toutes sur « auto-attribution » — trois d'entre elles se lisant
« déjà sûr ». Les trois rôles métier sont maintenant distincts, et une chaîne de
délégation est posée **et vérifiée comme précondition**.

---

## 6. Mécanisme déterministe de chaque test concurrent

**Aucun `sleep` d'ordonnancement.** Les `sleep 0.1` présents sont un pas de
scrutation à l'intérieur d'une barrière qui **échoue bruyamment** si sa
condition ne se produit pas — la différence exacte avec une temporisation.

| test | mécanisme | condition observée |
|---|---|---|
| 3 | porteur `psql -f <tube>` tenant un verrou consultatif **exclusif** ; concurrents en `pg_advisory_lock_shared` | les 2 concurrents vus `wait_event_type = 'Lock'`, puis relâchés **ensemble** |
| 12 | idem | idem |
| 14 | **deux** barrières : A révoque puis se **parque**, transaction ouverte et verrou de ligne en main ; B tente ensuite de consommer | A vue parquée, **puis** B vue bloquée. La course est **construite**, pas espérée |

Sept barrières franchies, chacune enregistrée avec son rang de scrutation.

### Deux interblocages, mesurés dans `/proc`, corrigés

1. **La levée par EOF ne levait rien.** `exec {BAR_FD}>` alloue un descripteur
   ordinaire, hérité par les sous-shells lancés ensuite et conservé par leur
   `psql`. Relevé pendant le blocage : **quatre écrivains survivants** en plus
   du parent. Fermer celui du parent ne produisait aucun EOF ; le porteur ne
   sortait pas, les concurrents attendaient une libération qui exigeait leur
   propre sortie. → la levée est un **ordre explicite** envoyé dans le tube.
2. **Un `wait` nu** attendait aussi le coprocessus qui détient le verrou du
   harnais pour toute la durée de l'exécution (`lib_harnais.sh:604`). → on
   n'attend plus que les PID lancés par le test.

Les deux étaient des défauts **du harnais**, pas du produit. Ils sont
documentés dans le fichier parce qu'un futur retour à la forme naïve
réveillerait exactement le même blocage.

---

## 7. Câblage — prouvé par exécution

> « Ne considère jamais la simple présence d'un fichier de test comme une
> preuve. »

`db/test/run.sh` appelle le harnais, juste après `authority_closure.sh`, dans le
groupe des surfaces qui exigent un jeu de rôles canoniques vierge. L'étape y est
annoncée **« ROUGE ATTENDU »**.

**Preuve.** Dans le worktree jetable `/tmp/esc-cablage`, le harnais a été
remplacé par un témoin d'une ligne, puis `run.sh` a été lancé. Le témoin a été
écrit :

```
TEMOIN-CABLE argv=eurostruct_testrt
```

`run.sh` atteint donc réellement le fichier et l'appelle avec son argument. Le
comportement du vrai harnais est prouvé séparément, par ses propres exécutions.

---

## 8. Ce qui n'est pas trouvable dans le dépôt

| attendu par la consigne | état réel |
|---|---|
| `PostgresConfirmationProvider` | **absent** |
| routes API / HTTP | **absentes** |
| services applicatifs | **absents** |
| CLI d'autorité | **absente** (la seule CLI est `tools/ndp_import`, hors autorité) |
| source externe autorisée pour le bootstrap | **absente** — aucune trace d'un registre, d'un mandat signé ou d'une décision hors-système |

**Sur la source externe du bootstrap.** Son absence est un constat, pas une
invitation à en inventer une. Trois options minimales, non implémentées et
soumises à décision :

1. **Cérémonie hors-ligne à empreinte** — l'amorçage exige un document de
   mandat dont l'empreinte est fournie en paramètre et inscrite dans l'audit.
   Ne prouve pas l'identité, mais rend la décision **traçable et opposable**.
2. **Double commande** — l'amorçage exige deux rôles de déploiement distincts,
   dans deux transactions séparées, avec une fenêtre d'expiration.
3. **Amorçage différé** — le déploiement crée une *demande* d'amorçage ;
   l'octroi n'existe qu'après confirmation par un canal distinct.

Aucune ne remplace une authentification réelle. Les trois ferment **I-1** sans
prétendre fermer **I-2**.

---

## 9. Ce que ce lot n'a pas fait, délibérément

- **Aucun code de production modifié.** Ni `db/migrations/`, ni
  `db/control_plane/`, ni le moteur.
- **Aucune campagne de mutation de clôture.**
- **Aucune authentification inventée.** Toute garantie de la forme « c'est bien
  *cette personne* » reste **`BLOCKED_BY_REAL_AUTH`**.
- **Aucun PR.**

---

## 10. Falsifiabilité — chaque garde neutralisée, une par une

> « Nous ne voulons plus seulement une assertion verte. Nous voulons savoir
> quelle propriété elle défend, comment la rendre fausse volontairement, et
> voir le test devenir rouge pour cette raison précise. »

Six exécutions dans le worktree jetable `/tmp/esc-cablage`. **Aucune
neutralisation n'a jamais touché l'arbre partagé.**

| volet | garde neutralisée | résultat | attribution |
|---|---|---|---|
| **T0** | aucune (témoin) | 4 rouges, 11 sûrs, 0 non parcouru | reproduit l'exécution de référence à l'identique |
| **N1** | I-4 — `if new.grantee_id = acteur` désarmé | **test 5 → ROUGE**, 5 rouges | **exacte** : seul le test 5 change |
| **N2** | I-5 — le refus « ne détient pas … couvrant la portée » désarmé | **tests 7 ET 13 → ROUGE**, 6 rouges | voir ci-dessous |
| **N3** | I-9 — `UPDATE`/`DELETE` accordés au rôle applicatif | test 10 → **ÉCHEC**, pas rouge | voir ci-dessous |
| **N4** | I-9 — privilège **et** RLS levés, déclencheur gardé | test 10 reste sûr, refusé par `forbid_mutation()` | layer 3 suffit seul |
| **N5** | I-9 — les **trois** couches levées | **test 10 (`UPDATE`) → ROUGE**, 6 lignes réécrites | falsification obtenue |

### N2 — un seul `if` défend deux invariants

Neutraliser la vérification de portée fait rougir **7 et 13 ensemble**. Ce n'est
pas un défaut d'attribution : c'est un fait de structure. I-5 (pas
d'amplification de portée) et I-6 (comparaison sur les quatre axes) sont
défendus par **le même appel** — `consume_normative_authorisation()` résolvant
la portée de l'acteur. Il n'y a pas deux gardes, il y en a une.

**Conséquence pour la suite :** tout correctif touchant cette résolution met en
jeu les deux invariants à la fois, et doit être testé comme tel.

### N3 → N5 — I-9 est défendu par **quatre** couches, pas une

Le test 10 n'est devenu rouge qu'après avoir retiré **trois** protections, et
la quatrième a résisté :

| couche | mécanisme | levée en |
|---|---|---|
| 1 | privilège de table (`UPDATE`/`DELETE` jamais accordés) | N3 |
| 2 | RLS — **aucune policy** `UPDATE`/`DELETE` n'existe, donc zéro ligne visible | N4 |
| 3 | déclencheur `normative_grants_are_immutable` → `forbid_mutation()` | N5 |
| 4 | clé étrangère `on delete restrict` depuis les révocations | **jamais levée** |

Deux enseignements, tous deux mesurés :

1. **N3 a produit un ÉCHEC, pas un faux vert, et c'est le harnais qui l'a
   attrapé.** Avec le seul privilège accordé, l'ordre est *accepté* et n'affecte
   *aucune* ligne — la RLS filtrant à zéro. Une branche écrite exprès refuse de
   lire « sans erreur et sans effet » comme une protection :
   *« probable filtrage RLS à zéro ligne, et non un refus »*. Sans elle, N3 se
   serait lu « déjà sûr » et j'aurais conclu que le test défendait une garde
   qu'il ne touchait pas.
2. **La quatrième couche n'était pas prévue.** En N5, l'`UPDATE` passe (6 lignes
   réécrites, rouge obtenu) mais le `DELETE` reste refusé — par la contrainte
   `on delete restrict` des révocations. La moitié `DELETE` du test 10 **n'est
   donc pas falsifiée** par cette campagne. La falsifier exigerait de supprimer
   la clé étrangère, c'est-à-dire de neutraliser le modèle de données et non une
   garde : je m'en suis abstenu, et je le signale plutôt que de présenter le
   test comme entièrement falsifié.

### Les trois observations, pour les gardes falsifiées

| garde | autorisé → vert | interdit → rouge | garde neutralisée → rouge |
|---|---|---|---|
| I-4 | l'octroi vers un tiers aboutit (test 6, T0) | l'auto-attribution est refusée (test 5, T0) | **N1** : test 5 rouge |
| I-5 / I-6 | délégation dans la portée : 1 octroi (contrôles positifs 7 et 13, T0) | délégation hors portée refusée (T0) | **N2** : tests 7 et 13 rouges |
| I-9 (`UPDATE`) | l'`INSERT` d'octroi aboutit (T0) | `UPDATE` refusé (T0) | **N5** : test 10 rouge, 6 lignes réécrites |

---

## 11. État final

| élément | valeur |
|---|---|
| branche | `claude/wip-6.3c-racine-de-confiance` |
| SHA du checkpoint rouge | `4c1966b` |
| `git status --porcelain` (arbre partagé) | **vide** |
| worktree adverse | retiré ; `git worktree list` ne le montre plus |
| code de production modifié | **aucun** |
