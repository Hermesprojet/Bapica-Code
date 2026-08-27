# 6.3c — lot autonome : le quatre-yeux explicite, et ce que la falsification a trouvé

> **Ce document rapporte l'état MESURÉ, pas l'état souhaité.** Chaque chiffre
> vient d'une exécution dont le journal existe. Ce qui n'a pas été exécuté est
> nommé comme non exécuté ; ce qui dépend d'un authentificateur réel est nommé
> comme tel, et n'est jamais compté comme vert.

Base de départ : `6989b46`.
Branche : `claude/wip-6.3c-racine-de-confiance`.

---

## 1. Ce que ce lot a trouvé, et qui n'était pas cherché

Sept défauts ont été découverts **par la mesure**, non par relecture. Aucun
n'était visible dans le catalogue des droits, et plusieurs rendaient une
réponse fausse plutôt qu'une erreur — ce qui est la forme la plus coûteuse.

### 1.1 Un couvreur qui meurt avec le retiré ne couvre rien — gouvernance irrécupérable

**C'est le défaut le plus grave du lot**, et il a été trouvé en rejouant la
suite de garanties existante, que 6.3c n'avait pas relancée depuis qu'il a
fermé la frontière d'écriture.

`0010` interdit de retirer le dernier administrateur d'une portée : il exige
qu'un **autre octroi actif** couvre la portée retirée. `0012` a rendu
l'efficacité **transitive** — un octroi dont un ancêtre est révoqué ne vaut
plus rien. Les deux, ensemble, ouvrent un trou :

1. la racine délègue une administration globale « de relève » ;
2. la relève est **active**, donc la garde de couverture accepte ;
3. l'octroi d'amorçage est retiré ;
4. la relève, descendante de l'amorçage, devient **inefficace** au même
   instant.

État final mesuré : **zéro administrateur efficace**. L'amorçage étant
singulier (index partiel sur une constante), il ne peut pas être rejoué : la
gouvernance est **irrécupérable**. C'est exactement la catastrophe que la garde
de `0010` existe pour empêcher, rouverte par `0012` sans que rien ne le dise.

**Correction** — la garde exige désormais l'**efficacité** et non l'activité,
et **écarte les descendants** de l'octroi retiré : un candidat n'est une relève
que s'il survit à la révocation.

**Conséquence assumée, désormais écrite dans le test** : il n'existe pas de
passation par révocation de la racine, puisque toute relève en descend. Une
procédure de « bris de glace » relève d'une décision distincte — `0010` le
disait déjà, et rien ici ne l'anticipe.

### 1.2 Quatre migrations rejouées à chaque déploiement

Le roundtrip sur base éphémère a mesuré : au second passage, 10 migrations sur
14 sont constatées « déjà appliquée » et **`0011` à `0014` sont rejouées**.
Elles n'appelaient pas `normative_migration_applied()` ; le registre n'en
gardait aucune trace. Les dix précédentes le font toutes.

* tout déploiement ultérieur les rejoue — or elles transfèrent des propriétés,
  posent des policies et retirent des droits ; elles ne sont pas idempotentes
  par construction ;
* la protection « on ne peut pas les appliquer hors du runner » disparaît :
  c'est la substitution de `:'esc_migration_id'` qui la porte.

Elles n'étaient pas non plus transactionnelles : une erreur au milieu du
fichier laissait la moitié des changements en place.

### 1.3 Un privilège sans policy — quatre tables, une seule corrigée

