# Modèle de menace du sous-système normatif

Ce document dit **qui l'on cherche à contenir**, et **qui l'on ne cherche pas à
contenir**. Sans cette liste, chaque garantie se discute au cas par cas et
finit par reposer sur une hypothèse implicite que personne n'a écrite.

Il s'applique à `db/migrations/0000_sceau_normatif.sql` et
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
3. **La transition** — une seule entrée publique mutante,
   `normative_finalize_deployment(manifeste_attendu)`. Ses étapes internes ne
   se composent pas depuis plusieurs transactions.
4. **L'idempotence** — une seconde finalisation ne réussit que si le manifeste
   présenté est celui qui a été approuvé.
5. **Les identités** — plan de contrôle et migrateur sont deux rôles distincts,
   contrôlés par OID **et** par nom, partout où une exemption est accordée.

## Ce que ce modèle ne couvre pas

* **Le vol d'identifiants du plan de contrôle.** Qui se connecte comme lui
  approuve ; c'est le sens même du rôle.
* **La restauration inter-cluster.** L'identité du plan porte un OID
  PostgreSQL, qu'un `pg_dump`/restore vers un autre cluster ne préserve pas. Le
  comportement attendu est un refus qui se lit — voir *RESTAURATION
  INTER-CLUSTER* dans `0000_sceau_normatif.sql`. L'OID n'est délibérément pas
  réinscriptible : le rendre modifiable rouvrirait la substitution.
* **Le `topology_digest`.** C'est une **photographie d'audit**, pas un
  détecteur de dérive : rien ne le recalcule ni ne le compare. Ce qui bloque
  certaines dérives, ce sont les invariants de `assert_normative_topology()`.
  Voir *CONTRAT DU topology_digest* dans `0000_sceau_normatif.sql`.
