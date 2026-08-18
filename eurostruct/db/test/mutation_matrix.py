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
R = "db/test/run.sh"
SCRATCH = os.environ.get("TMPDIR", "/tmp")


def exiger_arbre_propre():
    """Refuse de demarrer sur un arbre modifie.

    Ce fichier restaure ses mutations par `git checkout --`, qui ECRASE le
    fichier de travail. Sur un arbre modifie, il emporterait le travail en
    cours. Cette garde est la seule chose qui rend l'outil utilisable sans
    precaution particuliere.
    """
    p = subprocess.run(["git", "status", "--porcelain", "--", M, R],
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


def lancer():
    env = dict(os.environ)
    env["TMPDIR"] = SCRATCH
    p = subprocess.run(["bash", "db/test/finalisation_contract.sh", "mu"],
                       cwd=RACINE, env=env, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def essayer(nom, point, fichier, paires, redondant=False):
    muter(fichier, paires)
    try:
        code, sortie = lancer()
    finally:
        restaurer(fichier)
    # Les points 2 et 8 se subdivisent (« 2a. », « 2b. », « 8b. »): un rouge sur
    # une sous-verification EST un rouge du point. Une expression qui exigeait
    # « 2. » exactement a fait passer pour hollow un controle qui avait
    # parfaitement detecte la mutation.
    base = re.match(r"\d+", point).group(0)
    rougit = re.search(rf"^ *(ROUGE ATTENDU \(a fermer\)|ECHEC): {base}[a-z]?\.",
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


MUT_INTENT = ("""  select * into intention from normative_finalization_intent;
  if not found then""",
              """  select * into intention from normative_finalization_intent;
  if false then""")
MUT_PLAN_NUL = ("  if plan_oid is null or plan_nom is null then", "  if false then")
MUT_EXEMPTION = ("""         m.oid = normative_control_plane_oid()
         and m.rolname = normative_control_plane()""",
                 """         m.rolname = normative_control_plane()""")
MUT_COHERENCE = ("""      if not exists (select 1 from pg_roles
                      where oid = plan_oid and rolname = plan_nom) then""",
                 """      if false then""")

CAS = [
    ("1  le manifeste n'est plus compare", "1", M,
     [("  if courant is distinct from p_manifeste then", "  if false then")], False),
    ("2  un seul des deux refus d'absence de preparation", "2", M,
     [MUT_INTENT], True),
    ("2b LES DEUX refus d'absence de preparation", "2", M,
     [MUT_INTENT, MUT_PLAN_NUL], False),
    ("3  un seul des deux controles d'identite du plan", "3", M,
     [MUT_EXEMPTION], True),
    ("3b LES DEUX controles d'identite du plan", "3", M,
     [MUT_EXEMPTION, MUT_COHERENCE], False),
    ("4  la finalisation n'est plus serialisee", "4", M,
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
    ("6  policy FOR ALL sur l'activation", "6", M,
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
    ("8  la separation plan/migrateur est retiree", "8b", M,
     [("  if d_oid = m_oid or d_nom = m_nom then", "  if false then")], False),
]

exiger_arbre_propre()
print("MUTATIONS — chaque garantie retiree doit rougir son contre-exemple")
ok = all([essayer(*c) for c in CAS])
print()
print("MUTATIONS: les huit controles portent quelque chose."
      if ok else "MUTATIONS: au moins un controle ne porte rien.")
sys.exit(0 if ok else 1)
