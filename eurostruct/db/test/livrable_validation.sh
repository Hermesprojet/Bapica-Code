#!/usr/bin/env bash
#
# EUROSTRUCT — LE LIVRABLE: DU BROUILLON A L'EMISSION, PAR LES ROUTES REELLES
#
#   db/test/livrable_validation.sh <prefixe-de-base-jetable>
#
# LE DEFAUT PRODUIT QUE CE HARNAIS FERME
# ----------------------------------------
# La machine a etats `draft -> review -> validated -> final` existait en base
# depuis 0005, avec ses transitions interdites, sa chaine de revisions, son
# journal, et l'exigence (0009) qu'un signataire soit membre ACTIF et porteur
# du role de validation. RIEN N'Y ACCEDAIT. `eurostruct_authority_backend`
# n'atteint que les fonctions qu'on lui declare, et aucune ne touchait
# `deliverables` ni `validations`. C'etait un escalier dans un mur sans porte:
# ecrit, eprouve, et inutilisable.
#
# Mesure du jour, avant ce lot: toute route de livrable rendait 404.
#
# CE QUE CE HARNAIS ETABLIT
# --------------------------
#   1. un calcul STRICT aboutit — apres confirmation des parametres par le
#      quatre-yeux, seul chemin qui ouvre le mode strict;
#   2. un brouillon est produit DEPUIS LES DONNEES GELEES, ses octets sont
#      deposes, relus, et leur empreinte verifiee AVANT tout enregistrement;
#   3. les octets telecharges sont exactement ceux qui ont ete deposes, et ils
#      reviennent identiques apres rechargement complet de l'application;
#   4. soumission a la relecture, retour au brouillon avec motif, historique
#      horodate et attribue;
#   5. attestation metier par un compte FICTIF habilite — nom, role et numero
#      d'inscription DERIVES de l'adhesion, jamais du corps HTTP;
#   6. emission impossible sans attestation, puis possible apres;
#   7. un livrable emis ne se modifie plus: corriger, c'est emettre l'indice
#      suivant;
#   8. et tous les refus: jeton absent, falsifie, expire, role insuffisant,
#      membre desactive, nom absent, calcul exploratoire, calcul d'un autre
#      projet, substitution par le corps, organisation voisine, transition
#      interdite.
#
# LES COMPTES SONT EXPLICITEMENT FICTIFS ET VIVENT DANS UNE BASE JETABLE.
# Aucune attestation produite ici n'est une validation reelle. Le registre
# national reste a 0/29, la mention « PROJET — NON SIGNABLE » reste vraie de
# tout calcul non strict, et `SUPABASE_UNVERIFIED` reste vrai.
#
# SANS PILOTE NI FASTAPI, IL REND 4 — NON EXECUTE. Une surface qu'on n'a pas pu
# exercer n'est pas une surface qui a tenu.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: livrable_validation.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "livrable_validation.sh" || exit 2
harnais_verrou_prendre  "livrable_validation.sh" || exit $?
exiger_cluster_jetable  "livrable_validation.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "livrable_validation.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_mt_${JETON}"; CTL="${PREFIXE}_ct_${JETON}"
SVC="${PREFIXE}_st_${JETON}"; BASE="${PREFIXE}_dt_${JETON}"
MDP="FICTIF-livrable-${JETON}"
MANDAT="11111111-8888-8888-8888-888888888801:FICTIF-EMPREINTE-LIVRABLE-${JETON}"
RACINE_ID="11111111-8888-8888-8888-888888888801"
#: LES SEPT IDENTITES, ET CHACUNE EXISTE POUR UN REFUS PRECIS.
#:
#: A  — ingenieur d'ORG_A: cree, calcule, produit le brouillon, soumet.
#: V  — ingenieur VALIDATEUR d'ORG_A, nomme et inscrit: le seul qui atteste.
#: W  — simple lecteur d'ORG_A: son role ne porte pas la validation.
#: D  — validateur d'ORG_A dont l'acces est REVOQUE: la ligne survit, le droit
#:      de signer non.
#: N  — validateur d'ORG_A sans nom enregistre: une attestation porte le nom
#:      d'une personne, et « 3f2a-... » n'en est pas un.
#: B  — ingenieur d'ORG_B: l'ailleurs sans lequel l'isolation ne se prouve pas.
ACTEUR_A="22222222-8888-8888-8888-88888888aaa1"
ACTEUR_V="22222222-8888-8888-8888-88888888bbb1"
ACTEUR_W="22222222-8888-8888-8888-88888888ccc1"
ACTEUR_D="22222222-8888-8888-8888-88888888ddd1"
ACTEUR_N="22222222-8888-8888-8888-88888888eee1"
ACTEUR_B="33333333-8888-8888-8888-88888888fff1"
ORG_A="44444444-8888-8888-8888-8888888888c1"
ORG_B="55555555-8888-8888-8888-8888888888e1"

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

