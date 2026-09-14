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
    # LA DISTINCTION CONTROLE / POINT, FIGEE. La prose nomme « MF2 »; le
    # controle s'appelle « MF2 l'assertion... » cote matrice, et surtout la
    # recherche porte sur le POINT. Chercher le CONTROLE dans la prose ne
    # trouve rien et rend SURVIVANT un controle tue depuis des semaines —
    # mesure du 29/08.
    #
    # LE HARNAIS CITE ICI A CHANGE, ET C'EST UN FAIT DE MIGRATION. Ce cas
    # portait sur `provider_contract.sh` et son point `D9`. Ce harnais EMET
    # depuis le 29/08: le traducteur le refuse desormais, et l'ancienne
    # redaction faisait lever cet auto-test. On reancre la propriete sur un
    # harnais ENCORE non migre — elle ne concerne pas un fichier en
    # particulier — et le refus de l'ancien devient le cas 19c.
    ev_pt = cl.traduire_prose("      ROUGE: AH. MF2. le manifeste refuse", "MF2c",
                              point="MF2",
                              harnais="db/test/authority_sql_hardening.sh",
                              run_id=RUN, sha=SHA)
    verifier("19b. la prose nomme le POINT, l'evenement porte le CONTROLE",
             (ev_pt[0]["controle_id"], ev_pt[0]["point_id"]) if ev_pt else None,
             ("MF2c", "MF2"))

    # 19c. LE HARNAIS MIGRE N'A PLUS DE REPLI TEXTUEL.
    try:
        cl.traduire_prose("      ROUGE: PR. D9. la barriere refuse", "F4",
                          point="D9", harnais="db/test/provider_contract.sh",
                          run_id=RUN, sha=SHA)
        r19c = "traduit"
    except cl.TraducteurRefuse:
        r19c = "REFUSE"
    verifier("19c. provider_contract.sh migre: le traducteur refuse",
             r19c, "REFUSE")

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


#: Mutations du LECTEUR ou de L'EMETTEUR. Chacune doit faire ECHOUER cet
#: auto-test. Le fichier est nomme: le canal a deux bouts, et neutraliser
#: l'emission est aussi grave que neutraliser la lecture.
PREUVES_NEGATIVES = [
    ("N4 l'emission d'un point declare est neutralisee", "lib_harnais.sh",
     '  esc_evt "$pt" ROUGE runtime "$@"',
     '  : neutralise'),
    ("N1 le rejet des evenements d'un autre run/sha est retire", "canal_lecture.py",
     '''        if (run_id is not None and evt["run_id"] != run_id) or \\
           (sha is not None and evt["sha"] != sha):''',
     '''        if False:'''),
    ("N2 le traducteur accepte n'importe quel harnais (repli textuel rouvert)",
     "canal_lecture.py",
     '''    if harnais not in HARNAIS_NON_MIGRES:''',
     '''    if False:'''),
    ("N3 les champs inconnus ne sont plus refuses", "canal_lecture.py",
     '''    inconnus = set(evt) - CHAMPS
    if inconnus:''',
     '''    inconnus = set()
    if False:'''),
    ("N5 un sous-processus de decor herite de nouveau du canal",
     "canal_lecture.py",
     '''    for cle in CONTEXTE_CANAL:
        env.pop(cle, None)''',
     '''    for cle in ():
        env.pop(cle, None)'''),
    ("N6 le garde des points declares est neutralise", "lib_harnais.sh",
     '''  case "$ESC_POINTS_DECLARES" in *" $1 "*) return 0 ;; esac''',
     '''  return 0'''),
]


