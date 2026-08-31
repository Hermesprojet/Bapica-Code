# Rapport de lot — autorisation, magasin objet, entrée dans l'application

*Branche `claude/wip-6.3c-racine-de-confiance`, depuis `950259c`.*

**Ce lot ne revendique ni `PRODUCTION_READY`, ni compatibilité Supabase, ni
aucune validation humaine réelle.** Le registre national reste à **0 / 29**,
`SUPABASE_UNVERIFIED` reste vrai, et tout document tiré d'un calcul non strict
reste « PROJET — NON SIGNABLE ».

---

## 1. Les SHAs

| SHA | Ce qu'il ferme |
|---|---|
| `240a874` | La matrice d'autorisation, et PostgreSQL qui la fait respecter |
| `d20a345` | Les livrables quittent le disque pour un magasin objet réel |
| `e07d6c7` | Le produit avait un écran vide et aucune porte pour en sortir |
| `2bfdb36` | L'écran d'un compte tout neuf a enfin deux boutons |
| `4b4a2a5` | Le prévol CORS refusait `PATCH` : le panneau des membres était inatteignable |

---

## 2. Bloc 1 — les défauts d'autorisation

### Les preuves rouges, mesurées sur les octets de `950259c`

Quatre hypothèses ont été formulées avant d'écrire une ligne. **Les quatre
étaient vraies**, et deux défauts de plus sont apparus en les éprouvant.

1. **`is_active` n'était lu nulle part** sauf dans la primitive d'attestation.
   Ni `project_actor_is_member`, ni `project_actor_can_write`, ni
   `project_workspace_list`, ni aucune primitive de livrable ne le regardaient.
   Un accès révoqué gardait la lecture **et l'écriture**. La colonne existe
   depuis 0009 et sa raison d'être y est écrite ; elle n'était vraie que sur
   une seule route.

2. **Un simple `engineer` pouvait émettre** un livrable déjà attesté :
   `project_deliverable_finalize` ne contrôlait aucun rôle. La séparation entre
   celui qui rédige et celui qui répond du calcul disparaissait à la dernière
   étape — celle qui met le document en circulation.

3. **Une mutation refusée répondait 200.** Les politiques RLS filtrent la ligne
   par leur clause `using` : l'`update` touche alors **zéro** ligne, sans
   erreur, et la primitive rendait quand même l'état visé. Un refus qui se
   présente comme un succès est pire qu'un refus — le client range son document
   comme soumis, et il ne l'est pas.

4. **Les octets étaient déposés avant le contrôle d'autorisation.** Une
   tentative refusée laissait un objet dans le magasin, que plus aucune ligne ne
   référençait.

5. **Le `viewer` n'était bloqué que par accident**, par la clause `with check`
   d'une politique écrite pour décider autre chose.

6. **`validating_engineer` était rangé avec les rédacteurs.**

Mesure : `9 failed, 41 passed` sur `api/tests/test_autorisations.py`.

### La matrice effectivement appliquée

Elle vit dans **une seule fonction**, `project_exiger_capacite(org, capacité)`
(migration `0023`, étendue par `0024`), et les primitives l'appellent.

| Qui | Lecture | Rédaction | Validation | Administration |
|---|---|---|---|---|
| `owner` actif | ✔ | ✔ | ✘ | ✔ |
| `admin` actif | ✔ | ✔ | ✘ | ✔ |
| `engineer` actif | ✔ | ✔ | ✘ | ✘ |
| `validating_engineer` actif | ✔ | ✘ | ✔ | ✘ |
| `viewer` actif | ✔ | ✘ | ✘ | ✘ |
| membre **désactivé** | ✘ | ✘ | ✘ | ✘ |
| autre organisation | ✘ | ✘ | ✘ | ✘ |

* **Rédaction** = brouillon, révision, soumission à la relecture.
* **Validation** = retour motivé au brouillon, attestation, émission.
* **Administration** = inviter, lister l'annuaire, changer un rôle, révoquer.

Deux précisions qui ne se devinent pas :

* `project_actor_can_write` **garde** `validating_engineer` pour les projets et
  les calculs. Un ingénieur validateur lance évidemment des calculs ; ce qu'il
  ne fait pas, c'est rédiger le livrable qu'il attestera. La séparation porte
  sur le **document**, pas sur le travail.
* `validating_engineer` est **exclu de l'administration**, comme `engineer`.
  Porter la responsabilité technique d'un calcul et décider qui entre dans le
  bureau sont deux pouvoirs distincts ; les confondre ferait du validateur
  l'administrateur de fait de sa propre supervision.

**La ligne d'adhésion désactivée survit** — une note de dix ans doit rester
lisible et nommer son signataire (0009). Ce qui disparaît, c'est l'accès.

### Ce qui a été aligné plutôt que conservé

