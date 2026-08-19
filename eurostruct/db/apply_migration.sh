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
# fichier. Pose `ESC_MIGRATION_DIAG` avec le diagnostic REEL quand une
# interrogation echoue.
#
# TROIS REPONSES POSSIBLES A LA PREMIERE INTERROGATION, ET NON DEUX.
#
# Elle demande `to_regclass(...) is null`. La premiere ecriture testait
# `!= "f"` et concluait ABSENTE: une sortie VIDE — connexion tombee, droit
# manquant, proxy qui recycle une session — n'est pas « f », et valait donc
# « le registre n'existe pas ». Sur une base portant deja ses migrations, la
# suivante etait REJOUEE. Le commentaire du second aller-retour affirmait
# pourtant deja la bonne regle: « une reponse illisible n'est pas une
# absence ». Contre-exemple mesure: db/test/deploy_recovery.sh, T7, ou
# `0001_init.sql` etait reexecute sur une base en portant cinq.
#
#   « t »      -> le registre n'existe pas: base vierge, on applique;
#   « f »      -> il existe: on interroge le portillon;
#   tout autre -> INDETERMINE, et AUCUN SQL de migration n'est execute.
#
# DEUX ALLERS-RETOURS, ET C'EST NECESSAIRE. Une seule requete avec un `case`
# ne fonctionne PAS: PostgreSQL resout les fonctions et les tables a l'ANALYSE,
# pas a l'execution. Sur une base vierge — ou ni le registre ni
# `normative_migration_gate()` n'existent — la requete echouait a l'analyse, et
# la premiere migration n'etait jamais appliquee. Mesure faite en cablant ce
# fichier.
# ELLE NE REND PLUS SON ETAT PAR `echo`, ET C'EST LA CORRECTION D'UN DEFAUT.
# L'appelant faisait `etat="$(esc_migration_etat ...)"`. Une substitution de
# commande s'execute dans un SOUS-SHELL: `ESC_MIGRATION_DIAG` y etait bien
# posee, et mourait avec lui. Le rapport affichait donc « <aucun> » a l'endroit
# meme ou l'exploitant a besoin de la cause. Contre-exemple mesure: T17.
#
# Les deux resultats sont desormais des GLOBALES, et la fonction est appelee
# directement.
ESC_MIGRATION_DIAG=""
ESC_MIGRATION_GATE_STATE=""
esc_migration_etat() {
  local fichier="$1"; shift
  local id sum reponse presence errfic
  id="$(basename "$fichier")"
  sum="$(esc_empreinte_migration "$fichier")"
  ESC_MIGRATION_DIAG=""
  ESC_MIGRATION_GATE_STATE=""

  # LE DIAGNOSTIC EST CONSERVE, ET NON JETE. `2>/dev/null` renvoyait « le
  # registre n'a pas pu etre interrogo » sans jamais dire pourquoi, et
  # l'exploitant etait envoye vers une cause supposee — « le migrateur a
  # change » — qui pouvait n'avoir aucun rapport.
  errfic="$(mktemp)"
  presence=$("$@" -tA 2>"$errfic" <<'SQL'
select to_regclass('public.normative_migration_ledger') is null;
SQL
  )
  case "$presence" in
    t) rm -f "$errfic"; ESC_MIGRATION_GATE_STATE="ABSENTE"; return 0 ;;
    f) : ;;
    *)
      ESC_MIGRATION_DIAG="$(grep -m2 -v '^[[:space:]]*$' "$errfic" | cut -c1-300)"
      [[ -n "$ESC_MIGRATION_DIAG" ]] \
        || ESC_MIGRATION_DIAG="reponse « ${presence:-<vide>} », attendu « t » ou « f »"
      rm -f "$errfic"
      ESC_MIGRATION_GATE_STATE="INDETERMINE"
      return 0 ;;
  esac
  rm -f "$errfic"

  errfic="$(mktemp)"
  reponse=$("$@" -tA -v id="$id" -v sum="$sum" 2>"$errfic" <<'SQL'
select normative_migration_gate(:'id', :'sum');
SQL
  )
  case "$reponse" in
    ABSENTE|DEJA|MISMATCH) rm -f "$errfic"; ESC_MIGRATION_GATE_STATE="$reponse" ;;
    # UNE REPONSE ILLISIBLE N'EST PAS UNE ABSENCE. Base injoignable, droit
    # manquant, registre a demi cree: on ne peut pas conclure, et conclure
    # « ABSENTE » ferait rejouer une migration deja appliquee.
    *)
      ESC_MIGRATION_DIAG="$(grep -m2 -v '^[[:space:]]*$' "$errfic" | cut -c1-300)"
      [[ -n "$ESC_MIGRATION_DIAG" ]] \
        || ESC_MIGRATION_DIAG="reponse « ${reponse:-<vide>} » du portillon"
      rm -f "$errfic"
      ESC_MIGRATION_GATE_STATE="INDETERMINE" ;;
  esac
}

