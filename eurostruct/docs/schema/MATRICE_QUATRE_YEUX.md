# Matrice du quatre-yeux explicite — `0014_four_eyes_decisions.sql`

**Jalon 6.3c — racine de confiance.**
Statut du sous-système : `DB_AUTHORITY_CONTROLS_COMPLETE — BLOCKED_BY_REAL_AUTH`.
Ce document n'est **pas** une clôture de 6.3c.

---

## 0. Ce que ce document est, et ce qu'il n'est pas

Il met face à face **ce que la migration `0014` prétend garantir** et **ce
qu'une mesure a réellement établi**, ligne par ligne. Chaque ligne nomme le
contrôle qui l'a produite, dans le harnais qui l'exécute.

Il **ne dit pas** que le quatre-yeux est opérationnel. Il dit que le
*contrat* tient dans PostgreSQL. La différence est tout l'objet du § 4.

Le contrat, tel qu'il est écrit dans `0014` :

> Un proposant A et un approbateur B distinct, soit **deux principals au
> total**. Les **deux** habilitations invoquées sont conservées — sans elles
> on saurait *qui* a décidé, jamais *au titre de quoi*.

---

## 1. Le cycle, et ce qui le tient

| Étape | Primitive | Ce qui est exigé | Où c'est imposé |
|---|---|---|---|
| — | — | l'acteur n'est **jamais** un paramètre | signature des trois primitives : aucune ne reçoit d'UUID d'acteur |
| `PENDING` | `normative_decision_propose` | A est authentifié ; A détient une habilitation **efficace** couvrant l'objet | `normative_authenticated_actor()` + `consume_normative_authorisation()` |
| `APPROVED` | `normative_decision_approve` | B ≠ A ; B détient sa propre habilitation couvrante ; **celle de A est encore efficace** | contrainte `decision_two_distinct_principals` + relecture sous verrou de chaîne |
| `CONSUMED` | `normative_decision_consume` | la décision est `APPROVED` ; **les deux** sources sont encore efficaces | verrou de chaîne puis double `normative_grant_is_effective()` |

Le cycle est **`PENDING → APPROVED → CONSUMED`, et il ne remonte pas.**

---

## 2. La matrice, mesurée

Vingt-quatre contrôles déclarés dans `db/test/authority_four_eyes.sh`, tous
exécutés, tous sûrs, aucun non parcouru. La colonne « mesuré » ne reprend pas
l'intention du code : elle reprend ce que l'exécution a produit.

### 2.1 L'acteur est dérivé, jamais fourni

| Exigence | Contrôle | Mesuré |
|---|---|---|
| Sans contexte d'acteur, rien n'est proposé | `sans-authentification` | refus « aucun acteur dans le contexte » ; 0 ligne écrite |
| Un rôle ordinaire ne fabrique pas une identité en posant un GUC | `acteur-falsifie` | le rôle n'atteint pas la primitive ; 0 ligne écrite |
| Aucune API publique n'accepte librement l'acteur | `invocation-sql-directe` | `permission denied` sur la table ; aucun rôle applicatif n'y a de privilège |

**Non-vacuité** : le backend authentifié, lui, propose (`proposition-autorisee`).
Sans cette contrepartie, les trois refus ci-dessus seraient satisfaits par un
système où *personne* ne peut rien.

### 2.2 Deux principals, imposés par PostgreSQL

| Exigence | Contrôle | Mesuré |
|---|---|---|
| A ne s'approuve pas lui-même | `auto-approbation` | refusé — et la contrainte de table le refuserait même si l'appelant changeait |
| B distinct approuve | `approbation-second-principal` | `APPROVED`, `approver_id = B` |
| B doit détenir sa **propre** autorité | `approbateur-sans-autorite` | refusé |
| L'autorité invoquée doit couvrir **cet** objet | `source-hors-scope`, `confusion-organisation`, `confusion-edition` | refusé sur chacun des trois axes |

La distinction A ≠ B est portée par `constraint
decision_two_distinct_principals`, **pas** par le code appelant. Un message
se contourne en changeant d'appelant ; une contrainte non.

### 2.3 Une seule approbation, une seule consommation

