"""EN 1992-1-1 §6.2 — ULS shear of a rectangular beam.

Scope of this module (the *validated domain*; anything else raises
:class:`~eurostruct_engine.exceptions.OutOfValidationDomain`):

* rectangular cross-section, constant web width ``b_w``;
* vertical shear links (``alpha = 90°``);
* concrete up to C50/60;
* no axial force (``sigma_cp = 0``) unless one is supplied;
* variable strut inclination truss of §6.2.3, with the strut angle **chosen by
  the engineer** and checked against the national bounds.

Two regimes, and the module decides which applies
-------------------------------------------------
§6.2.1(3)–(5): if ``V_Ed <= V_Rd,c`` the member needs no *designed* shear
reinforcement — only the minimum links of §9.2.2. Otherwise the whole shear is
carried by the truss, and ``V_Rd,c`` plays no further part: EN 1992-1-1 does
**not** add the two contributions. Getting that wrong is a classic and
unconservative mistake, so the two branches are kept visibly separate here.

Why the strut angle is an input, not a choice the engine makes
-------------------------------------------------------------
``cot theta`` is free between national bounds, and picking it is a design
decision with consequences the engine cannot arbitrate: a flat strut saves
links and costs longitudinal steel and web crushing capacity. The engine
therefore takes the angle, checks it against ``cot_theta_min`` and
``cot_theta_max``, and refuses if either bound is unavailable — an unchecked
bound is a missing verification, not a minor gap.

For Belgium ``cot_theta_max`` is precisely such a gap: NBN EN 1992-1-1 ANB
§6.2.3(2) replaces the 2,5 bound with an expression in the axial stress and
the link arrangement, which the scalar parameter model cannot hold. The module
refuses rather than substituting 2,5 — a value the Belgian annex does not
adopt.

alpha_cc in shear
-----------------
NBN EN 1992-1-1 ANB §3.1.6(1)P gives ``alpha_cc = 0,85`` for axial force and
bending, and 1,0 "pour les autres cas". Shear is one of the other cases, so
this module asks for the ``"other"`` branch. Inheriting the bending value would
under-estimate ``f_cd`` by 15 % and, through ``V_Rd,max``, under-estimate web
crushing resistance — in the unsafe direction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Final, Mapping

from ..basis import DesignSituation
from ..exceptions import (
    InconsistentInput,
    OutOfValidationDomain,
    UnrepresentableNationalParameter,
)
from ..materials.concrete import Concrete
from ..materials.reinforcement import Reinforcement
from ..ndp.registry import ParameterSet
from ..traceability import EC2, Journal, Provenance
from ..units import Q_, Quantity, fmt, require_dimension
from ..verification import Check, VerificationReport
from ..version import ENGINE_VERSION

__all__ = [
    "ShearSection",
    "ShearLinks",
    "ShearDesign",
    "design_shear",
    "required_parameters",
    "EC2_11",
]

EC2_11: Final = "EN 1992-1-1"

#: Highest concrete grade this module has been validated for.
_FCK_MAX_MPA = 50.0

#: §6.2.2(1): the size-effect factor is capped at 2,0.
_K_MAX = 2.0

#: §6.2.2(1): the longitudinal reinforcement ratio is capped at 0,02.
_RHO_L_MAX = 0.02

#: §6.2.3(3): sigma_cp is capped at 0,2 f_cd in the V_Rd,max expression.
_SIGMA_CP_CAP_RATIO = 0.2


def required_parameters(situation: DesignSituation) -> tuple[str, ...]:
    """National parameters this module needs, for preflight (TICKET 1.3)."""
    suffix = situation.partial_factor_suffix
    return (
        f"{EC2_11}:gamma_C_{suffix}",
        f"{EC2_11}:gamma_S_{suffix}",
        f"{EC2_11}:alpha_cc",
        f"{EC2_11}:C_Rd_c_coeff",
        f"{EC2_11}:v_min_coeff",
        f"{EC2_11}:k1_shear",
        f"{EC2_11}:cot_theta_min",
        f"{EC2_11}:cot_theta_max",
        f"{EC2_11}:alpha_cw",
        f"{EC2_11}:nu1_coeff",
        f"{EC2_11}:nu1_fck_divisor",
        f"{EC2_11}:rho_w_min_coeff",
        f"{EC2_11}:s_l_max_coeff",
    )


@dataclass(frozen=True, slots=True)
class ShearSection:
    """The section as the shear check sees it.

    :param b_w: smallest web width in the tension zone.
    :param d: effective depth.
    :param A_sl: area of *anchored* tension reinforcement, §6.2.2(1). Anchored
        means extending at least ``l_bd + d`` beyond the section considered —
        bars that stop short do not count, and the engine cannot see that from
        an area alone, so the caller states it.
    :param N_Ed: axial force, positive in compression. Zero unless supplied.
    :param A_c: gross concrete area, needed only when ``N_Ed`` is non-zero.
    """

    b_w: Quantity
    d: Quantity
    A_sl: Quantity
    N_Ed: Quantity | None = None
    A_c: Quantity | None = None

    def __post_init__(self) -> None:
        require_dimension(self.b_w, "[length]", "b_w")
        require_dimension(self.d, "[length]", "d")
        require_dimension(self.A_sl, "[length] ** 2", "A_sl")
        for name, v in (("b_w", self.b_w), ("d", self.d)):
            if v.magnitude <= 0:
                raise InconsistentInput(f"'{name}' doit etre strictement positif")
        if self.A_sl.magnitude < 0:
            raise InconsistentInput("'A_sl' ne peut pas etre negatif")
        if self.N_Ed is not None:
            require_dimension(self.N_Ed, "[force]", "N_Ed")
            if self.A_c is None:
                raise InconsistentInput(
                    "un effort normal est fourni sans l'aire de beton A_c: "
                    "sigma_cp = N_Ed / A_c ne peut pas etre calcule."
                )
            require_dimension(self.A_c, "[length] ** 2", "A_c")

    @property
    def z(self) -> Quantity:
        """Inner lever arm, taken as ``0,9 d`` for a beam without axial force.

        §6.2.3(1) allows this simplification; it is stated rather than derived
        so the note de calcul can show the assumption.
        """
        return 0.9 * self.d


@dataclass(frozen=True, slots=True)
class ShearLinks:
    """Vertical links actually detailed.

    :param A_sw: cross-sectional area of the shear reinforcement in one set of
        links (both legs of a two-legged stirrup, for instance).
    :param s: spacing along the member axis.
    """

    A_sw: Quantity
    s: Quantity

    def __post_init__(self) -> None:
        require_dimension(self.A_sw, "[length] ** 2", "A_sw")
        require_dimension(self.s, "[length]", "s")
        if self.A_sw.magnitude <= 0 or self.s.magnitude <= 0:
            raise InconsistentInput("'A_sw' et 's' doivent etre strictement positifs")

    @property
    def per_metre(self) -> Quantity:
        """``A_sw / s``, the quantity every shear formula actually uses."""
        return (self.A_sw / self.s).to("mm**2/m")


@dataclass
class ShearDesign:
    """Result of the shear verification."""

    element: str
    #: Resistance without designed shear reinforcement, §6.2.2.
    V_Rd_c: Quantity
    #: True when ``V_Ed <= V_Rd,c``: only minimum links are needed.
    links_required: bool
    #: Truss resistance, §6.2.3(3) eq. (6.8). ``None`` in the no-links regime.
    V_Rd_s: Quantity | None
    #: Web crushing resistance, eq. (6.9). ``None`` in the no-links regime.
    V_Rd_max: Quantity | None
    #: Governing resistance actually compared with ``V_Ed``.
    V_Rd: Quantity
    #: Links required by strength, as an area per unit length.
    Asw_over_s_required: Quantity
    #: Minimum from §9.2.2(5), eq. (9.5N).
    Asw_over_s_min: Quantity
    #: Maximum longitudinal spacing, §9.2.2(6), eq. (9.6N).
    s_l_max: Quantity
    #: Additional longitudinal tensile force, §6.2.3(7), eq. (6.18).
    delta_F_td: Quantity
    cot_theta: float
    report: VerificationReport
    journal: Journal
    engine_version: str = ENGINE_VERSION
    ndp_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def utilisation(self) -> float:
        return self.report.max_utilisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element,
            "engine_version": self.engine_version,
            "V_Rd_c_kN": float(self.V_Rd_c.to("kN").magnitude),
            "links_required": self.links_required,
            "V_Rd_s_kN": (
                None if self.V_Rd_s is None else float(self.V_Rd_s.to("kN").magnitude)
            ),
            "V_Rd_max_kN": (
                None if self.V_Rd_max is None
                else float(self.V_Rd_max.to("kN").magnitude)
            ),
            "V_Rd_kN": float(self.V_Rd.to("kN").magnitude),
            "Asw_over_s_required_mm2_per_m": float(
                self.Asw_over_s_required.to("mm**2/m").magnitude
            ),
            "Asw_over_s_min_mm2_per_m": float(
                self.Asw_over_s_min.to("mm**2/m").magnitude
            ),
            "s_l_max_mm": float(self.s_l_max.to("mm").magnitude),
            "delta_F_td_kN": float(self.delta_F_td.to("kN").magnitude),
            "cot_theta": self.cot_theta,
            "utilisation": self.utilisation,
            "verification": self.report.to_dict(),
            "journal": self.journal.to_dict(),
            "ndp": self.ndp_summary,
        }


def _strut_bounds(params: ParameterSet, j: Journal) -> tuple[float, float]:
    """The national bounds on ``cot theta``, or a refusal naming what is missing.

    An unchecked bound is a missing verification. Belgium's upper bound is an
    expression this model cannot hold, so the calculation stops here rather
    than falling back on the EN recommendation of 2,5 — a value the Belgian
    annex explicitly does not adopt.
    """
    cot_min = float(params.get(f"{EC2_11}:cot_theta_min", j).magnitude)
    try:
        cot_max = float(params.get(f"{EC2_11}:cot_theta_max", j).magnitude)
    except UnrepresentableNationalParameter as exc:
        raise OutOfValidationDomain(
            "strut_angle_bound_unavailable",
            "la borne superieure de cot(theta) n'a pas de valeur scalaire dans "
            "l'Annexe Nationale de ce pays, et le moteur ne lui en substitue "
            "aucune: verifier l'angle des bielles contre une borne non "
            f"controlee reviendrait a ne pas le verifier. Detail: {exc}",
            clause="EN 1992-1-1 §6.2.3(2)",
        ) from exc
    return cot_min, cot_max


def design_shear(
    *,
    section: ShearSection,
    concrete: Concrete,
    steel: Reinforcement,
    V_Ed: Quantity,
    params: ParameterSet,
    cot_theta: float = 1.0,
    links: ShearLinks | None = None,
    situation: DesignSituation = DesignSituation.PERSISTENT,
    element: str = "element",
    provenance: Mapping[str, Provenance] | None = None,
) -> ShearDesign:
    """Verify a rectangular beam in shear, EN 1992-1-1 §6.2.

    :param cot_theta: strut inclination chosen by the engineer, checked against
        the national bounds. Defaults to 1,0 (45° struts), the conservative
        classic: it maximises the links and minimises both the web crushing
        demand and the additional longitudinal force.
    :param links: the links actually detailed. When omitted, the required area
        is reported and the utilisation is computed against it.
    :raises OutOfValidationDomain: outside the scope declared above, or when a
        national bound cannot be checked.
    """
    require_dimension(V_Ed, "[force]", "V_Ed")
    if V_Ed.magnitude < 0:
        raise InconsistentInput(
            "V_Ed doit etre positif: fournir la valeur absolue de l'effort "
            "tranchant de calcul."
        )
    if concrete.fck.to("MPa").magnitude > _FCK_MAX_MPA:
        raise OutOfValidationDomain(
            "high_strength_concrete",
            f"ce module est valide jusqu'a C50/60; {concrete.name} le depasse.",
            clause="EN 1992-1-1 §3.1.2",
        )

    params.require(required_parameters(situation))

    j = Journal(f"Effort tranchant ELU — {element}")
    prov = dict(provenance or {})

    j.input("b_w", "Largeur d'ame", section.b_w,
            prov.get("b_w", Provenance.user("coffrage")), clause=EC2("§6.2.2(1)"))
    j.input("d", "Hauteur utile", section.d,
            prov.get("d", Provenance.user("coffrage")), clause=EC2("§6.2.2(1)"))
    j.input("A_sl", "Section d'armature tendue ancree", section.A_sl,
            prov.get("A_sl", Provenance.user("ferraillage longitudinal")),
            clause=EC2("§6.2.2(1)"), display_unit="mm**2")
    j.input("V_Ed", "Effort tranchant de calcul a l'ELU", V_Ed,
            prov.get("V_Ed", Provenance.user("combinaison EN 1990 retenue")),
            clause=EC2("§6.2.1"), display_unit="kN")
    j.input("f_ck", f"Resistance caracteristique du beton ({concrete.name})",
            concrete.fck, Provenance.user(f"classe {concrete.name}"),
            clause=EC2("§3.1.2, Tab. 3.1"), display_unit="MPa")
    j.input("f_ywk", f"Limite d'elasticite des armatures d'ame ({steel.name})",
            steel.fyk, Provenance.user(f"nuance {steel.name}"),
            clause=EC2("§3.2.2"), display_unit="MPa")

    # --- national parameters ----------------------------------------------
    suffix = situation.partial_factor_suffix
    gamma_C = float(params.get(f"{EC2_11}:gamma_C_{suffix}", j).magnitude)
    gamma_S = float(params.get(f"{EC2_11}:gamma_S_{suffix}", j).magnitude)
    # §3.1.6(1)P: l'effort tranchant releve des « autres cas ». En Belgique
    # alpha_cc y vaut 1,0 et non 0,85. Heriter de la valeur de flexion
    # sous-estimerait f_cd de 15 %, donc V_Rd,max — dans le sens defavorable.
    alpha_cc = float(params.get(f"{EC2_11}:alpha_cc", j, condition="other").magnitude)
    c_rd_c = float(params.get(f"{EC2_11}:C_Rd_c_coeff", j).magnitude)
    v_min_c = float(params.get(f"{EC2_11}:v_min_coeff", j).magnitude)
    k1_shear = float(params.get(f"{EC2_11}:k1_shear", j).magnitude)
    alpha_cw = float(params.get(f"{EC2_11}:alpha_cw", j).magnitude)
    nu1_c = float(params.get(f"{EC2_11}:nu1_coeff", j).magnitude)
    nu1_div = float(params.get(f"{EC2_11}:nu1_fck_divisor", j).magnitude)
    rho_w_min_c = float(params.get(f"{EC2_11}:rho_w_min_coeff", j).magnitude)
    s_l_max_c = float(params.get(f"{EC2_11}:s_l_max_coeff", j).magnitude)

    cot_min, cot_max = _strut_bounds(params, j)
    if not (cot_min <= cot_theta <= cot_max):
        raise OutOfValidationDomain(
            "strut_angle_out_of_bounds",
            f"cot(theta) = {cot_theta} est hors des bornes nationales "
            f"[{cot_min} ; {cot_max}]. Choisir un angle admissible.",
            clause="EN 1992-1-1 §6.2.3(2)",
        )

    fcd = concrete.fcd(alpha_cc, gamma_C).to("MPa")
    j.step("f_cd", "Resistance de calcul du beton en compression", fcd,
           EC2("§3.1.6(1)P", "(3.15)"),
           latex=r"f_{cd} = \alpha_{cc}\, f_{ck} / \gamma_C",
           numeric=f"{fmt(alpha_cc)} · {fmt(concrete.fck, 'MPa', 0)} / {fmt(gamma_C)}",
           depends_on=("f_ck", f"{EC2_11}:alpha_cc", f"{EC2_11}:gamma_C_{suffix}"),
           display_unit="MPa")

    fywd = steel.fyd(gamma_S).to("MPa")
    j.step("f_ywd", "Resistance de calcul des armatures d'ame", fywd,
           EC2("§3.2.7(2)", "(3.14)"),
           latex=r"f_{ywd} = f_{ywk} / \gamma_S",
           numeric=f"{fmt(steel.fyk, 'MPa', 0)} / {fmt(gamma_S)}",
           depends_on=("f_ywk", f"{EC2_11}:gamma_S_{suffix}"), display_unit="MPa")

    z = section.z.to("mm")
    j.step("z", "Bras de levier interne", z, EC2("§6.2.3(1)"),
           latex=r"z = 0{,}9\, d",
           numeric=f"0.9 · {fmt(section.d, 'mm', 0)}",
           depends_on=("d",), display_unit="mm")

    # --- V_Rd,c, §6.2.2(1) -------------------------------------------------
    d_mm = float(section.d.to("mm").magnitude)
    k = min(1.0 + math.sqrt(200.0 / d_mm), _K_MAX)
    j.step("k", "Coefficient d'effet d'echelle", Q_(k, "dimensionless"),
           EC2("§6.2.2(1)"),
           latex=r"k = 1 + \sqrt{200/d} \le 2{,}0",
           numeric=f"1 + √(200 / {fmt(section.d, 'mm', 0)})", depends_on=("d",))

    rho_l = min(
        float((section.A_sl / (section.b_w * section.d)).to("dimensionless").magnitude),
        _RHO_L_MAX,
    )
    j.step("rho_l", "Taux d'armature longitudinale tendue",
           Q_(rho_l, "dimensionless"), EC2("§6.2.2(1)"),
           latex=r"\rho_l = A_{sl} / (b_w\, d) \le 0{,}02",
           numeric=(f"{fmt(section.A_sl, 'mm**2', 0)} / ({fmt(section.b_w, 'mm', 0)} · "
                    f"{fmt(section.d, 'mm', 0)})"),
           depends_on=("A_sl", "b_w", "d"))

    fck_mpa = float(concrete.fck.to("MPa").magnitude)
    if section.N_Ed is not None and section.A_c is not None:
        sigma_cp_q = (section.N_Ed / section.A_c).to("MPa")
        sigma_cp = min(
            float(sigma_cp_q.magnitude),
            _SIGMA_CP_CAP_RATIO * float(fcd.magnitude),
        )
    else:
        sigma_cp = 0.0
    j.step("sigma_cp", "Contrainte de compression moyenne",
           Q_(sigma_cp, "MPa"), EC2("§6.2.2(1)"),
           latex=r"\sigma_{cp} = N_{Ed}/A_c < 0{,}2\, f_{cd}",
           numeric=("0 (aucun effort normal declare)" if section.N_Ed is None
                    else f"min(N_Ed/A_c ; 0.2 · {fmt(fcd, 'MPa', 2)})"),
           depends_on=("f_cd",), display_unit="MPa")

    # v_Rd,c and its floor are stresses; multiply by b_w d at the end.
    v_rd_c_stress = c_rd_c / gamma_C * k * (100.0 * rho_l * fck_mpa) ** (1.0 / 3.0)
    v_min = v_min_c * k**1.5 * math.sqrt(fck_mpa)
    governing_floor = v_min > v_rd_c_stress
    v_rd_c_stress = max(v_rd_c_stress, v_min) + k1_shear * sigma_cp

    j.step("v_min", "Plancher de la contrainte de cisaillement resistante",
           Q_(v_min, "MPa"), EC2("§6.2.2(1)", "(6.3N)"),
           latex=r"v_{min} = 0{,}035\, k^{3/2}\, f_{ck}^{1/2}",
           numeric=f"{fmt(v_min_c)} · {k:.4f}^1.5 · √{fck_mpa:.0f}",
           depends_on=("k", "f_ck", f"{EC2_11}:v_min_coeff"), display_unit="MPa")

    V_Rd_c = (Q_(v_rd_c_stress, "MPa") * section.b_w * section.d).to("kN")
    j.step("V_Rd_c", "Effort tranchant resistant sans armatures d'effort tranchant",
           V_Rd_c, EC2("§6.2.2(1)", "(6.2a)/(6.2b)"),
           latex=(r"V_{Rd,c} = \left[C_{Rd,c}\, k\, (100\rho_l f_{ck})^{1/3} "
                  r"+ k_1 \sigma_{cp}\right] b_w d \ \ge (v_{min} + k_1\sigma_{cp}) b_w d"),
           numeric=(f"{'plancher v_min retenu' if governing_floor else 'terme principal retenu'}"
                    f" → {v_rd_c_stress:.4f} MPa · {fmt(section.b_w, 'mm', 0)} · "
                    f"{fmt(section.d, 'mm', 0)}"),
           depends_on=("k", "rho_l", "f_ck", "sigma_cp", "v_min", "b_w", "d",
                       f"{EC2_11}:C_Rd_c_coeff", f"{EC2_11}:k1_shear"),
           display_unit="kN")

    links_required = V_Ed.to("kN") > V_Rd_c

    # --- detailing minima, §9.2.2 -----------------------------------------
    fyk_mpa = float(steel.fyk.to("MPa").magnitude)
    rho_w_min = rho_w_min_c * math.sqrt(fck_mpa) / fyk_mpa
    Asw_s_min = (Q_(rho_w_min, "dimensionless") * section.b_w).to("mm**2/m")
    j.step("Asw_s_min", "Armature d'ame minimale par metre", Asw_s_min,
           EC2("§9.2.2(5)", "(9.5N)"),
           latex=r"\rho_{w,min} = 0{,}08\sqrt{f_{ck}}/f_{yk},\quad (A_{sw}/s)_{min} = \rho_{w,min} b_w",
           numeric=(f"{fmt(rho_w_min_c)} · √{fck_mpa:.0f} / {fyk_mpa:.0f} · "
                    f"{fmt(section.b_w, 'mm', 0)}"),
           depends_on=("f_ck", "f_ywk", "b_w", f"{EC2_11}:rho_w_min_coeff"),
           display_unit="mm**2/m")

    s_l_max = (s_l_max_c * section.d).to("mm")
    j.step("s_l_max", "Espacement longitudinal maximal des cadres", s_l_max,
           EC2("§9.2.2(6)", "(9.6N)"),
           latex=r"s_{l,max} = 0{,}75\, d\,(1 + \cot\alpha),\ \alpha = 90°",
           numeric=f"{fmt(s_l_max_c)} · {fmt(section.d, 'mm', 0)}",
           depends_on=("d", f"{EC2_11}:s_l_max_coeff"), display_unit="mm")

    # --- truss, §6.2.3 -----------------------------------------------------
    checks: list[Check] = []
    V_Rd_s: Quantity | None = None
    V_Rd_max: Quantity | None = None

    if links_required:
        j.step("cot_theta", "Inclinaison des bielles retenue",
               Q_(cot_theta, "dimensionless"), EC2("§6.2.3(2)", "(6.7N)"),
               latex=r"\cot\theta,\quad \cot\theta_{min} \le \cot\theta \le \cot\theta_{max}",
               numeric=f"{fmt(cot_theta)} (choix de l'ingenieur, borne [{cot_min} ; {cot_max}])",
               depends_on=(f"{EC2_11}:cot_theta_min", f"{EC2_11}:cot_theta_max"))

        # (6.8) inverted: the links needed to carry V_Ed on the chosen truss.
        Asw_s_req = (V_Ed / (z * fywd * cot_theta)).to("mm**2/m")

        nu1 = nu1_c * (1.0 - fck_mpa / nu1_div)
        j.step("nu_1", "Coefficient de reduction du beton fissure a l'effort tranchant",
               Q_(nu1, "dimensionless"), EC2("§6.2.2(6)", "(6.6N)"),
               latex=r"\nu_1 = 0{,}6\left(1 - f_{ck}/250\right)",
               numeric=f"{fmt(nu1_c)} · (1 − {fck_mpa:.0f} / {nu1_div:.0f})",
               depends_on=("f_ck", f"{EC2_11}:nu1_coeff", f"{EC2_11}:nu1_fck_divisor"))

        V_Rd_max = (
            alpha_cw * section.b_w * z * nu1 * fcd / (cot_theta + 1.0 / cot_theta)
        ).to("kN")
        j.step("V_Rd_max", "Effort tranchant resistant limite par l'ecrasement des bielles",
               V_Rd_max, EC2("§6.2.3(3)", "(6.9)"),
               latex=(r"V_{Rd,max} = \frac{\alpha_{cw}\, b_w\, z\, \nu_1\, f_{cd}}"
                      r"{\cot\theta + \tan\theta}"),
               numeric=(f"{fmt(alpha_cw)} · {fmt(section.b_w, 'mm', 0)} · "
                        f"{fmt(z, 'mm', 1)} · {nu1:.4f} · {fmt(fcd, 'MPa', 2)} / "
                        f"({fmt(cot_theta)} + {1.0 / cot_theta:.4f})"),
               depends_on=("b_w", "z", "nu_1", "f_cd", "cot_theta",
                           f"{EC2_11}:alpha_cw"),
               display_unit="kN")

        Asw_s_provided = links.per_metre if links is not None else Asw_s_req
        Asw_s_required = max(
            Asw_s_req.to("mm**2/m"), Asw_s_min.to("mm**2/m"), key=lambda q: q.magnitude
        )
        V_Rd_s = (Asw_s_provided * z * fywd * cot_theta).to("kN")
        j.step("V_Rd_s", "Effort tranchant resistant du treillis", V_Rd_s,
               EC2("§6.2.3(3)", "(6.8)"),
               latex=r"V_{Rd,s} = \frac{A_{sw}}{s}\, z\, f_{ywd}\, \cot\theta",
               numeric=(f"{fmt(Asw_s_provided, 'mm**2/m', 1)} · {fmt(z, 'mm', 1)} · "
                        f"{fmt(fywd, 'MPa', 1)} · {fmt(cot_theta)}"),
               depends_on=("z", "f_ywd", "cot_theta"), display_unit="kN")

        V_Rd = min(V_Rd_s, V_Rd_max, key=lambda q: q.to("kN").magnitude)

        checks.append(Check.from_ratio(
            "ELU effort tranchant — treillis (§6.2.3)", V_Ed, V_Rd_s,
            EC2("§6.2.3(3)", "(6.8)"),
            remedy="augmenter A_sw/s, ou coucher les bielles (cot theta plus grand).",
        ))
        checks.append(Check.from_ratio(
            "ELU effort tranchant — ecrasement des bielles (§6.2.3)", V_Ed, V_Rd_max,
            EC2("§6.2.3(3)", "(6.9)"),
            remedy=("elargir l'ame, augmenter la classe de beton, ou redresser "
                    "les bielles (cot theta plus petit)."),
        ))
        checks.append(Check.from_ratio(
            "Armature d'ame minimale (§9.2.2)", Asw_s_min, Asw_s_provided,
            EC2("§9.2.2(5)", "(9.5N)"),
            remedy="resserrer les cadres ou augmenter leur section.",
        ))
    else:
        # §6.2.1(4): no designed reinforcement needed. V_Rd,c is the resistance,
        # and the minimum links of §9.2.2 still apply to a beam.
        V_Rd = V_Rd_c
        Asw_s_required = Asw_s_min
        checks.append(Check.from_ratio(
            "ELU effort tranchant — sans armatures d'effort tranchant (§6.2.2)",
            V_Ed, V_Rd_c, EC2("§6.2.2(1)", "(6.2a)"),
            detail=("V_Ed <= V_Rd,c: aucune armature d'effort tranchant calculee "
                    "n'est requise. Les cadres minimaux du §9.2.2 restent dus."),
            remedy="augmenter la hauteur utile ou la section d'armature longitudinale.",
        ))
        if links is not None:
            checks.append(Check.from_ratio(
                "Armature d'ame minimale (§9.2.2)", Asw_s_min, links.per_metre,
                EC2("§9.2.2(5)", "(9.5N)"),
                remedy="resserrer les cadres ou augmenter leur section.",
            ))

    if links is not None:
        checks.append(Check.from_ratio(
            "Espacement longitudinal des cadres (§9.2.2)", links.s, s_l_max,
            EC2("§9.2.2(6)", "(9.6N)"),
            remedy="rapprocher les cadres.",
        ))

    # --- shift rule, §6.2.3(7) --------------------------------------------
    # The truss puts extra tension in the chord. It is reported even in the
    # no-links regime — as zero there — so the note never leaves it unsaid.
    delta_F_td = (0.5 * V_Ed * cot_theta).to("kN") if links_required else Q_(0.0, "kN")
    j.step("delta_F_td", "Effort de traction longitudinal supplementaire",
           delta_F_td, EC2("§6.2.3(7)", "(6.18)"),
           latex=r"\Delta F_{td} = 0{,}5\, V_{Ed}\,(\cot\theta - \cot\alpha),\ \alpha = 90°",
           numeric=(f"0.5 · {fmt(V_Ed, 'kN', 1)} · {fmt(cot_theta)}" if links_required
                    else "0 (aucun treillis: §6.2.2 s'applique)"),
           depends_on=("V_Ed",) + (("cot_theta",) if links_required else ()),
           display_unit="kN")

    return ShearDesign(
        element=element,
        V_Rd_c=V_Rd_c,
        links_required=links_required,
        V_Rd_s=V_Rd_s,
        V_Rd_max=V_Rd_max,
        V_Rd=V_Rd,
        Asw_over_s_required=Asw_s_required,
        Asw_over_s_min=Asw_s_min,
        s_l_max=s_l_max,
        delta_F_td=delta_F_td,
        cot_theta=cot_theta,
        report=VerificationReport(element=element, checks=tuple(checks)),
        journal=j,
        ndp_summary=params.summary(),
    )
