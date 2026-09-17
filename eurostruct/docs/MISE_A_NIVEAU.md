# Installer, mettre a jour, reprendre, restaurer

Ce document dit quatre choses, et rien d'autre :

1. **installer** une version ;
2. **mettre a jour** une installation qui porte deja des etudes, **en les
   conservant** ;
3. **reprendre** une mise a jour interrompue ;
4. **restaurer** une sauvegarde.

Le critere auquel il repond est celui de l'exploitant : *je garde mes etudes,
j'installe une nouvelle version, je retrouve mon travail intact.*

---

## 0. Ce qui change, et ce qui ne change pas

Une installation EUROSTRUCT vit dans trois endroits, et une mise a jour doit
les respecter tous les trois :

| ou | quoi | ce que la mise a jour en fait |
|---|---|---|
| PostgreSQL | organisations, projets, etudes, variantes, resultats, verifications, lignes de livrables, decisions d'autorite | conserve — seules les migrations **manquantes** sont appliquees |
| magasin d'objets | les **octets** des PDF et des DXF | n'y touche pas |
| roles du cluster | les six roles canoniques, les trois logins | inchanges, sauf pendant la fenetre (voir §5) |

**Les migrations historiques sont immuables.** Une migration deja inscrite au
registre n'est pas rejouee ; son empreinte est confrontee au fichier present,
et une divergence **refuse** au lieu d'appliquer quoi que ce soit.

**Les decisions normatives et leurs traces sont conservees.** La mise a jour
n'ecrit aucune confirmation, ne consomme aucune decision, et ne modifie ni le
sceau, ni la racine d'autorite, ni les declarations approuvees : le manifeste
est confronte **avant** et **apres**, et une mise a jour qui elargirait la
portee approuvee est refusee.

---

## 1. Installer

### Demonstration locale (un poste, Docker)

```bash
deploy/demo.sh prerequis     # ce qu'il faut sur le poste, et ce qui manque
deploy/demo.sh up            # construit, demarre, amorce, sert
```

`up` est **idempotente** : relancee sur des volumes deja peuples, elle constate
ce qui est deja fait et sort. Elle n'applique **jamais** une migration a une
base en service — voir §2.

### Staging (machine dediee, TLS)

```bash
deploy/staging.sh prerequis
deploy/staging.sh privileges     # ce que l'hebergeur doit accorder
deploy/staging.sh migrer         # sceau, migrations, activation
deploy/staging.sh up
```

### Base hebergee (Supabase ou autre)

Voir `docs/DEPLOIEMENT_BASE_HEBERGEE.md`. La commande officielle est la meme :

```bash
ESC_PLAN_URL=… ESC_MIGRATOR_URL=… tools/deploy_eurostruct.sh
```

---

## 2. Mettre a jour en conservant les donnees

### Le symptome

Vous recuperez une nouvelle version, vous relancez `up`, et la composition
refuse de monter :

```
ACTIVE_SCHEMA_UPGRADE_REQUIRED: cette base est ACTIVE, et le depot porte des
       migrations qu'elle n'a pas:

           0027_historique_filiation.sql
```

**Ce n'est pas une panne, et rien n'a ete applique.** C'est le refus
d'appliquer une migration par surprise a des donnees que personne n'a
sauvegardees. `reset` **n'est pas** la reponse : il detruirait vos etudes.

### La reponse

```bash
deploy/demo.sh diagnostic        # ce qui serait fait — ne modifie RIEN
deploy/demo.sh mettre-a-jour     # sauvegarde, migration, redemarrage
```

En staging :

```bash
deploy/staging.sh diagnostic
deploy/staging.sh mettre-a-niveau
```

Sur une base hebergee, sans Docker :

```bash
ESC_PLAN_URL=… ESC_MIGRATOR_URL=… \
  tools/deploy_eurostruct.sh --mettre-a-niveau --diagnostic

ESC_UPGRADE_CONSENTEMENT=oui-mettre-a-niveau-<nom-de-la-base> \
ESC_UPGRADE_SAUVEGARDE=/chemin/vers/base.dump \
ESC_PLAN_URL=… ESC_MIGRATOR_URL=… \
  tools/deploy_eurostruct.sh --mettre-a-niveau
```

**C'est la meme implementation dans les trois cas.** `demo.sh mettre-a-jour` et
`staging.sh mettre-a-niveau` appellent le service `init`, qui appelle
`tools/deploy_eurostruct.sh --mettre-a-niveau`. Il n'existe pas un chemin de
mise a jour « pour la demonstration » et un autre « pour de vrai ».

### Ce que `mettre-a-jour` fait, dans cet ordre

| # | etape | l'application |
|---|---|---|
| 1 | construit les images de la nouvelle version | **sert encore** |
| 2 | prend une sauvegarde : roles, base, livrables | **sert encore** |
| 3 | arrete l'API et l'interface | arretee |
| 4 | ouvre la fenetre de mise a niveau, applique les migrations manquantes, la referme | arretee |
| 5 | redemarre l'application dans la nouvelle version | repart |
| 6 | controle `/ready` | sert |

