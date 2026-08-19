#!/usr/bin/env python3
"""EUROSTRUCT — MATRICE DE MUTATION DU CONTRAT DE FINALISATION

    python3 db/test/mutation_matrix.py

CE QUE CE FICHIER EXISTE POUR ETABLIR
--------------------------------------
`finalisation_contract.sh` est vert. Un test vert ne prouve rien tant qu'on ne
l'a pas vu rougir: il peut etre vert parce que la garantie tient, ou vert parce
qu'il ne regarde rien. Ce fichier retire les garanties UNE PAR UNE et exige que
le contre-exemple correspondant rougisse.

IL N'EST PAS DANS LA SUITE CANONIQUE, ET C'EST DELIBERE. Il MODIFIE des
fichiers suivis par git puis les restaure par `git checkout --`. Lance sur un
arbre de travail modifie, il detruirait ce travail. Il refuse donc de demarrer
si l'arbre n'est pas propre — et `run_tests.sh` ne l'appelle jamais.

DEUX POINTS SONT COUVERTS PAR DEUX GARANTIES INDEPENDANTES. Pour ceux-la,
retirer UNE SEULE garantie ne doit rien rougir — c'est la redondance voulue — et
retirer LES DEUX doit rougir. Les deux cas sont exerces.

La connexion vient de l'ENVIRONNEMENT, comme pour tous les harnais.
"""
import os
import re
import subprocess
import sys

# `.../eurostruct/db/test/mutation_matrix.py` -> `.../eurostruct`: TROIS
# remontees. Deux laissaient RACINE sur `.../db`, ou `git status -- db/...` ne
# designe rien: la garde d'arbre propre passait alors sans rien constater.
RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
M = "db/migrations/0010_normative_confirmation.sql"
S = "db/control_plane/0001_normative_seal.sql"
R = "db/test/run.sh"
H = "db/test/authority_closure.sh"
CMD = "tools/deploy_eurostruct.sh"
# LES TROIS CIBLES DE 6.3b6e. Le registre vit dans la premiere migration,
# l'applicateur au-dessus d'elle, et `0002` sert de temoin au controle statique
# de transactionnalite. Les trois sont mutees, donc les trois entrent dans la
# garde d'arbre propre — un fichier mute sans y figurer serait restaure par
# `git checkout --` sans que la garde ait pu prevenir.
INIT = "db/migrations/0001_init.sql"
APP = "db/apply_migration.sh"
RLS = "db/migrations/0002_rls.sql"
SCRATCH = os.environ.get("TMPDIR", "/tmp")


def exiger_arbre_propre():
    """Refuse de demarrer sur un arbre modifie.

    Ce fichier restaure ses mutations par `git checkout --`, qui ECRASE le
    fichier de travail. Sur un arbre modifie, il emporterait le travail en
    cours. Cette garde est la seule chose qui rend l'outil utilisable sans
    precaution particuliere.
    """
    p = subprocess.run(["git", "status", "--porcelain", "--",
                        M, S, R, H, CMD, INIT, APP, RLS],
                       cwd=RACINE, capture_output=True, text=True)
    if p.stdout.strip():
        raise SystemExit(
            "REFUS: cet outil mute puis RESTAURE par `git checkout --`, ce qui\n"
            "       ecraserait les modifications non validees suivantes:\n"
            + p.stdout.rstrip()
            + "\n       Validez ou mettez de cote, puis relancez.")


def muter(fichier, paires):
    chemin = f"{RACINE}/{fichier}"
    s = open(chemin).read()
    for vieux, neuf in paires:
        if vieux not in s:
            raise SystemExit(f"motif absent dans {fichier}: {vieux[:60]!r}")
        s = s.replace(vieux, neuf, 1)
    open(chemin, "w").write(s)


def restaurer(fichier):
    subprocess.run(["git", "checkout", "--", fichier], cwd=RACINE, check=True)


