#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b6d: LE CONTRAT DU SCEAU
#
#   seal_contract.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `authority_closure.sh` etablit que le migrateur est CONTENU. Il ne dit rien
# de la question suivante, qui est celle de l'exploitation: la racine de
# confiance est-elle DEPLOYABLE — separee du jeu de migrations, versionnee,
# reexecutable, et honnete sur ce qu'elle garantit ?
#
# Cinq affirmations sont mises a l'epreuve. Elles ne portent pas sur des
# fonctionnalites normatives: elles portent sur la frontiere entre le plan de
# controle et le migrateur, et sur ce que le systeme DIT de lui-meme.
#
#   H. LA FRONTIERE DE PHASE est structurelle, pas conventionnelle
#   I. LE SCEAU EST VERSIONNE et sa reexecution est definie
#   J. LE POSEUR DU SCEAU est celui qui finalise
#   K. IL N'EXISTE QU'UNE SEULE ENTREE PUBLIQUE MUTANTE
#   M. LE NIVEAU D'ASSURANCE survit a la console
#
# La restauration inter-cluster — le sixieme point — demande un SECOND CLUSTER
# et vit dans `cross_cluster_restore.sh`.
#
# POURQUOI CES CINQ, ET PAS D'AUTRES. Chacune est une phrase que le depot
# affirme aujourd'hui — dans un commentaire, dans le modele de menace ou dans
# le runbook — et qu'aucune surface ne verifie. Une affirmation non verifiee
# n'est pas une garantie: c'est une intention.
#
# Toutes les identites sont FICTIVES. Aucune confirmation normative reelle
# n'est creee.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e): les harnais
# l'empruntent AUSSI, sans quoi ils testeraient un chemin que la
# production n'emprunte pas.
# shellcheck source=../apply_migration.sh
source "$HERE/../apply_migration.sh"

PREFIXE="${1:?usage: seal_contract.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "seal_contract.sh" || exit 2
# LE CONSENTEMENT AVANT LE VERROU, et non l'inverse. `exiger_cluster_jetable`
# ne lit qu'une variable d'environnement: rien ne justifie de detenir le verrou
# pendant ce controle. Mesure faite en ecrivant ce fichier — dans l'ordre
# inverse, un refus de consentement sortait AVANT que le piege EXIT ne soit
# arme, et laissait le verrou detenu par une session psql orpheline: la
# relance suivante annoncait « une autre execution est en cours » alors
# qu'aucune ne l'etait.
exiger_cluster_jetable  "seal_contract.sh" || exit 2
harnais_verrou_prendre  "seal_contract.sh" || exit $?
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"

CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment)

exiger_roles_absents "seal_contract.sh" "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

KO=0; ROUGES=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
# `rouge` OUVRE un constat et compte UN scenario; `detail` le prolonge sans
# rien compter. Une premiere version comptait les LIGNES: dix scenarios rouges
# etaient annonces « 41 ouvertures a fermer », un chiffre qui ne correspondait
# a rien de denombrable et qui aurait varie a la moindre reformulation.
rouge()  { echo "      ROUGE ATTENDU (a fermer): $*"; ROUGES=$((ROUGES + 1)); }
detail() { echo "                                $*"; }

adm() { psql -X -q -d postgres "$@"; }

# --------------------------------------------------------------------------
# OU EST LE SCEAU
# --------------------------------------------------------------------------
# `HARNAIS_SCEAU` vient de `lib_harnais.sh`: un seul endroit du depot connait
# ce chemin. La version ROUGE de ce fichier resolvait elle-meme les deux
# emplacements possibles, parce que le sceau n'avait pas encore demenage; ce
# n'est plus necessaire, et redire un chemin, c'est le desynchroniser.
SCEAU="$HARNAIS_SCEAU"
if [[ ! -f "$SCEAU" ]]; then
  echo "      ECHEC: le sceau est introuvable ($SCEAU)" >&2
  harnais_verrou_rendre
  exit 2
fi

