"""Deterministic DXF rendering of a reinforced concrete beam cross-section.

Cahier des charges section 5.2 and interdiction 1: drawings are produced by a
deterministic library (``ezdxf``), never by a language model. Nothing in this
module reads or writes anything other than its arguments.

CE MODULE NE CALCULE PLUS AUCUNE COORDONNEE. La geometrie vit dans
:mod:`.modele`, qui ne connait aucune bibliotheque de dessin, et ce module la
transcrit en DXF. :mod:`.svg` transcrit le MEME objet en apercu. C'est ce qui
garantit que l'apercu affiche a l'ecran et le fichier telecharge decrivent la
meme poutre: ils viennent du meme objet gele, pas de deux codes relus l'un a
cote de l'autre.

The section is drawn in model space at 1:1 in millimetres. ``plot_scale`` only
governs the size of annotation (text, arrows, dimension offsets), so that the
sheet reads correctly once plotted at that scale, while the geometry keeps true
coordinates — cahier des charges section 7.2, "echelle vraie".

Coordinate system: origin at the bottom-left corner of the concrete outline,
X to the right, Y upwards.
"""

from __future__ import annotations

from typing import Any, Final

import ezdxf
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment

from . import ezdxf_determinisme
from .layers import LAYERS
from .modele import (
    LEGAL_NOTICE,
    BarRow,
    BeamSectionSpec,
    Cote,
    Disque,
    ModeleSection,
    Polyligne,
    RebarScheduleRow,
    Texte,
    construire_modele,
)

__all__ = [
    "DIMSTYLE",
    "LEGAL_NOTICE",
    "BarRow",
    "BeamSectionSpec",
    "ModeleSection",
    "RebarScheduleRow",
    "build_beam_section",
    "construire_modele",
    "rendre_dxf",
]

#: DEUX DESSINS DU MEME CALCUL DOIVENT DONNER LES MEMES OCTETS.
#:
#: L'adressage par contenu l'exige, et rien d'autre ne le garantit : le chemin
#: de stockage d'un livrable derive de son SHA-256, si bien qu'un fichier dont
#: les octets bougent d'une execution a l'autre se depose deux fois, sous deux
#: chemins, et aucune relecture ne peut plus prouver qu'il s'agit du meme
#: dessin. C'est la meme lecon que la compression zlib du PDF.
#:
#: Sans ce reglage, ``ezdxf`` estampille a l'ecriture quatre valeurs volatiles.
#: Mesure faite sur deux rendus successifs d'une meme section (tailles egales,
#: 63 994 octets, huit lignes differentes) :
#:
#:     -{519CC0F6-828B-4982-9AC4-6C13FD7FBCE4}   $FINGERPRINTGUID
#:     +{FDA97C7E-8F29-489D-8FBA-885ECF5F7232}
#:     -{7E13FDF5-4415-4F9A-83B7-EAAC59418340}   $VERSIONGUID
#:     +{DB5681C2-676A-4857-B418-D9EF7CD0E489}
#:     -1.4.4 @ 2026-09-01T07:14:25.870408+00:00 marqueur ezdxf
#:     +1.4.4 @ 2026-09-01T07:14:25.895330+00:00
#:
#: plus les dates julienne ``$TDCREATE`` / ``$TDUPDATE``.
#:
#: Le nom de l'option dit « for testing » parce que c'est l'usage qu'en fait
#: ``ezdxf`` ; son effet, lui, est exactement celui qu'il nous faut : des
#: metadonnees fixes. Elle est posee au chargement du module et **jamais
#: remise a False**, de sorte qu'aucune execution concurrente ne puisse
#: tomber dans une fenetre ou elle serait desactivee. Elle vaut pour la
#: creation du document autant que pour son ecriture — la date de creation
#: est gravee des ``ezdxf.new()``.
#:
#: CE QUE CELA NE FAIT PAS PERDRE : la date reelle de production et l'identite
#: du moteur ne vivent pas dans l'en-tete DXF mais dans la ligne de livrable
#: (``created_at``, ``engine_build``), qui est la seule source opposable.
#:
#: CE REGLAGE EST NECESSAIRE, ET IL N'EST PAS SUFFISANT — MESURE DU 01/09.
#:
#: Huit rendus de la MEME coupe, dans huit processus distincts, ont rendu DEUX
#: empreintes (quatre chacune), pour une taille identique de 63 993 octets. Le
#: diff fait huit lignes, toutes dans la section ``CLASSES``: les
#: enregistrements ``LAYOUT`` et ``ACDBPLACEHOLDER`` echangent leur place.
#:
#: La cause est dans ``ezdxf`` 1.4.4 et non ici: en R2018,
#: ``REQUIRED_CLASSES`` retombe sur ``REQ_R2004``, qui ne cite aucune des deux;
#: elles ne sont donc enregistrees que par la boucle finale de
#: ``add_required_classes``, qui itere le ``set[str]`` rendu par
#: ``EntityDB.dxf_types_in_use`` — donc dans un ordre qui depend de
#: ``PYTHONHASHSEED``.
#:
#: A L'INTERIEUR D'UN PROCESSUS, LES OCTETS SONT STABLES, et c'est ce que le
#: parcours navigateur constate en reproduisant le plan apres un rechargement
#: complet. D'un processus a l'autre, ils ne le sont pas: deux plans du meme
#: dessin portent alors deux empreintes, donc deux chemins de stockage, et le
#: magasin ne supprime jamais.
#:
#: CORRIGE LE 02/09 par ``ezdxf_determinisme.appliquer()``, appele ci-dessous:
#: l'ordre de la section ``CLASSES`` est desormais canonique. Le module dit
#: pourquoi cette forme de correctif et pas une autre; le test decisif est
#: ``engine/tests/test_dxf_determinisme.py``, qui rend en SOUS-PROCESSUS sous
#: plusieurs germes — sans quoi il ne mesurerait rien, ``PYTHONHASHSEED`` etant
#: fixe pour la duree d'un processus.
ezdxf.options.write_fixed_meta_data_for_testing = True

