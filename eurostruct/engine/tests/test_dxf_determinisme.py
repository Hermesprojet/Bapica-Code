"""Deux plans du meme dessin doivent porter la MEME empreinte.

CE QUE CE MODULE MESURE, ET POURQUOI AILLEURS NE SUFFIT PAS
------------------------------------------------------------
`test_dxf.py` verifie qu'un rendu decrit la bonne geometrie. Il tourne dans le
processus de pytest, ou `PYTHONHASHSEED` est fixe une fois pour toutes: un
desordre qui depend de ce germe y est INVISIBLE, et le restera quel que soit le
nombre de rendus qu'on y ajoute.

Ce module rend donc le MEME dessin dans plusieurs SOUS-PROCESSUS, sous des
germes explicitement differents, et exige une seule empreinte.

CE QUE COUTE UNE EMPREINTE INSTABLE
-------------------------------------
Le chemin de stockage d'un livrable derive de son SHA-256 et le magasin ne
supprime jamais (`docs/STOCKAGE.md` §5). Un fichier dont les octets bougent
d'une execution a l'autre:

  * se depose sous DEUX chemins, definitivement;
  * casse la comparaison d'empreintes — un auditeur qui compare deux plans
    identiques conclut qu'ils different.

MESURE DU 01/09, AVANT CORRECTIF: huit rendus, huit processus, DEUX empreintes
(quatre chacune) pour une taille identique de 63 993 octets. Le diff faisait
huit lignes, toutes dans la section CLASSES: `LAYOUT` et `ACDBPLACEHOLDER`
echangeaient leur place. Voir `docs/TICKET_DXF_DETERMINISME.md`.
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor

import ezdxf
import pytest
from ezdxf.audit import Auditor

from eurostruct_engine.drawing.beam_section import rendre_dxf
from eurostruct_engine.drawing.modele import construire_modele, spec_depuis_dict

#: LA COUPE DE REFERENCE, telle que l'etude complete la gele.
#:
#: Elle est ecrite ici en dur — et non tiree d'un calcul — parce que ce module
#: n'eprouve pas le moteur: il eprouve la TRANSCRIPTION. Un calcul en amont
#: ajouterait une source de variation sans rapport avec la question posee.
COUPE = {
    "b": 300.0, "h": 600.0, "cover": 40.0,
    "link_diameter": 10.0, "link_spacing": 150.0, "link_mark": "C1",
    "bottom": [{"count": 4, "diameter": 20.0, "mark": "A1"}], "top": [],
    "element": "P1", "concrete_grade": "C30/37", "steel_grade": "B500B",
    "exposure_class": "XC3", "plot_scale": 20.0,
}

#: Les germes imposes. `0` desactive la randomisation, `random` la force, et
#: les trois valeurs fixes donnent trois ordres d'ensemble differents.
GERMES = ("0", "1", "12345", "98765", "random")


def octets_du_plan() -> bytes:
    """Les octets du DXF de la coupe de reference, dans CE processus."""
    tampon = io.StringIO()
    rendre_dxf(construire_modele(spec_depuis_dict(COUPE))).write(tampon)
    return tampon.getvalue().encode("utf-8")


_SCRIPT = textwrap.dedent(
    """
    import hashlib, io
    from eurostruct_engine.drawing.beam_section import rendre_dxf
    from eurostruct_engine.drawing.modele import (
        construire_modele, spec_depuis_dict)

    coupe = %r
    tampon = io.StringIO()
    rendre_dxf(construire_modele(spec_depuis_dict(coupe))).write(tampon)
    octets = tampon.getvalue().encode("utf-8")
    print(hashlib.sha256(octets).hexdigest(), len(octets))
    """
) % (COUPE,)


def _rendu_dans_un_processus(germe: str) -> tuple[str, int]:
    """Rend la coupe dans un interprete NEUF, sous le germe demande.

    L'ENVIRONNEMENT EST REDUIT A CE QUI EST NECESSAIRE. Transmettre
    l'environnement du test laisserait passer un `PYTHONHASHSEED` deja pose et
    le sous-processus n'eprouverait alors que le germe du parent.
    """
    sortie = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        capture_output=True, text=True, check=True,
        env={"PYTHONHASHSEED": germe, "PATH": "/usr/bin:/bin"},
    )
    empreinte, taille = sortie.stdout.split()
    return empreinte, int(taille)


# ---------------------------------------------------------------------------
# 1. PLUSIEURS PROCESSUS, PLUSIEURS GERMES, UNE SEULE EMPREINTE
# ---------------------------------------------------------------------------
def test_une_seule_empreinte_sur_plusieurs_processus_et_plusieurs_germes() -> None:
    """LE CAS DECISIF.

    Cinq germes, dont `random`, joues deux fois chacun: dix interpretes neufs.
    Une seule empreinte est attendue. Deux empreintes signifient que quelque
    chose dans la chaine itere un ensemble ou un dictionnaire dont l'ordre
    depend du germe de hachage.
    """
    resultats = [_rendu_dans_un_processus(g) for g in GERMES for _ in (1, 2)]
    empreintes = {e for e, _ in resultats}
    tailles = {t for _, t in resultats}

    assert len(tailles) == 1, (
        f"les rendus n'ont pas la meme taille: {sorted(tailles)}")
    assert len(empreintes) == 1, (
        "LE PLAN N'EST PAS DETERMINISTE ENTRE PROCESSUS. "
        f"{len(empreintes)} empreintes pour {len(resultats)} rendus de la meme "
        f"coupe: {sorted(empreintes)}. Le chemin de stockage derive du "
        "SHA-256 et le magasin ne supprime jamais: un meme dessin se deposera "
        "sous plusieurs chemins, definitivement."
    )


def test_le_processus_courant_rend_la_meme_empreinte_que_les_autres() -> None:
    """Le processus de pytest n'est pas un cas a part.

    Sans ce controle, un correctif qui ne s'appliquerait qu'aux
    sous-processus — parce qu'il depend d'un import qu'eux seuls font —
    passerait le cas decisif tout en laissant le produit non deterministe.
    """
    ici = hashlib.sha256(octets_du_plan()).hexdigest()
    ailleurs, _ = _rendu_dans_un_processus("31337")
    assert ici == ailleurs, (
        f"le rendu du processus de test ({ici[:16]}…) differe de celui d'un "
        f"processus neuf ({ailleurs[:16]}…)")


# ---------------------------------------------------------------------------
# 2. LES GENERATIONS CONCURRENTES
# ---------------------------------------------------------------------------
def test_les_generations_concurrentes_rendent_les_memes_octets() -> None:
    """HUIT RENDUS EN PARALLELE, DANS LE MEME PROCESSUS.

    L'API sert plusieurs requetes a la fois. Un correctif qui passerait par un
    etat global mutable — un cache, un drapeau pose puis retire — donnerait ici
    des octets qui dependent de l'entrelacement, et le defaut ne se verrait
    qu'en charge.
    """
    with ThreadPoolExecutor(max_workers=8) as pool:
        rendus = list(pool.map(lambda _: octets_du_plan(), range(8)))

    empreintes = {hashlib.sha256(o).hexdigest() for o in rendus}
    assert len(empreintes) == 1, (
        f"huit rendus concurrents ont donne {len(empreintes)} empreintes: "
        f"{sorted(empreintes)}")


# ---------------------------------------------------------------------------
# 3. LE FICHIER RESTE UN DXF VALIDE, ET SA GEOMETRIE NE BOUGE PAS
# ---------------------------------------------------------------------------
def test_le_plan_se_relit_et_l_audit_ezdxf_ne_trouve_rien() -> None:
    """UN FICHIER DETERMINISTE QUI NE S'OUVRE PLUS N'EST PAS UN PROGRES.

    On relit les octets produits avec `ezdxf` et on passe l'auditeur: c'est le
    controle que fait un logiciel de CAO a l'ouverture.
    """
    doc = ezdxf.read(io.StringIO(octets_du_plan().decode("utf-8")))
    auditeur = Auditor(doc)
    auditeur.run()
    assert not auditeur.errors, (
        f"l'audit ezdxf rapporte {len(auditeur.errors)} erreur(s): "
        f"{[str(e) for e in auditeur.errors[:5]]}")


def test_la_geometrie_relue_est_celle_de_la_coupe() -> None:
    """LA CORRECTION NE DOIT RIEN DEPLACER.

    Le contour de la poutre, les quatre barres et le cadre sont relus depuis
    les octets produits, pas depuis le modele en memoire: c'est ce qu'un
    logiciel de CAO verra.
    """
    doc = ezdxf.read(io.StringIO(octets_du_plan().decode("utf-8")))
    msp = doc.modelspace()

    #: LES QUATRE BARRES SONT DES CERCLES DE RAYON 10 mm (HA20).
    cercles = [e for e in msp if e.dxftype() == "CIRCLE"]
    rayons = sorted({round(c.dxf.radius, 6) for c in cercles})
    assert 10.0 in rayons, (
        f"aucun cercle de rayon 10 mm parmi {rayons}: les HA20 ont bouge")
    assert len([c for c in cercles if round(c.dxf.radius, 6) == 10.0]) == 4, (
        "le lit tendu ne porte pas quatre barres")

    #: LE CONTOUR DE LA SECTION, 300 x 600, EST DANS LE FICHIER.
    xs, ys = set(), set()
    for e in msp:
        if e.dxftype() == "LWPOLYLINE":
            for p in e.get_points("xy"):
                xs.add(round(p[0], 6))
                ys.add(round(p[1], 6))
    assert min(xs) == 0.0 and max(xs) >= 300.0, (
        f"la largeur relue ne couvre pas 0..300: {min(xs)}..{max(xs)}")
    assert max(ys) - min(ys) >= 600.0, (
        f"la hauteur relue ne couvre pas 600 mm: {max(ys) - min(ys)}")


# ---------------------------------------------------------------------------
# 4. LE GARDE-FOU DU CORRECTIF SE FALSIFIE
# ---------------------------------------------------------------------------
def test_le_correctif_refuse_une_methode_absente() -> None:
    """UN PATCH APPLIQUE A L'AVEUGLE EST PIRE QUE PAS DE PATCH.

    Le correctif enveloppe une methode interne d'`ezdxf`. Si une version
    ulterieure la renomme ou la deplace, l'enveloppe doit REFUSER bruyamment
    plutot que de s'appliquer a autre chose que ce qu'elle a ete eprouvee a
    corriger.
    """
    from eurostruct_engine.drawing import ezdxf_determinisme as det

    with pytest.raises(det.EzdxfIncompatible) as capture:
        det.verifier_signature(type("Faux", (), {}))
    message = str(capture.value)
    assert "add_required_classes" in message
    assert det.VERSIONS_EPROUVEES[0] in message, (
        "le refus ne dit pas quelles versions ont ete eprouvees")
    assert "TICKET_DXF_DETERMINISME" in message, (
        "le refus n'oriente pas vers le dossier qui explique quoi faire")


def test_le_correctif_refuse_une_signature_qui_a_change() -> None:
    """Une methode qui prend un parametre de plus ne joue plus le meme role."""
    from eurostruct_engine.drawing import ezdxf_determinisme as det

    class SignatureAutre:
        def add_required_classes(self, dxfversion, strict=False):
            ...

    with pytest.raises(det.EzdxfIncompatible) as capture:
        det.verifier_signature(SignatureAutre)
    assert "dxfversion" in str(capture.value)


def test_le_correctif_refuse_un_export_qui_ne_suit_plus_le_dictionnaire() -> None:
    """LE FAIT PORTEUR, ET LE SEUL QUI NE SE LISE PAS DANS UNE SIGNATURE.

    Reordonner `self.classes` ne sert a rien si l'export trie de son cote. Ce
    cas fabrique exactement cela — un export qui ignore l'ordre du
    dictionnaire — et exige que le controle le voie.
    """
    from ezdxf.sections.classes import ClassesSection

    from eurostruct_engine.drawing import ezdxf_determinisme as det

    class ExportIndifferent(ClassesSection):
        def export_dxf(self, tagwriter) -> None:
            #: Le meme contenu, mais toujours dans l'ordre canonique: une
            #: inversion du dictionnaire n'a plus aucun effet visible.
            for cle in sorted(self.classes):
                self.classes[cle].export_dxf(tagwriter)

    with pytest.raises(det.EzdxfIncompatible) as capture:
        det.verifier_signature(ExportIndifferent)
    assert "ordre du dictionnaire" in str(capture.value)


def test_l_enveloppe_est_idempotente() -> None:
    """Deux appels a `appliquer()` n'empilent pas deux enveloppes.

    Une seconde enveloppe resterait CORRECTE — elle appellerait la premiere —
    mais rendrait la pile illisible le jour ou l'on diagnostique, et chaque
    import supplementaire en ajouterait une.
    """
    from ezdxf.sections.classes import ClassesSection

    from eurostruct_engine.drawing import ezdxf_determinisme as det

    avant = ClassesSection.add_required_classes
    det.appliquer()
    det.appliquer()
    assert ClassesSection.add_required_classes is avant, (
        "un appel supplementaire a enveloppe une seconde fois")