`0013` avait déplacé `INSERT` de `normative_backend` vers
`eurostruct_authority_backend` sur les **quatre** tables d'écriture normative,
et n'avait fait suivre la policy que sur la première. Sous `FORCE ROW LEVEL
SECURITY`, le backend authentifié détenait donc le privilège sans qu'aucune
policy ne le nomme.

| Table | INSERT accordé à | Policy INSERT nommant | Effet mesuré |
|---|---|---|---|
| `normative_authorisation_grants` | `eurostruct_authority_backend` | ce rôle | nominal |
| `normative_authorisation_revocations` | `eurostruct_authority_backend` | `normative_backend` | **refus RLS** |
| `normative_rule_confirmations` | `eurostruct_authority_backend` | `normative_backend` | **refus RLS** |
| `normative_rule_confirmation_revocations` | `eurostruct_authority_backend` | `normative_backend` | **refus RLS** |

Deux conséquences, de gravité différente :

* en `INSERT`, chaque ligne était refusée — « *new row violates row-level
  security policy* ». Le chemin de révocation **et** le chemin de confirmation
  étaient morts pour tout le monde, y compris pour le chemin nominal ;
* en `SELECT`, une table sans policy rend **zéro ligne**, pas une erreur. Or
  `normative_grant_is_effective()` est `language sql`, donc **droits de
  l'appelant**, et `0013` en donne l'`EXECUTE` au backend. Sans policy de
  lecture sur les révocations, la sous-requête « existe-t-il une révocation ? »
  ne voyait rien, et la fonction déclarait **EFFICACE une habilitation
  révoquée**.

`has_table_privilege` répond « oui » dans les deux cas. C'est exactement ce qui
rend l'écart invisible : le catalogue des droits est vert, la policy manque, et
le système répond faux sans se plaindre.

**Correction** — les trois policies `INSERT` manquantes, les trois policies
`SELECT`, et une assertion post-migration **généralisée** : pour chaque table
sous `FORCE RLS` où le backend détient `SELECT` ou `INSERT`, une policy
permissive doit le nommer, sinon la migration échoue.

### 1.4 La consommation d'une décision ignorait une révocation en vol

Le contrôle `revocation-pendant-consommation` a été observé **ROUGE**. Une
révocation parquée sur une barrière déterministe — transaction ouverte, verrou
consultatif exclusif en main — n'a **jamais** bloqué la consommation d'une
décision reposant sur l'habilitation en cours de retrait.

La consommation relisait `normative_grant_is_effective()`, qui ne prend aucun
verrou et lit un instantané où la révocation non validée n'existe pas.

On pourrait plaider que « consommer puis révoquer » est un ordre sériel
explicable. `0010` a **explicitement refusé** ce raisonnement pour les
confirmations : le déclencheur de révocation prend l'exclusif sur
`grantrow:<octroi>` précisément pour qu'une écriture normative en vol ne se
glisse pas sous un état intermédiaire. Consommer une décision est une écriture
normative du même poids. Une porte fermée à côté d'une porte ouverte ne ferme
rien.

**Correction** — `normative_lock_grant_chains()` prend le verrou **partagé**
sur l'union des chaînes d'ascendance, dans l'ordre des identifiants. Appelée
par `normative_decision_consume` (les deux sources) et par
`normative_decision_approve` (la source du proposant ; celle de l'approbateur
l'était déjà via `consume_normative_authorisation`). Les verrous étant
partagés, deux approbations concurrentes ne s'interbloquent pas ; seule une
révocation, qui prend l'exclusif, s'y oppose. Aucun verrou de ligne n'est pris
sur `organizations` : le `FOR NO KEY UPDATE` antérieur est conservé.

### 1.5 Une assertion qui se déclenchait sans nommer l'écart

Découvert par la falsification `N1`. En rendant `normative_decision_approve`
exécutable par `PUBLIC`, l'assertion post-migration de `0014` détectait bien
l'écart, puis échouait sur « *malformed array literal* » au lieu de le nommer.

`text[] || 'littéral'` est ambigu : PostgreSQL essaie d'abord
`anyarray || anyarray` et tente de convertir le littéral non typé en tableau.
Les branches écrites avec `format()` n'avaient pas le problème — `format()`
rend un `text` déjà typé — ce qui explique que le défaut soit resté invisible.

Une garde qui se déclenche sans dire ce qui manque coûte l'heure qu'elle devait
faire gagner.

### 1.6 La dette d'intégration : la porte fermée n'avait été rouverte nulle part

6.3c a fermé l'écriture normative aux rôles applicatifs et l'a rouverte pour
ses cinq harnais d'autorité. **Le reste de la suite n'avait pas été rejoué.**
`db/test/run.sh` n'était pas vert, pour cinq raisons cumulées :

| Symptôme mesuré | Cause |
|---|---|
| `BOOTSTRAP_AUTHORITY_NOT_CONFIGURED` sur la base principale | `run.sh` ne déclarait ni `authority_backend_logins` ni `bootstrap_mandate` |
| `permission denied for table normative_authorisation_grants` | le parcours passait par `normative_backend`, qui n'a plus `INSERT` |
| l'acteur n'était pas vu | les contextes posaient `request.jwt.claim.sub`, que le déclencheur ne lit plus |
| `toute delegation doit nommer parent_grant_id` | les octrois légataires ne nommaient pas leur ascendance (`0012`) |
| **sept suites refusaient de démarrer** | `eurostruct_authority_backend` manquait aux listes de rôles canoniques de trois harnais : il survivait au démontage |

À quoi s'ajoute une garantie antérieure violée par `0012` et `0013` : trois
fonctions `normative_*` avaient été accordées à `normative_governance`, alors
qu'une garantie interdit à tout rôle applicatif d'exécuter une fonction
« normative ». Les trois `GRANT` sont retirés — la gouvernance lit les tables,
sur lesquelles elle a `SELECT` et une policy.

Un rôle oublié dans une liste de démontage n'est pas un détail : il arrête tout
ce qui vient après.

### 1.7 Cinq défauts de mesure dans les harnais eux-mêmes

Un test peut être vert parce que la garantie tient, ou vert parce qu'il ne
regarde rien. Cinq cas du second type ont été trouvés.

* `execute-direct` mesurait `$SVC`, que le décor rend **membre** de
  `eurostruct_authority_backend`. Il mesurait donc le backend authentifié en
  l'appelant « le rôle applicatif ». Le contrôle porte désormais sur `$ORD`.
* L'énumération des primitives ne couvrait ni `0012`, ni `0013`, ni `0014`.
  L'étendre a fait apparaître que deux déclencheurs de `0014` n'avaient ni
  retrait à `PUBLIC` ni transfert de propriété.
* `double-approbation-sequentielle` faisait tenter la seconde approbation par
  un tiers hors portée : le contrôle de **portée** refusait avant que l'état
  soit regardé, et la machine à états n'était jamais atteinte (§3.2).
* **`deploy_recovery.sh` T11 ajoutait au milieu en croyant ajouter en
  suffixe.** Le fichier fabriqué s'appelait `0011_ajout_legitime.sql` et triait
  donc **avant** `0011_authority_hardening.sql` : ce n'était plus un suffixe
  mais une insertion dans le préfixe déjà appliqué — exactement le geste que
  T10 vérifie être refusé. Le scénario mesurait l'inverse de ce qu'il annonce
  depuis l'instant où une migration `0011` a existé.
* `deploy_recovery.sh` T13–T16 exigeaient « dix migrations inscrites ». Le
  chiffre était juste **par accident** : `0011` à `0014` ne s'inscrivaient pas
  au registre. Le compte est désormais lu depuis le répertoire.

Le libellé « ROUGE ATTENDU (à fermer) » laissait par ailleurs entendre qu'un
rouge pouvait être accepté. Il devient « ROUGE » dans les harnais qui comptent
leurs verdicts ; aucun mécanisme d'inversion ne subsiste, un rouge fait
échouer la suite.

---

## 2. État mesuré des suites ciblées

Chaque harnais **déclare** ses contrôles à l'avance, chacun rend **un seul**
statut, et l'égalité `déclarés == exécutés == rouges + sûrs + non parcourus`
est vérifiée à la fin. Un harnais dont le total ne s'additionne pas n'atteste
rien ; un second verdict pour un même contrôle est une faute, et un contrôle
déclaré sans verdict aussi.

| Suite | Déclarés | Rouges | Sûrs | Non parcourus |
|---|---:|---:|---:|---:|
| `authority_sql_hardening` | 20 | 0 | 20 | 0 |
| `authority_four_eyes` | 20 | 0 | 20 | 0 |
| `authority_root_of_trust` | 14 | 0 | 14 | 0 |
| `authority_delegation_lineage` | 15 | 0 | 15 | 0 |
| `authority_bootstrap_contract` | 8 | 0 | 8 | 0 |
| **total** | **77** | **0** | **77** | **0** |

Deux contrôles sont nouveaux dans ce lot :

* `policy-suit-privilege` — pour chaque table sous `FORCE RLS` où le backend
  d'autorité détient un droit, une policy permissive doit le nommer, et les
  quatre écritures normatives doivent être couvertes ;
* `surface-du-backend` — le backend authentifié atteint **exactement** six
  fonctions. Compter « au moins trois » laisserait un septième `GRANT` passer
  sans que rien ne le dise ;

et un troisième dans le quatre-yeux :

* `double-approbation-autorisee` — un second approbateur **habilité sur la
  portée exacte** est refusé une fois la décision approuvée, et ni
  l'approbateur ni la source d'origine ne bougent.

`deux-authentifications` reste marqué `BLOCKED_BY_REAL_AUTH` (voir §4).

---

## 3. Campagne de falsification adversariale

Chaque garde est neutralisée **séparément**, dans un worktree jetable du même
SHA, et l'on vérifie que le test qui **nomme** l'invariant perdu devient rouge.
Une neutralisation qui ne rend rien rouge ne prouve pas que la garde tient :
elle prouve que le test ne la touche pas.

Le harnais de campagne **refuse de conclure** quand le motif de neutralisation
ne correspond plus au fichier : une neutralisation sans effet rapporterait
« garde tenue » alors qu'elle n'a jamais été éprouvée — c'est le piège du
`GRANT` sans droit, qui se contente d'un `WARNING`.

### 3.1 Vingt neutralisations, trois passes

| # | Garde neutralisée | Migration | Test qui nomme l'invariant | Verdict |
|---|---|---|---|---|
| N1 | `EXECUTE` rendu à `PUBLIC` sur une primitive de décision | 0014 | — | non concluant → §1.3 |
| N1bis | idem, après correction du diagnostic | 0014 | assertion post-migration | **falsifiée** |
| N2 | transfert de propriété de `resolve_` retiré (0011 seul) | 0011 | `proprietaires` | redondance → N2bis |
| N2bis | **les deux** transferts retirés (0011 **et** 0012) | 0011+0012 | `proprietaires` | **falsifiée** |
| N3 | `search_path` d'une primitive rendu héritable | 0011 | `search-path` | **falsifiée** |
| N4 | `NO FORCE ROW LEVEL SECURITY` sur les octrois | 0014 | `force-rls` | **falsifiée** |
| N5 | création du rôle d'exécution rendue au **migrateur** | sceau+0013 | `migrateur-non-membre` | **falsifiée** |
| N6 | contrainte + refus de l'auto-approbation retirés | 0014 | `auto-approbation` | **falsifiée** |
| N7 | l'approbation enregistre la source du **proposant** | 0014 | `sources-conservees` | **falsifiée** |
| N8 | la proposition accepte n'importe quelle habilitation | 0014 | `source-hors-scope` | **falsifiée** |
| N9 | l'approbation ne relit plus la source du proposant | 0014 | `revocation-avant-approbation` | **falsifiée** |
| N10 | condition d'état retirée de l'approbation | 0014 | `double-approbation-sequentielle` | redondance → N10ter |
| N10bis | condition d'état **et** déclencheur de transition | 0014 | `double-approbation-sequentielle` | non falsifiée → §3.2 |
| N10ter | idem, avec un second approbateur **habilité** | 0014 | `double-approbation-autorisee` | **falsifiée** |
| N11 | transition de consommation rendue inconditionnelle | 0014 | `double-consommation-concurrente` | redondance → N11bis |
| N11bis | condition d'état **et** déclencheur de transition | 0014 | `double-consommation-concurrente` | **falsifiée** |
| N12 | `p_grantee` n'est plus confronté au mandat | 0013 | `grantee-different` | **falsifiée** |
| N13 | policy `INSERT` retirée, assertion retirée aussi | 0013 | `policy-suit-privilege` | **falsifiée** |
| N14 | policy `INSERT` retirée, **assertion conservée** | 0013 | assertion post-migration | **falsifiée** |
| N15 | verrou de chaîne retiré de la consommation | 0014 | `revocation-pendant-consommation` | **falsifiée** |

### 3.2 Ce que les « non falsifiées » ont appris — deux choses différentes

**Une redondance n'est pas un trou** (N2, N10, N11). Retirer *une* occurrence
d'une garde posée deux fois ne retire pas la garde. `resolve_normative_
authorisation` voit sa propriété transférée par `0011` **puis** par `0012` ; la
machine à états est tenue par la condition `WHERE state = <attendu>` **et** par
le déclencheur de transition. Retirer les deux rend bien le test rouge.

**Un test peut ne pas toucher l'invariant qu'il nomme** (N10bis). Le contrôle
`double-approbation-sequentielle` faisait tenter la seconde approbation par un
tiers dont l'habilitation porte sur une **autre édition**. Le contrôle de
**portée** la refusait avant que l'état soit seulement regardé : la machine à
états n'était jamais atteinte, et la garde semblait non éprouvée alors que le
test ne l'effleurait pas.

C'est exactement le défaut qu'une campagne de falsification existe pour
trouver, et il ne se voit ni en lecture ni dans un compte de tests verts. La
correction ajoute une cinquième identité fictive **habilitée sur la portée
exacte de la décision** : son refus ne peut alors venir que de l'état.

---

## 4. Ce qui reste hors d'atteinte, et pourquoi

**`deux-authentifications` est marqué `BLOCKED_BY_REAL_AUTH`, jamais vert.**
Une connexion de pool sert légitimement plusieurs utilisateurs successifs :
« deux connexions » ne prouve rien. Ce qu'il faudrait prouver — deux
**authentifications** indépendantes — exige un authentificateur réel, qui
n'existe pas dans ce dépôt. Un faux peut éprouver un contrat ; il ne prouve
jamais une authentification.

**Aucune affirmation de compatibilité Supabase n'est faite.** Les migrations
sont écrites pour PostgreSQL 16 et portent la marque `SUPABASE_UNVERIFIED`.
Rien n'a été exécuté sur Supabase ni sur aucune base non jetable.

---

## 5. Ce que la campagne de mutations existante ne couvre pas

`db/test/mutation_matrix.py` mute 65 garanties, réparties sur sept harnais
(`finalisation_contract`, `authority_closure`, `seal_contract`,
`cross_cluster_restore`, `official_deployment`, `deploy_recovery`,
`gate_protocol_selftest`). **Aucune ne porte sur `0011` à `0014`.** Les gardes
de ce jalon sont couvertes par la campagne de falsification décrite en §3, qui
est un mécanisme distinct : la matrice mute des garanties de déploiement, la
campagne neutralise des gardes d'autorité. Les deux existent, aucune ne
remplace l'autre, et il serait faux de compter les 65 comme couvrant 6.3c.

---

## 5 bis. La campagne complète de mutations, exécutée sur le SHA gelé

Lancée après le gel, avec 195 minutes disponibles contre les 100 exigées.
Espace isolé : worktree détaché sur `ea72f73`.

```
MUTATIONS: definis 65 | executes 64 | non executes 1 | echecs inexpliques 1
           dont tues 56, redondants voulus 7, PERIMES 1
