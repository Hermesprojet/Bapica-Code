# Lot L5 — rapport de fin

## Temps

| repère | valeur |
|---|---|
| début UTC | `2026-08-29T08:54:56Z` |
| lecture monotone au départ | 21,57 s (**le conteneur avait redémarré**) |
| fin de la campagne finale | monotone 22 200 s, soit H+6h09 |
| horloge murale écoulée | ≈ 6 h 10 |

Le conteneur a redémarré avant ce lot : la référence monotone du lot L4 n'existe
plus. PostgreSQL était arrêté et a dû être relancé.

**Une correction sur mes propres repères** : pendant la première moitié du lot
j'ai annoncé des jalons (« H+1h08 », « H+2h30 ») que j'estimais de tête au lieu
de les lire. La lecture monotone donnait H+0h22 au moment où j'annonçais H+2h30.
Les repères ci-dessus sont lus, pas estimés.

## Branche

    TARGET_BRANCH_UNRESOLVED

Aucune instruction du dépôt ni de sa configuration ne désigne de branche
canonique : pas de `CLAUDE.md` à la racine ni sous `eurostruct/`, et les deux
workflows CI ciblent `branches: ["**"]`. Le travail reste donc sur la branche
courante, `claude/wip-6.3c-racine-de-confiance`, qui a son propre amont.

Relation mesurée, sans rien déplacer :

* `origin/claude/eurostruct-saas-platform-js2o49` = `d04abf0` ;
* `merge-base` des deux branches = `d04abf0` — c'est **la tête de `js2o49`** ;
* commits de `js2o49` absents de `wip` : **0** ;
* commits de `wip` absents de `js2o49` : **72** au moment du constat.

`js2o49` est donc un **ancêtre strict** de `wip`. Aucune divergence, aucun
travail en péril, et un `fast-forward` serait possible — mais il n'a pas été
fait, faute d'instruction désignant la branche canonique.

## L'incohérence de preuve du lot L4, résolue

Le rapport L4 annonçait un HEAD `54b9f0c` et attribuait la validation ordonnée
à `5140436`.

* le delta `5140436..54b9f0c` est **un seul commit, un seul fichier** :
  `eurostruct/docs/RAPPORT_L4.md`. Aucun fichier sous `db/` ou `engine/` ;
* **mais la validation ne vaut pour aucun des deux.** Elle avait tourné sur
  l'**arbre de travail**, avant que `5140436` n'existe, et je l'avais ensuite
  attribuée à ce SHA. Le conteneur ayant redémarré, l'arbre d'alors n'est même
  plus recalculable.

Elle est traitée comme **non probante** et a été refaite depuis un worktree
détaché. C'est exactement le défaut que le champ `sha` du canal ferme
désormais.

## Le graphe des SHA

    d04abf0  tete de claude/eurostruct-saas-platform-js2o49 (ancetre)
       ...
    54b9f0c  HEAD au debut de ce lot
    1ad3c5b  canal JSONL contractuel — protocole 2
    775a786  SC1 a SC5 inscrits au registre
    fe111db  contre-exemple complet des cinq couches
    a24e514  comptabilite des anomalies du canal        <- 1er SHA gele
    acf107d  2b attendait le point « 2 »                <- SHA FINAL, gele
    (+ ce rapport et la cartographie provider/Supabase, documents seuls)

### Validation ordonnée et campagne portent sur le même SHA

|  | `a24e514` | `acf107d` |
|---|---|---|
| validation ordonnée | 31 surfaces, 0 rouge | **31 surfaces, 0 rouge** |
| worktree | détaché, `/tmp/esc-gel` | détaché, `/tmp/esc-gel2` |
| arbre avant / après | identique | **identique** |
| campagne | 109/109, **1 survivant** | **109/109, 0 survivant** |
| verdict | non concluante | **concluante** |

La campagne de `a24e514` reste archivée et **n'est pas réécrite**. La correction
du survivant a créé `acf107d` et l'a invalidée, comme prévu.

Preuve que les deux portent sur le même arbre : `git rev-parse HEAD^{tree}` et
l'empreinte SHA-256 de tous les `.sh`, `.py` et `.sql` ont été relevées avant
**et** après chaque exécution, et sont identiques ; `git status --porcelain`
du worktree est vide dans les deux cas.

