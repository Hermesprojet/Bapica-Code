#!/usr/bin/env python3
"""Éprouve la barrière AST sur des arbres Python fabriqués pour elle.

POURQUOI CE FICHIER EXISTE
---------------------------
La campagne des 103 a laissé survivre ``F4`` et ``F5`` — les deux mutations de
``barriere_provider.py``. La cause n'était pas une attribution ratée : le
témoin nommé était ``D8``, qui lance la barrière sur **l'arbre produit réel**.
Cet arbre est conforme ; il ne contient donc ni alias d'import trompeur ni
répertoire vide. La barrière n'y était jamais mise en difficulté, et retirer
son suivi des alias ne changeait rien à ce que ``D8`` observait.

Une garantie que rien n'exerce est indiscernable d'une garantie perdue. On
n'exerce donc plus la barrière sur l'arbre candidat : on lui fabrique des
arbres **réellement non conformes**, un par manquement, plus un arbre conforme
qui doit passer.

CE QUE CHAQUE ARBRE ÉTABLIT
----------------------------
=========================  ====================================================
arbre                      ce qu'il doit provoquer
=========================  ====================================================
``import_direct``          refus — construction du provider mémoire
``alias_import``           refus — ``import X as P`` puis ``P()``
``construction_pg``        refus — provider PostgreSQL sans la factory
``import_indirect``        refus — ``getattr(module, "…Provider")()``
``acteur_brut``            refus — acteur passé en mot-clé
``repli_memoire``          refus — repli dans un ``except``
``import_fixture``         refus — authentificateur venu d'un module de test
``zero_module``            refus — répertoire sans aucun module à inspecter
``syntaxe_invalide``       refus — fichier illisible, jamais « rien à signaler »
``conforme``               ACCEPTÉ — passe par la factory
=========================  ====================================================

Rend 0 si les dix verdicts sont ceux attendus.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

#: (nom, contenu, refus_attendu)
ARBRES: list[tuple[str, str | None, bool]] = [
    ("import_direct", """
from eurostruct_engine.ndp.confirmation import InMemoryConfirmationProvider

def demarrer():
    return InMemoryConfirmationProvider()
""", True),
    ("alias_import", """
from eurostruct_engine.ndp.confirmation import InMemoryConfirmationProvider as P

def demarrer():
    return P()
""", True),
    ("construction_pg", """
from eurostruct_engine.ndp.postgres_provider import PostgresConfirmationProvider

def demarrer(cx, auth):
    return PostgresConfirmationProvider(connexion=cx, authentificateur=auth)
""", True),
    ("import_indirect", """
import eurostruct_engine.ndp.confirmation as c

def demarrer():
    return getattr(c, "InMemoryConfirmationProvider")()
""", True),
    ("acteur_brut", """
from eurostruct_engine.ndp.provider_factory import creer_provider_de_production

def demarrer(preuve, fab, auth):
    p = creer_provider_de_production(fabrique_de_connexion=fab, authentificateur=auth)
    return p.proposer_decision(preuve, actor_id="u-1", subject_kind="k", subject_id="s")
""", True),
    ("repli_memoire", """
from eurostruct_engine.ndp.confirmation import InMemoryConfirmationProvider
from eurostruct_engine.ndp.provider_factory import creer_provider_de_production

def demarrer(fab, auth):
    try:
        return creer_provider_de_production(
            fabrique_de_connexion=fab, authentificateur=auth)
    except Exception:
        return InMemoryConfirmationProvider()
""", True),
    ("import_fixture", """
from eurostruct_engine.ndp.test_doubles import AuthentificateurFictif

def demarrer():
    return AuthentificateurFictif()
""", True),
    ("zero_module", None, True),          # répertoire sans aucun .py
    ("syntaxe_invalide", """
def demarrer(:
    pass
""", True),
    ("conforme", """
from eurostruct_engine.ndp.provider_factory import creer_provider_de_production

def demarrer(fab, auth):
    return creer_provider_de_production(
        fabrique_de_connexion=fab, authentificateur=auth)
""", False),
]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: fixtures_barriere.py <chemin-de-barriere_provider.py>",
              file=sys.stderr)
        return 2
    barriere = argv[1]
    racine = pathlib.Path(tempfile.mkdtemp(prefix="esc_fixtures_"))
    echecs: list[str] = []
    try:
        for nom, contenu, refus_attendu in ARBRES:
            d = racine / nom
            d.mkdir()
            if contenu is not None:
                (d / "module.py").write_text(contenu, encoding="utf-8")
            r = subprocess.run([sys.executable, barriere, str(d)],
                               capture_output=True, text=True, errors="replace")
            refuse = r.returncode != 0
            # LE NOMBRE DE MODULES INSPECTES EST LUI AUSSI UN FAIT. Une
            # barriere qui accepte en n'ayant rien regarde n'accepte rien.
            inspecte_zero = "0 module(s) inspecte" in r.stdout
            ok = (refuse == refus_attendu) and not (not refuse and inspecte_zero)
            etat = "REFUSE" if refuse else "accepte"
            attendu = "refus" if refus_attendu else "acceptation"
            print(f"  {'ok   ' if ok else 'ECHEC'} {nom:20s} {etat:8s} "
                  f"(attendu: {attendu})")
            if not ok:
                echecs.append(nom)
                for l in (r.stdout + r.stderr).strip().split("\n")[:2]:
                    print(f"         {l[:96]}")
    finally:
        shutil.rmtree(racine, ignore_errors=True)
    if echecs:
        print(f"\n  {len(echecs)} arbre(s) mal juges: {', '.join(echecs)}")
        return 1
    print(f"\n  les {len(ARBRES)} arbres sont juges correctement")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