#: L'ORDRE DE LA SECTION ``CLASSES``, POSE AVANT TOUT RENDU.
#:
#: Installe ici, au chargement du module qui produit les DXF, et pas dans
#: l'API: un plan se rend aussi depuis les tests, depuis un script, depuis un
#: futur travail par lots. Le determinisme d'un fichier adresse par contenu ne
#: peut pas dependre du chemin par lequel on est arrive.
#:
#: SI ``ezdxf`` A CHANGE DE FORME, CET APPEL LEVE — et le module ne se charge
#: pas. C'est voulu: le defaut qu'il corrige est silencieux, et un produit qui
#: demarrerait sans la correction en produisant des empreintes instables serait
#: pire qu'un produit qui refuse de demarrer en le disant.
ezdxf_determinisme.appliquer()

DIMSTYLE: Final = "EUROSTRUCT"


# ---------------------------------------------------------------------------
def _setup_document(scale: float) -> Drawing:
    doc = ezdxf.new(dxfversion="R2018", setup=True)
    doc.header["$INSUNITS"] = 4  # millimetres
    doc.header["$MEASUREMENT"] = 1  # metric

    for spec in LAYERS:
        layer = doc.layers.add(name=spec.name, color=spec.color)
        layer.dxf.lineweight = spec.lineweight
        if spec.linetype in doc.linetypes:
            layer.dxf.linetype = spec.linetype
        layer.description = spec.description

    # A dimension style bound to the STANDARD text style, so the file opens
    # identically in AutoCAD, BricsCAD and LibreCAD without a font substitution.
    ds = doc.dimstyles.add(DIMSTYLE)
    ds.dxf.dimtxsty = "Standard"
    ds.dxf.dimscale = scale
    ds.dxf.dimtxt = 2.5
    ds.dxf.dimasz = 2.5
    ds.dxf.dimexe = 1.25
    ds.dxf.dimexo = 2.0
    ds.dxf.dimgap = 0.8
    ds.dxf.dimdec = 0
    ds.dxf.dimlunit = 2
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    return doc


def _tracer_polyligne(msp: Any, p: Polyligne) -> None:
    msp.add_lwpolyline(
        p.sommets, format="xyb", close=p.fermee, dxfattribs={"layer": p.calque}
    )


def _tracer_disque(msp: Any, d: Disque) -> None:
    """Une barre longitudinale vue en coupe: cercle, et hachure si pleine."""
    msp.add_circle(center=(d.x, d.y), radius=d.rayon, dxfattribs={"layer": d.calque})
    if not d.plein:
        return
    hatch = msp.add_hatch(dxfattribs={"layer": d.calque, "color": 1})
    edge = hatch.paths.add_edge_path()
    edge.add_arc(center=(d.x, d.y), radius=d.rayon, start_angle=0.0, end_angle=360.0)


def _tracer_texte(msp: Any, t: Texte) -> None:
    attribs: dict[str, Any] = {"layer": t.calque}
    if t.couleur is not None:
        attribs["color"] = t.couleur
    entite = msp.add_text(t.contenu, height=t.hauteur, rotation=t.rotation,
                          dxfattribs=attribs)
    align = (TextEntityAlignment.MIDDLE_CENTER if t.ancrage == "centre"
             else TextEntityAlignment.LEFT)
    entite.set_placement((t.x, t.y), align=align)


def _text(
    msp: Any, s: str, x: float, y: float, height: float, layer: str
) -> None:
    """Un texte pose par sa ligne de base, aligne a gauche.

    Reste ici — et pas dans le modele — parce que c'est une primitive de DXF:
    :mod:`.beam_elevation` s'en sert encore directement, n'ayant pas encore
    son propre modele geometrique.
    """
    msp.add_text(s, height=height, dxfattribs={"layer": layer}).set_placement(
        (x, y), align=TextEntityAlignment.LEFT
    )


def _tracer_cote(msp: Any, c: Cote) -> None:
    msp.add_linear_dim(
        base=c.base, p1=c.p1, p2=c.p2, angle=c.angle,
        dimstyle=DIMSTYLE, dxfattribs={"layer": c.calque},
    ).render()


def rendre_dxf(modele: ModeleSection) -> Drawing:
    """Transcrit un modele gele en document DXF R2018.

    Aucune coordonnee n'est calculee ici: chaque entite reprend telle quelle
    celle que :func:`~.modele.construire_modele` a posee.
    """
    doc = _setup_document(modele.echelle)
    msp = doc.modelspace()
    for p in modele.polylignes:
        _tracer_polyligne(msp, p)
    for d in modele.disques:
        _tracer_disque(msp, d)
    for c in modele.cotes:
        _tracer_cote(msp, c)
    for t in modele.textes:
        _tracer_texte(msp, t)
    return doc


def build_beam_section(spec: BeamSectionSpec) -> tuple[Drawing, list[RebarScheduleRow]]:
    """Build the DXF document of one beam cross-section and its schedule.

    :returns: the ``ezdxf`` document and the rebar schedule rows.
    """
    modele = construire_modele(spec)
    return rendre_dxf(modele), list(modele.nomenclature)
