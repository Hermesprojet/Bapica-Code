# Essayer EUROSTRUCT

**Il n'y a pas de lien.** L'application n'est déployée nulle part. Ce qui suit
est la procédure exacte pour la faire tourner sur votre poste, en partant d'un
dépôt fraîchement cloné — et elle a été **suivie telle quelle** avant d'être
écrite (§7).

Une version antérieure de ce document promettait « une vérification à cinq
chapitres et ses documents, sans base ni compte ». C'était faux : l'étude
complète, sa note PDF et son plan DXF vivent dans un **projet**, et un projet
exige une base et une identité. La procédure ci-dessous fournit les deux.

---

## 0. Première utilisation, en cinq commandes

```bash
git clone -b claude/wip-6.3c-racine-de-confiance https://github.com/Hermesprojet/Bapica-Code.git
cd Bapica-Code/eurostruct
deploy/demo.sh prerequis     # dit ce qui manque, ne lance rien
deploy/demo.sh up            # construit (quelques minutes la première fois), démarre, amorce
deploy/demo.sh comptes       # le compte A et son mot de passe
```

Puis <http://127.0.0.1:3000> : se connecter avec le compte **A**, choisir le
projet « Démonstration — poutre belge », et suivre le §3 (créer, rouvrir,
créer une variante). Pour le faire faire au clavier et mesurer :
`deploy/demo_persistance.sh` (§4). Pour arrêter en gardant tout :
`deploy/demo.sh down`.

## 1. Ce qu'il faut avoir

| outil | minimum | pour quoi | testé ici avec |
|---|---|---|---|
| Docker Engine | celui qui porte Compose v2 (20.10 ou plus) | la pile entière tourne en conteneurs | 29.3.1 |
| Docker Compose | **2.24** — la surcouche emploie `!override` | assembler la composition | 5.1.1 |
| `git` | 2.x | cloner ; l'identité de build est le SHA du commit | 2.43.0 |
| `curl` | — | le lanceur amorce l'espace de travail par l'API | 8.5.0 |
| `python3` | 3.8 | vérifier les ports, lire les réponses JSON | 3.11.15 |
| Node.js *(facultatif)* | 22 | uniquement pour rejouer le parcours au clavier (§4) | 22.22.2 |

Ces minimums sont ceux que `deploy/demo.sh prerequis` vérifie ou que les
scripts emploient ; la colonne de droite est le poste sur lequel cette
procédure a été suivie (§7) : **Ubuntu 24.04.4 LTS, x86_64**.

Pas d'AutoCAD, pas de licence CAO, pas de compte Supabase. Le DXF est produit
par `ezdxf` (MIT) et s'ouvre avec le logiciel de votre choix.

## 2. Démarrer — une commande

```bash
git clone -b claude/wip-6.3c-racine-de-confiance https://github.com/Hermesprojet/Bapica-Code.git
cd Bapica-Code/eurostruct
deploy/demo.sh prerequis     # ce qu'il faut sur le poste, et ce qui manque
deploy/demo.sh up
```

`prerequis` ne lance rien : il dit, ligne par ligne, ce qui est là et ce qui
manque — Docker et son démon, Compose 2.24 ou plus (la surcouche emploie
`!override`), `git`, `curl`, `python3`, et les trois ports (8000, 3000,
54321) libres. Un port pris se change **avant** le premier `up`, par
`EUROSTRUCT_DEMO_PORT_API`, `_WEB` ou `_AUTH` : il est ensuite figé dans
`deploy/demo.env`. `up` refait les mêmes contrôles et refuse au premier
manquant, avec la même phrase.

Le premier appel construit deux images (quelques minutes), génère
`deploy/demo.env` — mots de passe tirés au hasard, ignoré par Git — puis
démarre, amorce et rend la main avec ceci :

```
   interface : http://127.0.0.1:3000
   API       : http://127.0.0.1:8000/ready
   comptes   : ingenieur-a@demonstration.invalid  et  ingenieur-b@demonstration.invalid
               (mots de passe: deploy/demo.sh comptes)
   projet    : « Démonstration — poutre belge »
```

Ce qui tourne alors, sur la boucle locale seulement :

| conteneur | rôle |
|---|---|
| `db` | PostgreSQL 16, migrations appliquées, référentiel des annexes posé |
| `demo-auth` | un émetteur de jetons **de démonstration**, clé de signature persistante |
| `api` | l'image de production de l'API, sous le login applicatif non superutilisateur |
| `web` | l'image de production de l'interface (`next build`, `next start`) |