#: LE MAGASIN D'OBJETS DU HARNAIS.
#:
#: `mktemp -d` cree le repertoire; c'est donc un objet DONT LE HARNAIS PEUT
#: PROUVER LA CREATION, et sa destruction ne repose sur aucun motif large.
MAGASIN=""

NETTOYAGE_KO=0
sortie_propre() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "livrable_validation.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  # LE REPERTOIRE CREE PAR CE HARNAIS, ET LUI SEUL.
  if [[ -n "$MAGASIN" && -d "$MAGASIN" && "$MAGASIN" == /tmp/* ]]; then
    rm -rf -- "$MAGASIN" || NETTOYAGE_KO=1
  fi
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

MANQUANTS=""
python3 -c "import psycopg2" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS psycopg2"
python3 -c "import fastapi"  >/dev/null 2>&1 || MANQUANTS="$MANQUANTS fastapi"
python3 -c "import jwt"      >/dev/null 2>&1 || MANQUANTS="$MANQUANTS pyjwt"
python3 -c "import eurostruct_api" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS eurostruct-api"
python3 -c "from fastapi.testclient import TestClient" >/dev/null 2>&1 \
  || MANQUANTS="$MANQUANTS httpx(TestClient)"
if [[ -n "$MANQUANTS" ]]; then
  echo "NON EXECUTE: livrable_validation.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       Le parcours de relecture ne peut pas etre eprouve, et une" >&2
  echo "       surface non executee n'est pas verte." >&2
  echo "       Installer: pip install -e eurostruct/api" >&2
  exit 4
fi

echo "    tranche applicative: le livrable — brouillon, relecture, attestation"

creer_role "$MIG" "login password '$MDP' createrole createdb" || exit 1
creer_role "$CTL" "login password '$MDP' createrole"          || exit 1
creer_role "$SVC" "login password '$MDP'"                     || exit 1
adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
creer_base "$BASE" "owner \"$MIG\"" || exit 1
registre_base "$BASE"

admb -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL

if ! SORTIE=$(ctl -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
  echo "      ECHEC: phase 0: $(grep -m1 ERROR <<<"$SORTIE" | cut -c1-160)" >&2
  exit 1
fi
adm -c "grant eurostruct_deployment to \"$CTL\" with inherit true;" >/dev/null 2>&1
ctlp -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
adm -c "alter database \"$BASE\"
          set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
adm -c "alter database \"$BASE\"
          set eurostruct.approved_service_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\"
          set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1

for f in "$DB_DIR"/migrations/*.sql; do
  if ! esc_appliquer_migration "$f" mig; then
    echo "      ECHEC: $(basename "$f"):" >&2
    esc_diag_rapporter "phase 1 / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
    exit 1
  fi
done
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_finalize_deployment($(esc_litteral "$M"))" >/dev/null 2>&1
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1 | tr -d ' ')
if [[ "$ETAT" != "ACTIVE" ]]; then
  echo "      ECHEC: la base n'est pas ACTIVE ($ETAT)" >&2
  exit 1
fi

ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1

# ---------------------------------------------------------------------
# LE DECOR METIER. Pose par le PROPRIETAIRE de la base, pas par le produit:
# creer une organisation et enroler ses membres releve de l'administration du
# compte, et aucune route ne le fait.
# ---------------------------------------------------------------------
# LE DECOR PARLE QUAND IL ECHOUE.
#
# Les harnais anterieurs posent leur decor en `>/dev/null 2>&1`: une insertion
# refusee ne se voit qu'a la premiere assertion du parcours, sous la forme d'un
# echec fonctionnel sans rapport avec sa cause. On capture ici, et on rapporte.
DECOR_SORTIE="$(admb -v ON_ERROR_STOP=1 2>&1 <<SQL
insert into auth.users (id) values
  ('$RACINE_ID'),('$ACTEUR_A'),('$ACTEUR_V'),('$ACTEUR_W'),
  ('$ACTEUR_D'),('$ACTEUR_N'),('$ACTEUR_B')
on conflict do nothing;
insert into organizations (id, name, country) values
  ('$ORG_A', 'FICTIF Bureau A', 'BE'),
  ('$ORG_B', 'FICTIF Bureau B', 'BE')
on conflict do nothing;

-- LES ADHESIONS, ET CE QUE CHACUNE PROUVE.
--
-- AUCUN ACCENT GRAVE DANS CE CORPS, ET CE N'EST PAS UNE COQUETTERIE. Cet
-- heredoc n'est PAS quote: le shell y developpe les substitutions, et une
-- paire d'accents graves autour d'un nom de colonne s'executerait comme une
-- commande. Sa sortie — vide — entrerait dans le flux SQL a la place du mot.
-- Le scanner du depot refuse cette forme, et il a raison: elle ne se voit
-- pas, parce qu'un commentaire SQL mutile reste un commentaire.
--
-- Les colonnes display_name et professional_id sont posees PAR
-- L'ORGANISATION. La primitive d'attestation les DERIVE de la, jamais du
-- corps HTTP: c'est ce qui rend impossible de signer sous le nom de
-- quelqu'un d'autre.
insert into organization_members
  (org_id, user_id, role, display_name, professional_id) values
  ('$ORG_A', '$ACTEUR_A', 'engineer',
   'FICTIF Ing. A', null),
  ('$ORG_A', '$ACTEUR_V', 'validating_engineer',
   'FICTIF Ing. V (compte de test)', 'FICTIF-ORDRE-0001'),
  ('$ORG_A', '$ACTEUR_W', 'viewer',
   'FICTIF Lecteur W', null),
  ('$ORG_A', '$ACTEUR_D', 'validating_engineer',
   'FICTIF Ing. D (revoque)', 'FICTIF-ORDRE-0002'),
  ('$ORG_A', '$ACTEUR_N', 'validating_engineer',
   null, 'FICTIF-ORDRE-0003'),
  ('$ORG_B', '$ACTEUR_B', 'engineer',
   'FICTIF Ing. B', null)
on conflict do nothing;

-- L'ACCES DE D EST REVOQUE, ET SA LIGNE SURVIT. C'est exactement ce que 0009
-- construit: un ancien collaborateur reste lisible dans une note de dix ans,
-- et ne peut plus rien signer aujourd'hui.
update organization_members
   set is_active = false, deactivated_at = now() - interval '1 day'
 where org_id = '$ORG_A' and user_id = '$ACTEUR_D';

-- UNE ANNEXE NATIONALE EN VIGUEUR, sans quoi la creation de projet refuse. Le
-- decor pose le DOCUMENT, jamais ses valeurs: aucun parametre n'est insere,
-- aucune valeur normative n'est inventee.
insert into national_annexes (country_code, standard_family, part, reference,
                              edition, effective_from, source_official)
values ('BE', 'EN 1992', '1-1', 'FICTIF NBN EN 1992-1-1 ANB',
        'FICTIF — edition de decor', date '2010-08-01',
        'FICTIF — organisme de decor')
on conflict do nothing;
SQL
)"
if grep -q "ERROR" <<<"$DECOR_SORTIE"; then
  echo "      ECHEC: la pose du decor metier a ete refusee:" >&2
  grep -m3 "ERROR\|DETAIL\|LINE" <<<"$DECOR_SORTIE" | cut -c1-200 >&2
  exit 1
fi

# LE DECOR EST CONSTATE, PAS SUPPOSE. Compter ce qui est REELLEMENT en base
# reste necessaire meme quand l'erreur est rapportee: un `on conflict do
# nothing` qui absorbe une ligne ne produit aucune erreur.
NB_ORG=$(q "select count(*) from organizations")
NB_MEM=$(q "select count(*) from organization_members")
NB_ACT=$(q "select count(*) from organization_members where is_active")
NB_NOM=$(q "select count(*) from organization_members where display_name is not null")
NB_ANX=$(q "select count(*) from national_annexes where country_code = 'BE'")
if [[ "$NB_ORG" != "2" || "$NB_MEM" != "6" || "$NB_ACT" != "5"
      || "$NB_NOM" != "5" || "$NB_ANX" == "0" ]]; then
  echo "      ECHEC: le decor metier n'est pas pose." >&2
  echo "             org=$NB_ORG membres=$NB_MEM actifs=$NB_ACT" >&2
  echo "             nommes=$NB_NOM annexes_BE=$NB_ANX" >&2
  exit 1
fi

# ---------------------------------------------------------------------
# LA RACINE D'AUTORITE ET LES DEUX HABILITATIONS DU QUATRE-YEUX.
#
# LE MODE STRICT NE S'OUVRE QUE PAR CE CHEMIN. Un calcul strict refuse tant
# qu'aucun parametre national n'est confirme, et une attestation ne peut porter
# que sur un calcul strict abouti. Confirmer les parametres est donc un
# PREALABLE du parcours de validation, pas un contournement: le harnais fait ce
# qu'un bureau d'etudes ferait, par les routes du produit.
#
# AUCUNE VALEUR NORMATIVE N'EST INVENTEE ICI. Les valeurs viennent du registre
# du moteur, ou elles sont deja marquees `pending_verification`; la confirmation
# est une DECISION HUMAINE fictive a deux regards, et le registre national reste
# a 0/29 pour ce qui est des Annexes officielles ingerees.
# ---------------------------------------------------------------------
ctl -tAc "select bootstrap_normative_administrator(
            '$RACINE_ID'::uuid, 'FICTIF racine', 'FICTIF racine livrable')" \
  >/dev/null 2>&1
GR="$(q "select id from normative_authorisation_grants where origin='bootstrap' limit 1")"
if [[ ! "$GR" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: aucune racine amorcee; les primitives ne peuvent rien faire." >&2
  exit 1
fi

# L'EDITION DE LA PORTEE VIENT DU REGISTRE, PAS D'UNE CONSTANTE.
EDITION_BE="$(python3 - <<'FINPY'
from eurostruct_engine.ndp import load_parameter_set
jeu = load_parameter_set("BE", strict=True)
editions = {jeu.find(k).edition for k in jeu.keys()}
if len(editions) != 1:
    raise SystemExit(f"editions multiples: {sorted(editions)}")
print(editions.pop())
FINPY
)"
if [[ -z "$EDITION_BE" ]]; then
  echo "      ECHEC: edition du registre belge illisible." >&2
  exit 1
fi

octroyer() {   # octroyer <beneficiaire> <motif>
  PGUSER="$SVC" PGPASSWORD="$MDP" psql -X -q -tAc \
    "set eurostruct.actor_id = '$RACINE_ID';
     insert into normative_authorisation_grants
       (grantee_id, grantee_name, permission, country_code, standard_family,
        part, edition, reason, parent_grant_id)
     values ('$1', 'FICTIF $1', 'can_validate_normative_reference', 'BE',
             'EN 1992', '1-1', \$\$$EDITION_BE\$\$, '$2', '$GR')" -d "$BASE" >/dev/null 2>&1
  q "select id from normative_authorisation_grants where reason = '$2'"
}
GA="$(octroyer "$ACTEUR_A" 'FICTIF autorite de A (livrable)')"
GV="$(octroyer "$ACTEUR_V" 'FICTIF autorite de V (livrable)')"
if [[ ! "$GA" =~ ^[0-9a-f-]{36}$ || ! "$GV" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: les habilitations du quatre-yeux n'ont pas ete creees." >&2
  echo "             A=$GA V=$GV" >&2
  exit 1
fi

# ---------------------------------------------------------------------
# LE MAGASIN D'OBJETS. Reel, local, et cree par ce harnais.
#
# LE PRODUIT REFUSE DE CREER UN LIVRABLE SANS MAGASIN — c'est un 503, et l'un
# des cas eprouves. Le declarer ici est donc la condition du parcours nominal,
# pas une commodite.
# ---------------------------------------------------------------------
MAGASIN="$(mktemp -d "/tmp/esc-livrables-${JETON}-XXXXXX")" || {
  echo "      ECHEC: magasin d'objets non cree." >&2; exit 1; }

export EUROSTRUCT_E2E_DSN="dbname=$BASE user=$SVC password=$MDP host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_E2E_DSN_OBS="dbname=$BASE host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_BUILD_SHA="FICTIF-build-${JETON}"
export EUROSTRUCT_STORAGE_DIR="$MAGASIN"
export EUROSTRUCT_LIVRABLE_ACTEUR_A="$ACTEUR_A"
export EUROSTRUCT_LIVRABLE_ACTEUR_V="$ACTEUR_V"
export EUROSTRUCT_LIVRABLE_ACTEUR_W="$ACTEUR_W"
export EUROSTRUCT_LIVRABLE_ACTEUR_D="$ACTEUR_D"
export EUROSTRUCT_LIVRABLE_ACTEUR_N="$ACTEUR_N"
export EUROSTRUCT_LIVRABLE_ACTEUR_B="$ACTEUR_B"
export EUROSTRUCT_LIVRABLE_ORG_A="$ORG_A"
export EUROSTRUCT_LIVRABLE_ORG_B="$ORG_B"

python3 -m pytest "$RACINE/api/tests/test_livrables.py" \
        "$RACINE/api/tests/test_livrable_dxf.py" \
        "$RACINE/api/tests/test_apercu_svg.py" \
        "$RACINE/api/tests/test_dossier_instantane.py" \
        "$RACINE/api/tests/test_autorisations.py" \
        -p no:cacheprovider --no-header
CODE=$?
unset EUROSTRUCT_E2E_DSN EUROSTRUCT_E2E_DSN_OBS EUROSTRUCT_STORAGE_DIR \
      EUROSTRUCT_LIVRABLE_ACTEUR_A EUROSTRUCT_LIVRABLE_ACTEUR_V \
      EUROSTRUCT_LIVRABLE_ACTEUR_W EUROSTRUCT_LIVRABLE_ACTEUR_D \
      EUROSTRUCT_LIVRABLE_ACTEUR_N EUROSTRUCT_LIVRABLE_ACTEUR_B \
      EUROSTRUCT_LIVRABLE_ORG_A EUROSTRUCT_LIVRABLE_ORG_B

# LES OCTETS ONT-ILS REELLEMENT ETE ECRITS SUR DISQUE?
#
# LE CONSTAT EST FAIT ICI, HORS DU PROCESSUS DE TEST. Un test qui verifie son
# propre magasin par la meme abstraction que le produit ne prouve pas que
# quelque chose existe sur disque: il prouve que l'abstraction est coherente
# avec elle-meme. Le harnais, lui, regarde le systeme de fichiers.
if [[ $CODE -eq 0 ]]; then
  NB_OBJETS=$(find "$MAGASIN" -type f -name '*.html' 2>/dev/null | wc -l)
  NB_LIGNES=$(q "select count(*) from deliverables")
  if [[ "$NB_OBJETS" -eq 0 ]]; then
    echo "      ECHEC: aucun octet n'a ete ecrit dans le magasin." >&2
    echo "             Les lignes de livrables promettraient des documents" >&2
    echo "             introuvables." >&2
    CODE=1
  elif [[ "$NB_LIGNES" == "0" ]]; then
    echo "      ECHEC: aucun livrable enregistre malgre des octets deposes." >&2
    CODE=1
  else
    echo "      $NB_OBJETS objet(s) sur disque, $NB_LIGNES ligne(s) de livrable."
  fi
fi

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " Un brouillon tire d'un calcul gele, des octets"
  echo " relus avant d'etre promis, une attestation"
  echo " metier authentifiee, une emission qui l'exige,"
  echo " et un indice suivant pour corriger."
  echo "================================================="
fi
exit $CODE
