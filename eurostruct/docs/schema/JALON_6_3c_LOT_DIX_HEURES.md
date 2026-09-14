# 6.3c — lot de dix heures : la frontière des rôles, et l'instrument qui la mesure

**Statut retenu : `DB_AUTHORITY_CONTROLS_COMPLETE — BLOCKED_BY_REAL_AUTH`.**
Ce document ne présente pas 6.3c comme close. Ni `DEPLOYABLE`, ni
`PRODUCTION_READY`. Supabase reste `SUPABASE_UNVERIFIED`.

**SHA validé : `c27ea65`.** Arbre propre — l'espace isolé de la campagne n'a
recopié **aucun** fichier non validé.

**Ce que « validé » veut dire ici, et ce que cela ne dit pas du HEAD courant.**
`c27ea65` est le commit sur lequel `run.sh` complet, le pré-vol intégral et la
campagne de mutations ont tourné, dans cet ordre, sur un arbre immobile. Le
commit qui ajoute *ce document* vient **après** : il ne porte donc pas cette
validation, et le HEAD courant n'est pas le SHA validé. Le delta est purement
documentaire — mais il appartient quand même à la chaîne de preuve, et le
prétendre validé serait exactement l'erreur rectifiée à l'ouverture de ce lot.

---

## 1. Rectification d'entrée, appliquée

La modification de `0013` ajoutant une précondition nommée est une modification
de **migration**. Toutes les preuves obtenues sur `ea72f73`, `56777d1` ou
`ea989e8` avant elle sont **périmées**, et ce lot ne s'en réclame pas. Tout ce
qui est chiffré ici a été remesuré.

Le total des contrôles de mutation n'est plus fixé : il est calculé depuis le
registre. Il est passé de 67 à **73** dans ce lot, par ajout — pas par
redécoupage.

---

## 2. Ce que ce lot a trouvé

### 2.1 L'`ADMIN OPTION` est la capacité, et la frontière ne la mesurait pas

Toute la frontière de 6.3c tient à une question : le migrateur peut-il
atteindre `eurostruct_authority_backend`, ou y enrôler quelqu'un ? Elle était
mesurée par `pg_has_role(…, 'USAGE')` et `pg_has_role(…, 'SET')`.

**Fait mesuré (PostgreSQL 16.13).** `CREATE ROLE` par un rôle `CREATEROLE` crée
une appartenance `admin_option=t, inherit_option=f, set_option=f` :

```
pg_has_role(créateur, cible, 'USAGE')  -> false
pg_has_role(créateur, cible, 'SET')    -> false
pg_has_role(créateur, cible, 'MEMBER') -> true
```

Le créateur ne peut ni hériter ni endosser — et il **enrôle qui il veut**.
Non-vacuité établie dans les deux sens par le contrôle `migrateur-sans-admin` :
avec l'ADMIN le `GRANT` réussit ; l'ADMIN retiré, le **même** `GRANT` est
refusé avec `Only roles with the ADMIN option on role "…" may grant this role.`

Mesurer USAGE et SET et s'arrêter là laissait donc passer exactement le chemin
par lequel la contenance s'était rouverte.

### 2.2 Une assertion écrite et jamais appelée

`assert_authority_backend_membership()` existait depuis le premier jet de
`0013`. **Seuls deux harnais l'invoquaient.** Le produit ne la vérifiait
jamais lui-même.

C'est grave à cause d'un fait mesuré cinq fois dans ce jalon : PostgreSQL 16
n'échoue pas sur un `GRANT`/`REVOKE` émis sans le droit requis — il émet un
**WARNING** et ne fait rien —, et `psql -v ON_ERROR_STOP=1` ne s'arrête pas sur
un WARNING. Une migration pouvait donc se terminer « avec succès » en laissant
la frontière dans l'état qu'elle prétendait corriger.

Elle est désormais posée **en postcondition de `0013`**, après tous les
`GRANT`/`REVOKE`/transferts, et elle a été renforcée :

| Couche | Ce qu'elle voit, que les autres ne voient pas |
|---|---|
| H1 | les **lignes** de `pg_auth_members` : un porteur d'ADMIN seul, invisible à `USAGE`/`SET` |
| H2 | la **chaîne** : un ADMIN transitif que nulle ligne ne nomme |
| H3 | le sens inverse — déclaré mais absent — exigé en `ACTIVE` seulement |