Et, amorcés par les routes du produit sous le compte A : un bureau, le projet
belge, et les habilitations normatives des deux comptes d'essai.

Les autres commandes : `deploy/demo.sh status`, `down` (arrête, **garde
tout**), `comptes`, `journaux [service] [n]`, `reset` (détruit, avec
consentement explicite).

### 2.0 Passer à une nouvelle version sans perdre vos études

Vous récupérez une version plus récente du dépôt, et elle porte une migration
que votre base n'a pas. `up` **refuse** alors, sans rien appliquer — c'est
voulu. La suite :

```bash
deploy/demo.sh diagnostic      # ce qui serait fait — ne modifie RIEN
deploy/demo.sh mettre-a-jour   # sauvegarde, migration, redémarrage
```

`mettre-a-jour` construit la nouvelle version **pendant que l'ancienne sert
encore**, prend une sauvegarde complète, arrête les écritures, applique les
migrations manquantes, puis redémarre. Vos projets, études, variantes, PDF et
DXF sont là ensuite, aux mêmes identifiants et aux mêmes octets.

| commande | ce qu'elle fait |
|---|---|
| `deploy/demo.sh sauvegarder` | rôles, base et livrables dans `deploy/sauvegardes/<horodatage>/` |
| `deploy/demo.sh diagnostic` | annonce la version présente, la cible, les migrations prévues. Ne modifie rien |
| `deploy/demo.sh mettre-a-jour` | la mise à jour complète, données conservées |
| `deploy/demo.sh reprendre` | referme une mise à jour interrompue (machine éteinte, Ctrl-C) |
| `deploy/demo.sh restaurer <dossier>` | remet une sauvegarde en place (consentement explicite) |

`reset` reste **autre chose** : une suppression volontaire, qui ne prétend rien
conserver. Ce n'est pas la façon de changer de version. Détail complet :
`docs/MISE_A_NIVEAU.md`.

### 2.1 Où vivent les données, et ce qui les garde

Tout est sur **ce poste**, dans Docker ; rien ne part ailleurs.

| quoi | où | survit à `down` / `up` | survit à `reset` |
|---|---|---|---|
| projets, études, verdicts, journaux, lignes de livrables | volume `eurostruct-demo_db` (PostgreSQL) | **oui** | non |
| octets des notes PDF et des plans DXF | volume `eurostruct-demo_livrables` | **oui** | non |
| octets des pièces déposées (plans, cahiers des charges), sous `pieces/` | le même volume `eurostruct-demo_livrables` | **oui** | non |
| clé de signature de l'émetteur de démonstration | volume `eurostruct-demo_demo-cles` | **oui** | non |
| comptes d'essai, mots de passe, ports | `deploy/demo.env` (0600, ignoré par Git) | oui | **oui** — le supprimer regénère des comptes |
| la session du navigateur | nulle part | **non** : aucun jeton n'est persisté, on se reconnecte | — |

`deploy/demo.sh down` arrête les conteneurs et garde les trois volumes ;
`up` les remonte tels quels — c'est ce que `deploy/demo_persistance.sh`
mesure. `reset` détruit les volumes et exige
`EUROSTRUCT_DEMO_RESET=oui-detruire-les-donnees-de-demonstration`. Une
étude enregistrée est **immuable** : une variante est un nouveau calcul, et
un document produit n'est jamais supprimé par le produit.

### 2.2 Quand ça ne démarre pas

Chaque refus est écrit avec l'action qui permet de reprendre. Les cas
ordinaires :

