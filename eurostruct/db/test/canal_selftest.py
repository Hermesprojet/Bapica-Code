#!/usr/bin/env python3
"""Auto-test du canal machine — aucune forme n'a le droit de mentir.

POURQUOI CE FICHIER EXISTE
---------------------------
La campagne des 103 controles sur ``3d0acc2`` a rendu ONZE survivants. SEPT
n'etaient pas des garanties perdues : le harnais avait rougi, et le lanceur
n'avait pas su le rattacher parce qu'il cherchait ``ROUGE: <point>.`` dans une
prose ecrite pour un humain. Une ponctuation decidait si une garantie comptait
comme defendue.

Ce fichier fige les formes qui ont coute ces survivants, les invariants du
protocole 2, et — depuis L5 — une PREUVE NEGATIVE : neutraliser le lecteur
JSONL ou rouvrir l'attribution textuelle doit faire echouer cet auto-test.
Sans elle, rien ne prouverait que ces cas savent encore voir.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canal_lecture as cl  # noqa: E402

ECHECS: list[str] = []

# ---------------------------------------------------------------------------
# UN ESPACE POSSEDE, NETTOYE DANS UN `finally`
# ---------------------------------------------------------------------------
# CE FICHIER LAISSAIT 108 FICHIERS PAR EXECUTION. Mesure du 29/08 avec un
# TMPDIR neuf: 27 par le chemin normal, et 81 par les trois sous-processus des
# preuves negatives — chaque copie rejouant le chemin complet.
#
# La cause etait `NamedTemporaryFile(delete=False)` sans `unlink`. Le `False`
# etait NECESSAIRE — le fichier doit survivre a sa fermeture pour etre relu —
# mais rien ne le reprenait ensuite.
#
# On ne compte donc plus les fichiers un a un: tout est cree DANS un
# repertoire que ce processus possede, et ce repertoire est detruit dans un
# `finally`. Un `unlink` par fichier oublierait le prochain; un repertoire
# possede n'oublie rien, et ne peut rien detruire au-dehors.
_ESPACE: tempfile.TemporaryDirectory | None = None


def espace() -> str:
    """Le repertoire possede par cette execution. Cree a la demande."""
    global _ESPACE
    if _ESPACE is None:
        _ESPACE = tempfile.TemporaryDirectory(prefix="canal-selftest-")
    return _ESPACE.name


def liberer_espace() -> None:
    """Detruit le repertoire possede — et LUI SEUL."""
    global _ESPACE
    if _ESPACE is not None:
        _ESPACE.cleanup()
        _ESPACE = None


RUN = "run-selftest"
SHA = "0" * 40
#: Garde de recursion: la preuve negative relance CE fichier sur une copie
#: mutee. Sans garde, chaque copie relancerait la preuve a son tour.
IMBRIQUE = bool(os.environ.get("ESC_CANAL_PREUVE_NEGATIVE"))


#: Cas REELLEMENT parcourus. Ce n'est pas une constante declaree: c'est un
#: compteur, incremente par chaque verdict rendu. Une constante mentirait le
#: jour ou une boucle serait videe; un compteur ne le peut pas.
PARCOURUS = [0]


def verifier(nom: str, obtenu, attendu) -> None:
    PARCOURUS[0] += 1
    if obtenu == attendu:
        print(f"      ok: {nom}")
    else:
        print(f"      ECHEC: {nom} — obtenu {obtenu!r}, attendu {attendu!r}")
        ECHECS.append(nom)


def canal(*evts) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                    dir=espace(), encoding="utf-8")
    for e in evts:
        f.write((e if isinstance(e, str)
                 else json.dumps(e, ensure_ascii=False)) + "\n")
    f.close()
    return f.name


_SEQ = [0]


def ev(controle, statut="ROUGE", phase="runtime", point=None, **kw) -> dict:
    _SEQ[0] += 1
    d = {"protocole": 2, "run_id": RUN, "sha": SHA,
         "controle_id": controle, "point_id": point or controle,
         "statut": statut, "phase": phase, "seq": _SEQ[0], "terminal": True}
    d.update(kw)
    return d


def statut(fichier, controle, declares=None):
    lec = cl.lire(fichier, declares or {controle}, run_id=RUN, sha=SHA)
    return cl.verdict_du_controle(lec, controle)[0]


def invalide(evt_ou_texte, declares={"P"}) -> str:
    """Rend « CANAL_INVALIDE » si la lecture refuse, « accepte » sinon."""
    try:
        cl.lire(canal(evt_ou_texte), declares, run_id=RUN, sha=SHA)
        return "accepte"
    except cl.CanalInvalide:
        return "CANAL_INVALIDE"


def cas_protocole() -> None:
    # --- les formes qui ont coute des survivants ------------------------
    verifier("1. « A: » au lieu de « A. » — sans effet",
             statut(canal(ev("A", effet="ECHEC: A: la finalisation refuse")), "A"),
             "KILLED_RUNTIME")
    verifier("2. prefixe humain « PR. » — sans effet",
             statut(canal(ev("D5", effet="ROUGE: PR. D5. une connexion")), "D5"),
             "KILLED_RUNTIME")
    verifier("3. identifiant apres 1000 caracteres",
             statut(canal(ev("X1", diagnostic={"nature": "tard",
                                               "detail": "x" * 1200},
                             invariant="AUTHORITY_TARD")), "X1"),
             "KILLED_RUNTIME")
    verifier("4. prose nommant un AUTRE controle",
             statut(canal(ev("MF1", statut="SUR",
                             effet="ROUGE: MF2. MF3. MF4.")),
                    "MF1", {"MF1", "MF2"}),
             "SURVIVED")
    c5 = canal(ev("P1"), ev("P2"))
    verifier("5. deux controles rouges distincts",
             (statut(c5, "P1", {"P1", "P2"}), statut(c5, "P2", {"P1", "P2"})),
             ("KILLED_RUNTIME", "KILLED_RUNTIME"))
    verifier("6. double verdict terminal = faute",
             cl.lire(canal(ev("P1"), ev("P1", statut="SUR")), {"P1"},
                     run_id=RUN, sha=SHA).double_terminal, 1)
    verifier("7. enregistrement tronque",
             invalide('{"protocole":2,"run_id":"r","sha":"s","controle_id":"P","stat'),
             "CANAL_INVALIDE")
    verifier("8. champ inconnu", invalide(dict(ev("P"), zz=1)), "CANAL_INVALIDE")
    verifier("9. phase installation",
             statut(canal(ev("MF2", phase="installation",
                             invariant="AUTHORITY_MANIFEST_SEARCH_PATH")), "MF2"),
             "KILLED_INSTALL_ASSERTION")
    verifier("10. phase runtime", statut(canal(ev("R1")), "R1"), "KILLED_RUNTIME")
    verifier("11. teardown non terminal n'ecrase pas le verdict",
             statut(canal(ev("T1"), ev("T1", statut="SUR", phase="teardown",
                                       terminal=False)), "T1"),
             "KILLED_RUNTIME")

    # --- les invariants ---------------------------------------------------
    verifier("12. controle non declare = faute comptee",
             cl.lire(canal(ev("INCONNU")), {"P1"},
                     run_id=RUN, sha=SHA).unknown_event, 1)
    verifier("13. verdict absent -> NOT_RUN, jamais vert",
             statut(canal(), "Z"), "NOT_RUN")
    verifier("14. NON_PARCOURU -> NOT_RUN",
             statut(canal(ev("N1", statut="NON_PARCOURU")), "N1"), "NOT_RUN")
    verifier("15. INFRA -> INFRA_FAILURE",
             statut(canal(ev("I1", statut="INFRA")), "I1"), "INFRA_FAILURE")

    # --- protocole 2: run, SHA, sequence, diagnostic structure -----------
    autre_run = cl.lire(canal(dict(ev("P"), run_id="run-autre")), {"P"},
                        run_id=RUN, sha=SHA)
    verifier("21. evenement d'un AUTRE run: rejete et compte",
             (autre_run.cross_run_event, autre_run.terminaux), (1, {}))
    verifier("21b. et le controle devient NOT_RUN, jamais vert",
             cl.verdict_du_controle(autre_run, "P")[0], "NOT_RUN")
    autre_sha = cl.lire(canal(dict(ev("P"), sha="f" * 40)), {"P"},
                        run_id=RUN, sha=SHA)
    verifier("22. evenement d'un AUTRE sha: rejete et compte",
             (autre_sha.cross_run_event, autre_sha.terminaux), (1, {}))
    verifier("23. protocole 1 (version inconnue) = campagne invalide",
             invalide(dict(ev("P"), protocole=1)), "CANAL_INVALIDE")
    e_sans_seq = ev("P"); del e_sans_seq["seq"]
    verifier("24. seq manquante = campagne invalide",
             invalide(e_sans_seq), "CANAL_INVALIDE")
    verifier("25. seq non entiere = campagne invalide",
             invalide(dict(ev("P"), seq="12")), "CANAL_INVALIDE")
    verifier("26. diagnostic en prose libre = campagne invalide",
             invalide(dict(ev("P"), diagnostic="une phrase")), "CANAL_INVALIDE")
    verifier("27. diagnostic a cle inconnue = campagne invalide",
             invalide(dict(ev("P"), diagnostic={"zz": 1})), "CANAL_INVALIDE")
    e1 = ev("P"); e2 = dict(ev("P"), seq=e1["seq"], statut="SUR")
    verifier("30. meme (controle, seq) deux fois = refuse, le premier tient",
             statut(canal(e1, e2), "P"), "KILLED_RUNTIME")

    # --- le traducteur: nomme, et refusant par defaut ---------------------
    for nom, controle, prose, phase in [
        ("16. traduction « ECHEC: A: »", "A",
         "      ECHEC: A: la finalisation refuse, mais pas au motif", "runtime"),
        ("17. traduction « ROUGE: PR. D5. »", "D5",
         "      ROUGE: PR. D5. une connexion non conforme est refusee", "runtime"),
        ("18. traduction d'un refus d'installation", "MF2",
         "      ECHEC: decor: phase 1 refusee sur 0015_authority_manifest.sql:\n"
         "              invariant: AUTHORITY_MANIFEST_SEARCH_PATH", "installation"),
        ("19. la prose d'un autre controle ne traduit rien", "MF1",
         "      ROUGE: MF2. ...\n      ROUGE: MF3. ...", None),
    ]:
        evts = cl.traduire_prose(prose, controle, point=controle,
                                 harnais="db/test/seal_contract.sh",
                                 run_id=RUN, sha=SHA)
        verifier(nom, evts[0]["phase"] if evts else None, phase)

    try:
        cl.traduire_prose("ROUGE: P.", "P", point="P",
                          harnais="db/test/harness_safety_selftest.sh",
                          run_id=RUN, sha=SHA)
        r28 = "traduit"
    except cl.TraducteurRefuse:
        r28 = "REFUSE"
    # LA DISTINCTION CONTROLE / POINT, FIGEE. La prose nomme « D9 »; le
    # controle s'appelle « F4 ». Chercher le controle ne trouve rien et rend
    # SURVIVANT un controle tue depuis des semaines — mesure du 29/08.
    ev_f4 = cl.traduire_prose("      ROUGE: PR. D9. la barriere refuse", "F4",
                              point="D9", harnais="db/test/provider_contract.sh",
                              run_id=RUN, sha=SHA)
    verifier("19b. la prose nomme le POINT, l'evenement porte le CONTROLE",
             (ev_f4[0]["controle_id"], ev_f4[0]["point_id"]) if ev_f4 else None,
             ("F4", "D9"))

    verifier("28. harnais MIGRE: le traducteur refuse (pas de repli silencieux)",
             r28, "REFUSE")

    # 29. LA PROSE NE PEUT RIEN, MEME EN NOMMANT DES CONTROLES. Un canal qui
    # dit SUR reste SUR, quelle que soit la prose qui l'accompagne.
    verifier("29. prose truffee d'identifiants: aucun effet sur le verdict",
             statut(canal(ev("P", statut="SUR",
                             effet="ROUGE: P. ECHEC: P: ROUGE: PR. P.")), "P"),
             "SURVIVED")


def cas_emetteur() -> None:
    lib = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "lib_harnais.sh")
    f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, dir=espace())
    f.close()
    env = {**os.environ, "ESC_CANAL": f.name, "ESC_RUN_ID": RUN,
           "ESC_SHA": SHA, "ESC_CONTROLE_ID": "S9", "ESC_POINT_ATTENDU": "19.9"}
    subprocess.run(
        ["bash", "-c",
         f'source "{lib}"; esc_evt "19.9" ROUGE runtime '
         f'detail="ERROR: ligne 1\nligne 2 « accents » et \\"guillemets\\"" '
         f'nature=selftest effet="ROUGE: PR. Z9. prose"'],
        env=env, capture_output=True, text=True)
    try:
        d = json.loads(open(f.name, encoding="utf-8").read().strip())
        ok = (d["controle_id"] == "S9" and d["point_id"] == "19.9"
              and d["run_id"] == RUN and d["sha"] == SHA
              and isinstance(d["seq"], int) and d["terminal"] is True
              and "\n" in d["diagnostic"]["detail"])
    except Exception:
        ok = False
    verifier("31. l'emetteur estampille run, sha, controle, seq et echappe l'UTF-8",
             ok, True)

    # 32. UN POINT QUI N'EST PAS LE POINT ATTENDU N'EST PAS TERMINAL. Sans
    # cela, un harnais rougissant sur plusieurs points produirait plusieurs
    # verdicts terminaux et invaliderait la campagne a tort.
    g = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, dir=espace()); g.close()
    subprocess.run(
        ["bash", "-c", f'source "{lib}"; esc_evt "19.5" ROUGE runtime'],
        env={**env, "ESC_CANAL": g.name}, capture_output=True, text=True)
    try:
        d = json.loads(open(g.name, encoding="utf-8").read().strip())
        ok32 = d["terminal"] is False
    except Exception:
        ok32 = False
    verifier("32. un point autre que l'attendu est enregistre, non terminal",
             ok32, True)

    # 33. SANS CONTEXTE, L'EMETTEUR REFUSE. Un evenement qu'on ne peut
    # rattacher ni au run ni au SHA vaut moins que pas d'evenement du tout:
    # il ferait conclure NOT_RUN sans qu'on sache pourquoi.
    h = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, dir=espace()); h.close()
    nu = {k: v for k, v in os.environ.items()
          if k not in {"ESC_RUN_ID", "ESC_SHA", "ESC_CONTROLE_ID"}}
    r = subprocess.run(
        ["bash", "-c", f'source "{lib}"; esc_evt "P" ROUGE runtime'],
        env={**nu, "ESC_CANAL": h.name}, capture_output=True, text=True)
    verifier("33. emission sans run/sha/controle: refus, canal vide",
             (r.returncode != 0, os.path.getsize(h.name)), (True, 0))


#: Mutations du LECTEUR. Chacune doit faire ECHOUER cet auto-test.
PREUVES_NEGATIVES = [
    ("N1 le rejet des evenements d'un autre run/sha est retire",
     '''        if (run_id is not None and evt["run_id"] != run_id) or \\
           (sha is not None and evt["sha"] != sha):''',
     '''        if False:'''),
    ("N2 le traducteur accepte n'importe quel harnais (repli textuel rouvert)",
     '''    if harnais not in HARNAIS_NON_MIGRES:''',
     '''    if False:'''),
    ("N3 les champs inconnus ne sont plus refuses",
     '''    inconnus = set(evt) - CHAMPS
    if inconnus:''',
     '''    inconnus = set()
    if False:'''),
]


def cas_preuve_negative() -> None:
    """Neutraliser le lecteur doit faire ROUGIR cet auto-test.

    Sans cette preuve, les trente-trois cas ci-dessus pourraient tous passer
    parce qu'ils ne regardent rien — c'est la faute meme des onze survivants,
    prouver une garantie avec l'exemple qu'elle couvre deja.
    """
    ici = pathlib.Path(__file__).resolve().parent
    for nom, avant, apres in PREUVES_NEGATIVES:
        with tempfile.TemporaryDirectory() as d:
            dd = pathlib.Path(d)
            shutil.copy(ici / "canal_lecture.py", dd / "canal_lecture.py")
            shutil.copy(ici / "canal_selftest.py", dd / "canal_selftest.py")
            shutil.copy(ici / "lib_harnais.sh", dd / "lib_harnais.sh")
            cible = dd / "canal_lecture.py"
            texte = cible.read_text(encoding="utf-8")
            if texte.count(avant) != 1:
                verifier(nom, f"ancre absente ({texte.count(avant)})", "1 occurrence")
                continue
            cible.write_text(texte.replace(avant, apres), encoding="utf-8")
            r = subprocess.run([sys.executable, str(dd / "canal_selftest.py")],
                               capture_output=True, text=True,
                               env={**os.environ,
                                    "ESC_CANAL_PREUVE_NEGATIVE": "1"})
            verifier(nom, "ROUGE" if r.returncode != 0 else "VERT", "ROUGE")


#: Nombre de cas que ce fichier PARCOURT. Publie a la sortie, et exige par le
#: controle de proprete: un `rc == 0` ne distingue pas « tout est passe » de
#: « rien n'a ete execute ».
CAS_ATTENDUS = 35  # chemin complet, preuves negatives comprises


def _corps() -> int:
    print("    le canal machine: la ponctuation ne decide plus d'un verdict")
    cas_protocole()
    cas_emetteur()
    if not IMBRIQUE:
        print("      --- preuve negative: le lecteur neutralise doit rougir ---")
        cas_preuve_negative()

    print("")
    if ECHECS:
        print("=================================================")
        print(f" Canal machine: {len(ECHECS)} forme(s) mal jugee(s).")
        print("=================================================")
        return 1
    print("=================================================")
    print(" Canal machine: protocole 2, aucune forme ne ment,")
    print(" et le lecteur neutralise fait rougir l'auto-test.")
    print("=================================================")
    return 0


def main() -> int:
    """Enveloppe `_corps()` et libere l'espace possede, quoi qu'il arrive.

    LE `finally` EST LE POINT. Un nettoyage place a la fin du chemin heureux
    ne s'execute pas quand un cas leve, et c'est precisement l'execution qui
    laisse le plus de traces. Le repertoire possede part dans les deux cas.
    """
    try:
        code = _corps()
    finally:
        # LE COMPTE EST PUBLIE AVANT LA LIBERATION, et meme en cas d'echec:
        # un controle qui ne saurait pas combien de cas ont ete parcourus ne
        # pourrait pas distinguer un decor vide d'un decor conforme.
        print(f"CANAL_SELFTEST_CAS={PARCOURUS[0]}")
        liberer_espace()
    return code


if __name__ == "__main__":
    sys.exit(main())
