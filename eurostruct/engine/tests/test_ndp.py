"""National parameters — EPIC 1.

Defends interdictions 2, 3 and 4 of the cahier des charges: no invented value,
no Eurocode applied without its National Annex, and Spain not treated as a
pure-Eurocode country.
"""

from __future__ import annotations

from datetime import date

import pytest

from eurostruct_engine.basis import DesignSituation
from eurostruct_engine.ec2 import RectangularSection, design_flexure
from eurostruct_engine.ec2.beam_flexure import EC2_11, required_parameters
from eurostruct_engine.exceptions import (
    DeprecatedNationalParameter,
    NationalAnnexIncomplete,
    UnverifiedNationalParameter,
)
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.ndp import (
    ValidationStatus,
    available_countries,
    load_country_registry,
    load_parameter_set,
)
from eurostruct_engine.units import Q_

AS_OF = date(2026, 7, 26)
ALL_COUNTRIES = ("BE", "FR", "ES", "DE")


# ---------------------------------------------------------------------------
# TICKET 1.2 — registry per country / standard / part / version
# ---------------------------------------------------------------------------
def test_all_four_markets_are_present() -> None:
    assert set(available_countries()) == set(ALL_COUNTRIES)


def test_unknown_country_is_refused() -> None:
    with pytest.raises(KeyError, match="aucun referentiel national"):
        load_country_registry("XX")


@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_registry_carries_the_annex_identity(country: str) -> None:
    """TICKET 1.1: family, part, reference, edition and validity are separate."""
    reg = load_country_registry(country)
    annex = reg.annex_for("EN 1992-1-1", AS_OF)
    assert annex is not None
    assert annex.standard_family == "EN 1992"
    assert annex.part == "1-1"
    assert annex.reference
    assert annex.edition
    assert annex.source_official
    assert annex.effective_from <= AS_OF


@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_every_parameter_declares_source_status_and_clause(country: str) -> None:
    reg = load_country_registry(country)
    for annex in reg.annexes:
        for p in annex.parameters:
            assert p.parameter_name and p.clause and p.description
            assert p.source_official
            assert isinstance(p.validation_status, ValidationStatus)
            assert p.key.startswith(f"{p.standard}:")
            assert p.unit


def test_engine_refuses_to_guess_a_missing_annex() -> None:
    """TICKET 1.2, acceptance criterion 2: no substitution, no fallback."""
    p = load_parameter_set("BE", strict=False, as_of=AS_OF)
    with pytest.raises(KeyError, match="ne devine pas une annexe absente"):
        p.get("EN 1993-1-1:gamma_M0")          # steel annex not loaded
    report = p.preflight(["EN 1993-1-1:gamma_M0"])
    assert report.blocking[0].reason == "annex_missing"


def test_annex_not_yet_in_force_is_not_selected() -> None:
    """Resolution is by date: an annex is not used before it takes effect."""
    reg = load_country_registry("BE")
    annex = reg.annex_for("EN 1992-1-1", date(2000, 1, 1))
    assert annex is None


def test_parameter_set_is_pinned_to_a_reference_date() -> None:
    p = load_parameter_set("FR", strict=False, as_of=AS_OF)
    assert p.as_of == AS_OF
    assert p.summary()["as_of"] == "2026-07-26"


def test_invalid_key_format_is_rejected() -> None:
    p = load_parameter_set("BE", strict=False, as_of=AS_OF)
    with pytest.raises(KeyError, match="Format attendu"):
        p.get("alpha_cc")


# ---------------------------------------------------------------------------
# TICKET 1.3 — strict mode blocks, and reports every blocker at once
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_strict_mode_blocks_every_unverified_parameter(country: str) -> None:
    p = load_parameter_set(country, strict=True, as_of=AS_OF)
    required = required_parameters(DesignSituation.PERSISTENT)
    report = p.preflight(required)
    assert not report.ok
    # All of them, not just the first: that is the point of the preflight.
    assert len(report.blocking) == len(required)
    assert {b.reason for b in report.blocking} == {"pending_verification"}


def test_preflight_report_is_readable_and_machine_parsable() -> None:
    """Acceptance criterion: usable by a human and by CI."""
    p = load_parameter_set("BE", strict=True, as_of=AS_OF)
    report = p.preflight(required_parameters(DesignSituation.PERSISTENT))

    text = report.render()
    assert "Calcul impossible pour BE" in text
    assert "NBN EN 1992-1-1 ANB" in text
    assert "ingenieur habilite" in text
    for b in report.blocking:
        assert b.key in text

    data = report.to_dict()
    assert data["ok"] is False
    assert data["country_code"] == "BE"
    assert data["as_of"] == "2026-07-26"
    assert len(data["blocking"]) == len(report.blocking)
    assert set(data["blocking"][0]) >= {
        "key", "reason", "detail", "standard", "parameter_name"
    }


def test_calculation_is_blocked_before_it_starts() -> None:
    """The whole list comes back in one exception, not one failure at a time."""
    p = load_parameter_set("FR", strict=True, as_of=AS_OF)
    with pytest.raises(NationalAnnexIncomplete) as e:
        design_flexure(
            section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
            concrete=concrete("C30/37"), steel=reinforcement("B500B"),
            M_Ed=Q_(250, "kN*m"), params=p,
        )
    assert len(e.value.blocking) == 8
    assert e.value.to_dict()["ok"] is False
    assert "NF EN 1992-1-1/NA" in str(e.value)


