"""Le DXF : les entités de l'espace objet, par ezdxf (licence MIT).

C'EST LE FORMAT D'ÉCHANGE QUE CE PRODUIT LIT (interdiction 7, tranchée : DXF
R2018 via ezdxf). Les textes, les textes multilignes, les attributs de blocs
et les cotes y sont des objets, pas des pixels : leur contenu est exact, leur
position aussi.

L'UNITÉ DU DESSIN EST LUE, PAS SUPPOSÉE. ``$INSUNITS`` dit en quoi le dessin
est tracé ; une cote mesurée hérite de cette unité, et la proposition cite la
variable. Un dessin « sans unité » (``$INSUNITS = 0``) donne des cotes sans
unité — que l'ingénieur devra préciser avant de pouvoir les reporter.
"""

from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass, field
from typing import Any, Final

from ..modele import EntiteDxf
from .dxf_cotes import mesure_de_cote

__all__ = ["LectureDxf", "UNITES_INSUNITS", "lire_dxf"]

#: Les codes ``$INSUNITS`` que ce lecteur sait nommer. Les autres (miles,
#: microns, années-lumière…) rendent ``None`` : unité non reconnue, dite.
UNITES_INSUNITS: Final[dict[int, str]] = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}

#: Au-delà, les entités restantes ne sont pas lues — et le compte rendu le dit.
ENTITES_MAX: Final[int] = 50_000

#: Des cotes que ce lecteur ne mesure pas : comptées, jamais proposées.
_COTES_NON_LUES: Final[dict[str, str]] = {"ARC_DIMENSION": "longueur_arc",
                                          "LARGE_RADIAL_DIMENSION": "rayon_raccourci"}


@dataclass
class LectureDxf:
    entites: list[EntiteDxf] = field(default_factory=list)
    unites: str | None = None
    insunits: int | None = None
    version: str | None = None
    tronquee: bool = False
    erreurs_corrigees: int = 0
    #: Les primitives géométriques (``geometrie.PrimitivesDxf``), même passe.
    primitives: Any = None
    #: Si la lecture géométrique a échoué : pourquoi. Les textes restent lus.
    erreur_geometrie: str | None = None
    #: Les cotes de l'espace objet, par nature — celles qui ne proposent rien
    #: (angles, ordonnées, longueurs d'arc) comprises : comptées et nommées.
    cotes_par_type: dict[str, int] = field(default_factory=dict)


def _point(valeur: Any) -> tuple[float, float] | None:
    try:
        return (round(float(valeur[0]), 4), round(float(valeur[1]), 4))
    except (TypeError, ValueError, IndexError):
        return None


def lire_dxf(octets: bytes) -> LectureDxf:
    """Lit l'espace objet. Lève si ezdxf ne peut rien en tirer."""
    import ezdxf
    from ezdxf import recover

    if octets.startswith(b"AutoCAD Binary DXF"):
        # LE DXF BINAIRE NE PASSE PAS PAR LE LECTEUR DE REPARATION: celui-ci
        # ne lit que l'ASCII (mesure: « Invalid group code »). `readfile`
        # reconnait le binaire, mais seulement depuis un fichier: on en ecrit
        # un, temporaire, detruit a la sortie du bloc.
        with tempfile.NamedTemporaryFile(suffix=".dxf") as fichier:
            fichier.write(octets)
            fichier.flush()
            document = ezdxf.readfile(fichier.name)
        auditeur = document.audit()
    else:
        document, auditeur = recover.read(io.BytesIO(octets))
    lecture = LectureDxf()
    lecture.version = str(document.dxfversion)
    lecture.erreurs_corrigees = len(getattr(auditeur, "fixes", []) or [])
    insunits = document.header.get("$INSUNITS", 0)
    try:
        lecture.insunits = int(insunits)
    except (TypeError, ValueError):
        lecture.insunits = None
    lecture.unites = UNITES_INSUNITS.get(lecture.insunits or 0)

    for entite in document.modelspace():
        if len(lecture.entites) >= ENTITES_MAX:
            lecture.tronquee = True
            break
        nature = _COTES_NON_LUES.get(entite.dxftype())
        if nature is not None:
            lecture.cotes_par_type[nature] = lecture.cotes_par_type.get(nature, 0) + 1
        lecture.entites.extend(_lire_entite(entite))
    for lue in lecture.entites:
        if lue.type == "DIMENSION" and lue.genre:
            lecture.cotes_par_type[lue.genre] = lecture.cotes_par_type.get(lue.genre, 0) + 1

    # LA GEOMETRIE, DANS LA MEME OUVERTURE DU FICHIER. Son echec ne fait pas
    # echouer la lecture des textes: il est dit, et rien n'en est propose.
    from ..geometrie.primitives import lire_primitives

    try:
        lecture.primitives = lire_primitives(document, insunits=lecture.insunits,
                                             unites=lecture.unites)
    except Exception as cause:  # noqa: BLE001 — la geometrie illisible se constate
        lecture.erreur_geometrie = f"{type(cause).__name__}: {' '.join(str(cause).split())[:160]}"
    return lecture