def cas_migration() -> None:
    """Les primitives sur lesquelles repose un harnais MIGRE.

    UN HARNAIS MIGRE NE PEUT PLUS RETOMBER SUR LA PROSE. Ces cas eprouvent les
    deux fonctions dont depend cette propriete — `esc_point_rouge` et
    `esc_conclure` — et le refus du traducteur pour un harnais migre.

    Ils sont RAPIDES a dessein: eprouver la migration en relancant
    `finalisation_contract.sh` couterait dix minutes par cas, et un controle
    trop cher finit par etre saute.
    """
    lib = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "lib_harnais.sh")

    def lancer(script: str, attendu: str = "2b") -> tuple[list[dict], str]:
        """Rend (evenements, stderr) — le second sert au garde de declaration."""
        f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False,
                                        dir=espace())
        f.close()
        r = subprocess.run(
            ["bash", "-c", f'source "{lib}"; {script}'],
            env={**os.environ, "ESC_CANAL": f.name, "ESC_RUN_ID": RUN,
                 "ESC_SHA": SHA, "ESC_CONTROLE_ID": "MIG",
                 "ESC_POINT_ATTENDU": attendu},
            capture_output=True, text=True)
        with open(f.name, encoding="utf-8") as fh:
            evts = [json.loads(ligne) for ligne in fh if ligne.strip()]
        return evts, r.stderr

    def emettre(script: str, attendu: str = "2b") -> list[dict]:
        return lancer(script, attendu)[0]

    # 34. LE POINT EST DECLARE, PAS EXTRAIT DE LA PROSE.
    e = emettre('esc_point_rouge 2b nature=t detail="peu importe le texte"')
    verifier("34. esc_point_rouge declare le point et le rend terminal",
             (len(e), e[0]["point_id"], e[0]["statut"], e[0]["terminal"])
             if e else None, (1, "2b", "ROUGE", True))

    # 35. UN AUTRE POINT EST ENREGISTRE, MAIS N'ATTRIBUE RIEN.
    e = emettre('esc_point_rouge 2a nature=t detail="autre point"')
    verifier("35. un point autre que l'attendu n'est pas terminal",
             (len(e), e[0]["terminal"]) if e else None, (1, False))

    # 36. LE POINT QUI PASSE PRODUIT UN SUR — jamais un silence.
    # Sans cela le lanceur lirait NOT_RUN — « pas mesure » — la ou il faut
    # lire SURVIVED — « la garantie a ete retiree et rien n'a rougi ».
    e = emettre('esc_conclure')
    verifier("36. esc_conclure rend SUR quand le point attendu n'a pas rougi",
             (len(e), e[0]["statut"], e[0]["point_id"], e[0]["terminal"])
             if e else None, (1, "SUR", "2b", True))

    # 37. ET N'ECRASE PAS UN ROUGE DEJA RENDU.
    e = emettre('esc_point_rouge 2b nature=t detail="rouge"; esc_conclure')
    verifier("37. esc_conclure n'ecrase pas un rouge deja rendu",
             [(x["statut"], x["terminal"]) for x in e], [("ROUGE", True)])

    # 37b. UN TROU EST DIFFERE — il n'ecrit rien tant qu'on n'a pas conclu.
    # L'emettre aussitot le graverait avant qu'un rouge plus tardif sur le
    # meme point ait pu se produire (cas 37d).
    e = emettre('esc_point_troue 2b "decor absent"')
    verifier("37b. un trou seul n'ecrit rien avant la conclusion", len(e), 0)

    # 37c. ET IL DEVIENT NON_PARCOURU A LA CONCLUSION, JAMAIS SUR.
    # `NON_PARCOURU` vaut NOT_RUN cote lanceur — « on ne sait rien » — et
    # jamais SURVIVED — « la garantie retiree n'a rien casse ». Confondre les
    # deux, c'est declarer prouve un scenario qu'on n'a pas joue.
    e = emettre('esc_point_troue 2b "decor absent"; esc_conclure')
    verifier("37c. un point troue conclut NON_PARCOURU, et une seule fois",
             [(x["statut"], x["terminal"], x["diagnostic"]["detail"]) for x in e],
             [("NON_PARCOURU", True, "decor absent")])

    # 37d. LE ROUGE L'EMPORTE SUR UN TROU DEJA CONSTATE.
    #
    # LE CAS QUI JUSTIFIE LE REPORT. Quatre verdicts declares de
    # `migration_postconditions.sh` partagent le point `Y1`. Que le premier
    # chemin soit troue et le second rouge est ordinaire — et si le trou avait
    # ete grave aussitot, il aurait tenu: le premier verdict terminal gagne. Le
    # controle serait ressorti « non mesure » alors qu'il venait d'etre tue.
    e = emettre('esc_point_troue 2b "decor absent"; '
                'esc_point_rouge 2b nature=t detail="rouge tardif"; esc_conclure')
    verifier("37d. un rouge tardif l'emporte sur un trou anterieur",
             [(x["statut"], x["terminal"]) for x in e], [("ROUGE", True)])

    # 37e. ET LE PREMIER ROUGE GAGNE — comme le traducteur, qui rendait
    # `[_evt(...)]` sur la premiere ligne portant le point et s'arretait.
    e = emettre('esc_point_rouge 2b nature=t detail="premier"; '
                'esc_point_rouge 2b nature=t detail="second"; esc_conclure')
    verifier("37e. deux rouges sur un meme point: un seul verdict, le premier",
             [(x["statut"], x["diagnostic"]["detail"]) for x in e],
             [("ROUGE", "premier")])

    # 38. LE TRADUCTEUR REFUSE UN HARNAIS MIGRE.
    try:
        cl_local = cl.traduire_prose(
            "ROUGE: 2b.", "2b", point="2b",
            harnais="db/test/finalisation_contract.sh", run_id=RUN, sha=SHA)
        r = "traduit"
    except cl.TraducteurRefuse:
        r = "REFUSE"
    verifier("38. finalisation_contract.sh migre: le traducteur refuse",
             r, "REFUSE")

    # 38b. UN POINT DECLARE PASSE SANS BRUIT.
    e, err = lancer('esc_points_declares 2a 2b 3; '
                    'esc_point_rouge 2b nature=t detail="declare"')
    verifier("38b. un point declare n'attire aucune faute",
             (len(e), "FAUTE DE DECLARATION" in err), (1, False))

    # 38c. UN POINT NON DECLARE EST UNE FAUTE — MAIS L'EVENEMENT PART.
    #
    # LES DEUX MOITIES COMPTENT, ET LA SECONDE PLUS QUE LA PREMIERE. Taire
    # l'evenement transformerait une erreur de tenue de liste en ABSENCE DE
    # PREUVE: le controle passerait de « tue » a « non mesure » pour une faute
    # de declaration. On emet donc, et on se plaint.
    e, err = lancer('esc_points_declares 3; '
                    'esc_point_rouge 2b nature=t detail="non declare"')
    verifier("38c. un point non declare: faute imprimee, evenement emis quand meme",
             (len(e), "FAUTE DE DECLARATION" in err), (1, True))

    # 38d. ET LE GARDE EST INERTE TANT QUE RIEN N'EST DECLARE.
    # Les harnais non encore migres n'appellent pas `esc_points_declares`; le
    # garde ne doit pas se mettre a crier sur chacun d'eux.
    e, err = lancer('esc_point_rouge 2b nature=t detail="aucune declaration"')
    verifier("38d. sans declaration, le garde se tait",
             (len(e), "FAUTE DE DECLARATION" in err), (1, False))


