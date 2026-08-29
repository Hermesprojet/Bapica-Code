#!/usr/bin/env python3
"""L'auto-test du canal ne doit rien laisser derriere lui.

CE QUE CE CONTROLE EXISTE POUR EMPECHER
----------------------------------------
Mesure du 29/08, `canal_selftest.py` lance avec un `TMPDIR` neuf :

    108 fichiers .jsonl laisses
     27 par le chemin normal
     81 par les trois sous-processus des preuves negatives (27 chacun,
        chaque copie rejouant le chemin complet)

La cause etait `NamedTemporaryFile(delete=False)` sans reprise. Le `False`
etait NECESSAIRE — le fichier doit survivre a sa fermeture pour etre relu —
mais rien ne le reprenait ensuite.

Un harnais qui salit son `TMPDIR` a chaque execution finit par remplir le
disque d'un poste ou d'un runner, et par masquer les residus qui, eux,
comptent : bases, roles, verrous. « Aucun fichier temporaire » n'est pas une
formule de rapport, c'est une propriete qui se verifie.

CE QUE CE CONTROLE VERIFIE, ET DANS QUEL ORDRE
-----------------------------------------------
1. **chemin normal** — le selftest reussit ET son `TMPDIR` dedie est vide ;
2. **erreur controlee** — le selftest lance sur une copie MUTEE echoue ET son
   `TMPDIR` dedie est vide malgre l'echec. C'est le cas qui compte : un
   nettoyage place a la fin du chemin heureux ne s'execute pas quand un cas
   leve, et c'est precisement l'execution qui laisse le plus de traces ;
3. **decor parcouru** — le selftest publie le nombre de cas REELLEMENT
   parcourus, et ce controle refuse de conclure si ce nombre manque ou baisse.
   Un `rc == 0` ne distingue pas « tout est passe » de « rien n'a tourne » ;
4. **preuve negative** — retirer `dir=espace()` doit faire REAPPARAITRE des
   residus. Sans ce cas, les trois premiers pourraient tous passer parce que
   le selftest ne cree plus rien : un nettoyage parfait et un decor vide se
   ressemblent, vus du repertoire.

   La premiere version de ce cas neutralisait l'appel a `liberer_espace()`.
   Aucun residu ne reapparaissait — `TemporaryDirectory` porte son PROPRE
   finaliseur. L'appel explicite rend le nettoyage deterministe ; ce qui evite
   la fuite, c'est que les fichiers naissent DANS le repertoire possede. Une
   falsification qui vise la mauvaise cause ne prouve rien.

CE QU'IL NE FAIT PAS
---------------------
Il ne supprime rien hors du repertoire qu'il a cree lui-meme, et n'emploie
aucun motif large. Chaque repertoire observe est cree par ce processus et
detruit dans un `finally`.

Rend 0 si tout passe, 1 sinon.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ICI = pathlib.Path(__file__).resolve().parent
SELFTEST = ICI / "canal_selftest.py"
LECTURE = ICI / "canal_lecture.py"
LIB = ICI / "lib_harnais.sh"

#: Le chemin complet en parcourt 37 (34 quand les preuves negatives sont
#: sautees). On exige le compte du chemin complet: un selftest ampute
#: rendrait moins, et ce controle doit le voir.
CAS_MINIMUM = 37

ECHECS: list[str] = []


def verifier(nom: str, obtenu, attendu) -> None:
    if obtenu == attendu:
        print(f"      ok: {nom}")
    else:
        print(f"      ECHEC: {nom} — obtenu {obtenu!r}, attendu {attendu!r}")
        ECHECS.append(nom)


def _residus(d: pathlib.Path) -> list[str]:
    """Ce qui reste sous `d`, chemins relatifs, tries."""
    return sorted(str(p.relative_to(d)) for p in d.rglob("*"))


def _cas_publies(sortie: str) -> int:
    """Le nombre de cas que le selftest declare avoir parcourus, ou -1."""
    for ligne in reversed(sortie.splitlines()):
        if ligne.startswith("CANAL_SELFTEST_CAS="):
            try:
                return int(ligne.split("=", 1)[1])
            except ValueError:
                return -1
    return -1


def _lancer(selftest: pathlib.Path, tmp: pathlib.Path) -> tuple[int, str]:
    """Lance `selftest` avec `tmp` comme TMPDIR, et rend (code, sortie)."""
    env = {**os.environ, "TMPDIR": str(tmp)}
    env.pop("ESC_CANAL_PREUVE_NEGATIVE", None)
    r = subprocess.run([sys.executable, str(selftest)],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def cas_chemin_normal() -> None:
    """Le selftest reussit, et son TMPDIR dedie reste vide."""
    with tempfile.TemporaryDirectory(prefix="proprete-normal-") as d:
        tmp = pathlib.Path(d)
        code, sortie = _lancer(SELFTEST, tmp)
        n = _cas_publies(sortie)
        verifier("1. le selftest reussit", code, 0)
        # LE DECOR DOIT AVOIR ETE PARCOURU. Un controle de proprete sur un
        # selftest qui n'a rien execute serait vert pour la pire des raisons.
        if n < CAS_MINIMUM:
            verifier(f"2. decor parcouru ({CAS_MINIMUM} cas au moins)", n,
                     f">= {CAS_MINIMUM}")
        else:
            print(f"      ok: 2. decor parcouru — {n} cas publies")
        verifier("3. le TMPDIR dedie est vide apres succes", _residus(tmp), [])


def cas_erreur_controlee() -> None:
    """Le selftest ECHOUE, et son TMPDIR dedie reste vide malgre l'echec.

    L'echec est obtenu en mutant une COPIE du lecteur — jamais par une porte
    derobee dans le selftest. Une variable d'environnement « fais semblant
    d'echouer » serait un chemin qui n'existe que pour ce controle, donc un
    chemin que rien d'autre n'eprouve.
    """
    with tempfile.TemporaryDirectory(prefix="proprete-erreur-") as d:
        dd = pathlib.Path(d)
        copie, tmp = dd / "copie", dd / "tmp"
        copie.mkdir(); tmp.mkdir()
        for f in (SELFTEST, LECTURE, LIB):
            shutil.copy(f, copie / f.name)
        cible = copie / LECTURE.name
        texte = cible.read_text(encoding="utf-8")
        # LA MUTATION DOIT ETRE COUVERTE PAR UN CAS DU SELFTEST.
        # Premiere version: on neutralisait la verification du `statut`. Aucun
        # cas ne l'eprouve, le selftest restait VERT, et ce controle concluait
        # « le mute n'echoue pas » — vrai, mais sans rapport. On reprend donc
        # l'ancre de la preuve negative N3, dont le cas 8 depend directement.
        avant = """    inconnus = set(evt) - CHAMPS
    if inconnus:"""
        if texte.count(avant) != 1:
            verifier("4. ancre de la mutation", texte.count(avant), 1)
            return
        cible.write_text(
            texte.replace(avant, "    inconnus = set()\n    if False:"),
            encoding="utf-8")

        code, _ = _lancer(copie / SELFTEST.name, tmp)
        verifier("4. le selftest mute ECHOUE", code != 0, True)
        verifier("5. le TMPDIR dedie est vide malgre l'echec", _residus(tmp), [])


def cas_preuve_negative() -> None:
    """Neutraliser la liberation doit faire REAPPARAITRE des residus.

    Sans ce cas, les quatre precedents pourraient passer parce que le selftest
    ne cree plus rien du tout — un nettoyage parfait et un decor vide se
    ressemblent, vus du repertoire.
    """
    with tempfile.TemporaryDirectory(prefix="proprete-negative-") as d:
        dd = pathlib.Path(d)
        copie, tmp = dd / "copie", dd / "tmp"
        copie.mkdir(); tmp.mkdir()
        for f in (SELFTEST, LECTURE, LIB):
            shutil.copy(f, copie / f.name)
        # CE QUI EMPECHE REELLEMENT LA FUITE, ET CE QUI N'Y CHANGE RIEN.
        #
        # Premiere version: on neutralisait `liberer_espace()`. Aucun residu
        # ne reapparaissait — parce que `TemporaryDirectory` porte son PROPRE
        # finaliseur et detruit le repertoire a la sortie de l'interprete.
        # L'appel explicite rend le nettoyage DETERMINISTE, il n'est pas ce
        # qui evite la fuite.
        #
        # Ce qui l'evite, c'est que les fichiers soient crees DANS le
        # repertoire possede. On falsifie donc cela: `dir=espace()` retire,
        # les fichiers retombent a la racine du TMPDIR et y restent.
        cible = copie / SELFTEST.name
        texte = cible.read_text(encoding="utf-8")
        avant = "delete=False, dir=espace()"
        n = texte.count(avant)
        if n < 1:
            verifier("6. ancre de la creation dans l'espace possede", n, ">= 1")
            return
        cible.write_text(texte.replace(avant, "delete=False"), encoding="utf-8")

        _lancer(copie / SELFTEST.name, tmp)
        restants = _residus(tmp)
        verifier("6. liberation neutralisee -> des residus REAPPARAISSENT",
                 len(restants) > 0, True)


def main() -> int:
    print("    proprete du canal: l'auto-test ne laisse rien derriere lui")
    try:
        cas_chemin_normal()
        cas_erreur_controlee()
        cas_preuve_negative()
    finally:
        # Rien a liberer ici: chaque cas possede son propre repertoire et le
        # detruit par son gestionnaire de contexte. Ce `finally` existe pour
        # que l'echec d'un cas n'empeche pas l'impression du verdict.
        pass

    print("")
    if ECHECS:
        print(f"    proprete du canal: {len(ECHECS)} cas en faute", file=sys.stderr)
        return 1
    print("    proprete du canal: 6 cas, aucun residu")
    return 0


if __name__ == "__main__":
    sys.exit(main())
