# Jalon 6.3b6e — la barrière de vivacité

Ce document dit **ce qui a été établi**, **comment**, et **ce qui ne l'a pas
été**. Ce n'est pas un compte rendu d'activité : chaque affirmation renvoie à
une assertion exécutable, et chaque assertion a été **falsifiée dans les deux
sens** — rouge contre la version défectueuse, verte contre la version corrigée.

Il s'applique à `db/test/mutation_matrix.py` (le wrapper), `db/test/lib_harnais.sh`
(le piège de signaux), et aux trois auto-tests
`db/test/gate_protocol_selftest.sh`, `db/test/mutation_signal_selftest.sh`,
`db/test/mutation_isolation_selftest.sh`.

## Le défaut d'origine

`READY` était une **photographie**. Le wrapper constatait trois processus
vivants à l'instant de la publication, puis publiait ; rien n'empêchait le
harnais de finir avant que le consommateur ne revalide. Mesure, `EUROSTRUCT`
sur `b20bc2e`, scénario A :

```
ok: harnais identifie PID 45206          <- vivant ici
ECHEC: groupes incoherents: harnais[] temoin[] wrapper[45204]
ECHEC: le temoin 45205 n'est plus vivant avant le signal
```

Le harnais est mort **entre deux lectures adjacentes du même script**. La
fenêtre n'était pas étroite : elle n'était pas bornée.

## Ce qui remplace la photographie

Le harnais ouvre une FIFO dont le wrapper garde l'unique extrémité d'écriture,
publie `GATE_ARMED` — **après** l'ouverture, jamais avant — puis s'y bloque. Sa
fin nominale devient inatteignable tant que le wrapper vit. Une sortie normale
du `read` est une **violation de protocole nommée**, pas un succès.

`GATE_ARMED` et non `BLOCKED` : c'est un état de **protocole**, pas une
observation de l'ordonnanceur. Personne n'a mesuré le harnais endormi dans le
noyau, et le nom ne le prétend pas.

## Les défauts trouvés en le prouvant

Huit, tous mesurés avant correction. Aucun n'a été déduit.

