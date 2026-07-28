"""EN 1992-1-1 §7 — stress limitation and crack width.

Three properties this file exists to defend:

* **The algebra is right**, checked against a calculation done by hand in the
  docstrings rather than against a previous run of the engine.
* **The National Annex actually reaches the result.** NBN EN 1992-1-1 ANB
  §7.2(2) tightens ``k1`` to 0,5 in XD/XF/XS where EN 1992-1-1 recommends 0,6
  and only imposes the limit there at all. The same beam in the same class must
  therefore come out differently in Belgium and in France — if it does not, the
  parameter layer is decorative.
* **What the module cannot know, it refuses or declares.** The creep
  coefficient is an input; pure tension is refused; an uncracked section is
  announced rather than silently producing a crack width that reads as measured.
"""

from __future__ import annotations

import math

import pytest

from eurostruct_engine.ec2 import (
    CrackControlDetail,
    ExposureClass,
    RectangularSection,
    design_serviceability,
)
from eurostruct_engine.exceptions import (
    ConditionalParameterNeedsContext,
    InconsistentInput,
    NationalAnnexIncomplete,
    OutOfValidationDomain,
)
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.materials.reinforcement import bars_area
from eurostruct_engine.units import Q_

SECTION = RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm"))
DETAIL = CrackControlDetail(
    phi=Q_(20, "mm"), cover=Q_(40, "mm"), bar_spacing=Q_(60, "mm")
)


def _design(params, **kw):
    base = dict(
        section=SECTION,
        concrete=concrete("C30/37"),
        steel=reinforcement("B500B"),
        A_s=bars_area(4, 20),
        M_qp=Q_(120, "kN*m"),
        M_char=Q_(180, "kN*m"),
        phi_creep=2.0,
        detail=DETAIL,
        exposure_class=ExposureClass.XC3,
        params=params,
        element="P1",
    )
    base.update(kw)
    return design_serviceability(**base)


# ---------------------------------------------------------------------------
# Hand calculation
# ---------------------------------------------------------------------------
@pytest.mark.reference
def test_hand_calculation_of_the_cracked_section(params_be) -> None:
    """300 × 600, d = 550, 4 HA20, C30/37, M_qp = 120 kN·m, phi = 2,0.

        E_cm     = 22 000 (38/10)^0,3                     = 32 836,568 MPa
        E_c,eff  = 32 836,568 / (1 + 2,0)                 = 10 945,523 MPa
        a_e,eff  = 200 000 / 10 945,523                   = 18,272312
        A_s      = 4 x pi x 20^2/4                        = 1 256,637 mm2

    The neutral axis was obtained by BISECTION on the equilibrium residual
    ``b x^2/2 - a_e A_s (d - x)``, not by the closed-form root the engine uses:

        x        = 223,546054 mm
        I        = 300 x 223,546^3/3 + 18,272312 x 1256,637 x (550 - 223,546)^2
                 = 3 564 197 625,87 mm4
        sigma_s  = 18,272312 x 120e6 x 326,453946 / I     = 200,832910 MPa
    """
    d = _design(params_be)
    assert d.quasi_permanent.alpha_e == pytest.approx(18.272312, abs=5e-7)
    assert d.quasi_permanent.x.to("mm").magnitude == pytest.approx(223.546054, abs=5e-7)
    assert d.quasi_permanent.I.to("mm**4").magnitude == pytest.approx(3564197625.87, abs=5e-2)
    assert d.quasi_permanent.sigma_s.to("MPa").magnitude == pytest.approx(200.832910, abs=5e-7)


