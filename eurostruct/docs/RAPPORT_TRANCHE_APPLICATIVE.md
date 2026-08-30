# RAPPORT — première tranche applicative exécutable

**Branche** `claude/wip-6.3c-racine-de-confiance` · **base** `4a489f4` · **SHA final** `da04d7e`

---

## 1. Le parcours qu'un utilisateur peut exécuter aujourd'hui

```
eurostruct/dev.sh                    # une commande, deux services
  -> API      http://localhost:8000  (/health, /ready, /docs)
  -> interface http://localhost:3000
```

Le script **attend que les deux répondent** avant de rendre la main. Un
processus lancé n'est pas un service disponible, et annoncer l'un pour l'autre
fait chercher la panne du mauvais côté.

Ensuite, dans le navigateur :

1. **Connexion Supabase** si la configuration est présente. Le jeton reste en
   mémoire — jamais dans `localStorage`, qu'un script tiers lirait.
2. **Saisie d'une poutre rectangulaire** (b, h, d, M_Ed, béton, acier).
3. **Calcul** → `POST /v1/calculations/ec2/beam-flexure`.
4. **En mode strict — le cas normal aujourd'hui — la réponse est un refus
   422**, rendu comme une **liste de travail** : les 8 paramètres nationaux
   bloquants, chacun avec sa clause et son annexe. Ce n'est pas une page
   d'erreur : c'est ce qu'il reste à faire pour que l'étude soit signable.
5. **En mode exploratoire** (`strict_ndp=false`, demandé explicitement) : le
   résultat s'affiche sous la mention **« PROJET — NON SIGNABLE »**, portée par
   la réponse HTTP elle-même et pas seulement par l'écran — une note produite
   par un autre client doit la porter aussi.
6. **DXF** de la section ferraillée, téléchargeable.
7. **Bandeau de référentiel** avant tout calcul — « Référentiel BE — 0 / 29
   valeur(s) confirmée(s) » — et, replié dessous, le **plan de charge** : les
   29 paramètres, leur clause, leur annexe, leur folio, et ce qui reste à faire
   sur chacun. La question « où en est la Belgique ? » ne devrait pas exiger de
   saisir une poutre.
8. **Autorité** : proposer une décision, la faire approuver par un second
   ingénieur, la consommer une fois. L'identité vient **du jeton vérifié et de
   lui seul** : aucun point d'entrée n'accepte `actor_id`, proposant ou
   approbateur comme donnée.

Vérifié dans un Chromium réel sur le build de production :
strict → refus nommant 8 paramètres ; non-strict → `A_s = 849 mm²`,
`M_Rd = 150,0 kN·m`, utilisation 100,0 %, 4 vérifications ;
DXF `P1.dxf`, 64 537 octets, en-tête `AC1032` valide.

---

## 2. Ce que ce lot a trouvé, et qui n'était pas dans la commande

### 2.1 Un fichier du dépôt ouvrait la porte du mode strict

`confirmation.py` annonce, en toutes lettres :

> « aucun fichier editable du depot ne peut rendre une regle REELLE
> strict-ready »

**L'annonce était fausse.** Mesuré le 30/08 : en basculant deux champs de
`be.json` — `validation_status` à `confirmed` et `value_provenance` à
`national_annex` — un calcul belge en mode **strict** aboutit et se déclare
signable, avec pour vérificateur la chaîne de caractères qu'on a bien voulu
écrire. Aucun quatre-yeux, aucune ligne en base, aucun `ConfirmationProvider`
consulté.

`assert_provider_is_usable_in_production` gardait un chemin que le calcul ne
prend pas : le portillon du strict est `usable_in_strict_mode`, qui lit ce
fichier.

**Fermé** (`07df06c`) : le chargeur JSON refuse `confirmed`. Un fichier
transcrit ; il ne confirme pas. Le cas de régression **fait l'édition** — il
copie les données, bascule les 22 paramètres et appelle
`load_country_registry` — parce que vérifier qu'une fonction refuse une chaîne
ne prouverait rien sur le chemin réel.

### 2.2 Le provider écrivait des décisions que rien ne pouvait relire

`confirmations_for` et `revocations_for` levaient `NotImplementedError`. Tout
l'appareil du quatre-yeux — décompte des regards indépendants, politique de
production, `assess_confirmations` — existait et **ne recevait aucune donnée**.

