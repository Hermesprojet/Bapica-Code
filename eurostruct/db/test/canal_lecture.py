"""Le canal JSONL — seule autorite des verdicts de mutation.

CE QUE CE MODULE REMPLACE
--------------------------
Le lanceur decidait d'une mise a mort en cherchant ``ROUGE: <point>.`` dans une
sortie destinee a un humain. La campagne des 103 controles sur ``3d0acc2`` a
rendu onze survivants, dont **six** ou le harnais avait bel et bien rougi :

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

LE PROTOCOLE 2 — CE QUE LE 1 NE PORTAIT PAS
--------------------------------------------
Le protocole 1 identifiait un evenement par son seul ``point_id``. Trois
choses manquaient, et chacune est une facon de se tromper de preuve :

* **``run_id``** — deux campagnes concurrentes, ou une capture oubliee dans le
  scratch, et les evenements de l'une comptaient pour l'autre ;
* **``sha``** — un evenement produit par un arbre different repondait pour le
  candidat gele. C'est le defaut exact qu'a montre le lot L4 : une execution
  verte de l'arbre de travail attribuee a un SHA qui n'existait pas encore ;
* **``seq``** — deux harnais ecrivant en parallele dans le meme canal ne
  laissaient aucun moyen d'ordonner leurs verdicts.

``controle_id`` est enfin distingue de ``point_id``. Le premier nomme la
MUTATION eprouvee (``S1``, ``MF1``), le second nomme le POINT DE CONTROLE du
harnais qui a parle. Les confondre, c'est ce qui a permis a ``MF1`` d'etre
declare tue par les rouges de ``MF2``, ``MF3`` et ``MF4``.

LES INVARIANTS, ET CE QU'ILS COUTENT QUAND ILS MANQUENT
--------------------------------------------------------
* un controle declare produit **exactement un** verdict terminal ;
* un controle inconnu est une **faute**, jamais un silence ;
* un controle declare mais absent devient ``NOT_RUN`` — jamais « vert » ;
* JSON tronque, champ inconnu, version inconnue : **campagne invalide** ;
* un evenement d'un autre ``run_id`` ou d'un autre ``sha`` est **rejete** et
  compte : la campagne exige ``cross_run_event == 0`` ;
* la prose humaine n'a **aucun** effet, meme si elle contient des
  identifiants de controle ;
* aucun repli silencieux vers les anciennes regex : le traducteur refuse tout
  harnais qui n'est pas nommement declare non migre.
"""
from __future__ import annotations

import json
import re as _re
from dataclasses import dataclass, field

PROTOCOLE_ATTENDU = 2

STATUTS = {"ROUGE", "SUR", "NON_PARCOURU", "INFRA"}
PHASES = {"installation", "runtime", "teardown"}

#: Champs OBLIGATOIRES. Leur absence invalide l'evenement, donc la campagne.
OBLIGATOIRES = {"protocole", "run_id", "sha", "controle_id", "point_id",
                "statut", "phase", "seq"}
#: Champs facultatifs reconnus. Tout autre champ invalide la campagne — un
#: champ qu'on ne sait pas lire est un champ dont on ignore s'il changeait le
#: sens des autres.
FACULTATIFS = {"terminal", "invariant", "diagnostic", "chemin", "scenario_id",
               "code", "effet", "horodatage"}
CHAMPS = OBLIGATOIRES | FACULTATIFS

#: Le diagnostic est STRUCTURE: un objet a cles connues, pas une prose libre.
#: Une prose libre redevient vite ce qu'on analyse, et l'on retombe dans la
#: faute que ce module existe pour supprimer.
CLES_DIAGNOSTIC = {"nature", "detail", "objet", "attendu", "obtenu"}

#: Harnais qui n'emettent pas encore et passent par le traducteur. TOUTE
#: entree ici est une dette: elle nomme un harnais dont le verdict depend
#: encore d'une prose. Le traducteur REFUSE tout harnais absent de cette
#: liste — c'est ce qui empeche un repli silencieux.
HARNAIS_NON_MIGRES = {
    "db/test/authority_bootstrap_contract.sh",
    "db/test/authority_closure.sh",
    "db/test/authority_delegation_lineage.sh",
    "db/test/authority_four_eyes.sh",
    "db/test/authority_role_frontier.sh",
    "db/test/authority_root_of_trust.sh",
    "db/test/authority_sql_hardening.sh",
    "db/test/cross_cluster_restore.sh",
    "db/test/deploy_recovery.sh",
    "db/test/gate_protocol_selftest.sh",
    "db/test/migration_postconditions.sh",
    "db/test/migration_roundtrip.sh",
    "db/test/official_deployment.sh",
    "db/test/provider_contract.sh",
    "db/test/seal_contract.sh",
    "db/test/two_phase_deployment.sh",
    "db/test/mutation_matrix.py",
}


class CanalInvalide(Exception):
    """Un evenement mal forme. La campagne entiere devient invalide.

    Ce n'est pas une severite choisie par gout : un canal dont on ne sait pas
    lire une ligne ne permet plus d'affirmer que les autres lignes disent ce
    qu'on croit.
    """


