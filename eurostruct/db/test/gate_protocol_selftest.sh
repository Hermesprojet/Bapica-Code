#!/usr/bin/env bash
#
# EUROSTRUCT — CONTRE-EXEMPLES PERMANENTS DE LA BARRIERE DE VIVACITE
#
#   gate_protocol_selftest.sh
#
# CE QUE CE FICHIER ETABLIT
# --------------------------
# Le scenario A de `mutation_signal_selftest.sh` affirmait qu'un signal
# atteignait un harnais VIVANT. Rien ne le tenait: `READY` certifiait une
# PHOTOGRAPHIE — trois processus constates vivants a l'instant de la
# publication — et le harnais, sous W1, avait une execution finie et legitime.
# Mesure, `EUROSTRUCT` sur b20bc2e:
#
#     ok: harnais identifie PID 45206          <- vivant ici
#     ECHEC: groupes incoherents: harnais[] temoin[] wrapper[45204]
#     ECHEC: le temoin 45205 n'est plus vivant avant le signal
#
# Mort entre deux lectures adjacentes du meme script. La fenetre n'etait pas
# etroite: elle n'etait pas bornee.
#
# LES SHA `ef90bb7`, `42601e7` ET `91f5a4b` NE SONT PAS DES REFERENCES.
# Ils introduisent la barriere et n'ont JAMAIS tourne verts sur le vrai
# harnais: ils cassaient quatre appelants — canal du marqueur deja occupe,
# `GATE_ARMED` exige inconditionnellement, double de harnais qui n'arme pas,
# jeton absent — et le premier scenario mourait avant les autres sur un
# message qui ne nommait pas la cause (« delai depasse »).
#
# LE PREMIER SHA OU LE CHEMIN NOMINAL COMPLET PASSE EST `6448229`. Qui
# bissecte cette periode y trouverait un vert qui n'a jamais existe. L'histoire
# n'est pas reecrite; elle est dite. Voir
# `docs/schema/JALON_6_3b6e_BARRIERE_DE_VIVACITE.md`.
#
# LA BARRIERE REMPLACE LA PHOTOGRAPHIE PAR UNE VIVACITE DETENUE. Ce fichier
# verifie que chaque garantie de ce protocole a un contre-exemple qui la
# CASSE — sans quoi « vert » ne dirait rien.
#
# LE TEXTE DU WRAPPER EST EXTRAIT DE `mutation_matrix.py`, jamais recopie: un
# double du protocole diverge, et le test finirait par prouver ses propres
# hypotheses au lieu du produit.
#
# PLATEFORME. Ce harnais depend de Bash (FD alloues par `{VAR}<>`), des groupes
# de processus POSIX, des FIFO et de `/proc` POUR SES PREUVES. La cible CI est
# Linux + Bash; `/proc` n'est utilise que par les assertions de test, jamais
# par le protocole lui-meme.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJET="$(dirname "$(dirname "$HERE")")"
MATRICE="$HERE/mutation_matrix.py"
KO=0
# LE POINT DE GARANTIE EN COURS. La matrice de mutation ne sait lire qu'une
# chose: « ECHEC: <point>. » en fin de ligne de verdict. Les cas de ce fichier
# sont numerotes par CAS, pas par garantie, et un cas rouge ne disait donc a
# personne QUELLE garantie venait de tomber. `POINT_COURANT` rattache chaque
# echec a la garantie qu'il defend, et le verdict final la NOMME — c'est ce qui
# rend la neuvieme mutation tuable par ce fichier.
POINT_COURANT=""
KO_POINTS=()
ok()     { echo "      ok: $*"; }
echoue() { echo "      ECHEC: $*" >&2; KO=1
           [[ -n "$POINT_COURANT" ]] && KO_POINTS+=("$POINT_COURANT"); return 0; }
point_touche() {   # point_touche <nom> -> vrai si ce point a rougi
  local p="$1" e
  for e in ${KO_POINTS+"${KO_POINTS[@]}"}; do [[ "$e" == "$p" ]] && return 0; done
  return 1
}
detail() { echo "                $*"; }

echo "    la barriere de vivacite: chaque garantie a son contre-exemple"
[[ -f "$MATRICE" ]] || { echoue "matrice introuvable: $MATRICE"; exit 2; }

# --------------------------------------------------------------------------
# LE WRAPPER REEL, EXTRAIT DE LA MATRICE
# --------------------------------------------------------------------------
ENVELOPPE="$(mktemp)"
python3 - "$MATRICE" "$ENVELOPPE" <<'PY' || { echo "      ECHEC: extraction du wrapper impossible" >&2; exit 2; }
import re, sys
# UN SEUL BLOC, ET IL DOIT EXISTER. Zero bloc: le test prouverait le vide.
# Plusieurs: on ne saurait pas lequel est le protocole reellement utilise.
src = open(sys.argv[1], encoding="utf-8").read()
blocs = re.findall(r"        enveloppe = \((.*?)\n        \)\n", src, re.S)
if len(blocs) != 1:
    sys.exit(f"attendu 1 bloc `enveloppe`, trouve {len(blocs)}")
texte = eval("(" + blocs[0] + ")")
if not texte.strip():
    sys.exit("le bloc `enveloppe` est vide")
open(sys.argv[2], "w", encoding="utf-8").write(texte)
PY
bash -n "$ENVELOPPE" || { echoue "le wrapper extrait n'est pas du Bash valide"; exit 2; }
ok "wrapper extrait de mutation_matrix.py ($(wc -c <"$ENVELOPPE") octets, syntaxe valide)"

TMP="$(mktemp -d)"; chmod 0700 "$TMP"
FAUX="$TMP/faux_harnais.sh"
JETON="G-$$-${RANDOM}"

# --------------------------------------------------------------------------
# HARNAIS DE SUBSTITUTION — il n'existe que pour casser le protocole
# --------------------------------------------------------------------------
# Les branches PUREMENT PROTOCOLAIRES se prouvent ici. Le chemin nominal reel,
# la presence effective du decor et le nettoyage sont prouves par le scenario A
# contre `seal_contract.sh` — un faux harnais ne reproduit ni ses descripteurs
# herites ni ses sorties.
cat >"$FAUX" <<'FIN'
set -u
# LE CODE RENDU DEPUIS LA TRAP EST CHOISI PAR L'APPELANT: c'est ce qui permet de
# dresser la table de priorite des codes sans inventer six faux harnais.
trap 'echo "TRAP_HARNAIS" >>"$ESC_TRACE"; exit "${ESC_CODE_TRAP:-143}"' TERM
echo "DEMARRE pid=$$" >>"$ESC_TRACE"
[[ -n "${ESC_FIN_IMMEDIATE:-}" ]] && { echo "FIN_AVANT_PORTE" >>"$ESC_TRACE"; exit 7; }
[[ -z "${ESC_HARNAIS_PORTE:-}" ]] && { echo "HOOK_INERTE" >>"$ESC_TRACE"; exit 0; }
# FENETRE AVANT `GATE_ARMED`: le harnais a demarre, il n'a rien publie, et il ne
# publiera pas avant ce delai. La fenetre est donc OUVERTE et DATEE, au lieu
# d'etre visee a l'aveugle.
if [[ -n "${ESC_RETARD_PORTE:-}" ]]; then
  echo "AVANT_PORTE" >>"$ESC_TRACE"
  sleep "$ESC_RETARD_PORTE" & wait $! 2>/dev/null
fi
exec {FD}<"$ESC_HARNAIS_PORTE" || { echo "OUVERTURE_KO" >>"$ESC_TRACE"; exit 4; }
PID_PUB="$$"; PGID_PUB="$(ps -o pgid= -p $$ | tr -d ' ')"
JET_PUB="$ESC_HARNAIS_JETON"; ETAT_PUB=GATE_ARMED
[[ -n "${ESC_FAUX_PID:-}" ]]   && PID_PUB="$ESC_FAUX_PID"
[[ -n "${ESC_FAUX_PGID:-}" ]]  && PGID_PUB="$ESC_FAUX_PGID"
[[ -n "${ESC_FAUX_JETON:-}" ]] && JET_PUB="$ESC_FAUX_JETON"
[[ -n "${ESC_FAUX_ETAT:-}" ]]  && ETAT_PUB="$ESC_FAUX_ETAT"
if [[ -z "${ESC_SANS_PUBLICATION:-}" ]]; then
  { echo "FORMAT=esc-harness-gate/1"; echo "SCENARIO=$ESC_HARNAIS_SCENARIO"
    echo "TOKEN=$JET_PUB"; echo "PID=$PID_PUB"; echo "PGID=$PGID_PUB"
    echo "STATE=$ETAT_PUB"; } >"$ESC_HARNAIS_ETAT.tmp"
  ln "$ESC_HARNAIS_ETAT.tmp" "$ESC_HARNAIS_ETAT" 2>/dev/null \
    || { echo "PUBLICATION_DUPLIQUEE" >>"$ESC_TRACE"; exit 9; }
  rm -f "$ESC_HARNAIS_ETAT.tmp"
  echo "PUBLIE $ETAT_PUB pid=$PID_PUB pgid=$PGID_PUB" >>"$ESC_TRACE"