**Implémenté** (`81523cf`), et la projection ne recopie pas, elle vérifie :

| confrontation | ce qu'elle attrape |
|---|---|
| `Digest` re-hache son payload | payload retouché sans le hash, et l'inverse |
| pile reconstruite vs `stack_digest` | pile substituée |
| dossier reconstruit vs `evidence_digest` | citation ou folio retouchés |
| version de canonicalisation | payload ancien réinterprété par la méthode d'aujourd'hui |

Les trois gardes ont été **éprouvées par mutation** : en retirant chacune, le
cas correspondant tombe.

S'y ajoute un garde que RLS rend nécessaire : sous `row level security`, un
rôle sans politique applicable ne reçoit pas d'erreur, il reçoit **zéro
ligne**. « Je n'ai pas le droit de voir » et « il n'y en a aucune » deviennent
le même octet — et c'est le second que lirait un décompte à quatre yeux. Le
provider demande donc à PostgreSQL, **avant** de conclure quoi que ce soit d'un
ensemble vide, si le rôle courant est couvert.

### 2.3 Chaque lecture émettait un avertissement PostgreSQL

```
WARNING:  there is already a transaction in progress
```

Le garde de rôle interrogeait la base sur **son propre curseur**, avant la
requête. Avec `autocommit=False`, ce premier ordre ouvre déjà la transaction :
le `begin` explicite qui suivait arrivait toujours en second. À chaque lecture,
sans que rien n'échoue — le genre de défaut qui dure. Reproduit **hors du
produit** avant d'y toucher.

Le garde partage désormais le curseur de la requête qu'il autorise. L'écriture,
elle, garde son `begin` : `SET LOCAL` n'a aucune portée hors transaction, et
aligner les deux « par symétrie » casserait le second chemin.

### 2.4 La seconde porte de la même pièce

`generate_ndp_seed.py` lit les **mêmes fichiers** que le moteur et écrit dans la
base de référence. Après §2.1, le moteur refusait `confirmed` mais le
générateur l'aurait encore émis : la base aurait dit une chose et le calcul une
autre — pire que les deux erreurs séparément. Il refuse maintenant aussi.

### 2.5 La mention obligatoire manquait sur la réponse de calcul

**Interdiction n° 8** — « ne jamais livrer un document sans la mention de
validation par un ingénieur ».

Le DXF la porte : `legal.py` l'y inscrit, `test_dxf.py` le vérifie. **La
réponse JSON, non.** Or c'est elle qu'un client transforme en note de calcul.

Ce qui rendait le manque invisible : le mode strict refuse partout
aujourd'hui, donc une réponse de succès est rare. Le jour où des paramètres
seront confirmés, un calcul strict rendrait un résultat sans mention, et
chaque client devrait penser à l'ajouter — l'interdiction serait respectée par
habitude plutôt que par construction.

`notice` et `mention` ne disent pas la même chose, et les fusionner ferait
disparaître l'une des deux :

| champ | dit | quand |
|---|---|---|
| `notice` | « doit être vérifié et signé par un ingénieur habilité » | **toujours** — aucun logiciel ne signe une note |
| `mention` | « PROJET — NON SIGNABLE » | seulement si des NDP non confirmés ont servi |

La première dit *pas encore signé*, la seconde *pas signable, par personne*.

### 2.6 Le workflow `EUROSTRUCT` était rouge pour l'outillage

Rouge depuis `2e342ec`, où `api_e2e.sh` est entré dans `db/test/run.sh`. Le job
« Schema de donnees » n'installait pas le paquet API : le harnais rendait 4
(NON EXÉCUTÉ) et `run.sh` sort en 1 dès qu'une surface n'a pas tourné — c'est
voulu, une garantie qu'on n'a pas pu vérifier n'est pas verte.

Même famille que le rouge de l'autre workflow, corrigé plus tôt : `httpx` vit
dans l'extra `dev` et `fastapi.testclient.TestClient` l'exige. Le poste de
développement l'avait installé à la main ; le runner non. **Les deux étapes
vérifient désormais leur propre effet** en important `TestClient`.

---

## 3. Commandes et résultats

### Démarrer la tranche

```
pip install -e eurostruct/engine -e "eurostruct/api[dev]"
(cd eurostruct/web && npm install)
eurostruct/dev.sh                 # API :8000 + interface :3000
```