class TraducteurRefuse(Exception):
    """Le traducteur a ete appele pour un harnais non declare non migre."""


@dataclass
class Lecture:
    evenements: list[dict] = field(default_factory=list)
    fautes: list[str] = field(default_factory=list)
    #: controle_id -> statut terminal
    terminaux: dict[str, str] = field(default_factory=dict)
    #: compteurs exiges nuls par la comptabilite de campagne
    unknown_event: int = 0
    cross_run_event: int = 0
    double_terminal: int = 0

    def statut_de(self, controle: str) -> str | None:
        return self.terminaux.get(controle)

    def anomalies(self) -> dict[str, int]:
        return {"unknown_event": self.unknown_event,
                "cross_run_event": self.cross_run_event,
                "double_terminal": self.double_terminal}


def _valider_forme(evt: dict, n: int) -> None:
    """Forme de l'evenement, independamment du run et du SHA."""
    if not isinstance(evt, dict):
        raise CanalInvalide(f"ligne {n}: l'enregistrement n'est pas un objet")
    inconnus = set(evt) - CHAMPS
    if inconnus:
        raise CanalInvalide(f"ligne {n}: champs inconnus {sorted(inconnus)}")
    manquants = OBLIGATOIRES - set(evt)
    if manquants:
        raise CanalInvalide(f"ligne {n}: champs manquants {sorted(manquants)}")
    if evt["protocole"] != PROTOCOLE_ATTENDU:
        raise CanalInvalide(
            f"ligne {n}: protocole {evt['protocole']!r}, attendu "
            f"{PROTOCOLE_ATTENDU}. Un canal d'une autre version ne se devine "
            f"pas: on ignore ce que ses champs signifiaient.")
    if evt["statut"] not in STATUTS:
        raise CanalInvalide(f"ligne {n}: statut {evt['statut']!r} inconnu")
    if evt["phase"] not in PHASES:
        raise CanalInvalide(f"ligne {n}: phase {evt['phase']!r} inconnue")
    if not isinstance(evt["seq"], int) or isinstance(evt["seq"], bool):
        raise CanalInvalide(f"ligne {n}: seq {evt['seq']!r} n'est pas un entier")
    diag = evt.get("diagnostic")
    if diag is not None:
        if not isinstance(diag, dict):
            raise CanalInvalide(
                f"ligne {n}: diagnostic non structure ({type(diag).__name__}). "
                f"Une prose libre redevient ce qu'on analyse.")
        sup = set(diag) - CLES_DIAGNOSTIC
        if sup:
            raise CanalInvalide(f"ligne {n}: diagnostic, cles inconnues {sorted(sup)}")


def lire(chemin: str, controles_declares: set[str], *,
         run_id: str | None = None, sha: str | None = None) -> Lecture:
    """Lit un canal JSONL et le valide.

    ``run_id`` et ``sha`` sont les valeurs ATTENDUES. Un evenement qui en
    porte d'autres est rejete et compte dans ``cross_run_event``: il ne peut
    ni tuer, ni sauver, ni attribuer.
    """
    lec = Lecture()
    try:
        with open(chemin, encoding="utf-8") as f:
            brut = f.read()
    except OSError:
        return lec  # canal absent: aucun evenement, ce qui est un fait lisible

    vus: set[tuple[str, int]] = set()
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
        _valider_forme(evt, n)

        # RUN ET SHA — REJET, PAS TOLERANCE.
        if (run_id is not None and evt["run_id"] != run_id) or \
           (sha is not None and evt["sha"] != sha):
            lec.cross_run_event += 1
            lec.fautes.append(
                f"ligne {n}: evenement d'un autre contexte "
                f"(run {evt['run_id']!r}/sha {evt['sha'][:12]!r}, attendu "
                f"{str(run_id)!r}/{str(sha)[:12]!r})")
            continue

        lec.evenements.append(evt)
        controle = evt["controle_id"]

        # CONTROLE INCONNU: une FAUTE, et non un evenement qu'on ignore. Un
        # harnais qui emet pour un controle non declare a soit une faute de
        # frappe soit une comptabilite qui derive; les deux se corrigent,
        # aucune ne se tolere.
        if controles_declares and controle not in controles_declares:
            lec.unknown_event += 1
            lec.fautes.append(
                f"ligne {n}: evenement pour le controle « {controle} », "
                f"qui n'est pas declare")
            continue

        # ORDRE DES SORTIES CONCURRENTES: (controle, seq) identifie l'evenement.
        # Deux harnais ecrivant en parallele ne peuvent plus produire deux
        # verdicts que rien ne departagerait.
        cle = (controle, evt["seq"])
        if cle in vus:
            lec.fautes.append(
                f"ligne {n}: seq {evt['seq']} deja vue pour « {controle} »")
            continue
        vus.add(cle)

        if evt.get("terminal", True):
            if controle in lec.terminaux:
                lec.double_terminal += 1
                lec.fautes.append(
                    f"ligne {n}: SECOND verdict terminal pour « {controle} » "
                    f"(« {lec.terminaux[controle]} » puis « {evt['statut']} »)")
            else:
                lec.terminaux[controle] = evt["statut"]
    return lec