@pytest.mark.reference
def test_hand_calculation_of_the_crack_width(params_be) -> None:
    """Continuing the same beam, §7.3.2(3), §7.3.4(2) and §7.3.4(3).

        h_c,ef   = min(2,5(600-550) ; (600-223,546054)/3 ; 600/2)
                 = min(125 ; 125,484649 ; 300)            = 125 mm
        rho_p,ef = 1256,637 / (300 x 125)                 = 0,03351032

        f_ct,eff = 0,30 x 30^(2/3)                        = 2,896468 MPa
        k_t      = 0,4 (charge de longue duree)
        terme    = 0,4 x (2,896468/0,03351032) x (1 + 6,090771 x 0,03351032)
                 = 34,573929 x 1,204104                   = 41,630730 MPa
        crochet  = 200,832910 - 41,630730                 = 159,202180 MPa
        eps_diff = 159,202180 / 200 000                   = 0,796011 pour mille
        plancher = 0,6 x 200,832910/200 000 = 0,602499 pour mille -> ne gouverne pas

        espacement 60 <= 5(40 + 20/2) = 250  ->  formule (7.11)
        s_r,max  = 3,4 x 40 + 0,8 x 0,5 x 0,425 x 20/0,03351032
                 = 136 + 101,461276                       = 237,461276 mm
        w_k      = 237,461276 x 0,796011e-3               = 0,18902176 mm
    """
    d = _design(params_be)
    assert d.h_c_ef.to("mm").magnitude == pytest.approx(125.0, abs=1e-9)
    assert d.rho_p_eff == pytest.approx(0.03351032, abs=5e-9)
    assert not d.eps_floor_governs
    assert d.eps_diff == pytest.approx(0.796011e-3, abs=5e-10)
    assert not d.wide_spacing
    assert d.s_r_max.to("mm").magnitude == pytest.approx(237.461276, abs=5e-7)
    assert d.w_k.to("mm").magnitude == pytest.approx(0.18902176, abs=5e-9)


@pytest.mark.reference
def test_hand_calculation_of_the_service_stresses(params_be) -> None:
    """Characteristic combination, short-term modulus — §7.2.

        a_e      = 200 000 / 32 836,568                   = 6,090771
        x        = 143,942541 mm   (meme bisection, sans fluage)
        I        = 300 x 143,942541^3/3
                   + 6,090771 x 1256,637 x (550 - 143,942541)^2
                 = 1 560 234 505,83 mm4
        sigma_c  = 180e6 x 143,942541 / 1 560 234 505,83  = 16,606258 MPa
        sigma_s  = 6,090771 x 180e6 x 406,057459 / I      = 285,326661 MPa
    """
    d = _design(params_be)
    assert d.alpha_e_short == pytest.approx(6.090771, abs=5e-7)
    assert d.characteristic.x.to("mm").magnitude == pytest.approx(143.942541, abs=5e-7)
    assert d.characteristic.I.to("mm**4").magnitude == pytest.approx(1560234505.83, abs=5e-2)
    assert d.characteristic.sigma_c.to("MPa").magnitude == pytest.approx(16.606258, abs=5e-7)
    assert d.characteristic.sigma_s.to("MPa").magnitude == pytest.approx(285.326661, abs=5e-7)


def test_the_governing_check_is_the_one_with_the_highest_ratio(params_be) -> None:
    """0,189/0,3 = 0,630 ; 16,607/18 = 0,9226 ; 285,34/400 = 0,7134."""
    d = _design(params_be)
    assert d.utilisation == pytest.approx(0.9226, abs=5e-5)
    assert d.report.governing.name.startswith("ELS — contrainte du beton")
    assert d.report.passed


# ---------------------------------------------------------------------------
# The National Annex must change the answer
# ---------------------------------------------------------------------------
def test_belgium_tightens_the_concrete_stress_limit_in_XS(
    params_be, params_fr_sls
) -> None:
    """NBN EN 1992-1-1 ANB §7.2(2): k1 = 0,5 in XD/XF/XS, 0,6 elsewhere.

    EN 1992-1-1 recommends 0,6. The same beam, same class, must therefore fail
    in Belgium and pass in France — the parameter layer earning its keep.
    """
    be = _design(params_be, exposure_class=ExposureClass.XS2)
    fr = _design(params_fr_sls, exposure_class=ExposureClass.XS2)

    assert be.sigma_c_limit.to("MPa").magnitude == pytest.approx(15.0)   # 0,5 x 30
    assert fr.sigma_c_limit.to("MPa").magnitude == pytest.approx(18.0)   # 0,6 x 30

    # Meme contrainte agissante, verdicts opposes.
    assert be.characteristic.sigma_c == fr.characteristic.sigma_c
    assert not be.report.passed
    assert fr.report.passed


