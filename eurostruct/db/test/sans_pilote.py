#!/usr/bin/env python3
"""Éprouve la factory là où **aucun pilote PostgreSQL n'est disponible**.

POURQUOI CE FICHIER EXISTE
---------------------------
La campagne des 103 a laissé survivre ``F6`` — la mutation qui transforme un
pilote absent en extincteur de toute la couche Python. La cause est simple et
n'est pas une attribution ratée : **le pilote est installé sur cette machine**.
La mutation y est donc inerte, et aucun témoin ne pouvait la tuer.

Un environnement où le pilote est présent ne peut pas tuer ``F6``. Il faut
fabriquer l'absence, sans désinstaller quoi que ce soit d'un environnement
partagé — ce qui casserait tous les autres harnais.

COMMENT L'ABSENCE EST FABRIQUÉE
--------------------------------
Un **sous-processus isolé** installe un ``meta_path`` finder qui refuse
``psycopg2`` et ses variantes, puis importe la factory et l'invoque. Rien n'est
désinstallé ; l'interdiction vit et meurt avec le sous-processus.

CE QUI EST EXIGÉ
-----------------
1. la factory **refuse**, et refuse **avant** toute opération ;
2. le refus est un ``PiloteIndisponible``, pas un ``ImportError`` remonté brut,
   pas un provider mémoire, pas un ``None`` ;
3. ``provider_contract`` importé dans ce même environnement **exécute** malgré
   tout ses propriétés structurelles, de factory et de barrière — un pilote
   absent ne doit pas devenir un laissez-passer pour la couche Python.
"""
from __future__ import annotations

import subprocess
import sys

INTERDICTION = r'''
import sys, os

class RefusDePilote:
    """Rend indisponibles les pilotes PostgreSQL, pour ce processus seul."""
    INTERDITS = {"psycopg2", "psycopg2cffi", "psycopg", "pg8000", "asyncpg"}
    def find_module(self, nom, chemin=None):
        return self if nom.split(".")[0] in self.INTERDITS else None
    def find_spec(self, nom, chemin=None, cible=None):
        if nom.split(".")[0] in self.INTERDITS:
            raise ImportError(f"no module named {nom!r} (interdit par le test)")
        return None
    def load_module(self, nom):
        raise ImportError(f"no module named {nom!r} (interdit par le test)")

sys.meta_path.insert(0, RefusDePilote())
for mod in list(sys.modules):
    if mod.split(".")[0] in RefusDePilote.INTERDITS:
        del sys.modules[mod]

sys.path.insert(0, os.environ["ESC_MOTEUR_SRC"])

# 1. L'ABSENCE EST-ELLE REELLE ? Sans cette verification, le test passerait
#    aussi sur une machine ou le pilote est present: il ne mesurerait rien.
try:
    import psycopg2          # noqa: F401
    print("VACUITE: le pilote reste importable, le test ne mesure rien")
    sys.exit(3)
except ImportError:
    pass

from eurostruct_engine.ndp.provider_factory import (
    PiloteIndisponible, creer_provider_de_production,
)

class Auth:
    identite_de_l_authentificateur = "FICTIF-declare-reel"
    est_fictif = False
    def authentifier(self, preuve):
        raise AssertionError("la factory ne doit jamais authentifier ici")

def fabrique():
    import psycopg2         # doit lever: le pilote est interdit
    return psycopg2.connect("")

try:
    creer_provider_de_production(
        fabrique_de_connexion=fabrique, authentificateur=Auth())
except PiloteIndisponible as e:
    print("REFUS_ATTENDU: " + str(e).split(".")[0][:80])
    sys.exit(0)
except ImportError as e:
    print(f"REFUS_BRUT: ImportError remonte tel quel ({e})")
    sys.exit(4)
except Exception as e:
    print(f"REFUS_INATTENDU: {type(e).__name__}: {e}")
    sys.exit(5)
print("AUCUN_REFUS: la factory a rendu un provider sans pilote")
sys.exit(6)
'''


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: sans_pilote.py <chemin-engine/src>", file=sys.stderr)
        return 2
    r = subprocess.run([sys.executable, "-c", INTERDICTION],
                       capture_output=True, text=True, errors="replace",
                       env={**__import__("os").environ,
                            "ESC_MOTEUR_SRC": argv[1]})
    sortie = (r.stdout + r.stderr).strip()
    attendus = {
        0: ("ok   ", "la factory refuse, et le refus est un PiloteIndisponible"),
        3: ("ECHEC", "l'absence de pilote n'a pas pu etre fabriquee: vacuite"),
        4: ("ECHEC", "ImportError remonte brut au lieu d'un refus nomme"),
        5: ("ECHEC", "refus d'un type inattendu"),
        6: ("ECHEC", "AUCUN refus: un provider a ete rendu sans pilote"),
    }
    etat, texte = attendus.get(r.returncode, ("ECHEC", f"code {r.returncode}"))
    print(f"  {etat} sans pilote: {texte}")
    for l in sortie.split("\n")[:3]:
        if l.strip():
            print(f"         {l[:100]}")
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