`H3` n'est exigé qu'en `ACTIVE`, **délibérément** : pendant la migration il est
faux par construction — `0013` installe le schéma, l'enrôlement des logins est
postérieur et relève du plan de contrôle.

### 2.3 Le contrôle « en chaîne » ne posait aucune chaîne

Trouvé **en écrivant sa falsification.** Le scénario accordait l'ADMIN en ligne
*directe* — que la lecture ligne à ligne voit déjà. La couche transitive
n'était jamais atteinte : `PM2` aurait survécu, et le contrôle portait le mot
« chaîne » dans son nom.

Le corriger a mis au jour un **point de menace réel**, désormais écrit dans le
modèle : un chemin transitif exige un rôle détenant l'ADMIN en ligne directe,
plus quelqu'un membre de ce rôle. Le seul détenteur légitime est le **plan de
contrôle** — celui que la lecture ligne à ligne exempte. Donc :

> **Qui entre dans le rôle du plan de contrôle peut enrôler qui il veut** dans
> le rôle qui détient `INSERT` sur les tables d'autorité, sans qu'aucune ligne
> de `pg_auth_members` ne le nomme sur le backend.

Contenu aujourd'hui par `pg_has_role(…, 'MEMBER WITH ADMIN OPTION')`, transitive
par construction. Contrôle `postcondition-admin-en-chaine`, falsification `PM2`.

### 2.4 Deux déclencheurs de `0014` jamais exercés

`check_normative_decision_transition()` et `forbid_decision_delete()`
existaient depuis le premier jet. Les vingt scénarios du quatre-yeux passent
tous par les trois primitives — qui, par construction, ne tentent jamais ce que
les déclencheurs refusent.

Quatre contrôles les exercent désormais, **sous le superutilisateur et
délibérément** : le modèle de menace le place hors périmètre pour les
*privilèges*, mais un déclencheur s'applique à lui. C'est la seule façon
d'isoler la garantie du déclencheur de celle des ACL.

### 2.5 Le verdict d'un signal exigeait des colonnes qui n'existent plus

Premier `run.sh` complet depuis la refonte du décompte, et il a trouvé.
`mutation_signal_selftest.sh` vérifie qu'une matrice interrompue rend un
verdict **complet**, par un motif nommant chaque colonne. `perimes` et `creux`
étaient devenus `stale` et `survived` : le motif exigeait des colonnes
disparues, et la garantie avait **cessé d'être vérifiée sans que rien ne le
dise**. Corrigé ; le motif reste aussi exigeant, seuls les noms suivent.

### 2.6 Le critère `duplicate_id` a servi le jour même

Deux contrôles portant le même code rendraient **deux verdicts sous un nom** :
le compte global tiendrait — les deux sont tentés — mais le tableau perdrait
une ligne, et une fois sur deux c'est la *survivante*. Un compte juste sur un
tableau faux rassure à tort.

Ajouté au pré-vol, il a immédiatement refusé les codes `R1`/`R2` que j'avais
choisis pour mes nouveaux contrôles : ils étaient déjà pris. Non-vacuité
mesurée par réinjection d'un vrai contrôle, puis restauration du fichier à
l'octet.

### 2.7 Aucun provider PostgreSQL n'existe

Recherche exhaustive : aucun fichier `provider`/`pool`, aucun module important
`psycopg`, `psycopg2`, `asyncpg`, `sqlalchemy` ou `sqlite3`, aucun appel
applicatif aux trois primitives, rien qui pose `eurostruct.actor_id` hors des
harnais. L'isolation du moteur est **délibérée et testée**.