La coupure reelle tient entre 3 et 5. La construction, qui est le long moment,
a lieu pendant que l'ancienne version sert.

### Le diagnostic ne modifie rien

`diagnostic` annonce la version presente, la version cible, les migrations
prevues avec leurs empreintes, et evalue **tous** les prerequis avant de rendre
son verdict. Il ne prend aucun verrou, n'ecrit pas, et ne pose meme pas les
mots de passe : sur une installation ou tout est en place, il sort en 0 sans
qu'une seule ligne ait bouge.

---

## 3. Reprendre une operation interrompue

Un `Ctrl-C`, un conteneur tue, une machine qui redemarre : la fenetre peut
rester ouverte. Elle se reconnait a ceci — le migrateur detient encore des
emprunts, et le login applicatif n'est plus membre de
`eurostruct_authority_backend`.

```bash
deploy/demo.sh reprendre          # demonstration
deploy/staging.sh reprendre       # staging
tools/deploy_eurostruct.sh --reprendre-mise-a-niveau    # base hebergee
```

La reprise **constate** l'etat reel plutot que de le supposer : elle applique
ce que le registre declare manquant, revoque les emprunts, verifie qu'il n'en
reste aucun, puis rend au login applicatif son appartenance. Elle est sure a
relancer : relancee sur une fenetre deja refermee, elle le dit et sort.

`mettre-a-jour` **ne redemarre pas l'application** quand la fenetre a pu
s'ouvrir et que l'operation a echoue : une application qui repart ecrirait dans
une base a moitie migree. Le message nomme alors les deux issues — reprendre,
ou restaurer.

---

## 4. Restaurer une sauvegarde

Une sauvegarde prise par `deploy/demo.sh sauvegarder` est un dossier de trois
fichiers, et les trois sont necessaires :

| fichier | pourquoi il est la |
|---|---|
| `globals.sql` | les **roles du cluster et leurs appartenances**. Ils vivent hors de la base : un `pg_dump` ne les porte pas. La restauration les rejoue pour rendre une appartenance qu'une fenetre interrompue aurait retiree. Pris avec `--no-role-passwords` : **aucun mot de passe n'entre dans la sauvegarde**. |
| `base.dump` | la base, format `custom`. C'est l'archive que la mise a niveau inspecte avant d'ouvrir sa fenetre. |
| `livrables.tar` | les **octets** des PDF et des DXF. Une base sans eux promet des documents introuvables. |

```bash
deploy/demo.sh sauvegarder        # -> deploy/sauvegardes/<horodatage>/

EUROSTRUCT_DEMO_RESTAURER=oui-remplacer-par-la-sauvegarde \
  deploy/demo.sh restaurer deploy/sauvegardes/<horodatage>
```

**Restaurer remplace.** La commande arrete les ecrivains, rejoue les
appartenances, **remplace la base** par celle de la sauvegarde, remplace les
octets du magasin, puis redemarre par le chemin ordinaire — l'initialisation
constate ce qui est deja la. Le consentement explicite est exige pour la meme
raison que pour `reset`.

### La restauration reste dans la meme grappe, et ce n'est pas un detail

Premiere version de cette commande, mesuree le 17/09 : elle detruisait les
volumes, repartait d'une grappe vide et y rejouait `globals.sql`. La base
revenait entiere — memes etudes, memes livrables, memes proprietaires de
tables — et la mise a niveau suivante a **refuse** :

```
topologie: « eurostruct_plan » atteint « eurostruct_normative_activator »
(admin=t). CE ROLE PORTE LE NOM DU PLAN DE CONTROLE APPROUVE SANS ETRE LUI:
approuve = oid 16386, present sous ce nom = oid 16394.
```

Le plan de controle approuve est **fige par son identifiant interne, pas par
son nom**. Un nom se reprend ; une identite non. Des roles recrees dans une
grappe neuve sont d'**autres principaux**, meme sous les memes noms, et
l'exemption d'ADMIN residuel dont beneficie le plan de controle d'origine ne
leur est pas transmise.

C'est le comportement voulu : une base restauree dans une grappe etrangere ne
peut pas revendiquer en silence l'assurance de celle qui l'a produite. La
consequence pratique : **une sauvegarde se restaure dans la grappe qui l'a
produite.** Remonter une grappe entiere depuis zero est une autre operation,
qui repart d'une installation neuve.

Ce que la restauration ne remet pas non plus : les reglages declares au niveau
de la base (`ALTER DATABASE … SET`). Ils sont dans le **catalogue du cluster**,
pas dans le dump, et c'est l'initialisation qui les repose depuis le fichier
d'environnement au demarrage suivant. Une restauration sur un environnement
dont le fichier a change produit donc un manifeste different de celui qui avait
ete approuve — et la prochaine mise a niveau le refusera, a raison.

