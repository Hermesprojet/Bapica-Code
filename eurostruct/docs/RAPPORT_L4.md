# Lot L4 — rapport de fin

> **Compte rendu historique.** Ce document décrit l'état du dépôt **au SHA
> de son époque** et n'est pas mis à jour. Pour l'état courant du produit,
> voir le `README.md` à la racine de `eurostruct/`.

**Référence monotone** : `/proc/uptime` 27421,1 s au départ (2026-08-28T21:28:23Z).
Le conteneur a redémarré en cours de lot. L'horloge lue n'a pas été remise à
zéro — elle suit l'hôte — donc **aucun redémarrage n'a été détecté
automatiquement**, et environ 2,4 h d'horloge murale se sont écoulées pendant
l'indisponibilité. C'est écrit ici parce que le chronomètre ne le dit pas
tout seul.

## État — c'est un plafond, pas une ambition

    DB_AUTHORITY_MIGRATION_CONTRACTS_COMPLETE
    PROVIDER_IMPLEMENTED_NOT_INTEGRATED
    BLOCKED_BY_REAL_AUTH
    SUPABASE_UNVERIFIED
    FULL_MUTATION_PENDING

6.3c n'est ni `CLOSED`, ni `DEPLOYABLE`, ni `PRODUCTION_READY`. `3d0acc2`
n'est pas un candidat final.

## Validation ordonnée — `5140436`

    30 surfaces, 0 rouge, 0 non exécutée
    « Toutes les surfaces de db/test sont vertes. »

Lancée en capturant le PID exact (14139), attendue sur ce PID — jamais par
`pgrep -f`, qui reconnaît sa propre ligne de commande. Durée mesurée :
~18,5 min.

Elle a été **relancée trois fois**, sur `96df869`, `1eb57ab` puis `5140436`.
Se prévaloir d'une exécution verte pour un arbre modifié depuis serait
rattacher une preuve à un état qui n'existe plus.

**Ce que cette exécution ne dit pas** : elle établit que les trente surfaces
passent, pas que les garanties qu'elles portent sont irremplaçables. Seule la
campagne de mutations le dit, et elle n'a pas tourné.

## La campagne `3d0acc2` reste historique et non concluante

Son verdict n'est pas réécrit :

    definis 103 | tentes 103 | killed_runtime 80 | killed_install_assertion 5
    redundant_proven 7 | survived 11 | stale 0 | infra_failure 0 | not_run 0

Onze survivants. Le diagnostic causal a montré que **sept sur onze n'étaient
pas des garanties perdues mais des défauts d'attribution** : le verdict était
calculé en lisant la prose destinée à l'humain. C'est ce constat qui a motivé
tout le lot. Les onze sont clos et vérifiés par rejeu filtré ; le registre
compte 104 contrôles, préflight tout à zéro.

`FULL_MUTATION_PENDING` : la campagne complète demande ~3,5 h mesurées. La
fenêtre restante ne le permettait pas, elle n'a donc **pas** été lancée —
plutôt que lancée et laissée inachevée.

## Ce que le lot a produit

| commit | ce qu'il ferme |
|---|---|
| `b9e2a91` | le canal machine versionné remplace l'attribution par la prose |
| `f6b4429` | MF1 reçoit un témoin causal portant son propre identifiant |
| `3d9921c` | F1 à F6 reçoivent des témoins qui les mettent en difficulté |
| `9d8a830` | F6 est tué — le harnais s'éprouve lui-même sans pilote |
| `04e89a1` | la matrice de séparation mesurée : cinq couches, pas trois |
| `96df869` | le scanner voit les deux défauts de composition SQL |
| `1eb57ab` | 19.9 — le scanner doit voir sa propre cécité |
| `5140436` | les 31 recollages clos, par doublement des apostrophes |

## Les trois résultats qui comptent

### La séparation tient par cinq couches, et j'en annonçais trois

Les sept combinaisons non vides de neutralisation des trois couches connues
ont été exercées sur un décor confondu — un seul rôle joue le migrateur *et*
le plan de contrôle. **L'état n'atteint jamais `ACTIVE`.** Les deux couches
que j'ignorais encadrent les trois autres :
`assert_authority_backend_membership()` refuse dès la phase 1, et
`normative_record_activation()` refuse au dernier instant avant d'écrire.

Ce que la matrice **n'établit pas** : aucun contre-exemple complet. Obtenir
`ACTIVE` à tort exigerait de neutraliser les cinq couches, ce qui n'a pas été
fait. La triple neutralisation reste refusée, et le test permanent
correspondant n'existe donc pas. Travail ouvert, pas résultat.

Détail dans `MATRICE_SEPARATION.md`, avec les trois défauts de banc qui ont
chacun produit un diagnostic sans rapport avec la cause.

### Les 31 recollages sont clos — mais pas par la route évidente

Trente et un sites lisaient le manifeste **dans la base** — avec `2>&1`, donc
en cas d'échec la variable portait un message d'erreur français plein
d'apostrophes — et le recollaient dans un littéral SQL. La valeur cassait
l'instruction, et le harnais lisait une **erreur de syntaxe** comme s'il
lisait un **refus**.