def test_single_lookup_still_raises_in_strict_mode() -> None:
    p = load_parameter_set("BE", strict=True, as_of=AS_OF)
    with pytest.raises(UnverifiedNationalParameter):
        p.get(f"{EC2_11}:alpha_cc")


def test_non_strict_mode_allows_exploratory_work() -> None:
    p = load_parameter_set("BE", strict=False, as_of=AS_OF)
    assert p.preflight(required_parameters(DesignSituation.PERSISTENT)).ok
    assert p.get(f"{EC2_11}:alpha_cc").magnitude == 1.0


def test_missing_parameter_is_never_defaulted() -> None:
    p = load_parameter_set("BE", strict=False, as_of=AS_OF)
    with pytest.raises(KeyError, match="Aucune valeur par defaut"):
        p.get(f"{EC2_11}:parametre_inexistant")
    assert p.preflight([f"{EC2_11}:parametre_inexistant"]).blocking[0].reason == "missing"


# ---------------------------------------------------------------------------
# Deprecated values are refused in every mode
# ---------------------------------------------------------------------------
def test_deprecated_value_is_refused_even_outside_strict_mode() -> None:
    """A deprecated value is known wrong, unlike a merely unverified one.

    Built by rebuilding the registry with one parameter marked deprecated,
    rather than by patching methods: the frozen dataclasses make that both
    easy and faithful to how a real superseded edition would look.
    """
    import dataclasses

    from eurostruct_engine.ndp.registry import ParameterSet

    base = load_parameter_set("BE", strict=False, as_of=AS_OF)
    annex = base.registry.annexes[0]
    patched_params = tuple(
        dataclasses.replace(
            prm,
            validation_status=ValidationStatus.DEPRECATED,
            notes="remplacee par l'edition suivante",
        )
        if prm.parameter_name == "alpha_cc" else prm
        for prm in annex.parameters
    )
    registry = dataclasses.replace(
        base.registry,
        annexes=(dataclasses.replace(annex, parameters=patched_params),),
    )
    ps = ParameterSet(registry=registry, region=None, as_of=AS_OF, strict=False)

    report = ps.preflight([f"{EC2_11}:alpha_cc"])
    assert report.blocking[0].reason == "deprecated"
    with pytest.raises(DeprecatedNationalParameter, match="obsolete"):
        ps.get(f"{EC2_11}:alpha_cc")


# ---------------------------------------------------------------------------
# Interdiction 4 — Spain is not a pure-Eurocode country
# ---------------------------------------------------------------------------
def test_spain_declares_its_binding_framework() -> None:
    reg = load_country_registry("ES")
    fw = reg.regulatory_framework
    assert "Codigo Estructural" in fw.binding_reference
    assert "CTE" in fw.binding_reference
    assert "NCSE-02" in fw.binding_reference
    assert "PAS" in fw.eurocode_status  # "n'est PAS un pays « Eurocode pur »"
    assert "visado colegial" in fw.verification_regime.lower()


def test_germany_declares_its_verification_regime() -> None:
    fw = load_country_registry("DE").regulatory_framework
    assert "MVV TB" in fw.binding_reference
    assert "Prufstatiker" in fw.verification_regime
    assert "Bauvorlageberechtigung" in fw.verification_regime


@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_regulatory_framework_reaches_the_note_de_calcul(country: str) -> None:
    """The note must state which framework the project was verified under."""
    summary = load_parameter_set(country, strict=False, as_of=AS_OF).summary()
    fw = summary["regulatory_framework"]
    assert fw["binding_reference"] and fw["eurocode_status"]
    assert fw["verification_regime"]


# ---------------------------------------------------------------------------
# Honesty of the shipped dataset
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_confirmed_values_carry_a_named_verifier(country: str) -> None:
    """Guards against a placeholder being flipped to 'confirmed' by accident."""
    reg = load_country_registry(country)
    for annex in reg.annexes:
        for p in annex.parameters:
            if p.validation_status is ValidationStatus.CONFIRMED:
                assert p.verified_by, (
                    f"{country}/{p.key} est 'confirmed' sans verified_by. "
                    "Renseigner qui a releve la valeur dans l'annexe publiee."
                )
                assert p.verified_at, f"{country}/{p.key}: verified_at manquant"
                assert p.source_type.value == "national_annex", (
                    f"{country}/{p.key}: une valeur confirmee doit venir de "
                    "l'Annexe Nationale, pas de la recommandation EN."
                )


@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_shipped_dataset_is_flagged_unverified(country: str) -> None:
    """No annex has been read yet, and the data says so."""
    ps = load_parameter_set(country, strict=False, as_of=AS_OF)
    assert set(ps.unverified_keys()) == set(ps.keys())


def test_calculation_freezes_the_parameter_set_it_used() -> None:
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"),
        params=load_parameter_set("BE", strict=False, as_of=AS_OF),
    )
    ndp = r.ndp_summary
    assert ndp["country"] == "BE"
    assert ndp["as_of"] == "2026-07-26"
    assert ndp["annexes"][0]["reference"] == "NBN EN 1992-1-1 ANB"
    assert ndp["unverified"]              # honestly reported in the deliverable
    assert ndp["regulatory_framework"]["binding_reference"]