Trois cas de `test_livrables.py` encodaient l'ancien comportement, plus large.
Ils ont été **alignés sur la matrice**, pas conservés « pour compatibilité ».

---

## 3. Bloc 2 — le magasin objet

### Le défaut

Les octets d'un livrable ne vivaient que sur le **disque local** du conteneur
d'API. Un volume nommé repoussait le problème d'un cran ; il ne le fermait pas :
**deux instances derrière un répartiteur ne partagent pas ce disque**, et la
moitié des téléchargements aurait rendu 503 sur des livrables parfaitement
enregistrés. Un document conservé dix ans au titre de la décennale ne peut pas
dépendre du disque d'une machine.

### Ce qui a été construit

* `api/src/eurostruct_api/s3.py` — un client S3 **SigV4 écrit à la main** sur
  `urllib`. Aucune dépendance ajoutée : `boto3` tire une quinzaine de paquets
  pour six requêtes HTTP, et le moteur doit rester installable hors ligne.
  `S3Refuse` est construite pour ne porter **ni clé ni identifiant**.
* `StockageS3` — dépôt, relecture, lecture en flux. Un second dépôt des mêmes
  octets est **sans effet** ; un dépôt d'octets **différents** sous la même clé
  est **refusé** plutôt qu'écrasé.
* `EUROSTRUCT_STORAGE_BACKEND` — `local` ou `s3`, et rien d'autre. Une valeur
  inconnue est **refusée**. **Aucun repli de `s3` vers le disque**, dans aucune
  circonstance : une configuration incomplète donne un 503 qui nomme les
  **variables** manquantes, jamais leurs valeurs.
* Le téléchargement passe **en flux**, empreinte calculée au fil de l'eau, avec
  le premier bloc lu hors du générateur pour qu'un objet absent devienne un 503
  **avant** tout en-tête. `Content-Disposition` porte enfin les **deux** formes
  de la RFC 6266.

### Les huit étapes, contre un MinIO réel

`db/test/stockage_s3.sh` — ni faux client, ni `moto`, ni répertoire déguisé :

1. un **volume neuf**, créé par le harnais et constaté vide ;
2. le **compartiment**, créé par **notre propre signature** — pas par `mc` ;
3. le **dépôt** par les routes réelles, depuis un calcul strict ;
4. l'**API arrêtée** (processus détruit) et **MinIO redémarré** ;
5. le **téléchargement** dans un processus neuf, qui ne crée rien ;
6. l'**empreinte** des octets servis, **et** la recherche de ces octets
   *verbatim* dans le volume copié par `docker cp` — hors du produit, hors du
   test ;
7. le **refus inter-organisations** : le témoin **lit** l'objet dans le
   compartiment, et le bureau voisin est refusé. C'est ce qui distingue « on ne
   vous le donne pas » de « il n'y est pas » ;
8. la **destruction** du conteneur et du volume, tous deux créés ici.

À chaque étape, `EUROSTRUCT_STORAGE_DIR` pointe sur un répertoire jetable et
**vide** : un seul fichier qui y apparaîtrait révélerait un repli silencieux.

### La composition et la CI

`compose.yaml` gagne `objets` (MinIO, version **épinglée**, aucun port publié,
volume nommé) et `objets-init` (`mc mb` + `mc anonymous set none`). **Le
compartiment n'est pas créé par le produit** : un service qui créerait le sien
au démarrage masquerait une erreur de configuration.

Nouveau job CI `stockage`, séparé de `schema` parce qu'il exige Docker. Il lit
la version de l'image **dans `compose.yaml`**, pour que la preuve et la
composition ne dérivent pas.

### Ce qui n'est pas établi

Ni AWS S3, ni Supabase Storage, ni aucun fournisseur nommé n'a été joint depuis
ce dépôt. Un serveur qui parle le même protocole n'est pas une promesse de
compatibilité avec un service qu'on n'a pas essayé.

### La politique des orphelins

**Rien n'est jamais supprimé du magasin par le produit.** `ClientS3` n'a
**aucune** méthode de suppression, et ce n'est pas un oubli : il n'existe donc
aucun chemin de code capable de supprimer un objet encore référencé, parce
qu'il n'en existe aucun capable d'en supprimer un tout court. Détail complet
dans `docs/STOCKAGE.md`.

---

## 4. Bloc 3 — entrer dans l'application

### Le cul-de-sac, mesuré

Tout le produit suppose une ligne dans `organization_members`. Sans elle,
`GET /v1/projects` rendait une liste **vide** — pas une erreur, pas une
explication, un écran nu — et la création d'un projet refusait par « aucune
organisation ». **Ce refus est juste.** Ce qui manquait, c'est la suite :
aucune route, aucune primitive ne permettait d'en sortir. La seule façon
d'exister dans l'application était un `insert` fait à la main par le
propriétaire de la base.

