"""Les niveaux : situés dans le modèle, pas proposés une seconde fois.

Les propositions de niveau restent celles des règles de texte (convention du
mètre, déjà en place) ; la géométrie situe chaque mention — texte ou bloc de
niveau avec attribut — pour que le modèle dise OÙ le plan l'écrit. Un même
niveau écrit trois fois (vue, cartouche) est UN niveau, cité trois fois.
"""

from __future__ import annotations

from ..extracteurs.motifs import MOTIF_NIVEAU
from ..nombres import lire_nombre
from .classification import role_du_nom
from .modele import Niveau
from .primitives import PrimitivesDxf

__all__ = ["lire_niveaux"]


def _valeur(texte: str) -> float | None:
    m = MOTIF_NIVEAU.search(texte)
    if m is None:
        return None
    signe = m.group("s")
    valeur = float(lire_nombre(m.group("n")))
    if signe in "-−":
        return -valeur
    if signe == "±" and valeur != 0:
        return None
    return valeur


def lire_niveaux(prims: PrimitivesDxf) -> list[Niveau]:
    niveaux: list[Niveau] = []
    for texte in prims.textes:
        if (texte.source.type == "ATTRIB" and texte.source.blocs
                and role_du_nom(texte.source.blocs[-1]) == "niveau"):
            continue  # lu ci-dessous, avec le point et la poignée de l'INSERT
        valeur = _valeur(texte.texte)
        if valeur is not None:
            niveaux.append(Niveau(" ".join(texte.texte.split()), valeur, texte.ancrage,
                                  texte.source.poignee))
    for insertion in prims.insertions:
        if role_du_nom(insertion.nom_bloc) != "niveau":
            continue
        for _, valeur_attr in insertion.attributs:
            valeur = _valeur(valeur_attr)
            if valeur is not None:
                niveaux.append(Niveau(valeur_attr.strip(), valeur, insertion.point,
                                      insertion.source.poignee))
                break
    niveaux.sort(key=lambda n: (n.valeur, n.point[1], n.point[0], n.poignee))
    return niveaux