| ce que vous lisez | cause | pour reprendre |
|---|---|---|
| `REFUS: demon docker: ne repond pas` | Docker est arrêté | démarrer Docker (Desktop, ou `sudo systemctl start docker`), puis `deploy/demo.sh up` |
| `MANQUE port 8000 (API) — deja pris sur ce poste` (ou 3000, 54321) | un autre service écoute | libérer le port, ou choisir `EUROSTRUCT_DEMO_PORT_API=8010` (`_WEB`, `_AUTH`) **avant le premier `up`** ; après, changer `API_PORT` et les URL dans `deploy/demo.env`, puis `down` et `up` |
| `MANQUE docker compose 2.20 (>= 2.24)`, `MANQUE curl`, `MANQUE python3` | dépendance absente ou trop ancienne | l'installer ou la mettre à jour, puis `deploy/demo.sh up` |
| `ECHEC: la construction des images s'est interrompue` | réseau coupé, proxy, Ctrl-C, disque plein | relancer `deploy/demo.sh up` : la construction repart du dernier étage réussi ; `docker system df` si le disque est en cause |
| `ECHEC: la composition n'est pas montee` puis les journaux `init` et `api` | l'initialisation de la base a refusé, ou un conteneur ne passe pas sa sonde | lire la cause dans le journal affiché (`deploy/demo.sh journaux init`), corriger, relancer `up` — l'initialisation constate ce qui est déjà fait |
| `ECHEC: /ready ne passe pas au vert` | l'API tourne mais une dépendance est rouge | `deploy/demo.sh status` nomme la vérification rouge ; `deploy/demo.sh journaux api` porte la cause |
| `ECHEC: cette version du depot porte une migration que la base de demonstration existante n'a pas` | vous avez récupéré une version plus récente du dépôt, et `up` **n'applique aucune migration à une base en service** : rien n'a été fait, vos études sont intactes | `deploy/demo.sh diagnostic` pour voir, puis `deploy/demo.sh mettre-a-jour` : sauvegarde, migration, redémarrage, **données conservées** (§2.0, `docs/MISE_A_NIVEAU.md`) |
| « Session expirée » après un redémarrage | aucun jeton n'est persisté | se reconnecter (§2.1) |

## 3. Le parcours court, avec ce que vous devez voir à chaque pas

Connexion → projet belge → étude → PDF/DXF → réouverture → variante → retour
à l'origine. Les résultats attendus sont ceux **mesurés** par le parcours au
clavier du §4 sur le même dépôt ; les fichiers de référence qu'il produit
(`deploy/demo/`) sont ceux joints au rapport de lot. Quand ce que vous voyez
diffère de la colonne « attendu », c'est une anomalie à signaler — avec le
pas, et la valeur vue.

Avant : `deploy/demo.sh up`, puis `deploy/demo.sh comptes` pour le mot de
passe du compte A.

