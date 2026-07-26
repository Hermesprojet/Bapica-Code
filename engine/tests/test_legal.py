"""Legal notices and the role of the software — TICKET 4.2.

    "Aucun document final ne presente le logiciel comme ingenieur ou
     signataire."

That is a property of every generator, so it is tested against the documents
they actually produce, not against the constants in isolation.
"""

from __future__ import annotations

import ezdxf
import pytest

from eurostruct_engine.drawing import BarRow, BeamSectionSpec, build_beam_section
from eurostruct_engine.legal import (
    DRAFT_WATERMARK,
    FORBIDDEN_SELF_DESCRIPTIONS,
    LEGAL_REGIMES,
    MANDATORY_NOTICE,
    SOFTWARE_ROLE,
    Language,
    notice,
)

ALL_LANGUAGES = tuple(Language)


def _texts_of(doc) -> str:
    return " ".join(e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT")


def _spec(**kw) -> BeamSectionSpec:
    base = dict(
        b=300, h=600, cover=30, link_diameter=8,
        bottom=(BarRow(count=4, diameter=20, mark="A1", length=6200),),
        link_spacing=200, project="EUROSTRUCT", element="P1",
    )
    base.update(kw)
    return BeamSectionSpec(**base)


# ---------------------------------------------------------------------------
# The notices themselves
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("language", ALL_LANGUAGES)
def test_every_notice_exists_in_the_five_languages(language: Language) -> None:
    """§11 requires FR/NL/EN/ES/DE, technical terminology included."""
    for table in (MANDATORY_NOTICE, SOFTWARE_ROLE, DRAFT_WATERMARK):
        assert language in table
        assert table[language].strip()


@pytest.mark.parametrize("language", ALL_LANGUAGES)
def test_mandatory_notice_states_the_three_obligations(language: Language) -> None:
    """Checked, completed, signed — by a qualified engineer, before use."""
    text = MANDATORY_NOTICE[language].lower()
    verbs = {
        Language.FR: ("verifie", "complete", "signe", "ingenieur habilite"),
        Language.NL: ("geverifieerd", "aangevuld", "ondertekend", "bevoegd ingenieur"),
        Language.EN: ("checked", "completed", "signed", "qualified engineer"),
        Language.ES: ("verificado", "completado", "firmado", "ingeniero habilitado"),
        Language.DE: ("prueft", "ergaenzt", "unterzeichnet", "ingenieur"),
    }[language]
    for fragment in verbs:
        assert fragment in text, f"'{fragment}' absent de la mention {language.value}"


@pytest.mark.parametrize("language", ALL_LANGUAGES)
def test_software_role_denies_being_a_signatory(language: Language) -> None:
    text = SOFTWARE_ROLE[language].lower()
    assert "eurostruct" in text
    # It says what it is not, and where responsibility sits.
    negations = {
        Language.FR: ("n'est ni", "signataire", "responsabilite"),
        Language.NL: ("geen", "ondertekenaar", "verantwoordelijkheid"),
        Language.EN: ("not a", "signatory", "responsibility"),
        Language.ES: ("no es", "firmante", "responsabilidad"),
        Language.DE: ("weder", "unterzeichner", "verantwortung"),
    }[language]
    for fragment in negations:
        assert fragment in text, f"'{fragment}' absent du role {language.value}"


def test_notice_helper_defaults_to_french() -> None:
    assert notice() == MANDATORY_NOTICE[Language.FR]
    assert notice(Language.DE) == MANDATORY_NOTICE[Language.DE]


# ---------------------------------------------------------------------------
# What the generated documents actually contain
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("language", ALL_LANGUAGES)
def test_drawing_carries_the_notice_in_its_language(language: Language, tmp_path) -> None:
    doc, _ = build_beam_section(_spec(language=language, validated=True))
    path = tmp_path / "s.dxf"
    doc.saveas(path)
    texts = " ".join(_texts_of(ezdxf.readfile(path)).split())

    # The notice is wrapped across lines; check its distinctive fragments.
    expected = MANDATORY_NOTICE[language]
    head = " ".join(expected.split()[:4])
    tail = " ".join(expected.split()[-4:])
    assert head in texts, f"debut de mention {language.value} absent"
    assert tail in texts, f"fin de mention {language.value} absente"


def test_unvalidated_drawing_is_watermarked() -> None:
    """§9: a sheet nobody signed must not look like one somebody did."""
    doc, _ = build_beam_section(_spec(validated=False))
    assert DRAFT_WATERMARK[Language.FR] in _texts_of(doc)


def test_validated_drawing_carries_no_watermark() -> None:
    doc, _ = build_beam_section(_spec(validated=True))
    assert DRAFT_WATERMARK[Language.FR] not in _texts_of(doc)


def test_watermark_follows_the_document_language() -> None:
    doc, _ = build_beam_section(_spec(validated=False, language=Language.DE))
    assert DRAFT_WATERMARK[Language.DE] in _texts_of(doc)


def test_drawings_default_to_unvalidated() -> None:
    """The safe default: a drawing is a draft until someone says otherwise."""
    assert _spec().validated is False


@pytest.mark.parametrize("validated", [True, False])
def test_no_document_presents_the_software_as_signatory(validated: bool) -> None:
    """The blocking property of TICKET 4.2, checked on the real output."""
    doc, _ = build_beam_section(_spec(validated=validated))
    texts = " ".join(_texts_of(doc).lower().split())
    for phrase in FORBIDDEN_SELF_DESCRIPTIONS:
        assert phrase not in texts, (
            f"le livrable presente le logiciel comme signataire: '{phrase}'"
        )
    # The software appears only as the engine that produced the file.
    assert "eurostruct-engine" in texts


def test_forbidden_list_covers_the_ways_it_could_go_wrong() -> None:
    joined = " ".join(FORBIDDEN_SELF_DESCRIPTIONS)
    for verb in ("certifie", "garantit", "signe", "valide", "approuve"):
        assert verb in joined, (
            f"la liste des formulations interdites ne couvre pas '{verb}'"
        )


# ---------------------------------------------------------------------------
# Per-country regime
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("country", ["BE", "FR", "ES", "DE"])
def test_each_market_declares_who_must_sign(country: str) -> None:
    regime = LEGAL_REGIMES[country]
    assert regime.signatory_role
    assert regime.obligations
    assert regime.retention_years >= 10  # décennale


def test_country_specific_obligations_are_named() -> None:
    """Not generic boilerplate: the actual regime of each market."""
    text = {c: " ".join(r.obligations).lower() for c, r in LEGAL_REGIMES.items()}
    assert "peeters" in text["BE"]
    assert "1792" in text["FR"] and "ctc" in text["FR"]
    assert "visado colegial" in text["ES"] and "codigo estructural" in text["ES"]
    assert "prufstatiker" in text["DE"] and "bauvorlageberechtigung" in text["DE"]