def lancer(harnais="db/test/finalisation_contract.sh", prefixe="mu"):
    env = dict(os.environ)
    env["TMPDIR"] = SCRATCH
    # LE CONSENTEMENT EST POSE ICI, EXPLICITEMENT. Sans lui les harnais
    # refusent — a juste titre — et la matrice conclurait sur des executions
    # qui n'ont pas eu lieu.
    env["EUROSTRUCT_CLUSTER_JETABLE"] = "oui-cluster-jetable-et-isole"
    p = subprocess.run(["bash", harnais, prefixe],
                       cwd=RACINE, env=env, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def essayer(nom, point, fichier, paires, redondant=False,
            harnais="db/test/finalisation_contract.sh", prefixe="mu"):
    muter(fichier, paires)
    try:
        code, sortie = lancer(harnais, prefixe)
    finally:
        restaurer(fichier)
    # Les points 2 et 8 se subdivisent (« 2a. », « 2b. », « 8b. »): un rouge sur
    # une sous-verification EST un rouge du point. Une expression qui exigeait
    # « 2. » exactement a fait passer pour hollow un controle qui avait
    # parfaitement detecte la mutation.
    # UNE SURFACE NON EXECUTEE N'EST PAS UN VERDICT (6.3b6c).
    #
    # Les codes 2 (refus de garde) et 3 (decor non rendu, verrou detenu)
    # signifient que le harnais N'A PAS TOURNE. La version precedente les
    # comptait comme « aucun rouge » et concluait « le controle ne porte
    # rien » — mesure: lancee sans `EUROSTRUCT_CLUSTER_JETABLE`, la matrice a
    # declare les DIX controles creux alors qu'aucun n'avait ete exerce.
    # LE CODE 4 EST LUI AUSSI UN NON-VERDICT (6.3b6d). Il signifie « surface
    # non executable ici » — pas de second cluster, pas d'ecoute TCP. Absent de
    # cette liste, il tombait dans la branche normale et faisait conclure « le
    # controle ne porte rien »: mesure, les trois mutations de
    # `official_deployment.sh` ont ete declarees creuses alors que le harnais
    # n'avait pas demarre. C'est exactement le defaut que les codes 2 et 3
    # avaient deja produit en 6.3b6c, reintroduit par un code de plus.
    if code in (2, 3, 4):
        print(f"  NON EXECUTE {nom}\n        -> le harnais a refuse (code {code}), "
              f"aucune conclusion possible:")
        for ligne in sortie.splitlines()[:3]:
            if ligne.strip():
                print("        " + ligne.strip()[:120])
        return False
    # Les points se subdivisent (« 2a. », « 8b. », « A1. »): un rouge sur une
    # sous-verification EST un rouge du point.
    base = re.match(r"[0-9A-Z]+", point).group(0)
    rougit = re.search(rf"^ *(ROUGE ATTENDU \(a fermer\)|ECHEC): {base}[0-9a-z]?\.",
                       sortie, re.M) is not None
    if redondant:
        if code == 0:
            print(f"  ok    {nom}\n        -> reste vert: la seconde garantie couvre (redondance voulue)")
            return True
        print(f"  note  {nom}\n        -> rougit (code {code}): la redondance n'en est pas une")
        return True
    if rougit:
        print(f"  ok    {nom}\n        -> le point {point} rougit (code {code})")
        return True
    print(f"  ECHEC {nom}\n        -> le point {point} reste VERT: le controle ne porte rien")
    for ligne in sortie.splitlines():
        if re.match(r"^ *(ok|ROUGE|ECHEC)", ligne):
            print("        " + ligne.strip())
    return False


# --------------------------------------------------------------------------
# LE CONTRAT DE FINALISATION (6.3b6b) — les cibles ont demenage en phase 0
# --------------------------------------------------------------------------
# La racine de confiance est passee dans `db/control_plane/0001_normative_seal.sql` (6.3b6c, deplace en 6.3b6d).
# Une matrice qui continuait de muter `0010` ne trouvait plus ses motifs — et
# `muter()` le dit, au lieu de rendre un vert silencieux.
MUT_INTENT = ("""  select * into intention from normative_finalization_intent;
  if not found then""",
              """  select * into intention from normative_finalization_intent;
  if false then""")
MUT_TXID = ("  if intention.prepare_txid <> txid_current() then", "  if false then")
MUT_VERROU_RECORD = ("""  if not exists (
    select 1 from pg_locks
     where locktype = 'advisory'
       and pid = pg_backend_pid()
       and granted
       and ((classid::bigint << 32) | objid::bigint)
           = hashtext('eurostruct.normative_finalisation')::bigint
  ) then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction: '""",
                     """  if false then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction: '""")
MUT_VERROU_PREPARE = ("""  if not exists (
    select 1 from pg_locks
     where locktype = 'advisory'
       and pid = pg_backend_pid()
       and granted
       and ((classid::bigint << 32) | objid::bigint)
           = hashtext('eurostruct.normative_finalisation')::bigint
  ) then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction. La '""",
                      """  if false then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction. La '""")
MUT_GC_INTENTION = ("""  delete from normative_finalization_intent
   where prepare_txid <> txid_current();""",
                    """  -- ramassage retire par mutation""")
MUT_EXEMPTION = ("""         m.oid = normative_control_plane_oid()
         and m.rolname = normative_control_plane()""",
                 """         m.rolname = normative_control_plane()""")
MUT_COHERENCE = ("""      if not exists (select 1 from pg_roles
                      where oid = plan_oid and rolname = plan_nom) then""",
                 """      if false then""")

CAS = [
    ("1  le manifeste n'est plus compare", "1", S,
     [("  if courant is distinct from p_manifeste then", "  if false then")], False),
    ("2  un seul des trois refus d'ecriture directe", "2", S,
     [MUT_INTENT], True),
    ("2b LES TROIS refus d'ecriture directe", "2", S,
     [MUT_INTENT, MUT_TXID, MUT_VERROU_RECORD], False),
    ("3  un seul des deux controles d'identite du plan", "3", S,
     [MUT_EXEMPTION], True),
    ("3b LES DEUX controles d'identite du plan", "3", S,
     [MUT_EXEMPTION, MUT_COHERENCE], False),
    ("4  la finalisation n'est plus serialisee", "4", S,
     [("  perform pg_advisory_xact_lock(hashtext('eurostruct.normative_finalisation'));",
       "  -- verrou retire par mutation")], False),
    ("5  le declencheur PENDING passe apres les autres", "5", M,
     [("create trigger normative_activation_required_grants",
       "create trigger zz_activation_required_grants"),
      ("create trigger normative_activation_required_grant_revocations",
       "create trigger zz_activation_required_grant_revocations"),
      ("create trigger normative_activation_required_confirmations",
       "create trigger zz_activation_required_confirmations"),
      ("create trigger normative_activation_required_confirmation_revocations",
       "create trigger zz_activation_required_confirmation_revocations")], False),
    ("6  policy FOR ALL sur l'activation", "6", S,
     [("""create policy normative_activation_lecture on normative_activation
  for select to eurostruct_normative_activator using (true);
create policy normative_activation_ecriture on normative_activation
  for insert to eurostruct_normative_activator with check (true);""",
       """create policy normative_activation_activateur on normative_activation
  for all to eurostruct_normative_activator using (true) with check (true);""")], False),
    ("7  l'activator quitte le jeu canonique", "7", R,
     [("""CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator
            normative_backend normative_governance eurostruct_deployment)""",
       """CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            normative_backend normative_governance eurostruct_deployment)""")], False),
    ("8  la separation plan/migrateur est retiree", "8b", S,
     [("  if d_oid = m_oid or d_nom = m_nom then", "  if false then")], False),
]

# --------------------------------------------------------------------------
# LA FERMETURE DE L'AUTORITE (6.3b6c) — sept garanties, sept mutations
# --------------------------------------------------------------------------
CAS_AUTORITE = [
    # A — LE LEVIER EST LE DECOR, PAS LA MIGRATION. Ce qui garantit que le
    # migrateur n'atteint jamais l'activateur, c'est que personne ne le lui
    # prete: 0010 ne le demande plus, et le deploiement ne l'accorde plus.
    # Muter la liste d'emprunt de 0010 ferait seulement echouer la migration —
    # un refus, pas une mesure de A1. On simule donc un deploiement qui le
    # prete, et A1 doit le voir.
    ("A  le deploiement prete l'activateur au migrateur", "A1", H,
     [("""grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL""",
       """grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
grant eurostruct_normative_activator to "$MIG" with admin option;
SQL""")], False),
    ("B  les tables de preuve restent au migrateur", "B1", M,
     [("alter table normative_authorisation_grants          owner to eurostruct_normative_writer;",
       "-- transfert retire par mutation")], False),
    ("B' la RLS des tables de preuve n'est plus forcee", "B1", M,
     [("alter table normative_authorisation_grants          force row level security;",
       "-- FORCE retire par mutation")], False),
    ("C  un seul des deux refus de composition", "C2", S,
     [MUT_TXID], True),
    # TROIS garanties, pas deux: la preparation exige elle aussi le verrou, et
    # c'est elle qui refuse en premier dans ce parcours.
    ("C+ LES TROIS refus de composition", "C2", S,
     [MUT_TXID, MUT_VERROU_RECORD, MUT_VERROU_PREPARE], False),
    ("C' un seul des deux refus de preparation isolee", "C1", S,
     [MUT_VERROU_PREPARE], True),
    # TROIS ici aussi: le verrou de preparation, le ramassage de l'intention
    # morte, et la meme-transaction exigee par l'ecriture de confiance.
    ("C'+ verrou de preparation, rederivation ET meme transaction", "C1", S,
     [MUT_VERROU_PREPARE, MUT_GC_INTENTION, MUT_TXID], False),
    ("D  l'idempotence ne compare plus le manifeste", "D", S,
     [("    perform normative_exiger_manifeste_approuve(p_manifeste);\n    perform assert_normative_topology();\n    return 'ACTIVE (deja finalise)';",
       "    perform assert_normative_topology();\n    return 'ACTIVE (deja finalise)';")], False),
    ("E  une exemption de service redevient nominale", "E", S,
     [("""         p.oid = normative_control_plane_oid()
         and p.rolname = normative_control_plane()""",
       """         p.rolname = normative_control_plane()""")], False),
    ("G  le diagnostic de restauration disparait", "G", S,
     [("-- RESTAURATION INTER-CLUSTER — le cas le plus probable de ce refus.",
       "-- Transport de base — le cas le plus probable de ce refus."),
      ("CAS COURANT: RESTAURATION INTER-CLUSTER", "CAS COURANT: transport de base")], False),
]


# --------------------------------------------------------------------------
# L'INDUSTRIALISATION DU SCEAU (6.3b6d) — treize garanties, treize mutations
# --------------------------------------------------------------------------
# Elles portent sur trois harnais differents, et c'est le sujet: une garantie
# qui vit dans `0001_normative_seal.sql` mais n'est constatee que par
# `official_deployment.sh` ne serait pas couverte par une matrice qui ne
# lancerait qu'un seul harnais.
CAS_SCEAU = [
    ("I3  la garde de reexecution ne refuse plus", "I3", S,
     [("""  raise exception
    'SEAL_ALREADY_INSTALLED: le sceau « % » est deja pose sur cette base, et '""",
       """  return;
  raise exception
    'SEAL_ALREADY_INSTALLED: le sceau « % » est deja pose sur cette base, et '""")], False),
    ("I4  le controle de completude du sceau disparait", "I4", S,
     [("  if presents <> array_length(objets, 1) then", "  if false then")], False),
    ("I2  la phase 1 n'exige plus la version du sceau", "I2", M,
     [("  if not (posee = any (compatibles)) then", "  if false then")], False),
    ("J   la liaison poseur/finaliseur est retiree", "J", S,
     [("    if d_oid <> p_oid or d_nom <> p_nom then", "    if false then")], False),
    # REDONDANCE VOULUE: le nom seul et l'OID seul attrapent chacun le
    # contre-exemple J, ou les deux different. En retirer UN ne doit rien
    # rougir; c'est ce qui distingue une double verification d'un doublon.
    ("J'  une SEULE des deux moities de l'identite", "J", S,
     [("    if d_oid <> p_oid or d_nom <> p_nom then", "    if d_oid <> p_oid then")], True),
    ("M   le niveau d'assurance est toujours « contenu »", "M", S,
     [("""       case when c.rolsuper or s.rolsuper then 'UNCONTAINED_SUPERUSER'
            else 'CONTAINED_NON_SUPERUSER' end""",
       """       'CONTAINED_NON_SUPERUSER'""")], False),
    ("K1  une primitive mutante est ouverte a la gouvernance", "K1", S,
     [("""revoke all on function normative_prepare_activation(text) from public;""",
       """revoke all on function normative_prepare_activation(text) from public;
grant execute on function normative_prepare_activation(text) to normative_governance;""")], False),
]

CAS_RESTAURATION = [
    ("L3  le marqueur du diagnostic de restauration disparait", "L3", S,
     [("          'CAS COURANT: RESTAURATION INTER-CLUSTER — les OID ne survivent pas '",
       "          'CAS COURANT: transport de base — les OID ne survivent pas '")], False),
    ("L4  le diagnostic promet a nouveau une reprise", "L4", S,
     [("          'une base NEUVE sur ce cluster (phases 0, 1, 2) et reprenez-y les '",
       "          'refinalisee sur place. Deployez une base NEUVE et reprenez-y les '")], False),
]

CAS_COMMANDE = [
    ("N4  la commande accepte deux acteurs identiques", "N4", CMD,
     [('if [[ "$PLAN_USER" == "$MIG_USER" ]]; then', 'if false; then')], False),
    ("N5  le mode strict ne refuse plus l'assurance degradee", "N5", CMD,
     [("""  if ((STRICT)); then
    echec "niveau d'assurance « $SCEAU_ASSURANCE ».""",
       """  if false; then
    echec "niveau d'assurance « $SCEAU_ASSURANCE ».""")], False),
    ("N3  la relance reaccorde les emprunts sur une base ACTIVE", "N3", CMD,
     [('if [[ "$DEJA" == "ACTIVE" ]]; then', 'if false; then')], False),
    # N1 est couvert par tout ce qui precede: aucune de ces mutations ne peut
    # rougir si le deploiement complet ne tourne pas. Il n'a donc pas de
    # mutation propre, et le dire vaut mieux que d'en inventer une.
    #
    # N6 — « la commande ne contient aucune destruction » — n'en a pas non plus,
    # DELIBEREMENT: sa mutation consisterait a ECRIRE un `drop database` dans un
    # outil de deploiement, meme sur une branche morte. Le fichier est restaure
    # apres coup, mais une interruption au mauvais moment le laisserait en
    # place. Le risque n'est pas proportionne a ce que la mutation etablirait
    # d'un `grep`.
]

# --------------------------------------------------------------------------
# LA REPRISE SURE DE LA COMMANDE (6.3b6e) — treize mutations
# --------------------------------------------------------------------------
# Elles portent sur QUATRE fichiers: la commande, l'applicateur de migrations,
# le registre (dans `0001`) et une migration temoin. Ce n'est pas un accident
# de decoupage: la reprise n'est une garantie que si les quatre tiennent
# ENSEMBLE, et une matrice qui n'en muterait qu'un le laisserait croire.
#
# TROIS PAIRES DE REDONDANCE Y FIGURENT, et elles sont le sujet:
#   P2  — l'ADMIN preexistant ET l'octroi constate;
#   R1  — la borne de longueur ET l'interpolation sure;
#   T4  — le portillon (hors transaction) ET le controle re-fait a l'ecriture.
# Pour chacune, retirer UNE garantie doit rester vert, et retirer LES DEUX doit
# rougir. C'est ce qui distingue une double verification d'un doublon.
MUT_P2_ADMIN = ("""  if [[ "$(plan -tAc "select pg_has_role(current_user, 'eurostruct_deployment', 'MEMBER WITH ADMIN OPTION')::text" 2>/dev/null)" != "true" ]]; then""",
                """  if false; then""")
MUT_P2_CONSTAT = ("""  if [[ "$(plan -tAc "select pg_has_role(current_user, 'eurostruct_deployment', 'USAGE')::text" 2>/dev/null)" != "true" ]]; then""",
                  """  if false; then""")
MUT_R1_BORNE = ("  if [[ ${#valeur} -eq 0 || ${#valeur} -gt 63 ]]; then",
                "  if false; then")
# L'INTERPOLATION SURE, RETIREE. Le heredoc cite (`<<'SQL'`) devient non cite,
# et `:"m"` — que psql sait citer comme IDENTIFIANT — devient une substitution
# shell. C'est la forme exacte qui rendait la commande injectable avant 6.3b6e.
MUT_R1_INTERP = ("""SORTIE=$(plan -v ON_ERROR_STOP=1 -v m="$MIG_USER" 2>&1 <<'SQL'
grant eurostruct_normative_writer    to :"m" with admin option;
grant eurostruct_normative_bootstrap to :"m" with admin option;
SQL
)""",
                 """SORTIE=$(plan -v ON_ERROR_STOP=1 -v m="$MIG_USER" 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG_USER" with admin option;
grant eurostruct_normative_bootstrap to "$MIG_USER" with admin option;
SQL
)""")
MUT_T4_PORTILLON = ("  return 'MISMATCH';", "  return 'DEJA';")
MUT_T4_ECRITURE = ("  if found and connu <> p_sum then", "  if false then")

CAS_REPRISE = [
    ("P2  l'ADMIN preexistant n'est plus exige", "P2", CMD,
     [MUT_P2_ADMIN], True),
    ("P2b l'ADMIN exige ET l'octroi constate", "P2", CMD,
     [MUT_P2_ADMIN, MUT_P2_CONSTAT], False),
    ("Q   la compensation ne se declenche plus", "Q1", CMD,
     [("  if [[ $EMPRUNTS_ACCORDES -eq 1 && $FINALISE -eq 0 ]]; then",
       "  if false; then")], False),
    ("R1  la borne de longueur des identifiants", "R1", CMD,
     [MUT_R1_BORNE], True),
    ("R1' l'interpolation sure du nom de migrateur", "R1", CMD,
     [MUT_R1_INTERP], True),
    ("R1b LES DEUX: borne retiree ET interpolation shell", "R1", CMD,
     [MUT_R1_BORNE, MUT_R1_INTERP], False),
    ("S1  le verrou de deploiement ne refuse plus", "S1", CMD,
     [('if [[ "$PRIS" != "true" ]]; then', "if false; then")], False),
    ("T1  le registre repond toujours « jamais appliquee »", "T1", APP,
     [('    ABSENTE|DEJA|MISMATCH) echo "$reponse" ;;',
       '    ABSENTE|DEJA|MISMATCH) echo "ABSENTE" ;;')], False),
    ("T4  le portillon ne signale plus la divergence", "T4", INIT,
     [MUT_T4_PORTILLON], False),
    ("T4' le controle re-fait a l'ecriture du registre", "T4", INIT,
     [MUT_T4_ECRITURE], True),
    ("T5  une migration perd sa transaction", "T5", RLS,
     [("begin;", "-- begin retire par mutation")], False),
    # UNE SEULE MUTATION POUR U1 ET U2, ET C'EST LE PROPOS. Brancher sur la
    # prose casse les deux a la fois: le message reformule n'est plus reconnu
    # (U1), et n'importe quel SQLSTATE portant le meme texte passe (U2). Les
    # deux contre-exemples sont donc exerces contre le MEME defaut, ce qui est
    # exactement ce qu'ils ont ete ecrits pour attraper.
    ("U1  le branchement suit la prose et non le SQLSTATE", "U1", CMD,
     [('sqlstate() { grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE"; }',
       'sqlstate() { case "$1" in\n'
       '  ES001) grep -qF "SEAL_ALREADY_INSTALLED" <<<"$SORTIE" ;;\n'
       '  *) grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE" ;;\n'
       'esac; }')], False),
    ("U2  le meme branchement, vu par l'autre contre-exemple", "U2", CMD,
     [('sqlstate() { grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE"; }',
       'sqlstate() { case "$1" in\n'
       '  ES001) grep -qF "SEAL_ALREADY_INSTALLED" <<<"$SORTIE" ;;\n'
       '  *) grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE" ;;\n'
       'esac; }')], False),
    ("V1  PGOPTIONS n'est plus efface", "V1", CMD,
     [("unset PGSERVICE PGSERVICEFILE PGPASSFILE PGOPTIONS PGDATABASE PGHOSTADDR \\",
       "unset PGSERVICE PGSERVICEFILE PGPASSFILE PGDATABASE PGHOSTADDR \\")], False),
    ("V2  la politique TLS stricte ne s'applique plus", "V2", CMD,
     [("if ((STRICT)) && ! cible_locale; then", "if false; then")], False),
]

# --------------------------------------------------------------------------
# LE MOINDRE PRIVILEGE DU SCEAU (6.3b6e, point 7) — une mutation
# --------------------------------------------------------------------------
CAS_ACL_SCEAU = [
    ("W1  les metadonnees du sceau redeviennent publiques", "W1", S,
     [("grant select on normative_seal_metadata to eurostruct_deployment;",
       "grant select on normative_seal_metadata to public;\n"
       "grant select on normative_seal_metadata to eurostruct_deployment;")], False),
]

print("MUTATIONS — chaque garantie retiree doit rougir son contre-exemple")
ok = all([essayer(*c) for c in CAS])
ok = all([essayer(*c, harnais="db/test/authority_closure.sh", prefixe="mv")
          for c in CAS_AUTORITE]) and ok
ok = all([essayer(*c, harnais="db/test/seal_contract.sh", prefixe="ms")
          for c in CAS_SCEAU]) and ok
ok = all([essayer(*c, harnais="db/test/cross_cluster_restore.sh", prefixe="mx")
          for c in CAS_RESTAURATION]) and ok
ok = all([essayer(*c, harnais="db/test/official_deployment.sh", prefixe="mo")
          for c in CAS_COMMANDE]) and ok
ok = all([essayer(*c, harnais="db/test/deploy_recovery.sh", prefixe="mp")
          for c in CAS_REPRISE]) and ok
ok = all([essayer(*c, harnais="db/test/seal_contract.sh", prefixe="mw")
          for c in CAS_ACL_SCEAU]) and ok
print()
TOTAL = len(CAS) + len(CAS_AUTORITE) + len(CAS_SCEAU) + len(CAS_RESTAURATION) \
      + len(CAS_COMMANDE) + len(CAS_REPRISE) + len(CAS_ACL_SCEAU)
print(f"MUTATIONS: les {TOTAL} controles portent quelque chose." if ok
      else "MUTATIONS: au moins un controle ne porte rien.")
sys.exit(0 if ok else 1)
