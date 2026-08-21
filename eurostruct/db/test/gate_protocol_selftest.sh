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
ok()     { echo "      ok: $*"; }
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
detail() { echo "                $*"; }

echo "    la barriere de vivacite: chaque garantie a son contre-exemple"
[[ -f "$MATRICE" ]] || { echoue "matrice introuvable: $MATRICE"; exit 2; }

# --------------------------------------------------------------------------
# LE WRAPPER REEL, EXTRAIT DE LA MATRICE
# --------------------------------------------------------------------------
ENVELOPPE="$(mktemp)"
python3 - "$MATRICE" "$ENVELOPPE" <<'PY' || { echo "      ECHEC: extraction du wrapper impossible" >&2; exit 2; }
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"        enveloppe = \((.*?)\n        \)\n", src, re.S)
if not m:
    sys.exit("bloc `enveloppe` introuvable dans la matrice")
open(sys.argv[2], "w", encoding="utf-8").write(eval("(" + m.group(1) + ")"))
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
trap 'echo "TRAP_HARNAIS" >>"$ESC_TRACE"; exit 143' TERM
echo "DEMARRE pid=$$" >>"$ESC_TRACE"
[[ -n "${ESC_FIN_IMMEDIATE:-}" ]] && { echo "FIN_AVANT_PORTE" >>"$ESC_TRACE"; exit 7; }
[[ -z "${ESC_HARNAIS_PORTE:-}" ]] && { echo "HOOK_INERTE" >>"$ESC_TRACE"; exit 0; }
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
[[ -n "${ESC_DESCENDANCE:-}" ]] && { ( sleep 600 ) >/dev/null 2>&1 </dev/null &
                                     echo "PETIT_FILS=$!" >>"$ESC_TRACE"; }
read -r -u "$FD"
echo "READ_RENDU=$?" >>"$ESC_TRACE"
exit 77
FIN

# lancer_barriere <fichier-marqueur> <trace> [VAR=val ...]
lancer_barriere() {
  local marqueur="$1" trace="$2"; shift 2
  ( for kv in "$@"; do export "${kv?}"; done
    export ESC_TEMOIN="$marqueur" ESC_MUTATION_JETON="$JETON" ESC_SCENARIO=A
    export ESC_TRACE="$trace"
    exec bash "$ENVELOPPE" bash "$FAUX" ) >/dev/null 2>&1 &
  BARRIERE_PID=$!
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
  n=0; while (( ++n <= 300 )); do zombie "$H" || break; sleep 0.1; done
  zombie "$H" \
    && echoue "10: le harnais reste zombie apres 30 s — personne ne l'a moissonne" \
    || ok "10: le harnais orphelin a ete moissonne (aucun zombie persistant)"
  # LE WRAPPER TUE NE PEUT PAS NETTOYER: c'est un etat classe, pas un succes vide.
  [[ -d "$BAR" ]] \
    && ok "10: repertoire barriere subsistant — classe « wrapper SIGKILLe, nettoyage impossible »" \
    || ok "10: repertoire barriere absent"
  rm -rf "$BAR"
else
  echoue "10: la porte ne s'est pas armee"
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

echo
if (( KO == 0 )); then
  echo "    Barriere de vivacite: chaque garantie a son contre-exemple."
  exit 0
fi
echo "    Des garanties de la barriere ne sont pas defendues."
exit 1