# `esc_verifier_historique <repertoire> <psql...>` — L'INTEGRITE DE L'HISTOIRE,
# et non celle d'un fichier.
#
# CE QUE L'EMPREINTE NE VOIT PAS. Elle protege un fichier ENCORE PRESENT: on la
# compare a celle qui est inscrite. Une migration appliquee puis SUPPRIMEE ou
# RENOMMEE echappe entierement au controle — le runner ne la demande plus au
# registre, et personne ne s'apercoit que la base porte un objet dont plus
# aucun fichier du depot ne rend compte. Une migration INSEREE avant la
# derniere appliquee est pire encore: elle sera appliquee APRES des migrations
# qui la suivent dans l'ordre, sur un schema qu'elle n'attend pas.
#
# UNE SEULE REGLE COUVRE LES TROIS: les migrations inscrites doivent former un
# PREFIXE EXACT de la liste locale ordonnee.
#
#   * supprimee ou renommee -> une ligne inscrite n'a plus de fichier;
#   * inseree retroactivement -> le prefixe contient un fichier NON inscrit;
#   * ajoutee en suffixe -> le prefixe est intact: c'est le cas normal, permis.
#
# L'IDENTITE DU MIGRATEUR EST FIXE POUR UNE BASE. Les fonctions du registre sont
# SECURITY INVOKER et lisent `normative_migration_ledger`: donner l'EXECUTE a un
# nouveau role ne suffit pas, il lui faudrait aussi la table. Plutot que
# d'improviser une delegation par quelques `GRANT`, la regle de ce jalon est
# qu'une base garde son migrateur. Une rotation de mot de passe conserve le role
# et reste possible; un transfert vers un AUTRE role sera une operation
# explicite, avec transfert de propriete et audit.
#
# Pose `ESC_HISTORIQUE_DIAG`. Rend 0 si tout va bien, 1 sinon.
ESC_HISTORIQUE_DIAG=""
esc_verifier_historique() {
  local dir="$1"; shift
  local f base locaux=() reponse ligne cle val
  local inscrites=() applied_by="" moi="" presence errfic

  ESC_HISTORIQUE_DIAG=""

  # 1. LA FORME CANONIQUE DES NOMS. Sans elle, l'ordre d'application n'est pas
  #    defini, et « prefixe de la liste ordonnee » ne veut rien dire.
  for f in "$dir"/*.sql; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f")"
    if [[ ! "$base" =~ ^[0-9]{4}_[A-Za-z0-9_]+\.sql$ ]]; then
      ESC_HISTORIQUE_DIAG="MIGRATION_HISTORY_DIVERGENCE: « $base » n'est pas une
       migration nommee canoniquement (NNNN_nom.sql). L'ordre d'application
       n'est alors pas defini, et l'integrite de l'historique ne peut pas etre
       verifiee."
      return 1
    fi
    locaux+=("$base")
  done
  # `*.sql` est deja trie par le glob, mais on ne s'en remet pas a la locale.
  mapfile -t locaux < <(printf '%s\n' "${locaux[@]}" | LC_ALL=C sort)

  errfic="$(mktemp)"
  presence=$("$@" -tA 2>"$errfic" <<'SQL'
select to_regclass('public.normative_migration_ledger') is null;
SQL
  )
  case "$presence" in
    t) rm -f "$errfic"; return 0 ;;   # base vierge: aucune histoire a verifier
    f) : ;;
    *)
      ESC_HISTORIQUE_DIAG="MIGRATION_LEDGER_UNREADABLE: l'existence du registre n'a pas pu
       etre etablie avant de verifier l'historique.
       $(grep -m2 -v '^[[:space:]]*$' "$errfic" | cut -c1-300)"
      rm -f "$errfic"
      return 1 ;;
  esac
  rm -f "$errfic"

  # 2. L'IDENTITE DU MIGRATEUR, ETABLIE SUR CE QUE TOUT LE MONDE PEUT LIRE.
  #
  #    L'ancre est le PROPRIETAIRE du registre, et non la colonne `applied_by`.
  #    Mesure (T12): un second migrateur n'a AUCUN droit sur la table — c'est
  #    precisement la situation qu'on veut nommer —, si bien qu'une identite
  #    lue dans la table ne peut pas l'etre par celui qu'il faut refuser. Le
  #    catalogue, lui, est lisible par tous, et le proprietaire ne se falsifie
  #    pas depuis une session ordinaire.
  errfic="$(mktemp)"
  reponse=$("$@" -tA -F$'\t' -v ON_ERROR_STOP=1 2>"$errfic" <<'SQL'
select 'OWNER', pg_get_userbyid(relowner) from pg_class
 where oid = to_regclass('public.normative_migration_ledger');
select 'ME', session_user;
SQL
  )
  if [[ -z "$reponse" ]]; then
    ESC_HISTORIQUE_DIAG="MIGRATION_LEDGER_UNREADABLE: le proprietaire du registre n'a pas pu etre
       etabli.
       $(grep -m2 -v '^[[:space:]]*$' "$errfic" | cut -c1-300)"
    rm -f "$errfic"
    return 1
  fi
  rm -f "$errfic"
  while IFS=$'\t' read -r cle val; do
    case "$cle" in
      OWNER) applied_by="$val" ;;
      ME)    moi="$val" ;;
    esac
  done <<<"$reponse"

  if [[ -n "$applied_by" && "$applied_by" != "$moi" ]]; then
      ESC_HISTORIQUE_DIAG="MIGRATOR_IDENTITY_MISMATCH: cette base a ete migree par « $applied_by »,
       et la connexion presente est « $moi ». Une base garde son migrateur.

       Les fonctions du registre sont SECURITY INVOKER et lisent
       normative_migration_ledger: un simple GRANT EXECUTE ne suffirait pas, et
       ne rendrait pas au nouveau role la propriete des objets deja crees.

       Une rotation de MOT DE PASSE conserve le role et ne pose pas ce refus.
       Un transfert vers un AUTRE role est une operation explicite — transfert
       de propriete et audit — qui n'existe pas encore. Aucun SQL n'est
       applique."
    return 1
  fi

  # 3. LE CONTENU DU REGISTRE. Il n'est lu qu'APRES l'identite: c'est justement
  #    le role refuse en 2 qui n'a pas le droit de le lire, et une lecture
  #    partielle passerait pour un registre vide.
  #
  #    `ON_ERROR_STOP=1` N'EST PAS DECORATIF ICI. Sans lui, psql poursuit apres
  #    une erreur: un `permission denied` sur la table laissait passer la ligne
  #    suivante, la reponse n'etait pas vide, et le registre etait repute VIDE —
  #    donc l'historique intact. Mesure faite en cablant T12.
  errfic="$(mktemp)"
  reponse=$("$@" -tA -F$'\t' -v ON_ERROR_STOP=1 2>"$errfic" <<'SQL'
select 'ID', migration_id from normative_migration_ledger order by migration_id;
SQL
  )
  if [[ -n "$(grep -m1 -v '^[[:space:]]*$' "$errfic")" ]]; then
    ESC_HISTORIQUE_DIAG="MIGRATION_LEDGER_UNREADABLE: le registre existe mais n'a pas pu etre lu.
       $(grep -m2 -v '^[[:space:]]*$' "$errfic" | cut -c1-300)"
    rm -f "$errfic"
    return 1
  fi
  rm -f "$errfic"
  while IFS=$'\t' read -r cle val; do
    [[ "$cle" == "ID" ]] && inscrites+=("$val")
  done <<<"$reponse"

  # 4. LE PREFIXE EXACT.
  local n=${#inscrites[@]} i
  if (( n > ${#locaux[@]} )); then
    ESC_HISTORIQUE_DIAG="MIGRATION_HISTORY_DIVERGENCE: le registre porte $n migration(s), le depot
       n'en contient que ${#locaux[@]}. Des migrations appliquees ont disparu du
       depot. Aucun SQL n'est applique."
    return 1
  fi
  for (( i = 0; i < n; i++ )); do
    if [[ "${inscrites[$i]}" != "${locaux[$i]}" ]]; then
      ESC_HISTORIQUE_DIAG="MIGRATION_HISTORY_DIVERGENCE: en position $((i + 1)), la base a applique
       « ${inscrites[$i]} » et le depot presente « ${locaux[$i]} ».

       Les migrations appliquees doivent former un PREFIXE EXACT de la liste
       locale ordonnee. Trois gestes produisent cet ecart:

         * une migration appliquee a ete SUPPRIMEE du depot;
         * elle a ete RENOMMEE — pour le registre, c'est une disparition;
         * une migration a ete INSEREE AVANT la derniere appliquee, et serait
           donc appliquee apres des migrations qui la suivent.

       Ajouter une migration EN SUFFIXE reste permis. Aucun SQL n'est applique."
      return 1
    fi
  done
  return 0
}

# `esc_appliquer_migration <fichier> <psql...>` — le chemin unique.
esc_appliquer_migration() {
  local fichier="${1:?usage: esc_appliquer_migration <fichier> <psql...>}"; shift
  [[ $# -gt 0 ]] || { echo "REFUS: aucune commande psql fournie." >&2; return 2; }
  [[ -f "$fichier" ]] || { echo "REFUS: migration introuvable ($fichier)." >&2; return 2; }

  local id sum etat
  id="$(basename "$fichier")"
  sum="$(esc_empreinte_migration "$fichier")"
  # APPEL DIRECT, ET NON `$( ... )`: c'est la seule facon de recevoir le
  # diagnostic que la fonction vient de poser.
  esc_migration_etat "$fichier" "$@"
  etat="$ESC_MIGRATION_GATE_STATE"

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
      ESC_MIGRATION_SORTIE="MIGRATION_LEDGER_UNREADABLE: le registre de migrations n'a pas pu
       etre interroge pour « $id ». Un controle qui n'a pas pu s'executer ne
       vaut pas un controle reussi: AUCUN SQL DE MIGRATION N'A ETE EXECUTE.

       DIAGNOSTIC RENDU PAR L'INTERROGATION:
       ${ESC_MIGRATION_DIAG:-<aucun>}

       Ce diagnostic est le fait; ce qui suit n'est qu'une liste de causes
       possibles, a confronter avec lui:

         * la base ou le reseau n'ont pas repondu — un pooler qui recycle une
           session produit exactement cette forme;
         * le role qui migre n'est pas celui qui a applique les migrations
           precedentes (voir MIGRATOR_IDENTITY_MISMATCH);
         * le registre existe a moitie.

       Ne relancez pas a l'aveugle: tant que la cause n'est pas etablie, on ne
       sait pas ce que cette base porte."
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
