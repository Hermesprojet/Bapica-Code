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
exiger_cluster_jetable() {
  local qui="${1:-ce harnais}"
  local attendu='oui-cluster-jetable-et-isole'
  local n

  # 1. L'INTENTION, declaree, avec un jeton exact. Pas « 1 », pas « true »: une
  #    valeur qu'on ne pose pas par reflexe ni par copie d'un autre projet.
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

  # 2. LA BOUCLE LOCALE. Un cluster jetable est local au conteneur de test. Une
  #    declaration ne doit pas pouvoir emporter le script sur un hote distant.
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

detruire_roles_crees() {
  local r
  # A l'envers: les roles crees en dernier peuvent dependre des precedents.
  for (( idx=${#HARNAIS_ROLES_CREES[@]}-1 ; idx>=0 ; idx-- )); do
    r="${HARNAIS_ROLES_CREES[idx]}"
    # Pas de CASCADE. `drop owned by X cascade` suit les dependances au-dela
    # des objets du role et peut emporter ce qui ne lui appartient pas. Sans
    # cascade, un objet dependant fait echouer le DROP — et c'est ce qu'on
    # veut: un diagnostic, pas une destruction silencieuse.
    psql -X -q -d postgres -c "drop owned by \"$r\";" >/dev/null 2>&1
    psql -X -q -d postgres -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
  HARNAIS_ROLES_CREES=()
}
