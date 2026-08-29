# EUROSTRUCT — jalon 6.3c — rapport du lot L6

**Statut du jalon : inchangé.** `6.3c` n'est ni `CLOSED`, ni `DEPLOYABLE`, ni
`PRODUCTION_READY`. `PROVIDER_IMPLEMENTED_NOT_INTEGRATED`,
`BLOCKED_BY_REAL_AUTH`, `SUPABASE_UNVERIFIED` et `TARGET_BRANCH_UNRESOLVED`
restent vrais. Aucune route, aucun authentificateur produit, aucun secret,
aucune instance Supabase n'ont été créés pendant ce lot.

Ce rapport ne réécrit ni `RAPPORT_L4.md` ni `RAPPORT_L5.md`. Les campagnes
historiques qu'ils décrivent restent ce qu'elles sont.

---

## 1. Ce qu'on savait en entrant, et ce qui était faux

### 1.1 État Git initial

`HEAD` = `892f3fa` (« docs(6.3c): bilan de nettoyage et chantier non
entrepris »), branche `claude/wip-6.3c-racine-de-confiance`, arbre propre,
local et distant au même point.

### 1.2 État CI initial : rouge depuis vingt-deux exécutions

Deux workflows tournent sur cette branche. `EUROSTRUCT` était vert.
`eurostruct — tests` était **rouge**, et pas depuis la veille :