| Exigence | Contrôle | Mesuré |
|---|---|---|
| Deux approbations séquentielles | `double-approbation-sequentielle`, `double-approbation-autorisee` | la seconde est refusée ; l'identité C — autorisée sur la **même** portée — établit que le refus vient de l'état, non de la portée |
| Deux approbations **concurrentes** | `double-approbation-concurrente` | barrière déterministe : les deux sessions **observées bloquées**, puis une seule aboutit |
| Deux consommations concurrentes | `double-consommation-concurrente` | idem, une seule aboutit |
| Rejeu après consommation | `rejeu-apres-consommation` | refusé |

Aucun `sleep` ne sert de synchronisation. Les barrières sont **atteintes et
constatées** — la trace du harnais les énumère avec leur numéro d'essai.

### 2.4 Les sources restent efficaces aux trois moments

| Exigence | Contrôle | Mesuré |
|---|---|---|
| Révocation entre proposition et approbation | `revocation-avant-approbation` | l'approbation est refusée |
| Révocation **en vol** pendant la consommation | `revocation-pendant-consommation` | la consommation est **observée bloquée** par la révocation parquée, puis refusée |

Cette seconde ligne a été **rouge à la mesure** avant correction : la
consommation relisait `normative_grant_is_effective()` sans verrou, donc sur
un instantané où la révocation non validée n'existait pas encore. D'où
`normative_lock_grant_chains()`, en verrou **partagé** sur l'union des chaînes
d'ancêtres, ordonné par identifiant.

### 2.5 Le socle est figé, et les déclencheurs le prouvent

Ces quatre contrôles s'exécutent **sous le superutilisateur**, délibérément :
le modèle de menace place les superutilisateurs hors périmètre pour les
*privilèges*, mais un déclencheur s'applique à eux. C'est la seule façon
d'isoler la garantie du déclencheur de celle des ACL.

| Exigence | Contrôle | Mesuré |
|---|---|---|
| Objet, organisation, portée, édition, proposant, source, corrélation figés | `objet-fige` | 6 tentatives, 6 refus nommant la colonne ; le socle est **relu** après et n'a pas bougé |
| `PENDING → CONSUMED` et `CONSUMED → APPROVED` | `transition-interdite` | les deux refusées ; les états sont relus et inchangés |
| Consommer sans réécrire l'approbation | `approbation-non-rejouee` | refusé ; `approver_id` et `approval_source_grant_id` inchangés |
| Une décision ne s'efface pas | `suppression-refusee` | refusé ; le compte de lignes est identique |

### 2.6 Traçabilité

| Exigence | Contrôle | Mesuré |
|---|---|---|
| Les **deux** sources sont conservées, exactement | `sources-conservees` | `proposal_source_grant_id = GA`, `approval_source_grant_id = GB` |
| Les événements portent la corrélation de la décision | `audit-correlation` | `proposed = 1`, `approved = 1`, même `correlation_id` |

---

## 3. Ce que la base refuse — table de vérité

| Situation | Résultat | Imposé par |
|---|---|---|
| Aucun acteur dans le contexte | refus | `normative_authenticated_actor()` |
| Acteur posé par un rôle ordinaire | refus | ACL : le rôle n'atteint pas la primitive |
| A propose sans habilitation couvrante | refus | `consume_normative_authorisation()` |
| B = A | refus | `CHECK decision_two_distinct_principals` |
| B sans habilitation couvrante | refus | `consume_normative_authorisation()` |
| Habilitation de A révoquée avant l'approbation | refus | verrou de chaîne + relecture |
| Seconde approbation (séquentielle ou concurrente) | refus | `UPDATE … WHERE state = 'PENDING'`, `row_count` |
| Consommation d'une décision non `APPROVED` | refus | garde d'état |
| Une des deux sources inefficace à la consommation | refus | verrou de chaîne + double relecture |
| Seconde consommation | refus | `UPDATE … WHERE state = 'APPROVED'`, `row_count` |
| `INSERT` direct dans la table | refus | aucun privilège applicatif + FORCE RLS |
| `UPDATE` du socle | refus | `check_normative_decision_transition()` |
| Transition illégale | refus | idem |
| `DELETE` | refus | `forbid_decision_delete()` |

---

## 4. Le provider PostgreSQL — CE QUI MANQUE, PRÉCISÉMENT