def _lire_entite(entite: Any, calque_parent: str | None = None) -> list[EntiteDxf]:
    type_ = entite.dxftype()
    calque = str(entite.dxf.get("layer", calque_parent or "0"))
    poignee = str(entite.dxf.get("handle", "") or "")

    if type_ == "TEXT" or type_ == "ATTRIB":
        texte = entite.plain_text() if hasattr(entite, "plain_text") else entite.dxf.text
        return [EntiteDxf(type_, calque, poignee, texte=str(texte),
                          point=_point(entite.dxf.get("insert")),
                          hauteur_texte=entite.dxf.get("height"))]

    if type_ == "MTEXT":
        texte = entite.plain_text(split=False)
        return [EntiteDxf(type_, calque, poignee, texte=str(texte),
                          point=_point(entite.dxf.get("insert")),
                          hauteur_texte=entite.dxf.get("char_height"))]

    if type_ == "DIMENSION":
        # LA MESURE PAR TYPE, la même que celle de la géométrie (dxf_cotes.py) :
        # une cote alignée mesure la distance de ses deux points.
        mesuree = mesure_de_cote(entite)
        texte = str(entite.dxf.get("text", "") or "")
        points = tuple(p for p in (_point(entite.dxf.get("defpoint")),
                                   _point(entite.dxf.get("defpoint2")),
                                   _point(entite.dxf.get("defpoint3"))) if p)
        try:
            facteur = float(entite.override().get("dimlfac", 1.0) or 1.0)
        except Exception:  # noqa: BLE001 — un style illisible: facteur 1, dit tel
            facteur = 1.0
        return [EntiteDxf(type_, calque, poignee, texte=texte,
                          point=_point(entite.dxf.get("text_midpoint")),
                          mesure=mesuree.valeur, points_de_definition=points, facteur=facteur,
                          genre=mesuree.nature, mesure_autocad=mesuree.autocad)]

    if type_ == "LINE":
        debut, fin = _point(entite.dxf.start), _point(entite.dxf.end)
        return [EntiteDxf(type_, calque, poignee,
                          points_de_definition=tuple(p for p in (debut, fin) if p))]

    if type_ == "CIRCLE":
        return [EntiteDxf(type_, calque, poignee,
                          point=_point(entite.dxf.center),
                          mesure=float(entite.dxf.radius))]

    if type_ == "INSERT":
        # LES ATTRIBUTS D'UN BLOC sont souvent l'etiquette d'un axe ou d'un
        # repere; les textes DANS le bloc aussi. On les lit sous la forme que
        # le dessin affiche (entites virtuelles, deja placees).
        lues: list[EntiteDxf] = []
        for attribut in getattr(entite, "attribs", []) or []:
            lues.extend(_lire_entite(attribut, calque))
        try:
            virtuelles = list(entite.virtual_entities())
        except Exception:  # noqa: BLE001 — un bloc mal forme n'arrete rien
            virtuelles = []
        for virtuelle in virtuelles:
            if virtuelle.dxftype() in ("TEXT", "MTEXT", "CIRCLE"):
                lues.extend(_lire_entite(virtuelle, calque))
        return lues

    return []