Cinq exigences restent donc **non mesurables**, et sont inscrites comme telles
dans `MATRICE_QUATRE_YEUX.md` § 4 — ni vertes (ce serait un faux vert), ni
rouges (cela accuserait un code qui n'existe pas) : purge du contexte après
`COMMIT`, après `ROLLBACK`, après erreur ; absence de fuite d'acteur entre
locataires d'un pool ; deux authentifications réelles.

---

## 3. Mesures

### 3.1 Suites

| Suite | Déclarés | Exécutés | Rouges | Non parcourus |
|---|---|---|---|---|
| `run.sh` complet | 28 étapes | 28 | 0 | — |
| frontière des rôles PostgreSQL | 18 | 18 | 0 | 0 |
| quatre-yeux explicite | 24 | 24 | 0 | 0 |
| fermeture de l'autorité | — | — | 0 | 0 |
| roundtrip des migrations | 4 | 4 | 0 | 0 |
| contrat d'amorçage | 8 | 8 | 0 | 0 |
| auto-test du moteur de mutations | 17 propriétés | 17 | 0 | — |

`run.sh` complet, arbre immobile, sur `c27ea65` :

```
=================================================
 Toutes les surfaces de db/test sont vertes.
=================================================
code=0
```

Le passage précédent avait rendu `code=1` sur deux surfaces — les deux sur la
matrice de mutation, et pour les raisons dites au § 4 et § 2.5. Les deux ont
été traitées : l'une était une erreur d'opérateur, l'autre un défaut réel,
corrigé.

### 3.2 Pré-vol intégral, sur `c27ea65`

```
PRE-VOL: 73 controle(s) retenus, tous exercables.
         stale 0 | ambiguous 0 | missing_combined_control 0 | duplicate_id 0
```

### 3.3 Campagne complète, `c27ea65`, sans filtre

```
MUTATIONS: defined 73 | attempted 73 | killed_runtime 65
         | killed_install_assertion 1 | redundant_proven 7
           survived 0 | stale 0 | infra_failure 0 | not_run 0 | code 0

           INVARIANTS DE CAMPAGNE:
             [ok] defined == attempted
             [ok] defined == killed_runtime + killed_install_assertion
                             + redundant_proven + survived
             [ok] survived == 0
             [ok] stale == 0
             [ok] infra_failure == 0
             [ok] not_run == 0
```

**Les sept redondances**, chacune rattachée à son contrôle combiné, lequel est
déclaré ET retenu dans cette campagne :

| Redondance | Contrôle combiné | Résultat du combiné |
|---|---|---|
| `2` un seul des trois refus d'écriture directe | `2b` | tué |
| `3` un seul des deux contrôles d'identité du plan | `3b` | tué |
| `C` un seul des deux refus de composition | `C+` | tué |
| `C'` un seul des deux refus de préparation isolée | `C'+` | tué |
| `J'` une SEULE des deux moitiés de l'identité | `J` | tué |
| `P2` l'ADMIN préexistant n'est plus exigé | `P2b` | tué |
| `T4'` le contrôle re-fait à l'écriture du registre | `T4` | tué |

**Le contrôle `B`, ses deux couches, séparées :**

| Contrôle | Statut | Ce qui est établi |
|---|---|---|
| `B` | `KILLED_INSTALL_ASSERTION` | `0013` refuse d'installer, **en nommant l'invariant** ; transaction entièrement annulée |
| `B=` | `KILLED_RUNTIME` | postcondition et `set role` neutralisés, le schéma s'installe réellement avec les tables au migrateur — la défense d'exécution rougit `B1` |

**Les six falsifications ajoutées dans ce lot**, toutes tuées :

| Contrôle | Fichier muté | Point rougi |
|---|---|---|
| `PM1` la branche « membre SUPPLÉMENTAIRE » retirée | `0013` | `PC1` |
| `PM2` la chaîne d'ADMIN n'est plus suivie | `0013` | `PC2` |
| `PM3` la déclaration décorative n'est plus vue | `0013` | `PC3` |
| `PM4` l'ADMIN direct n'est plus confronté au plan | `0013` | `PC4` |
| `DT1` le socle d'une décision n'est plus figé | `0014` | `X1` |
| `DT2` une décision redevient effaçable | `0014` | `X4` |

Le relevé par entrée — identifiant, fichier(s) muté(s), empreinte SHA-256 du
fichier muté, harnais, statut terminal, diagnostic — est produit par
`ESC_MUTATION_TRACE` ; 74 lignes de trace pour 73 contrôles (le contrôle `B=`
est multifichier).

### 3.4 Résidus après la campagne, puis après `run.sh`

```
bases hors modèles              : aucune
rôles canoniques normatifs      : aucun
rôles de harnais restants       : aucun
verrous consultatifs détenus    : 0
```

### 3.5 Interruption, mesurée pour de vrai

Un `SIGTERM` envoyé à la campagne pendant le contrôle `2b` :

```
MUTATIONS: definis 73 | termines 2 | interrompu 1 | non commences 70
         | stale 0 | survived 0 | code 143
           controle actif : 2b LES TROIS refus d'ecriture directe
           fichier mute   : db/control_plane/0001_normative_seal.sql (restaure)
           signal recu    : SIGTERM (15)
           SHA teste      : 3e772967dc63…
           CAMPAGNE INTERROMPUE — ce compte rendu ne vaut PAS pour la matrice
           entiere.
```

Fichier restauré, worktree retiré, aucun résidu.

---

## 4. Deux erreurs d'opérateur, dites comme telles

1. **J'ai édité des fichiers pendant que `run.sh` tournait.** Le contrôle
   d'isolation l'a vu (`M mutation_matrix.py`) et a rougi. Le constat est
   juste ; la mesure était invalidée par moi, pas par le produit. C'est la
   deuxième fois dans ce jalon.
2. **J'ai lancé la campagne sur un arbre non validé** : l'espace isolé
   recopiait deux fichiers de travail, ce qui privait la campagne du SHA unique
   qu'elle doit avoir. Arrêtée après deux contrôles, commitée, relancée propre.

Une troisième, sans conséquence : `pgrep -f "python3 mutation_matrix.py"` a
mordu sur le shell wrapper dont la ligne de commande contient ce texte — la
même famille de piège que `pgrep -f "run.sh"` plus tôt. Résolu par comparaison
exacte sur `/proc/<pid>/cmdline`.

---

## 5. Constat ouvert, non corrigé, et pourquoi

| Assertion | Définie dans | Appelée par la migration ? |
|---|---|---|
| `assert_authority_backend_membership()` | `0013` | **oui**, depuis ce lot |
| `assert_authority_surface_hardened()` | `0011` | **non** — un harnais seul l'exerce |
| aucune | `0012` (8 `GRANT`/`REVOKE`) | **non** |
| aucune | `0014` (12 `GRANT`/`REVOKE`) | **non** |

Même motif que celui corrigé dans `0013` : un WARNING sans effet ne fait pas
échouer la migration. `authority_sql_hardening.sh` verrait la dérive — mais
seulement si quelqu'un lance la suite, et jamais lors d'un déploiement réel.

**Non corrigé dans ce lot** : modifier `0011`, `0012` ou `0014` aurait périmé
la campagne en cours sur le SHA candidat. Le constat est posé avec sa mesure,
comme travail ouvert nommé.

---

## 6. Faits PostgreSQL 16 mesurés dans ce lot

* `CREATE ROLE` par un `CREATEROLE` : `admin=t, inherit=f, set=f` — administrer
  n'est pas utiliser, mais administrer suffit à s'octroyer l'usage.
* `GRANT`/`REVOKE` sans le droit : **WARNING**, aucun effet, migration verte.
  Cinquième forme rencontrée : `REVOKE <rôle> FROM <membre>` émis par un
  **non-donneur** ne fait rien et le membre reste. Elle avait produit un faux
  rouge.
* Après `REVOKE ADMIN OPTION`, le `GRANT` est refusé : `Only roles with the
  ADMIN option on role "…" may grant this role.`
* `pg_has_role(…)::text` rend `true`/`false`, **pas** `t`/`f` — dix faux rouges.
* Table sous `FORCE RLS` sans policy applicable : **zéro ligne**, pas d'erreur.
* `text[] || 'littéral'` est ambigu ; le littéral doit être typé.

---

## 7. Ce que ce lot ne prétend pas avoir démontré

* Que 6.3c est close. Elle ne l'est pas.
* Que le quatre-yeux est **opérationnel** : il est contractuellement tenu par
  PostgreSQL, et pratiquement inatteignable tant qu'aucun authentificateur
  n'existe.
* Que la compatibilité Supabase est établie : aucun cycle n'a été validé sur un
  staging réel.
* Que les cinq exigences liées au provider tiennent : il n'y a pas de code à
  mesurer.

## 8. Discipline tenue

Aucune PR. Aucun changement de jalon. Aucune réécriture d'historique, aucun
`amend`, aucun force-push, aucun cherry-pick. Commits séparés. Aucun secret
dans `argv`. Aucune instance réelle touchée : cluster jetable déclaré, prouvé
tel, et vidé. Aucun `DROP DATABASE`/`DROP ROLE` hors des objets dont le harnais
prouve la création.