```

**Deux contrôles n'ont pas tué, et les deux disent quelque chose.**

### Le contrôle 7 était PÉRIMÉ, et personne ne le savait

`7 — l'activator quitte le jeu canonique` mutait un texte de `run.sh` qui a
changé quand `eurostruct_authority_backend` a rejoint le jeu canonique
(commit `6989b46`). La matrice le comptait « non exécuté » — jamais tué,
jamais rouge. **La garantie n'était plus vérifiée par mutation, en silence.**

Le texte muté a été remis en face du code, et le contrôle tue de nouveau :

```
ok    7  l'activator quitte le jeu canonique
      -> le point 7 rougit (code 1)
```

C'est la règle que la matrice énonce elle-même : *« le contrôle doit être remis
en face du code, pas retiré »*.

### Le contrôle B n'est plus tué — il est intercepté PLUS TÔT

`B — les tables de preuve restent au migrateur` laisse les quatre tables
d'autorité au migrateur. Auparavant, le contre-exemple `B1` rougissait. Depuis
6.3c, **`0013` refuse d'appliquer la migration** : ses assertions
post-migration constatent l'écart avant que le harnais ait pu évaluer quoi que
ce soit, et tous les décors s'effondrent.

```
ECHEC B  les tables de preuve restent au migrateur
      -> le point B1 reste VERT: le controle ne porte rien
      ECHEC: decor a: phase 1 refusee sur 0013_authenticated_actor.sql
```

