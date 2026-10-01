"""Le format d'un fichier, constaté sur ses octets.

NI L'EXTENSION, NI LE TYPE ANNONCÉ PAR LE NAVIGATEUR. Un ``plan.pdf`` peut
être une archive ZIP renommée, et un ``Content-Type`` vient de celui qui
envoie. La seule source qui ne ment pas sur le format est la signature que
le format impose lui-même en tête de fichier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = [
    "FORMATS",
    "FormatDetecte",
    "FormatNonPrisEnCharge",
    "VERSIONS_DWG",
    "detecter_format",
]


class FormatNonPrisEnCharge(ValueError):
    """Les octets ne sont ni un PDF, ni un DXF, ni un DWG."""


@dataclass(frozen=True)
class FormatDetecte:
    format: str
    type_media: str
    extension: str
    version: str | None = None
    libelle_version: str | None = None


#: Les trois formats reçus, leur type de média et leur extension de stockage.
FORMATS: Final[dict[str, tuple[str, str]]] = {
    "pdf": ("application/pdf", "pdf"),
    "dxf": ("image/vnd.dxf", "dxf"),
    "dwg": ("image/vnd.dwg", "dwg"),
}

#: Les versions DWG que la signature ``ACxxxx`` permet de NOMMER. Lire la
#: version n'est pas lire le dessin : c'est l'en-tête de six octets, documenté
#: publiquement, et rien de plus (interdiction 7).
VERSIONS_DWG: Final[dict[str, str]] = {
    "AC1009": "AutoCAD R11/R12",
    "AC1012": "AutoCAD R13",
    "AC1014": "AutoCAD R14",
    "AC1015": "AutoCAD 2000",
    "AC1018": "AutoCAD 2004",
    "AC1021": "AutoCAD 2007",
    "AC1024": "AutoCAD 2010",
    "AC1027": "AutoCAD 2013",
    "AC1032": "AutoCAD 2018",
}

_DXF_BINAIRE: Final[bytes] = b"AutoCAD Binary DXF\r\n\x1a\x00"
_DWG: Final[re.Pattern[bytes]] = re.compile(rb"^AC10\d\d")


def detecter_format(octets: bytes) -> FormatDetecte:
    """Le format des octets, ou :class:`FormatNonPrisEnCharge`."""
    if not octets:
        raise FormatNonPrisEnCharge("fichier vide: aucun format a constater.")

    # PDF : `%PDF-` dans le premier kilo-octet (la norme tolere un prefixe).
    if b"%PDF-" in octets[:1024]:
        return _detecte("pdf")

    if octets.startswith(_DXF_BINAIRE):
        return _detecte("dxf", version="binaire")

    entete = _DWG.match(octets[:6])
    if entete:
        version = entete.group(0).decode("ascii")
        return _detecte("dwg", version=version,
                        libelle=VERSIONS_DWG.get(version, "version DWG inconnue"))

    if _ressemble_a_un_dxf_ascii(octets[:4096]):
        return _detecte("dxf", version="ascii")

    raise FormatNonPrisEnCharge(
        "le fichier n'est ni un PDF, ni un DXF, ni un DWG (signature non "
        "reconnue). Le format se constate sur les octets, pas sur l'extension."
    )


def _detecte(fmt: str, *, version: str | None = None,
             libelle: str | None = None) -> FormatDetecte:
    type_media, extension = FORMATS[fmt]
    return FormatDetecte(fmt, type_media, extension, version, libelle)


def _ressemble_a_un_dxf_ascii(debut: bytes) -> bool:
    """Un DXF ASCII commence par des paires « code de groupe / valeur ».

    Le premier couple utile est ``0`` / ``SECTION``, éventuellement précédé de
    commentaires ``999``. On ne demande rien de plus : c'est ezdxf qui jugera
    la suite, et dira s'il échoue.
    """
    try:
        texte = debut.decode("latin-1")
    except UnicodeDecodeError:  # pragma: no cover — latin-1 decode tout
        return False
    lignes = [ligne.strip() for ligne in texte.splitlines()]
    i = 0
    while i + 1 < len(lignes) and lignes[i] == "999":
        i += 2
    return i + 1 < len(lignes) and lignes[i] == "0" and lignes[i + 1] == "SECTION"
