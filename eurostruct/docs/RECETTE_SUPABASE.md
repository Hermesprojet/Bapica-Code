# Recette sur un staging Supabase

**Statut : `SUPABASE_UNVERIFIED`. Aucune des sept étapes n'a été exécutée sur
une instance Supabase réelle.**

Ce document a été remplacé par
[`DEPLOIEMENT_BASE_HEBERGEE.md`](DEPLOIEMENT_BASE_HEBERGEE.md), qui sépare
provisionnement, migrations et exécution, nomme ce que chaque étape exige
selon le scénario, et dit ce qui a été exécuté — l'auto-test de la recette sur
un PostgreSQL local provisionné comme une base hébergée — et ce qui ne l'a pas
été.

La recette elle-même : `db/test/recette_supabase_staging.sh`, sept étapes,
chacune **EXECUTEE**, **ECHOUEE** ou **NON EXECUTEE** avec sa raison ; mode
`diagnostic` sans aucune mutation ; codes de sortie 0 / 1 / 2 / 4 / 5.

Une version antérieure de cette page nommait quatorze variables, dont
plusieurs inventées pour l'occasion. La recette lit désormais celles que le
produit lit lui-même — `ESC_PLAN_URL`, `ESC_MIGRATOR_URL`,
`EUROSTRUCT_DATABASE_URL`, `EUROSTRUCT_SUPABASE_*`, `EUROSTRUCT_STORAGE_*` —
plus, pour ce qu'elle seule fait : `EUROSTRUCT_STAGING_JETON_A` et `_B`,
`EUROSTRUCT_RECETTE_JETONS_D_ESSAI`, `EUROSTRUCT_STAGING_BACKUP_URL`,
`EUROSTRUCT_STAGING_RESTORE_URL`, `EUROSTRUCT_RECETTE_CIBLE`. Lancée sans
rien, elle les liste, avec leur nature — secret, publique, ou choix.