Le contre-exemple n'est pas creux dans l'absolu : la mutation sœur
`B' — la RLS des tables de preuve n'est plus forcée` **tue bien `B1`**. Ce qui
manque est une catégorie dans le vocabulaire de la matrice : elle sait dire
« tué », « redondance voulue », « périmé », « non exécuté » — pas
« intercepté par une assertion de migration », qui est ici le résultat le plus
fort possible.

**Ce contrôle n'a pas été rerouté, et c'est délibéré.** Ajouter une catégorie
au vocabulaire de la matrice est un changement de conception ; le valider
exigerait de rejouer les 65 contrôles, ce que le temps restant ne permettait
pas. Un changement non démontré par l'exécution ne vaut pas mieux que le
défaut qu'il prétend corriger. Il est porté au suivi, avec sa mesure.

## 6. Faits PostgreSQL 16 mesurés, et conservés ici

* `CREATE ROLE` par un rôle `CREATEROLE` donne au créateur
  `admin_option=t, inherit_option=f, set_option=f` : il peut **administrer** le
  rôle, jamais l'**utiliser**. Compter les lignes de `pg_auth_members`
  confondrait les deux.
* `GRANT` / `REVOKE` émis sans le droit correspondant produit un **WARNING**,
  pas une erreur : la commande n'a aucun effet et la migration passe. Ce piège
  s'est présenté quatre fois dans ce jalon.
