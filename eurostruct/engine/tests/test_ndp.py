"""Nationally determined parameters.

These tests defend interdictions 2 and 3 of the cahier des charges: no invented
value, and no Eurocode applied without its National Annex.
"""

from __future__ import annotations

import pytest

from eurostruct_engine.ec2 import RectangularSection, design_flexure
from eurostruct_engine.exceptions import UnverifiedNationalParameter
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.ndp import NdpStatus, available_countries, load_parameter_set
from eurostruct_engine.units import Q_


def test_countries_available() -> None:
    assert {"BE", "FR"} <= set(available_countries())


def test_unknown_country_is_refused() -> None:
    with pytest.raises(KeyError, match="aucun jeu de NDP"):
        load_parameter_set("XX")


def test_strict_mode_refuses_unverified_parameter() -> None:
    """The seeded sets are unverified, so strict mode must refuse to use them.

    This is the mechanism preventing a signed note de calcul from being built
    on an assumed National Annex.
    """
    p = load_parameter_set("BE", strict=True)
    with pytest.raises(UnverifiedNationalParameter) as e:
        p.get("EC2.alpha_cc")
    assert e.value.status == NdpStatus.NA_PENDING_VERIFICATION.value
    assert "ingenieur habilite" in str(e.value)


def test_strict_mode_blocks_a_whole_calculation() -> None:
    p = load_parameter_set("FR", strict=True)
    with pytest.raises(UnverifiedNationalParameter):
        design_flexure(
            section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
            concrete=concrete("C30/37"), steel=reinforcement("B500B"),
            M_Ed=Q_(250, "kN*m"), params=p,
        )


def test_missing_parameter_is_never_defaulted(params_be) -> None:
    """A gap in the data set must raise, not silently fall back to the EN value."""
    with pytest.raises(KeyError, match="Aucune valeur par defaut"):
        params_be.get("EC2.parametre_inexistant")


def test_every_seeded_parameter_declares_its_source_and_status() -> None:
    for country in ("BE", "FR"):
        p = load_parameter_set(country, strict=False)
        assert p.values, f"jeu de NDP vide pour {country}"
        for key, v in p.values.items():
            assert v.source, f"{country}/{key}: source manquante"
            assert v.standard and v.clause, f"{country}/{key}: clause manquante"
            assert v.description, f"{country}/{key}: description manquante"
            assert isinstance(v.status, NdpStatus)


def test_seeded_sets_are_honestly_flagged_as_unverified() -> None:
    """Guards against someone marking the placeholder data 'confirmed'.

    Flipping a value to ``na_confirmed`` is a deliberate act that must be
    accompanied by the name of the engineer who read the published annex and
    the date they did so. This test makes an accidental flip visible.
    """
    for country in ("BE", "FR"):
        p = load_parameter_set(country, strict=False)
        for key, v in p.values.items():
            if v.status is NdpStatus.NA_CONFIRMED:
                assert v.confirmed_by, (
                    f"{country}/{key} est marque 'na_confirmed' sans nom de "
                    "verificateur. Renseigner confirmed_by et confirmed_at."
                )
                assert v.confirmed_at, f"{country}/{key}: date de verification manquante"
            else:
                assert key in p.unverified_keys()


def test_summary_is_what_the_note_de_calcul_prints(params_be) -> None:
    s = params_be.summary()
    assert s["country"] == "BE"
    assert s["version"]
    assert s["published_at"]
    assert set(s["unverified"]) == set(params_be.unverified_keys())
    entry = s["parameters"]["EC2.alpha_cc"]
    assert entry["clause"].startswith("EN 1992-1-1")
    assert entry["en_recommended"] == 1.0


def test_calculation_freezes_the_parameter_set_it_used(params_be) -> None:
    """Section 4.2: the NDP set, its version and its date go into the result."""
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"), params=params_be,
    )
    assert r.ndp_summary["country"] == "BE"
    assert r.ndp_summary["version"]
    assert r.ndp_summary["published_at"]
    assert r.ndp_summary["unverified"]  # honestly reported in the deliverable