## Campagne finale — `acf107d`

    RUN L5-acf107d-123511 | SHA acf107d88ce87ab0297fafc1dc433c83a89de6ac

    defined 109 | attempted 109 | killed_runtime 91
    killed_install_assertion 11 | redundant_proven 7
    survived 0 | stale 0 | infra_failure 0 | not_run 0 | code 0

    CANAL: unknown_event 0 | invalid_jsonl 0 | cross_run_event 0
           double_terminal 0

Les dix invariants sont tenus : `defined == attempted`, la somme se referme
(91+11+7+0 = 109), et `survived`, `stale`, `infra_failure`, `not_run`,
`unknown_event`, `invalid_jsonl`, `cross_run_event`, `double_terminal` valent
tous zéro.

### Le survivant de `a24e514`, et pourquoi ce n'était pas une garantie perdue

`2b LES TROIS refus d'écriture directe` a survécu. Le harnais **avait rougi** :

    ROUGE ATTENDU (a fermer): 2b. l'appel direct sans preparation n'est pas
        refuse pour ce motif:
        ERROR: null value in column "role_oid" ... not-null constraint

Les trois gardes retirées, l'écriture de confiance reste refusée — mais par une
contrainte `NOT NULL` incidente, pas par la garde visée. Le harnais le dit
exactement. Le registre, lui, cherchait le point `2` quand
`finalisation_contract.sh` étiquette cette assertion `2b`.

Vérifié avant de conclure : ce rouge est **absent** de la validation ordonnée
verte sur le même SHA. L'assertion ne parle que sous mutation ; la mise à mort
est donc légitime, pas un rouge préexistant.

Un **diagnostic automatique** a été ajouté, qui ne reclasse rien : le lanceur
nomme désormais les points qui ont rougi et distingue « un point rouge non
attendu → faute d'attribution probable » de « aucun point rouge → garantie
vraisemblablement perdue ». Le verdict reste `SURVIVED` dans les deux cas.

## Le canal JSONL, devenu contractuel

Protocole **2**. Champs obligatoires : `protocole`, `run_id`, `sha`,
`controle_id`, `point_id`, `statut`, `phase`, `seq`. Facultatifs reconnus :
`terminal`, `invariant`, `diagnostic`, `chemin`, `scenario_id`, `code`,
`effet`, `horodatage`.

Ce que le protocole 1 ne portait pas, et que chaque manque coûtait :

* **`run_id`** — deux campagnes concurrentes, ou une capture oubliée, et les
  événements de l'une comptaient pour l'autre ;
* **`sha`** — un événement d'un autre arbre répondait pour le candidat gelé.
  C'est le défaut exact du lot L4 ;
* **`seq`** — deux harnais écrivant en parallèle ne laissaient aucun moyen
  d'ordonner leurs verdicts ;
* **`controle_id` distinct de `point_id`** — les confondre est ce qui a permis
  à `MF1` d'être déclaré tué par les rouges de `MF2`, `MF3` et `MF4`.

Le `diagnostic` est **structuré** (objet à clés connues) : une prose libre
redevient vite ce qu'on analyse.

### Invariants tenus par le lecteur

| règle | comportement |
|---|---|
| un verdict terminal par contrôle | second terminal → faute comptée |
| contrôle inconnu | faute, `unknown_event` |
| contrôle déclaré mais absent | `NOT_RUN`, jamais vert |
| JSON tronqué / champ inconnu / version inconnue | **campagne invalide** |
| événement d'un autre `run_id` ou `sha` | rejeté, `cross_run_event` |
| prose contenant des identifiants | **aucun effet** |
| sorties concurrentes | `(controle, seq)` lève l'ambiguïté |
| repli vers les regex | **impossible en silence** |

### Le traducteur, et la dette qu'il nomme

`traduire_prose` exige le nom du harnais et **refuse** tout harnais absent de
`HARNAIS_NON_MIGRES`. Cette liste est la dette exacte — dix-huit harnais dont
le verdict dépend encore d'une prose :

`authority_bootstrap_contract`, `authority_closure`,
`authority_delegation_lineage`, `authority_four_eyes`,
`authority_role_frontier`, `authority_root_of_trust`,
`authority_sql_hardening`, `cross_cluster_restore`, `deploy_recovery`,
`finalisation_contract`, `gate_protocol_selftest`, `migration_postconditions`,
`migration_roundtrip`, `official_deployment`, `provider_contract`,
`seal_contract`, `two_phase_deployment`, `mutation_matrix`.

