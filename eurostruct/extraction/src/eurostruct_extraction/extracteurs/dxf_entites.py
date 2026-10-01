"""Ce que les ENTITÉS d'un DXF disent, au-delà de leurs textes.

Deux lectures, et deux seulement :

* les **cotes** (``DIMENSION``) : la valeur affichée sur le dessin, soit la
  mesure × ``DIMLFAC`` (un détail au 1/20 sur un plan au 1/50 affiche 30 là où
  le trait mesure 75). Si le dessinateur a forcé un texte numérique, c'est CE
  texte qui est la valeur — c'est lui que le plan montre — et la mesure
  géométrique est citée à côté. Un texte forcé non numérique (« VAR », « voir
  détail ») ne propose rien : le dessin n'y affirme aucun nombre ;
* une cote à ``DIMLFAC ≠ 1`` N'HÉRITE PAS de ``$INSUNITS`` : un dessin en m
  coté en cm (100) et un détail au 1/20 (0,4) ne se distinguent pas. Seule une
  mention écrite (« Cotes en cm ») donne l'unité du nombre affiché ; sans elle,
  il reste sans unité ;
* les **étiquettes d'axes** : un texte court (« A », « 3 ») posé sur un calque
  d'axes devient une proposition de file.

LE CALQUE CLASSE, ET LE DIT. Une cote sur un calque d'axes est proposée comme
entraxe ; ailleurs, comme cote non classée. Le nom du calque est cité.

CE QUE LA GÉOMÉTRIE A DÉJÀ RATTACHÉ N'EST PAS PROPOSÉ DEUX FOIS. Une cote
accrochée à deux axes, ou une étiquette lue dans une bulle, corrobore déjà une
proposition géométrique : ses poignées sont dans ``contexte.absorbees``.
"""

from __future__ import annotations

import re
from typing import Any, Final

from ..modele import Candidat, DocumentAnalyse, EntiteDxf
from ..nombres import lire_nombre
from .unites import Declaration, unite_declaree

__all__ = ["CALQUES_AXES", "ExtracteurEntitesDxf"]

CALQUES_AXES: Final[re.Pattern[str]] = re.compile(
    r"(?i)(axe|axes|axis|grid|grille|stramien|raster|trame)")
_ETIQUETTE_AXE: Final[re.Pattern[str]] = re.compile(r"[A-Z]{1,2}|\d{1,2}")
#: LE TEXTE FORCE EST LA COTE ENTIERE: « 2 450 » y est UN nombre, et le
#: separateur de milliers par espace y est donc admis.
_NOMBRE_SEUL: Final[re.Pattern[str]] = re.compile(
    r"\s*(\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(mm|cm|m)?\s*")


def _format(mesure: float) -> str:
    return f"{mesure:.3f}".rstrip("0").rstrip(".")


def _valeur(mesure: float) -> int | float:
    arrondie = round(mesure, 6)
    return int(arrondie) if arrondie == int(arrondie) else arrondie


def _position(entite: EntiteDxf, unites: str | None) -> dict[str, Any]:
    position: dict[str, Any] = {"space": "modelspace", "entity": entite.type,
                                "layer": entite.calque, "handle": entite.poignee,
                                "drawing_units": unites}
    if entite.point is not None:
        position["insert"] = list(entite.point)
    if entite.points_de_definition:
        position["defpoints"] = [list(p) for p in entite.points_de_definition]
    return position


class ExtracteurEntitesDxf:
    nom = "entites_dxf"

    def extraire(self, analyse: DocumentAnalyse, contexte: Any = None) -> list[Candidat]:
        if not analyse.entites_dxf:
            return []
        candidats: list[Candidat] = []
        insunits = analyse.compte_rendu.get("insunits")
        absorbees = getattr(contexte, "absorbees", None) or set()
        declaration = unite_declaree(1, getattr(contexte, "declarations", None) or [])
        for entite in analyse.entites_dxf:
            if entite.poignee and entite.poignee in absorbees:
                continue
            if entite.type == "DIMENSION":
                candidat = self._cote(entite, analyse.unites_dxf, insunits, declaration)
            elif entite.type in ("TEXT", "MTEXT", "ATTRIB"):
                candidat = self._etiquette_d_axe(entite, analyse.unites_dxf)
            else:
                candidat = None
            if candidat is not None:
                candidats.append(candidat)
        return candidats

    @staticmethod
    def _cote(entite: EntiteDxf, unites_dessin: str | None, insunits: Any,
              declaration: Declaration | None) -> Candidat | None:
        if entite.mesure is None:
            return None
        texte = (entite.texte or "").strip()
        facteur = entite.facteur if entite.facteur is not None else 1.0
        # LA VALEUR AFFICHEE EST LA MESURE A L'ECHELLE DE LA COTE (DIMLFAC).
        affichable = entite.mesure * facteur
        fondement: dict[str, Any] = {"rule": "cote_dxf", "layer": entite.calque,
                                     "measured": _format(entite.mesure)}
        unites = unites_dessin
        if facteur != 1.0:
            fondement["dimlfac"] = facteur
            fondement["drawing_units"] = unites_dessin
            unites = declaration.unite if declaration is not None else None
        if texte and texte != "<>":
            # LE TEXTE FORCE EST CE QUE LE PLAN MONTRE.
            affiche = texte.replace("<>", _format(affichable))
            lu = _NOMBRE_SEUL.fullmatch(affiche)
            if lu is None:
                return None
            valeur: int | float = lire_nombre(lu.group(1))
            unite = lu.group(2) or unites
            fondement["rule"] = "cote_dxf_texte_force"
            brut = affiche
            fondement["unit_basis"] = ("explicite" if lu.group(2)
                                       else "declaration" if unites else "absente")
        else:
            valeur = _valeur(affichable)
            unite = unites
            brut = _format(affichable)
            fondement["unit_basis"] = "declaration" if unites else "absente"
        if fondement["unit_basis"] == "declaration" and facteur != 1.0:
            fondement["unit_declaration"] = {"source": "mention_ecrite",
                                             **declaration.citation()}  # type: ignore[union-attr]
        elif fondement["unit_basis"] == "declaration":
            fondement["unit_declaration"] = {"source": "$INSUNITS", "value": insunits,
                                             "unit": unites}
        axes = CALQUES_AXES.search(entite.calque) is not None
        confiance = 0.8 - {"explicite": 0.0, "declaration": 0.05,
                           "absente": 0.25}[fondement["unit_basis"]]
        return Candidat(
            categorie="grid_spacing" if axes else "dimension", valeur=valeur,
            unite=unite, texte_brut=f"cote {brut} (calque {entite.calque})",
            page=1, confiance=round(confiance, 3), methode="dxf",
            position=_position(entite, unites_dessin), fondement=fondement)

    @staticmethod
    def _etiquette_d_axe(entite: EntiteDxf, unites: str | None) -> Candidat | None:
        texte = (entite.texte or "").strip()
        if not CALQUES_AXES.search(entite.calque) or not _ETIQUETTE_AXE.fullmatch(texte):
            return None
        return Candidat(
            categorie="grid_line", valeur=texte, unite=None,
            texte_brut=f"{texte} (calque {entite.calque})", page=1, confiance=0.7,
            methode="dxf", position=_position(entite, unites),
            fondement={"rule": "etiquette_sur_calque_d_axes", "layer": entite.calque})