fi
# DEUX NIVEAUX, ET LA FORME COMPTE. `( sleep 600 ) &` n'en cree QU'UN: bash
# remplace le sous-shell par la commande unique, si bien que `$!` EST le
# `sleep` et que son pere est le harnais. Mesure: `pgrep -P $!` ne rend rien.
# `( sleep 600 & wait ) &` force le sous-shell a rester — enfant du harnais —
# et le `sleep` devient son petit-fils. Sans cela, « la terminaison atteint la
# descendance PROFONDE » se verifierait sur une descendance plate.
[[ -n "${ESC_DESCENDANCE:-}" ]] && { ( sleep 600 & wait ) >/dev/null 2>&1 </dev/null &
                                     echo "ENFANT=$!" >>"$ESC_TRACE"; }
read -r -u "$FD"
echo "READ_RENDU=$?" >>"$ESC_TRACE"
exit 77
FIN

# lancer_barriere <fichier-marqueur> <trace> [VAR=val ...]
# `BARRIERE_ERR`, s'il est pose par l'appelant, RECUEILLE l'erreur standard du
# wrapper. Par defaut elle part au neant: un cas qui veut prouver un diagnostic
# doit dire explicitement ou il le lit.
BARRIERE_ERR=""
lancer_barriere() {
  local marqueur="$1" trace="$2"; shift 2
  local err="${BARRIERE_ERR:-/dev/null}"
  ( for kv in "$@"; do export "${kv?}"; done
    export ESC_TEMOIN="$marqueur" ESC_MUTATION_JETON="$JETON" ESC_SCENARIO=A
    export ESC_TRACE="$trace"
    # GROUPE PROPRE, comme la matrice reelle (`start_new_session=True`). Sans
    # cela le wrapper partage le groupe du TEST: terminer « le groupe » revenait
    # a se signaler soi-meme. Mesure: le cas 2 s'est tue lui-meme au premier
    # essai. `setsid` ne fork pas ici — l'enfant n'est pas meneur de groupe —
    # donc `$!` est bien le processus final, et son PGID vaut son PID.
    exec setsid bash "$ENVELOPPE" bash "$FAUX" ) >/dev/null 2>"$err" &
  BARRIERE_PID=$!
}

# GARDE-FOU: ne jamais signaler son propre groupe. Une erreur d'un chiffre ici
# tuerait la suite au lieu du sujet, et le rouge serait attribue au produit.
groupe_sujet() {   # groupe_sujet <pid> -> PGID, ou vide si c'est le notre
  local p="$1" pg mien
  pg="$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')"
  mien="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')"
  [[ -n "$pg" && "$pg" != "$mien" ]] || return 1
  echo "$pg"
}

# attendre_fichier <fichier> <deciseconds> — BORNE, jamais un ordonnancement
attendre_fichier() {
  local f="$1" max="$2" n=0
  while [[ ! -s "$f" ]]; do
    (( ++n >= max )) && return 1
    sleep 0.1
  done
  return 0
}

vivant() { local e; e="$(ps -o stat= -p "$1" 2>/dev/null | tr -d ' ')"
           [[ -n "$e" && "$e" != Z* ]]; }
zombie() { local e; e="$(ps -o stat= -p "$1" 2>/dev/null | tr -d ' ')"
           [[ "$e" == Z* ]]; }

champ() { sed -n "s/^$2=//p" "$1" 2>/dev/null | head -1; }

# --------------------------------------------------------------------------
# LA COUVERTURE DES FENETRES DE SIGNAL SE DECLARE A L'ENDROIT OU ELLE EST OBTENUE
# --------------------------------------------------------------------------
# Une table ecrite a la main derive: elle continue d'annoncer une couverture
# apres que le cas qui la portait a ete supprime ou renomme. `fenetre_couverte`
# est appelee PAR LE CAS PORTEUR, sur son chemin de succes uniquement — la
# table qui la lit ne peut donc annoncer que ce qui a reellement tourne.
FENETRES=()
fenetre_couverte() { FENETRES+=("$1|$2"); }
fenetre_vue() {
  local n="$1" e
  for e in ${FENETRES+"${FENETRES[@]}"}; do [[ "${e%%|*}" == "$n" ]] && return 0; done
  return 1
}
fenetre_par_qui() {
  local n="$1" e out=""
  for e in ${FENETRES+"${FENETRES[@]}"}; do
    [[ "${e%%|*}" == "$n" ]] && out="${out:+$out, }${e#*|}"
  done
  printf '%s' "$out"
}

# Chaque cas nettoie son propre etat, par chemins exacts.
menage_cas() {
  [[ -n "${BARRIERE_PID:-}" ]] && { kill -KILL "$BARRIERE_PID" 2>/dev/null
                                    wait "$BARRIERE_PID" 2>/dev/null; }
  BARRIERE_PID=""
}
trap 'menage_cas; rm -rf "$TMP" "$ENVELOPPE"' EXIT

# ==========================================================================
# 1. LE HARNAIS FINIT AVANT LA PORTE -> FAILED, JAMAIS READY
# ==========================================================================
# LES CAS 1 A 6 DEFENDENT UNE SEULE ET MEME GARANTIE, nommee B1: « READY
# n'est publie qu'apres preuve que le harnais est TENU ». Les rattacher a un
# point permet au verdict final de dire laquelle est tombee, au lieu de
# laisser un numero de cas parler pour une propriete.
POINT_COURANT=B1
echo "      -- 1. harnais termine avant la porte"
M1="$TMP/m1"; T1="$TMP/t1"; : >"$T1"
lancer_barriere "$M1" "$T1" "ESC_FIN_IMMEDIATE=1"
if attendre_fichier "$M1" 300; then
  E="$(champ "$M1" STATE)"; G="$(champ "$M1" GATE)"
  [[ "$E" == FAILED ]] \
    && ok "1: STATE=FAILED — la photographie n'a pas suffi a publier READY" \
    || echoue "1: STATE=$E, attendu FAILED"
  [[ "$G" == HARNAIS_TERMINE_AVANT_BLOCKED ]] \
    && ok "1: GATE=$G — la cause est nommee, pas devinee" \
    || echoue "1: GATE=$G, attendu HARNAIS_TERMINE_AVANT_BLOCKED"
  grep -q FIN_AVANT_PORTE "$T1" \
    && ok "1: NON VACUITE — le harnais a bien atteint sa fin avant la porte" \
    || echoue "1: le harnais n'a jamais signale sa fin: cas non exerce"
else
  echoue "1: aucun marqueur publie"
fi
menage_cas

# ==========================================================================
# 2 a 5. IDENTITE DE LA PORTE — chaque attribut compte
# ==========================================================================
# 2. PORTE JAMAIS PUBLIEE — le wrapper attend un EVENEMENT, il ne tranche pas.
# Depuis que le plafond autonome du wrapper a ete retire (une seule autorite de
# delai), l'absence de porte ne produit AUCUN marqueur: le wrapper attend, et
# c'est le PARENT qui borne. L'attendu n'est donc pas « FAILED » mais « jamais
# READY », et le refus appartient au consommateur.
echo "      -- 2. porte jamais publiee: aucun READY, le parent borne"
M2="$TMP/m2"; T2="$TMP/t2"; : >"$T2"
lancer_barriere "$M2" "$T2" "ESC_SANS_PUBLICATION=1"
attendre_fichier "$M2" 50
if [[ -s "$M2" ]] && [[ "$(champ "$M2" STATE)" == READY ]]; then
  echoue "2: READY publie sans porte — la photographie est revenue"
else
  ok "2: aucun READY publie tant que la porte n'est pas armee"
fi
grep -q "^DEMARRE" "$T2" \
  && ok "2: NON VACUITE — le harnais a demarre puis n'a rien publie" \
  || echoue "2: le harnais n'a jamais demarre: cas non exerce"
# « AUCUN READY » NE DISTINGUE PAS UN REFUS CORRECT D'UN BLOCAGE ETERNEL. Le
# parent doit reprendre la main: on termine le groupe, comme le ferait
# `_arreter_enfant()`, et l'on exige zero survivant.
PG2="$(groupe_sujet "$BARRIERE_PID")" || PG2=""
if [[ -n "$PG2" ]]; then
  kill -TERM -"$PG2" 2>/dev/null
  n=0; while (( ++n <= 300 )); do
    [[ -z "$(ps -o pid= -g "$PG2" 2>/dev/null | tr -d ' \n')" ]] && break
    sleep 0.1
  done
  kill -KILL -"$PG2" 2>/dev/null
  n=0; while (( ++n <= 100 )); do
    [[ -z "$(ps -o pid= -g "$PG2" 2>/dev/null | tr -d ' \n')" ]] && break
    sleep 0.1
  done
  restants="$(ps -o pid=,stat= -g "$PG2" 2>/dev/null | tr -s ' ' | tr '\n' ' ')"
  [[ -z "${restants// /}" ]] \
    && ok "2: le parent a repris la main — groupe $PG2 vide, aucun blocage eternel" \
    || echoue "2: survivants dans le groupe $PG2: $restants"
else
  echoue "2: le sujet ne possede pas son propre groupe — refus de signaler le notre"
