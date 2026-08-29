# Lot L4 — rapport de fin

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

## Validation ordonnée — `96df869`

    30 surfaces, 0 rouge, 0 non exécutée
    « Toutes les surfaces de db/test sont vertes. »

Lancée en capturant le PID exact (27268), attendue sur ce PID — jamais par
`pgrep -f`, qui reconnaît sa propre ligne de commande.

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

## Les deux résultats qui comptent

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

### J'ai généralisé une mesure faite sur un heredoc à `-c`

Trente et un sites lisent une valeur **dans la base** — avec `2>&1`, donc en
cas d'échec la variable porte un message d'erreur français plein
d'apostrophes — et la recollent dans un littéral SQL. La valeur casse alors
l'instruction, et le harnais lit une erreur de syntaxe **comme s'il lisait un
refus**.

J'ai converti les trente-deux sites en variables psql, ayant mesuré `:'m'`
dans un **heredoc**. `run.sh` est devenu rouge sur trois surfaces. La mesure
que j'aurais dû faire d'abord :

    psql -tA -v v="abc'def" -c    "select :'v'"   -> ERROR: syntax error at ":"
    psql -tA -v v="abc'def"     <<<"select :'v'"  -> abc'def

**psql n'interpole pas ses variables dans une chaîne `-c`.** Vingt-sept des
trente-deux sites sont des `-c`. Et le passage à l'entrée standard change la
sémantique d'échec :

    psql -tAc "select 1/0"                       -> rc=1
    psql -tA       <<<"select 1/0"               -> rc=0   (!)
    psql -tA -v ON_ERROR_STOP=1 <<<"select 1/0"  -> rc=3

Sans `ON_ERROR_STOP`, la conversion aurait rendu **verts des contrôles qui
doivent être rouges**. Vingt-sept sites, quinze harnais, aucune exécution
disponible pour valider ce changement : la conversion est **reprise**, pas
faite à moitié. Le défaut reste nommé, compté à 31, sous un cliquet qui ne
peut que baisser.

Ce qui reste et qui vaut : le scanner voit les deux défauts sur tous les
véhicules et non les seuls heredocs ; il accepte un chemin de fichier ; il
refuse de conclure sur zéro fichier ; onze selftests l'éprouvent sur des cas
**fabriqués** — dont le cas 10, qui *mesure* qu'une forme échappée arrive
littérale à l'écriture et s'évalue chez la couche cible (c'était le trou
connu), et le cas 8, qui fixe la seule forme de correction qui marche pour
qu'aucune relecture ne reprenne la mienne.

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
* la conversion des 31 recollages, qui exige de valider un changement de
  sémantique d'échec harnais par harnais ;
* le contre-exemple complet de la séparation : neutraliser les **cinq**
  couches, et le test permanent qui en découle ;
* l'intégration du provider : aucun consommateur produit — `BLOCKED_BY_REAL_AUTH` ;
* Supabase : `SUPABASE_UNVERIFIED`, aucune affirmation de compatibilité, aucun
  script lancé sur une instance réelle.
