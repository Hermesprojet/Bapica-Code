"""Des mots positionnés vers des lignes de texte, sans perdre les positions.

POURQUOI CE N'EST PAS ``page.extract_text()``. Le texte d'une page de plan
mêle des étiquettes éloignées posées sur la même hauteur : « P1 30x60 » à
gauche, « XC3 » trente centimètres plus loin. Les coller en une phrase ferait
lire « 30x60 XC3 » comme une seule indication. Les lignes sont donc coupées
là où l'espace entre deux mots dépasse quelques largeurs de caractère.

ET CHAQUE CARACTÈRE DE LA LIGNE SAIT DE QUEL MOT IL VIENT. Une règle qui
reconnaît « C30/37 » au milieu d'une ligne rend la boîte de CES mots-là, pas
celle de la ligne entière : l'écran surligne ce qui a été lu, pas la zone.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

from ..modele import Boite, EntiteDxf, Mot, PageLue

__all__ = ["Ligne", "lignes_de_la_page", "lignes_du_dxf"]

#: Un texte brut plus long que cela est coupé : une proposition cite sa ligne,
#: pas un chapitre.
LONGUEUR_MAX_TEXTE = 500


@dataclass(frozen=True)
class Ligne:
    page: int
    texte: str
    methode: str
    mots: tuple[Mot, ...] = ()
    #: Le décalage, dans ``texte``, du premier caractère de chaque mot.
    debuts: tuple[int, ...] = ()
    #: Pour un DXF : calque, poignée, point d'insertion — une position, pas
    #: une boîte.
    position: dict[str, Any] | None = None
    #: Dimensions de la page en points (PDF), pour qu'un lecteur futur puisse
    #: ramener la boîte à l'échelle de son affichage.
    largeur_page: float | None = None
    hauteur_page: float | None = None

    @property
    def texte_brut(self) -> str:
        return self.texte[:LONGUEUR_MAX_TEXTE]

    def _indices(self, debut: int, fin: int) -> list[int]:
        retenus = []
        for i, (mot, d) in enumerate(zip(self.mots, self.debuts, strict=True)):
            f = d + len(mot.texte)
            if d < fin and f > debut:
                retenus.append(i)
        return retenus

    def boite_de(self, debut: int, fin: int) -> Boite | None:
        """La boîte des mots qui couvrent ``texte[debut:fin]``."""
        indices = self._indices(debut, fin)
        if not indices:
            return None
        boite = self.mots[indices[0]].boite
        for i in indices[1:]:
            boite = boite.union(self.mots[i].boite)
        return boite

    def confiance_ocr(self, debut: int, fin: int) -> float | None:
        """La plus FAIBLE confiance OCR des mots couverts.

        La plus faible, pas la moyenne : une valeur dont un chiffre a été mal
        lu est mal lue, quelle que soit la qualité de ses voisins.
        """
        valeurs = [self.mots[i].confiance for i in self._indices(debut, fin)
                   if self.mots[i].confiance is not None]
        return min(valeurs) if valeurs else None

    def position_de(self) -> dict[str, Any] | None:
        if self.position is not None:
            return dict(self.position)
        if self.largeur_page is None:
            return None
        return {"origin": "top-left", "unit": "pt",
                "page_width": round(self.largeur_page, 2),
                "page_height": round(self.hauteur_page or 0.0, 2)}


def _construire(page: PageLue, mots: Sequence[Mot]) -> Ligne:
    parties: list[str] = []
    debuts: list[int] = []
    curseur = 0
    for mot in mots:
        if parties:
            parties.append(" ")
            curseur += 1
        debuts.append(curseur)
        parties.append(mot.texte)
        curseur += len(mot.texte)
    return Ligne(page=page.numero, texte="".join(parties), methode=page.methode,
                 mots=tuple(mots), debuts=tuple(debuts),
                 largeur_page=page.largeur, hauteur_page=page.hauteur)


def lignes_de_la_page(page: PageLue) -> list[Ligne]:
    """Regroupe les mots d'une page en lignes, dans l'ordre de lecture."""
    if not page.mots:
        return []
    mots = sorted(page.mots, key=lambda m: (round(m.boite.centre_y, 1), m.boite.x0))

    rangees: list[list[Mot]] = []
    for mot in mots:
        if rangees:
            rangee = rangees[-1]
            hauteur = median([m.boite.hauteur for m in rangee] + [mot.boite.hauteur])
            centre = median([m.boite.centre_y for m in rangee])
            if abs(mot.boite.centre_y - centre) <= 0.5 * max(hauteur, 1.0):
                rangee.append(mot)
                continue
        rangees.append([mot])

    lignes: list[Ligne] = []
    for rangee in rangees:
        rangee.sort(key=lambda m: m.boite.x0)
        largeurs = [(m.boite.x1 - m.boite.x0) / max(len(m.texte), 1) for m in rangee]
        chasse = median(largeurs) if largeurs else 5.0
        # UN ECART DE PLUS DE TROIS CARACTERES COUPE LA LIGNE: deux etiquettes
        # voisines sur un plan ne forment pas une phrase.
        seuil = max(3.0 * chasse, 6.0)
        segment: list[Mot] = [rangee[0]]
        for precedent, mot in zip(rangee, rangee[1:], strict=False):
            if mot.boite.x0 - precedent.boite.x1 > seuil:
                lignes.append(_construire(page, segment))
                segment = []
            segment.append(mot)
        lignes.append(_construire(page, segment))
    return lignes


def lignes_du_dxf(entites: Iterable[EntiteDxf], *,
                  unites: str | None) -> list[Ligne]:
    """Chaque texte du dessin devient une ou plusieurs lignes (page 1).

    Un texte multiligne est découpé à ses retours : chaque ligne garde la
    position de l'entité, son calque et sa poignée.
    """
    lignes: list[Ligne] = []
    for entite in entites:
        if entite.type not in ("TEXT", "MTEXT", "ATTRIB") or not entite.texte:
            continue
        for rang, texte in enumerate(entite.texte.splitlines()):
            texte = " ".join(texte.split())
            if not texte:
                continue
            position: dict[str, Any] = {
                "space": "modelspace", "entity": entite.type,
                "layer": entite.calque, "handle": entite.poignee,
                "drawing_units": unites,
            }
            if entite.point is not None:
                position["insert"] = list(entite.point)
            if rang:
                position["line"] = rang + 1
            lignes.append(Ligne(page=1, texte=texte, methode="dxf",
                                position=position))
    return lignes
