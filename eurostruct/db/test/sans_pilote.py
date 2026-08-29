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


#: Second volet : le HARNAIS lui-meme, prive de pilote.
#:
#: `F6` mute `provider_contract.py` pour qu'un pilote absent n'y declenche plus
#: la sortie en code 4. Le premier volet ne pouvait pas la tuer: il eprouve la
#: FACTORY, qui ne lit jamais `PILOTE_PRESENT`. Le temoin doit donc lancer le
#: harnais lui-meme dans l'environnement sans pilote, et exiger:
#:
#:   * que les proprietes structurelles et de factory s'executent QUAND MEME —
#:     un pilote absent ne doit pas devenir un laissez-passer pour la couche
#:     Python;
#:   * que le harnais rende 4 — « non executee » n'est pas « verte ».
HARNAIS = r"""
import sys, os, runpy

class RefusDePilote:
    INTERDITS = {"psycopg2", "psycopg2cffi", "psycopg", "pg8000", "asyncpg"}
    def find_spec(self, nom, chemin=None, cible=None):
        if nom.split(".")[0] in self.INTERDITS:
            raise ImportError(f"no module named {nom!r} (interdit par le test)")
        return None

sys.meta_path.insert(0, RefusDePilote())
for mod in list(sys.modules):
    if mod.split(".")[0] in RefusDePilote.INTERDITS:
        del sys.modules[mod]

try:
    import psycopg2   # noqa: F401
    print("VACUITE: le pilote reste importable")
    sys.exit(3)
except ImportError:
    pass

sys.argv = ["provider_contract.py", "base", "login", "mdp", "A", "B", "gA", "gB"]
try:
    runpy.run_path(os.environ["ESC_HARNAIS"], run_name="__main__")
except SystemExit as e:
    sys.exit(e.code if isinstance(e.code, int) else 1)
"""


def eprouver_harnais(harnais: str, moteur_src: str) -> tuple[int, str]:
    """Lance `provider_contract.py` sans pilote. Rend (code, sortie)."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import canal_lecture
    r = subprocess.run([sys.executable, "-c", HARNAIS],
                       capture_output=True, text=True, errors="replace",
                       # SANS CANAL, ET DEPUIS ICI AUSSI. Le parent nous lance
                       # deja avec `env_decor`; on le refait au site qui
                       # RELANCE reellement le harnais, pour que la propriete
                       # tienne meme lance a la main. Une seule definition —
                       # `canal_lecture.env_decor` — appliquee deux fois.
                       env={**canal_lecture.env_decor(),
                            "ESC_HARNAIS": harnais,
                            "PYTHONPATH": moteur_src,
                            # COUPE LA RECURSION. `provider_contract` lance ce
                            # fichier en D10; sans ce marqueur il se relance
                            # lui-meme sans fin. Mesure: le second volet ne
                            # rendait jamais la main.
                            "ESC_SANS_PILOTE_IMBRIQUE": "1"})
    return r.returncode, r.stdout + r.stderr


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
    if r.returncode != 0:
        return 1

    # SECOND VOLET: le harnais lui-meme, prive de pilote.
    import os
    harnais = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "provider_contract.py")
    code, sortie2 = eprouver_harnais(harnais, argv[1])
    a_execute = sum(1 for l in sortie2.split("\n")
                    if l.strip().startswith("ok: D")
                    or l.strip().startswith("ok: A"))
    if code == 3:
        print("  ECHEC le pilote reste importable dans le second volet")
        return 1
    if a_execute == 0:
        print("  ECHEC un pilote absent ETEINT la couche Python: "
              f"0 propriete executee (code {code})")
        return 1
    if code != 4:
        print(f"  ECHEC sans pilote le harnais rend {code}, attendu 4 "
              "(« non executee » n'est pas « verte »)")
        return 1
    print(f"  ok    le harnais prive de pilote execute {a_execute} propriete(s) "
          f"puis rend 4")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
