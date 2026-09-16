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

## 1. Ce qu'il faut avoir

| | pour quoi |
|---|---|
| Docker et Docker Compose (v2.24 ou plus) | la pile entière tourne en conteneurs |
| `git`, `curl`, `python3` | le lanceur amorce l'espace de travail par l'API |
| Node.js 22 *(facultatif)* | uniquement pour rejouer le parcours au clavier (§4) |

Pas d'AutoCAD, pas de licence CAO, pas de compte Supabase. Le DXF est produit
par `ezdxf` (MIT) et s'ouvre avec le logiciel de votre choix.

## 2. Démarrer — une commande

```bash
git clone <url-du-depot> && cd eurostruct
deploy/demo.sh up
```

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
tout**), `comptes`, `reset` (détruit, avec consentement explicite).

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

8. Se reconnecter, choisir le projet : l'étude est dans l'**historique**, avec
   ses livrables. La session, elle, n'a pas survécu — c'est le contrat : aucun
   jeton n'est persisté.

## 4. La même chose, au clavier, mesurée

```bash
deploy/demo_persistance.sh
```

Il enchaîne `up`, un parcours Chromium qui fait les gestes du §3 et compare les
octets reçus aux empreintes enregistrées, `down`, `up`, puis un second parcours
qui retrouve l'étude — à l'écran, relue par l'API sous la même session, avec
ses deux livrables. Il laisse l'environnement debout. Fichiers produits :
`deploy/demo/note-de-calcul.pdf`, `deploy/demo/plan-de-ferraillage.dxf`,
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
parcours au clavier, `down`, `up`, `retrouver`. Deux contraintes de cet
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
| AutoCAD, BricsCAD, LibreCAD | **aucun n'a été ouvert.** Ce qui est établi sur le DXF, et ce qui ne l'est pas : [`DESSIN_DXF.md`](DESSIN_DXF.md) §5 |
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