* Une table sous `FORCE ROW LEVEL SECURITY` sans policy applicable rend **zéro
  ligne** en lecture — une réponse, pas une erreur.
* `text[] || 'littéral'` est ambigu ; le littéral doit être typé.

---

## 7. État réel à la clôture du lot

### 7.1 Ce qui est mesuré vert

**SHA gelé : `ea72f73`.** Les quatre étages ont été exécutés dans l'ordre exigé,
sur ce SHA, avec l'arbre propre et sans aucune édition pendant l'exécution.

| Étage | Résultat |
|---|---|
| 1. cinq suites ciblées | **77 contrôles, 77 sûrs, 0 rouge, 0 non parcouru** |
| 2. tests contractuels | moteur 935, importeur 88, contrat + providers — tous verts |
| 3. roundtrip des migrations | **SÛR** : 14 appliquées, 14 constatées déjà appliquées, **0 rejouée**, empreinte `4eb92f4d…` identique de part et d'autre |
| 4. `db/test/run.sh` complet | **code 0 — « Toutes les surfaces de db/test sont vertes »** |

Détail de l'étage 1 :

| Suite | Déclarés | Rouges | Sûrs | Non parcourus |
|---|---:|---:|---:|---:|
| `authority_sql_hardening` | 20 | 0 | 20 | 0 |
| `authority_four_eyes` | 20 | 0 | 20 | 0 |
| `authority_root_of_trust` | 14 | 0 | 14 | 0 |
| `authority_delegation_lineage` | 15 | 0 | 15 | 0 |
| `authority_bootstrap_contract` | 8 | 0 | 8 | 0 |
| **total** | **77** | **0** | **77** | **0** |