fi
menage_cas

for cas in "3:ESC_FAUX_JETON=jeton-usurpe:mauvais jeton" \
           "4:ESC_FAUX_PID=999999:mauvais PID" \
           "5:ESC_FAUX_PGID=999999:mauvais PGID"; do
  n="${cas%%:*}"; reste="${cas#*:}"; var="${reste%%:*}"; libelle="${reste#*:}"
  echo "      -- $n. $libelle"
  M="$TMP/m$n"; T="$TMP/t$n"; : >"$T"
  lancer_barriere "$M" "$T" "$var"
  if attendre_fichier "$M" 300; then
    E="$(champ "$M" STATE)"
    [[ "$E" == FAILED ]] \
      && ok "$n: STATE=FAILED — $libelle refuse" \
      || echoue "$n: STATE=$E, attendu FAILED ($libelle accepte)"
    grep -q "^PUBLIE" "$T" \
      && ok "$n: NON VACUITE — le harnais a reellement publie un etat" \
      || echoue "$n: aucune publication: cas non exerce"
  else
    echoue "$n: aucun marqueur publie"
  fi
  menage_cas
done

# ==========================================================================
# 6. READY EXIGE LA PORTE — un etat autre que GATE_ARMED ne suffit pas
# ==========================================================================
echo "      -- 6. READY sans porte armee"
M6="$TMP/m6"; T6="$TMP/t6"; : >"$T6"
lancer_barriere "$M6" "$T6" "ESC_FAUX_ETAT=PRETENDU_PRET"
if attendre_fichier "$M6" 300; then
  [[ "$(champ "$M6" STATE)" == FAILED ]] \
    && ok "6: un etat de porte inconnu ne produit pas READY" \
    || echoue "6: STATE=$(champ "$M6" STATE), attendu FAILED"
  [[ "$(champ "$M6" HARNESS_GATE_STATE)" == PRETENDU_PRET ]] \
    && ok "6: l'etat refuse est RAPPORTE, pas efface" \
    || detail "etat rapporte: $(champ "$M6" HARNESS_GATE_STATE)"
else
  echoue "6: aucun marqueur publie"
fi
menage_cas
POINT_COURANT=""

# ==========================================================================
# 11. ECRITURE DANS LA FIFO -> VIOLATION, JAMAIS SUCCES
# ==========================================================================
# La barriere doit se rompre par le SIGNAL et par rien d'autre. Si une ecriture
# suffisait a liberer le harnais, la garantie « la fin nominale est
# inatteignable » serait fausse — et le test redeviendrait une course.
echo "      -- 11. ecriture dans la FIFO: violation nommee"
M11="$TMP/m11"; T11="$TMP/t11"; : >"$T11"
lancer_barriere "$M11" "$T11"
if attendre_fichier "$M11" 300 && [[ "$(champ "$M11" STATE)" == READY ]]; then
  ok "11: porte armee (READY, $(champ "$M11" HARNESS_GATE_STATE))"
  H="$(champ "$M11" HARNESS_PID)"
  PORTE="$(readlink /proc/"$(champ "$M11" WRAPPER_PID)"/fd/* 2>/dev/null \
           | grep -m1 'harnais\.fifo')"
  if [[ -p "$PORTE" ]]; then
    echo "liberation" >"$PORTE" &
    for _ in $(seq 1 100); do grep -q READ_RENDU "$T11" && break; sleep 0.1; done
    grep -q "READ_RENDU=0" "$T11" \
      && ok "11: le read a rendu 0 — le chemin de violation est atteint" \
      || echoue "11: le read n'a pas rendu 0: $(grep READ_RENDU "$T11" || echo '(rien)')"
    for _ in $(seq 1 100); do vivant "$H" || break; sleep 0.1; done
    vivant "$H" && echoue "11: le harnais survit a la violation" \
                || ok "11: le harnais termine sur violation, il ne poursuit pas"
  else
    echoue "11: FIFO de la porte introuvable"
  fi
else
  echoue "11: la porte ne s'est pas armee"
fi
menage_cas

# ==========================================================================
# 13. CONSOMMATEUR RETARDE — le bail tient, sans `sleep` comme ordre
# ==========================================================================
# LA REPETITION N'EST PAS LA PREUVE. Ce cas ne rend pas la fenetre plus large:
# il montre qu'apres une attente ARBITRAIREMENT longue, la fin nominale reste
# inatteignable. C'est structurel, pas probabiliste.
echo "      -- 13. consommateur retarde: le bail reste tenu"
M13="$TMP/m13"; T13="$TMP/t13"; : >"$T13"
lancer_barriere "$M13" "$T13"
if attendre_fichier "$M13" 300 && [[ "$(champ "$M13" STATE)" == READY ]]; then
  H="$(champ "$M13" HARNESS_PID)"; W="$(champ "$M13" WITNESS_PID)"
  # attente deliberee du consommateur, bien au-dela de ce que durait la course
  n=0; while (( ++n <= 50 )); do sleep 0.1; done
  if vivant "$H" && vivant "$W"; then
    ok "13: apres 5 s de retard, harnais ET temoin sont toujours vivants"
    grep -q "READ_RENDU" "$T13" \
      && echoue "13: le harnais est sorti de la porte sans signal" \
      || ok "13: la porte n'a jamais rendu la main d'elle-meme"
  else
    echoue "13: bail perdu — harnais $(vivant "$H" && echo vivant || echo absent), temoin $(vivant "$W" && echo vivant || echo absent)"
  fi
else
  echoue "13: la porte ne s'est pas armee"
fi
menage_cas

# ==========================================================================
# 14. DESCRIPTEURS — aucun ecrivain herite, aucun FD de l'appelant ecrase
# ==========================================================================
# CONTRE-EXEMPLE HISTORIQUE: les FD 6 et 7 etaient codes en dur. Mesure sur le
# vrai wrapper, harnais bloque, AVANT correction:
#     harnais fd 6 -> harnais.fifo  flags 0100002 (LECTURE+ECRITURE)
#     temoin  fd 7 -> temoin.fifo   flags 0100002 (LECTURE+ECRITURE)
# Chaque enfant heritait d'une extremite d'ECRITURE de SA PROPRE barriere: la
# mort du wrapper n'aurait produit AUCUN EOF.
echo "      -- 14. descripteurs: unicite de l'ecrivain, FD de l'appelant intacts"
M14="$TMP/m14"; T14="$TMP/t14"; : >"$T14"
OCC6="$TMP/occ6"; OCC7="$TMP/occ7"; : >"$OCC6"; : >"$OCC7"
( exec 6>"$OCC6" 7>"$OCC7"
  export ESC_TEMOIN="$M14" ESC_MUTATION_JETON="$JETON" ESC_SCENARIO=A ESC_TRACE="$T14"
  exec bash "$ENVELOPPE" bash "$FAUX" ) >/dev/null 2>&1 &
