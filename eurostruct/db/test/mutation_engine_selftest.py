#!/usr/bin/env python3
"""EUROSTRUCT — AUTO-TEST DU MOTEUR DE MUTATIONS

    python3 db/test/mutation_engine_selftest.py

CE QUE CE FICHIER EXISTE POUR ETABLIR
--------------------------------------
`mutation_matrix.py` est l'INSTRUMENT DE PREUVE de toute la suite: c'est lui
qui dit si une garantie porte quelque chose. Un instrument fausse ne rend pas
un verdict faux de temps en temps — il rend un verdict faux SILENCIEUSEMENT,
et tout ce qu'il a mesure devient sans valeur.

La prise en charge MULTIFICHIER, ajoutee pour scinder le controle B en ses
deux couches, introduit precisement le defaut le plus facile a commettre:
ecrire le premier fichier, echouer sur le second, et laisser le premier MUTE
dans l'espace de travail. Les controles suivants tourneraient alors sur un
code silencieusement modifie.

CE FICHIER NE TOUCHE AUCUNE BASE. Il extrait les fonctions pures du moteur et
les eprouve sur des fichiers jetables. Il tourne donc partout, en quelques
millisecondes, et n'a aucune raison d'etre saute.

LES ANCRES D'EXTRACTION ECHOUENT BRUYAMMENT. Si le moteur est reorganise, ce
fichier ne doit pas se taire: il doit dire que l'auto-test ne s'applique plus.
"""
import importlib.util
import pathlib
import shutil
import sys
import tempfile

RACINE = pathlib.Path(__file__).resolve().parents[2]
MOD = RACINE / 'db/test/mutation_matrix.py'

echecs = []


def verifier(nom, cond, detail=""):
    if cond:
        print(f"  ok   {nom}")
    else:
        print(f"  KO   {nom}  {detail}")
        echecs.append(nom)


# On charge le SOURCE sans l'executer: le module lance une campagne au import.
src = MOD.read_text()
# On extrait les fonctions pures dont on veut prouver le comportement.
ns = {}
try:
    debut = src.index("class MotifAbsent")
    fin = src.index("def restaurer(fichier):")
    fin = src.index("\n\n\n", fin)
except ValueError:
    sys.exit("AUTO-TEST DU MOTEUR: les ancres d'extraction ne correspondent "
             "plus a mutation_matrix.py. L'auto-test ne s'applique plus et ne "
             "doit PAS etre compte comme reussi: remettre les ancres en face "
             "du moteur.")
exec(compile(src[debut:fin], str(MOD), "exec"), ns)
# `_cibles` vit plus bas; on le recupere aussi.
try:
    d2 = src.index("def _cibles(fichier, paires):")
    f2 = src.index("def _code(nom):")
except ValueError:
    sys.exit("AUTO-TEST DU MOTEUR: `_cibles`/`_code` introuvables dans "
             "mutation_matrix.py — l'auto-test ne s'applique plus.")
exec(compile(src[d2:f2], str(MOD), "exec"), ns)

tmp = pathlib.Path(tempfile.mkdtemp())
ns["ESPACE"] = str(tmp)
ns["ORIGINAUX"] = {}

A = tmp / "a.sql"
B = tmp / "b.sql"
A.write_text("garde alpha\nreste\n")
B.write_text("garde beta\nreste\n")
ORIG_A, ORIG_B = A.read_text(), B.read_text()

muter = ns["muter"]
restaurer = ns["restaurer"]
MotifAbsent = ns["MotifAbsent"]
_cibles = ns["_cibles"]

# 1. forme courte et forme longue
verifier("_cibles: forme courte",
         _cibles("a.sql", [("x", "y")]) == [("a.sql", [("x", "y")])])
verifier("_cibles: forme longue",
         _cibles([("a.sql", [("x", "y")]), ("b.sql", [("z", "w")])], None)
         == [("a.sql", [("x", "y")]), ("b.sql", [("z", "w")])])

# 2. mutation simple, puis restauration exacte
muter("a.sql", [("garde alpha", "-- retiree")])
verifier("muter: le fichier est bien modifie", A.read_text() != ORIG_A)
restaurer("a.sql")
verifier("restaurer: le texte d'avant est rendu a l'octet",
         A.read_text() == ORIG_A)

# 3. motif absent -> MotifAbsent, et RIEN n'est ecrit
leve = False
try:
    muter("a.sql", [("garde alpha", "-- ok"), ("MOTIF-ABSENT", "x")])
except MotifAbsent:
    leve = True
verifier("muter: un motif absent leve MotifAbsent", leve)
verifier("muter: aucun octet ecrit quand un motif manque",
         A.read_text() == ORIG_A,
         f"contenu={A.read_text()!r}")

# 4. ECHEC SUR LE SECOND FICHIER -> le premier ne reste pas mute.
#    C'est la propriete que la prise en charge multifichier introduit, et la
#    plus facile a casser: on ecrit A, on echoue sur B, et A reste sale.
posees = []
leve = False
try:
    for f, pr in _cibles([("a.sql", [("garde alpha", "-- retiree")]),
                          ("b.sql", [("MOTIF-ABSENT", "x")])], None):
        muter(f, pr)
        posees.append(f)
except MotifAbsent:
    leve = True
    for f in posees:
        restaurer(f)
verifier("multifichier: l'echec sur le second leve", leve)
verifier("multifichier: le PREMIER fichier est restaure",
         A.read_text() == ORIG_A, f"a.sql={A.read_text()!r}")
verifier("multifichier: le second n'a pas bouge", B.read_text() == ORIG_B)

# 5. restauration complete apres une mutation multifichier reussie
for f, pr in _cibles([("a.sql", [("garde alpha", "-- ra")]),
                      ("b.sql", [("garde beta", "-- rb")])], None):
    muter(f, pr)
verifier("multifichier: les deux fichiers sont mutes",
         A.read_text() != ORIG_A and B.read_text() != ORIG_B)
for f in ("a.sql", "b.sql"):
    restaurer(f)
verifier("multifichier: les deux fichiers sont restaures",
         A.read_text() == ORIG_A and B.read_text() == ORIG_B)

# 6. `restaurer` d'un fichier jamais mute ne casse rien
restaurer("a.sql")
verifier("restaurer: idempotent sur un fichier non mute",
         A.read_text() == ORIG_A)

# 7. une mutation identique au candidat ne change rien -> le moteur doit
#    pouvoir le detecter (c'est le refus « diff vide » d'essayer()).
muter("a.sql", [("garde alpha", "garde alpha")])
verifier("diff vide: le contenu est inchange apres une mutation identique",
         A.read_text() == ORIG_A)
restaurer("a.sql")

shutil.rmtree(tmp, ignore_errors=True)
print()
if echecs:
    print(f"AUTO-TEST DU MOTEUR: {len(echecs)} propriete(s) en echec: {echecs}")
    sys.exit(1)
print("AUTO-TEST DU MOTEUR: toutes les proprietes tiennent.")