`dev.sh` **attend que les deux répondent** avant de rendre la main. Sans
`.env`, l'API démarre quand même : `/health` répond et `/ready` dit ce qui
manque, sans révéler aucune valeur.

### Ce qui a été exécuté

| commande | résultat |
|---|---|
| `python -m pytest engine/tests -q -W error` | **collectes 962 · executes 962 · reussis 962 · ignores 0 · echoues 0**, aucun avertissement |
| `python -m pytest api/tests -q` | **collectes 86 · executes 86 · reussis 72 · ignores 14 · echoues 0** (les 14 E2E sautés hors décor) |
| `db/test/api_e2e.sh` (PostgreSQL 16 réel) | **14/14**, zéro résidu |
| `db/test/run.sh` | **rc=0 — les 31 surfaces vertes**, 0 base et 0 rôle résiduels |
| mutation du correctif d'avertissement | `begin` rétabli → le cas tombe (rc=1) ; corrigé → 14/14 |
| `eurostruct/run_tests.sh` | COMPLET — les 6 surfaces ont tourne, toutes vertes. |
| `npm run typecheck` / `npm run build` | passent |
| Chromium réel, build de production | bandeau et refus vérifiés (ci-dessous) |
| `scripts/audit_engine_dependencies.py` | 14 paquets, **aucun import réseau ni IA** |
| `db/seed/generate_ndp_seed.py` | graine **octet pour octet** identique à `0001_ndp.sql` ; le garde refuse une graine `confirmed` |

### Les mutations qui rendent les gardes décisives

En retirant chaque garde de la projection, le cas correspondant tombe :

| garde retirée | cas qui tombe |
|---|---|
| `pile.digest.digest != attendue` | `test_une_pile_substituee_est_refusee` |
| `confirmation.evidence.digest != attendu` | `…dossier_de_preuve_retouche…` et `…page_imprimee_retouchee…` |
| `version != CANONICALIZATION_VERSION` | `…version_de_canonicalisation_inconnue…` |

Un premier cas de falsification **ne pouvait pas échouer** : il remplaçait
`0.6` dans un payload qui ne le contient pas. La retouche est désormais
appliquée puis **vérifiée** avant l'assertion.

### Vu dans un vrai navigateur

- `Référentiel BE — 0 / 29 valeur(s) nationale(s) confirmée(s) au 2026-08-30.
  Aucune note signable ne peut être produite pour ce pays aujourd'hui.`
  Le bandeau suit le pays choisi ; aucune requête en échec.
- Le repli **« Voir les 29 paramètres et ce qui reste à faire »** ne charge
  rien tant qu'on ne l'ouvre pas : avant ouverture, un seul appel
  (`/v1/ndp/BE`) et zéro fiche rendue ; après, `/v1/ndp/BE/parameters` part et
  les 29 fiches s'affichent avec clause, annexe et folio imprimé.
  `cot_theta_max` y porte « aucune relecture ne le débloque ».
- strict → refus nommant les **8** paramètres bloquants sur 8 requis, chacun
  avec sa clause (`§3.1.6(1)P`) et son annexe (`NBN EN 1992-1-1 ANB`).
- non strict → `A_s = 849 mm²`, `M_Rd = 150,0 kN·m`, utilisation 100,0 %,
  4 vérifications, sous **« PROJET — NON SIGNABLE »**.
- DXF `P1.dxf`, 64 537 octets, en-tête `AC1032`.

### CI

| workflow | avant | après |
|---|---|---|
| `eurostruct — tests` | rouge depuis `2e342ec` (`httpx` absent des dépendances de base) | **vert** sur `d42a358` |
| `EUROSTRUCT` | rouge depuis `2e342ec` (job sans le paquet API : `api_e2e.sh` rendait 4) | **vert** sur `bb35cf8` |

Les deux étapes d'installation **vérifient leur propre effet** en important
`TestClient` : installer sans contrôler laisserait le rouge revenir sans dire
pourquoi.

---

## 4. Les interdictions vérifiées sur le chemin produit

Vérifiées en exécutant l'API, pas en relisant le code :

