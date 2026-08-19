# Modèle de menace du sous-système normatif

Ce document dit **qui l'on cherche à contenir**, et **qui l'on ne cherche pas à
contenir**. Sans cette liste, chaque garantie se discute au cas par cas et
finit par reposer sur une hypothèse implicite que personne n'a écrite.

Il s'applique à `db/control_plane/0001_normative_seal.sql` et
`db/migrations/0010_normative_confirmation.sql`, et aux harnais
`db/test/authority_closure.sh` et `db/test/finalisation_contract.sh`.

## Les quatre acteurs

| Acteur | Fiable pour | **Non** fiable pour |
|---|---|---|
| **Rôles applicatifs** (`authenticated`, `normative_backend`, `normative_governance`) | rien du tout | écrire, lire ou approuver quoi que ce soit hors de leurs politiques RLS |
| **Migrateur** | appliquer un schéma | **approuver une norme**, activer le sous-système, posséder une preuve |
| **Plan de contrôle** | approuver, finaliser, conserver l'ADMIN résiduel | — |
| **Superutilisateur** | — | **hors modèle** |

### Rôles applicatifs

Ils portent un jeton, ou sont endossés par un authentificateur. Toute écriture
normative passe par des déclencheurs `SECURITY DEFINER` qui recalculent les
empreintes côté serveur : ce qu'un rôle applicatif *déclare* n'est jamais cru.

### Migrateur — le point qui a coûté le plus cher

Le migrateur est fiable pour ce que son nom dit : appliquer des migrations. Il
n'est **pas** fiable pour l'approbation normative, et c'est un point de
conception, pas une méfiance de principe :

* il est choisi par l'exploitant, pas par l'ingénieur qui approuve ;
* il tourne dans un pipeline de déploiement, donc sous le contrôle de qui peut
  modifier ce pipeline ;
* il est, chez un hébergeur géré, le rôle le plus proche d'un superutilisateur
  dont dispose le client — c'est précisément pour cela qu'il ne doit pas être
  la racine.

**Conséquence directe.** Pendant la phase 1, le migrateur doit pouvoir endosser
les rôles d'autorité `eurostruct_normative_writer` et
`eurostruct_normative_bootstrap` : PostgreSQL l'exige pour transférer la
propriété des fonctions `SECURITY DEFINER`. Cette capacité est **temporaire et
restituée** par la phase 2.

Il ne doit en revanche **jamais** pouvoir endosser le rôle qui possède la
racine de confiance. Mesure faite sur `fc13990`, avant correctif :

```
pg_has_role(migrateur, 'eurostruct_normative_activator', 'SET')   -> true
set role eurostruct_normative_activator;
insert into normative_activation (activated_by, topology_digest)
values (session_user, repeat('0', 64));
-> normative_activation_state() = ACTIVE
```

Le sous-système passait ACTIVE sans finalisation, sans manifeste, sans
restitution — puis acceptait une écriture normative. Un déclencheur vérifiant
`current_user = activateur` n'y changeait rien : après `SET ROLE`, la condition
est exactement satisfaite. Un déclencheur vérifiant `session_user` n'y changeait
rien non plus : devenu **propriétaire** de la table, l'attaquant peut retirer le
déclencheur.

**La racine ne peut donc pas être une condition. Elle doit être une
propriété.**

### Plan de contrôle

Il approuve, et il est le seul à le faire. Il conserve un ADMIN résiduel
irrévocable sur les rôles qu'il a créés — fait `F1` de PostgreSQL 16, mesuré :
le créateur d'un rôle reçoit `admin=t, inherit=f, set=f`, donné par `postgres`.
Cet ADMIN est **toléré pour lui seul**, jamais avec `SET` ni `USAGE`, et son
identité est figée à l'installation par **OID et par nom**.

### Superutilisateur — hors modèle, explicitement

Un superutilisateur PostgreSQL peut désactiver n'importe quel déclencheur,
changer n'importe quel propriétaire, écrire dans les catalogues et endosser
n'importe qui. Prétendre le contenir donnerait une fausse assurance.

