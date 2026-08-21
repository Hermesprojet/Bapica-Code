# 6.3b6e — DOSSIER DIAGNOSTIC : rouge `EUROSTRUCT` sur `31552da`

**Statut : `31552da` est candidat DIAGNOSTIQUE, pas candidat de cloture.**
Faits geles avant toute modification. Aucun code n'a ete touche depuis.

## 1. Identification

| | |
|---|---|
| SHA | `31552da1020ecd45030f2bae3fbfdb98f4e574f5` |
| Branche | `claude/eurostruct-saas-platform-js2o49` |
| Workflow ROUGE | `EUROSTRUCT` — run `32431018442` |
| Workflow VERT | `eurostruct — tests` — run `32431018437` |
| Job fautif | `Schema de donnees` — job `96622398473` |
| Job voisin, vert | `Moteur de calcul` — job `96622398320` |
| Etape fautive | n° 8 — `Migrations et garanties structurelles` |
| Debut / fin de l'etape | `2026-08-21T00:02:20Z` -> `00:08:47Z` (**6 min 27 s**) |
| Debut / fin du job | `00:01:17Z` -> `00:08:49Z` |

### Reference verte, meme workflow, SHA precedent

| | |
|---|---|
| SHA | `28daf35d6ff00b16334a8aa4cd96d3ae9b04e113` |
| Workflow | `EUROSTRUCT` — run `32428213261`, job `96614428004` |
| Etape 8 | `2026-08-20T23:21:03Z` -> `23:31:13Z` (**10 min 10 s**), succes |
| `eurostruct — tests` | run `32428213231`, succes |

## 2. Localisation de la defaillance

`run.sh` deploie une base dediee `${DB_NAME}_conc`, appelle `concurrency.sh`,
detruit la base, puis `exit $CONC_CODE`. Un rouge de cette surface termine donc
`run.sh` immediatement et toutes les surfaces suivantes — dont le harnais de
signaux — ne sont pas executees.

Derniere trace SQL de concurrence, relevee dans le journal du conteneur
`postgres:16` (seul flux accessible, cf. §5) :

| run | derniere trace de concurrence | fin de l'etape 8 | ecart |
|---|---|---|---|
| VERT `28daf35` | `2026-08-20 23:28:14 UTC` | `23:31:13Z` | **2 min 59 s** |
| ROUGE `31552da` | `2026-08-21 00:08:42 UTC` | `00:08:47Z` | **5 s** |

Les trois dernieres erreurs SQL du run ROUGE, toutes des contre-exemples
DELIBERES de `concurrency.sh` (elles apparaissent aussi dans les runs verts) :

```
00:08:41  un administrateur normatif existe deja: l'amorcage ne sert qu'a ouvrir
          la chaine, pas a la contourner. Passer par un octroi ordinaire.
00:08:42  un octroi actif de meme portee existe deja pour
          c0000000-0000-0000-0000-00000000000f (can_validate_normative_reference)
00:08:42  operation refusee: l'habilitation 2c53a062-1655-4616-bfb7-574c75baeead
          a ete revoquee pendant l'operation.
00:08:42  revocation refusee: c0000000-0000-0000-0000-0000000000ab ne detient pas
          « can_manage_normative_authorisations » couvrant la portee de l'octroi
          a24deb7a-bfd1-4784-87cb-a92315d5e977.
```

Ces lignes LOCALISENT la defaillance. Elles ne la DIAGNOSTIQUENT pas : les
assertions de `concurrency.sh` sont ecrites sur son stdout, inaccessible (§5).

## 3. Absence confirmee d'execution du harnais de signaux

Dans le run VERT, les 2 min 59 s qui suivent la concurrence portent la signature
du harnais de signaux dans le journal du conteneur :

```
23:30:51 .. 23:31:10   terminating connection due to administrator command   (x8)
```

C'est `pg_terminate_backend` appele par les scenarios C, E et K.

Dans le run ROUGE, **aucune** ligne de cette forme apres la concurrence, et
l'etape se termine 5 secondes plus tard. Le harnais de signaux n'a donc pas
tourne.

## 4. Diff exact `28daf35..31552da`

```
 eurostruct/db/test/mutation_signal_selftest.sh | 14 ++++++++++++++
 1 file changed, 14 insertions(+)
```

Un seul fichier, un seul bloc : l'assertion nommee du relais, dans le scenario
L1 du harnais de signaux. **Ce code n'a pas ete atteint par le run ROUGE** (§3).
`concurrency.sh` et toute la surface SQL sont identiques a l'octet pres entre le
run VERT et le run ROUGE.

## 5. Observabilite : ce qui est accessible, et ce qui ne l'est pas

| canal | etat |
|---|---|
| `get_job_logs` | plafonne a **5000 lignes** et renvoie le journal du **conteneur de service** `postgres:16`, jamais le stdout de l'etape |
| archive ZIP complete | **refusee par la politique du proxy** — `connect_rejected`, 403 sur CONNECT vers `results-receiver.actions.githubusercontent.com:443` |
| metadonnees job/etape | accessibles (dates, conclusions, numeros) |

Consequence : les assertions shell de `concurrency.sh` ne sont pas lisibles
depuis cette session. La cause doit etre etablie par reproduction locale, ou par
une observabilite ajoutee et publiee en artefact (voir plan §7).

## 6. Configurations respectives des deux workflows

Elles ne sont **pas** identiques : `eurostruct — tests` vert et `EUROSTRUCT`
rouge sur le meme SHA ne suffit donc pas a prouver une intermittence.

| | `EUROSTRUCT` / `Schema de donnees` | `eurostruct — tests` / `tests` |
|---|---|---|
| Service | `postgres:16`, `POSTGRES_PASSWORD` | `postgres:16`, `POSTGRES_PASSWORD` + `POSTGRES_USER` |
| Python | **3.12** | **3.11** |
| Installation | `pip install -e engine` (global) | **venv** `.venv-eurostruct` + `engine` + `tools/ndp_import` + `pytest` |
| Client psql | fourni par l'etape `postgresql-16` | `apt-get install postgresql-client` |
| Serveur local | **installe** (`postgresql-16`) puis **cluster arrete** | non installe |
| Connexion | `PGHOST/PGUSER/PGPASSWORD` | `DATABASE_URL` |
| Consentement | `EUROSTRUCT_CLUSTER_JETABLE` sur l'etape | `EUROSTRUCT_CLUSTER_JETABLE` sur l'etape |
| Commande | `./db/test/run.sh` | `./eurostruct/run_tests.sh --require-db` |

Differences pertinentes pour une course : la version de Python, la presence
d'un serveur PostgreSQL local installe puis arrete, et le nombre de processus
concurrents sur un runner a deux cœurs.

## 7. Qualification

**La defaillance est localisee a la surface de concurrence. Le diff
`28daf35..31552da` n'a pas ete atteint. Une non-determination est fortement
suspectee, mais PAS demontree.**

La comparaison determinante est `EUROSTRUCT` **contre lui-meme** sur le meme
SHA, sans nouveau push. Elle est en cours.

Interpretation retenue d'avance :

* meme echec, meme scenario -> defaut probablement deterministe lie a cette
  configuration ;
* succes sans changement -> preuve forte d'intermittence, **et non** une
  autorisation de cloture ;
* echec different -> probleme d'isolation ou d'observabilite plus large.