def verdict_du_controle(lec: Lecture, controle: str) -> tuple[str, str]:
    """Rend (statut, motif) pour un controle attendu.

    « Absent » ne devient jamais « vert »: c'est ``NOT_RUN``.
    """
    st = lec.statut_de(controle)
    if st is None:
        return ("NOT_RUN", f"aucun verdict terminal pour « {controle} »")
    if st == "ROUGE":
        evt = next(e for e in lec.evenements
                   if e["controle_id"] == controle and e.get("terminal", True))
        phase = evt["phase"]
        inv = evt.get("invariant")
        if phase == "installation":
            return ("KILLED_INSTALL_ASSERTION",
                    f"refus a l'installation, invariant « {inv or 'non nomme'} »")
        return ("KILLED_RUNTIME",
                f"« {controle} » rougit en {phase} au point "
                f"« {evt['point_id']} »")
    if st == "INFRA":
        return ("INFRA_FAILURE", f"le decor de « {controle} » n'a pas tenu")
    if st == "NON_PARCOURU":
        return ("NOT_RUN", f"le chemin de « {controle} » n'a pas ete atteint")
    return ("SURVIVED",
            f"« {controle} » reste SUR: le controle ne porte rien")


#: Compatibilite de nom pour les appelants qui parlaient de « point ».
verdict_du_point = verdict_du_controle


# ---------------------------------------------------------------------------
# LE TRADUCTEUR — une entree unique, nommee, et qui refuse par defaut
# ---------------------------------------------------------------------------
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
_INVARIANT = _re.compile(
    r"\b((?:AUTHORITY|PRECONDITION|NORMATIVE|MIGRATION)_[A-Z0-9_]{4,})")


def traduire_prose(sortie: str, controle: str, *, point: str, harnais: str,
                   run_id: str, sha: str, depart_seq: int = 10_000) -> list[dict]:
    """Convertit la sortie d'un harnais NON MIGRE en evenements de canal.

    CE QUE CE TRADUCTEUR EST, ET N'EST PAS
    ---------------------------------------
    Ce n'est **pas** un second mecanisme d'attribution. Le verdict est calcule
    par :func:`verdict_du_controle`, depuis le canal, et seulement depuis lui.
    Le traducteur est un **adaptateur d'entree** : il produit des evenements a
    partir d'une prose, pour les harnais qui n'emettent pas encore.

    La difference n'est pas cosmetique. Un second mecanisme rendrait le verdict
    dependant de celui des deux qui a parle ; un adaptateur alimente l'unique
    mecanisme, et ses defauts se voient dans les evenements qu'il produit — pas
    dans un verdict qu'on ne saurait plus expliquer.

    ON CHERCHE LE ``point``, ON ESTAMPILLE LE ``controle``. La prose d'un
    harnais nomme son POINT DE CONTROLE (« D9 »), jamais la mutation qu'on lui
    applique (« F4 ») — le harnais ignore cette derniere. Confondre les deux
    fait chercher dans la prose un identifiant qui n'y figure jamais, et tout
    controle non migre devient alors SURVIVANT. Mesure du 29/08: `F4`, tue
    depuis des semaines, est ressorti survivant a la premiere execution ou
    j'avais passe le controle au lieu du point.

    IL REFUSE PAR DEFAUT. ``harnais`` doit figurer dans
    :data:`HARNAIS_NON_MIGRES`. Sans cela, un harnais migre pourrait retomber
    en silence sur les regex le jour ou son canal se tairait — et un canal
    muet redeviendrait indistinguable d'un canal vert.
    """
    if harnais not in HARNAIS_NON_MIGRES:
        raise TraducteurRefuse(
            f"« {harnais} » n'est pas declare non migre. Le traducteur ne "
            f"sert pas de repli: si ce harnais emet sur le canal, son silence "
            f"est un fait, pas une invitation a relire sa prose.")

    def _evt(statut: str, phase: str, point_vu: str, seq: int, **extra) -> dict:
        base = {"protocole": PROTOCOLE_ATTENDU, "run_id": run_id, "sha": sha,
                "controle_id": controle, "point_id": point_vu, "statut": statut,
                "phase": phase, "seq": seq, "terminal": True,
                "chemin": f"traducteur/{harnais}"}
        base.update(extra)
        return base

    lignes = sortie.split("\n")
    for ligne in lignes:
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
            return [_evt("ROUGE", "runtime", m.group("point"), depart_seq,
                         effet=ligne.strip()[:200])]

    # AUCUN POINT D'EXECUTION: la mutation a-t-elle ete arretee A L'INSTALLATION ?
    for i, ligne in enumerate(lignes):
        mi = _INSTALL.search(ligne)
        if not mi:
            continue
        fenetre = "\n".join(lignes[i:i + 6])
        inv = _INVARIANT.search(fenetre)
        return [_evt("ROUGE", "installation", point, depart_seq,
                     chemin=mi.group("fichier"),
                     invariant=inv.group(1) if inv else None,
                     diagnostic={"nature": "refus_installation",
                                 "detail": fenetre[:300]},
                     effet=ligne.strip()[:200])]
    return []