Ce qui est garanti : **un déploiement où aucun des deux acteurs n'est
superutilisateur** — la forme Supabase — tient les invariants ci-dessous. Les
harnais l'exercent sous cette forme, avec un migrateur et un plan de contrôle
tous deux non superutilisateurs.

## Les invariants

1. **Pendant `PENDING`** — aucun rôle exerçant les migrations ne peut créer une
   activation, désigner un plan de contrôle, figer des paramètres approuvés ni
   créer une intention de finalisation.
2. **Après `ACTIVE`** — aucune table normative n'appartient au migrateur ; ni
   lui ni un rôle applicatif ne peut désactiver un déclencheur ou contourner la
   RLS ; les propriétaires sont `NOLOGIN` et la RLS est **forcée**.
3. **La transition** — une entrée **orchestratrice** supportée,
   `normative_finalize_deployment(manifeste_attendu)`, et deux primitives de
   bas niveau, `normative_prepare_activation(manifeste)` et
   `normative_record_activation()`. Les trois sont réservées à
   `eurostruct_deployment` ; aucune n'est atteignable par `PUBLIC`, par un
   porteur de jeton ni par un rôle de service. Les primitives portent
   **exactement** les mêmes contraintes que l'orchestrateur — verrou détenu par
   la transaction courante, préparation et enregistrement dans **une seule**
   transaction (`prepare_txid`, assigné par le serveur), appelant égal au
   donneur dérivé, manifeste comparé aux déclarations réellement posées,
   révocations constatées effectives — et le chemin composé n'atteint **aucun
   état** que l'orchestrateur n'atteigne.

   **Cette formulation en remplace une qui était fausse.** Le document affirmait
   « une seule entrée publique mutante ». Les deux primitives étaient pourtant
   exécutables par `eurostruct_deployment`, et se composaient dans une seule
   transaction sous un verrou pris par l'appelant : mesuré, le sous-système
   passait `ACTIVE` sans que `normative_finalize_deployment()` ait été appelée.
   6.3b6c avait fermé la composition en *plusieurs* transactions, pas celle-ci.
4. **L'idempotence** — une seconde finalisation ne réussit que si le manifeste
   présenté est celui qui a été approuvé.
5. **Les identités** — plan de contrôle et migrateur sont deux rôles distincts,
   contrôlés par OID **et** par nom, partout où une exemption est accordée.
6. **La racine ne se lit pas** — `normative_seal_metadata` nomme le rôle qui a
   posé la racine, son OID et le niveau d'assurance : c'est la carte de la
   chaîne de confiance, donc la désignation de la cible qu'il faudrait usurper.
   Elle n'est lisible ni par `PUBLIC`, ni par un porteur de jeton, ni par un
   rôle de service. Quatre lecteurs nommés seulement : l'activateur qui la
   possède, `eurostruct_deployment`, `normative_governance` pour l'audit, et le
   **poseur** lui-même. La phase 1 ne la lit pas : elle interroge
   `normative_seal_version()`, qui rend la version **et rien d'autre**.
   Exercé par `db/test/seal_contract.sh`, scénario W, dans les deux sens — un
   lecteur légitime qui perd son accès est rouge autant qu'un rôle non listé
   qui en gagne un.

### Pourquoi l'API ne se réduit pas à une seule entrée

Ce n'est pas un choix, c'est une contrainte de PostgreSQL 16, mesurée.

Fermer l'API demanderait que `normative_finalize_deployment` fasse elle-même
les écritures dans les tables de confiance, donc qu'elle soit `SECURITY
DEFINER` possédée par `eurostruct_normative_activator`. Or elle doit **aussi**
exécuter les `REVOKE` des emprunts, et PostgreSQL n'accorde d'effet à un
`REVOKE` d'appartenance que s'il est exercé par le **donneur** de l'octroi :

```
set role t_admin;                       -- ADMIN OPTION sur t_cible
revoke t_cible from t_membre;
WARNING:  role "t_membre" has not been granted membership in role "t_cible"
          by role "t_admin"                                  -- sans effet

revoke t_cible from t_membre granted by t_donneur;
ERROR:  permission denied to revoke privileges granted by role "t_donneur"
DETAIL: Only roles with privileges of role "t_donneur" may revoke privileges
        granted by this role.