`reset` reste autre chose : une **suppression volontaire** de la demonstration,
qui ne pretend rien conserver.

---

## 5. Ce que la fenetre tient, et ce qu'elle rend

La mise a niveau n'est pas un effet de bord d'une relance. Elle ouvre une
fenetre nommee et bornee, dans cet ordre :

1. un **consentement qui nomme la base** (`ESC_UPGRADE_CONSENTEMENT=oui-mettre-a-niveau-<base>`) ;
   un consentement recopie d'un autre environnement ne l'ouvre pas ;
2. une **sauvegarde verifiee** (`ESC_UPGRADE_SAUVEGARDE`) : archive `pg_dump -Fc`
   lisible **portant le registre des migrations**. A defaut,
   `fournisseur:<texte>` declare une sauvegarde prise chez l'hebergeur — et
   c'est consigne comme **declaration**, pas comme verification ;
3. l'**exclusion mutuelle** par le verrou de deploiement : deux mises a niveau
   concurrentes, une seule applique ;
4. l'**arret des ecritures**, prouve puis pose : aucune session des logins
   applicatifs declares, puis **retrait** de leur appartenance a
   `eurostruct_authority_backend`. Une application qui se reconnecterait
   pendant la fenetre n'ecrit rien — elle est refusee par la base, pas par une
   convention ;
5. les **emprunts temporaires** rendus au migrateur (`writer`, `bootstrap`) ;
6. les **migrations manquantes, et elles seules**, par le registre ;
7. la **revocation** des emprunts, **constatee** ;
8. les **controles** avant retablissement : etat ACTIVE, registre, manifeste
   approuve inchange, topologie CONFORME, zero capacite residuelle du
   migrateur ;
9. le **retablissement du service** : l'appartenance retiree en 4 est rendue,
   et le constat est fait.

Si la commande est interrompue, la compensation rend **exactement** ce qui a
ete retire — ni plus, ni moins — et le dit.

### Les codes de sortie

| code | signification | l'application peut-elle repartir ? |
|---|---|---|
| 0 | fait | oui |
| 2 | prerequis refuses — **rien n'a ete modifie** | oui, dans sa version actuelle |
| 3 | precondition de deploiement non tenue | oui |
| 4 | une autre mise a niveau tient le verrou | oui |
| 5 / 7 | la compensation n'a pas pu tout rendre, ou ne peut pas le prouver | **non** — reprendre |
| 6 | reprise refusee : une condition n'est pas etablie | **non** |
| 8 | verrou perdu en cours de route | **non** — reprendre |
| 9 | base ACTIVE, migrations manquantes, mise a niveau **non demandee** | oui |

---

## 6. Ce qui est mesure, et par quoi

`db/test/mise_a_niveau_active.sh` installe une **ancienne version reelle** par
sa propre commande officielle, la peuple **par le produit** (projet, etude,
variante, PDF, DXF), puis la fait evoluer par la commande officielle du depot
courant. Il verifie ensuite, dans cet ordre :

* le **diagnostic** n'a pas touche au registre ;
* les **refus** : sans consentement, avec un consentement qui nomme une autre
  base, sans sauvegarde, avec une archive qui n'est pas celle de cette base,
  application connectee ;
* la **concurrence** : deux mises a niveau simultanees, une seule applique
  (l'autre sort en 4) ;
* la **mise a niveau**, puis sa **relance** (idempotence) ;
* la **restauration** de la sauvegarde dans une base **isolee**, et la
  comparaison **ligne pour ligne** des tables metier — *un comptage identique
  de lignes ne suffit pas* ;
* l'**interruption** a une etape critique, puis la **reprise** prevue ;
* la **verification par le produit nouveau** : memes identifiants, meme
  filiation entre etude et variantes, memes entrees, memes resultats, memes
  empreintes, et les livrables retelecharges **aux memes octets**.

`deploy/demo_persistance.sh` fait le meme genre de constat a travers le
navigateur, sur la composition de demonstration.

---

## 7. Ce que ce document n'etablit pas

* **Supabase.** Le cycle complet n'a pas ete execute sur une instance
  Supabase ; la compatibilite reste `SUPABASE_UNVERIFIED`. Ce qui est etabli
  l'est sur PostgreSQL 16.
* **Un certificat public.** Les parcours HTTPS sont executes contre une
  autorite locale approuvee dans l'environnement d'essai.
* **Une reprise a un instant choisi.** Il n'y a ni archivage continu des
  journaux de transactions, ni point de reprise dans le temps : la sauvegarde
  est ponctuelle, et la restauration ramene a son horodatage.
* **Une duree.** Aucune mesure de fenetre d'interruption n'a ete faite sur un
  volume de production.
