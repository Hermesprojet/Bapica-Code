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

### 2.1 Où vivent les données, et ce qui les garde

Tout est sur **ce poste**, dans Docker ; rien ne part ailleurs.

| quoi | où | survit à `down` / `up` | survit à `reset` |
|---|---|---|---|
| projets, études, verdicts, journaux, lignes de livrables | volume `eurostruct-demo_db` (PostgreSQL) | **oui** | non |
| octets des notes PDF et des plans DXF | volume `eurostruct-demo_livrables` | **oui** | non |
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
| « Session expirée » après un redémarrage | aucun jeton n'est persisté | se reconnecter (§2.1) |

## 3. Créer une étude, la retrouver — le parcours court

1. Ouvrir <http://127.0.0.1:3000>. Le bandeau **« Environnement de
   démonstration »** est affiché : c'est voulu, voir §5.
2. Se connecter avec le compte **A** (`deploy/demo.sh comptes`).
3. Dans **Projet**, choisir « Démonstration — poutre belge ».
4. Remplir les sept étapes de l'étude. Les valeurs du parcours de référence :
   section 300 × 600, d = 550, portée 6000 mm ; C30/37, B500B, classe XC3 ;
   M_Ed 250 kN·m, V_Ed 300 kN, M_car 180, M_qp 120 ; 4 Ø20, cadres 2 brins
   Ø10 e = 150, enrobage 40, cot θ = 1,5, ancrage disponible 800 ;
   φ(∞,t0) = 2,0, travée simplement appuyée.
5. Étape **Mode** : décocher *strict*, cocher la case qui assume
   l'exploratoire, puis **Lancer**. La synthèse affiche cinq chapitres et la
   mention **« PROJET — NON SIGNABLE »**.
6. **Note PDF** et **Plan DXF** : les deux se téléchargent ; leur empreinte
   SHA-256 est celle que la base a enregistrée.
7. Fermer le navigateur. Puis :

   ```bash
   deploy/demo.sh down
   deploy/demo.sh up
   ```

8. Se reconnecter, choisir le projet : l'étude est dans l'**historique**.
   **Rouvrir** la ramène dans la synthèse à cinq chapitres — les mêmes
   verdicts, les mêmes taux, les mêmes entrées et les mêmes empreintes que le
   jour du calcul, et la synthèse dit que rien n'a été recalculé. Dans
   **Livrables**, **Télécharger** rend la note et le plan : les mêmes octets,
   pas un document recomposé. La session, elle, n'a pas survécu — c'est le
   contrat : aucun jeton n'est persisté.
9. **Créer une variante**, sous la synthèse de l'étude rouverte : les sept
   étapes se préremplissent avec les entrées **enregistrées** de l'étude (pas
   avec ce qui avait été tapé), et le bandeau nomme l'étude d'origine.
   Modifier ce qu'on veut — par exemple 5 Ø20 au lieu de 4 — réassumer le
   mode exploratoire, lancer. Le nouveau calcul reçoit **son propre
   identifiant** et sa synthèse porte « Variante de l'étude … » avec un
   bouton **Rouvrir l'étude d'origine** ; l'étude initiale et ses documents
   restent tels quels dans l'historique et les livrables. Changer de projet
   ou se déconnecter efface tout ce qui était affiché du dossier précédent.

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
leurs octets aux empreintes initiales. Un troisième parcours crée une variante
depuis l'étude rouverte (chaque champ prérempli est comparé à l'entrée gelée,
5 barres au lieu de 4, identifiant propre, origine nommée), rouvre l'origine
et vérifie ses cinq verdicts du premier jour, puis change de projet et se
déconnecte en vérifiant que l'écran ne montre plus rien du contexte
précédent. Il laisse l'environnement debout.
Fichiers produits : `deploy/demo/note-de-calcul.pdf`,
`deploy/demo/plan-de-ferraillage.dxf`, `deploy/demo/etude-rouverte.png` (la
capture de l'étude rouverte), `deploy/demo/note-de-calcul.retrouvee.pdf`,
`deploy/demo/plan-de-ferraillage.retrouve.dxf`, `deploy/demo/etude-variante.png`
(la capture de la variante), `deploy/demo/note-de-calcul.variante.pdf`,
`deploy/demo/etat.json`.

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
| LibreCAD | **ouvert et imprimé sans écran** (2.2.0.2, `dxf2pdf`, A3, monochrome) sur le DXF livré par le parcours : géométrie, deux cotes avec valeur et flèches, barres, textes, unités, cartouche et « PROJET - NON SIGNABLE » lisibles. Quatre défauts trouvés et corrigés le 16/09 — cotes sans valeur, tiret cadratin en « ◊ », mention absente du cartouche, dossier imprimé « — ». Ce qui est établi et ce qui ne l'est pas : [`DESSIN_DXF.md`](DESSIN_DXF.md) §5.5 |
| note PDF | **rasterisée et relue** (poppler 24.02, 150 dpi, 12 pages) : cinq chapitres dans l'ordre, données d'entrée avec unités, verdicts, références de clause, mention en tête et en pied. Un défaut trouvé et corrigé : un symbole long recouvrait la colonne voisine. Le tiret cadratin y est rendu « -- » (police standard, substitution déclarée) |
| AutoCAD, BricsCAD | **aucun n'a été ouvert.** |
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
