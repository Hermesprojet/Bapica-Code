#!/usr/bin/env bash
#
# EUROSTRUCT — APPLIQUER UNE MIGRATION, ET L'INSCRIRE
#
#   source db/apply_migration.sh
#   esc_appliquer_migration <fichier> <commande-psql...>
#
# POURQUOI CE FICHIER EXISTE
# ---------------------------
# Huit appelants appliquaient les migrations, chacun avec sa propre boucle
# `for f in db/migrations/*.sql; do psql -f "$f"; done`. Aucun ne savait ce qui
# avait deja ete applique: une phase 1 interrompue ne se relancait pas, et une
# migration reecrite apres coup n'etait pas detectee (6.3b6e, T1 a T4).
#
# Un seul endroit sait desormais appliquer une migration. Les harnais l'
# utilisent AUSSI — sans quoi ils testeraient un chemin que la production
# n'emprunte pas.
#
# IL N'EST PAS DANS `db/test/`, ET C'EST DELIBERE. `tools/deploy_eurostruct.sh`
# ne doit rien partager avec les harnais de test — mais il doit partager AVEC
# EUX ce que « appliquer une migration » veut dire.
#
# CE QU'IL FAIT
# --------------
#   1. calcule l'empreinte sha256 du FICHIER;
#   2. demande au registre ce qu'il en sait — ABSENTE, DEJA, MISMATCH;
#   3. saute, refuse, ou applique;
#   4. l'application inscrit la ligne DANS LA MEME TRANSACTION que la migration:
#      c'est la migration elle-meme qui appelle `normative_migration_applied()`
#      en derniere ligne, avant son `commit`.
#
# LES DEUX VARIABLES SONT PASSEES A psql, ET LA MIGRATION LES EXIGE. Une
# migration appliquee hors de ce chemin echoue sur une erreur de syntaxe —
# `psql` laisse `:'esc_migration_id'` tel quel quand la variable n'est pas
# posee. On ne peut donc pas contourner le registre par inadvertance.
#
# SORTIES: 0 appliquee ou sautee, 1 refusee (erreur SQL), 2 usage,
#          6 MIGRATION_CHECKSUM_MISMATCH.
#
# APRES L'APPEL: `ESC_MIGRATION_ETAT` vaut APPLIQUEE, SAUTEE ou REFUSEE, et
# `ESC_MIGRATION_SORTIE` porte le detail. Distinguer « appliquee » de « sautee »
# n'est pas cosmetique: un compte rendu qui les confond ne dit pas si une
# relance a repris ou tout rejoue.
ESC_MIGRATION_ETAT=""
ESC_MIGRATION_SORTIE=""

# `esc_empreinte_migration <fichier>` — le sha256 du CONTENU, sans le nom de
# fichier: `sha256sum <fichier` et non `sha256sum fichier`, dont la sortie
# porte le chemin et changerait selon l'endroit d'ou on l'appelle.
esc_empreinte_migration() {
  sha256sum <"$1" | cut -d' ' -f1
}

# `esc_migration_etat <fichier> <psql...>` — ce que le registre sait de ce
# fichier. Rend ABSENTE quand le registre lui-meme n'existe pas encore: c'est
# le cas d'une base vierge, ou la premiere migration cree le registre.
esc_migration_etat() {
  local fichier="$1"; shift
  local id sum reponse
  id="$(basename "$fichier")"
  sum="$(esc_empreinte_migration "$fichier")"
  # DEUX ALLERS-RETOURS, ET C'EST NECESSAIRE. Une seule requete avec un `case`
  # ne fonctionne PAS: PostgreSQL resout les fonctions et les tables a
  # l'ANALYSE, pas a l'execution. Sur une base vierge — ou ni le registre ni
  # `normative_migration_gate()` n'existent encore — la requete echouait donc a
  # l'analyse, la reponse etait vide, et l'etat devenait INDETERMINE: la
  # premiere migration n'etait jamais appliquee. Mesure faite en cablant ce
  # fichier.
  if [[ "$("$@" -tA 2>/dev/null <<'SQL'
select to_regclass('public.normative_migration_ledger') is null;
SQL
  )" != "f" ]]; then
    echo "ABSENTE"
    return 0
  fi
  reponse=$("$@" -tA -v id="$id" -v sum="$sum" 2>/dev/null <<'SQL'
select normative_migration_gate(:'id', :'sum');
SQL
  )
  case "$reponse" in
    ABSENTE|DEJA|MISMATCH) echo "$reponse" ;;
    # UNE REPONSE ILLISIBLE N'EST PAS UNE ABSENCE. Base injoignable, droit
    # manquant, registre a demi cree: on ne peut pas conclure, et conclure
    # « ABSENTE » ferait rejouer une migration deja appliquee.
    *) echo "INDETERMINE" ;;
  esac
}

# `esc_appliquer_migration <fichier> <psql...>` — le chemin unique.
esc_appliquer_migration() {
  local fichier="${1:?usage: esc_appliquer_migration <fichier> <psql...>}"; shift
  [[ $# -gt 0 ]] || { echo "REFUS: aucune commande psql fournie." >&2; return 2; }
  [[ -f "$fichier" ]] || { echo "REFUS: migration introuvable ($fichier)." >&2; return 2; }

  local id sum etat
  id="$(basename "$fichier")"
  sum="$(esc_empreinte_migration "$fichier")"
  etat="$(esc_migration_etat "$fichier" "$@")"

  case "$etat" in
    DEJA)
      ESC_MIGRATION_ETAT=SAUTEE
      ESC_MIGRATION_SORTIE="deja appliquee (${sum:0:12}...)"
      return 0 ;;
    MISMATCH)
      ESC_MIGRATION_ETAT=REFUSEE
      ESC_MIGRATION_SORTIE="MIGRATION_CHECKSUM_MISMATCH: « $id » a deja ete appliquee avec une
       AUTRE empreinte. Le schema de cette base ne correspond a aucun etat du
       depot. Ne rejouez pas: retrouvez la version appliquee, ou ecrivez une
       NOUVELLE migration qui porte le correctif."
      return 6 ;;
    INDETERMINE)
      ESC_MIGRATION_ETAT=REFUSEE
      ESC_MIGRATION_SORTIE="le registre de migrations n'a pas pu etre interroge pour « $id ».
       Un controle qui n'a pas pu s'executer ne vaut pas un controle reussi:
       rien n'est applique.

       CAUSE LA PLUS PROBABLE: le role qui migre n'est pas celui qui a applique
       les migrations precedentes. Le registre et ses deux fonctions
       appartiennent au migrateur d'origine, et ne sont executables que par
       lui. Accordez au nouveau role:

           GRANT EXECUTE ON FUNCTION normative_migration_gate(text, text),
                                     normative_migration_applied(text, text)
             TO <nouveau migrateur>;"
      return 1 ;;
  esac

  # ABSENTE — on applique. `ON_ERROR_STOP` est pose ici et non laisse a
  # l'appelant: sans lui, psql poursuivrait apres une erreur et la migration
  # serait comptee comme reussie.
  ESC_MIGRATION_SORTIE=$("$@" -v ON_ERROR_STOP=1 \
                          -v esc_migration_id="$id" -v esc_migration_sum="$sum" \
                          -f "$fichier" 2>&1)
  local code=$?
  ESC_MIGRATION_ETAT=APPLIQUEE
  if [[ $code -ne 0 ]]; then
    ESC_MIGRATION_ETAT=REFUSEE
    grep -qF "MIGRATION_CHECKSUM_MISMATCH" <<<"$ESC_MIGRATION_SORTIE" && return 6
    return 1
  fi
  return 0
}