| interdiction | état | comment |
|---|---|---|
| n° 1 — aucun résultat produit par un LLM | tient | audit du **moteur** : 14 paquets, aucun import réseau ni IA. Étendu à la main aux deux couches ajoutées : dépendances de l'API = `fastapi`, `pydantic`, `psycopg2-binary`, `pyjwt[crypto]` ; de l'interface = `next`, `react`, `react-dom`. Aucune occurrence d'un client de modèle dans `api/` ni `web/` |
| n° 2 — aucune valeur inventée | tient | source et page sur chaque paramètre ; le fichier ne confirme plus (§2.1) |
| n° 6 — rien hors du domaine testé | tient | 5 entrées hors domaine → **5 refus 422**, chacun **nommant le domaine** |
| n° 7 — pas de « DWG natif » promis | tient | aucune occurrence de « DWG » dans l'API ni l'interface |
| n° 8 — mention de validation | **était fausse sur le JSON** | corrigée, §2.5 |

L'interdiction n° 6 tenait déjà ; ce qui manquait, c'est ce qui l'exerce. Sur
le chemin API, deux cas seulement étaient gardés (`d > h`, unité invalide).
Classe de béton inconnue, nuance d'acier inconnue et moment au-delà de
`mu_lim` ne l'étaient pas — ils le sont maintenant, et les cas vérifient que
le refus **énumère le domaine** plutôt que de se contenter de refuser.

---

## 5. Supabase

**Aucune preuve sur une instance Supabase réelle.** Raison précise : aucun
paramètre de staging n'est présent dans cet environnement, et le cahier des
charges interdit d'en demander ou d'en inventer. La **vérification** est celle
de production — algorithmes asymétriques seulement, `issuer`, `audience`,
`exp`, `nbf`, `sub`, `kid` inconnu, rechargement JWKS borné — mais les clés du
trousseau sont générées en mémoire dans les tests.

`SUPABASE_UNVERIFIED` reste vrai. `/ready` échoue tant que la configuration
n'est pas posée : le processus démarre pour pouvoir **dire** pourquoi il ne
peut pas servir, il ne sert pas en mode dégradé.

Aucun double de test ne peut satisfaire la fabrique de production : celle-ci
refuse tout authentificateur `est_fictif`, et le refus est **antérieur** à
l'ouverture de la connexion.

---

## 6. Ce qui bloque encore un MVP déployé

1. **Aucune valeur nationale n'est confirmée — 0 sur 29.** Le mode strict
   refuse donc pour tous les pays, et c'est le comportement voulu. Depuis
   `07df06c`, il est inatteignable par **tout** chemin ; il l'était auparavant
   par un mauvais chemin.
2. **Le pont manque entre la confirmation et le portillon.** Le provider sait
   maintenant lire, et `assess_confirmations` sait décider — mais **rien
   n'appelle `assess_confirmations` hors des tests**, et rien ne relie son
   verdict à `usable_in_strict_mode`. C'est la machinerie de sélection que le
   dépôt appelle 6.3b.
   **Elle ne peut pas être écrite sans apport normatif** : elle exige, pour
   chaque règle, l'empreinte de la spécification nationale et celle du code qui
   l'exécute. Les inventer violerait l'interdiction n° 2.
3. **Supabase n'a jamais été éprouvé sur un staging réel.**
4. Dette L6 non bloquante : 12 harnais non migrés, 50 attributions traduites,
   résidu `canal_<uuid>.jsonl`.

---

## 7. Ce qui exige une intervention humaine

| # | décision | pourquoi elle n'est pas la mienne |
|---|---|---|
| 1 | **Valider la fermeture des §2.1 et §2.4** | Elle ferme le niveau 3 « transcrit et signé dans un fichier » au profit du seul chemin d'autorité. C'est un choix de gouvernance, pas une correction de bogue — même si l'état antérieur était intenable. |
| 2 | Fournir un staging Supabase | Secrets et instance ; jamais dans la conversation. |
| 3 | Relever les valeurs des annexes | Un ingénieur nommé ouvre l'annexe publiée à la page citée. Aucun agent ne peut le faire à sa place. |
| 4 | Trancher ODA / RealDWG | Interdiction n° 7 : pas de promesse « DWG natif » avant. |

---

## 8. Statut

Ni `PRODUCTION_READY` ni « 6.3c CLOSED ». Ce lot livre une **tranche
applicative exécutable** et ferme deux trous mesurés. Il ne livre pas un
référentiel national confirmé, et sans lui aucune note ne peut être signée.
