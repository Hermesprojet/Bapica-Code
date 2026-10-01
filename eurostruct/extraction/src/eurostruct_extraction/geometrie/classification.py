"""Ce qu'un calque, un bloc ou un type de ligne dit d'un trait.

UNE TABLE, PAS UNE INTUITION. Les noms de calques varient d'un bureau à
l'autre, mais pas au hasard : `POTEAUX`, `S-COLS`, `KOLOMMEN`, `STÜTZEN` disent
la même chose. La table ci-dessous est multilingue (FR, NL, EN, DE) et suit
les conventions AIA (`S-COLS`, `S-BEAM`, `S-GRID`…). Un nom qu'elle ne connaît
pas ne classe rien : l'élément sera reconnu par sa forme et sa position, avec
une confiance plus basse, et le fondement le dira.

LE PLUS SPÉCIFIQUE L'EMPORTE. `S-BEAM-TEXT` est un calque de texte, pas de
poutre ; `POUTRES-COTES` un calque de cotes. Les rôles d'annotation passent
donc avant les rôles d'éléments.

LES PIEUX ET LES FONDATIONS PASSENT JUSTE APRÈS LES COTES (voir
``docs/GEOMETRIE_PIEUX_GAINES_UNITE.md``). Un pieu n'est jamais un poteau, un
axe de pieux (`Pr_Pieux_axe`) n'est pas un axe de grille, le texte d'un calque
de pieux est un repère de pieu, son niveau n'est pas un niveau de plancher.
Un massif (`PILE_CAP`, `POER`, `SEMELLE`) est lu avant le pieu : ce n'est pas
un pieu, et ce n'est pas un poteau.

UN BLOC PRIME SUR SON CALQUE. Un bloc `POT30x30` inséré sur `0` reste un
poteau ; le bloc le plus intérieur qui se reconnaît décide.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Literal

__all__ = [
    "Classement",
    "Role",
    "classer",
    "est_type_de_ligne_cache",
    "est_type_de_ligne_d_axe",
    "nomme_un_pieu",
    "role_du_nom",
]

Role = Literal["axe", "poteau", "poutre", "voile", "dalle", "tremie", "cote",
               "texte", "niveau", "armature", "cadre", "hachure", "pieu", "fondation",
               "inconnu"]

_AVANT: Final[str] = r"(?<![A-Z])"

#: LES PIEUX, en cinq langues. Les composés néerlandais et allemands sont
#: LISTÉS, pas devinés : « paal » est une sous-chaîne de ``BEPAALD``. La tête
#: d'un pieu (``PAALKOP``, ``PFAHLKOPF``) est le pieu ; ``PILOTIS`` (poteaux)
#: n'en est pas un.
_PIEU: Final[str] = (
    r"(?:MICRO[ _.-]?)?PIEUX?|PILES?(?![A-Z])|PILING|PILOTES?(?![A-Z])|"
    r"(?:HEI|BOOR|SCHROEF|PREFAB|VIBRO|FUNDERINGS?)?PA(?:AL|LEN)(?:KOP(?:PEN)?)?(?![A-Z])|"
    r"(?:BOHR|RAMM|MIKRO|GRUNDUNGS|GRUENDUNGS)?PF(?:AHL|AEHLE|AHLE)"
    r"(?:KOPF|KOEPFE|KOPFE)?(?![A-Z])")
#: Les fondations qui ne sont pas des pieux : massifs, semelles, têtes de
#: groupe. Lues AVANT les pieux (``PILE_CAP`` est un massif).
_FONDATION: Final[str] = (
    r"PILE[ _.-]?CAPS?|SEMELLES?(?![A-Z])|MASSIFS?(?![A-Z])|FOOTINGS?|"
    r"POER(?:EN)?(?![A-Z])|(?:EINZEL|STREIFEN)FUNDAMENTE?|PFAHLKOPFPLATTEN?|PFAHLROST")

#: L'ORDRE EST LA PRIORITÉ: annotation d'abord, éléments ensuite.
_ROLES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (role, re.compile(_AVANT + r"(?:" + motif + r")"))
    for role, motif in (
        ("cote", r"COTES?(?![A-Z])|COTATIONS?|DIMS?(?![A-Z])|DIMENSIONS?|MAATVOERING|"
                 r"MAAT(?![A-Z])|MATEN|BEMASSUNG|BEMASZUNG"),
        ("fondation", _FONDATION),
        ("pieu", _PIEU),
        ("texte", r"TEXTES?|TEXT(?![A-Z])|TXT|TEKST|ANNO(?:T|TATION|TATIONS)?(?![A-Z])|"
                  r"LABELS?|REPERES?|LEGENDE|NOMENCLATURE|BESCHRIFTUNG"),
        ("niveau", r"NIVEAUX?|NIV(?![A-Z])|LEVELS?|PEIL"),
        ("armature", r"FERRAILL|ARMATUR|REINF|REBAR|WAPENING|BEWEHRUNG"),
        ("cadre", r"CARTOUCHE|CADRE|FRAME|TITLE|TITRE|KADER|RAHMEN|VIEWPORT|VPORT"),
        ("tremie", r"TREMIES?|RESERVATIONS?|OUVERTURES?|OPENINGS?|SPARINGEN|SPARING|"
                   r"AUSSPARUNG|DURCHBRUCH"),
        ("poteau", r"POTEAUX?|POT(?![A-Z])|COLONNES?|COLUMNS?|COLS?(?![A-Z])|KOLOMMEN|"
                   r"KOLOM|STUTZEN|STUETZEN|STUTZE|STUETZE|PILIERS?"),
        ("poutre", r"POUTRES?|RETOMBEES?|LINTEAUX|LINTEAU|SOMMIERS?|BEAMS?|BALKEN|BALK|"
                   r"UNTERZ(?:UG|UGE|UEGE)|LATEI|LINTELS?"),
        ("voile", r"VOILES?|MURS?(?![A-Z])|REFENDS?|WALLS?|WANDEN|WAND|WAENDE|WANDE"),
        ("dalle", r"DALLES?|PLANCHERS?|HOURDIS|PREDALLES?|SLABS?|VLOEREN|VLOER|PLATEN|"
                  r"PLAAT|DECKEN?"),
        ("axe", r"AXES?(?![A-Z])|AXIS|GRIDS?|GRILLES?|TRAMES?|STRAMIEN|RASTER|ACHSEN?|"
                r"BULLES?|BUBBLES?"),
        ("hachure", r"HACH|HATCH|ARCERING|SCHRAFF"),
    )
)

#: Types de ligne d'axe (trait-point) et de retombée vue par-dessous (tirets).
_LIGNE_AXE: Final[re.Pattern[str]] = re.compile(
    r"CENTER|CENTRE|DASHDOT|DASH_DOT|AXE|AXIS|MITTE|ACAD_ISO0[4589]W100|ACAD_ISO1[0-4]W100")
_LIGNE_CACHEE: Final[re.Pattern[str]] = re.compile(
    r"HIDDEN|DASHED|CACHE|TIRET|VERDECKT|GESTRICHELT|STREEP|ACAD_ISO0[23]W100")

#: Des noms qui ne disent RIEN de l'élément : on les note pour le dire.
_GENERIQUES: Final[re.Pattern[str]] = re.compile(
    r"^(?:0|COFFRAGE|STRUCTURE|STRUCT|BETON|BA|GROS.?OEUVRE|GO|BOUWKUNDIG|RUWBOUW|"
    r"ROHBAU|TRAGWERK|DEFPOINTS|S|A|PLAN)$")


@dataclass(frozen=True)
class Classement:
    role: Role
    #: ``bloc``, ``calque``, ``style`` (PDF), ``type_de_ligne`` ou ``aucune``.
    regle: str
    #: Le nom qui a décidé (calque, bloc, type de ligne), cité tel quel.
    motif: str | None = None
    #: Trait en tirets sur un calque qui ne dit rien : indice de retombée.
    cache: bool = False
    #: Calque nommé mais générique (`COFFRAGE`, `0`) : la forme décidera.
    generique: bool = False


def _normaliser(nom: str) -> str:
    sans_accents = "".join(c for c in unicodedata.normalize("NFKD", nom)
                           if not unicodedata.combining(c))
    return sans_accents.upper()


#: Un texte qui NOMME un pieu (« PIEU 12 », « pile P3 », « Paal 4 ») : jamais le
#: repère d'un poteau, d'un voile ou d'une poutre.
_TEXTE_PIEU: Final[re.Pattern[str]] = re.compile(_AVANT + r"(?:" + _PIEU + r")")


def nomme_un_pieu(texte: str) -> bool:
    return bool(_TEXTE_PIEU.search(_normaliser(texte)))


def role_du_nom(nom: str) -> Role | None:
    """Le rôle qu'un nom de calque ou de bloc désigne, ou ``None``."""
    norme = _normaliser(nom)
    for role, motif in _ROLES:
        if motif.search(norme):
            return role  # type: ignore[return-value]
    return None