`db/test/entree_application.sh` pose une base **sans aucune organisation** — le
seul décor du dépôt qui parte de là — et rendait **6 rouges sur 8**.

### Les huit primitives de `0024`

`organization_bootstrap`, `organization_invitation_create/accept/revoke/list`,
`organization_member_list/update`, `project_workspace_organisations`.
L'acteur vient du **jeton** dans chacune.

* **Amorçage atomique** : l'organisation et l'adhésion `owner` naissent
  ensemble ou pas du tout. Un verrou consultatif sur `(acteur, nom)` plus un
  index unique font qu'un **double-clic** rend le bureau déjà créé.
* **Invitations** : secret à forte entropie tiré par l'API, **empreinte seule**
  en base, usage unique, révocable, expirant, lié à organisation **et** rôle,
  destinataire **authentifié**, **aucune adresse stockée** (donc aucune
  énumération possible), lien copiable montré une fois.
* **Administration** : pas d'auto-élévation, un `admin` ne donne pas plus que
  son pouvoir, le dernier `owner` actif ne disparaît pas,
  `validating_engineer` n'est jamais auto-attribué.

### Deux défauts que la migration a elle-même révélés

1. **`insert … returning` applique les politiques de LECTURE** à la ligne
   rendue. À l'instant de la fondation, l'adhésion `owner` n'existe pas encore,
   donc le fondateur n'est pas membre, donc la relecture est refusée — et
   PostgreSQL rend « new row violates row-level security policy », un message
   qui **accuse l'écriture** alors que c'est la **relecture** qui a échoué.
   Mesure : prédicat d'insertion `true`, privilège `INSERT` accordé, politique
   permissive présente, **et refus**. L'identifiant est désormais tiré par la
   primitive.

2. **`postgres_atelier` lisait `organization_invitations` directement** pour
   relire une date d'expiration. Le login de service n'a **aucun** privilège de
   table — c'est le principe de 0018, et c'est la propriété exacte dont dépend
   la borne d'annuaire. **La base a refusé comme elle doit** ; le défaut était
   dans le module Python.

### L'annuaire, et la propriété dont il dépend

0018 a mesuré qu'une politique sur `organization_members` qui interroge
`organization_members` **boucle**. Sa politique de lecture est donc la plus
étroite possible : la ligne de l'appelant.

La politique ajoutée **n'interroge aucune table** : elle compare l'`org_id` de
la ligne à un réglage de **transaction** que seule une primitive pose, et
seulement **après** avoir exigé la capacité `administration`. Ce réglage n'est
**pas** une preuve de confiance — l'autorisation est prise par
`project_exiger_capacite`, qui lit la vraie ligne d'adhésion.

Il ne deviendrait une porte que si un rôle pouvait à la fois le poser **et**
lire la table. `eurostruct_authority_backend` n'a aucun privilège sur ces trois
tables : une **postcondition de la migration** et un **cas de test** le
constatent.

---

## 5. Le parcours navigateur, en quatorze points

`db/test/parcours_entree.sh` dresse Chromium → build de production Next.js →
uvicorn → PostgreSQL, sur un décor **sans aucune organisation**.

1. F se connecte, et son écran dit qu'il n'appartient à aucun bureau, avec
   **deux portes** — pas un sélecteur vide ;
2. il fonde son organisation depuis l'écran, et en devient `owner` ;
3. le même geste répété ne fonde pas un second bureau ;
4. il crée le projet **qui refusait avant** ;
5. il émet une invitation ; le secret apparaît à l'écran, **une** fois ;
6. la liste des invitations ne porte ni le secret ni son empreinte ;
7. après rechargement complet **et reconnexion**, le secret n'est plus nulle
   part — ni dans la page, ni dans `localStorage`, ni dans `sessionStorage` ;
8. I colle le lien et entre avec le rôle que l'invitation portait ;
9. le même lien, présenté par X, est refusé — et X n'entre nulle part ;
10. I, `engineer`, ne voit aucun panneau d'administration ; l'écran dit
    pourquoi, et la route forcée refuse de la même façon ;
11. le brouillon téléchargé porte l'empreinte que la base a enregistrée ;
12. F promeut I `validating_engineer`, et I le voit à sa reconnexion ;
13. F désactive I : la ligne reste à l'écran marquée révoquée, et I ne voit
    plus le bureau ;
14. F n'a ni sélecteur ni bouton sur sa propre ligne, et les deux refus de la
    base tiennent quand on force la route.

Le constat final est fait **hors du navigateur**, en SQL : 1 bureau,
1 propriétaire actif, 1 invitation consommée, 1 accès révoqué.

### Le défaut que seul ce parcours pouvait voir

