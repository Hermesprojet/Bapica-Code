"""Lecture et validation du canal machine — la seule source du verdict.

CE QUE CE MODULE REMPLACE
--------------------------
Le lanceur de mutations decidait d'une mise a mort en cherchant la chaine
``ROUGE: <point>.`` dans une sortie destinee a un humain. La campagne des 103
controles sur ``3d0acc2`` a rendu onze survivants, dont **six** ou le harnais
avait bel et bien rougi :

===========  ==========================================  ====================
controle     ce que le harnais a imprime                 pourquoi c'est rate
===========  ==========================================  ====================
``SEP1``     ``ECHEC: A: la finalisation refuse...``      deux-points
``F2``       ``ROUGE: PR. D5. une connexion...``          prefixe humain
``F3``       ``ROUGE: PR. D3. un authentificateur...``    prefixe humain
``MF2``      ``ECHEC: decor: phase 1 refusee``            tue a l'installation
``MF4``      ``ECHEC: decor: phase 1 refusee``            tue a l'installation
``MF1``      ``ROUGE: MF2.`` ``MF3.`` ``MF4.``            temoin implicite
===========  ==========================================  ====================

Une virgule decidait si une garantie comptait comme defendue.

LES INVARIANTS DU PROTOCOLE
----------------------------
* un point declare produit **exactement un** verdict terminal ;
* un point inconnu est une **faute**, pas un silence ;
* un double verdict terminal est une **faute** ;
* un verdict absent devient ``NOT_RUN`` ou ``INFRA_FAILURE``, jamais « vert » ;
* un diagnostic non reconnu **n'est pas** une mise a mort ;
* un evenement mal forme **invalide la campagne** ;
* la prose humaine est libre : ponctuation, Unicode, longueur, sans effet ;
* l'ordre des evenements est controle.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

PROTOCOLE_ATTENDU = 1

STATUTS = {"ROUGE", "SUR", "NON_PARCOURU", "INFRA"}
PHASES = {"installation", "runtime", "teardown"}
CHAMPS = {"protocole", "point_id", "statut", "phase", "scenario_id", "chemin",
          "invariant", "diagnostic", "code", "effet", "terminal"}


class CanalInvalide(Exception):
    """Un evenement mal forme. La campagne entiere devient invalide.

    Ce n'est pas une severite choisie par gout : un canal dont on ne sait pas
    lire une ligne ne permet plus d'affirmer que les autres lignes disent ce
    qu'on croit.
    """


@dataclass
class Lecture:
    evenements: list[dict] = field(default_factory=list)
    fautes: list[str] = field(default_factory=list)
    #: point_id -> statut terminal
    terminaux: dict[str, str] = field(default_factory=dict)

    def statut_de(self, point: str) -> str | None:
        return self.terminaux.get(point)


def lire(chemin: str, points_declares: set[str]) -> Lecture:
    """Lit un canal JSONL et le valide. Leve `CanalInvalide` si mal forme."""
    lec = Lecture()
    try:
        with open(chemin, encoding="utf-8") as f:
            brut = f.read()
    except OSError:
        return lec  # canal absent: aucun evenement, ce qui est un fait lisible

    for n, ligne in enumerate(brut.split("\n"), start=1):
        if not ligne.strip():
            continue
        try:
            evt = json.loads(ligne)
        except json.JSONDecodeError as e:
            raise CanalInvalide(
                f"ligne {n}: enregistrement illisible ({e}). Un canal dont une "
                f"ligne ne se lit pas ne permet plus d'affirmer ce que disent "
                f"les autres.") from e
        if not isinstance(evt, dict):
            raise CanalInvalide(f"ligne {n}: l'enregistrement n'est pas un objet")
        inconnus = set(evt) - CHAMPS
        if inconnus:
            raise CanalInvalide(f"ligne {n}: champs inconnus {sorted(inconnus)}")
        manquants = {"protocole", "point_id", "statut", "phase"} - set(evt)
        if manquants:
            raise CanalInvalide(f"ligne {n}: champs manquants {sorted(manquants)}")
        if evt["protocole"] != PROTOCOLE_ATTENDU:
            raise CanalInvalide(
                f"ligne {n}: protocole {evt['protocole']}, attendu "
                f"{PROTOCOLE_ATTENDU}. Un canal d'une autre version ne se "
                f"devine pas.")
        if evt["statut"] not in STATUTS:
            raise CanalInvalide(f"ligne {n}: statut {evt['statut']!r} inconnu")
        if evt["phase"] not in PHASES:
            raise CanalInvalide(f"ligne {n}: phase {evt['phase']!r} inconnue")

        lec.evenements.append(evt)
        point = evt["point_id"]

        # POINT INCONNU: une FAUTE, et non un evenement qu'on ignore. Un
        # harnais qui emet pour un point non declare a soit une faute de frappe
        # soit une comptabilite qui derive; les deux se corrigent, aucune ne
        # se tolere.
        if points_declares and point not in points_declares:
            lec.fautes.append(
                f"ligne {n}: evenement pour le point « {point} », qui n'est pas "
                f"declare")
            continue

        if evt.get("terminal", True):
            if point in lec.terminaux:
                lec.fautes.append(
                    f"ligne {n}: SECOND verdict terminal pour « {point} » "
                    f"(« {lec.terminaux[point]} » puis « {evt['statut']} »)")
            else:
                lec.terminaux[point] = evt["statut"]
    return lec


def verdict_du_point(lec: Lecture, point: str) -> tuple[str, str]:
    """Rend (statut, motif) pour un point attendu.

    « Absent » ne devient jamais « vert »: c'est ``NOT_RUN``.
    """
    st = lec.statut_de(point)
    if st is None:
        return ("NOT_RUN", f"aucun verdict terminal pour « {point} »")
    if st == "ROUGE":
        evt = next(e for e in lec.evenements
                   if e["point_id"] == point and e.get("terminal", True))
        phase = evt["phase"]
        inv = evt.get("invariant")
        if phase == "installation":
            return ("KILLED_INSTALL_ASSERTION",
                    f"refus a l'installation, invariant « {inv or 'non nomme'} »")
        return ("KILLED_RUNTIME", f"le point « {point} » rougit ({phase})")
    if st == "INFRA":
        return ("INFRA_FAILURE", f"le decor de « {point} » n'a pas tenu")
    if st == "NON_PARCOURU":
        return ("NOT_RUN", f"le chemin de « {point} » n'a pas ete atteint")
    return ("SURVIVED", f"le point « {point} » reste SUR: le controle ne porte rien")


# ---------------------------------------------------------------------------
# LE TRADUCTEUR — une seule entree, pas un second mecanisme
# ---------------------------------------------------------------------------
#: Formes de prose observees dans les harnais, avec l'enregistrement du jour
#: ou chacune a coute un survivant.
import re as _re

_FORMES = [
    # « ROUGE: MF2. ... »  — la forme canonique
    _re.compile(r"^ *(?:ROUGE ATTENDU \(a fermer\)|ROUGE|ECHEC): +"
                r"(?P<point>[0-9A-Z][0-9A-Za-z']*)[0-9a-z]?\."),
    # « ECHEC: A: ... »    — deux-points (SEP1, two_phase_deployment.sh)
    _re.compile(r"^ *(?:ROUGE|ECHEC): +(?P<point>[0-9A-Z][0-9A-Za-z']*): "),
    # « ROUGE: PR. D5. ... » — prefixe humain (F2/F3, provider_contract)
    _re.compile(r"^ *(?:ROUGE|ECHEC): +[A-Z]{2}\. +"
                r"(?P<point>[0-9A-Z][0-9A-Za-z']*)\."),
]

#: Un refus a l'installation: la migration nomme le fichier fautif.
_INSTALL = _re.compile(r"phase 1 refusee sur (?P<fichier>\S+)")
_INVARIANT = _re.compile(r"\b((?:AUTHORITY|PRECONDITION|NORMATIVE|MIGRATION)_[A-Z0-9_]{4,})")


def traduire_prose(sortie: str, point: str) -> list[dict]:
    """Convertit la sortie humaine d'un harnais NON MIGRE en evenements.

    CE QUE CE TRADUCTEUR EST, ET N'EST PAS
    ---------------------------------------
    Ce n'est **pas** un second mecanisme d'attribution. Le verdict est calcule
    par :func:`verdict_du_point`, depuis le canal, et seulement depuis lui.
    Le traducteur est un **adaptateur d'entree** : il produit des evenements de
    canal a partir d'une prose, pour les harnais qui n'emettent pas encore.

    La difference n'est pas cosmetique. Un second mecanisme rendrait le verdict
    dependant de celui des deux qui a parle ; un adaptateur, lui, alimente
    l'unique mecanisme, et ses defauts se voient dans les evenements qu'il
    produit — pas dans un verdict qu'on ne saurait plus expliquer.

    LES TROIS FORMES SONT CELLES QUI ONT COUTE DES SURVIVANTS, textuellement :

    * ``ROUGE: MF2. ...``       forme canonique
    * ``ECHEC: A: ...``         deux-points — ``SEP1``
    * ``ROUGE: PR. D5. ...``    prefixe humain — ``F2`` et ``F3``

    Un refus d'installation devient un evenement de phase ``installation``,
    avec l'invariant nomme s'il apparait : c'est ce qui manquait a ``MF2``,
    ``MF4`` et ``K1``, tues a l'installation et cherches en execution.
    """
    evenements: list[dict] = []
    lignes = sortie.split("\n")

    for i, ligne in enumerate(lignes):
        for forme in _FORMES:
            m = forme.match(ligne)
            if not m:
                continue
            # `continue`, ET NON `break`. Mesure: la forme canonique matche
            # « ROUGE: PR. » avec point=« PR »; un `break` abandonnait la ligne
            # avant d'essayer la forme a prefixe, et F2/F3 ne se traduisaient
            # pas. Une forme qui matche sans donner LE point n'epuise pas la
            # ligne: elle epuise seulement cette forme-la.
            if m.group("point") != point:
                continue
            evenements.append({
                "protocole": PROTOCOLE_ATTENDU, "point_id": point,
                "statut": "ROUGE", "phase": "runtime",
                "scenario_id": None, "chemin": "traducteur/prose",
                "invariant": None, "diagnostic": None, "code": None,
                "effet": ligne.strip()[:200], "terminal": True,
            })
            break
        if evenements:
            break

    if evenements:
        return evenements

    # AUCUN POINT D'EXECUTION: la mutation a-t-elle ete arretee A L'INSTALLATION ?
    for i, ligne in enumerate(lignes):
        mi = _INSTALL.search(ligne)
        if not mi:
            continue
        fenetre = "\n".join(lignes[i:i + 6])
        inv = _INVARIANT.search(fenetre)
        evenements.append({
            "protocole": PROTOCOLE_ATTENDU, "point_id": point,
            "statut": "ROUGE", "phase": "installation",
            "scenario_id": None, "chemin": mi.group("fichier"),
            "invariant": inv.group(1) if inv else None,
            "diagnostic": fenetre[:300], "code": None,
            "effet": ligne.strip()[:200], "terminal": True,
        })
        break
    return evenements
