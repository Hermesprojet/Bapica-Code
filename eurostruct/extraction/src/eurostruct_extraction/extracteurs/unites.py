"""D'où vient l'unité d'un nombre écrit sans unité.

« P1 30x60 » ne dit pas si ce sont des centimètres. Le plan, souvent, le dit
ailleurs : « Cotes en cm », « Maten in mm », « All dimensions in mm ». Cette
mention est une SOURCE — elle se cite, avec sa page — et c'est la seule chose
qui autorise à attacher une unité à un nombre qui n'en porte pas.

LA RÈGLE, ET RIEN DE PLUS :

* une mention sur la MÊME page s'applique à cette page ;
* sinon, si toutes les mentions du document disent la même unité, elle
  s'applique au document ;
* sinon — aucune mention, ou des mentions qui se contredisent — l'unité reste
  ABSENTE, et la proposition le dit. Elle ne pourra être reportée dans une
  étude qu'après correction par l'ingénieur.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final

from ..modele import Boite
from .lignes import Ligne

__all__ = ["Declaration", "declarations_d_unite", "unite_declaree"]

_DECLARATION: Final[re.Pattern[str]] = re.compile(
    r"(?i:\b(?:toutes\s+les\s+)?(?:cotes?|dimensions?|mesures|maten|maatvoering|"
    r"afmetingen|all\s+dimensions)\b)"
    r"[^.;\n]{0,30}?"
    r"(?i:\b(?:en|in|exprim[ée]es?\s+en)\b)\s*"
    r"(?P<u>mm|cm|m)\b"
)


@dataclass(frozen=True)
class Declaration:
    unite: str
    page: int
    texte_brut: str
    boite: Boite | None
    position: dict[str, Any] | None

    def citation(self) -> dict[str, Any]:
        cite: dict[str, Any] = {"unit": self.unite, "page": self.page,
                                "raw_text": self.texte_brut}
        if self.boite is not None:
            cite["bbox"] = self.boite.en_liste()
        if self.position is not None:
            cite["position"] = self.position
        return cite


def declarations_d_unite(lignes: Iterable[Ligne]) -> list[Declaration]:
    trouvees = []
    for ligne in lignes:
        for m in _DECLARATION.finditer(ligne.texte):
            trouvees.append(Declaration(
                unite=m.group("u"), page=ligne.page, texte_brut=ligne.texte_brut,
                boite=ligne.boite_de(m.start(), m.end()),
                position=ligne.position))
    return trouvees


def unite_declaree(page: int, declarations: list[Declaration]) -> Declaration | None:
    sur_la_page = [d for d in declarations if d.page == page]
    if sur_la_page:
        unites = {d.unite for d in sur_la_page}
        return sur_la_page[0] if len(unites) == 1 else None
    unites = {d.unite for d in declarations}
    if len(unites) == 1:
        return declarations[0]
    return None