`harness_safety_selftest.sh` n'y figure pas : il **émet** sur le canal. Son
silence deviendrait `NOT_RUN`, jamais vert.

### Preuve négative permanente

Trois mutations du lecteur sont appliquées à une copie, et l'auto-test **doit
rougir** : retrait du rejet `run`/`sha`, réouverture du repli textuel,
acceptation des champs inconnus. Sans elle, trente-trois cas verts ne
prouveraient pas qu'ils voient.

Une régression trouvée par le bout-en-bout et figée par le cas 19b : la prose
nomme le **point** (`D9`), jamais le **contrôle** (`F4`). En passant le contrôle
au traducteur, `F4` — tué depuis des semaines — est ressorti **survivant**.

## S1 à S5 — inscrits, sous les identifiants `SC1` à `SC5`

Le pré-vol a refusé la première version, et il avait raison : `S1` à `S4` sont
**déjà** les identifiants des contrôles du verrou de déploiement. Deux verdicts
sous un même nom font disparaître une ligne du tableau. Les nouveaux s'appellent
`SC1`–`SC5`, le nom de la spécification restant visible entre parenthèses.

Cible unique : `verifier_heredocs.py`. Point attendu : `19.9`. Harnais :
`harness_safety_selftest.sh`, **migré** — donc aucun repli textuel possible.

`19.9` n'est pas un `rc == 0` : un selftest amputé rendrait zéro et passerait
pour vert. Le selftest publie le **compte** de cas parcourus, et `19.9` refuse
un compte inférieur à douze. Un décor qui n'a pas été parcouru ne conclut pas.

### La démonstration exigée, lue dans le canal

Scanner aveuglé par `SC1` :

    point 19.5   statut SUR    terminal false   corpus_propre
    point 19.9   statut ROUGE  terminal true    scanner_aveugle

**19.5 inspecte le corpus ; 19.9 falsifie l'instrument.** Le corpus est propre :
un scanner devenu aveugle y rend zéro et 19.5 reste vert pendant que la garantie
a disparu. Trois des cinq mutations (`SC1`, `SC2`, `SC3`) ne sont vues que par
19.9. C'est pourquoi le contrôle du corpus ne remplace pas celui de
l'instrument.

## Les cinq couches — contre-exemple complet

Harnais permanent `db/test/separation_layers.sh`, câblé dans `run.sh`.

| # | garde | où | quand |
|---|---|---|---|
| 1 | `assert_authority_backend_membership()` | `0013` | phase 1 |
| 2 | exception procédurale de `normative_finalize_deployment` | sceau | finalisation |
| 3 | contrainte `finalization_intent_separates_roles` | sceau | finalisation |
| 4 | assertion de capacité résiduelle | sceau | finalisation |
| 5 | `normative_record_activation()` | sceau | avant d'écrire |

**`ACTIVE` est atteint quand, et seulement quand, les cinq couches tombent.**
Il n'y a pas de sixième défense, et aucune des cinq n'est redondante : chaque
cas « laissée‑N » montre la couche N refusant seule.

Le **masquage est nommé** : neutraliser la seule couche 3 ne dit rien sur elle,
la couche 1 refuse avant, en phase 1. Les quatre cas `seule‑N` sont marqués
masqués et ne concluent rien.