**Le câblage du nouveau harnais est démontré par l'exécution**, pas par la
présence du fichier : `migration_roundtrip.sh` a tourné comme étape de
`db/test/run.sh`, et son propre journal montre ses quatre contrôles sûrs.

**Résidu à la clôture de l'étage 4** — aucun processus, aucune base, aucun
rôle hors `postgres`, aucun verrou consultatif, aucune entrée dans
`pg_db_role_setting`, aucun worktree résiduel, `git status --porcelain` propre.
Les seules lignes de `pg_auth_members` sont les appartenances internes de
`pg_monitor`.

### 7.2 Ce qui reste ouvert

* **Le contrôle de mutation `B` doit être reclassé** (§5 bis). Il n'est plus
  tué parce que `0013` intercepte la mutation à l'application ; la matrice n'a
  pas de catégorie pour cet aboutissement. Le changement de conception n'a pas
  été fait faute de pouvoir rejouer les 65 contrôles pour le valider — **c'est
  le premier élément du suivi.**
* **La campagne n'a pas été rejouée après la correction du contrôle 7.** Ce
  contrôle a été vérifié seul, en exécution filtrée, et tue de nouveau ; les
  64 autres n'ont pas été réexécutés depuis cette correction. Le compte rendu
  complet ci-dessus est donc celui d'avant la correction.