```

Une même transaction ne peut donc pas être à la fois **l'activateur** — pour
écrire la racine — et **le donneur** — pour que les révocations prennent —,
sauf à être superutilisateur, c'est-à-dire hors modèle.

Ce qui serait grave n'est pas que deux chemins existent : c'est qu'un chemin
donne plus que l'autre. `db/test/seal_contract.sh`, scénario K2, joue les deux
sur **la même base** — le chemin composé dans une transaction annulée, puis
l'orchestrateur sur la base intacte — et compare l'état, l'identité figée du
plan par OID **et** par nom, l'empreinte des déclarations gelées et le
`topology_digest`. Les quatre sont identiques.

## Ce que ce modèle ne couvre pas

* **Le vol d'identifiants du plan de contrôle.** Qui se connecte comme lui
  approuve ; c'est le sens même du rôle.
* **Le transport, en dehors du mode strict.** `tools/deploy_eurostruct.sh`
  exige `verify-ca` ou `verify-full` vers une cible distante — sans quoi le mot
  de passe du plan de contrôle passe en clair, ou l'on scelle une base
  substituée sans le savoir. `--auto-heberge` lève cette exigence : le chemin
  réseau devient alors la responsabilité de l'exploitant, et ce déploiement
  n'obtient pas les garanties ci-dessus contre un attaquant du réseau. Le
  refus, et sa levée, sont exercés par `db/test/deploy_recovery.sh`, V2.
* **La restauration inter-cluster — non prise en charge, et c'est un blocage
  explicite de mise en production.** L'identité du plan porte un OID
  PostgreSQL, qu'un `pg_dump`/restore vers un autre cluster ne préserve pas.

  Le comportement est un refus qui se lit : la topologie diagnostique
  `RESTAURATION INTER-CLUSTER`. Ce refus est **définitif pour cette base**.
  Il n'existe aucune procédure de reprise, et il ne peut pas en exister une
  sans rouvrir ce que la racine ferme : `normative_control_plane` est un
  singleton immuable, `normative_activation` est append-only,
  `normative_record_activation()` refuse dès que l'état est `ACTIVE`, et
  personne ne peut endosser l'activateur après la phase 0.

  Le document a longtemps dit « refinaliser la base sur place, par son propre
  plan de contrôle ». **Cette opération n'existe pas.** Mesuré sur une
  restauration réelle entre deux clusters (`db/test/cross_cluster_restore.sh`,
  qui crée le second cluster par `initdb`) : la consigne exécutée rend
  `MANIFEST_MISMATCH`, et vider la table d'activation est refusé même au
  **propriétaire** de la base restaurée. Un refus fail-closed qui envoie
  l'exploitant exécuter une procédure inexistante ne protège pas mieux qu'un
  refus muet.

  **Le chemin supporté vers un autre cluster** est un déploiement neuf —
  phases 0, 1 et 2 sur le cluster cible — suivi d'une reprise des données
  métier. Il ne transporte pas l'approbation, parce qu'une approbation vaut
  pour le cluster où elle a eu lieu. Cette procédure de reprise des données
  n'existe pas encore : tant qu'elle n'existe pas, une migration inter-cluster
  d'une base EUROSTRUCT en service est un **blocage de mise en production**,
  pas une opération courante.

  L'OID n'est délibérément **pas** réinscriptible : le rendre modifiable
  « pour réparer une restauration » rouvrirait exactement la substitution que
  6.3b6b a fermée, puisqu'il suffirait de déclarer que le bon OID est celui
  qu'on veut.
* **Le `topology_digest`.** C'est une **photographie d'audit**, pas un
  détecteur de dérive : rien ne le recalcule pour le comparer, et rien ne le
  fera — une dérive qui reste dans les règles doit pouvoir avoir lieu sans
  qu'un digest figé la refuse. Ce qui bloque les dérives interdites, ce sont
  les invariants de `assert_normative_topology()`.
  `normative_topology_digest(...)` permet de **refaire la photo** et de la
  comparer à celle qui a été inscrite : c'est une information d'audit, jamais
  un verdict. Le contrat est écrit sous le titre `CONTRAT DU topology_digest`
  dans `0001_normative_seal.sql`.