def test_outside_XD_XF_XS_the_two_countries_agree(params_be, params_fr_sls) -> None:
    """The Belgian deviation is confined to the classes the annex names.

    France needs the patched fixture here — see
    :func:`test_france_refuses_crack_width_for_want_of_a_formula`.
    """
    be = _design(params_be, exposure_class=ExposureClass.XC3)
    fr = _design(params_fr_sls, exposure_class=ExposureClass.XC3)
    assert be.sigma_c_limit == fr.sigma_c_limit


def test_france_refuses_crack_width_for_want_of_a_formula(params_fr) -> None:
    """Interdiction 6, on the country that most needs it.

    NF EN 1992-1-1/NA §7.3.4(3) keeps k3 = 3,4 only up to a 25 mm cover. Beyond
    that it is ``3,4 (25/c)^{2/3}`` — a formula in the cover, not a constant. At
    the 40 mm cover used throughout this file that is 2,486, twenty-seven per
    cent below the stored value, and in the direction that UNDERSTATES crack
    spacing and therefore crack width.

    So the engine refuses. It does not fall back on 3,4, and it does not
    silently apply the EN recommendation France declined to adopt. The French
    crack-width check stays unavailable until the module can evaluate the
    expression — which is a defect to fix, not a value to sign.
    """
    with pytest.raises(NationalAnnexIncomplete) as exc:
        _design(params_fr)

    # Le refus vient du PREFLIGHT, pas de la lecture du parametre: tous les
    # bloquants sont rapportes d'un coup, avant qu'aucun calcul ne commence.
    message = str(exc.value)
    assert "k3_crack_spacing" in message
    assert "not_representable" in message
    assert "NF EN 1992-1-1/NA" in message


@pytest.mark.parametrize(
    "cls, expected_mm",
    [
        (ExposureClass.X0, 0.4),
        (ExposureClass.XC1, 0.4),
        (ExposureClass.XC2, 0.3),
        (ExposureClass.XC4, 0.3),
        (ExposureClass.XD1, 0.3),
        (ExposureClass.XS3, 0.3),
    ],
)
def test_w_max_follows_the_row_of_table_7_1N(params_be, cls, expected_mm) -> None:
    d = _design(params_be, exposure_class=cls)
    assert d.w_max.to("mm").magnitude == pytest.approx(expected_mm)


def test_the_exposure_class_reaches_the_journal_as_a_declared_case(params_be) -> None:
    """Interdiction 2: which row was read must be visible, not inferred.

    The class is not a quantity and so is not journalised as one. It is
    journalised where it acts — in the case declared to the parameter.
    """
    d = _design(params_be, exposure_class=ExposureClass.XS2)
    text = d.journal.to_json()
    assert "XD_XF_XS" in text
    assert "XC2_XC4_XD_XS" in text


def test_an_undeclared_case_is_refused_rather_than_approximated(params_be) -> None:
    """An annex slicing the classes differently must break loudly."""
    with pytest.raises(ConditionalParameterNeedsContext, match="XF_only"):
        params_be.get("EN 1992-1-1:w_max", condition="XF_only")


