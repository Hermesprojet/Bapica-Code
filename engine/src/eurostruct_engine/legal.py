"""Legal notices and the role of the software — TICKET 4.2.

    "Positionner l'application comme assistant de bureau d'etudes, pas comme
     signataire. Aucun document final ne presente le logiciel comme ingenieur
     ou signataire."

One source for every wording that appears on a deliverable, in the five
languages of §11 (FR / NL / EN / ES / DE). Hard-coding the notice in each
generator is how a translation ends up missing from one document type.

Why the wording matters, and not only legally: in the four target markets a
piece of software cannot be the signatory. Belgium requires an architect and a
stability engineer, with compulsory decennial insurance; France a design office
and, depending on the works, a contrôleur technique; Spain the visado colegial
and a Dirección Facultativa; Germany a Prüfstatiker and Bauvorlageberechtigung.
None of those regimes admits a program. The software assists; a named human
answers for the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Mapping

__all__ = [
    "Language",
    "MANDATORY_NOTICE",
    "SOFTWARE_ROLE",
    "DRAFT_WATERMARK",
    "FORBIDDEN_SELF_DESCRIPTIONS",
    "notice",
    "CountryLegalRegime",
    "LEGAL_REGIMES",
]


class Language(str, Enum):
    FR = "fr"
    NL = "nl"
    EN = "en"
    ES = "es"
    DE = "de"


#: Cahier des charges §9: on every page of every deliverable.
MANDATORY_NOTICE: Final[Mapping[Language, str]] = {
    Language.FR: (
        "Document genere par assistance logicielle. Doit etre verifie, complete "
        "et signe par un ingenieur habilite avant tout usage en construction."
    ),
    Language.NL: (
        "Document gegenereerd met software-ondersteuning. Moet worden "
        "geverifieerd, aangevuld en ondertekend door een bevoegd ingenieur voor "
        "elk gebruik in de bouw."
    ),
    Language.EN: (
        "Document produced with software assistance. It must be checked, "
        "completed and signed by a qualified engineer before any use in "
        "construction."
    ),
    Language.ES: (
        "Documento generado con asistencia informatica. Debe ser verificado, "
        "completado y firmado por un ingeniero habilitado antes de cualquier uso "
        "en obra."
    ),
    Language.DE: (
        "Mit Softwareunterstutzung erstelltes Dokument. Es muss vor jeder "
        "Verwendung im Bauwesen von einem bauvorlageberechtigten Ingenieur "
        "geprueft, ergaenzt und unterzeichnet werden."
    ),
}

#: What the software is, stated on the cover page of a note de calcul.
SOFTWARE_ROLE: Final[Mapping[Language, str]] = {
    Language.FR: (
        "EUROSTRUCT est un outil d'aide a la conception. Il n'est ni un "
        "organisme de certification, ni un bureau d'etudes, ni un signataire. "
        "La responsabilite du dimensionnement demeure entierement celle de "
        "l'ingenieur qui valide et signe le present document."
    ),
    Language.NL: (
        "EUROSTRUCT is een ontwerphulpmiddel. Het is geen certificatie-"
        "instelling, geen studiebureau en geen ondertekenaar. De "
        "verantwoordelijkheid voor het ontwerp blijft volledig bij de ingenieur "
        "die dit document valideert en ondertekent."
    ),
    Language.EN: (
        "EUROSTRUCT is a design aid. It is not a certification body, not a "
        "design office and not a signatory. Responsibility for the design "
        "remains entirely with the engineer who validates and signs this "
        "document."
    ),
    Language.ES: (
        "EUROSTRUCT es una herramienta de ayuda al diseno. No es un organismo "
        "de certificacion, ni una oficina tecnica, ni un firmante. La "
        "responsabilidad del dimensionado corresponde integramente al ingeniero "
        "que valida y firma este documento."
    ),
    Language.DE: (
        "EUROSTRUCT ist ein Entwurfswerkzeug. Es ist weder eine "
        "Zertifizierungsstelle noch ein Ingenieurbuero noch ein Unterzeichner. "
        "Die Verantwortung fuer die Bemessung liegt vollstaendig bei dem "
        "Ingenieur, der dieses Dokument prueft und unterzeichnet."
    ),
}

#: Stamped across any deliverable that has not been validated.
DRAFT_WATERMARK: Final[Mapping[Language, str]] = {
    Language.FR: "PROJET — NON VALIDE",
    Language.NL: "ONTWERP — NIET GEVALIDEERD",
    Language.EN: "DRAFT — NOT VALIDATED",
    Language.ES: "BORRADOR — NO VALIDADO",
    Language.DE: "ENTWURF — NICHT GEPRUEFT",
}

#: Phrases a deliverable may never contain about the software. Checked by
#: ``test_legal.py``: a wording change that made the software look like the
#: signatory would fail the build.
FORBIDDEN_SELF_DESCRIPTIONS: Final[tuple[str, ...]] = (
    "calcule et signe par eurostruct",
    "note de calcul certifiee par eurostruct",
    "eurostruct certifie",
    "eurostruct garantit",
    "eurostruct, ingenieur",
    "valide par eurostruct",
    "approuve par eurostruct",
    "certified by eurostruct",
    "eurostruct guarantees",
    "signed by eurostruct",
)


def notice(language: Language = Language.FR) -> str:
    """The mandatory notice, in *language*."""
    return MANDATORY_NOTICE[language]


@dataclass(frozen=True, slots=True)
class CountryLegalRegime:
    """Who must intervene, per market — cahier des charges §9."""

    country_code: str
    signatory_role: str
    obligations: tuple[str, ...]
    retention_years: int = 10

    def to_dict(self) -> dict[str, object]:
        return {
            "country_code": self.country_code,
            "signatory_role": self.signatory_role,
            "obligations": list(self.obligations),
            "retention_years": self.retention_years,
        }


LEGAL_REGIMES: Final[Mapping[str, CountryLegalRegime]] = {
    "BE": CountryLegalRegime(
        country_code="BE",
        signatory_role="Ingenieur en stabilite, aux cotes de l'architecte",
        obligations=(
            "Architecte obligatoire (loi du 20/02/1939).",
            "Assurance obligatoire de la responsabilite civile decennale "
            "(loi Peeters).",
            "Permis d'urbanisme regionalise (Wallonie, Flandre, Bruxelles).",
        ),
    ),
    "FR": CountryLegalRegime(
        country_code="FR",
        signatory_role="Ingenieur du bureau d'etudes technique",
        obligations=(
            "Controle technique obligatoire (CTC) selon la nature de l'ouvrage; "
            "missions L/LE/PS/SEI.",
            "Assurance decennale (art. 1792 C. civ.).",
            "DTU applicables en execution.",
        ),
    ),
    "ES": CountryLegalRegime(
        country_code="ES",
        signatory_role="Tecnico competente, avec visado colegial",
        obligations=(
            "Visado colegial par le Colegio professionnel.",
            "Direccion Facultativa obligatoire.",
            "Referentiel opposable: Codigo Estructural (RD 470/2021), CTE, "
            "NCSE-02.",
        ),
    ),
    "DE": CountryLegalRegime(
        country_code="DE",
        signatory_role="Aufsteller der Standsicherheitsnachweise",
        obligations=(
            "Verification independante par un Prufstatiker / Prufingenieur fur "
            "Standsicherheit, selon le Land.",
            "Bauvorlageberechtigung requise pour deposer les documents.",
            "MVV TB du Land applicable.",
        ),
    ),
}
