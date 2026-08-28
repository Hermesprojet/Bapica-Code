#!/usr/bin/env bash
#
# EUROSTRUCT — SECURITE DES HARNAIS DE TEST
#
#   source "$(dirname "${BASH_SOURCE[0]}")/lib_harnais.sh"
#
# CE QUE CE FICHIER EXISTE POUR EMPECHER
# ---------------------------------------
# Deux defauts reels, presents dans les harnais avant ce commit, et qui ne se
# voyaient pas parce que tout tournait sur un conteneur jetable:
#
#   1. UN SECRET DANS `argv`. Les scripts appelaient `psql "$DATABASE_URL"`.
#      L'URL porte le mot de passe, et `argv` est lisible par tout processus de
#      la machine (`ps`, `/proc/<pid>/cmdline`). En CI, sur une machine
#      partagee, ou dans une trace de debogage, le secret fuit sans qu'aucune
#      etape ne le mentionne.
#
#   2. LA DESTRUCTION DE ROLES GLOBAUX SUR UN CLUSTER QUELCONQUE.
#      `two_phase_deployment.sh` faisait `drop owned by eurostruct_normative_writer
#      cascade` puis `drop role`. Les roles PostgreSQL sont GLOBAUX au cluster:
#      lance par erreur avec une `DATABASE_URL` de staging — ou de production —
#      il aurait detruit les vrais roles normatifs et, par CASCADE, les objets
#      qui en dependent. Rien ne l'en empechait.
#
# CE QUI EST FOURNI ICI
# ----------------------
#   harnais_connexion            l'URL est decoupee en variables libpq, jamais
#                                passee en argument; les PG* ambiantes sont
#                                effacees; DATABASE_URL est retiree ensuite.
#   harnais_jeton                un jeton aleatoire par execution.
#   exiger_cluster_jetable       refus par defaut si le cluster n'est pas
#                                prouve jetable et isole.
#   exiger_roles_absents         refus si un role canonique preexiste — on ne
#                                detruit JAMAIS ce qu'on n'a pas cree.
#   registre_role / detruire_roles_crees
#                                nettoyage par NOMS EXACTS, jamais par motif.
#
# MODELE DE MENACE DE CE FICHIER: l'operateur distrait, la variable
# d'environnement heritee, la copie de commande. Pas l'operateur malveillant —
# qui a de toute facon un `psql`.

# --------------------------------------------------------------------------
# OU EST LA PHASE 0 — UN SEUL ENDROIT LE SAIT (6.3b6d)
# --------------------------------------------------------------------------
# Le sceau vivait dans `db/migrations/`, et chaque harnais devait l'ignorer:
#
#     [[ "$(basename "$f")" == 0000_* ]] && continue
#
# Cinq appelants portaient cette ligne, un sixieme l'avait oubliee. La frontiere
# entre ce que le PLAN DE CONTROLE applique et ce que le MIGRATEUR applique est
# maintenant celle des repertoires — `db/control_plane/` contre
# `db/migrations/` — et plus une convention d'ecriture.
#
# `HARNAIS_SCEAU` est donne ici pour qu'aucun harnais ne redise ce chemin: le
# jour ou une version 2 s'ajoutera, c'est cette ligne qui changera, et elle
# seule.
HARNAIS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNAIS_DB_DIR="$(dirname "$HARNAIS_LIB_DIR")"
HARNAIS_SCEAU="$HARNAIS_DB_DIR/control_plane/0001_normative_seal.sql"

# --------------------------------------------------------------------------
# LE SERVEUR REPOND-IL EN TCP ? (6.3b6e)
# --------------------------------------------------------------------------
# `tools/deploy_eurostruct.sh` recoit deux URL: un `postgresql://` porte un
# HOTE, pas un repertoire de socket. Les harnais qui l'exercent doivent donc
# savoir si le cluster ecoute en TCP, meme quand le reste de la suite passe par
# la socket unix.
#
# LA QUESTION EST « LE SERVEUR REPOND-IL », PAS « PUIS-JE M'AUTHENTIFIER ».
# Premiere ecriture, mesuree: le controle se connectait en `postgres` avec le
# mot de passe de l'environnement. Sur un cluster local ou `postgres` n'a pas
# de mot de passe, il obtenait « password authentication failed » et concluait
# a l'absence de TCP — alors que le serveur venait precisement de repondre. Une
# garde trop large efface la surface qu'elle pretend proteger: trois scenarios
# etaient annonces NON EXECUTE sans qu'aucun ne l'ait ete pour cette raison.
#
# `pg_isready` pose exactement la bonne question. A defaut, on retombe sur
# `psql` en distinguant un refus d'AUTHENTIFICATION — qui prouve que le serveur
# repond — d'une absence de reponse.
harnais_tcp_joignable() {
  if command -v pg_isready >/dev/null 2>&1; then
    pg_isready -h localhost -p "${PGPORT:-5432}" >/dev/null 2>&1
    return $?
  fi
  local err
  err=$(PGHOST=localhost PGPORT="${PGPORT:-5432}" PGCONNECT_TIMEOUT=5 \
          psql -X -q -tAc "select 1" -d postgres 2>&1)
  [[ $? -eq 0 ]] && return 0
  grep -qiE "authentication|role .* does not exist|database .* does not exist" <<<"$err"
}

# --------------------------------------------------------------------------
# CONNEXION — le secret ne passe jamais par argv
# --------------------------------------------------------------------------
# Apres cet appel, TOUTE connexion se fait par `psql -X -q [-d base]`, sans
# aucun argument de connexion: hote, port, utilisateur et mot de passe viennent
# de l'environnement. Changer de base se fait par `-d`, ce qui ne perd plus ni
# l'hote ni les identifiants — le defaut qu'une URL reecrite a la main
# reintroduisait a chaque fois.
harnais_connexion() {
  if [[ -z "${DATABASE_URL:-}" ]]; then
    # Pas d'URL: on garde les PG* de l'environnement, en posant les defauts
    # locaux. Rien a decouper, donc rien a proteger.
    export PGHOST="${PGHOST:-/tmp}"
    export PGUSER="${PGUSER:-postgres}"
    export PGDATABASE="${PGDATABASE:-postgres}"
    return 0
  fi

  local errpy conn ligne
  errpy="$(mktemp)"
  # Le decoupage est CAPTURE ET VERIFIE avant tout `eval`. Une URL invalide
  # produirait une sortie vide, `eval` ne poserait rien, et `psql` se
  # rabattrait sur les PG* ambiantes — donc potentiellement sur une AUTRE base
  # que celle qu'on croit viser. Un echec de decoupage doit arreter le script
  # avant le premier appel, pas le rediriger en silence.
  if ! conn="$(DATABASE_URL="$DATABASE_URL" python3 - 2>"$errpy" <<'FINPARSE'
import os, sys, shlex
from urllib.parse import urlsplit, unquote, parse_qs
u = urlsplit(os.environ["DATABASE_URL"])
if u.scheme not in ("postgres", "postgresql"):
    sys.stderr.write("schema attendu postgres:// ou postgresql://\n"); sys.exit(2)
if not u.hostname:
    sys.stderr.write("hote absent de l'URL\n"); sys.exit(2)
if not u.username:
    sys.stderr.write("utilisateur absent de l'URL\n"); sys.exit(2)
base = unquote(u.path.lstrip("/"))
if not base:
    sys.stderr.write("nom de base absent de l'URL\n"); sys.exit(2)
q = parse_qs(u.query)
champs = {
    "PGHOST": u.hostname,
    "PGPORT": str(u.port or 5432),
    "PGUSER": unquote(u.username),
    "PGPASSWORD": unquote(u.password or ""),
    "PGDATABASE": base,
    "PGSSLMODE": q.get("sslmode", ["prefer"])[0],
}
for k, v in champs.items():
    print(f"export {k}={shlex.quote(v)}")
FINPARSE
  )"; then
    echo "REFUS: DATABASE_URL inexploitable." >&2
    sed 's/^/       /' "$errpy" >&2
    rm -f "$errpy"
    return 2
  fi
  rm -f "$errpy"

  # La sortie doit avoir EXACTEMENT la forme attendue: on n'evalue pas du texte
  # dont on n'a pas verifie la nature.
  while IFS= read -r ligne; do
    [[ -n "$ligne" ]] || continue
    if ! [[ "$ligne" =~ ^export\ PG(HOST|PORT|USER|PASSWORD|DATABASE|SSLMODE)= ]]; then
      echo "REFUS: sortie de decoupage inattendue, evaluation refusee." >&2
      return 2
    fi
  done <<<"$conn"

  # AUCUN REPLI POSSIBLE. Les PG* ambiantes — y compris les redirections par
  # service ou par fichier de mots de passe — sont effacees AVANT d'appliquer
  # celles de l'URL.
  unset PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE PGSSLMODE \
        PGSERVICE PGSERVICEFILE PGPASSFILE PGREQUIRESSL PGCHANNELBINDING
  eval "$conn"

  local v
  for v in PGHOST PGUSER PGDATABASE; do
    if [[ -z "${!v:-}" ]]; then
      echo "REFUS: $v vide apres decoupage de l'URL." >&2
      return 2
    fi
  done

  # L'URL a livre ce qu'elle contenait: elle n'a plus de raison d'exister. La
  # garder exposerait le secret a tout sous-processus — y compris a un `psql`
  # remplace sur le PATH — et a toute trace de debogage.
  unset DATABASE_URL
  return 0
}