Correction de cartographie : la couche 1 n'est pas une garde mais une fonction à
trois branches (H1 ligne directe, H2 fermeture **transitive**, H3 pluralité
d'ADMIN). Neutraliser une branche ne neutralise pas la couche — et H2 serait
passée pour une sixième défense inexistante. Le harnais vise le **point de
décision**.

Détail dans `MATRICE_SEPARATION.md`.

## `run.sh`

31 surfaces, 0 rouge, 0 non exécutée, sur `acf107d`, depuis un worktree
détaché, PID exact capturé et attendu — jamais `pgrep -f`. Durée ≈ 16 min.

## Provider et Supabase

Voir `PROVIDER_SUPABASE.md`. En résumé :

* `creer_provider_de_production` n'est appelée **nulle part** hors de sa
  définition ; `InMemoryConfirmationProvider` n'est construit que dans son
  module et les tests ;
* **il n'existe aucune couche de routes** — ni FastAPI, ni Flask, ni routeur.
  La frontière d'intégration n'est pas « brancher la factory sur la route X » :
  la couche appelante n'est pas écrite ;
* **aucune implémentation non fictive d'`Authentificateur` n'existe** ;
* une opération privilégiée n'est **pas** accessible sans authentificateur
  réel, et la défense n'est pas le format de la GUC mais le **privilège** :
  un rôle ordinaire qui pose la GUC obtient `insufficient_privilege` ;
* côté Supabase, **aucune** propriété n'est démontrée contre un environnement
  réel. Signature, issuer, audience, expiration, révocation : non démontrées,
  aucun vérificateur de jeton n'existe dans le dépôt.

## Statut

    DB_AUTHORITY_MIGRATION_CONTRACTS_COMPLETE
    FULL_MUTATION_CAMPAIGN_CONCLUSIVE — acf107d
    PROVIDER_IMPLEMENTED_NOT_INTEGRATED
    BLOCKED_BY_REAL_AUTH
    SUPABASE_UNVERIFIED
    TARGET_BRANCH_UNRESOLVED

Le critère de clôture porté par la campagne est atteint sur `acf107d` : campagne
complète terminée, aucun survivant, aucun contrôle non exécuté, aucune erreur
d'infrastructure, aucune attribution textuelle non déclarée.

**Cela ne clôt pas le jalon.** Les trois réserves restent séparées et entières :
le provider n'a pas de consommateur, aucune authentification réelle n'est
démontrée, et Supabase n'est pas vérifié. Elles ne dépendent pas de la
campagne : aucune campagne de mutation ne peut les lever.

## Un audit statique tenté, et son résultat négatif

Après la campagne, j'ai cherché s'il restait d'autres défauts du type `2b` —
un point attendu par le registre qu'aucune ligne rouge du harnais ne rendrait.
L'audit relève les émetteurs de rouge de chaque harnais non migré, reconstruit
la ligne qui serait imprimée, et la donne au traducteur.

Il a signalé **29 contrôles orphelins**. Vérification contre le journal de la
campagne : **les 29 ont été tués**. Vingt-neuf faux positifs sur vingt-neuf.

La cause est dans l'audit, pas dans le registre : son modèle de « comment un
harnais imprime un rouge » ne couvre que les appels littéraux
`rouge "…"` / `echoue "…"`. Or `provider_contract.sh` délègue à un script
Python, `migration_postconditions.sh` compose ses messages par variables, et
d'autres nomment leurs émetteurs autrement.

**Conséquence, et c'est le résultat utile** : un audit statique ne peut pas
remplacer la campagne ici, et celui-ci n'est pas livré comme contrôle — il
produirait 29 fausses alertes à chaque exécution. Un contrôle qui crie sans
raison finit par être sauté, ce qui est pire que pas de contrôle. Le fichier
reste dans le bloc-notes de session, non versionné.

## Défauts de mes propres instruments, trouvés dans ce lot

1. **j'ai importé `mutation_matrix.py` comme une bibliothèque** pour tester une
   fonction — c'est un script, et l'import a lancé une campagne entière, qui a
   échoué en `INFRA` faute de variables `PG*`. Aucun résidu, mais du temps
   perdu. La fonction a ensuite été éprouvée en l'extrayant par AST ;
2. **`pgrep -f mutation_matrix` a reconnu sa propre ligne de commande** et
   annoncé un processus vivant qui n'existait pas — le piège exact signalé
   auparavant ;
3. **une base de diagnostic laissée derrière** rendait les rôles canoniques
   indestructibles (`drop owned by` ne porte que sur la base *courante*) et a
   fait rougir **seize cas** du harnais des cinq couches pour une cause
   étrangère. Le harnais refuse désormais de démarrer sur un cluster déjà
   porteur des rôles canoniques ;
4. **`$3` non lié** sous `set -u` dans la fonction d'assertion du même harnais.

## Reste ouvert

* migrer les dix-huit harnais encore tributaires du traducteur ; chacun est
  nommé dans `HARNAIS_NON_MIGRES` ;
* écrire la couche appelante du provider, puis un authentificateur réel ;
* vérifier Supabase contre une instance réelle ;
* trancher la branche canonique (`TARGET_BRANCH_UNRESOLVED`).