# LES MIGRATIONS DE PHASE 1 — celles que le MIGRATEUR applique. Aujourd'hui la
# liste doit exclure le sceau; apres H1 elle n'aura plus rien a exclure, parce
# que le sceau ne sera plus dans le repertoire.
migrations_de_phase_1() {
  local f
  for f in "$DB_DIR"/migrations/*.sql; do
    [[ "$f" == "$SCEAU" ]] && continue
    echo "$f"
  done
}

# --------------------------------------------------------------------------
# LE DECOR
# --------------------------------------------------------------------------
# Trois acteurs, aucun superutilisateur — la forme Supabase:
#   <p>_m<s>  migrateur         proprietaire de la base, CREATEROLE, CREATEDB
#   <p>_c<s>  plan de controle  pose le sceau, finalise
#   <p>_g<s>  delegue           recoit des capacites, tente de finaliser (J)
#
# Les suffixes sont en MINUSCULES: PostgreSQL replie les identifiants non
# quotes, et une connexion PGUSER=pAmig echouerait sur « role does not exist ».
MIG=""; CTL=""; DEL=""; BASE=""; MDP=""
mig()   { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()   { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
del()   { PGUSER="$DEL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
delp()  { PGUSER="$DEL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
admb()  { psql -X -q -d "$BASE" "$@"; }

# `decor_roles <suffixe>` — les trois acteurs et la base, sans phase 0 ni 1.
decor_roles() {
  local s="$1"
  MIG="${PREFIXE}_m${s}_${JETON}"
  CTL="${PREFIXE}_c${s}_${JETON}"
  DEL="${PREFIXE}_g${s}_${JETON}"
  BASE="${PREFIXE}_d${s}_${JETON}"
  MDP="FICTIF-sc-${s}-${JETON}"

  creer_role "$MIG" "login password '$MDP' createrole createdb" \
    || { echoue "decor $s: creation du migrateur impossible"; return 1; }
  creer_role "$CTL" "login password '$MDP' createrole" \
    || { echoue "decor $s: creation du plan de controle impossible"; return 1; }
  creer_role "$DEL" "login password '$MDP' createrole" \
    || { echoue "decor $s: creation du delegue impossible"; return 1; }
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
  adm -c "grant \"$DEL\" to ${PGUSER:-postgres};" >/dev/null 2>&1

  creer_base "$BASE" "owner \"$MIG\"" \
    || { echoue "decor $s: creation de la base impossible"; return 1; }
  registre_base "$BASE"

  admb -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
-- LE POSEUR DU SCEAU cree des objets dans `public` et les transfere a
-- l'activateur: CREATE avec GRANT OPTION. Prerequis de deploiement, voir
-- docs/DEPLOIEMENT_PREREQUIS.md.
grant create on schema public to "$CTL" with grant option;
grant create on schema public to "$DEL" with grant option;
grant usage on schema auth to "$CTL";
grant usage on schema auth to "$DEL";
SQL
  adm -c "alter database \"$BASE\"
            set eurostruct.approved_deployment_roles = '$MIG,$CTL,$DEL';" >/dev/null 2>&1
  adm -c "alter database \"$BASE\"
            set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
  return 0
}

# `decor_phase_1 <suffixe>` — applique la phase 1 sous le migrateur.
decor_phase_1() {
  local s="$1" f sortie
  while read -r f; do
    if ! esc_appliquer_migration "$f" mig; then
      sortie="$ESC_MIGRATION_SORTIE"
      echoue "decor $s: phase 1 refusee sur $(basename "$f"):"
      grep -m1 ERROR <<<"$sortie" | cut -c1-200 | sed 's/^/              /' >&2
      return 1
    fi
  done < <(migrations_de_phase_1)
  return 0
}

# `decor_poser <suffixe>` — decor COMPLET et LEGITIME: le plan de controle pose
# le sceau, prete les deux roles d'autorite au migrateur, phase 1, PENDING.
decor_poser() {
  local s="$1" sortie etat
  decor_roles "$s" || return 1

  if ! sortie=$(ctl -v ON_ERROR_STOP=1 -f "$SCEAU" 2>&1); then
    echoue "decor $s: phase 0 refusee:"
    grep -m1 ERROR <<<"$sortie" | cut -c1-200 | sed 's/^/              /' >&2
    return 1
  fi
  adm -c "grant eurostruct_deployment to \"$CTL\" with inherit true;" >/dev/null 2>&1
  ctlp -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
  decor_phase_1 "$s" || return 1

  etat=$(ctl -tAc "select normative_activation_state()" 2>&1)
  if [[ "$etat" != "PENDING" ]]; then
    echoue "decor $s: phase 1 ne se termine pas en PENDING (obtenu: $etat)"
    return 1
  fi
  return 0
}

decor_deposer() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$DEL"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
}

NETTOYAGE_KO=0
TOUS_ROLES=()
suivre_decor() { TOUS_ROLES+=("$MIG" "$CTL" "$DEL"); }
sortie_propre() {
  local r
  decor_deposer
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS_ROLES[@]}"; do
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "seal_contract.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS_ROLES[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    contrat du sceau: la racine est-elle deployable ?"

# ==========================================================================
# H. LA FRONTIERE DE PHASE EST STRUCTURELLE, PAS CONVENTIONNELLE
# ==========================================================================
# LE DEFAUT, TEL QU'IL ETAIT. Le sceau vivait dans le repertoire des
# migrations. Tout outil standard — un migrateur du commerce, un script de
# deploiement, une boucle `psql -f` — parcourt ce repertoire et l'aurait
# applique SOUS LE MIGRATEUR, c'est-a-dire aurait pose la racine de confiance a
# la portee de celui qu'elle doit contenir.
#
# Ce qui l'en empechait etait une ligne de bash, repetee dans chaque appelant,
# qui comparait le nom du fichier et sautait. Cinq appelants la portaient; un
# sixieme — `role_prerequisites.sh` — l'avait oubliee, et appliquait le
# repertoire entier sous un acteur unique.
#
# Une frontiere de confiance qui depend de la vigilance de chaque appelant
# n'est pas une frontiere: c'est une convention, et les conventions s'oublient.
# C'est maintenant la frontiere des REPERTOIRES, et ces trois controles la
# tiennent.

# --- H1. le repertoire des migrations ne contient pas la racine ------------
# LE CONTROLE PORTE SUR LE CONTENU, pas sur le nom du fichier. Renommer le
# fichier suffirait a satisfaire un controle nominal sans rien deplacer.
#
# La racine de confiance se reconnait a ce qu'elle CREE: les six roles
# canoniques et les tables de confiance possedees par l'activateur.
RACINE_DANS_MIGRATIONS=()
for f in "$DB_DIR"/migrations/*.sql; do
  if grep -qE "create role eurostruct_normative_activator" "$f" \
     || grep -qE "^create table normative_control_plane" "$f"; then
    RACINE_DANS_MIGRATIONS+=("$(basename "$f")")
  fi
done
if [[ ${#RACINE_DANS_MIGRATIONS[@]} -eq 0 ]]; then
  echo "      ok: H1. aucune migration du jeu standard ne contient la racine"
else
  rouge "H1. la racine de confiance est dans le jeu standard des migrations:"
  detail "    ${RACINE_DANS_MIGRATIONS[*]}"
  detail "    Un outil qui applique « migrations/*.sql » sous le migrateur pose"
  detail "    donc la racine SOUS LE MIGRATEUR — exactement ce que 6.3b6c a"
  detail "    ferme, rouvert par la disposition des fichiers."
fi

# --- H2. aucun script n'a besoin d'ignorer specialement un fichier ---------
# Le motif cherche est l'idiome d'exclusion PAR LE NOM: un `basename` compare a
# un motif, suivi d'un `continue`. Tant qu'un seul appelant doit le porter, la
# frontiere reste conventionnelle.
#
# LES LIGNES DE COMMENTAIRE SONT EXCLUES, et c'est necessaire: ce fichier
# lui-meme decrit l'idiome quelques lignes plus haut pour expliquer ce qui a ete
# ferme. Un controle qu'une explication suffit a faire rougir ne serait pas
# tenable — on cesserait d'expliquer.
EXCLUSIONS=$(grep -rn --include='*.sh' --include='*.py' \
               -E '^[^#]*\bbasename\b[^#]*\bcontinue\b' \
               "$DB_DIR" "$RACINE/tools" "$RACINE/run_tests.sh" \
               2>/dev/null | cut -d: -f1 | sed "s#^$RACINE/##" | sort -u | tr '\n' ' ')
if [[ -z "$EXCLUSIONS" ]]; then
  echo "      ok: H2. aucun script n'exclut une migration par son nom"
else
  rouge "H2. des scripts doivent ignorer specialement le fichier du sceau:"
  detail "    $EXCLUSIONS"
  detail "    La frontiere de confiance ne doit pas dependre de la presence"
  detail "    d'un « continue » dans chaque appelant."
fi

# --- H3. le fichier du plan de controle a son propre repertoire ------------
if [[ -f "$DB_DIR/control_plane/0001_normative_seal.sql" ]]; then
  echo "      ok: H3. le sceau vit dans db/control_plane/"
else
  rouge "H3. il n'existe pas de repertoire de plan de controle."
  detail "    Le sceau est en $(sed "s#^$RACINE/##" <<<"$SCEAU"), c'est-a-dire"
  detail "    dans le repertoire que le migrateur parcourt."
fi

# --- H4. phase 1 SANS sceau: un refus nomme, avant toute ecriture ----------
# Cette garantie EXISTE deja (6.3b6c): 0010 verifie le sceau. Elle est ecrite
# ici parce qu'elle doit SURVIVRE au deplacement — et parce que rien ne la
# verifiait: une regression l'aurait retiree sans qu'aucune surface ne bouge.
if ! decor_roles h; then
  echoue "le decor H n'a pas pu etre pose: H4 n'est pas evalue"
else
suivre_decor
SORTIE_H4=$(
  while read -r f; do
    esc_appliquer_migration "$f" mig || { echo "$ESC_MIGRATION_SORTIE"; break; }
  done < <(migrations_de_phase_1)
)
if grep -qF "le sceau normatif est absent ou incomplet" <<<"$SORTIE_H4"; then
  # ET AVANT TOUTE ECRITURE NORMATIVE: la surface de confirmation ne doit pas
  # exister. Si elle existait, le refus serait arrive trop tard.
  RESTES=$(admb -tAc "select count(*) from pg_class
                       where relname in ('normative_rule_confirmations',
                                         'normative_authorisation_grants')" 2>&1)
  if [[ "$RESTES" == "0" ]]; then
    echo "      ok: H4. phase 1 sans sceau: refus nomme, aucune surface normative"
  else
    rouge "H4. la phase 1 sans sceau a refuse, mais APRES avoir cree $RESTES"
    detail "    table(s) normative(s). Le refus arrive trop tard."
  fi
else
  rouge "H4. la phase 1 appliquee sans sceau ne produit pas de refus nomme:"
  detail "    $(grep -m1 -E 'ERROR|FATAL' <<<"$SORTIE_H4" | cut -c1-160)"
fi
decor_deposer
fi

# ==========================================================================
# I. LE SCEAU EST VERSIONNE ET SA REEXECUTION EST DEFINIE
# ==========================================================================
# Quatre noms de tables, un proprietaire et FORCE RLS: c'est tout ce que la
# phase 1 verifie aujourd'hui. Cela ne dit pas QUELLE racine est en place.
#
# Une phase 0 d'une version anterieure — ou une racine fabriquee qui presente
# les memes quatre noms — passe le controle a l'identique. Et le jour ou ces
# 2000 lignes evolueront, rien ne distinguera une base scellee par la nouvelle
# version d'une base scellee par l'ancienne.
# --- I2. la phase 1 exige une version -------------------------------------
# LE CONTROLE EST COMPORTEMENTAL, et il a d'abord ete ecrit en `grep`: « le
# texte de la phase 1 contient-il SEAL_VERSION_MISMATCH ? ». Cela ne prouve
# rien — un message peut exister sans qu'aucun chemin ne l'atteigne, ce qui est
# exactement le defaut que le scenario G d'`authority_closure.sh` avait.
#
# On pose donc un sceau qui declare une AUTRE version, sur une base neuve, et
# on demande a la phase 1 de s'appliquer dessus. La copie modifiee ne vit que
# le temps du scenario; elle n'est jamais ecrite dans le depot.
SCEAU_AUTRE="$(mktemp "/tmp/${PREFIXE}_sceau_v9.XXXXXX.sql")"
sed 's#esc-normative-seal/1#esc-normative-seal/9-FICTIF#g' "$SCEAU" >"$SCEAU_AUTRE"
if ! grep -qF 'esc-normative-seal/9-FICTIF' "$SCEAU_AUTRE"; then
  echoue "I2. la version n'a pas pu etre substituee; le scenario n'est pas evalue"
elif ! decor_roles i2; then
  echoue "I2. le decor n'a pas pu etre pose"
else
  suivre_decor
  if ! SORTIE_I2=$(ctl -v ON_ERROR_STOP=1 -f "$SCEAU_AUTRE" 2>&1); then
    echoue "I2. la phase 0 en version 9-FICTIF a refuse: $(grep -m1 ERROR <<<"$SORTIE_I2" | cut -c1-140)"
  else
    ctlp -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
    SORTIE_I2B=$(
      while read -r f; do
        esc_appliquer_migration "$f" mig || { echo "$ESC_MIGRATION_SORTIE"; break; }
      done < <(migrations_de_phase_1)
    )
    if grep -qF "SEAL_VERSION_MISMATCH" <<<"$SORTIE_I2B"; then
      echo "      ok: I2. la phase 1 refuse un sceau d'une autre version"
    else
      rouge "I2. la phase 1 s'applique sur un sceau de version « 9-FICTIF »."
      detail "    Quatre tables aux bons noms suffisent: une racine d'une version"
      detail "    anterieure — ou fabriquee — passe le controle a l'identique."
      detail "    $(grep -m1 -E 'ERROR|FATAL' <<<"$SORTIE_I2B" | cut -c1-150)"
    fi
  fi
  decor_deposer
fi
rm -f "$SCEAU_AUTRE"

if ! decor_poser i; then
  echoue "le decor I n'a pas pu etre pose: les scenarios I ne sont pas evalues"
else
suivre_decor
echo "      ok: decor I — sceau pose par « $CTL », phase 1 par « $MIG », PENDING"

# --- I1. le sceau porte son identite --------------------------------------
META=$(admb -tAc "select count(*) from pg_class c join pg_roles o on o.oid = c.relowner
                   where c.relname = 'normative_seal_metadata'
                     and o.rolname = 'eurostruct_normative_activator'
                     and c.relrowsecurity and c.relforcerowsecurity" 2>&1)
if [[ "$META" == "1" ]]; then
  echo "      ok: I1. normative_seal_metadata existe, activateur, RLS forcee"
else
  rouge "I1. il n'existe aucune table de metadonnees du sceau."
  detail "    Rien ne dit QUELLE version de la racine est en place, ni QUI l'a"
  detail "    posee, ni sous quel niveau d'assurance."
fi


# --- I3. reexecution stricte du sceau -------------------------------------
# LA REEXECUTION EST UN FAIT D'EXPLOITATION, pas une hypothese: un deploiement
# interrompu, un pipeline rejoue, un operateur qui doute. Ce qu'elle doit
# produire est DECIDE — succes idempotent nomme, ou refus propre — et surtout
# SANS MUTATION PARTIELLE.
AVANT_I3=$(admb -tAc "select count(*) from pg_class where relname like 'normative%'" 2>&1)
SORTIE_I3=$(ctl -v ON_ERROR_STOP=1 -f "$SCEAU" 2>&1); CODE_I3=$?
APRES_I3=$(admb -tAc "select count(*) from pg_class where relname like 'normative%'" 2>&1)
if grep -qF "SEAL_ALREADY_INSTALLED" <<<"$SORTIE_I3"; then
  if [[ "$AVANT_I3" == "$APRES_I3" ]]; then
    echo "      ok: I3. reexecution: SEAL_ALREADY_INSTALLED, aucune mutation"
  else
    rouge "I3. la reexecution refuse proprement mais a mute la base"
    detail "    ($AVANT_I3 -> $APRES_I3 objets normatifs)."
  fi
else
  rouge "I3. la reexecution stricte du sceau n'a pas de semantique definie."
  detail "    Obtenu (code $CODE_I3): $(grep -m1 -E 'ERROR|FATAL' <<<"$SORTIE_I3" | cut -c1-140)"
  detail "    C'est une erreur brute de PostgreSQL, au milieu du fichier — donc"
  detail "    APRES que les blocs precedents ont deja agi."
fi

# --- I4. sceau PARTIEL: fail-closed ---------------------------------------
# Une phase 0 interrompue laisse une racine incomplete. Ce qui est exige n'est
# pas qu'elle se repare: c'est qu'elle REFUSE, des deux cotes — la phase 0
# comme la phase 1 — au lieu de completer un sceau dont personne ne sait plus
# quelle version il porte.
admb -v ON_ERROR_STOP=1 -c \
  "drop table if exists normative_finalization_intent cascade;" >/dev/null 2>&1
SORTIE_I4=$(ctl -v ON_ERROR_STOP=1 -f "$SCEAU" 2>&1)
if grep -qE "SEAL_PARTIAL|sceau (est )?(partiel|incomplet)" <<<"$SORTIE_I4"; then
  echo "      ok: I4. sceau partiel: la phase 0 refuse en le nommant"
else
  rouge "I4. sur un sceau PARTIEL, la phase 0 ne produit pas de refus nomme:"
  detail "    $(grep -m1 -E 'ERROR|FATAL' <<<"$SORTIE_I4" | cut -c1-140)"
  detail "    Une racine a moitie posee doit etre un refus fail-closed, jamais"
  detail "    une reparation silencieuse."
fi
decor_deposer
fi

# ==========================================================================
# J. LE POSEUR DU SCEAU EST CELUI QUI FINALISE
# ==========================================================================
# L'identite du plan de controle est DERIVEE du grantor des emprunts, au moment
# de la finalisation. Le sceau, lui, n'enregistre pas qui l'a pose.
#
# CONSEQUENCE MESUREE: A pose la racine, puis A est efface — l'administrateur
# lui retire son ADMIN residuel, ce qui est une operation legitime et
# documentee, les six roles pouvant PREEXISTER. B recoit les capacites, prete
# au migrateur, finalise. B devient le plan de controle du sceau de A, sans
# qu'aucun evenement ne soit inscrit nulle part.
#
# CE N'EST PAS UNE DELEGATION INTERDITE PAR PRINCIPE. C'est une delegation
# SILENCIEUSE: si l'exploitation veut transferer le plan de controle, ce doit
# etre un evenement explicite et audite, pas la consequence indirecte d'un
# GRANT.
if ! decor_roles j; then
  echoue "le decor J n'a pas pu etre pose: J n'est pas evalue"
else
suivre_decor
# LES SIX ROLES PREEXISTENT, crees par l'administrateur. C'est la forme que le
# sceau documente lui-meme (« Ils peuvent PREEXISTER »), et c'est elle qui rend
# le contre-exemple atteignable: A ne sera pas le createur des roles, donc son
# ADMIN residuel sera revocable par son donneur (fait F3).
adm -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
create role normative_backend;
create role normative_governance;
create role eurostruct_normative_writer nologin;
create role eurostruct_normative_bootstrap nologin;
create role eurostruct_normative_activator nologin;
create role eurostruct_deployment nologin;
grant eurostruct_normative_activator to "$CTL" with admin option, set false, inherit false;
SQL
SORTIE_J=$(ctl -v ON_ERROR_STOP=1 -f "$SCEAU" 2>&1)
if [[ $? -ne 0 ]]; then
  echoue "decor J: phase 0 refusee: $(grep -m1 ERROR <<<"$SORTIE_J" | cut -c1-160)"
else
  # A EST EFFACE: son donneur lui retire l'ADMIN residuel.
  adm -c "revoke admin option for eurostruct_normative_activator from \"$CTL\";" >/dev/null 2>&1
  # B RECOIT LES CAPACITES et prete au migrateur.
  adm -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$DEL" with admin option, set false, inherit false;
grant eurostruct_normative_bootstrap to "$DEL" with admin option, set false, inherit false;
grant eurostruct_deployment to "$DEL" with inherit true;
SQL
  delp -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
  if decor_phase_1 j; then
    MANIF_J=$(del -tAc "select normative_settings_manifest()" 2>&1)
    SORTIE_J2=$(del -tAc "select normative_finalize_deployment('$MANIF_J')" 2>&1)
    ETAT_J=$(del -tAc "select normative_activation_state()" 2>&1)
    PLAN_J=$(admb -tAc "select role_name from normative_control_plane" 2>&1)
    if [[ "$ETAT_J" == "PENDING" ]] \
       && grep -qE "SEAL_INSTALLER_MISMATCH|n'a pas pose le sceau|poseur du sceau" \
                <<<"$SORTIE_J2"; then
      echo "      ok: J. un tiers ne finalise pas le sceau d'un autre"
    elif [[ "$ETAT_J" == "ACTIVE" ]]; then
      rouge "J. « $DEL » a finalise le sceau pose par « $CTL »."
      detail "   Etat: $ETAT_J. Plan de controle fige: « $PLAN_J »."
      detail "   Le sceau n'enregistre pas son poseur, et la finalisation ne le"
      detail "   demande pas: le plan de controle se transfere par un GRANT."
    else
      rouge "J. la finalisation par un tiers a echoue, mais PAS sur l'identite"
      detail "   du poseur: $(grep -m1 ERROR <<<"$SORTIE_J2" | cut -c1-150)"
      detail "   Un refus obtenu par une autre barriere ne ferme pas ce defaut:"
      detail "   il le masque tant que cette autre barriere tient."
    fi
  fi
fi
decor_deposer
fi

# ==========================================================================
# K. LA SURFACE MUTANTE, ET CE QU'ELLE PERMET EXACTEMENT
# ==========================================================================
# LE MODELE DE MENACE AFFIRMAIT: « une seule entree publique mutante,
# normative_finalize_deployment(manifeste_attendu) ». C'ETAIT FAUX.
# `normative_prepare_activation()` et `normative_record_activation()` sont
# executables par `eurostruct_deployment`, et se composent DANS UNE SEULE
# transaction sous un verrou que l'appelant prend lui-meme. 6.3b6c avait ferme
# la composition en PLUSIEURS transactions, pas celle-ci.
#
# POURQUOI L'INTEGRATION PREFEREE EST IMPOSSIBLE — mesure, PostgreSQL 16.
#
# Fermer l'API demanderait que `normative_finalize_deployment` fasse elle-meme
# les ecritures, donc qu'elle soit SECURITY DEFINER possedee par l'activateur.
# Or elle doit AUSSI executer les REVOKE des emprunts, et PostgreSQL n'accorde
# d'effet a un REVOKE que s'il est exerce par le DONNEUR de l'octroi:
#
#     set role t_admin;                      -- ADMIN OPTION sur t_cible
#     revoke t_cible from t_membre;
#     WARNING: role "t_membre" has not been granted membership in role
#              "t_cible" by role "t_admin"          -> sans effet
#
#     revoke t_cible from t_membre granted by t_donneur;
#     ERROR: permission denied to revoke privileges granted by role "t_donneur"
#     DETAIL: Only roles with privileges of role "t_donneur" may revoke
#             privileges granted by this role.
#
# Une seule transaction ne peut donc pas etre a la fois l'ACTIVATEUR (pour
# ecrire la racine) et le DONNEUR (pour que les revocations prennent), sauf a
# etre superutilisateur — c'est-a-dire hors du modele.
#
# CE QUI EST FAIT A LA PLACE, ET QUI EST LA SECONDE ISSUE ACCEPTABLE:
#
#   * l'affirmation est CORRIGEE dans le modele de menace — une entree
#     orchestratrice supportee, deux primitives de bas niveau reservees au role
#     de deploiement;
#   * et la propriete qui compte vraiment est ETABLIE PAR L'EXPERIENCE: les
#     primitives ne permettent AUCUN etat que le finaliseur ne permette.
#
# Ce qui serait grave, ce n'est pas que deux chemins existent: c'est qu'un
# chemin donne plus que l'autre.
if ! decor_poser k; then
  echoue "le decor K n'a pas pu etre pose: les scenarios K ne sont pas evalues"
else
suivre_decor

# --- K1. la surface mutante est bornee au role de deploiement --------------
# Ce que ce controle exige n'est plus « aucune autre fonction mutante », qui
# etait faux et le restera: c'est qu'aucune ne soit atteignable AILLEURS que
# par `eurostruct_deployment`. Un role applicatif, un porteur de jeton ou
# PUBLIC ne doivent en toucher aucune.
FUITE=$(admb -tAc "
  select coalesce(string_agg(p.proname || ' <- ' || r.role_nom, '; '), '')
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   cross join (values ('public'),('authenticated'),('normative_backend'),
                      ('normative_governance')) as r(role_nom)
   where n.nspname = 'public'
     and p.proname in ('normative_prepare_activation',
                       'normative_record_activation',
                       'normative_finalize_deployment')
     and has_function_privilege(r.role_nom, p.oid, 'EXECUTE')" 2>&1)
if [[ -z "$FUITE" ]]; then
  echo "      ok: K1. les trois entrees mutantes sont bornees au deploiement"
else
  rouge "K1. une entree mutante est atteignable hors du role de deploiement:"
  detail "    $FUITE"
fi

# --- K2. EQUIVALENCE: le chemin compose n'atteint rien de plus -------------
# LES DEUX CHEMINS SONT JOUES SUR LA MEME BASE, ce qui est le seul moyen de
# comparer des empreintes: le `topology_digest` porte les OID des roles, qui
# different d'une base a l'autre. Deux bases jumelles auraient donc donne deux
# empreintes differentes sans que cela prouve quoi que ce soit.
#
# Le chemin compose est joue DANS UNE TRANSACTION ANNULEE: son etat final est
# lu avant le `rollback`, puis la base — intacte — recoit le finaliseur. Ce que
# l'on compare est donc bien deux resultats sur le meme monde.
MANIF_K=$(ctl -tAc "select normative_settings_manifest()" 2>&1)

# CE QUI EST LU, ET PAR QUI. Les tables de confiance ne sont lisibles ni par le
# plan de controle ni par le migrateur — c'est le sceau. L'etat est donc lu par
# les LECTEURS PUBLICS que le sceau expose au role de deploiement:
#
#   normative_activation_state()     l'etat
#   normative_control_plane_oid/()   l'identite figee, OID et nom
#   normative_approved_manifest()    l'empreinte des declarations gelees
#
# et l'empreinte de topologie est la VALEUR DE RETOUR de l'appel — celle de
# `normative_record_activation()` d'un cote, de `normative_finalize_deployment()`
# de l'autre. Rien n'est lu par un superutilisateur: faire lire l'admin aurait
# compare deux etats sous une autorite que le chemin teste n'a pas.
LECTURE="select normative_activation_state() || ' // '
              || coalesce(normative_control_plane_oid()::text, 'AUCUN')
              || '|' || coalesce(normative_control_plane(), 'AUCUN')
              || ' // ' || coalesce(normative_approved_manifest(), 'AUCUN')"

# LE CHEMIN COMPOSE, DANS UNE TRANSACTION ANNULEE. Son etat final est lu avant
# le `rollback`; la base — rendue intacte — recoit ensuite le finaliseur. C'est
# le seul moyen de comparer deux empreintes: le `topology_digest` porte les OID
# des roles, qui different d'une base a l'autre. Deux bases jumelles auraient
# donne deux empreintes differentes sans que cela prouve quoi que ce soit.
BRUT_COMPOSE=$(ctl -tA -v ON_ERROR_STOP=1 2>&1 <<SQL
begin;
select pg_advisory_xact_lock(hashtext('eurostruct.normative_finalisation'));
select normative_prepare_activation('$MANIF_K');
revoke eurostruct_normative_writer    from "$MIG";
revoke eurostruct_normative_bootstrap from "$MIG";
select 'DIGEST=' || normative_record_activation();
$LECTURE;
rollback;
SQL
)
DIGEST_COMPOSE=$(grep -oE 'DIGEST=[0-9a-f]+' <<<"$BRUT_COMPOSE" | head -1)
ETAT_COMPOSE=$(grep -F ' // ' <<<"$BRUT_COMPOSE" | tail -1)

APRES_ANNULATION=$(ctl -tAc "select normative_activation_state()" 2>&1)
DIGEST_FINAL=$(ctl -tAc "select 'DIGEST=' || normative_finalize_deployment('$MANIF_K')" 2>&1 \
                 | grep -oE 'DIGEST=[0-9a-f]+' | head -1)
ETAT_FINAL=$(ctl -tAc "$LECTURE" 2>&1 | grep -F ' // ' | tail -1)

if [[ "$APRES_ANNULATION" != "PENDING" ]]; then
  echoue "K2. l'annulation du chemin compose n'a pas rendu la base a PENDING"
  echoue "    (obtenu: $APRES_ANNULATION); la comparaison ne porterait sur rien"
elif [[ -z "$ETAT_COMPOSE" || -z "$ETAT_FINAL" || -z "$DIGEST_COMPOSE" ]]; then
  echoue "K2. l'un des deux chemins n'a produit aucun etat lisible"
  echoue "    compose:    ${DIGEST_COMPOSE:-<vide>} ${ETAT_COMPOSE:-<vide>}"
  echoue "    finaliseur: ${DIGEST_FINAL:-<vide>} ${ETAT_FINAL:-<vide>}"
elif [[ "$ETAT_COMPOSE" == "$ETAT_FINAL" && "$DIGEST_COMPOSE" == "$DIGEST_FINAL" ]]; then
  echo "      ok: K2. le chemin compose atteint EXACTEMENT l'etat du finaliseur"
  echo "             (etat, plan par OID et nom, declarations gelees, empreinte)"
else
  rouge "K2. le chemin compose atteint un etat DIFFERENT du finaliseur."
  detail "    compose:    $DIGEST_COMPOSE $ETAT_COMPOSE"
  detail "    finaliseur: $DIGEST_FINAL $ETAT_FINAL"
  detail "    Deux chemins vers l'activation sont tolerables tant qu'ils"
  detail "    donnent le meme resultat. Une divergence signifie que l'un des"
  detail "    deux applique une contrainte que l'autre n'applique pas."
fi
decor_deposer
fi

# ==========================================================================
# M. LE NIVEAU D'ASSURANCE SURVIT A LA CONSOLE
# ==========================================================================
# Quand la phase 0 est appliquee par un superutilisateur, le sceau emet un
# NOTICE: « le sceau est pose, mais il ne contient pas celui qui l'a pose ».
#
# C'est exact, et c'est perdu. Un NOTICE ne survit pas au pipeline qui l'a
# affiche: aucune readiness, aucune decision applicative, aucun audit ne peut
# le relire. Deux bases identiques par ailleurs — l'une scellee par un role
# contenu, l'autre par un superutilisateur — sont indiscernables le lendemain.
if ! decor_roles m; then
  echoue "le decor M n'a pas pu etre pose: M n'est pas evalue"
else
suivre_decor
# PHASE 0 PAR UN SUPERUTILISATEUR — forme auto-hebergee, legitime.
SORTIE_M=$(psql -X -q -d "$BASE" -v ON_ERROR_STOP=1 -f "$SCEAU" 2>&1)
if grep -qF "SUPERUTILISATEUR" <<<"$SORTIE_M"; then
  NIVEAU=$(admb -tAc "select assurance_level from normative_seal_metadata" 2>&1)
  if [[ "$NIVEAU" == "UNCONTAINED_SUPERUSER" ]]; then
    echo "      ok: M. le niveau d'assurance est persiste ($NIVEAU)"
  else
    rouge "M. la phase 0 superutilisateur le DIT (notice) mais ne l'INSCRIT pas."
    detail "   Lecture de assurance_level: ${NIVEAU:-<table absente>}"
    detail "   Une information de securite qui ne vit que dans une sortie"
    detail "   console ne peut etre lue par aucune readiness."
  fi
else
  echoue "M. la phase 0 superutilisateur n'a pas emis son notice; scenario non evalue"
fi
decor_deposer
fi

echo ""
echo "================================================="
if [[ $KO -eq 0 && $ROUGES -eq 0 ]]; then
  echo " Contrat du sceau: la racine est deployable."
  echo "================================================="
  exit 0
fi
echo " Contrat du sceau:"
echo "   $KO ecart(s) de decor"
echo "   $ROUGES ouverture(s) a fermer"
echo "================================================="
exit 1