BARRIERE_PID=$!
if attendre_fichier "$M14" 300 && [[ "$(champ "$M14" STATE)" == READY ]]; then
  W="$(champ "$M14" WRAPPER_PID)"; H="$(champ "$M14" HARNESS_PID)"
  T="$(champ "$M14" WITNESS_PID)"
  ecrivains=0; lecteurs_h=0; lecteurs_t=0; herites=0
  for p in $W $H $T; do
    for fd in /proc/$p/fd/*; do
      c="$(readlink "$fd" 2>/dev/null)"; case "$c" in *.fifo) ;; *) continue;; esac
      fl="$(sed -n 's/^flags:[[:space:]]*//p' /proc/$p/fdinfo/"$(basename "$fd")" 2>/dev/null)"
      [[ -z "$fl" ]] && continue
      mode=$(( (8#$fl) & 3 ))
      if (( mode == 1 || mode == 2 )); then
        if [[ "$p" == "$W" ]]; then ecrivains=$((ecrivains + 1))
        else herites=$((herites + 1)); detail "ecrivain herite: pid $p -> $(basename "$c")"; fi
      else
        [[ "$p" == "$H" ]] && lecteurs_h=$((lecteurs_h + 1))
        [[ "$p" == "$T" ]] && lecteurs_t=$((lecteurs_t + 1))
      fi
    done
  done
  (( ecrivains == 2 )) \
    && ok "14: le wrapper detient les DEUX extremites d'ecriture, et lui seul" \
    || echoue "14: $ecrivains extremite(s) d'ecriture chez le wrapper, attendu 2"
  (( herites == 0 )) \
    && ok "14: aucun ecrivain herite chez le harnais ni chez le temoin" \
    || echoue "14: $herites ecrivain(s) herite(s) — la mort du wrapper ne produirait pas d'EOF"
  (( lecteurs_h == 1 && lecteurs_t == 1 )) \
    && ok "14: harnais et temoin ont chacun leur unique lecteur" \
    || echoue "14: lecteurs harnais=$lecteurs_h temoin=$lecteurs_t, attendu 1 et 1"
  [[ "$(readlink /proc/$BARRIERE_PID/fd/6 2>/dev/null)" == "$OCC6" \
     && "$(readlink /proc/$BARRIERE_PID/fd/7 2>/dev/null)" == "$OCC7" ]] \
    && ok "14: les FD 6 et 7 preouverts par l'appelant sont INTACTS" \
    || echoue "14: FD de l'appelant modifies: 6 -> $(readlink /proc/$BARRIERE_PID/fd/6 2>/dev/null), 7 -> $(readlink /proc/$BARRIERE_PID/fd/7 2>/dev/null)"
else
  echoue "14: la porte ne s'est pas armee"
fi
menage_cas

# ==========================================================================
# 10. WRAPPER TUE -> EOF REEL, violation nommee, aucun blocage eternel
# ==========================================================================
echo "      -- 10. wrapper SIGKILL: EOF reel, aucun blocage eternel"
M10="$TMP/m10"; T10="$TMP/t10"; : >"$T10"
lancer_barriere "$M10" "$T10"
if attendre_fichier "$M10" 300 && [[ "$(champ "$M10" STATE)" == READY ]]; then
  W="$(champ "$M10" WRAPPER_PID)"; H="$(champ "$M10" HARNESS_PID)"
  T="$(champ "$M10" WITNESS_PID)"
  BAR="$(dirname "$(readlink /proc/$W/fd/* 2>/dev/null | grep -m1 'harnais\.fifo')")"
  kill -KILL "$W" 2>/dev/null
  n=0; while (( ++n <= 300 )); do vivant "$H" || break; sleep 0.1; done
  vivant "$H" && echoue "10: le harnais est encore bloque apres la mort du wrapper" \
               || ok "10: le harnais a rendu la main en $(echo "scale=1; $n/10" | bc)s"
  grep -q "READ_RENDU=1" "$T10" \
    && ok "10: read a rendu 1 (EOF) — la cause est nommee" \
    || { echoue "10: pas d'EOF observe"; detail "trace: $(tr '\n' ' ' <"$T10")"; }
  n=0; while (( ++n <= 300 )); do vivant "$T" || break; sleep 0.1; done
  vivant "$T" && echoue "10: le temoin survit au wrapper" || ok "10: le temoin ne survit pas"
  # LE WRAPPER TUE NE PEUT PLUS MOISSONNER: l'orphelin est reparente, et c'est
  # au sous-reaper de le recolter. On l'attend donc de facon BORNEE au lieu de
  # constater un zombie transitoire et d'en faire un defaut — ou, pire, de le
  # declarer absent sans avoir regarde.
  # QUI MOISSONNE ? On ne suppose pas l'existence d'un sub-reaper: on publie le
  # PPID observe jusqu'a convergence bornee, et l'on nomme le moissonneur.
  ppid_obs=""; etat_obs=""
  n=0; while (( ++n <= 300 )); do
    etat_obs="$(ps -o stat= -p "$H" 2>/dev/null | tr -d ' ')"
    [[ -z "$etat_obs" ]] && break
    ppid_obs="$(ps -o ppid= -p "$H" 2>/dev/null | tr -d ' ')"
    sleep 0.1
  done
  if [[ -n "$etat_obs" ]]; then
    echoue "10: le harnais subsiste apres 30 s (etat $etat_obs, ppid $ppid_obs)"
  else
    ok "10: le harnais orphelin a disparu; dernier PPID observe: ${ppid_obs:-inconnu}"
    if [[ -n "$ppid_obs" && "$ppid_obs" != "1" ]]; then
      detail "moissonneur = pid $ppid_obs ($(ps -o comm= -p "$ppid_obs" 2>/dev/null || echo disparu))"
    else
      detail "reparente a pid 1: c'est init qui a moissonne"
    fi
  fi
  # LE WRAPPER TUE NE PEUT PAS NETTOYER: c'est un etat classe, pas un succes vide.
  fenetre_couverte 6 "cas 10"
  [[ -d "$BAR" ]] \
    && ok "10: repertoire barriere subsistant — classe « wrapper SIGKILLe, nettoyage impossible »" \
    || ok "10: repertoire barriere absent"
  rm -rf "$BAR"
else
  echoue "10: la porte ne s'est pas armee"
fi
menage_cas

# ==========================================================================
# 7. PUBLICATION `READY` DUPLIQUEE -> REFUSEE, ET LA VIOLATION EST ENREGISTREE
# ==========================================================================
# L'exclusivite du BLOCKED etait eprouvee; celle du READY ne l'etait pas. Un
# `mv -f` y aurait ecrase un etat anterieur en silence. On occupe donc la cible
# AVANT que le wrapper ne publie: le lien dur doit echouer, le document
# anterieur survivre intact, et la violation etre inscrite dans `.doublon`.
echo "      -- 7. publication READY dupliquee"
M7="$TMP/m7"; T7="$TMP/t7"; E7="$TMP/e7"; : >"$T7"; : >"$E7"
printf 'FORMAT=esc-mutation-marker/2\nSTATE=ANTERIEUR\n' >"$M7"
AVANT7="$(sha256sum "$M7" | cut -d' ' -f1)"
BARRIERE_ERR="$E7"
lancer_barriere "$M7" "$T7"
BARRIERE_ERR=""
attendre_fichier "$M7.doublon" 300
if [[ -f "$M7.doublon" ]]; then
  ok "7: la seconde publication est REFUSEE et inscrite ($(head -1 "$M7.doublon"))"
else
  echoue "7: aucun .doublon — la publication concurrente est passee en silence"
fi
[[ "$(sha256sum "$M7" | cut -d' ' -f1)" == "$AVANT7" ]] \
  && ok "7: le document anterieur est INTACT — aucun ecrasement" \
  || { echoue "7: le document anterieur a ete ecrase"
       detail "contenu: $(tr '\n' ' ' <"$M7")"; }
grep -q "^PUBLIE" "$T7" \
  && ok "7: NON VACUITE — le harnais avait bien arme sa porte" \
  || echoue "7: le harnais n'a pas arme: cas non exerce"
# LE REFUS DOIT ETRE DIT, PAS SEULEMENT ENREGISTRE. `.doublon` s'adresse a qui
# ira le lire; un parent qui attend le marqueur, lui, ne voyait que du silence
# jusqu'a son propre delai. C'est exactement ce qui a coute une campagne: le
# canal etait deja occupe, la publication echouait a la premiere seconde, et le
# verdict rendu 300 s plus tard etait « delai depasse » — le seul message qui ne
# designe pas la cause.
if grep -q "^ESC-WRAPPER: publication du marqueur REFUSEE" "$E7"; then
  ok "7: le refus est DIT sur l'erreur standard, pas seulement inscrit"
  detail "$(grep -m1 '^ESC-WRAPPER' "$E7")"
else
  echoue "7: refus silencieux — rien sur l'erreur standard"
  detail "erreur standard: $(tr '\n' ' ' <"$E7" | cut -c1-160)"
fi
grep -q "un canal doit etre un nom LIBRE" "$E7" \
  && ok "7: le diagnostic nomme le CONTRAT viole, pas seulement le symptome" \
  || echoue "7: le diagnostic ne dit pas ce que l'appelant doit corriger"
menage_cas
rm -f "$M7.doublon"

# ==========================================================================
# 17. LES APPELANTS REELS HONORENT LE CONTRAT DE NOM LIBRE
# ==========================================================================
# LE PROTOCOLE ETAIT CORRECT ET LE PRODUIT ETAIT CASSE. Le cas 7 prouve que la
# publication exclusive refuse une cible occupee; il ne dit rien de la question
# qui a reellement coute la campagne — les appelants presentent-ils un nom
# libre ? Ils ne le faisaient pas: `mktemp` CREE le fichier, et depuis le
# passage de `mv -f` a `ln` chaque canal de `mutation_signal_selftest.sh`
# etait deja occupe avant meme le lancement.
#
# Cette verification est STRUCTURELLE et c'en est la limite: elle lit le texte,
# pas l'execution. Elle est ici parce que le cout d'attraper ce defaut a
# l'execution est une campagne entiere, et son cout ici, une seconde.
echo "      -- 17. les appelants presentent un nom LIBRE"
SELFTEST="$(dirname "$MATRICE")/mutation_signal_selftest.sh"
if [[ ! -f "$SELFTEST" ]]; then
  echoue "17: $SELFTEST introuvable — contrat non verifie"
else
  # Les variables passees en ESC_MUTATION_TEMOIN / ESC_MUTATION_RESULTAT...
  mapfile -t VARS < <(grep -oE 'ESC_MUTATION_(TEMOIN|RESULTAT)="?\$\{?[A-Za-z_][A-Za-z0-9_]*' \
                        "$SELFTEST" | grep -oE '[A-Za-z_][A-Za-z0-9_]*$' | sort -u)
  # ...ET UN NIVEAU D'INDIRECTION, parce que le premier jet n'en suivait aucun
  # et le payait: `lancer_L` recoit le canal en TROISIEME PARAMETRE et l'exporte
  # sous le nom local `temoin`. Les cinq `L_TEM` passaient donc au travers, et
  # la verification se declarait verte sur la version defectueuse en n'ayant vu
  # que deux des sept canaux occupes. Une couverture partielle qui s'annonce
  # totale est pire qu'une absence de verification.
  mapfile -t -O "${#VARS[@]}" VARS < <(
    grep -oE '^[[:space:]]*lancer_L[[:space:]]+"?\$[A-Za-z_][A-Za-z0-9_]*"?[[:space:]]+"?\$[A-Za-z_][A-Za-z0-9_]*"?[[:space:]]+"?\$\{?[A-Za-z_][A-Za-z0-9_]*' \
      "$SELFTEST" | grep -oE '[A-Za-z_][A-Za-z0-9_]*$')
  # `printf '%s\n'` SANS ARGUMENT IMPRIME UNE LIGNE VIDE, et `sort -u` la
  # conserve: un tableau vide serait redevenu un tableau d'un element, et la
  # garde de non-vacuite juste en dessous aurait laisse passer « zero canal
  # repere » en se croyant a un. Les lignes vides sont donc filtrees.
  mapfile -t VARS < <(printf '%s\n' ${VARS+"${VARS[@]}"} | grep -v '^[[:space:]]*$' | sort -u)
  if (( ${#VARS[@]} == 0 )); then
    echoue "17: aucune variable de canal reperee — la verification serait vide"
  else
    ok "17: NON VACUITE — ${#VARS[@]} variable(s) de canal reperee(s): ${VARS[*]}"
    occupes=()
    for v in "${VARS[@]}"; do
      # `mktemp` sans `-u` et sans `-d` cree le fichier: nom OCCUPE.
      # PAS D'ANCRE EN DEBUT DE LIGNE: `L_TEM=` vient apres deux autres
      # affectations sur sa ligne, et l'ancre le rendait invisible.
      while IFS= read -r ligne; do
        [[ "$ligne" == *"${v}=\"\$(mktemp -u)\""* ]] && continue
        [[ "$ligne" == *"${v}=\"\$(mktemp -d)\""* ]] && continue
        [[ "$ligne" == *'IL EXISTE DEJA'* ]] && continue   # sujet d'un test
        occupes+=("$v: ${ligne%%:*}: $(sed 's/^[[:space:]]*//' <<<"${ligne#*:}" | cut -c1-90)")
      done < <(grep -nE "(^|[[:space:];&|]|local[[:space:]]+)${v}=\"?\\\$\(mktemp" "$SELFTEST")
    done
    if (( ${#occupes[@]} == 0 )); then
      ok "17: aucun canal n'est cree par un « mktemp » nu — le contrat tient"
    else
      echoue "17: ${#occupes[@]} canal(aux) presentent un nom DEJA OCCUPE"
      printf '                %s\n' "${occupes[@]}"
    fi
  fi
fi

# ==========================================================================
# 18. UNE CAUSE CONNUE NE DOIT PAS SE PAYER EN DELAI
# ==========================================================================
# Le cas 17 empeche la regression d'entrer; celui-ci borne ce qu'elle coute si
# elle entre quand meme par un chemin non couvert. La publication refusee etait
# CONNUE de tous des la premiere seconde — `.doublon` ecrit, marqueur vide — et
# le parent attendait pourtant ses 300 secondes avant de rendre « delai
# depasse », c'est-a-dire le seul verdict qui ne designe pas la cause.
#
# `attendre()` EST EXTRAITE DE `mutation_signal_selftest.sh`, jamais recopiee:
# un double du mecanisme divergerait, et ce test finirait par prouver ses
# propres hypotheses.
echo "      -- 18. l'attente abandonne sur cause connue au lieu d'expirer"
if [[ ! -f "$SELFTEST" ]]; then
  echoue "18: $SELFTEST introuvable — mecanisme non verifie"
else
  ATT="$TMP/attendre.sh"
  python3 - "$SELFTEST" "$ATT" <<'PY' || echoue "18: extraction d'attendre() impossible"
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
blocs = re.findall(r"\nattendre\(\) \{.*?\n\}\n", src, re.S)
if len(blocs) != 1:
    sys.exit(f"attendu 1 definition d'attendre(), trouve {len(blocs)}")
open(sys.argv[2], "w", encoding="utf-8").write(blocs[0])
PY
  if [[ -s "$ATT" ]] && bash -n "$ATT" 2>/dev/null; then
    ok "18: attendre() extraite de mutation_signal_selftest.sh ($(wc -c <"$ATT") octets)"
    # Harnais minimal: les dependances d'`attendre` sont nommees ici, pas
    # supposees presentes. `pilote18 <fichier> <arguments...>` ecrit un script
    # autonome autour de la definition EXTRAITE et l'appelle une fois.
    pilote18() {
      local cible="$1"; shift
      { echo 'set -uo pipefail'
        echo 'echoue() { echo "ECHEC:$*"; }'
        echo 'detail() { :; }'
        echo 'SORTIE=/dev/null'
        echo 'sleep 3600 & MPID=$!'
        echo "trap 'kill \"\$MPID\" 2>/dev/null' EXIT"
        cat "$ATT"
        echo 'T0=$(date +%s%N)'
        printf 'attendre'; printf ' %q' "$@"; printf '\n'
        echo 'CODE=$?'
        echo 'T1=$(date +%s%N)'
        echo 'echo "CODE=$CODE"'
        echo 'echo "DECISECONDES=$(( (T1 - T0) / 100000000 ))"'
      } >"$cible"
    }
    PILOTE="$TMP/pilote18.sh"
    pilote18 "$PILOTE" "un evenement qui n'arrivera pas" false 600 true "CAUSE NOMMEE"
    RES18="$(bash "$PILOTE" 2>&1)"
    C18="$(sed -n 's/^CODE=//p' <<<"$RES18")"
    D18="$(sed -n 's/^DECISECONDES=//p' <<<"$RES18")"
    [[ "$C18" == "1" ]] \
      && ok "18: l'attente rend 1 — un abandon n'est pas un succes" \
      || echoue "18: code $C18, attendu 1"
    # LE PLAFOND EST 600 DECISECONDES; l'abandon doit conclure sans l'atteindre.
    # On ne compare pas a « vite »: on compare au SEUL delai que ce test possede.
    if [[ -n "$D18" ]] && (( D18 < 60 )); then
      ok "18: conclu en ${D18} deciseconde(s), plafond 600 — la cause n'est pas payee en delai"
    else
      echoue "18: ${D18:-?} deciseconde(s) consommee(s) sur un plafond de 600"
    fi
    grep -q "CAUSE NOMMEE" <<<"$RES18" \
      && ok "18: le verdict NOMME la cause au lieu de dire « delai depasse »" \
      || { echoue "18: la cause n'est pas nommee dans le verdict"
           detail "$(tr '\n' ' ' <<<"$RES18" | cut -c1-160)"; }
    grep -q "delai depasse" <<<"$RES18" \
      && echoue "18: le verdict parle encore de delai depasse" \
      || ok "18: aucun « delai depasse » — le message n'induit plus en erreur"
    # NON VACUITE: SANS condition d'abandon, la MEME attente consomme son
    # plafond. Sinon ce cas pourrait passer sur une attente qui rend 1 pour une
    # tout autre raison.
    PILOTE2="$TMP/pilote18b.sh"
    pilote18 "$PILOTE2" "un evenement qui n'arrivera pas" false 12
    RES18B="$(bash "$PILOTE2" 2>&1)"
    D18B="$(sed -n 's/^DECISECONDES=//p' <<<"$RES18B")"
    if [[ -n "$D18B" ]] && (( D18B >= 10 )); then
      ok "18: NON VACUITE — sans condition d'abandon la meme attente consomme son plafond (${D18B} ds sur 12)"
    else
      echoue "18: sans abandon l'attente rend la main en ${D18B:-?} ds: le cas ne prouve rien"
    fi
    grep -q "delai depasse" <<<"$RES18B" \
      && ok "18: NON VACUITE — et c'est bien « delai depasse » qu'elle rend alors" \
      || echoue "18: sans abandon, le message attendu n'apparait pas"
  else
    echoue "18: attendre() extraite vide ou invalide"
  fi
fi

# ==========================================================================
# 19. UN SECOND SIGNAL NE DOIT PAS COUPER LE NETTOYAGE EN DEUX
# ==========================================================================
# LE HARNAIS RECOIT DEUX SIGTERM, ET C'EST LA NORME. La matrice signale LE
# GROUPE (`os.killpg`), puis le wrapper RELAIE le signal au harnais: deux
# livraisons a quelques microsecondes d'intervalle. Le second arrive donc
# pendant que le piege de sortie nettoie.
#
# CE QUE CELA COUTAIT, MESURE SUR LE VRAI HARNAIS. Le scenario A, une fois sa
# porte armee et son decor reellement pose, terminait avec « code 143 »,
# « groupe vide », « aucun descendant » — et laissait trois roles et une base.
# Le code de sortie est 143 dans LES DEUX cas: il ne distingue pas un nettoyage
# acheve d'un nettoyage tronque. Seul le residu le dit.
#
# `harnais_piege_signaux` EST EXTRAITE DE `lib_harnais.sh`, jamais recopiee.
echo "      -- 19. un second signal ne tronque pas le nettoyage"
LIB="$(dirname "$MATRICE")/lib_harnais.sh"
if [[ ! -f "$LIB" ]]; then
  echoue "19: $LIB introuvable — mecanisme non verifie"
else
  PIEGE="$TMP/piege.sh"
  python3 - "$LIB" "$PIEGE" <<'PY' || echoue "19: extraction du piege impossible"
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
blocs = re.findall(r"\nharnais_piege_signaux\(\) \{.*?\n\}\n", src, re.S)
if len(blocs) != 1:
    sys.exit(f"attendu 1 definition, trouve {len(blocs)}")
open(sys.argv[2], "w", encoding="utf-8").write(blocs[0])
PY
  if [[ -s "$PIEGE" ]] && bash -n "$PIEGE" 2>/dev/null; then
    ok "19: harnais_piege_signaux extraite de lib_harnais.sh ($(wc -c <"$PIEGE") octets)"
    SUJET="$TMP/sujet19.sh"
    { echo 'set -u'
      echo 'J="$1"'
      # Un nettoyage qui DURE: sans duree, le second signal n'aurait aucune
      # fenetre ou tomber et le cas ne prouverait rien.
      echo 'menage() { echo DEBUT >>"$J"; sleep 2; echo FIN >>"$J"; }'
      echo 'trap menage EXIT'
      cat "$PIEGE"
      echo 'harnais_piege_signaux'
      echo 'echo PRET >>"$J"'
      echo 'read -r -t 60 x < <(sleep 60)'
    } >"$SUJET"
    essai19() {   # essai19 <nombre-de-TERM> -> "code|journal"
      local nb="$1" j h c n=0
      j="$(mktemp -p "$TMP")"
      bash "$SUJET" "$j" & h=$!
      while (( ++n <= 100 )); do grep -q PRET "$j" 2>/dev/null && break; sleep 0.1; done
      kill -TERM "$h" 2>/dev/null
      local k=1
      while (( ++k <= nb )); do sleep 0.3; kill -TERM "$h" 2>/dev/null; done
      wait "$h" 2>/dev/null; c=$?
      printf '%s|%s\n' "$c" "$(tr '\n' ' ' <"$j")"
      rm -f "$j"
    }
    R1="$(essai19 1)"; R2="$(essai19 2)"; R3="$(essai19 3)"
    [[ "${R1#*|}" == *FIN* ]] \
      && ok "19: NON VACUITE — un seul signal: le nettoyage va jusqu'au bout" \
      || echoue "19: meme avec UN signal le nettoyage ne s'acheve pas: [$R1]"
    [[ "${R2#*|}" == *FIN* ]] \
      && ok "19: deux signaux: le nettoyage s'acheve quand meme" \
      || { echoue "19: le second signal a TRONQUE le nettoyage"
           detail "[$R2]"; }
    [[ "${R3#*|}" == *FIN* ]] \
      && ok "19: trois signaux: toujours acheve — le desarmement n'est pas a usage unique" \
      || { echoue "19: le troisieme signal a tronque le nettoyage"; detail "[$R3]"; }
    # LE CODE NE DIT RIEN, ET C'EST LE POINT. On l'affirme explicitement pour
    # que personne ne se remette a le lire comme une preuve de nettoyage.
    if [[ "${R1%%|*}" == "143" && "${R2%%|*}" == "143" ]]; then
      ok "19: code 143 dans les deux cas — le code NE PROUVE PAS le nettoyage, seul le residu le dit"
      fenetre_couverte 4 "cas 19"
    else
      echoue "19: codes inattendus: un signal ${R1%%|*}, deux signaux ${R2%%|*}"
    fi
  else
    echoue "19: piege extrait vide ou invalide"
  fi
fi

# ==========================================================================
# 20. LA DESCENDANCE PROFONDE EST DANS LE GROUPE, ET LE GROUPE L'EMPORTE
# ==========================================================================
# « Terminer le groupe » ne dit rien tant qu'on n'a pas montre que le groupe
# contient autre chose que le harnais. Le crochet `ESC_DESCENDANCE` existait
# dans le faux harnais de ce fichier et N'ETAIT EXERCE PAR AUCUN CAS: une
# capacite morte, c'est-a-dire une garantie qu'on croit avoir.
#
# La chaine est ici de quatre niveaux — wrapper, harnais, enfant, petit-fils —
# et c'est le PETIT-FILS qui porte la preuve: il n'est l'enfant direct de
# personne dans le groupe, et seule une terminaison PAR GROUPE peut l'atteindre.
#
# CE CAS COUVRE LA MOITIE PROTOCOLAIRE. L'autre moitie — l'escalade TERM puis
# KILL par `_arreter_enfant()`, seule autorite de delai — passe par la vraie
# matrice et vit dans `mutation_signal_selftest.sh`.
echo "      -- 20. descendance profonde: wrapper > harnais > enfant > petit-fils"
M20="$TMP/m20"; T20="$TMP/t20"; : >"$T20"
lancer_barriere "$M20" "$T20" "ESC_DESCENDANCE=1"
if attendre_fichier "$M20" 300 && [[ "$(champ "$M20" STATE)" == READY ]]; then
  W20="$(champ "$M20" WRAPPER_PID)"; H20="$(champ "$M20" HARNESS_PID)"
  E20="$(sed -n 's/^ENFANT=//p' "$T20" | head -1)"
  PF20=""
  n=0; while (( ++n <= 100 )); do
    PF20="$(pgrep -P "${E20:-0}" 2>/dev/null | head -1)"
    [[ -n "$PF20" ]] && break
    sleep 0.05
  done
  if [[ -z "$E20" || -z "$PF20" ]]; then
    echoue "20: descendance absente (enfant=${E20:-aucun} petit-fils=${PF20:-aucun}) — CHEMIN NON EXERCE"
  else
    ok "20: NON VACUITE — chaine wrapper $W20 > harnais $H20 > enfant $E20 > petit-fils $PF20"
    # LA PROFONDEUR EST VERIFIEE, PAS SUPPOSEE: le petit-fils n'est l'enfant ni
    # du harnais ni du wrapper.
    ppf="$(ps -o ppid= -p "$PF20" 2>/dev/null | tr -d ' ')"
    [[ "$ppf" == "$E20" ]] \
      && ok "20: le petit-fils est bien a DEUX niveaux sous le harnais (ppid $ppf)" \
      || echoue "20: ppid du petit-fils = ${ppf:-aucun}, attendu $E20"
    manque=()
    for p in "$H20" "$E20" "$PF20"; do
      pg="$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')"
      [[ "$pg" == "$W20" ]] || manque+=("$p[${pg:-mort}]")
    done
    (( ${#manque[@]} == 0 )) \
      && ok "20: les trois descendants portent le PGID du wrapper ($W20)" \
      || echoue "20: hors du groupe: ${manque[*]}"
    # TERMINAISON PAR GROUPE, comme le ferait `_arreter_enfant()`.
    PG20="$(groupe_sujet "$BARRIERE_PID")" || PG20=""
    if [[ -z "$PG20" ]]; then
      echoue "20: le sujet ne possede pas son propre groupe — refus de signaler le notre"
    else
      kill -TERM -"$PG20" 2>/dev/null
      n=0; while (( ++n <= 300 )); do
        [[ -z "$(ps -o pid= -g "$PG20" 2>/dev/null | tr -d ' \n')" ]] && break
        sleep 0.1
      done
      kill -KILL -"$PG20" 2>/dev/null
      n=0; while (( ++n <= 100 )); do
        [[ -z "$(ps -o pid= -g "$PG20" 2>/dev/null | tr -d ' \n')" ]] && break
        sleep 0.1
      done
      survivants=()
      for p in "$W20" "$H20" "$E20" "$PF20"; do vivant "$p" && survivants+=("$p"); done
      (( ${#survivants[@]} == 0 )) \
        && ok "20: aucun des quatre ne survit — la terminaison par groupe atteint le petit-fils" \
        || echoue "20: survivants: ${survivants[*]}"
      zombies=()
      for p in "$W20" "$H20" "$E20" "$PF20"; do zombie "$p" && zombies+=("$p"); done
      (( ${#zombies[@]} == 0 )) \
        && ok "20: aucun zombie parmi les quatre" \
        || echoue "20: zombies: ${zombies[*]}"
    fi
  fi
else
  echoue "20: la porte ne s'est pas armee"
fi
menage_cas

# ==========================================================================
# 21. LA PRIORITE DES CODES DE SORTIE, EN TABLE ET NON EN INTENTION
# ==========================================================================
# LA REGLE, telle que `sortie_wrapper` la met en oeuvre: quand un signal a ete
# recu, le wrapper rend 128+signal SI le harnais n'a rien de plus a dire —
# c'est-a-dire s'il a rendu 0 ou deja 128+signal. Sinon LE CODE DU HARNAIS
# L'EMPORTE: un echec de nettoyage a 9 ne doit pas etre maquille en 143, sans
# quoi « interrompu proprement » et « interrompu en laissant des degats »
# deviennent le meme verdict.
#
# ELLE N'ETAIT VERIFIEE QUE SUR DEUX POINTS — 143 par L1, 9 par L2 — et deux
# points ne dessinent pas une regle. La table les couvre tous, y compris les
# deux cotes de la frontiere: 0 (absorbe) et 1 (conserve).
#
# Chaque ligne est un LANCEMENT REEL du wrapper extrait, signale a la porte.
echo "      -- 21. priorite des codes: table complete, un lancement par ligne"
T21_KO=0; T21_N=0
for ligne in "0:143:le harnais n'a rien a dire -> 128+signal" \
             "143:143:le harnais rend deja 128+signal -> inchange" \
             "1:1:un echec generique du harnais l'emporte" \
             "2:2:un REFUS du harnais l'emporte" \
             "3:3:un NON EXECUTE du harnais l'emporte" \
             "9:9:un nettoyage rouge l'emporte sur le signal"; do
  IFS=: read -r c_harnais c_attendu quoi <<<"$ligne"
  M21="$TMP/m21-$c_harnais"; T21="$TMP/t21-$c_harnais"; : >"$T21"
  lancer_barriere "$M21" "$T21" "ESC_CODE_TRAP=$c_harnais"
  if ! attendre_fichier "$M21" 300 || [[ "$(champ "$M21" STATE)" != READY ]]; then
    echoue "21[$c_harnais]: la porte ne s'est pas armee — CHEMIN NON EXERCE"
    T21_KO=$((T21_KO + 1)); menage_cas; continue
  fi
  kill -TERM "$(champ "$M21" WRAPPER_PID)" 2>/dev/null
  C21=0; wait "$BARRIERE_PID" 2>/dev/null || C21=$?
  BARRIERE_PID=""
  T21_N=$((T21_N + 1))
  # NON VACUITE PAR LIGNE: la trap du harnais a bien tourne, donc le code
  # observe vient de LUI et non d'un wrapper qui aurait conclu tout seul.
  if ! grep -q '^TRAP_HARNAIS' "$T21"; then
    echoue "21[$c_harnais]: la trap du harnais n'a pas tourne — code non attribuable"
    T21_KO=$((T21_KO + 1))
  elif [[ "$C21" != "$c_attendu" ]]; then
    echoue "21[$c_harnais]: le wrapper rend $C21, attendu $c_attendu — $quoi"
    T21_KO=$((T21_KO + 1))
  else
    detail "21: harnais $c_harnais -> wrapper $C21   ($quoi)"
  fi
done
if (( T21_N == 0 )); then
  echoue "21: aucune ligne de la table n'a ete exercee"
elif (( T21_KO == 0 )); then
  ok "21: les $T21_N lignes de la table de priorite sont conformes"
else
  echoue "21: $T21_KO ligne(s) non conforme(s) sur $T21_N"
fi
menage_cas

# ==========================================================================
# 22. SIGNAL AVANT `GATE_ARMED` — le wrapper meurt sans mentir, et le parent
#     reprend la main
# ==========================================================================
# LA FENETRE. Entre le lancement du harnais et la publication de `GATE_ARMED`,
# le wrapper tourne dans sa boucle d'attente ET N'A PAS ENCORE ARME SES TRAPPES:
# elles ne sont posees qu'apres la publication du marqueur. Un signal recu ici
# le tue donc par la disposition PAR DEFAUT.
#
# CE QUI DOIT TENIR MALGRE CELA:
#   * AUCUN `READY` n'est publie — le wrapper ne peut pas affirmer une vivacite
#     qu'il n'a pas constatee, meme en mourant;
#   * le harnais orphelin ne reste pas bloque pour l'eternite: son extremite
#     d'ecriture disparait avec le wrapper, sa lecture rend EOF, et il sort;
#   * et si quelque chose survit quand meme, LE PARENT reprend la main.
#     « Aucun READY » ne distingue pas un refus correct d'un blocage eternel.
#
# LA FENETRE EST OUVERTE ET DATEE, pas visee a l'aveugle: `ESC_RETARD_PORTE`
# retient le harnais avant qu'il n'ouvre la porte, et `AVANT_PORTE` dit qu'on y
# est. Sans cela il faudrait courir apres quelques millisecondes.
echo "      -- 22. signal AVANT GATE_ARMED: fenetre ouverte deliberement"
M22="$TMP/m22"; T22="$TMP/t22"; : >"$T22"
lancer_barriere "$M22" "$T22" "ESC_RETARD_PORTE=10"
if ! attendre_fichier "$T22" 300 || ! grep -q '^AVANT_PORTE' "$T22"; then
  echoue "22: le harnais n'a pas atteint la fenetre — CHEMIN NON EXERCE"
  detail "trace: $(tr '\n' ' ' <"$T22")"
else
  ok "22: NON VACUITE — le harnais est DANS la fenetre, avant toute publication"
  [[ ! -s "$M22" ]] \
    && ok "22: aucun marqueur n'existe encore a cet instant" \
    || echoue "22: un marqueur est deja publie: $(tr '\n' ' ' <"$M22")"
  H22="$(sed -n 's/^DEMARRE pid=//p' "$T22" | head -1)"
  PG22="$(groupe_sujet "$BARRIERE_PID")" || PG22=""
  kill -TERM "$BARRIERE_PID" 2>/dev/null
  # LE WRAPPER MEURT: on l'attend, borne.
  n=0; while (( ++n <= 300 )); do vivant "$BARRIERE_PID" || break; sleep 0.1; done
  vivant "$BARRIERE_PID" \
    && echoue "22: le wrapper survit au signal recu avant l'armement de ses trappes" \
    || ok "22: le wrapper est mort — ses trappes n'etaient pas encore armees"
  [[ ! -s "$M22" ]] \
    && ok "22: AUCUN READY publie — le wrapper n'affirme rien en mourant" \
    || echoue "22: marqueur publie malgre la mort avant la porte: $(tr '\n' ' ' <"$M22")"
  # LE HARNAIS ORPHELIN NE SE LIBERE PAS TOUT SEUL, ET C'EST MESURE.
  # L'attente naive etait « son ecrivain a disparu, donc sa lecture rend EOF ».
  # FAUX dans cette fenetre: il n'a pas encore OUVERT la FIFO, et l'ouverture en
  # lecture d'une FIFO SANS ECRIVAIN BLOQUE. Mesure sur le processus lui-meme:
  #
  #     etat=S  wchan=wait_for_partner   (aucun descripteur de FIFO ouvert)
  #
  # Il n'y a donc pas d'EOF a recevoir: il n'est pas dans `read`, il est dans
  # `open`. Un orphelin de cette fenetre attendrait indefiniment.
  #
  # CE N'EST PAS UN DEFAUT DU PROTOCOLE, C'EST CE QUI REND LE PARENT
  # OBLIGATOIRE. « Aucun READY » ne distingue pas un refus correct d'un blocage
  # eternel; seule la reprise en main par le groupe fait la difference, et elle
  # est verifiee juste apres.
  if [[ -n "$H22" ]]; then
    if vivant "$H22"; then
      ok "22: le harnais orphelin $H22 NE se libere PAS seul — la reprise du parent est obligatoire"
      detail "wchan: $(cat "/proc/$H22/wchan" 2>/dev/null || echo inconnu)"
    else
      # Sortie autonome: possible si le harnais avait deja ouvert la porte.
      # Ce n'est pas un echec, mais ce n'est pas la fenetre visee.
      detail "22: le harnais est sorti seul — la fenetre visee n'etait deja plus celle-la"
      detail "trace: $(tr '\n' ' ' <"$T22")"
    fi
  else
    echoue "22: le PID du harnais n'a pas ete publie: rien a verifier"
  fi
  # LE PARENT REPREND LA MAIN, dans tous les cas: zero survivant.
  if [[ -n "$PG22" ]]; then
    kill -TERM -"$PG22" 2>/dev/null
    n=0; while (( ++n <= 300 )); do
      [[ -z "$(ps -o pid= -g "$PG22" 2>/dev/null | tr -d ' \n')" ]] && break
      sleep 0.1
    done
    kill -KILL -"$PG22" 2>/dev/null
    n=0; while (( ++n <= 100 )); do
      [[ -z "$(ps -o pid= -g "$PG22" 2>/dev/null | tr -d ' \n')" ]] && break
      sleep 0.1
    done
    reste22="$(ps -o pid=,stat= -g "$PG22" 2>/dev/null | tr -s ' ' | tr '\n' ' ')"
    if [[ -z "${reste22// /}" ]]; then
      ok "22: le groupe $PG22 est vide — aucun blocage eternel"
      fenetre_couverte 1 "cas 22"
    else
      echoue "22: survivants dans le groupe $PG22: $reste22"
    fi
  else
    echoue "22: le sujet ne possede pas son propre groupe — refus de signaler le notre"
  fi
fi
menage_cas

# ==========================================================================
# 8 et 9. PERTES APRES `READY` — assertions defensives, enfin FALSIFIEES
# ==========================================================================
# `LEASE_LOST_AFTER_READY` et `WITNESS_LOST_AFTER_READY` existent dans le
# scenario A depuis la correction, mais la porte rend justement ces pertes
# impossibles: aucune execution ne les atteignait, et deux assertions jamais
# exercees ne defendent rien. On provoque donc les pertes par un `kill`
# EXTERNE — ce que la porte ne pretend pas empecher — pour prouver qu'elles
# sont DETECTABLES et nommables separement.
echo "      -- 8. harnais perdu apres READY: evenement terminal distinct"
M8="$TMP/m8"; T8="$TMP/t8"; : >"$T8"
lancer_barriere "$M8" "$T8"
if attendre_fichier "$M8" 300 && [[ "$(champ "$M8" STATE)" == READY ]]; then
  H8="$(champ "$M8" HARNESS_PID)"
  kill -KILL "$H8" 2>/dev/null
  attendre_fichier "$M8.terminal" 300
  if [[ -f "$M8.terminal" ]]; then
    [[ "$(champ "$M8.terminal" STATE)" == FAILED_AFTER_READY ]] \
      && ok "8: FAILED_AFTER_READY publie — evenement terminal SEPARE du READY" \
      || echoue "8: etat terminal $(champ "$M8.terminal" STATE)"
    ok "8: code du harnais rapporte: HARNESS_RC=$(champ "$M8.terminal" HARNESS_RC)"
  else
    echoue "8: aucun evenement terminal apres la perte du harnais"
  fi
  [[ "$(champ "$M8" STATE)" == READY ]] \
    && ok "8: le fichier READY n'a PAS ete reecrit" \
    || echoue "8: le READY a ete transforme en $(champ "$M8" STATE)"
else
  echoue "8: la porte ne s'est pas armee"
fi
menage_cas

echo "      -- 9. temoin perdu apres READY: perte independante et detectable"
M9="$TMP/m9"; T9="$TMP/t9"; : >"$T9"
lancer_barriere "$M9" "$T9"
if attendre_fichier "$M9" 300 && [[ "$(champ "$M9" STATE)" == READY ]]; then
  H9="$(champ "$M9" HARNESS_PID)"; W9="$(champ "$M9" WITNESS_PID)"
  kill -KILL "$W9" 2>/dev/null
  n=0; while (( ++n <= 300 )); do vivant "$W9" || break; sleep 0.1; done
  vivant "$W9" && echoue "9: le temoin survit a son propre SIGKILL" \
                || ok "9: le temoin est perdu — un consommateur le constate"
  vivant "$H9" \
    && ok "9: le harnais reste BLOQUE — les deux pertes sont independantes" \
    || echoue "9: la perte du temoin a entraine celle du harnais"
  if grep -q "READ_RENDU" "$T9"; then
    echoue "9: le harnais est sorti de la porte"
  else
    ok "9: la porte tient encore malgre la perte du temoin"
    fenetre_couverte 3 "cas 8 et 9"
  fi
else
  echoue "9: la porte ne s'est pas armee"
fi
menage_cas

# ==========================================================================
# 16. LE HOOK EST INERTE HORS AUTO-TEST
# ==========================================================================
echo "      -- 16. hook inerte quand la porte n'est pas demandee"
T16="$TMP/t16"; : >"$T16"
( export ESC_TRACE="$T16"; bash "$FAUX" ) >/dev/null 2>&1
rc=$?
[[ $rc -eq 0 ]] && grep -q HOOK_INERTE "$T16" \
  && ok "16: sans ESC_HARNAIS_PORTE, le harnais se termine normalement (code 0)" \
  || echoue "16: code $rc, trace: $(tr '\n' ' ' <"$T16")"
grep -q "PUBLIE\|READ_RENDU" "$T16" \
  && echoue "16: le hook a agi alors qu'il n'etait pas demande" \
  || ok "16: aucun marqueur, aucune attente: le hook n'a rien fait"

# ==========================================================================
# LA MATRICE DES FENETRES DE SIGNAL
# ==========================================================================
# SIX FENETRES, ET AUCUNE NE DOIT POUVOIR PASSER POUR VERTE SANS AVOIR ETE
# EXERCEE. Le signal peut arriver a six moments distincts du cycle, et chacun
# met en jeu une propriete differente. Les enumerer sans dire lesquelles sont
# reellement couvertes serait exactement le defaut que ce fichier existe pour
# interdire.
#
# LA TABLE NE S'ECRIT PAS A LA MAIN. Les fenetres portees ICI se declarent
# depuis le chemin de SUCCES de leur cas (`fenetre_couverte`): supprimer le cas,
# ou le faire echouer, retire la ligne. Les fenetres portees AILLEURS sont
# verifiees par la PRESENCE de leur assertion dans le fichier cite: renommer ou
# retirer l'assertion rougit la table, au lieu de la laisser citer un test qui
# n'existe plus.
echo
echo "      -- MATRICE DES FENETRES DE SIGNAL"
SELFTEST_F="$(dirname "$MATRICE")/mutation_signal_selftest.sh"
ISOLATION_F="$(dirname "$MATRICE")/mutation_isolation_selftest.sh"

# porte_ailleurs <numero> <libelle> <fichier> <texte-de-l-assertion>
porte_ailleurs() {
  local n="$1" quoi="$2" f="$3" motif="$4"
  if [[ ! -f "$f" ]]; then
    echoue "fenetre $n: $(basename "$f") introuvable — citation invalide"
    return 1
  fi
  if grep -qF "$motif" "$f"; then
    fenetre_couverte "$n" "$quoi"
    return 0
  fi
  echoue "fenetre $n: l'assertion citee n'existe plus dans $(basename "$f")"
  detail "cherche: $motif"
  return 1
}

porte_ailleurs 3 "L1 (auto-test de signaux)" "$SELFTEST_F" \
  "L1: le relais du wrapper a atteint le harnais"
porte_ailleurs 4 "cas 6 (auto-test d'isolation)" "$ISOLATION_F" \
  "6. le retrait du worktree va jusqu'au bout malgre deux signaux de plus"
porte_ailleurs 5 "L7 (auto-test de signaux)" "$SELFTEST_F" \
  "L7: le resultat est PUBLIE malgre le signal recu dans la fenetre"

FEN_LIBELLE=(
  "1|avant GATE_ARMED"
  "2|apres GATE_ARMED, avant READY"
  "3|apres READY"
  "4|pendant le nettoyage"
  "5|entre la fin du harnais et la publication du resultat"
  "6|apres la perte du wrapper"
)
FEN_NON=0
for e in "${FEN_LIBELLE[@]}"; do
  n="${e%%|*}"; libelle="${e#*|}"
  if fenetre_vue "$n"; then
    printf '                %s. %-52s porte par %s\n' "$n" "$libelle" "$(fenetre_par_qui "$n")"
  else
    printf '                %s. %-52s CHEMIN NON EXERCE\n' "$n" "$libelle"
    FEN_NON=$((FEN_NON + 1))
  fi
done

# LA FENETRE 2 EST DECLAREE NON EXERCEE, ET LA RAISON EST ECRITE.
# Entre la detection de la porte et la publication du marqueur, le wrapper
# n'execute que ses verifications d'identite: quelques appels a `ps`, soit
# quelques millisecondes. La viser sans crochet reviendrait a compter des
# reussites au lieu d'etablir une propriete. ET AUCUN CROCHET N'EST POSE DANS LE
# WRAPPER: c'est la piece meme que ce fichier extrait et met en echec, et y
# ajouter du code de test rendrait l'objet mesure different de l'objet livre.
#
# CE QUI EST QUAND MEME ETABLI DE PART ET D'AUTRE. Cote wrapper, le cas 22
# montre qu'un signal recu avant l'armement de ses trappes ne produit AUCUN
# READY. Cote harnais, le cas 10 montre qu'une porte deja armee rend la main en
# 0,1 s sur EOF quand le wrapper disparait. La fenetre 2 est encadree par les
# deux — elle n'est pas exercee, et elle est comptee comme telle.
if fenetre_vue 2; then
  echoue "fenetre 2: declaree couverte alors qu'aucun crochet ne permet de l'atteindre"
else
  detail "fenetre 2: quelques millisecondes de verifications d'identite; aucun"
  detail "           crochet dans le wrapper, qui est la piece mesuree. Encadree"
  detail "           par le cas 22 (cote wrapper) et le cas 10 (cote harnais)."
fi
if (( FEN_NON == 0 )); then
  ok "les six fenetres de signal sont exercees"
elif (( FEN_NON == 1 )) && ! fenetre_vue 2; then
  ok "cinq fenetres sur six exercees; la sixieme est declaree NON EXERCEE, avec sa raison"
else
  echoue "$FEN_NON fenetre(s) non exercee(s) — voir la table ci-dessus"
fi

# LE VERDICT NOMME LA GARANTIE TOMBEE, PAS SEULEMENT LE CAS. La matrice de
# mutation ne reconnait un contre-exemple que sous la forme « ECHEC: <point>. »;
# sans cette ligne, retirer la barriere du wrapper faisait rougir six cas sans
# qu'aucun verdict ne designe LA garantie perdue — et la mutation aurait ete
# comptee CREUSE alors qu'elle etait parfaitement detectee.
if point_touche B1; then
  echo "      ECHEC: B1. la barriere de vivacite ne tient plus: READY publie sans preuve de blocage" >&2
fi

echo
if (( KO == 0 )); then
  echo "    Barriere de vivacite: chaque garantie a son contre-exemple."
  exit 0
fi
echo "    Des garanties de la barriere ne sont pas defendues."
exit 1
