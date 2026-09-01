# Politique de sauvegarde et de reprise

> **CE DOCUMENT DÉCRIT UNE POLITIQUE VOULUE, PAS UN SERVICE FOURNI.**
>
> Rien de ce qui suit n'est en place dans un environnement d'exploitation :
> aucune infrastructure de production n'existe à ce jour, aucune sauvegarde
> planifiée n'a été configurée, aucun exercice de restauration n'a été mené
> hors du harnais de test. Ce texte fixe les objectifs à tenir et le contrat
> que l'infrastructure devra remplir. Il ne doit être cité ni dans un contrat
> client, ni dans une réponse d'appel d'offres, tant qu'il n'a pas été rendu
> vrai par une configuration réelle et un exercice daté.
>
> Ce qui **est** prouvé dans ce dépôt : `db/test/sauvegarde_restauration.sh`
> exerce le cycle complet — sauvegarde, destruction totale, restauration,
> confrontation des empreintes — contre un PostgreSQL et un MinIO jetables.
> C'est la mécanique, pas l'exploitation.

## 1. Objectifs

| Objectif | Valeur visée | Ce qu'elle signifie concrètement |
|---|---|---|
| **RPO** — perte de données maximale | **15 minutes** | Un sinistre ne doit jamais coûter plus d'un quart d'heure d'écritures. Un calcul enregistré à 14 h 50 doit être retrouvé après une panne à 15 h 00. |
| **RTO** — durée maximale d'interruption | **4 heures** | Entre la décision de restaurer et le service rendu de nouveau, tout compris : approvisionnement, restauration, vérification, bascule. |

Ces deux valeurs se tiennent ensemble. Un RPO de 15 minutes obtenu par une
sauvegarde qu'on ne sait pas restaurer en 4 heures ne protège de rien.

## 2. Base de données

* **PITR** (restauration à un instant donné) par **archivage WAL continu**,
  vers un stockage distinct de celui du serveur. C'est le seul mécanisme qui
  tienne un RPO de 15 minutes ; une sauvegarde nocturne seule donnerait un RPO
  de 24 heures.
* **Sauvegarde complète nocturne**, **chiffrée au repos**, en plus du WAL. Le
  PITR sans base complète récente allonge la restauration au-delà du RTO.
* Format `pg_dump -Fc` pour les exports logiques ponctuels ; l'image physique
  (`pg_basebackup` ou équivalent géré) pour la chaîne PITR.

## 3. Stockage objet

Les octets des livrables ne sont pas reconstructibles depuis la base : celle-ci
n'enregistre que leur empreinte et leur chemin. Perdre le magasin, c'est perdre
les documents.

* **Versionnement d'objets activé** — il protège de l'écrasement et de la
  suppression accidentelle, y compris par un opérateur.
* **Réplication hors site** vers une seconde région ou un second fournisseur.
* La politique de rétention du magasin reste celle de `docs/STOCKAGE.md` §5 :
  **le produit ne supprime jamais**. Une sauvegarde ne change rien à cela.

## 4. Conservation

| Génération | Nombre conservé |
|---|---|
| Quotidiennes | **30** |
| Mensuelles | **12** |
| Annuelles | archivées, **au moins 10 ans** |

Les 10 ans ne sont pas un choix de confort : c'est la durée de la
responsabilité décennale, et la raison pour laquelle un livrable doit rester
retrouvable et opposable dix ans après sa remise.

## 5. Exercice de restauration

**Mensuel**, sur un environnement jetable, et **avec confrontation
d'empreintes** — pas seulement « la base démarre » :

1. restaurer la base et le magasin à un instant choisi ;
2. relire un échantillon de livrables par le chemin produit ;
3. recalculer le SHA-256 de leurs octets et le confronter à la colonne
   `deliverables.sha256` ;
4. consigner la date, la durée réelle, l'instant restauré et le résultat.

Une sauvegarde dont la restauration n'a pas été exercée depuis un mois doit
être considérée comme non prouvée. **Le RTO se mesure sur cet exercice**, pas
sur une estimation.

## 6. Clés de chiffrement

Les clés sont détenues par **l'infrastructure ou l'opérateur**, jamais par
l'application. L'API ne doit posséder aucun moyen de déchiffrer une sauvegarde
ni d'en supprimer une : un service compromis ne doit pas pouvoir détruire ce
qui permettrait de réparer sa compromission.

Aucune clé, aucun DSN complet, aucun identifiant réel ne figure dans ce dépôt
(voir la garde d'environnement, `api/.env.example`).

## 7. Ce qu'il reste à faire pour rendre ce document vrai

1. Provisionner l'infrastructure et configurer l'archivage WAL.
2. Activer le versionnement et la réplication du magasin objet.
3. Planifier la sauvegarde nocturne chiffrée et la rotation ci-dessus.
4. Mener un **premier** exercice de restauration complet, le dater, et
   consigner le RTO mesuré.
5. Alors seulement, remplacer l'avertissement en tête de ce document.