* **`deux-authentifications` reste `BLOCKED_BY_REAL_AUTH`** et le restera tant
  qu'aucun authentificateur réel n'existe. Ce n'est pas un rouge : c'est une
  propriété qu'aucun faux ne peut établir.
* **La compatibilité Supabase n'est pas établie** et rien n'a été exécuté
  ailleurs que sur un cluster jetable local.
* **La matrice de mutation ne couvre toujours pas `0011`–`0014`** (§5). Les
  gardes de ce jalon sont couvertes par la campagne de falsification, qui est
  un mécanisme distinct.

### 7.3 Ce que ce lot ne prétend pas avoir démontré

* **La compatibilité Supabase.** Rien n'a été exécuté sur Supabase ni sur
  aucune base non jetable. Les migrations restent marquées
  `SUPABASE_UNVERIFIED`.
* **Une authentification réelle.** `deux-authentifications` est
  `BLOCKED_BY_REAL_AUTH`. Le contrat est éprouvé ; l'identité ne l'est pas.
* **Le comportement en montée de version depuis une base de production.**
  `run.sh` rejoue `0001..0013` puis la dernière migration sur une base séparée,
  ce qui couvre l'ajout en suffixe — pas un état de production réel.

### 7.4 Discipline tenue pendant ce lot

* Aucune identité réelle, aucun secret, aucune URL de connexion journalisée.
  Tous les principaux sont des UUID fictifs, toutes les empreintes de mandat
  portent littéralement la marque `FICTIF`.
* Aucun `DROP DATABASE`/`DROP ROLE` par motif large : les nettoyages ne visent
  que les objets dont le harnais peut prouver la création — les sept rôles
  canoniques que le sceau pose, les deux rôles stub, et les préfixes de la
  campagne.
* Aucune réécriture d'historique, aucun `--force`, aucun `amend`, aucune
  cerise. Commits séparés par correction.
* Aucun MCP PostgreSQL ou Supabase en écriture n'a été installé.
* Aucune pull request n'a été créée.