| # | Défaut | Mesure |
|---|---|---|
| 1 | Le canal du marqueur était **déjà occupé** : `mktemp` crée le fichier, et la publication exclusive par `ln` échouait donc systématiquement | porte armée en 11 s, `DOUBLON_READY`, marqueur vide, « délai dépassé » 300 s plus tard |
| 2 | `lire_marqueur` exigeait `GATE_ARMED` **inconditionnellement** — faux par construction | un `FAILED` régulier refusé (scénario J) |
| 3 | Le **double** du harnais n'armait pas la porte | les cinq scénarios L expiraient à 300 s chacun |
| 4 | Un **second** SIGTERM tronquait le nettoyage du harnais | 1 TERM → `DEBUT FIN` ; 2 TERM → `DEBUT` ; code 143 dans les deux cas |
| 5 | Un signal pendant la sortie de la matrice laissait un **worktree entier** | 4 fuites sur 10 ; 0 sur 20 après correction |
| 6 | Un signal entre la fin du harnais et la publication **perdait le résultat** | « RESULTAT PERDU », code 143 |
| 7 | Le scénario A **n'exerçait rien sous `run.sh`**, donc en CI | `REFUS: seal_contract.sh exige que ces roles n'existent pas encore` |
| 8 | Le total des contrôles était **écrit en dur** dans le scénario B | ajouter la 65ᵉ mutation rougissait un décompte correct |

Les défauts **4, 5 et 6 sont le même défaut chez trois acteurs différents** : un
signal reçu pendant une séquence terminale la coupe en deux, et le code de
sortie ne le dit pas.

Les défauts **1, 7 et 8 sont la même erreur d'écriture** : une assertion qui
décrit l'état observé au moment où on l'a écrite, au lieu de la propriété qu'on
veut tenir.

## Ce que le code de sortie ne prouve pas

143 dans tous les cas — nettoyage achevé ou tronqué. **Seul le résidu le dit**,
et personne ne le regardait : le scénario A affirmait « aucun résidu » sur un
décor qui n'avait jamais existé. C'est la non-vacuité du décor qui a rendu le
défaut 4 visible.

## Bloquer n'est pas ignorer

La séquence terminale de la matrice est protégée par `pthread_sigmask`, pas par
`SIG_IGN`. Le signal reste **en attente** et est délivré dès le masque levé :
l'interruption a bien lieu, juste après l'écriture atomique. Les trois
implémentations sont discriminées par le test :

| implémentation | résultat publié | code de la matrice |
|---|---|---|
| aucun masque | **perdu** | 143 |
| `SIG_IGN` | publié | **1** — signal avalé |
| `SIG_BLOCK` | publié | 143 — signal différé |

Ignorer aurait été faux : le masque est posé au milieu d'une campagne, et la
matrice serait devenue sourde pour tous les contrôles suivants.

## Une seule autorité de délai

`_arreter_enfant()` signale le groupe, attend sa patience, puis escalade en
SIGKILL. Aucun autre acteur ne borne : le wrapper attend des **événements**, et
les auto-tests observent le temps que l'escalade met à conclure au lieu de lui
en imposer un. Un test qui poserait son propre délai deviendrait une seconde
autorité, et l'on ne saurait plus laquelle a tranché.

Le désarmement des signaux pendant un nettoyage **ne crée pas** d'autorité
concurrente : SIGKILL n'est ni ignorable ni piégeable, et c'est lui qui borne un
nettoyage réellement bloqué.

## La matrice des fenêtres de signal

Six fenêtres. La table **ne s'écrit pas à la main** : les fenêtres portées dans
`gate_protocol_selftest.sh` se déclarent depuis le chemin de succès de leur cas,
et celles portées ailleurs sont vérifiées par la **présence** de leur assertion
dans le fichier cité — renommer l'assertion rougit la table.

| # | fenêtre | portée par |
|---|---|---|
| 1 | avant `GATE_ARMED` | cas 22 |
| 2 | après `GATE_ARMED`, avant `READY` | **CHEMIN NON EXERCÉ** |
| 3 | après `READY` | cas 8 et 9, L1 |
| 4 | pendant le nettoyage | cas 19, cas 6 (isolation) |
| 5 | entre la fin du harnais et la publication du résultat | L7 |
| 6 | après la perte du wrapper | cas 10 |

### Pourquoi la fenêtre 2 n'est pas exercée

Entre la détection de la porte et la publication du marqueur, le wrapper
n'exécute que ses vérifications d'identité : quelques appels à `ps`. La viser
sans crochet reviendrait à compter des réussites.

**Aucun crochet n'est posé dans le wrapper.** C'est la pièce que l'auto-test
extrait et met en échec ; y ajouter du code de test rendrait l'objet mesuré
différent de l'objet livré. Les crochets existants (`ESC_MUTATION_PAUSE_SORTIE`,
`ESC_MUTATION_PAUSE_RESULTAT`) vivent dans la matrice, pas dans le wrapper.

La fenêtre est encadrée par le cas 22 (côté wrapper : aucun `READY` publié) et
le cas 10 (côté harnais : EOF, main rendue en 0,1 s). Elle n'est pas couverte,
et la table le dit à chaque exécution.

## Les SHA intermédiaires ne sont pas des références

`ef90bb7`, `42601e7` et `91f5a4b` introduisent la barrière et **n'ont jamais
tourné verts sur le vrai harnais**. Ils cassaient quatre appelants, et le
premier scénario mourait avant les autres sur un message qui ne nommait pas la
cause. Le premier SHA où le chemin nominal complet passe est **`6448229`**.

L'historique n'est pas réécrit. Cette note et l'en-tête de
`db/test/gate_protocol_selftest.sh` le disent, pour que personne n'aille bissecter
vers un vert qui n'a jamais existé.

## Ce qui est exécuté, et où

`gate_protocol_selftest.sh` a été écrit comme suite permanente et **n'était
câblé nulle part** — ni `run.sh`, ni le workflow. Une garantie non exercée ne se
distingue plus d'une garantie perdue. Il est désormais une étape de `run.sh`, à
côté de l'auto-test d'isolation.

| surface | assertions | durée |
|---|---|---|
| `gate_protocol_selftest.sh` | 69 | ~30 s |
| `mutation_isolation_selftest.sh` | 7 | ~32 s |
| `mutation_signal_selftest.sh` | 127 | ~9 min |

## La campagne de clôture

Exécutée sur **`5d77933`**, le SHA gelé, en un seul passage :

```
MUTATIONS: definis 65 | executes 65 | non executes 0 | echecs inexpliques 0 | code 0
           dont tues 58, redondants voulus 7
           les 65 controles portent quelque chose.
```

Recevabilité vérifiée, et non supposée : l'espace isolé était un worktree
détaché **sur `5d77933`** ; aucun survivant, aucun contrôle creux, aucune
surface non exécutée ; et à la fin, zéro résidu — ni rôle, ni base, ni worktree,
ni FIFO, ni processus. Le dépôt n'a pas bougé pendant la campagne.

Ce document a été complété **après** la campagne. Le commit qui l'ajoute ne
touche que `docs/` : aucune surface exécutable n'a changé depuis `5d77933`, et
le verdict ci-dessus vaut donc pour tout ce que la matrice mesure.

## La neuvième mutation vise l'instrument

Les huit autres visent le produit. `B1` vise le wrapper que la matrice pose
elle-même : si la barrière de vivacité pouvait disparaître sans que rien ne
rougisse, **tous** les verdicts rendus par cette matrice reposeraient sur un
`READY` qui ne promet rien.

Elle est tuée par les cas 1 à 6 et 22, et le verdict nomme la garantie perdue —
`ECHEC: B1.` — parce que la matrice ne reconnaît un contre-exemple que sous
cette forme, et que six cas rouges sans point nommé auraient été comptés creux.