**Il n'existe aucun provider PostgreSQL dans ce dépôt.** Ce n'est pas une
omission de ce document : c'est une mesure.

Recherche effectuée sur l'arbre complet :

- aucun fichier dont le nom contient `provider` ou `pool` ;
- aucun module Python n'importe `psycopg`, `psycopg2`, `asyncpg`,
  `sqlalchemy` ou `sqlite3` ;
- aucun code applicatif n'appelle `normative_decision_propose`,
  `normative_decision_approve` ni `normative_decision_consume` ;
- rien ne pose `eurostruct.actor_id` en dehors des harnais de test.

L'isolation est **délibérée et testée** : `engine/tests/test_confirmation_domain.py`
contient une assertion qui échoue si l'un de ces modules devient importable
depuis le domaine. Le moteur ne connaît aucune base, par construction.

### 4.1 Ce qui ne peut donc pas être mesuré aujourd'hui

| Exigence du contrat | État | Ce qui manque exactement |
|---|---|---|
| Le contexte d'acteur est purgé après `COMMIT` | `pending_verification` | il n'existe aucune connexion applicative, donc aucun `COMMIT` applicatif |
| … après `ROLLBACK` | `pending_verification` | idem |
| … après une erreur | `pending_verification` | idem |
| Une connexion de pool ne fuit pas l'acteur au locataire suivant | `pending_verification` | il n'existe aucun pool |
| Les deux identités proviennent de deux authentifications **réelles** | `BLOCKED_BY_REAL_AUTH` | aucun vérificateur de jeton n'existe dans le dépôt |

Aucune de ces cinq lignes n'est déclarée verte, et aucune n'est déclarée
rouge. Un état non mesuré n'est ni l'un ni l'autre — le déclarer vert serait
un faux vert, le déclarer rouge accuserait un code qui n'existe pas.

### 4.2 Le contrat externe que le provider devra honorer

Quand un provider sera écrit, il devra — et la base ne peut pas l'imposer à
sa place :

1. **Poser l'acteur depuis un jeton vérifié**, jamais depuis une valeur reçue
   du client. La base vérifie qu'un acteur *est posé* et par *quel rôle* ;
   elle ne peut pas vérifier qu'il vient d'une authentification.
2. **Purger le contexte à la fin de chaque unité de travail**, y compris sur
   le chemin d'erreur. `SET LOCAL` meurt avec la transaction ; un `SET` de
   session survit à la connexion rendue au pool. Le choix entre les deux est
   celui qui décide si un locataire peut agir sous l'identité du précédent.
3. **Se connecter sous un login déclaré** dans
   `eurostruct.authority_backend_logins`, et sous aucun autre. La
   postcondition de `0013` refuse tout membre non déclaré du rôle
   d'exécution — mais elle s'exécute à la migration, pas à chaque requête.
4. **Ne jamais exposer une API qui accepte l'identifiant d'acteur en
   paramètre.** C'est la leçon de 6.3c : un UUID reçu est une donnée, jamais
   une preuve d'identité.

### 4.3 Pourquoi cela ne bloque pas le reste

Le sous-système est **fermé par défaut**. `normative_authenticated_actor()`
lève `BLOCKED_BY_REAL_AUTH` tant qu'aucun authentificateur n'est déclaré, et
aucun login de production ne reçoit le rôle d'exécution. Les tests
positifs passent par un provisionnement **explicitement privilégié**, posé
par le plan de contrôle dans un décor jetable — jamais par un chemin qu'un
déploiement réel emprunterait.

---

## 5. Ce que ce document ne prétend pas

- **Pas** que 6.3c est clos.
- **Pas** que le système est déployable ou prêt pour la production.
- **Pas** que le quatre-yeux est opérationnel : il est *contractuellement*
  tenu par PostgreSQL, et *pratiquement* inatteignable tant qu'aucun
  authentificateur n'existe.
- **Pas** que la compatibilité Supabase est établie : elle reste
  `SUPABASE_UNVERIFIED`, aucun cycle n'ayant été validé sur un staging réel.

Statut maximal atteignable en l'état, et statut retenu :
**`DB_AUTHORITY_CONTROLS_COMPLETE — BLOCKED_BY_REAL_AUTH`.**