# --------------------------------------------------------------------------
# JETON ALEATOIRE, un par execution
# --------------------------------------------------------------------------
# Des noms fixes rendent deux executions concurrentes destructrices l'une pour
# l'autre, et font qu'un nettoyage tardif peut emporter les objets d'une autre
# execution. Douze caracteres hexadecimaux: assez pour qu'une collision ne se
# produise pas, assez court pour rester sous la limite de 63 octets des
# identifiants PostgreSQL une fois prefixe.
harnais_jeton() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 6
  else
    python3 -c 'import secrets; print(secrets.token_hex(6))'
  fi
}

# --------------------------------------------------------------------------
# LA PORTE: ce cluster est-il PROUVE jetable et isole ?
# --------------------------------------------------------------------------
# FAIL-CLOSED. Aucune preuve = refus. Une declaration seule ne suffit pas non
# plus: la variable d'environnement dit l'INTENTION, les quatre controles
# suivants constatent les FAITS. Il faut les deux.
#
# A n'appeler QUE depuis un script qui cree et detruit des roles GLOBAUX.
# --------------------------------------------------------------------------
# PRECONTROLE SANS RESEAU — avant la premiere connexion
# --------------------------------------------------------------------------
# CE QUI L'A RENDU NECESSAIRE, mesure. La porte complete lit le CATALOGUE: elle
# doit donc se connecter. Le verrou aussi. Les deux precedaient tout controle
# d'intention et d'hote, si bien que:
#
#   DATABASE_URL="postgres://u:motdepasse@hote-distant/db" ./run.sh
#
# OUVRAIT UNE CONNEXION vers l'hote distant — verifie avec un ecouteur local:
# « CONNEXION RECUE » — alors qu'aucun consentement n'etait pose et que l'hote
# n'etait pas la boucle locale. Le refus arrivait apres, et sur un motif faux
# (« verrou deja detenu »), le co-processus ayant simplement echoue.
#
# Presenter des identifiants a une machine qu'on va refuser est deja un defaut,
# meme si le refus suit: le secret a quitte le processus.
#
# Ces deux controles ne lisent QUE l'environnement. Aucun octet ne part.
exiger_precontrole_local() {
  local qui="${1:-ce harnais}"
  local attendu='oui-cluster-jetable-et-isole'

  if [[ "${EUROSTRUCT_CLUSTER_JETABLE:-}" != "$attendu" ]]; then
    cat >&2 <<EOF
REFUS: $qui cree et detruit des ROLES GLOBAUX du cluster
       (eurostruct_normative_writer, normative_backend, ...). Les roles ne sont
       pas confines a une base: sur un cluster partage, de staging ou de
       production, cette execution detruirait les vrais roles normatifs.

       Ce script exige un cluster PostgreSQL ENTIEREMENT JETABLE, dedie a ces
       tests, dont la perte n'a aucune consequence.

       Ne le lancez JAMAIS sur Supabase ni sur un cluster partage.

       Si — et seulement si — le cluster vise est jetable:
           export EUROSTRUCT_CLUSTER_JETABLE=$attendu

       (Aucune connexion n'a ete ouverte.)
EOF
    return 2
  fi

  case "${PGHOST:-}" in
    /*|localhost|127.0.0.1|::1) : ;;
    *)
      echo "REFUS: $qui exige un hote de boucle locale (socket, localhost," >&2
      echo "       127.0.0.1 ou ::1). L'hote fourni ne l'est pas." >&2
      echo "       Aucune connexion n'a ete ouverte, aucun identifiant" >&2
      echo "       n'a ete presente." >&2
      return 2 ;;
  esac
  return 0
}

exiger_cluster_jetable() {
  local qui="${1:-ce harnais}"
  local attendu='oui-cluster-jetable-et-isole'
  local n

  # 1+2. L'intention et l'hote sont deja etablis SANS RESEAU par
  #      `exiger_precontrole_local`. Ils sont re-verifies ici — appeler la
  #      porte complete sans le precontrole resterait sur.
  if [[ "${EUROSTRUCT_CLUSTER_JETABLE:-}" != "$attendu" ]]; then
    cat >&2 <<EOF
REFUS: $qui cree et detruit des ROLES GLOBAUX du cluster
       (eurostruct_normative_writer, normative_backend, ...). Les roles ne sont
       pas confines a une base: sur un cluster partage, de staging ou de
       production, cette execution detruirait les vrais roles normatifs.

       Ce script exige un cluster PostgreSQL ENTIEREMENT JETABLE, dedie a ces
       tests, dont la perte n'a aucune consequence.

       Ne le lancez JAMAIS sur Supabase ni sur un cluster partage.

       Si — et seulement si — le cluster vise est jetable:
           export EUROSTRUCT_CLUSTER_JETABLE=$attendu
EOF
    return 2
  fi

  # 2. LA BOUCLE LOCALE, redite du precontrole.
  case "${PGHOST:-}" in
    /*|localhost|127.0.0.1|::1) : ;;
    *)
      echo "REFUS: $qui exige un hote de boucle locale (socket, localhost," >&2
      echo "       127.0.0.1 ou ::1). L'hote fourni ne l'est pas." >&2
      return 2 ;;
  esac

  # 3. AUCUN MARQUEUR DE PLATEFORME GEREE. Supabase, RDS, Cloud SQL et Azure
  #    laissent des roles caracteristiques. Leur presence prouve que le cluster
  #    n'est pas jetable, quoi qu'en dise la variable.
  n="$(psql -X -q -tA -d postgres -c "
    select count(*) from pg_roles
     where rolname in ('supabase_admin','supabase_auth_admin',
                       'supabase_storage_admin','supabase_replication_admin',
                       'supabase_read_only_user','dashboard_user',
                       'rds_superuser','rdsadmin','rds_replication',
                       'cloudsqlsuperuser','cloudsqladmin',
                       'azure_pg_admin','azuresu','pgbouncer')" 2>/dev/null)"
  if [[ -z "$n" ]]; then
    echo "REFUS: $qui n'a pas pu interroger le cluster pour verifier qu'il" >&2
    echo "       est jetable. Un controle qui n'a pas pu s'executer ne vaut" >&2
    echo "       pas un controle reussi." >&2
    return 2
  fi
  if [[ "$n" != "0" ]]; then
    echo "REFUS: $qui a trouve $n role(s) de plateforme GEREE (Supabase, RDS," >&2
    echo "       Cloud SQL, Azure). Ce cluster n'est pas jetable." >&2
    return 2
  fi

  # 4. AUCUNE BASE ETRANGERE. Un cluster dedie ne porte que les bases systeme
  #    et celles de ces tests. Une base inconnue signale un cluster partage
  #    avec autre chose — et donc des roles qui ne nous appartiennent pas.
  local etrangeres
  etrangeres="$(psql -X -q -tA -d postgres -c "
    select string_agg(datname, ', ') from pg_database
     where datname not in ('postgres','template0','template1')
       and datname !~ '^(eurostruct|esc)[a-zA-Z0-9_]*\$'" 2>/dev/null)"
  if [[ -n "$etrangeres" ]]; then
    echo "REFUS: $qui a trouve des bases etrangeres a ces tests: $etrangeres." >&2
    echo "       Ce cluster sert a autre chose; ses roles globaux ne sont pas" >&2
    echo "       a nous." >&2
    return 2
  fi

  # 5. SUPERUTILISATEUR. Un cluster jetable local en donne un; aucune
  #    plateforme geree n'en donne. C'est le controle le plus court et le plus
  #    difficile a satisfaire par erreur.
  if [[ "$(psql -X -q -tA -d postgres -c "select current_setting('is_superuser')" 2>/dev/null)" != "on" ]]; then
    echo "REFUS: $qui exige une connexion superutilisateur, ce qu'aucune" >&2
    echo "       plateforme geree n'accorde. Le cluster vise n'est donc pas" >&2
    echo "       le cluster jetable attendu." >&2
    return 2
  fi

  return 0
}

# --------------------------------------------------------------------------
# ON NE DETRUIT JAMAIS CE QU'ON N'A PAS CREE
# --------------------------------------------------------------------------
# Les roles canoniques portent des noms FIXES, imposes par la migration. Un
# script qui les cree doit donc constater qu'ils n'existent pas encore, et
# REFUSER sinon — jamais les detruire pour « repartir propre ». C'est
# exactement le geste qui, sur le mauvais cluster, detruit la production.
exiger_roles_absents() {
  local qui="$1"; shift
  local presents
  presents="$(psql -X -q -tA -d postgres -c "
    select string_agg(quote_ident(rolname), ', ' order by rolname)
      from pg_roles where rolname = any (array[$(
        printf "'%s'," "$@" | sed 's/,$//')])" 2>/dev/null)"
  if [[ -n "$presents" ]]; then
    cat >&2 <<EOF
REFUS: $qui exige que ces roles n'existent pas encore, et ils existent:
       $presents

       Ce script ne les detruira PAS: il n'a aucun moyen de savoir s'ils sont
       a lui. Sur un cluster jetable, detruisez-les a la main puis relancez.
EOF
    return 2
  fi
  return 0
}

# --------------------------------------------------------------------------
# IDENTIFIANTS POSTGRESQL — valides une fois, au meme endroit
# --------------------------------------------------------------------------
# Les noms de bases sont interpoles dans `create database`, `drop database` et
# dans des predicats `datname = '...'`. `run.sh` prenait `DB_NAME` de
# l'environnement et l'utilisait tel quel; seuls les sous-scripts validaient le
# leur, et le refus n'arrivait donc qu'apres coup — par accident d'ordre, pas
# par construction.
#
# LA LONGUEUR COMPTE AUTANT QUE LA FORME. PostgreSQL TRONQUE silencieusement
# les identifiants a 63 octets. Or les harnais derivent des noms:
#
#   DB_NAME + "_2p"        prefixe de two_phase_deployment.sh
#           + "_ctl_"      role du plan de controle
#           + 12           jeton hexadecimal
#
# soit 20 caracteres au-dela de `DB_NAME`. Deux bases distinctes tronquees au
# meme nom, et un harnais detruit les objets de l'autre en croyant nettoyer les
# siens. La borne est donc calculee, pas choisie: 63 - 20 = 43, arrondi a 40
# pour garder une marge si un suffixe s'allonge.
# --------------------------------------------------------------------------
# LES ROLES DU STUB SUPABASE SONT GLOBAUX, EUX AUSSI
# --------------------------------------------------------------------------
# `00_supabase_stub.sql` cree `anon` et `authenticated` — des ROLES, donc des
# objets de CLUSTER, qui survivent a la destruction de la base. Aucun harnais
# ne les rendait: mesure sur le cluster de test, ils subsistaient apres chaque
# execution de la commande canonique, et « aucun role residuel » etait faux.
#
# Ils sont traites exactement comme les roles canoniques: exiges absents au
# demarrage — un harnais ne detruit jamais ce qu'il n'a pas cree — et rendus en
# sortie.
HARNAIS_ROLES_STUB=(anon authenticated)

# --------------------------------------------------------------------------
# LE PIEGE DE SORTIE NE SUFFIT PAS: BASH NE L'EXECUTE PAS SUR UN SIGNAL
# --------------------------------------------------------------------------
# `trap ... EXIT` couvre la fin normale et `exit`. Il NE COUVRE PAS SIGTERM ni
# SIGINT: sans gestionnaire pour ces signaux, bash meurt sur-le-champ et le
# piege de sortie n'est jamais execute. Un harnais interrompu — Ctrl-C d'un
# operateur, timeout de CI, `kill` — laissait donc derriere lui ses roles
# GLOBAUX et sa base.
#
# MESURE: `harness_safety_selftest.sh` scenario 14 interrompt volontairement
# `two_phase_deployment.sh` et exige zero residu. Il annoncait « zero residu »
# alors que le cluster gardait `interr_mig_*`, `interr_ctl_*` et jusqu'a six
# roles canoniques — assez pour faire refuser les executions suivantes, ce qui
# s'est produit deux fois de suite.
#
# Les gestionnaires ci-dessous se contentent d'`exit`, ce qui DECLENCHE le
# piege de sortie. Les codes sont les codes conventionnels 128+signal, pour que
# « interrompu » reste distinguable de « refuse » (2) et de « non execute » (3).
#
# LE PREMIER SIGNAL PRIS DESARME LES SUIVANTS, ET C'EST CE QUI REND LE PIEGE DE
# SORTIE ATTEIGNABLE. Sans `trap ""`, un SECOND signal arrivant PENDANT le
# nettoyage relance ce gestionnaire, donc `exit`, et le nettoyage s'arrete la
# ou il en etait — en laissant exactement les roles et bases qu'il venait de
# commencer a rendre.
#
# CE N'EST PAS UNE HYPOTHESE. Deux TERM sont la norme, pas l'exception: la
# matrice signale LE GROUPE (`os.killpg`) et le wrapper RELAIE ensuite le
# signal au harnais. Mesure en isolation, meme forme que le harnais reel:
#
#   un seul TERM   -> code 143, journal « MENAGE_DEBUT MENAGE_FIN »
#   deux TERM      -> code 143, journal « MENAGE_DEBUT »          <- tronque
#   avec `trap ""` -> code 143, journal complet pour 1, 2 ou 3 TERM
#
# LE CODE DE SORTIE EST 143 DANS LES TROIS CAS: il ne distingue pas un
# nettoyage acheve d'un nettoyage coupe en deux. C'est le residu qui le dit,
# et personne ne le regardait — le scenario A affirmait « aucun residu » sur
# un decor qui n'avait jamais existe.
#
# CELA NE CREE PAS DE SECONDE AUTORITE DE DELAI. Le parent garde la sienne et
# escalade en SIGKILL, qui ne peut etre ni ignore ni piege: un nettoyage
# reellement bloque reste borne par lui, pas par le harnais.
harnais_piege_signaux() {
  trap 'trap "" TERM INT HUP; exit 143' TERM
  trap 'trap "" TERM INT HUP; exit 130' INT
  trap 'trap "" TERM INT HUP; exit 129' HUP
}

HARNAIS_IDENT_MAX=40

harnais_valider_identifiant() {
  local quoi="$1" valeur="$2"
  if ! [[ "$valeur" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "REFUS: $quoi « $valeur » n'est pas un identifiant PostgreSQL simple." >&2
    echo "       Attendu: une lettre ou « _ », puis lettres, chiffres et « _ »." >&2
    echo "       Il serait interpole dans du SQL." >&2
    return 2
  fi
  if [[ "${#valeur}" -gt "$HARNAIS_IDENT_MAX" ]]; then
    echo "REFUS: $quoi « $valeur » fait ${#valeur} caracteres, au-dela de" >&2
    echo "       $HARNAIS_IDENT_MAX. Les harnais en derivent des noms jusqu'a" >&2
    echo "       20 caracteres plus longs, et PostgreSQL TRONQUE a 63: deux" >&2
    echo "       noms distincts pourraient devenir le meme." >&2
    return 2
  fi
  return 0
}

# --------------------------------------------------------------------------
# VERROU EXCLUSIF AU NIVEAU DU CLUSTER
# --------------------------------------------------------------------------
# LA COURSE QU'IL FERME. `exiger_roles_absents` constate que les roles
# canoniques n'existent pas, et le harnais en deduit que tout role canonique
# present a la fin est a lui. Deux executions simultanees peuvent faire ce
# constat TOUTES LES DEUX, puis l'une detruire les roles que l'autre vient de
# creer — pendant qu'elle s'en sert. La deduction devient fausse, et le
# nettoyage devient une destruction.
#
# POURQUOI UN VERROU CONSULTATIF DE SESSION, ET PAS UNE TABLE NI UN FICHIER.
#
#   * un fichier de verrou est local a la machine; deux machines visant le
#     meme cluster ne se verraient pas;
#   * une ligne dans une table SURVIT a un processus tue, et wedge la CI
#     jusqu'a une intervention manuelle;
#   * un verrou consultatif de SESSION est libere par PostgreSQL lui-meme des
#     que la connexion tombe — plantage, `kill -9`, coupure reseau. Il n'y a
#     donc aucun etat rance possible.
#
# La session est tenue ouverte par un co-processus `psql`: tant que le script
# vit, la connexion vit et le verrou tient. Quand le script meurt, de quelque
# facon que ce soit, la connexion meurt avec lui.
# La cle est surchargeable par l'environnement, et cela sert a UNE chose: le
# scenario de concurrence de l'auto-test fait s'affronter deux enfants sur une
# cle qui leur est propre, pendant que le parent garde la vraie. Sans cela il
# devrait relacher le verrou reel — et ouvrir, le temps du scenario, la fenetre
# meme qu'il verifie. Defaut mesure: une seconde execution passait alors la
# porte et voyait les temoins transitoires de la premiere.
HARNAIS_VERROU_CLE="${EUROSTRUCT_HARNAIS_VERROU_CLE:-7314159}"

# LA CLE EST VALIDEE, PARCE QU'ELLE EST INTERPOLEE DANS DU SQL.
#
# CONTRE-EXEMPLE MESURE sur la version precedente:
#
#   EUROSTRUCT_HARNAIS_VERROU_CLE="1); create role injecte_temoin nologin; \
#                                   select pg_try_advisory_lock(1"
#
# le co-processus executait le `create role` — verifie, le role existait apres
# coup — et le harnais annoncait par-dessus « verrou deja detenu », donc un
# etat de verrou faux. Une variable d'environnement devenait un canal
# d'execution SQL arbitraire, sous le role administrateur du cluster.
#
# Un entier decimal, et rien d'autre. Pas de guillemets a echapper, pas de
# forme « presque valide » a interpreter: ce qui n'est pas un entier est
# refuse, et le refus est fatal.
harnais_valider_cle() {
  if ! [[ "$HARNAIS_VERROU_CLE" =~ ^[0-9]{1,18}$ ]]; then
    echo "REFUS: cle de verrou invalide. Un entier decimal est attendu;" >&2
    echo "       toute autre valeur serait interpolee dans du SQL execute" >&2
    echo "       sous le role administrateur du cluster." >&2
    return 2
  fi
  return 0
}
HARNAIS_VERROU_TENU=0

harnais_verrou_prendre() {
  local qui="${1:-ce harnais}" pris

  # VALIDER AVANT LA PREMIERE REQUETE, ET NON APRES.
  #
  # CONTRE-EXEMPLE MESURE: `harnais_valider_cle` etait appelee APRES le bloc de
  # reentrance, qui interpole pourtant la cle. Avec
  #
  #   EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE=1
  #   EUROSTRUCT_HARNAIS_VERROU_CLE="0 ; create role a1_injecte nologin ; select 0"
  #
  # le `create role` s'executait dans la requete de reentrance — verifie, le
  # role existait — et le refus « cle de verrou invalide » tombait ENSUITE.
  # Valider apres avoir tire, c'est valider pour la forme.
  harnais_valider_cle || return 2

  # LE MARQUEUR EST REFUSE, PAS NETTOYE.
  #
  # `${VAR//[^0-9]/}` retirait les caracteres non numeriques: « 99abc9 »
  # devenait « 999 », c'est-a-dire qu'une valeur invalide etait TRANSFORMEE en
  # valeur valide, puis utilisee. Un assainissement qui fabrique une entree
  # acceptable a partir d'une entree refusable ne protege pas: il devine.
  if [[ -n "${EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE:-}" ]] \
     && ! [[ "$EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE" =~ ^[0-9]{1,10}$ ]]; then
    echo "REFUS: marqueur de reentrance invalide. Un PID decimal est attendu;" >&2
    echo "       toute autre valeur serait interpolee dans du SQL." >&2
    return 2
  fi

  # RE-ENTRANCE. L'auto-test de securite INVOQUE la commande canonique pour la
  # mettre en echec: si l'enfant redemandait le verrou que son parent detient,
  # il refuserait pour une raison etrangere au scenario, et la preuve ne
  # porterait plus sur ce qu'elle annonce.
  #
  # Le jeton est pose par le parent et transmis par l'environnement. Il ne
  # relache aucune exclusion vis-a-vis des AUTRES arbres d'execution: ceux-la
  # n'ont pas le jeton, et se heurtent au verrou.
  if [[ -n "${EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE:-}" ]]; then
    # LE MARQUEUR NE SUFFIT PAS: IL EST FORGEABLE.
    #
    # CONTRE-EXEMPLE MESURE sur la version precedente: pendant qu'une
    # execution A detenait le verrou,
    #
    #   EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE=999999 ./two_phase_deployment.sh x
    #
    # etait ADMIS — « tenu=0 » — et repartait detruire des roles globaux en
    # parallele de A. Une variable d'environnement suffisait a desactiver le
    # verrou.
    #
    # Le marqueur porte donc le PID DU BACKEND qui detient reellement le
    # verrou, et on VERIFIE dans `pg_locks` que ce backend le detient encore,
    # sur CETTE cle. Forger le marqueur exige alors de nommer une session qui
    # detient veritablement le verrou — c'est-a-dire une execution de harnais
    # authentique, ce qui est exactement l'invariant recherche.
    #
    # `pg_try_advisory_lock(bigint)` decompose la cle en `classid` (32 bits de
    # poids fort) et `objid` (32 bits de poids faible), avec `objsubid = 1`.
    local reel
    reel="$(psql -X -q -tA -d postgres -c "
      select count(*) from pg_locks
       where locktype = 'advisory' and granted
         and objsubid = 1
         and pid = $EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
         and ((classid::bigint << 32) | objid::bigint) = $HARNAIS_VERROU_CLE" 2>/dev/null)"
    if [[ "$reel" == "1" ]]; then
      HARNAIS_VERROU_TENU=0
      return 0
    fi
    echo "      NOTE: marqueur de reentrance present mais AUCUN verrou reel ne" >&2
    echo "            correspond (pid $EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE)." >&2
    echo "            Il est ignore, et le verrou est demande normalement." >&2
    unset EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
  fi

  coproc HARNAIS_VERROU { psql -X -q -At -d postgres 2>&1; }
  if [[ -z "${HARNAIS_VERROU_PID:-}" ]]; then
    echo "NON EXECUTE: $qui n'a pas pu ouvrir la session du verrou." >&2
    return 3
  fi
  echo "select pg_try_advisory_lock($HARNAIS_VERROU_CLE)::text;" >&"${HARNAIS_VERROU[1]}"
  if ! read -r -t 15 -u "${HARNAIS_VERROU[0]}" pris; then
    echo "NON EXECUTE: $qui n'a obtenu aucune reponse du verrou en 15 s." >&2
    harnais_verrou_rendre
    return 3
  fi
  # TROIS REPONSES, ET NON DEUX. `true` et `false` sont des verdicts; TOUT LE
  # RESTE est une non-reponse, et la confondre avec `false` a produit un faux
  # diagnostic mesure: le socket local avait change de repertoire, `psql`
  # rendait « connection refused », et le harnais annoncait « une autre
  # execution est en cours » — sur un cluster ou aucune session n'existait.
  # L'exploitant cherchait alors un processus concurrent inexistant.
  if [[ "$pris" != "true" && "$pris" != "false" ]]; then
    cat >&2 <<EOF
NON EXECUTE: $qui n'a pas pu interroger le verrou de harnais.

       La session du verrou n'a rendu ni « true » ni « false », mais:
           $pris

       CE N'EST PAS UNE CONTENTION: rien ne dit qu'une autre execution tourne.
       La cause habituelle est une connexion impossible — PGHOST pointe vers un
       repertoire de socket ou le serveur n'ecoute pas. Verifiez:
           psql -X -q -tAc "select 1" -d postgres
EOF
    harnais_verrou_rendre
    return 3
  fi
  if [[ "$pris" == "false" ]]; then
    cat >&2 <<EOF
NON EXECUTE: le verrou de harnais est deja detenu par une autre execution.

       Deux executions simultanees se detruiraient mutuellement leurs roles
       globaux. Celle-ci s'arrete SANS RIEN NETTOYER — un nettoyage ici
       emporterait les objets de l'execution en cours.

       Relancez quand l'autre execution est terminee.
EOF
    harnais_verrou_rendre
    return 3
  fi

  HARNAIS_VERROU_TENU=1

  # Le PID DU BACKEND, et non celui du shell: c'est lui qui figure dans
  # `pg_locks`, donc le seul que l'enfant puisse verifier. Exporter `$$` — le
  # shell — ne prouvait rien et rendait le marqueur purement declaratif.
  local backend
  echo "select pg_backend_pid();" >&"${HARNAIS_VERROU[1]}"
  if ! read -r -t 15 -u "${HARNAIS_VERROU[0]}" backend || ! [[ "$backend" =~ ^[0-9]+$ ]]; then
    echo "NON EXECUTE: $qui n'a pas pu identifier le backend du verrou." >&2
    harnais_verrou_rendre
    return 3
  fi
  export EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE="$backend"
  export EUROSTRUCT_HARNAIS_VERROU_CLE="$HARNAIS_VERROU_CLE"
  return 0
}

harnais_verrou_rendre() {
  # LA CAPTURE DE DIAGNOSTIC MEURT ICI, ET DANS AUCUN HARNAIS EN PARTICULIER.
  # C'est le dernier geste de teardown que TOUS partagent: la placer ailleurs
  # reviendrait a la recopier vingt-cinq fois, ce qui est exactement la
  # divergence que `esc_diag_rapporter` existe pour supprimer. Les identifiants
  # ont deja atteint stderr au moment du refus; ce qui disparait ici est le
  # fichier, pas l'information.
  esc_diag_capture_fermer
  [[ -n "${HARNAIS_VERROU_PID:-}" ]] || return 0
  # Fermer l'entree du co-processus termine `psql`, donc la session, donc le
  # verrou. Aucun `pg_advisory_unlock` explicite: on veut que la liberation
  # tienne aussi quand le script meurt sans passer par ici.
  #
  # `exec {TABLEAU[1]}>&-` N'EST PAS la syntaxe de fermeture par variable: bash
  # n'accepte la forme `{nom}` qu'avec un nom simple. Avec un indice de
  # tableau, le mot est pris pour un NOM DE COMMANDE — et `exec` remplace alors
  # le shell, qui meurt sur-le-champ. Defaut mesure: le scenario de concurrence
  # ne s'executait pas du tout, sans un mot d'erreur, et le fichier se
  # declarait rouge sans dire lequel de ses controles avait echoue.
  #
  # On ferme donc le descripteur par son NUMERO, via `eval`.
  eval "exec ${HARNAIS_VERROU[1]}>&-" 2>/dev/null || true
  wait "$HARNAIS_VERROU_PID" 2>/dev/null || true
  unset HARNAIS_VERROU_PID
  HARNAIS_VERROU_TENU=0
}

# --------------------------------------------------------------------------
# REGISTRE DES BASES CREEES
# --------------------------------------------------------------------------
# `DROP OWNED BY` ne traite QUE la base courante. Le nettoyage s'executait dans
# `postgres` alors que les roles d'autorite possedent des fonctions dans les
# bases de test: le DROP echouait, l'echec etait masque par `2>/dev/null`, et
# le role survivait.
#
# Les bases sont donc inscrites, detruites AVANT les roles — ce qui emporte
# d'un coup tout ce que les roles y possedent — et la destruction est VERIFIEE.
HARNAIS_BASES_CREEES=()

creer_base() {
  local nom="$1"; shift
  psql -X -q -d postgres -v ON_ERROR_STOP=1 \
    -c "create database \"$nom\" $*" >/dev/null || return 1
  HARNAIS_BASES_CREEES+=("$nom")
  return 0
}
registre_base() { HARNAIS_BASES_CREEES+=("$1"); }

detruire_bases_creees() {
  local b echecs=0
  for b in "${HARNAIS_BASES_CREEES[@]:-}"; do
    [[ -n "$b" ]] || continue
    # Les connexions restantes empechent le DROP. On les termine d'abord, et
    # seulement sur CETTE base, nommee exactement.
    psql -X -q -d postgres -c \
      "select pg_terminate_backend(pid) from pg_stat_activity
        where datname = '$b' and pid <> pg_backend_pid();" >/dev/null 2>&1
    if ! psql -X -q -d postgres -c "drop database if exists \"$b\";" >/dev/null 2>&1; then
      echo "      ECHEC NETTOYAGE: la base « $b » n'a pas pu etre detruite" >&2
      echecs=$((echecs + 1))
    fi
  done
  return $(( echecs > 0 ))
}

# --------------------------------------------------------------------------
# POSTCONDITION DE NETTOYAGE — verifiee, jamais affirmee
# --------------------------------------------------------------------------
# « Deux executions consecutives sans residu » etait une observation du rapport
# final, pas une propriete controlee. Elle l'est ici: chaque base et chaque
# role, par son NOM EXACT, doit avoir disparu. Sinon code 3 — le decor n'est
# pas rendu, et l'execution suivante partirait d'un etat qu'on croit propre.
harnais_postcondition_nettoyage() {
  local qui="${1:-ce harnais}"; shift
  local restants=() b r
  for b in "${HARNAIS_BASES_CREEES[@]:-}"; do
    [[ -n "$b" ]] || continue
    [[ "$(psql -X -q -tA -d postgres -c \
        "select count(*) from pg_database where datname = '$b'" 2>/dev/null)" == "0" ]] \
      || restants+=("base $b")
  done
  for r in "${HARNAIS_ROLES_CREES[@]:-}" "$@"; do
    [[ -n "$r" ]] || continue
    [[ "$(psql -X -q -tA -d postgres -c \
        "select count(*) from pg_roles where rolname = '$r'" 2>/dev/null)" == "0" ]] \
      || restants+=("role $r")
  done
  if [[ ${#restants[@]} -gt 0 ]]; then
    echo "      NON EXECUTE: le nettoyage de $qui a laisse ${#restants[@]} objet(s):" >&2
    printf '              %s\n' "${restants[@]}" >&2
    echo "              L'execution suivante partirait d'un etat qu'elle" >&2
    echo "              croirait propre. Nettoyez a la main puis relancez." >&2
    return 3
  fi
  return 0
}

# --------------------------------------------------------------------------
# REGISTRE DES ROLES CREES — le seul nettoyage autorise
# --------------------------------------------------------------------------
# Aucun nettoyage par motif. `drop role ... like 'oracle_%'` emporte tout ce
# qui porte le prefixe, y compris les roles d'une execution concurrente ou
# d'un autre projet qui aurait choisi le meme mot. Le registre ne contient que
# ce que CETTE execution a cree, nom par nom.
HARNAIS_ROLES_CREES=()

registre_role() { HARNAIS_ROLES_CREES+=("$1"); }

# Cree un role ET l'inscrit au registre, dans le meme geste: un role cree sans
# etre inscrit ne serait jamais nettoye, et l'ecart entre les deux listes est
# exactement ce qu'on ne veut pas avoir a maintenir a la main.
creer_role() {
  local nom="$1"; shift
  psql -X -q -d postgres -v ON_ERROR_STOP=1 \
    -c "create role \"$nom\" $*" >/dev/null || return 1
  registre_role "$nom"
  return 0
}

# Les bases d'abord: `DROP OWNED BY` ne voit que la base courante, et un role
# qui possede une fonction dans une base de test ne peut pas etre detruit tant
# que cette base existe. L'ordre inverse echouait, et l'echec etait masque.
#
# Les echecs ne sont PLUS masques: `2>/dev/null` sur un DROP transformait
# « je n'ai pas pu nettoyer » en « rien a signaler », et le role survivait
# jusqu'a l'execution suivante — qui le prenait pour un residu etranger.
detruire_roles_crees() {
  local r echecs=0 sortie
  detruire_bases_creees || echecs=$((echecs + 1))
  # A l'envers: les roles crees en dernier peuvent dependre des precedents.
  for (( idx=${#HARNAIS_ROLES_CREES[@]}-1 ; idx>=0 ; idx-- )); do
    r="${HARNAIS_ROLES_CREES[idx]}"
    # Pas de CASCADE. `drop owned by X cascade` suit les dependances au-dela
    # des objets du role et peut emporter ce qui ne lui appartient pas. Sans
    # cascade, un objet dependant fait echouer le DROP — et c'est ce qu'on
    # veut: un diagnostic, pas une destruction silencieuse.
    psql -X -q -d postgres -c "drop owned by \"$r\";" >/dev/null 2>&1
    if ! sortie=$(psql -X -q -d postgres -c "drop role if exists \"$r\";" 2>&1); then
      echo "      ECHEC NETTOYAGE: le role « $r » n'a pas pu etre detruit" >&2
      sed 's/^/              /' <<<"$sortie" | head -3 >&2
      echecs=$((echecs + 1))
    fi
  done
  HARNAIS_ROLES_CREES=()
  return $(( echecs > 0 ))
}


# ==========================================================================
# LE DIAGNOSTIC D'INSTALLATION — LA SOURCE DE VERITE N'EST JAMAIS TRONQUEE
# ==========================================================================
# CE QUI A ETE MESURE. Douze sites de harnais rapportaient un refus
# d'installation ainsi:
#
#     grep -m1 ERROR <<<"$sortie" | cut -c1-200
#     grep -oE "AUTHORITY_[A-Z0-9_]+" <<<"$sortie" | head -4
#
# La premiere ligne est un affichage — legitime. Mais la sortie complete
# n'etait conservee NULLE PART: le tampon `$sortie` mourait avec le scenario.
# Deux mutations (B' et B=) ont ete comptees SURVIVED parce que
# `AUTHORITY_COMPOSITION_*` tombait au-dela du 200e caractere de la ligne
# ERROR, et rien ne subsistait pour contredire l'affichage. Corriger le seul
# affichage aurait recree la divergence au treizieme site: ils passent tous
# par cette fonction.
#
# LE CONTRAT
#   * la totalite de la sortie est ecrite dans un fichier de capture, sans
#     aucune coupe — c'est la source de verite;
#   * les identifiants sont extraits DE CE FICHIER, jamais d'un tampon coupe;
#   * le raccourcissement ne concerne QUE la ligne lue par un humain;
#   * le fichier est supprime au teardown, pas avant: un diagnostic detruit
#     avant d'etre lu ne vaut pas mieux qu'un diagnostic tronque.
#
# CE QU'IL NE FAIT PAS: deviner. Si aucun identifiant n'apparait, il le DIT —
# « aucun identifiant d'invariant » est une information, pas un silence.
ESC_DIAG_MOTIF='(AUTHORITY|PRECONDITION|NORMATIVE|MIGRATION|HARNAIS)_[A-Z0-9_]{4,}'
ESC_DIAG_LARGEUR=200        # affichage humain seulement
ESC_DIAG_IDS_MAX=12         # affichage humain seulement; la capture les a tous
ESC_DIAG_CAPTURE=""
ESC_DIAG_APPELS=0

esc_diag_capture_ouvrir() {
  [[ -n "$ESC_DIAG_CAPTURE" && -f "$ESC_DIAG_CAPTURE" ]] && return 0
  ESC_DIAG_CAPTURE="$(mktemp "${TMPDIR:-/tmp}/esc_diag_XXXXXXXX")" || {
    ESC_DIAG_CAPTURE=""; return 1; }
  return 0
}

# Supprime la capture. A appeler au TEARDOWN — jamais entre deux controles:
# le fichier est ce qui reste quand l'affichage a menti.
esc_diag_capture_fermer() {
  [[ -n "$ESC_DIAG_CAPTURE" ]] || return 0
  rm -f "$ESC_DIAG_CAPTURE"
  ESC_DIAG_CAPTURE=""
  return 0
}

# esc_diag_rapporter <etiquette> <sortie-integrale>
#
# N'emet PAS le « ECHEC: » — l'appelant garde son propre `echoue`, qui porte
# la comptabilite du harnais. Celle-ci n'ecrit que le corps du diagnostic.
esc_diag_rapporter() {
  local etiquette="$1" contenu="${2-}" debut ids n=0 id
  ESC_DIAG_APPELS=$((ESC_DIAG_APPELS + 1))
  if esc_diag_capture_ouvrir; then
    debut=$(( $(wc -c <"$ESC_DIAG_CAPTURE" 2>/dev/null || echo 0) + 1 ))
    printf '=== %s ===\n%s\n' "$etiquette" "$contenu" >>"$ESC_DIAG_CAPTURE"
    # L'EXTRACTION LIT LE FICHIER, PAS UN TAMPON. `tail -c +N` borne la
    # lecture a ce que CET appel vient d'ecrire: la capture est cumulative,
    # les identifiants rapportes ne le sont pas.
    ids=$(tail -c "+$debut" "$ESC_DIAG_CAPTURE" | grep -oE "$ESC_DIAG_MOTIF" | sort -u)
  else
    # Sans fichier on extrait quand meme du contenu INTEGRAL en memoire.
    # Degradation de la tracabilite, jamais de la detection.
    ids=$(grep -oE "$ESC_DIAG_MOTIF" <<<"$contenu" | sort -u)
    echo "              (capture indisponible: diagnostic en memoire seule)" >&2
  fi

  # 1. LA LIGNE HUMAINE — raccourcie, et elle seule.
  grep -m1 -iE 'ERROR|ERREUR|FATAL|REFUS' <<<"$contenu" \
    | cut -c1-"$ESC_DIAG_LARGEUR" | sed 's/^/              /' >&2

  # 2. LES IDENTIFIANTS — issus du contenu integral.
  if [[ -z "$ids" ]]; then
    echo "              aucun identifiant d'invariant dans la sortie" >&2
  else
    while IFS= read -r id; do
      [[ -n "$id" ]] || continue
      n=$((n + 1))
      if (( n <= ESC_DIAG_IDS_MAX )); then
        echo "              invariant: $id" >&2
      fi
    done <<<"$ids"
    if (( n > ESC_DIAG_IDS_MAX )); then
      echo "              ... et $(( n - ESC_DIAG_IDS_MAX )) autre(s), tous dans la capture" >&2
    fi
  fi

  # 3. OU EST LA VERITE.
  [[ -n "$ESC_DIAG_CAPTURE" ]] \
    && echo "              capture integrale: $ESC_DIAG_CAPTURE" >&2
  return 0
}


# ==========================================================================
# LE CYCLE DE VIE D'UN DECOR — le teardown s'execute sur TOUS les chemins
# ==========================================================================
# CE QUI A ETE MESURE. Dans `authority_closure.sh`, `decor_poser` rendait 1
# sur six chemins de refus — creation des trois roles, creation de la base,
# phase 0, phase 1, etat final — et AUCUN n'appelait `decor_deposer`. Un seul
# refus a l'installation laissait donc les six roles canoniques dans le
# cluster; le decor suivant echouait en « phase 0 refusee », puis tous les
# autres, et le harnais rendait « rien d'evalue » — ce qu'une campagne de
# mutation lit comme un SURVIVANT. Une contamination du scenario suivant est
# une erreur d'infrastructure, jamais une mise a mort.
#
# LE MECANISME EST DANS LA BIBLIOTHEQUE, et pas recopie dans chaque harnais,
# pour la meme raison que le diagnostic: douze recopies divergent, une seule
# se corrige.
#
#   esc_decor_ouvrir <nom> <fonction-de-teardown>
#   esc_decor_fermer                       -> teardown, UNE SEULE FOIS
#   esc_decor_abandonner [<code>]          -> teardown puis rend <code> (1)
#
# CINQ CHEMINS DE SORTIE, ET LE TEARDOWN LES COUVRE TOUS:
#   1. succes                  -> `esc_decor_fermer` explicite
#   2. erreur SQL              -> refus d'installation, `esc_decor_abandonner`
#   3. erreur shell            -> le trap EXIT du harnais appelle `fermer`
#   4. interruption            -> trap dedie TERM/INT/HUP, pose par `ouvrir`
#   5. echec DANS le teardown  -> signale, jamais avale: `ESC_DECOR_TEARDOWN_KO`
#                                 passe a 1 et le harnais sort en « non
#                                 executee », pas en « vert ».
#
# IDEMPOTENT PAR CONSTRUCTION: `fermer` appele deux fois n'execute qu'un
# teardown. Sans cela le trap EXIT redetruirait un decor deja rendu et le
# second passage rapporterait des echecs de nettoyage imaginaires.
ESC_DECOR_NOM=""
ESC_DECOR_TEARDOWN=""
ESC_DECOR_ARME=0
ESC_DECOR_TEARDOWN_KO=0
ESC_DECOR_FERMETURES=0

esc_decor_ouvrir() {       # esc_decor_ouvrir <nom> <fonction>
  local nom="${1:?usage: esc_decor_ouvrir <nom> <fonction>}"
  local fn="${2:?usage: esc_decor_ouvrir <nom> <fonction>}"
  if ! declare -F "$fn" >/dev/null 2>&1; then
    echo "REFUS: « $fn » n'est pas une fonction: le teardown ne serait" >&2
    echo "       jamais execute, et le decor « $nom » fuirait." >&2
    return 2
  fi
  if (( ESC_DECOR_ARME )); then
    # Un decor ouvert par-dessus un autre masquerait le teardown du premier.
    echo "REFUS: le decor « $ESC_DECOR_NOM » est encore ouvert." >&2
    return 2
  fi
  ESC_DECOR_NOM="$nom"; ESC_DECOR_TEARDOWN="$fn"; ESC_DECOR_ARME=1
  # SON PROPRE TRAP. Il ne remplace pas le trap EXIT du harnais: il s'ajoute,
  # rend le decor, puis sort avec le code conventionnel du signal.
  trap 'trap "" TERM INT HUP; esc_decor_fermer; exit 143' TERM
  trap 'trap "" TERM INT HUP; esc_decor_fermer; exit 130' INT
  trap 'trap "" TERM INT HUP; esc_decor_fermer; exit 129' HUP
  return 0
}

esc_decor_fermer() {
  (( ESC_DECOR_ARME )) || return 0
  local fn="$ESC_DECOR_TEARDOWN" nom="$ESC_DECOR_NOM"
  # DESARME D'ABORD: si le teardown lui-meme echoue ou est interrompu, on ne
  # le relance pas en boucle depuis son propre trap.
  ESC_DECOR_ARME=0; ESC_DECOR_TEARDOWN=""; ESC_DECOR_NOM=""
  ESC_DECOR_FERMETURES=$((ESC_DECOR_FERMETURES + 1))
  if ! "$fn"; then
    ESC_DECOR_TEARDOWN_KO=1
    echo "      ECHEC NETTOYAGE: le teardown du decor « $nom » a echoue." >&2
    echo "              L'execution suivante partirait d'un etat qu'elle" >&2
    echo "              croirait propre." >&2
  fi
  harnais_piege_signaux
  return 0
}

# Le chemin de refus: rend le decor PUIS le code d'echec, en un seul geste,
# pour qu'aucun `return 1` ne puisse a nouveau oublier le teardown.
esc_decor_abandonner() {
  local code="${1:-1}"
  esc_decor_fermer
  return "$code"
}


# ==========================================================================
# LA COMPTABILITE DES VERDICTS — un statut UNIQUE par controle declare
# ==========================================================================
# CE QUI A ETE MESURE, ET QUI EST CORRIGE ICI. `authority_root_of_trust.sh`
# comptait des APPELS, pas des controles: son attaque 10 bouclait sur `update`
# puis `delete` et emettait DEUX verdicts. Quatorze attaques rendaient donc
# « 4 rouges et 11 sures » — quinze. L'arithmetique le disait a chaque
# execution, et personne ne l'avait lue.
#
# UN COMPTEUR QUI PEUT MENTIR SUR SON PROPRE TOTAL N'ATTESTE RIEN DU PRODUIT.
# La comptabilite est donc structurelle, et partagee: un harnais ecrit demain
# ne peut pas redemarrer la meme derive dans son coin.
#
#   * les controles sont DECLARES d'avance — `verdicts_declarer 1 2 3 ...`;
#   * `verdict <id> <ROUGE|SUR|NON_PARCOURU> <texte>` en enregistre UN, et un
#     seul: un second verdict pour le meme id est lui-meme une faute;
#   * un controle declare qui ne rend aucun verdict est une faute;
#   * un verdict pour un controle non declare est une faute;
#   * et l'egalite est VERIFIEE en fin de course:
#
#         declares == executes == rouges + surs + non_parcourus
#
# Aucune de ces fautes n'est un avertissement: chacune force la sortie en
# echec. Une sous-observation se COMBINE en un verdict unique avant d'etre
# enregistree — c'est au harnais de trancher, pas au compteur de deviner.
#
# TROIS STATUTS, ET LEUR SENS EXACT
#   ROUGE         l'attaque a ABOUTI. L'invariant vise n'est pas defendu.
#   SUR           elle a ete REFUSEE, et le refus est attribue a la protection
#                 visee — jamais a une autre.
#   NON_PARCOURU  le chemin n'a pas ete ATTEINT. Ni rouge, ni assurance: un
#                 trou. C'est la lecon de 6.3b6e — une surface non executee
#                 n'est pas un verdict.
VERDICTS_DECLARES=()
declare -A VERDICTS=()
VERDICTS_KO=0
VERDICTS_ROUGES=0; VERDICTS_SURS=0; VERDICTS_NON_PARCOURUS=0
VERDICTS_EXECUTES=0

verdicts_declarer() { VERDICTS_DECLARES=("$@"); }

verdict_faute() {
  echo "      FAUTE DE COMPTABILITE: $*" >&2
  VERDICTS_KO=1
}

verdict() {                # verdict <id> <statut> <texte...>
  local id="$1" statut="$2"; shift 2
  local connu=0 x
  for x in "${VERDICTS_DECLARES[@]}"; do [[ "$x" == "$id" ]] && connu=1; done
  if (( ! connu )); then
    verdict_faute "verdict rendu pour « $id », qui n'est pas declare."
    return 1
  fi
  if [[ -n "${VERDICTS[$id]:-}" ]]; then
    verdict_faute "second verdict pour « $id » (« ${VERDICTS[$id]} » puis « $statut »)."
    return 1
  fi
  VERDICTS[$id]="$statut"
  case "$statut" in
    ROUGE)        echo "      ROUGE: $*" ;;
    SUR)          echo "      deja sur: $*" ;;
    NON_PARCOURU) echo "      NON PARCOURU: $*" >&2 ;;
    *) verdict_faute "statut « $statut » inconnu pour « $id »"; return 1 ;;
  esac
  return 0
}

verdicts_verifier() {
  local id
  VERDICTS_ROUGES=0; VERDICTS_SURS=0; VERDICTS_NON_PARCOURUS=0; VERDICTS_EXECUTES=0
  for id in "${VERDICTS_DECLARES[@]}"; do
    case "${VERDICTS[$id]:-}" in
      ROUGE)        VERDICTS_ROUGES=$((VERDICTS_ROUGES + 1)) ;;
      SUR)          VERDICTS_SURS=$((VERDICTS_SURS + 1)) ;;
      NON_PARCOURU) VERDICTS_NON_PARCOURUS=$((VERDICTS_NON_PARCOURUS + 1)) ;;
      "") verdict_faute "« $id » est declare mais n'a rendu AUCUN verdict."; continue ;;
    esac
    VERDICTS_EXECUTES=$((VERDICTS_EXECUTES + 1))
  done
  local total=$(( VERDICTS_ROUGES + VERDICTS_SURS + VERDICTS_NON_PARCOURUS ))
  if (( ${#VERDICTS_DECLARES[@]} != VERDICTS_EXECUTES )); then
    verdict_faute "declares=${#VERDICTS_DECLARES[@]} != executes=$VERDICTS_EXECUTES"
  fi
  if (( VERDICTS_EXECUTES != total )); then
    verdict_faute "executes=$VERDICTS_EXECUTES != rouges+surs+non_parcourus=$total"
  fi
  return $VERDICTS_KO
}

verdicts_resume() {        # verdicts_resume <titre>
  local id
  echo ""
  echo "      statut de chacun des ${#VERDICTS_DECLARES[@]} controles declares:"
  for id in "${VERDICTS_DECLARES[@]}"; do
    printf '                %-28s %s\n' "$id" "${VERDICTS[$id]:-<AUCUN VERDICT>}"
  done
  echo ""
  echo "================================================="
  echo " ${1:-controles}:"
  echo "   declares            ${#VERDICTS_DECLARES[@]}"
  echo "   executes            $VERDICTS_EXECUTES"
  echo "   dont rouges         $VERDICTS_ROUGES"
  echo "   dont surs           $VERDICTS_SURS"
  echo "   dont non parcourus  $VERDICTS_NON_PARCOURUS"
  if (( VERDICTS_KO )); then
    echo "   ARITHMETIQUE INVALIDE — voir les fautes de comptabilite ci-dessus"
  else
    echo "   invariant tenu: declares == executes == rouges + surs + non_parcourus"
  fi
  echo "================================================="
}