def est_type_de_ligne_d_axe(nom: str) -> bool:
    return bool(_LIGNE_AXE.search(_normaliser(nom)))


def est_type_de_ligne_cache(nom: str) -> bool:
    return bool(_LIGNE_CACHEE.search(_normaliser(nom)))


@lru_cache(maxsize=8192)
def classer(calque: str, blocs: tuple[str, ...], type_ligne: str) -> Classement:
    """Le rôle d'une primitive, et ce qui l'a décidé.

    UNE FEUILLE PDF N'A PAS DE CALQUES : son « calque » est le style du trait
    (``pdf:#DE0000:1.5``). Un style APPRIS de la feuille — celui des traits qui
    partent des bulles, celui des lignes qui portent les cotes — est nommé
    ``pdf:axe:…`` ou ``pdf:cote:…`` ; la règle est alors « style ». Un autre
    style ne dit rien : la forme décidera.
    """
    if calque.startswith("pdf:"):
        morceaux = calque.split(":")
        if len(morceaux) > 1 and morceaux[1] in ("axe", "cote"):
            return Classement(morceaux[1], "style", calque)  # type: ignore[arg-type]
        return Classement("inconnu", "aucune", None, cache=calque.endswith(":tirets"),
                          generique=True)
    for bloc in reversed(blocs):
        role = role_du_nom(bloc)
        if role is not None:
            return Classement(role, "bloc", bloc)
    role = role_du_nom(calque)
    if role is not None:
        return Classement(role, "calque", calque)
    if est_type_de_ligne_d_axe(type_ligne):
        return Classement("axe", "type_de_ligne", type_ligne)
    return Classement("inconnu", "aucune", None,
                      cache=est_type_de_ligne_cache(type_ligne),
                      generique=bool(_GENERIQUES.match(_normaliser(calque))))