# ---------------------------------------------------------------------------
# Branches of §7.3.4
# ---------------------------------------------------------------------------
def test_the_strain_floor_governs_a_lightly_loaded_section(params_be) -> None:
    """(7.9) never returns less than 0,6 sigma_s / E_s, including negatives.

    At low steel stress the bracket goes negative — the concrete between cracks
    would be carrying more than the steel — and without the floor ``w_k`` would
    come out negative.
    """
    d = _design(params_be, M_qp=Q_(30, "kN*m"), M_char=Q_(45, "kN*m"))
    assert d.eps_floor_governs
    assert d.eps_diff == pytest.approx(
        0.6 * float((d.quasi_permanent.sigma_s / Q_(200000, "MPa")).magnitude)
    )
    assert d.w_k.magnitude > 0


def test_widely_spaced_bars_switch_to_equation_7_14(params_be) -> None:
    """§7.3.4(3): beyond 5(c + phi/2), (7.11) no longer describes the pattern."""
    wide = CrackControlDetail(
        phi=Q_(20, "mm"), cover=Q_(40, "mm"), bar_spacing=Q_(400, "mm")
    )
    d = _design(params_be, detail=wide)
    assert d.wide_spacing
    expected = 1.3 * (600.0 - d.quasi_permanent.x.to("mm").magnitude)
    assert d.s_r_max.to("mm").magnitude == pytest.approx(expected, rel=1e-12)


def test_the_spacing_limit_is_five_times_cover_plus_half_diameter() -> None:
    assert DETAIL.spacing_limit().to("mm").magnitude == pytest.approx(250.0)


def test_a_smaller_bar_at_equal_area_reduces_the_crack_width(params_be) -> None:
    """The reason (7.11) carries phi/rho: distribution beats total area.

    8 HA14 (1 231 mm²) against 4 HA20 (1 257 mm²) — slightly *less* steel, and
    a narrower crack. A model that missed this would advise the wrong remedy.
    """
    coarse = _design(params_be)
    fine = _design(
        params_be,
        A_s=bars_area(8, 14),
        detail=CrackControlDetail(
            phi=Q_(14, "mm"), cover=Q_(40, "mm"), bar_spacing=Q_(30, "mm")
        ),
    )
    assert float(fine.w_k.magnitude) < float(coarse.w_k.magnitude)
    # Et la cause est bien s_r,max, pas un effet de bord sur eps.
    assert float(fine.s_r_max.magnitude) < float(coarse.s_r_max.magnitude)


def test_h_c_ef_takes_the_smallest_of_the_three_bounds(params_be) -> None:
    """§7.3.2(3). On a shallow section the h/2 bound is the one that bites."""
    shallow = RectangularSection(b=Q_(300, "mm"), h=Q_(200, "mm"), d=Q_(160, "mm"))
    d = _design(
        params_be, section=shallow, M_qp=Q_(15, "kN*m"), M_char=Q_(22, "kN*m")
    )
    bounds = [
        2.5 * (200.0 - 160.0),
        (200.0 - d.quasi_permanent.x.to("mm").magnitude) / 3.0,
        200.0 / 2.0,
    ]
    assert d.h_c_ef.to("mm").magnitude == pytest.approx(min(bounds), rel=1e-12)


# ---------------------------------------------------------------------------
# Cracked or not — §7.1(2)
# ---------------------------------------------------------------------------
def test_an_uncracked_section_is_announced_not_hidden(params_be) -> None:
    """A positive w_k on a member with no crack must not read as measured."""
    d = _design(params_be, M_qp=Q_(20, "kN*m"), M_char=Q_(30, "kN*m"))
    assert not d.is_cracked
    assert "NON FISSUREE" in d.cracking_statement
    assert "SECURITAIRE" in d.cracking_statement
    assert "§7.3.2" in d.cracking_statement
    # Le journal porte le meme verdict, a l'etape ou il se decide.
    assert "NON FISSUREE" in d.journal.get("sigma_ct").description


def test_a_cracked_section_says_so_too(params_be) -> None:
    d = _design(params_be)
    assert d.is_cracked
    assert "FISSUREE" in d.journal.get("sigma_ct").description
    assert "NON FISSUREE" not in d.journal.get("sigma_ct").description