J'ai d'abord converti vers la variable psql, ayant mesuré `:'m'` dans un
**heredoc**. `run.sh` est devenu rouge sur trois surfaces. La mesure que
j'aurais dû faire d'abord :

    psql -tA -v v="abc'def" -c    "select :'v'"   -> ERROR: syntax error at ":"
    psql -tA -v v="abc'def"     <<<"select :'v'"  -> abc'def

**psql n'interpole pas ses variables dans une chaîne `-c`**, et vingt-sept des
trente et un sites en sont. Y passer imposerait l'entrée standard, donc
`ON_ERROR_STOP` — sans lui une erreur SQL rend **zéro**, et des contrôles qui
doivent rougir seraient devenus verts — et ferait passer le code de sortie de
1 à 3 sur quinze harnais.

La route retenue est le **doublement des apostrophes** (`esc_litteral`), qui
ne change *rien* à l'invocation : même drapeau, même code de sortie, même
capture. Elle est complète parce que `standard_conforming_strings` vaut `on`
— lu, non supposé. Aller-retour mesuré sur une valeur portant apostrophe,
barre oblique inverse et guillemets français : identique octet pour octet.

Les quatre sites en heredoc ou en `-f` composent le littéral **avant** le
corps, dans une variable : y écrire `$(esc_litteral …)` aurait fermé le
défaut 2 en ouvrant le défaut 1.

Le plafond passe à zéro. Le cliquet a d'ailleurs fonctionné **sur lui-même** :
il a refusé le plafond périmé de 31 en nommant la valeur à inscrire.

### Le scanner est lui-même falsifiable, et c'est mesuré

Un instrument neuf ne vaut rien tant que rien ne prouve qu'il verrait sa
propre défaillance. Le contrôle **19.9** a donc été ajouté à
`harness_safety_selftest.sh` : il fait tourner les onze cas **fabriqués**.
Cinq façons d'aveugler le scanner ont ensuite été appliquées, chacune suivie
d'une exécution complète du harnais, et **deux** choses ont été mesurées à
chaque fois — 19.9 doit rougir, et 19.5 (le balayage du corpus réel) doit
rester vert :

| mutation | 19.9 | 19.5 | verdict |
|---|---|---|---|
| S1 la détection des heredocs est retirée | ROUGE | **VERT** | tué par 19.9 seul |
| S2 le refus sur zéro fichier est retiré | ROUGE | **VERT** | tué par 19.9 seul |
| S3 un chemin de fichier n'est plus accepté | ROUGE | **VERT** | tué par 19.9 seul |
| S4 la tolérance à la forme échappée est retirée | ROUGE | ROUGE | tué, mais 19.5 aussi |
| S5 la détection des recollages est retirée | ROUGE | ROUGE | tué, mais 19.5 aussi |

**Trois des cinq ne sont vues que par les cas fabriqués.** Le corpus réel est
propre : un scanner devenu aveugle y rend zéro, et 19.5 reste vert pendant que
la garantie a disparu. C'est la même faute que celle des onze survivants —
prouver une garantie avec l'exemple qu'elle couvre déjà — et 19.9 est
précisément ce qui la ferme.

Le scanner a été restauré et l'identité au fichier d'origine vérifiée par
`cmp`, non supposée.

**Ce que ceci n'est pas** : ces cinq falsifications ne sont pas encore des
contrôles du registre de mutations. Les inscrire demande une attribution par
point, que les harnais ne portent pas directement — elle passe par
l'adaptateur de prose. Le faire à moitié casserait un préflight aujourd'hui
tout à zéro. C'est le prochain pas, nommé, pas un acquis.

## Quatre défauts de mes propres instruments, trouvés en chemin

1. **une continuation de ligne cassée** rattachait le selftest du canal à une
   étape qui en nommait un autre, et laissait `mutation_signal_selftest.sh` en
   commande **nue** : sous `set -e`, sa défaillance ne devenait plus une
   surface rouge — elle tuait `run.sh` sans nom ni comptage ;
2. **le site d'appel du scanner** jugeait sur « sortie vide = conforme » : la
   ligne de succès que le scanner imprime désormais aurait rendu le contrôle
   19.5 **rouge** alors que le scanner était **vert** ;
3. **le plafond de recollages**, appliqué par fichier au lieu du corpus,
   déclarait en faute quatre cas fabriqués conformes ;
4. **ma propre sonde de suivi** comptait les rouges en cherchant `ECHEC|ROUGE`
   dans la sortie, et a compté deux rouges qui étaient les *libellés* de cas
   de test réussis (« traduction « ECHEC: A: » »). Attribuer un verdict en
   lisant de la prose : exactement le défaut que ce lot supprime ailleurs.

## Ce qui reste ouvert

* la campagne complète des 104 contrôles — `FULL_MUTATION_PENDING` ;
* inscrire S1–S5 au registre de mutations, ce qui suppose de donner au
  contrôle 19.9 un point attribuable par le canal plutôt que par la prose ;
* le contre-exemple complet de la séparation : neutraliser les **cinq**
  couches, et le test permanent qui en découle ;
* l'intégration du provider : aucun consommateur produit — `BLOCKED_BY_REAL_AUTH` ;
* Supabase : `SUPABASE_UNVERIFIED`, aucune affirmation de compatibilité, aucun
  script lancé sur une instance réelle.