| fait | mesure |
|---|---|
| dernier vert | `7afa11ba`, 2026-08-28 T00:24:55 Z, run [33129640314](https://github.com/Hermesprojet/Bapica-Code/actions/runs/33129640314) |
| premier rouge | `97a4a7df`, 2026-08-28 T08:00:40 Z, run [33153628862](https://github.com/Hermesprojet/Bapica-Code/actions/runs/33153628862) |
| rouge à l'entrée du lot | `892f3fa`, run [33259546903](https://github.com/Hermesprojet/Bapica-Code/actions/runs/33259546903) |
| exécutions rouges consécutives | **22** |

Vingt-deux exécutions rouges, et personne ne l'avait vu, parce que **la suite
est verte en local** : `psycopg2` est installé sur le poste de travail.

---

## 2. Défaut 1 — la CI n'installait pas le pilote PostgreSQL

### 2.1 Cause exacte

`.github/workflows/eurostruct.yml` installe explicitement `psycopg2-binary`.
`.github/workflows/eurostruct-tests.yml` **ne l'installait pas**. Or
`db/test/provider_contract.sh` rend `4` — *NON EXECUTE* — quand le pilote
manque, et la suite canonique compte une surface non exécutée comme un échec.
C'est le comportement voulu : *une surface qu'on n'a pas pu exercer n'est pas
une surface qui a tenu*. Le rouge était juste ; c'est la CI qui était
incomplète.

Cause du rouge, telle que la suite la nommait : `1 surface NON EXECUTEE —
contrat du provider`.

### 2.2 Correction, à la source

Une étape nommée, placée après `dependances`, dans le venv du job :

```yaml
- name: Pilote PostgreSQL (contrat du provider)
  run: |
    source "$GITHUB_WORKSPACE/.venv-eurostruct/bin/activate"
    pip install psycopg2-binary
    python -c "import psycopg2; print('pilote present:', psycopg2.__version__)"
```

Le pilote reste une dépendance **de test et de CI**. Il n'entre pas dans les
dépendances du moteur : le provider s'appuie délibérément sur un `Protocol`,
et l'y ajouter transformerait une frontière en couplage.

Le workflow n'a pas été relancé à l'identique : la correction est dans le
fichier, et c'est le fichier corrigé qui a produit le vert.

### 2.3 Le diagnostic censé expliquer ce rouge était lui-même mutilé

Sur le seul chemin où on le lit — celui où le pilote manque —
`provider_contract.sh` écrivait, entre guillemets **doubles** :

```bash
echo "       `python3 -c 'import psycopg2'` echoue. ..."
```

Bash y exécute la substitution. La commande échouait, sa trace partait vers
stderr au milieu du diagnostic, et le message se réduisait à
« `echoue. Les proprietes SQL du` ». Guillemets simples : rien ne s'y exécute.

---

## 3. Défaut 2 — l'auto-test du canal salissait son `TMPDIR`

### 3.1 Reproduction, chiffrée

`canal_selftest.py` lancé avec un `TMPDIR` neuf (`/tmp/reproL6.7SGesC`) :

```
108 fichiers .jsonl laisses
 27 par le chemin normal
 81 par les trois sous-processus des preuves negatives (27 chacun)
```

Cause : quatre `NamedTemporaryFile(delete=False)` sans reprise. Le `False`
était **nécessaire** — le fichier doit survivre à sa fermeture pour être relu —
mais rien ne le reprenait ensuite.

### 3.2 Correction

Un espace possédé (`tempfile.TemporaryDirectory`), les quatre sites créant
leurs fichiers **dedans**, et une libération dans un `finally`.

### 3.3 Contrôle permanent, et ses deux falsifications ratées

`db/test/canal_proprete.py` — six cas : chemin normal vert et `TMPDIR` vide ;
décor réellement parcouru (le selftest publie `CANAL_SELFTEST_CAS=`) ; `TMPDIR`
vide **aussi après une erreur contrôlée** ; et une preuve négative.

Deux versions de ce contrôle ont été jetées avant d'en garder une :

* la première mutation du cas 4 visait la vérification du `statut`, qu'aucun
  cas du selftest n'exerce : le muté restait **vert**, et le contrôle concluait
  « le muté n'échoue pas » — vrai, et sans rapport ;
* la première preuve négative neutralisait `liberer_espace()`. Aucun résidu ne
  réapparaissait : `TemporaryDirectory` porte son **propre** finaliseur.
  L'appel explicite rend le nettoyage déterministe, il n'est pas ce qui évite
  la fuite. Ce qui l'évite, c'est que les fichiers naissent **dans** le
  répertoire possédé — c'est donc cela qu'on falsifie.

Enregistré au registre sous `NT1`, point `19.10` du harnais
`harness_safety_selftest.sh`, après un contrôle global de doublons et arbitrage
du pré-vol (le premier ancrage a été refusé comme AMBIGU : trois occurrences).

### 3.4 Preuve de disparition, mesurée dans la nature

La disparition n'est pas affirmée, elle est datée. Deux populations de fichiers
coexistent sous `/tmp` :

| population | forme | nombre | plus récent |
|---|---|---|---|
| fuite `canal_selftest` | `tmp*.jsonl` | 509 | **2026-08-29 12:29:23** |
| canaux du lanceur | `canal_<uuid>.jsonl` | 163 | 2026-08-29 21:06:44 |

Le correctif est daté du **16:15:33**. Depuis, `canal_selftest.py` a tourné des
dizaines de fois — par `canal_proprete.py`, par le contrôle 19.10, par le
contrôle de mutation `NT1`, et par la campagne complète — et **pas un seul
fichier de la première forme n'est apparu**. Le plus récent lui est antérieur
de presque quatre heures.

---

## 4. La dette principale — six harnais migrés vers le canal natif

Dix-huit harnais dépendaient encore d'un traducteur de prose. Il en reste
**douze**.

| ordre | harnais | contrôles rejoués | résultat |
|---|---|---|---|
| 1 | `finalisation_contract.sh` | 10 | 8 tués + 2 redondances prouvées |
| 2 | `provider_contract.sh` | 7 | 5 tués + 2 redondances prouvées |
| 3 | `migration_postconditions.sh` | 7 | 7 tués en runtime |
| 4 | `authority_closure.sh` | 17 | 12 runtime + 3 installation + 2 redondances |
| 5 | `authority_role_frontier.sh` | 4 | 4 tués en runtime |
| 6 | `authority_root_of_trust.sh` | — | aucun contrôle ne le vise (§ 4.6) |

Dans tous les cas : la sortie humaine est **inchangée** et n'a plus autorité
sur le verdict ; le point est un **argument déclaré**, jamais un jeton relu
dans la prose ; `controle_id` reste distinct de `point_id` ; un canal muet vaut
`NOT_RUN` et ne déclenche plus le traducteur, qui refuse désormais nommément
ces six harnais.

**Un rejeu filtré ne clôt aucune campagne.** Chacun de ces rejeux dit
seulement que les contrôles concernés sont attribués nativement.

Harnais encore non migrés (12) : `authority_bootstrap_contract.sh`,
`authority_delegation_lineage.sh`, `authority_four_eyes.sh`,
`authority_sql_hardening.sh`, `cross_cluster_restore.sh`,
`deploy_recovery.sh`, `gate_protocol_selftest.sh`, `migration_roundtrip.sh`,
`official_deployment.sh`, `seal_contract.sh`, `two_phase_deployment.sh`,
`mutation_matrix.py`.

Dans la campagne finale, **50 attributions passent encore par le traducteur**
et **93 sont natives**. La dette est réduite, pas éteinte.

### 4.1 Un harnais qui se relance lui-même double son verdict

Premier rejeu filtré après la migration 2 : les sept contrôles de la factory
en `INFRA_FAILURE`, `double_terminal 7`. Ni le protocole ni le lecteur
n'étaient en cause.

`provider_contract.py` lance `sans_pilote.py`, qui **relance**
`provider_contract.py` privé de pilote — c'est tout l'objet de `D10`. L'enfant
héritait de `ESC_CANAL` et des trois variables de contexte, et écrivait son
propre verdict terminal pour le même contrôle : « SUR puis SUR », « ROUGE puis
SUR ».

La règle est posée une fois, dans `canal_lecture.env_decor()`, et elle nomme
une distinction qui vaut pour toutes les migrations à venir :

* un sous-processus de **décor** est exercé pour qu'on observe son code de
  retour ; le verdict est rendu par le parent, et il ne doit pas écrire ;
* un **délégataire** reçoit la main et écrit, et c'est le parent qui se tait.

Rendre l'enfant muet n'efface aucune preuve : le parent émet, et un canal muet
vaut `NOT_RUN` — jamais vert par défaut.

### 4.2 Une précédence entre verdicts qui partagent un point

`migration_postconditions.sh` est le premier harnais dont les verdicts ne sont
pas en bijection avec les points : quatre verdicts d'une même migration portent
`Y1`. Deux règles en découlent, dans `lib_harnais.sh` :

* **un seul verdict terminal par point, et le premier rouge gagne** — c'est ce
  que faisait déjà le traducteur, qui rendait un événement sur la première
  ligne portant le point et s'arrêtait ;
* **les trous sont différés**. Un chemin non atteint vaut `NOT_RUN` et jamais
  `SURVIVED`. Mais l'émettre aussitôt le graverait avant qu'un rouge plus
  tardif sur le même point ait pu se produire, et le premier verdict tient : le
  contrôle serait ressorti « non mesuré » alors qu'il venait d'être tué.
  `esc_point_troue` retient donc, et `esc_conclure` ne rend le trou que si rien
  n'a rougi. Le ROUGE, lui, part immédiatement : un harnais tué en cours de
  route doit laisser son rouge derrière lui.

### 4.3 Un `echoue` qui était en réalité un rouge

`authority_closure.sh`, point `B2`. Le commentaire du harnais tranche
lui-même : « ce qui serait rouge, c'est l'ABSENCE de refus ». La ligne imprimée
reste un `ECHEC` — la changer n'apprendrait rien — mais le canal émet un ROUGE.
Même famille que les cinq `echoue` porteurs de label de
`finalisation_contract.sh`, que le traducteur lisait comme des rouges et qui
auraient fait **survivre** leur contrôle une fois migrés sans cette
distinction.

### 4.4 Le point du contrôle `D2` était faux dans le registre

`D` éprouve l'idempotence **avant** le verrou, `D2` la relecture **après**.
Deux mutations, deux scénarios, et le harnais les distingue depuis toujours —
« ROUGE: D. » d'un côté, « ROUGE: D2. » de l'autre. Le registre attendait « D »
pour les deux.

Personne ne l'avait vu parce que le traducteur, ne trouvant pas « D » sur la
ligne « ROUGE: D2. » (vérifié : aucune des trois formes ne le rend), passait à
sa **seconde** passe — la détection générique d'un refus d'installation — et
rendait `KILLED_INSTALL_ASSERTION` avec « invariant non nommé ». Le contrôle
était compté comme tué par une heuristique **anonyme**, pour un point qui ne
correspondait à rien.

Mesure avant/après sur le même SHA : harnais non migré, `D2` rendait
`killed_install_assertion 1` ; migré, `survived 1` avec le diagnostic qui nomme
l'écart. Point corrigé en `D2` : `killed_runtime 1`, **deux fois de suite** —
le scénario est une course, on a donc regardé sa stabilité plutôt que de
conclure sur une exécution.

### 4.5 Un garde permanent : un harnais migré DÉCLARE ses points

Deux fautes du même jour ont la même forme — **un point attendu que personne
n'émet** :

* la conversion d'`authority_closure.sh` exigeait un chiffre après la lettre
  (`A1`, `H7`) et manquait `D`, `E`, `F`, `G`. Trois sont des points du
  registre : les contrôles D, E et G seraient devenus `NOT_RUN` après avoir été
  tués pendant des semaines ;
* le contrôle `D2` ci-dessus.

La campagne complète finit par les voir — `not_run == 0` échoue — mais
quatre-vingt-dix minutes plus tard, et seulement si on la lance. Le pré-vol le
dit maintenant en trois secondes.

**Pourquoi une déclaration et non un scanner.** Le scanner a été essayé : une
expression régulière sur les sites d'appel. Elle a raté `2b` dans
`finalisation_contract.sh`, où l'appel est en milieu de ligne — `|| {
rouge_point 2b "..."`. Un scanner qui rate un site rend un faux manquant, donc
un refus injustifié ; le rendre laxiste pour l'éviter le rend aveugle.

**Et la déclaration est tenue honnête par l'exécution.** Émettre un point
absent de la liste imprime une faute — mais **l'événement part quand même**. Le
taire transformerait une erreur de tenue de liste en absence de preuve : le
contrôle passerait de « tué » à « non mesuré » à cause d'une liste mal tenue.

Le garde est inerte tant que rien n'est déclaré : les douze harnais non migrés
passent par le traducteur et ne déclarent rien.

Ce garde a immédiatement arrêté une faute de plus : la première rédaction de la
déclaration d'`authority_role_frontier.sh` disait
`esc_points_declares "${POINT_DE[@]}"` — correct à l'exécution, **illisible
pour le pré-vol**, qui lit le fichier sans l'exécuter. Il n'y voyait que le
texte de l'expansion et a refusé les quatre contrôles `PC`. À juste titre.

### 4.6 Ce que la sixième migration ne prouve pas

Aucun contrôle du registre ne vise `authority_root_of_trust.sh` : `CAS_*` ne le
nomme nulle part. Il n'y a donc aucun rejeu filtré à produire, et aucune
mutation qui rougirait si l'émission était neutralisée. **C'est une dette
retirée, pas une garantie nouvellement éprouvée.**

Faute de contrôle de mutation, la preuve a été faite à la main et elle est
directe : attaque 7 forcée au rouge, le canal porte un ROUGE **terminal** sur
le point « 7 » et le harnais rend 1 ; sur le chemin vert, un seul événement, un
SUR terminal, aucune faute de déclaration. La mutation forcée a été retirée et
l'arbre vérifié identique ensuite.

---

## 5. Falsifications conduites

| falsification | attendu | mesuré |
|---|---|---|
| `POINT_DE` de `migration_postconditions.sh`, `Y1` → `Y99` | `MC1` cesse d'attribuer | `survived 1` |
| déclaration d'`authority_closure.sh` amputée de `D`, `E`, `G` | pré-vol refuse | 3 STALE, les trois contrôles nommés |
| point d'un contrôle remplacé par un inexistant | pré-vol refuse | 1 STALE, contrôle et point nommés |
| `_esc_point_connu` neutralisé (N6) | auto-test rouge | rouge |
| `env_decor` ne retire plus rien (N5) | auto-test rouge | rouge |
| émission d'un point déclaré neutralisée (N4) | auto-test rouge | rouge |
| `dir=espace()` retiré de `canal_selftest` | résidus réapparaissent | réapparaissent |
| attaque 7 d'`authority_root_of_trust` forcée | ROUGE terminal sur « 7 » | ROUGE terminal, rc=1 |

L'auto-test du canal passe de **43 à 57 cas** (six preuves négatives N1–N6).
`canal_proprete.py` exige ce compte : un selftest amputé rendrait moins, et le
contrôle doit le voir.

---

## 6. Deux diagnostics qui mentaient sur eux-mêmes

**Un refus tronqué juste avant sa cause.** Le compte rendu d'un harnais refusé
faisait `sortie.splitlines()[:3]` puis `if ligne.strip()` : les lignes **vides**
consommaient le budget sans rien afficher.

```
1  NON EXECUTE: ... n'a pas pu interroger le verrou de harnais.
2  (vide — comptee, non affichee)
3  La session du verrou n'a rendu ni « true » ni « false », mais:
4  psql: error: ... FATAL: role "root" does not exist   <-- LA CAUSE
```

Le diagnostic s'arrêtait sur « mais: ». Il a fallu **deux rejeux complets** pour
retrouver ce que la ligne 4 disait déjà. On filtre d'abord, on tronque ensuite,
six lignes utiles et non trois, et la troncature est **dite**.

**Un diagnostic de survivant qui se contredisait.** En falsifiant `POINT_DE`, le
message imprimait « le harnais a rougi sur ['Y1'], on attendait « Y1 » » — deux
fois la même valeur, comme si elles différaient. Il venait pourtant de détecter
exactement la bonne chose : la sortie humaine annonce un rouge sur le point
attendu et le canal n'en porte pas, ce qui, pour un harnais migré, est la
signature d'une émission mal câblée. C'est ce qu'il dit désormais. Le verdict ne
bouge pas : `SURVIVED` reste `SURVIVED`.

---

## 7. Le SHA gelé et la validation ordonnée

### 7.1 Gel

| | |
|---|---|
| SHA fonctionnel gelé | **`d6b54a2ab91dd80a05c444688ca9394c57f2c80e`** |
| arbre git | `51de48500cc43d0ae42143a8bd7d6d721ea1147c` |
| distant | identique au local au moment du gel |
| arbre de travail | propre |
| pré-vol global | 110 contrôles retenus, `stale 0 · ambiguous 0 · missing_combined_control 0 · duplicate_id 0` |

Dix commits fonctionnels, tous poussés sans force, sans réécriture, sans PR :

```
d6b54a2 authority_root_of_trust.sh emet nativement — 13 -> 12 non migres
8c5cd96 authority_role_frontier.sh emet nativement — 14 -> 13 non migres
c23082c un harnais migre DECLARE les points qu'il sait emettre
2963b1e authority_closure.sh emet nativement — 15 -> 14 non migres
556c45d un diagnostic de survivant qui se contredisait lui-meme
1cd2ead migration_postconditions.sh emet nativement — 16 -> 15 non migres
9d9fb35 le diagnostic d'un refus s'arretait juste avant sa cause
59382d9 provider_contract.sh emet nativement — 17 -> 16 non migres
77b787f finalisation_contract.sh emet nativement — 18 -> 17 non migres
f0249fa la CI etait rouge faute de pilote, et le canal salissait le TMPDIR
```

### 7.2 Empreintes avant / après

Empreinte SHA-256 de la liste des empreintes des 171 fichiers `.sh` / `.py` /
`.sql` :

| moment | empreinte globale |
|---|---|
| avant le gel (arbre de travail) | `6c1e1c38ab73806b010feb6b4024379cabb71cc7427ebc87c443ed9458b13a1c` |
| worktree détaché, avant validation | `6c1e1c38…13a1c` |
| après `run.sh` | `6c1e1c38…13a1c` |
| après la campagne complète | `6c1e1c38…13a1c` |

**Identiques.** Ni la validation ni la campagne n'ont modifié l'arbre qu'elles
mesuraient.

### 7.3 Validation ordonnée

`db/test/run.sh` lancé depuis un **worktree détaché** sur `d6b54a2`, contre un
PostgreSQL 16.13 réel et jetable, avec le consentement explicite qu'exigent les
gardes (`EUROSTRUCT_CLUSTER_JETABLE`).

* **31 surfaces**, 505 assertions vertes, verdict : *« Toutes les surfaces de
  db/test sont vertes. »*
* **Aucune surface non exécutée.** Le contrat du provider a bel et bien tourné :
  34 propriétés sûres, 0 échec, **y compris les propriétés SQL** `C1`–`C11` qui
  exigent un vrai serveur. C'est exactement la surface qui rendait la CI rouge.
* Résidus après `run.sh` : 0 base, 0 rôle, 0 verrou.

---

## 8. La campagne complète

Lancée depuis le **même worktree détaché**, sur le **même SHA**, arbre propre —
donc aucun fichier recopié par-dessus l'état gelé.

```
RUN  run-b5b5451e92744b48
SHA  d6b54a2ab91dd80a05c444688ca9394c57f2c80e

MUTATIONS: defined 110 | attempted 110 | killed_runtime 93
           | killed_install_assertion 8 | redundant_proven 9
           survived 0 | stale 0 | infra_failure 0 | not_run 0 | code 0
CANAL:     unknown_event 0 | invalid_jsonl 0 | cross_run_event 0
           | double_terminal 0
```

| critère exigé | mesuré |
|---|---|
| `defined == attempted` | 110 == 110 |
| somme exacte des statuts | 93 + 8 + 9 + 0 = 110 |
| `survived == 0` | 0 |
| `stale == 0` | 0 |
| `infra_failure == 0` | 0 |
| `not_run == 0` | 0 |
| `unknown_event == 0` | 0 |
| `invalid_jsonl == 0` | 0 |
| `cross_run_event == 0` | 0 |
| `double_terminal == 0` | 0 |

**Les dix critères sont tenus.** La comptabilité se referme : les 110 contrôles
portent quelque chose, aucun survivant, aucun périmé, aucune erreur
d'infrastructure, aucun contrôle non lancé.

Ce résultat vaut pour `d6b54a2` et pour lui seul.

---

## 9. Les deux workflows GitHub

Sur le SHA gelé `d6b54a2` :

| workflow | conclusion | run |
|---|---|---|
| `EUROSTRUCT` | **success** | <https://github.com/Hermesprojet/Bapica-Code/actions/runs/33267366155> |
| `eurostruct — tests` | **success** | <https://github.com/Hermesprojet/Bapica-Code/actions/runs/33267366137> |

L'étape `Pilote PostgreSQL (contrat du provider)` est présente et verte ;
l'étape `suite canonique`, celle qui échouait sur la surface non exécutée, est
verte. Vingt-deux exécutions rouges consécutives sont closes.

Les workflows ont tourné en parallèle de la campagne : ils ne changent pas le
SHA.

---

## 10. État résiduel, mesuré

| objet | état |
|---|---|
| processus de harnais ou de campagne | aucun vivant (vérifié par **PID exact**, jamais par motif) |
| bases non canoniques | 0 |
| rôles non systèmes | 0 |
| appartenances résiduelles | 0 — `pg_auth_members` compte 3 lignes, et ce sont les trois de la hiérarchie `pg_monitor` livrée par PostgreSQL, présentes sur tout cluster neuf. Le chiffre brut est donné pour qu'un lecteur qui interroge la table ne croie pas le rapport en défaut |
| verrous consultatifs | 0 |
| sessions clientes | 0 |
| arbre git | propre, local == distant == `d6b54a2` |
| worktrees | `/tmp/esc-fix` + le worktree détaché du gel, retiré en fin de lot |

**Fichiers temporaires — ce qui reste, et pourquoi je n'y touche pas.**

* `/tmp/reproL6.7SGesC` (108 fichiers) : le répertoire de reproduction que
  **j'ai créé** dans ce lot. Supprimé, sa création étant prouvable.
* 509 `tmp*.jsonl` : la fuite corrigée au § 3, **tous antérieurs au correctif**.
  Créés par des exécutions dont je ne peux pas prouver la paternité, certaines
  antérieures à ce lot. Aucun nettoyage par motif large.
* 163 `canal_<uuid>.jsonl` : **résidu non corrigé, nommé ici** (§ 11).

Le contrôle des processus par motif a d'ailleurs re-piégé son auteur : la
commande `ps | grep -E "[m]utation_matrix|..."` s'est trouvée elle-même, la
ligne de commande du shell englobant contenant le motif. C'est la même faute
que `pgrep -f`, déplacée d'un cran. Le décompte retenu est celui par PID exact.

---

## 11. Dette nommée, non traitée dans ce lot

**Le lanceur laisse ses canaux derrière lui.** `mutation_matrix.py` écrit un
fichier `canal_<uuid>.jsonl` par contrôle dans
`SCRATCH = os.environ.get("TMPDIR", "/tmp")`, et ne le reprend jamais : 163
fichiers, dont ceux de la campagne close ci-dessus. C'est la même famille que le
défaut 2, à un autre endroit — et il n'a **pas** été corrigé, délibérément : le
SHA est gelé et la campagne close ; une correction fonctionnelle maintenant
invaliderait l'une et l'autre. Elle appartient au lot suivant, avec son propre
contrôle permanent et sa propre falsification.

**Douze harnais dépendent encore d'une prose**, et 50 attributions de la
campagne passent par le traducteur.

**`authority_root_of_trust.sh` est migré sans contrôle de mutation qui
l'exerce** (§ 4.6) : lui en donner un est le premier candidat du prochain lot.

---

## 12. Delta entre le SHA prouvé et la documentation

Tout ce qui précède — validation ordonnée, campagne, empreintes, workflows —
porte sur `d6b54a2` et sur rien d'autre.

Le présent rapport est ajouté **après** ce SHA, dans un commit de documentation
distinct qui ne touche aucun fichier `.sh`, `.py`, `.sql` ni aucun workflow.
Le delta entre le SHA fonctionnel prouvé et le HEAD documentaire est donc d'un
seul commit, et ce commit ne change rien de ce qui a été mesuré.

---

## 13. Ce sur quoi il faut une décision humaine

Rien n'a été fait qui les engage, et rien ne le sera sans réponse :

* la branche cible reste non résolue — `TARGET_BRANCH_UNRESOLVED` ; aucune
  branche n'a été déplacée, `js2o49` n'a pas été avancée, aucune PR ouverte ;
* aucune instance Supabase n'a été touchée ni interrogée ;
  `SUPABASE_UNVERIFIED` tient : l'implémentation vise PostgreSQL 16 et aucune
  affirmation de compatibilité n'est faite tant qu'un staging réel n'a pas été
  éprouvé de bout en bout ;
* aucune racine d'authentification réelle n'existe dans ce dépôt :
  `BLOCKED_BY_REAL_AUTH`. Ce qui est éprouvé est le **contrat** d'intégration
  du provider, avec un authentificateur qui porte `FICTIF` dans son nom et le
  dit ;
* aucun secret n'a été demandé, journalisé ni inventé.
