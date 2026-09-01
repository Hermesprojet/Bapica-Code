# Rapport de lot — le document émis

Lot faisant suite au lot DXF / SVG / dossier de revue accepté au HEAD
`c9688b8`. Il ouvre la **28ᵉ primitive** `project_deliverable_issue_attestation`,
autorisée explicitement et pour elle seule : ce n'est **pas** une primitive
générique de création de livrables, et elle ne doit pas le devenir.

---

## 1. Ce que le lot ferme

L'attestation — nom du validateur, rôle, numéro d'inscription, déclaration,
réserves, date — vivait dans la table `validations`, c'est-à-dire **dans une
base que le destinataire du document ne voit pas**. Le PDF qu'on lui
transmettait n'en portait rien, et rien ne l'y distinguait d'un brouillon.

Modifier le PDF original pour y ajouter l'attestation était exclu : **son
empreinte est ce sur quoi l'attestation porte**. La retoucher aurait détruit le
lien qu'elle établit. D'où un **second** document, qui référence le premier par
son SHA-256 et ne le remplace pas.

Le champ de filiation est donc `derived_from_id`, **pas** `supersedes_id` :
un indice remplace, une dérivation constate. Dire « l'original est périmé »
aurait inversé le rapport — c'est l'original qui fait foi.

---

## 2. Commits

Neuf commits depuis `c9688b8`, du plus ancien au plus récent.

| SHA | Objet |
|---|---|
| `1f980f5` | L'attestation vivait dans la base ; le document qui circule n'en portait rien |
| `7124f58` | Deux PDF côte à côte, et rien ne disait lequel transmettre |
| `10fe077` | Le rapprochement demandait sa lecture seule ; il l'a maintenant par le droit |
| `f251f64` | Mes postconditions faisaient fumer le détecteur du voisin |
| `1cf7d5f` | Un rôle oublié dans une liste de démontage arrête tout ce qui vient après |
| `e5a87fc` | La leçon était écrite en commentaire ; un commentaire ne s'exécute pas |
| `246ab2c` | Un PDF anonyme ne se rattache à rien ; un PDF qui se certifie ment |
| `0b58caf` | Le parcours constatait que l'émission avait répondu, jamais qu'elle produisait |
| `fed8651` | L'assertion visait la bonne exigence, mais la mauvaise pièce |

---

## 3. La primitive, et ce qui la borde

`db/migrations/0025_document_emis.sql`. `security definer`, `search_path`
épinglé, propriétaire vérifié par postcondition.

L'ordre interne **est** la garantie :

1. `select … for update` sur la source — le verrou avant tout le reste ;
2. `project_exiger_capacite(org_id, 'validation')` ;
3. **idempotence** : `derived_from_id = p_source_id` existant, même SHA →
   on rend l'identifiant existant ; SHA différent → `unique_violation` ;
4. genre `calculation_note_pdf`, état `validated` ;
5. validation existante, nominative, et portant sur `deliverable_sha256 =
   d.sha256` — l'attestation doit désigner **ces** octets ;
6. description complète des octets, forme du SHA, SHA distinct de l'original ;
7. `project_deliverable_finalize(...)` — l'original passe à `final` ;
8. `insert … state='final', is_final=true, validation_id=d.validation_id,
   derived_from_id=d.id` ;
9. `get diagnostics … row_count`.

Un index unique `deliverables_un_seul_derive_par_source` sur
`(derived_from_id) where derived_from_id is not null` rend le double document
impossible **au niveau du schéma**, pas seulement au niveau de la fonction.

**Ordre magasin puis base, et il est délibéré.** Les octets sont écrits, relus,
et leur taille + SHA-256 vérifiés **avant** que la transaction ne commence. Si
le stockage réussit et que la transaction échoue, l'objet devient un candidat
orphelin — détectable par le scanner. La base, elle, ne référence **jamais** un
objet qui n'a pas été écrit et relu avec succès.

**Aucune information d'identité ne vient du corps HTTP.** Le nom du validateur
sort de son adhésion. La route déclare un corps `EmissionDemande` vide en
`extra="forbid"` : un corps hostile est refusé en 422, il n'est pas ignoré.

---

## 4. Rouge, puis vert

Les tests ont été écrits **avant** la primitive et ont échoué avant elle.

| Surface | Rouge | Vert |
|---|---|---|
| `livrable_validation.sh` | **16 failed, 91 passed** | **108 passed** |
| `reconciliation_role.sh` | — | 9 contrôles, dont 4 négatifs |
| `demontage_canonique.sh` | falsifié → ROUGE nommant fichier et rôle | 32 harnais × 8 rôles |
| `parcours_livrable.sh` | ROUGE : « l'émission n'a produit aucun document attesté » | CODE=0 |
| `mutation_signal_selftest.sh` | — | 129 contrôles |

Les quatorze refus exigés sont couverts : propriétaire, administrateur,
ingénieur rédacteur, lecteur ; validateur désactivé ; validateur d'une autre
organisation ; source en `draft` ; source en `review` ; calcul exploratoire ;
autre type de livrable ; validation ne correspondant pas au SHA ; octets mal
décrits ; impossibilité de dicter nom et identité ; impossibilité de créer un
livrable arbitraire ; deux appels simultanés (`threading.Barrier`) ;
idempotence après réponse perdue ; absence de double document ; état final
impossible si le PDF échoue.