def test_the_cracking_verdict_is_not_a_failing_check(params_be) -> None:
    """An uncracked beam is a good beam; it must not fail the report."""
    d = _design(params_be, M_qp=Q_(20, "kN*m"), M_char=Q_(30, "kN*m"))
    assert not d.is_cracked
    assert d.report.passed
    assert len(d.report.checks) == 3


# ---------------------------------------------------------------------------
# What the module refuses
# ---------------------------------------------------------------------------
def test_pure_tension_is_refused(params_be) -> None:
    with pytest.raises(OutOfValidationDomain, match="traction pure"):
        _design(
            params_be,
            detail=CrackControlDetail(
                phi=Q_(20, "mm"), cover=Q_(40, "mm"),
                bar_spacing=Q_(60, "mm"), pure_tension=True,
            ),
        )


def test_a_characteristic_moment_below_the_quasi_permanent_is_refused(params_be) -> None:
    """EN 1990 §6.5.3: the characteristic combination envelops the other."""
    with pytest.raises(InconsistentInput, match="enveloppe"):
        _design(params_be, M_qp=Q_(180, "kN*m"), M_char=Q_(120, "kN*m"))


def test_a_negative_creep_coefficient_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput, match="fluage"):
        _design(params_be, phi_creep=-1.0)


def test_high_strength_concrete_is_outside_the_domain(params_be) -> None:
    with pytest.raises(OutOfValidationDomain, match="C50/60"):
        _design(params_be, concrete=concrete("C55/67"))


def test_a_section_without_reinforcement_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput, match="A_s"):
        _design(params_be, A_s=Q_(0, "mm**2"))


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------
def test_the_creep_coefficient_is_declared_as_an_input(params_be) -> None:
    """Interdiction 2: phi depends on humidity, notional size and age.

    None of which this module is told, so it must not produce one.
    """
    d = _design(params_be)
    step = d.journal.get("phi_fluage")
    assert step.provenance.detail is not None
    assert "non" in step.provenance.detail.lower()
    assert "calculee par le moteur" in step.provenance.detail


def test_both_moduli_are_journalised_separately(params_be) -> None:
    """The one modelling choice a reviewer must be able to audit.

    Equation (7.9) says alpha_e = Es/Ecm; the section analysis uses the
    effective modulus. Both appear, neither is inferred from the other.
    """
    d = _design(params_be)
    assert d.journal.get("alpha_e").value.magnitude == pytest.approx(6.0907, rel=1e-4)
    assert d.journal.get("alpha_e_eff").value.magnitude == pytest.approx(18.272, rel=1e-4)
    assert d.alpha_e_short != d.quasi_permanent.alpha_e


def test_every_national_parameter_used_is_recorded(params_be) -> None:
    d = _design(params_be)
    cited = d.journal.to_json()
    for key in (
        "k1_stress_limit", "k3_steel_stress", "w_max",
        "k3_crack_spacing", "k4_crack_spacing",
    ):
        assert key in cited, f"parametre national {key} absent du journal"


def test_the_clauses_actually_applied_are_cited(params_be) -> None:
    d = _design(params_be)
    clauses = " ".join(d.journal.clauses())
    for clause in ("§7.1(2)", "§7.2(2)", "§7.2(5)", "§7.3.2(3)",
                   "§7.3.4(2)", "§7.3.4(3)", "§7.4.3(5)"):
        assert clause in clauses, f"{clause} non cite"


def test_generation_is_deterministic(params_be) -> None:
    a, b = _design(params_be), _design(params_be)
    assert a.to_dict() == b.to_dict()


def test_the_design_serialises_whole(params_be) -> None:
    import json

    data = _design(params_be).to_dict()
    assert json.dumps(data, sort_keys=True)
    assert data["exposure_class"] == "XC3"
    assert data["is_cracked"] is True
    assert not math.isnan(data["w_k_mm"])