`allow_methods` du middleware CORS énumérait `GET`, `POST`, `OPTIONS`. Les
routes `PATCH /members/{id}` et `DELETE /invitations/{id}` répondaient
parfaitement — 32 cas d'API verts — et **aucun navigateur n'y arrivait** :

```
Response to preflight request doesn't pass access control check
PATCH /v1/organizations/…/members/… — net::ERR_FAILED
```

Le prévol `OPTIONS` ne trouvait pas la méthode, et `fetch` échouait **avant**
d'émettre la requête réelle. Le panneau d'équipe affichait « l'API n'a pas
répondu » sur chaque changement de rôle. Une suite d'API ne peut pas voir cela :
elle parle à l'API **sans navigateur**, donc sans prévol.

---

## 6. Ce que ce parcours n'éprouve pas, et qui est écrit

* Le **magasin objet** : le parcours navigateur tourne sur le magasin local —
  même code de route, même vérification d'empreinte — parce qu'un MinIO réel
  exige un démon Docker qu'un harnais navigateur ne suppose pas. Le protocole
  S3 a son harnais en huit étapes.
* Le **calcul est exploratoire** : ouvrir le mode strict demande le quatre-yeux,
  éprouvé par `parcours_livrable.sh`. Le document produit porte donc
  « PROJET — NON SIGNABLE », et le parcours l'**exige** plutôt que de le taire.

---

## 7. Le gel — ce qui a réellement tourné, et son code de sortie

### La suite canonique, sur les octets commités

```
./eurostruct/run_tests.sh --require-db          → 0

 SURFACE              ETAT     DETAIL
 moteur               VERT     collectes 1014 | executes 1014 | reussis 1014 | echoues 0
 importeur            VERT     collectes   88 | executes   88 | reussis   88 | echoues 0
 API                  VERT     collectes  310 | executes  310 | reussis  135 | ignores 175
 securite des harnais VERT     30 barriere(s) mise(s) en echec, toutes ont refuse
 garanties SQL        VERT     13 groupe(s) de garanties verifie(s)
 coherence            VERT     seed NDP: ok, contrat TypeScript: ok, dependances: ok
 VERDICT: COMPLET — les 6 surfaces ont tourne, toutes vertes.
```

Les 175 cas « ignorés » de la surface API sont les modules à décor
PostgreSQL — `test_livrables`, `test_autorisations`, `test_entree`,
`test_stockage_s3` — que leurs harnais dédiés exécutent avec leur base
jetable. Ils ne sont pas sautés : ils sont exécutés **ailleurs**, et les
harnais ci-dessous le montrent.

### Les harnais, un par un

| Commande | Sortie | Ce qu'elle a mesuré |
|---|---|---|
| `db/test/entree_application.sh escent` | **0** | 32 cas, 1 bureau, 1 propriétaire actif, 1 invitation consommée |
| `db/test/livrable_validation.sh escloc` | **0** | 50 cas, 3 objets sur disque, 33 lignes de livrable |
| `db/test/stockage_s3.sh escs3` | **0** | 8 étapes contre MinIO réel, mêmes octets après redémarrage |
| `db/test/authority_sql_hardening.sh eschard` | **0** | 27 contrôles déclarés, 27 sûrs, 0 rouge |
| `db/test/parcours_entree.sh escnav` | **0** | 14 points depuis Chromium |
| `web && npm run typecheck` | **0** | — |
| `web && npm run build` | **0** | Next.js 16.3.3, compilé |
| `engine/scripts/export_contracts.py` | **0** | 64 types régénérés |

### L'intégration continue

Verte sur **`240a874`**, **`d20a345`**, **`e07d6c7`**, **`2bfdb36`** —
les quatre jobs du workflow `EUROSTRUCT` (Moteur, Schéma, **Magasin
d'objets**, Composition) et le workflow `eurostruct — tests`.

Le job `Magasin d'objets (MinIO réel, volume neuf, redémarrage)` exécute
l'étape « Dépôt, redémarrage, relecture (huit étapes) » : **succès**. Le job
`Composition de production` monte la pile avec MinIO dans `compose.yaml` :
**succès**.

---

## 8. Blocages externes restants

| Blocage | État |
|---|---|
| Validation par un ingénieur réel | **hors de ce dépôt**, à organiser par l'utilisateur |
| Annexes Nationales officielles | registre **0 / 29** ; aucune valeur inventée |
| Staging Supabase | `SUPABASE_UNVERIFIED` ; `supabase.com` est bloqué par le proxy de cet environnement |
| Licence ODA / RealDWG | non tranchée ; aucun « DWG natif » n'est promis |
| Build d'images Docker **dans cet environnement** | impossible : le conteneur de build ne fait pas confiance à l'autorité du proxy d'agent (`CERTIFICATE_VERIFY_FAILED` sur `pypi.org`). Sans rapport avec le code : la CI, elle, construit et démarre la composition avec succès. |