---

## 5. Parcours à deux acteurs réellement distincts

`db/test/parcours_livrable.sh` — Chromium réel, deux comptes authentifiés
séparément, **exit 0**.

- A (rédacteur) ouvre le mode strict par le quatre-yeux avec V, enregistre un
  calcul strict, produit un brouillon HTML **puis** un brouillon PDF ;
- les octets téléchargés portent l'empreinte enregistrée, et la conservent
  après un rechargement complet (F5 : la session ne survit pas, donc ce qui
  revient ne peut venir que de la base) ;
- l'écran de A n'offre **aucun** panneau d'attestation, et dit pourquoi ;
- V (validateur) atteste le PDF sous le nom et le numéro d'inscription de
  **son** adhésion ;
- V émet. L'émission produit un **second PDF**, que l'écran nomme
  « PDF émis avec attestation », qui dérive de l'original sans le remplacer,
  se télécharge, **cite le SHA-256 de l'original dans ses octets**, dit qu'il
  n'est pas une signature qualifiée — et **l'original reste byte-identique** ;
- le livrable émis ne se modifie plus, ni par bouton ni par route ;
- une révision d'indice 2 le remplace, créée par A (réviser est un geste de
  rédaction) ;
- B, de l'autre organisation, ne voit pas le projet et obtient un refus qui ne
  laisse rien filtrer.

---

## 6. Les deux PDF

Octets réels extraits d'une exécution du harnais, 24 empreintes vérifiées par
`sha256sum -c`.

| Pièce | SHA-256 | Taille |
|---|---|---|
| PDF original validé | `81163233b0e66c4ae9a47def632dce6c6ebec46184bec551c8b43d3ff10b8fb6` | 34 286 o |
| PDF émis avec attestation | `1c3c01f2f9cfca32918942092dc4b432f750660c9881413b95bc9122366ea082` | 6 989 o |
| Plan DXF (même projet) | `7e4604e2fda97f44ded7fcf1424718cdd867e6d9a1f8b7b8d8c37dab97bce02a` | 64 025 o |

Le PDF émis **cite le SHA-256 de l'original dans son corps**, vérifié par
relecture `pypdf` — un lecteur tiers, pas notre propre écrivain : se relire
soi-même ne prouve que la cohérence avec soi-même.

---

## 7. Identité du document émis

`SIGNATURE_OUTIL` nomme le logiciel, en **pied** et non en tête — l'outil n'est
pas le sujet du document — et décline explicitement toute part dans le contenu
technique. Deux bouts qui se contredisent devaient être tenus ensemble : un PDF
anonyme ne se rattache à rien, un PDF qui se certifie ment. Le seul acteur qui
engage sa responsabilité est l'ingénieur nommé.

`ZONE_LOGO` reste **vide par défaut**, et délibérément : un logo fictif intégré
comme marque officielle ferait passer un document de test pour la pièce d'un
bureau réel.

Le test interdit le vocabulaire d'organisme agréé — agrément, accréditation,
homologation. Il **n'interdit pas** « certifi » : « ce document ne certifie
rien » est exactement ce qu'on veut pouvoir écrire, et interdire la sous-chaîne
interdirait la dénégation en même temps que la prétention.

---

## 8. Rôle de réconciliation

`db/migrations/0026_role_reconciliation.sql`. `eurostruct_reconciliation` est
**créé par le plan de contrôle**, jamais par une migration : 0026 **exige**
qu'il préexiste et refuse sinon. Il est `NOLOGIN` sans attribut ; le compte
`LOGIN` sera fourni plus tard par l'infrastructure.

Il reçoit `usage` sur le schéma et `select` sur **sept colonnes nommées** de
`deliverables` : `id, org_id, project_id, storage_backend, storage_path,
sha256, size_bytes`. Rien d'autre.

Contrôles négatifs : `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` et l'appel des
primitives d'autorité sont refusés.

**Toutes les postconditions portent sur les octrois DIRECTS**, via
`aclexplode(attacl)` / `aclexplode(relacl)` avec `grantee <> 0` — jamais
`has_*_privilege`, qui inclut les droits hérités de PUBLIC. La première
rédaction employait le privilège effectif et **déplaçait le point de mise à
mort** de la mutation W1 : `killed_runtime` devenait
`killed_install_assertion`. Une postcondition qui change l'endroit où une
mutation meurt cesse de dire ce qu'elle prétend dire.

**Informations transversales accessibles** : ce rôle voit les chemins et
empreintes de **toutes** les organisations. C'est nécessaire au rapprochement —
un scanner qui ne verrait qu'un locataire ne pourrait pas dire si un objet est
orphelin — et c'est **le prix explicite** de cette fonction. Il ne voit ni nom
de fichier, ni contenu, ni identité de validateur, ni validation.