def cas_decor() -> None:
    """Un sous-processus de DECOR ne rend pas de verdict.

    CE QUE CES CAS EXISTENT POUR EMPECHER. Mesure du 29/08, premier rejeu
    filtre apres la migration de `provider_contract.sh`: les sept controles de
    la factory sont tombes en `INFRA_FAILURE`, `double_terminal 7`.
    `provider_contract.py` lance `sans_pilote.py`, qui RELANCE
    `provider_contract.py` prive de pilote — c'est tout l'objet de D10.
    L'enfant heritait de `ESC_CANAL` et ecrivait son PROPRE verdict terminal
    pour le meme controle: « SUR puis SUR », « ROUGE puis SUR ».

    Un harnais qui se relance lui-meme double son verdict. Ce n'est pas propre
    a `provider_contract`: toute migration future qui lance un decor herite du
    meme piege, et c'est pourquoi la regle est ici et non la-bas.

    LE CAS 40 EST LE SEUL QUI PROUVE QUELQUE CHOSE. « L'enfant n'ecrit rien »
    serait vrai aussi d'un enfant qui n'emet jamais — un canal muet et un
    canal correctement prive se ressemblent, vus du fichier. On exige donc
    D'ABORD que l'heritage nu ecrive REELLEMENT, puis que `env_decor` l'en
    empeche. Sans la premiere moitie, la seconde ne mesure rien.
    """
    ici = os.path.dirname(os.path.abspath(__file__))
    # Un enfant minimal qui CONCLUT: c'est exactement ce que fait le
    # `finally` d'un harnais Python migre.
    enfant = (f"import sys; sys.path.insert(0, {ici!r});"
              " import canal_lecture; canal_lecture.conclure([])")
    contexte = {"ESC_CANAL": None, "ESC_RUN_ID": RUN, "ESC_SHA": SHA,
                "ESC_CONTROLE_ID": "DEC", "ESC_POINT_ATTENDU": "d1"}

    def lancer(env: dict, canal: str) -> int:
        """Lance l'enfant et rend le nombre d'evenements qu'il a ecrits."""
        subprocess.run([sys.executable, "-c", enfant], env=env,
                       capture_output=True, text=True)
        with open(canal, encoding="utf-8") as f:
            return sum(1 for ligne in f if ligne.strip())

    # 39. `env_decor` retire les cinq variables, et RIEN d'autre.
    temoin = {**os.environ, **{k: (v or "x") for k, v in contexte.items()},
              "ESC_TEMOIN_A_CONSERVER": "present"}
    net = cl.env_decor(temoin)
    verifier("39. env_decor retire le contexte du canal et conserve le reste",
             (sorted(k for k in cl.CONTEXTE_CANAL if k in net),
              net.get("ESC_TEMOIN_A_CONSERVER")),
             ([], "present"))

    # 40. L'HERITAGE NU ECRIT — puis `env_decor` l'en empeche.
    f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, dir=espace())
    f.close()
    nu = {**os.environ, **contexte, "ESC_CANAL": f.name}
    verifier("40. sans env_decor, un sous-processus ECRIT sur le canal parent",
             lancer(nu, f.name), 1)

    g = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, dir=espace())
    g.close()
    verifier("41. avec env_decor, il n'ecrit rien",
             lancer(cl.env_decor({**nu, "ESC_CANAL": g.name}), g.name), 0)

    # 42. ET LA CONSEQUENCE COMPTABLE EST BIEN CELLE QU'ON A MESUREE.
    # Le parent conclut, l'enfant heritant conclut aussi: le lecteur doit voir
    # un SECOND verdict terminal. C'est ce que la campagne a rapporte sept
    # fois; on l'ancre ici pour que le lien fix/invariant soit eprouve.
    h = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, dir=espace())
    h.close()
    double = {**os.environ, **contexte, "ESC_CANAL": h.name}
    lancer(double, h.name)          # le « parent »
    lancer(double, h.name)          # l'enfant qui a herite
    lec = cl.lire(h.name, {"DEC"}, run_id=RUN, sha=SHA)
    verifier("42. deux conclusions sur le meme controle: double_terminal",
             lec.double_terminal, 1)