| # | geste | attendu | si ce n'est pas cela |
|---|---|---|---|
| 1 | ouvrir <http://127.0.0.1:3000> | le bandeau **« Environnement de démonstration »** (voulu, §5) et le formulaire de connexion | page vide ou erreur : `deploy/demo.sh status`, puis `journaux web` |
| 2 | se connecter avec le compte **A** | le bouton **Déconnexion** et le sélecteur **Projet** | « identifiants refusés » : `deploy/demo.sh comptes` (le mot de passe est dans `deploy/demo.env`) |
| 3 | choisir « Démonstration — poutre belge » | l'étape 1 affiche le référentiel **BE — 2026-…** en lecture seule ; l'**Historique** est vide au premier essai ; l'écran ne propose ni pays ni annexe à choisir | projet absent : `deploy/demo.sh up` refait l'amorçage |
| 4 | remplir les sept étapes avec les valeurs de référence : section 300 × 600, d = 550, portée 6000 ; C30/37, B500B, XC3 ; M_Ed 250, V_Ed 300, M_car 180, M_qp 120 ; 4 Ø20, cadres 2 brins Ø10 e = 150, enrobage 40, cot θ 1,5, ancrage 800 ; φ(∞,t0) 2,0, travée simplement appuyée ; entrées facultatives (b_eff/b_w, classe associée, α1–α6) **vides** | chaque onglet passe de « incomplète » à « remplie » ; le bouton de lancement reste gris tant que le mode strict est coché et qu'aucun paramètre belge n'est confirmé sur cette instance (§6) | un champ refusé « un nombre » : virgule ou point acceptés, pas d'unité dans le champ |
| 5 | étape **Mode** : décocher *strict*, cocher la case qui assume l'exploratoire, **Vérifier les cinq chapitres** | la synthèse **Étude P1**, cinq chapitres verts : flexion **92,2 %**, effort tranchant **88,7 %**, ancrage **81,6 %**, fissuration **92,3 %**, flèche **58,9 %** ; la mention **« PROJET — NON SIGNABLE »** ; l'historique gagne une ligne **« étude initiale »** | un chapitre rouge : une valeur du pas 4 diffère (le taux dit lequel) ; un refus 422 : le bandeau nomme le paramètre et la clause, rien n'est enregistré |
| 6 | **Note PDF** | un fichier `note-de-calcul…pdf` de **12 pages** : cinq chapitres dans l'ordre, données d'entrée avec unités, verdicts, clauses ; la mention en tête et en pied ; dans **Livrables**, la ligne porte la même empreinte SHA-256 que le fichier reçu (`sha256sum`) | pas de téléchargement : `deploy/demo.sh journaux api` |
| 7 | **Plan DXF** | un fichier DXF **R2018** (`AC1032`) ; ouvert dans LibreCAD : coupe 300 × 600, 4 HA20 en lit inférieur, cadre HA10 e = 150, deux cotes « 300 » et « 600 », cartouche **« Démonstration — poutre belge (DEMO-BE-001) »**, « PROJET - NON SIGNABLE », notice de validation ; textes noirs en impression couleur comme en monochrome (§8) | textes jaunes ou losanges « ◊ » : version antérieure au 17/09 |
| 8 | fermer le navigateur ; `deploy/demo.sh down` puis `deploy/demo.sh up` ; se reconnecter, choisir le projet | la session n'a pas survécu (voulu : aucun jeton persisté) ; l'étude est dans l'**historique** ; **Rouvrir** montre **les mêmes cinq verdicts et taux qu'au pas 5**, « rouverte sans recalcul », les entrées gelées avec leurs unités ; dans **Livrables**, **Télécharger** rend **les mêmes octets** (même SHA-256) | historique vide : les volumes ont été détruits (`reset`) ou `demo.env` a changé |
| 9 | **Créer une variante** sous la synthèse, ne rien modifier, réassumer l'exploratoire, lancer | un **nouvel identifiant** ; le bandeau « Variante de l'étude … » avec **Rouvrir l'étude d'origine** ; les mêmes cinq taux qu'au pas 5 ; dans l'historique, la ligne **« variante de P1 <id court> »** et, sur l'origine, **« 1 variante »** | « Non repris — lancement bloqué » : une entrée de l'origine n'a pas pu être reprise ; le message la nomme, saisissez-la ou détachez |
| 10 | **Rouvrir l'origine**, **Créer une variante**, mettre **5** barres, lancer | flexion **75,8 %**, effort tranchant 88,7 %, ancrage **65,3 %**, fissuration **84,8 %**, flèche **50,7 %** ; l'origine affiche **« 2 variantes »** | un autre taux : une autre valeur a bougé ; comparez les entrées de la synthèse |
| 11 | **Rouvrir l'étude d'origine** (bouton de la synthèse, ou de la ligne d'historique) | les cinq verdicts **du pas 5**, aucun bandeau de variante, sa note PDF toujours dans les livrables ; depuis l'historique, déplier « 2 variantes » puis **Rouvrir** l'une d'elles ramène ses propres taux | — |
| 12 | changer de projet, ou **Déconnexion** | plus de synthèse, plus d'historique, plus de lien de variante : rien du dossier précédent ne reste à l'écran | — |

Les valeurs des pas 5 et 10 sont celles du moteur pour ces entrées sous
l'Annexe belge transcrite (paramètres **non confirmés** : mode exploratoire).
Elles ne changent qu'avec les entrées, le moteur ou le référentiel — et alors
l'empreinte de calcul change avec elles.

### 3.1 Partir d'un plan plutôt que d'une saisie

Au-dessus des sept étapes, **Documents du projet** reçoit un plan PDF ou DXF,
ou un cahier des charges PDF. Un DWG est conservé mais **pas lu** (aucune
licence ODA ou RealDWG) : exportez-le en DXF. Rien n'est obligatoire — la
saisie manuelle reste entière.

| # | geste | attendu |
|---|---|---|
| 1 | choisir la nature, le fichier, **Déposer et analyser** | la pièce apparaît avec son statut de lecture (« analysé », « partiellement lu : … », « DWG conservé, non lu ») et ses décomptes « N à revoir · 0 confirmée(s) » ; la revue s'ouvre |
| 2 | dans la revue, lire une ligne | la valeur **proposée**, le texte cité tel qu'il a été lu, la page, la méthode (couche texte, OCR, entité DXF), la confiance, et d'où vient l'unité ; « Vous décidez en tant que *votre nom* » |
| 3 | **Confirmer**, **Corriger** (valeur, unité, motif) ou **Rejeter** (motif) | la ligne revient décidée, à votre nom, datée par le serveur, et n'offre plus de geste : une décision est définitive |
| 4 | **Reporter dans l'étude** (repère en cours, ex. « P1 ») | les champs correspondants se remplissent **dans l'unité du champ** (30 cm → 300 mm), chacun avec son origine (pièce, page, texte, décision) ; une valeur rejetée ou seulement proposée n'est jamais reportée |
| 5 | modifier un champ reporté | son origine disparaît : la valeur redevient une saisie |
| 6 | lancer l'étude | la note PDF gagne une section « Origine des données d'entrée » qui cite la pièce, la page et la décision de chaque champ reporté |

Un fichier qui n'est ni PDF, ni DXF, ni DWG est refusé **sur ses octets**,
quelle que soit son extension. Une charge lue (« Q = 2,5 kN/m² ») se confirme
mais ne devient jamais une sollicitation : `M_Ed` et `V_Ed` restent saisis.

Ce parcours est mesuré au clavier par `db/test/parcours_livrable.sh` (pile
dressée sur l'hôte : PostgreSQL, API, build de production de l'interface,
Chromium), **pas encore** par `deploy/demo_persistance.sh` sur la composition
Docker (§8).

## 4. La même chose, au clavier, mesurée

```bash
deploy/demo_persistance.sh
```

Il enchaîne `up`, un parcours Chromium qui fait les gestes du §3 et compare les
octets reçus aux empreintes enregistrées, `down`, `up`, puis un second parcours
qui clique **Rouvrir** et vérifie, chapitre par chapitre, que l'état et le taux
affichés sont ceux enregistrés le premier jour, que les entrées affichées sont
celles du calcul gelé, qu'aucun calcul n'a été lancé (les POST sont comptés),
puis retélécharge la note et le plan depuis la liste des livrables et compare
leurs octets aux empreintes initiales. Un troisième parcours mesure les
variantes en quatre temps : **A** une variante sans modification — chaque
champ prérempli est comparé à la **requête gelée** de l'origine (valeur et
unité saisies), et le calcul lancé rend la même empreinte d'entrées et la
même empreinte de calcul, sous un identifiant différent qui nomme l'origine ;
**B** une variante à 5 barres, dont les entrées gelées ne diffèrent de
l'origine que sur `bars.count` ; **C** une étude portant les paramètres
avancés (XF1 avec classe associée XC3, b_eff/b_w, six coefficients d'ancrage)
puis sa variante identique ; **D** le retour à l'origine par l'historique et
dans l'autre sens, ses cinq verdicts du premier jour intacts, puis le
changement de projet et la déconnexion, qui effacent l'écran. Il laisse
l'environnement debout.
Fichiers produits : `deploy/demo/note-de-calcul.pdf`,
`deploy/demo/plan-de-ferraillage.dxf`, `deploy/demo/etude-creee.png` (la
capture de l'étude au premier jour), `deploy/demo/etude-rouverte.png` (la
capture de l'étude rouverte), `deploy/demo/note-de-calcul.retrouvee.pdf`,
`deploy/demo/plan-de-ferraillage.retrouve.dxf`, `deploy/demo/etude-variante.png`
(la capture de la variante à 5 barres), `deploy/demo/note-de-calcul.variante.pdf`,
`deploy/demo/etat.json` (identifiants, empreintes, entrées gelées et requête
gelée de l'étude, de ses variantes et de l'étude avancée).

## 5. Ce qui est de démonstration, et ce qui ne l'est pas

**Les comptes.** A et B sont des comptes d'essai, tirés au hasard sur votre
poste. Ils sont tous deux habilités sur BE / EN 1992-1-1 pour que le circuit
à deux personnes puisse être **exercé** : A propose, B relit et approuve, la
décision est consommée, et le mode strict s'ouvre pour ce paramètre. Une
décision prise ainsi éprouve le circuit ; elle **ne représente aucune
approbation réelle** d'un paramètre national. L'API le dit (`/health` :
`"environnement": "demonstration"`), l'écran l'affiche.

**Tout le reste est le produit** : mêmes images, mêmes migrations, mêmes
politiques RLS, même vérification des jetons (RS256, JWKS, émetteur, audience,
expiration), mêmes refus. Le seul écart avec `compose.yaml` : les livrables
vont sur le volume `livrables` au lieu d'un MinIO — `--profile objets` le
rend, voir [`DEPLOIEMENT_BASE_HEBERGEE.md`](DEPLOIEMENT_BASE_HEBERGEE.md) §7.

## 6. Ce que vous allez voir refuser, et c'est le produit qui fonctionne

* **Le mode strict refuse** tant que les 19 paramètres belges ne sont pas
  confirmés à quatre yeux **sur cette instance**, et rend le refus comme une
  liste de travail. Le bandeau de référentiel sépare trois états — transcrit
  dans le dépôt, décidé sur cette base, utilisable pour ce calcul.
* **Décocher le mode strict** exige une case explicite, et le résultat porte
  « PROJET — NON SIGNABLE » : aucune correction de section ne le rendra
  signable.
* **Une poutre en XF ou XA** est refusée sur `w_max` : le tableau belge ne
  donne aucune ligne à ces classes, et le moteur ne rabat pas sur 0,3 mm.

**Votre passage réel dans le circuit** — avec votre compte, sur une instance
qui n'est pas de démonstration — exige une seconde personne, distincte,
habilitée. PostgreSQL l'impose par contrainte de table
(`decision_two_distinct_principals`). Rien de ce qui précède ne bloque le
démarrage, les calculs exploratoires ni les exports en attendant.

## 7. Ce qui a été suivi, et où

Cette procédure a été suivie du début à la fin depuis un environnement vierge
— Docker démarré à neuf, images construites depuis le dépôt, `demo.sh up`,
parcours au clavier, `down`, `up`, `retrouver`, `variante` — sur Ubuntu
24.04.4 LTS avec les versions du §1. Deux contraintes de cet
environnement-là, qui ne sont pas les vôtres :

* les conteneurs de construction ne connaissaient pas l'autorité de
  certification de son proxy de sortie ; deux images de base locales la
  portaient. Sur un poste ordinaire, `pip` et `npm` joignent leurs index
  directement ;
* le registre `minio/minio` y était injoignable ; la démonstration n'en a pas
  besoin (§5).

## 8. Ce qui n'a pas été essayé, et ne doit pas être annoncé

| | état |
|---|---|
| Supabase réel | **jamais traversé.** `SUPABASE_UNVERIFIED`. La recette et ce qui lui manque : [`DEPLOIEMENT_BASE_HEBERGEE.md`](DEPLOIEMENT_BASE_HEBERGEE.md) §5–§6 |
| LibreCAD | **ouvert et imprimé sans écran** (2.2.0.2, `dxf2pdf`, A3, **couleur et monochrome**) sur le DXF livré par le parcours : géométrie, deux cotes avec valeur et flèches, barres, textes, unités, cartouche et « PROJET - NON SIGNABLE » lisibles. Six défauts trouvés et corrigés les 16 et 17/09 — cotes sans valeur, tiret cadratin en « ◊ », mention absente du cartouche, dossier imprimé « — », textes jaunes et cotes cyan sur blanc en impression couleur, cartouche de la flexion seule portant un identifiant technique au lieu du nom du dossier. Ce qui est établi et ce qui ne l'est pas : [`DESSIN_DXF.md`](DESSIN_DXF.md) §5.5 |
| note PDF | **rasterisée et relue** (poppler 24.02, 150 dpi, 12 pages) : cinq chapitres dans l'ordre, données d'entrée avec unités, verdicts, références de clause, mention en tête et en pied. Un défaut trouvé et corrigé : un symbole long recouvrait la colonne voisine. Le tiret cadratin y est rendu « -- » (police standard, substitution déclarée) |
| AutoCAD, BricsCAD | **aucun n'a été ouvert.** |
| lecture des plans sur la composition Docker | **non suivie.** L'image de l'API (paquet de lecture, `tesseract-ocr` fra/eng) **se construit** — en intégration continue, sur `7863b49` —, mais la composition n'y démarre pas : le registre refuse `minio/minio`, comme avant ce lot. Le parcours du §3.1 a été suivi sur l'hôte, pas dans les conteneurs |
| plans réels | **aucun.** Les plans éprouvés sont fabriqués par les tests ; le rappel sur un plan de bureau d'études n'est pas mesuré, et l'OCR est borné (`docs/LECTURE_DES_PLANS.md` §6) |
| validation d'un projet calculé | distincte de la validation des paramètres, et non acquise |

## 9. Sans Docker : le moteur seul

`./dev.sh` démarre l'API et l'interface sur l'hôte, sans base ni compte. Le
**calcul exploratoire de flexion** y fonctionne — déterministe, rien n'est
écrit. Ce chemin **ne donne pas** l'étude à cinq chapitres, ni le PDF, ni le
DXF conservés : ils exigent un projet, donc la base et l'identité du §2.

## 10. Avant tout usage réel

Lire [`VALIDATION.md`](VALIDATION.md). Tout document produit par un calcul non
strict porte **« PROJET — NON SIGNABLE »**, et cette mention n'est pas
décorative.