**La suppression réelle des orphelins n'est pas implémentée.** Le scanner et le
`dry-run` suffisent pour la release candidate. Aucun effacement de production.

---

## 9. Campagne canonique

Sur `fed8651`, arbre propre au lancement.

```
 SURFACE              ETAT     DETAIL
 moteur               VERT     collectes 1023 | executes 1023 | reussis 1023 | echoues 0
 importeur            VERT     collectes   88 | executes   88 | reussis   88 | echoues 0
 API                  VERT     collectes  419 | executes  419 | reussis  181 | ignores 238 | echoues 0
 securite des harnais VERT     30 barriere(s) mise(s) en echec, toutes ont refuse
 garanties SQL        VERT     13 groupe(s) de garanties verifie(s)
 coherence            VERT     seed NDP: ok, contrat TypeScript: ok, dependances: ok
 VERDICT: COMPLET — les 6 surfaces ont tourne, toutes vertes.
```

Les 238 tests d'API ignorés le sont faute de décor PostgreSQL dans cette
surface ; ils tournent dans « garanties SQL », qui les invoque avec une base.

---

## 10. Défauts trouvés dans ce lot, et à qui ils sont

Cinq des sept sont de mon fait. Ils sont nommés comme tels.

1. **Le dossier de revue n'était plus déterministe** — mon `now()` du lot
   précédent. Remplacé par `artifacts_as_of = max(generated_at)`.
2. **Course sur le fichier temporaire du magasin local** — le nom ne portait
   que le PID ; deux dépôts concurrents dans le même processus entraient en
   collision et rendaient 503 alors que les octets étaient en place.
   `uuid4().hex` ajouté.
3. **Une route sans corps déclaré ignore ce qu'on lui envoie** — un corps
   hostile passait en 200. `EmissionDemande` vide en `extra="forbid"` → 422.
4. **Mes postconditions 0026 employaient le privilège effectif** (PUBLIC
   compris) et déplaçaient le point de mise à mort de W1.
5. **`nonsuperuser_install.sh` créait `eurostruct_reconciliation` sans le
   rendre** — sa phase 0 pose le sceau, sa liste de démontage l'ignorait. Le
   harnais **passait** (exit 0) et tout ce qui venait après refusait de
   démarrer. Deux surfaces rouges, vertes en isolé.
6. **Le parcours navigateur constatait que l'émission avait répondu, jamais
   qu'elle produisait** — puis, écrite, la nouvelle section visait le brouillon
   HTML au lieu du PDF. L'exigence était bonne, la pièce ne l'était pas.
7. **Une erreur d'attente, pas un défaut produit** : je m'attendais à ce que
   l'émission d'un plan DXF soit refusée. Refuser aurait été une régression —
   la route branche sur le genre, et c'est correct.

### Ce que le cinquième a coûté, et pourquoi il a récidivé

Le 26/08, `eurostruct_authority_backend` avait joué **exactement la même
scène**. La leçon avait été écrite — dans le fichier même, quatre lignes
au-dessus de la ligne fautive :

> « Un rôle oublié dans une liste de démontage n'est pas un détail : il arrête
> tout ce qui vient après. »

Elle n'a pas empêché la récidive. **Un commentaire ne s'exécute pas.**

`db/test/demontage_canonique.sh` rend donc l'invariant structurel : la liste
attendue se **dérive** des `create role` du sceau, et chaque harnais appelant
`exiger_roles_absents` doit nommer chacun de ces rôles. Il ne touche ni base ni
cluster — il lit des fichiers — et passe en **tête** de `run.sh` : la cause se
nomme en une seconde, avant la première base, au lieu de se manifester une
heure plus tard sur une autre surface.

**Sa première rédaction était fausse, et la falsification l'a dit.** Elle
cherchait le nom dans le fichier entier ; le commentaire expliquant la
correction nommait le rôle dix lignes plus haut et **satisfaisait le
contrôle**. Un contrôle que sa propre prose satisfait ne contrôle rien. Les
commentaires sont retirés avant la recherche.

Deux garde-fous protègent le garde-fou : zéro `create role` lu dans le sceau,
ou moins de vingt appelants trouvés, sont des **échecs** — un contrôle statique
dont le motif casse redevient vert en ne vérifiant plus rien.

---

## 11. Ce que ce lot ne prouve pas

- **La compatibilité Supabase reste `SUPABASE_UNVERIFIED`.** Elle ne sera
  établie que par une exécution sur une instance de staging réelle.
- **L'attestation du PDF ne couvre pas le plan DXF.** Le dossier de revue les
  énumère séparément, et le document émis le dit dans sa section « Portée et
  limites ».
- **Ce n'est pas une signature électronique qualifiée** au sens eIDAS. Le
  document le porte en tête **et** en pied.
- **Aucune attestation produite par les harnais n'est réelle.** Les comptes
  sont fictifs et les bases sont détruites.
- Le registre national reste à **0/29**. Aucune valeur n'est inventée ; ce qui
  manque reste `pending_verification`.

---

*Toute note produite par EUROSTRUCT doit être validée par un ingénieur
habilité avant usage. Ce rapport décrit un état de développement, non une
pièce de dossier.*