def cas_preuve_negative() -> None:
    """Neutraliser le lecteur doit faire ROUGIR cet auto-test.

    Sans cette preuve, les trente-trois cas ci-dessus pourraient tous passer
    parce qu'ils ne regardent rien — c'est la faute meme des onze survivants,
    prouver une garantie avec l'exemple qu'elle couvre deja.
    """
    ici = pathlib.Path(__file__).resolve().parent
    for nom, fichier, avant, apres in PREUVES_NEGATIVES:
        with tempfile.TemporaryDirectory() as d:
            dd = pathlib.Path(d)
            shutil.copy(ici / "canal_lecture.py", dd / "canal_lecture.py")
            shutil.copy(ici / "canal_selftest.py", dd / "canal_selftest.py")
            shutil.copy(ici / "lib_harnais.sh", dd / "lib_harnais.sh")
            cible = dd / fichier
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


#: LE COMPTE EST PUBLIE, PAS DECLARE. Il l'etait — `CAS_ATTENDUS = 35` — et
#: personne ne le lisait: le compte reel etait deja 43, puis 49. Une constante
#: que rien ne consomme derive en silence, et deux chiffres pour un seul fait
#: sont exactement le mecanisme qu'on retire partout ailleurs.
#:
#: Le seul compte qui vaut est `PARCOURUS`, incremente par `verifier()` et
#: imprime en `CANAL_SELFTEST_CAS=` a la sortie. `canal_proprete.py` le lit et
#: refuse de conclure s'il baisse: un `rc == 0` ne distingue pas « tout est
#: passe » de « rien n'a ete execute ».


def _corps() -> int:
    print("    le canal machine: la ponctuation ne decide plus d'un verdict")
    cas_protocole()
    cas_emetteur()
    cas_migration()
    cas_decor()
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
