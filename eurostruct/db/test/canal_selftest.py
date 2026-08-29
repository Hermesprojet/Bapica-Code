#!/usr/bin/env python3
"""Auto-test du canal machine — dix-neuf formes, aucune n'a le droit de mentir.

POURQUOI CE FICHIER EXISTE
---------------------------
La campagne des 103 controles sur ``3d0acc2`` a rendu ONZE survivants. SEPT
n'etaient pas des garanties perdues : le harnais avait rougi, et le lanceur
n'avait pas su le rattacher parce qu'il cherchait ``ROUGE: <point>.`` dans une
prose ecrite pour un humain. Une ponctuation decidait si une garantie comptait
comme defendue.

Ce fichier fige les formes qui ont coute ces survivants, plus celles qui
pourraient couter les suivants.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canal_lecture as cl  # noqa: E402

ECHECS: list[str] = []


def verifier(nom: str, obtenu, attendu) -> None:
    if obtenu == attendu:
        print(f"      ok: {nom}")
    else:
        print(f"      ECHEC: {nom} — obtenu {obtenu!r}, attendu {attendu!r}")
        ECHECS.append(nom)


def canal(*evts) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                    encoding="utf-8")
    for e in evts:
        f.write((e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)) + "\n")
    f.close()
    return f.name


def ev(point, statut="ROUGE", phase="runtime", **kw) -> dict:
    d = {"protocole": 1, "point_id": point, "statut": statut, "phase": phase,
         "terminal": True}
    d.update(kw)
    return d


def statut(fichier, point, declares=None):
    lec = cl.lire(fichier, declares or {point})
    return cl.verdict_du_point(lec, point)[0]


def main() -> int:
    print("    le canal machine: la ponctuation ne decide plus d'un verdict")

    # --- 1 a 11: les formes exigees ------------------------------------
    verifier("1. « A: » au lieu de « A. » — sans effet",
             statut(canal(ev("A", effet="ECHEC: A: la finalisation refuse")), "A"),
             "KILLED_RUNTIME")
    verifier("2. prefixe humain « PR. » — sans effet",
             statut(canal(ev("D5", effet="ROUGE: PR. D5. une connexion")), "D5"),
             "KILLED_RUNTIME")
    verifier("3. identifiant apres 1000 caracteres",
             statut(canal(ev("X1", diagnostic="x" * 1200 + " AUTHORITY_TARD",
                             invariant="AUTHORITY_TARD")), "X1"),
             "KILLED_RUNTIME")
    verifier("4. prose nommant un AUTRE point",
             statut(canal(ev("MF1", statut="SUR",
                             effet="ROUGE: MF2. MF3. MF4.")), "MF1", {"MF1", "MF2"}),
             "SURVIVED")
    c5 = canal(ev("P1"), ev("P2"))
    verifier("5. deux points rouges distincts",
             (statut(c5, "P1", {"P1", "P2"}), statut(c5, "P2", {"P1", "P2"})),
             ("KILLED_RUNTIME", "KILLED_RUNTIME"))
    verifier("6. double verdict terminal = faute",
             len(cl.lire(canal(ev("P1"), ev("P1", statut="SUR")), {"P1"}).fautes), 1)
    try:
        cl.lire(canal('{"protocole":1,"point_id":"P1","stat'), {"P1"})
        verifier("7. enregistrement tronque", "accepte", "CANAL_INVALIDE")
    except cl.CanalInvalide:
        verifier("7. enregistrement tronque", "CANAL_INVALIDE", "CANAL_INVALIDE")
    try:
        cl.lire(canal({"protocole": 1, "point_id": "P", "statut": "ROUGE",
                       "phase": "runtime", "zz": 1}), {"P"})
        verifier("8. champ inconnu", "accepte", "CANAL_INVALIDE")
    except cl.CanalInvalide:
        verifier("8. champ inconnu", "CANAL_INVALIDE", "CANAL_INVALIDE")
    verifier("9. phase installation",
             statut(canal(ev("MF2", phase="installation",
                             invariant="AUTHORITY_MANIFEST_SEARCH_PATH")), "MF2"),
             "KILLED_INSTALL_ASSERTION")
    verifier("10. phase runtime",
             statut(canal(ev("R1")), "R1"), "KILLED_RUNTIME")
    verifier("11. nettoyage apres emission (teardown non terminal)",
             statut(canal(ev("T1"), ev("T1", statut="SUR", phase="teardown",
                                       terminal=False)), "T1"),
             "KILLED_RUNTIME")

    # --- 12 a 15: les invariants du protocole ---------------------------
    verifier("12. point non declare = faute",
             len(cl.lire(canal(ev("INCONNU")), {"P1"}).fautes), 1)
    verifier("13. verdict absent -> NOT_RUN, jamais vert",
             statut(canal(), "Z"), "NOT_RUN")
    verifier("14. NON_PARCOURU -> NOT_RUN",
             statut(canal(ev("N1", statut="NON_PARCOURU")), "N1"), "NOT_RUN")
    verifier("15. INFRA -> INFRA_FAILURE",
             statut(canal(ev("I1", statut="INFRA")), "I1"), "INFRA_FAILURE")

    # --- 16 a 19: le traducteur d'entree, sur les formes historiques ----
    for nom, point, prose, phase in [
        ("16. traduction « ECHEC: A: »", "A",
         "      ECHEC: A: la finalisation refuse, mais pas au motif", "runtime"),
        ("17. traduction « ROUGE: PR. D5. »", "D5",
         "      ROUGE: PR. D5. une connexion non conforme est refusee", "runtime"),
        ("18. traduction d'un refus d'installation", "MF2",
         "      ECHEC: decor: phase 1 refusee sur 0015_authority_manifest.sql:\n"
         "              invariant: AUTHORITY_MANIFEST_SEARCH_PATH", "installation"),
        ("19. la prose d'un autre point ne traduit rien", "MF1",
         "      ROUGE: MF2. ...\n      ROUGE: MF3. ...", None),
    ]:
        evts = cl.traduire_prose(prose, point)
        obtenu = evts[0]["phase"] if evts else None
        verifier(nom, obtenu, phase)

    # --- 20: l'emetteur shell produit du JSON relisible -----------------
    lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib_harnais.sh")
    f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    f.close()
    subprocess.run(
        ["bash", "-c",
         f'source "{lib}"; esc_evt "Z9" ROUGE runtime '
         f'diagnostic="ERROR: ligne 1\nligne 2 « accents » et \\"guillemets\\"" '
         f'effet="ROUGE: PR. Z9. prose"'],
        env={**os.environ, "ESC_CANAL": f.name}, capture_output=True, text=True)
    try:
        d = json.loads(open(f.name, encoding="utf-8").read().strip())
        ok = (d["point_id"] == "Z9" and "\n" in (d["diagnostic"] or ""))
    except Exception:
        ok = False
    verifier("20. l'emetteur shell echappe sauts de ligne et UTF-8", ok, True)

    print("")
    if ECHECS:
        print("=================================================")
        print(f" Canal machine: {len(ECHECS)} forme(s) mal jugee(s).")
        print("=================================================")
        return 1
    print("=================================================")
    print(" Canal machine: vingt formes, aucune ne ment.")
    print("=================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
