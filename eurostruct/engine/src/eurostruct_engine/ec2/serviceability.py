"""EN 1992-1-1 §7 — serviceability of a rectangular reinforced section.

Two verifications, both resting on the same piece of mechanics:

* **§7.2 — stress limitation.** Under the characteristic combination, the
  concrete compressive stress is capped so longitudinal cracking does not open
  the cover, and the steel stress is capped so cracks stay within what §7.3
  assumes.
* **§7.3.4 — crack width.** Under the quasi-permanent combination, ``w_k`` is
  compared with ``w_max`` from the National Annex.

Scope of this module (the *validated domain*; anything else raises
:class:`~eurostruct_engine.exceptions.OutOfValidationDomain`):

* rectangular cross-section, constant width;
* pure bending, no axial force;
* tension reinforcement only, one layer at effective depth ``d``;
* reinforced concrete only — no prestress, no bonded tendons, so the
  ``w_max`` row for prestressed members is never the one read;
* concrete up to C50/60;
* linear-elastic material behaviour, which is what §7.2 and §7.3 assume.

Which modulus goes where
------------------------
This is the one modelling decision a reviewer must be able to see, so it is
stated here and journalised in the result rather than buried:

* the **section analysis** giving ``sigma_s`` under the quasi-permanent
  combination uses the effective modulus ``E_c,eff = E_cm / (1 + phi)`` of
  §7.4.3(5), because that combination acts for the life of the structure and
  creep roughly halves the concrete stiffness. The creep coefficient is an
  **input**: §3.1.4 and Annex B give a method, this module does not run it and
  will not invent a value.
* ``alpha_e`` inside equation (7.9) is ``E_s / E_cm``, which is what the
  equation says in as many words. Using the effective modulus there too is
  common practice and would give a different number; the text is followed
  instead, and both ratios are journalised so the difference is visible.

Under the characteristic combination the section analysis uses ``E_cm``: that
combination is short-term by construction.

Cracked or not
--------------
§7.1(2) makes a section cracked once the tensile stress passes ``f_ct,eff``.
The module computes the uncracked transformed section, reports the verdict, and
then calculates ``w_k`` **from the cracked section either way**. On an uncracked
section that is conservative — there is no crack, and the calculation returns a
positive width — so the result is safe, but it would be misleading to print it
without saying so. ``is_cracked`` is carried into the report and the journal
records that §7.3.2 minimum reinforcement is what actually governs there.

Nothing in this module owns a national value: every one of them is asked of the
:class:`~eurostruct_engine.ndp.registry.ParameterSet` by name, and every request
is recorded in the journal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final, Mapping

from ..exceptions import InconsistentInput, OutOfValidationDomain
from ..materials.concrete import Concrete
from ..materials.reinforcement import Reinforcement
from ..ndp.registry import ParameterSet
from ..traceability import EC2, Journal, Provenance
from ..units import Q_, Quantity, fmt, require_dimension
from ..verification import Check, VerificationReport
from ..version import ENGINE_VERSION
from .beam_flexure import EC2_11, RectangularSection

__all__ = [
    "ExposureClass",
    "CrackControlDetail",
    "CrackedSection",
    "ServiceabilityDesign",
    "design_serviceability",
    "required_parameters",
]

_FCK_MAX_MPA = 50.0

#: §7.3.4(2). Fixed in the EN text, not a nationally determined parameter:
#: 0,6 for short-term loading, 0,4 for long-term or repeated loading. The
#: quasi-permanent combination is long-term by definition.
_K_T_LONG_TERM: Final = 0.4

#: §7.3.4(3). Bond coefficient: 0,8 for ribbed (high-bond) bars, 1,6 for bars
#: with an effectively plain surface. Fixed in the EN text.
_K1_BOND_HIGH: Final = 0.8
_K1_BOND_PLAIN: Final = 1.6

#: §7.3.4(3). Strain distribution: 0,5 for bending, 1,0 for pure tension.
_K2_BENDING: Final = 0.5
_K2_PURE_TENSION: Final = 1.0

#: §7.3.4(3), equation (7.14): the fallback when the bars are too widely
#: spaced for (7.11) to describe the crack pattern.
_WIDE_SPACING_COEFF: Final = 1.3


class ExposureClass(str, Enum):
    """Exposure classes of §4.2, Table 4.1.

    Carried as an input rather than derived: which class a member belongs to is
    an engineering judgement about its environment, not something the geometry
    can reveal.
    """

    X0 = "X0"
    XC1 = "XC1"
    XC2 = "XC2"
    XC3 = "XC3"
    XC4 = "XC4"
    XD1 = "XD1"
    XD2 = "XD2"
    XD3 = "XD3"
    XS1 = "XS1"
    XS2 = "XS2"
    XS3 = "XS3"
    XF1 = "XF1"
    XF2 = "XF2"
    XF3 = "XF3"
    XF4 = "XF4"
    XA1 = "XA1"
    XA2 = "XA2"
    XA3 = "XA3"

    @property
    def w_max_condition(self) -> str:
        """Which row of Table 7.1N this class falls in.

        The vocabulary is the one declared in the parameter's variants. An
        annex that grouped the classes differently would make
        :meth:`ParameterSet.get` refuse an unknown case rather than let this
        module land on a neighbouring row.
        """
        if self in (ExposureClass.X0, ExposureClass.XC1):
            return "X0_XC1"
        return "XC2_XC4_XD_XS"

    @property
    def stress_limit_condition(self) -> str:
        """Which branch of §7.2(2) applies.

        EN 1992-1-1 imposes the compressive-stress limit in XD, XF and XS only.
        NBN EN 1992-1-1 ANB extends it to every class and tightens it to 0,5 in
        XD/XF/XS — which is why this is asked for by case and never as a single
        scalar.
        """
        if self.value.startswith(("XD", "XF", "XS")):
            return "XD_XF_XS"
        return "other"


def required_parameters() -> tuple[str, ...]:
    """National parameters this module needs, for preflight (TICKET 1.3)."""
    return (
        f"{EC2_11}:k1_stress_limit",
        f"{EC2_11}:k3_steel_stress",
        f"{EC2_11}:w_max",
        f"{EC2_11}:k3_crack_spacing",
        f"{EC2_11}:k4_crack_spacing",
    )


@dataclass(frozen=True, slots=True)
class CrackControlDetail:
    """The bar arrangement §7.3.4 needs, which a bending calculation never knew.

    :param phi: diameter of the tension bars.
    :param cover: cover to the **longitudinal** reinforcement, ``c`` in (7.11).
        Not the cover to the links, which is smaller by one link diameter.
    :param bar_spacing: centre-to-centre spacing of the tension bars. Decides
        between (7.11) and (7.14).
    :param high_bond: ribbed bars (``k1 = 0,8``) rather than effectively plain
        ones (``k1 = 1,6``).
    :param pure_tension: ``k2 = 1,0`` instead of the bending value 0,5. Outside
        this module's domain, kept so the constant is not silently assumed.
    """

    phi: Quantity
    cover: Quantity
    bar_spacing: Quantity
    high_bond: bool = True
    pure_tension: bool = False

    def __post_init__(self) -> None:
        for name, v in (
            ("phi", self.phi), ("cover", self.cover),
            ("bar_spacing", self.bar_spacing),
        ):
            require_dimension(v, "[length]", name)
            if v.magnitude <= 0:
                raise InconsistentInput(f"'{name}' doit etre strictement positif")

    @property
    def k1_bond(self) -> float:
        return _K1_BOND_HIGH if self.high_bond else _K1_BOND_PLAIN

    @property
    def k2_strain(self) -> float:
        return _K2_PURE_TENSION if self.pure_tension else _K2_BENDING

    def spacing_limit(self) -> Quantity:
        """``5 (c + phi/2)`` — §7.3.4(3), the bound (7.11) is valid below."""
        return (5.0 * (self.cover + self.phi / 2.0)).to("mm")


@dataclass(frozen=True, slots=True)
class CrackedSection:
    """Elastic analysis of a cracked rectangular section in pure bending.

    Neutral axis from horizontal equilibrium of the transformed section, with
    the concrete in tension ignored:

        b x^2 / 2 = alpha_e A_s (d - x)

    which is a quadratic with one positive root. Solved in closed form, so the
    result is reproducible bit-for-bit.
    """

    alpha_e: float
    x: Quantity
    I: Quantity
    sigma_c: Quantity
    sigma_s: Quantity


def _cracked_section(
    *, section: RectangularSection, A_s: Quantity, alpha_e: float, M: Quantity
) -> CrackedSection:
    b, d = section.b, section.d
    a = (alpha_e * A_s / b).to("mm")
    # x = -a + sqrt(a^2 + 2 a d), written so the subtraction never cancels.
    x = (a * (math.sqrt(1.0 + 2.0 * float((d / a).to("dimensionless").magnitude)) - 1.0)).to("mm")
    I = (b * x**3 / 3.0 + alpha_e * A_s * (d - x) ** 2).to("mm**4")
    sigma_c = (M * x / I).to("MPa")
    sigma_s = (alpha_e * M * (d - x) / I).to("MPa")
    return CrackedSection(alpha_e=alpha_e, x=x, I=I, sigma_c=sigma_c, sigma_s=sigma_s)


def _uncracked_tensile_stress(
    *, section: RectangularSection, A_s: Quantity, alpha_e: float, M: Quantity
) -> Quantity:
    """Extreme tensile fibre stress on the uncracked transformed section.

    Used for the §7.1(2) verdict only. The reinforcement is included — leaving
    it out would overstate the tensile stress and declare sections cracked that
    are not.
    """
    b, h, d = section.b, section.h, section.d
    A_t = (b * h + (alpha_e - 1.0) * A_s).to("mm**2")
    x_I = ((b * h**2 / 2.0 + (alpha_e - 1.0) * A_s * d) / A_t).to("mm")
    I_I = (
        b * h**3 / 12.0
        + b * h * (x_I - h / 2.0) ** 2
        + (alpha_e - 1.0) * A_s * (d - x_I) ** 2
    ).to("mm**4")
    return (M * (h - x_I) / I_I).to("MPa")


@dataclass
class ServiceabilityDesign:
    """Result of the §7.2 and §7.3 verifications on one section."""

    element: str
    exposure_class: ExposureClass
    #: §7.1(2) verdict under the quasi-permanent combination.
    is_cracked: bool
    #: Cracked-section analysis under the quasi-permanent combination
    #: (long-term modulus).
    quasi_permanent: CrackedSection
    #: Cracked-section analysis under the characteristic combination (E_cm).
    characteristic: CrackedSection
    #: alpha_e = E_s / E_cm, the ratio equation (7.9) names.
    alpha_e_short: float
    h_c_ef: Quantity
    A_c_eff: Quantity
    rho_p_eff: float
    #: eps_sm - eps_cm, equation (7.9).
    eps_diff: float
    #: Whether the 0,6 sigma_s / E_s floor of (7.9) governed.
    eps_floor_governs: bool
    s_r_max: Quantity
    #: Whether (7.14) was used instead of (7.11) — bars too widely spaced.
    wide_spacing: bool
    w_k: Quantity
    w_max: Quantity
    sigma_c_limit: Quantity
    sigma_s_limit: Quantity
    report: VerificationReport
    journal: Journal
    engine_version: str = ENGINE_VERSION
    ndp_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def utilisation(self) -> float:
        return self.report.max_utilisation

    @property
    def cracking_statement(self) -> str:
        """What §7.1(2) concluded, in words the note can print as an assumption.

        An uncracked section is not a failure and must not be reported as one —
        which is why this is a statement and not a :class:`Check`. But leaving
        it unsaid would let a positive ``w_k`` be read as a measured crack on a
        member that has none.
        """
        if self.is_cracked:
            return (
                "Section FISSUREE sous combinaison quasi-permanente (§7.1(2)): "
                "le calcul d'ouverture de fissure du §7.3.4 s'applique."
            )
        return (
            "Section NON FISSUREE sous combinaison quasi-permanente (§7.1(2)): "
            "la contrainte de traction n'atteint pas f_ct,eff. L'ouverture de "
            "fissure est neanmoins calculee sur la section fissuree, ce qui est "
            "SECURITAIRE — il n'y a pas de fissure a ouvrir. C'est la section "
            "minimale d'armature du §7.3.2 qui gouverne ce cas, verification "
            "que ce module ne conduit pas."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element,
            "engine_version": self.engine_version,
            "exposure_class": self.exposure_class.value,
            "cracking_statement": self.cracking_statement,
            "is_cracked": self.is_cracked,
            "alpha_e_long": self.quasi_permanent.alpha_e,
            "alpha_e_short": self.alpha_e_short,
            "x_qp_mm": float(self.quasi_permanent.x.to("mm").magnitude),
            "sigma_s_qp_MPa": float(self.quasi_permanent.sigma_s.to("MPa").magnitude),
            "sigma_c_char_MPa": float(self.characteristic.sigma_c.to("MPa").magnitude),
            "sigma_s_char_MPa": float(self.characteristic.sigma_s.to("MPa").magnitude),
            "h_c_ef_mm": float(self.h_c_ef.to("mm").magnitude),
            "rho_p_eff": self.rho_p_eff,
            "eps_diff": self.eps_diff,
            "eps_floor_governs": self.eps_floor_governs,
            "s_r_max_mm": float(self.s_r_max.to("mm").magnitude),
            "wide_spacing": self.wide_spacing,
            "w_k_mm": float(self.w_k.to("mm").magnitude),
            "w_max_mm": float(self.w_max.to("mm").magnitude),
            "utilisation": self.utilisation,
            "verification": self.report.to_dict(),
            "journal": self.journal.to_dict(),
            "ndp": self.ndp_summary,
        }


def design_serviceability(
    *,
    section: RectangularSection,
    concrete: Concrete,
    steel: Reinforcement,
    A_s: Quantity,
    M_qp: Quantity,
    M_char: Quantity,
    phi_creep: float,
    detail: CrackControlDetail,
    exposure_class: ExposureClass,
    params: ParameterSet,
    element: str = "poutre",
    provenance: Mapping[str, Provenance] | None = None,
) -> ServiceabilityDesign:
    """Verify §7.2 stress limitation and §7.3.4 crack width.

    :param A_s: tension reinforcement actually provided. Unlike the ULS module
        there is no "required area" here: crack width is a property of the bars
        in the section, so nothing can be designed without them.
    :param M_qp: bending moment under the quasi-permanent combination.
    :param M_char: bending moment under the characteristic combination. Both
        come from the caller — this module does not build combinations.
    :param phi_creep: creep coefficient ``phi(inf, t0)`` of §3.1.4. Supplied,
        never guessed: it depends on the notional size, the ambient humidity
        and the age at loading, none of which this module is told.
    :param detail: the bar arrangement §7.3.4 needs.
    :param exposure_class: selects the ``w_max`` row and the §7.2(2) branch.
    :raises OutOfValidationDomain: outside the scope in the module docstring.
    """
    require_dimension(A_s, "[length] ** 2", "A_s")
    for name, M in (("M_qp", M_qp), ("M_char", M_char)):
        require_dimension(M, "[length] ** 2 * [mass] / [time] ** 2", name)
        if M.magnitude < 0:
            raise InconsistentInput(f"{name} doit etre positif")
    if A_s.magnitude <= 0:
        raise InconsistentInput("A_s doit etre strictement positif")
    if phi_creep < 0:
        raise InconsistentInput(
            "le coefficient de fluage phi doit etre positif ou nul"
        )
    if M_char < M_qp:
        raise InconsistentInput(
            f"M_char = {fmt(M_char, 'kN*m', 2)} est inferieur a "
            f"M_qp = {fmt(M_qp, 'kN*m', 2)}. La combinaison caracteristique "
            "enveloppe la combinaison quasi-permanente (EN 1990 §6.5.3); "
            "verifier quelle valeur a ete portee dans quel champ."
        )
    if detail.pure_tension:
        raise OutOfValidationDomain(
            "pure_tension",
            "k2 = 1,0 designe la traction pure. Ce module ne couvre que la "
            "flexion simple: l'analyse de section fissuree qu'il applique "
            "suppose une zone comprimee, qui n'existe pas en traction pure.",
            clause="EN 1992-1-1 §7.3.4(3)",
        )

    fck_mpa = concrete.fck.to("MPa").magnitude
    if fck_mpa > _FCK_MAX_MPA:
        raise OutOfValidationDomain(
            "high_strength_concrete",
            f"beton {concrete.name} (fck = {fck_mpa:g} MPa) au-dela de C50/60, "
            "domaine dans lequel ce module n'a pas ete valide.",
            clause="EN 1992-1-1 §3.1.2",
        )

    params.require(required_parameters())

    prov = dict(provenance or {})
    j = Journal(title=f"{element} — etats limites de service (EN 1992-1-1 §7)")

    # --- inputs ------------------------------------------------------------
    j.input("b", "Largeur de la section", section.b,
            prov.get("b", Provenance.user("saisie utilisateur")), display_unit="mm")
    j.input("h", "Hauteur totale de la section", section.h,
            prov.get("h", Provenance.user("saisie utilisateur")), display_unit="mm")
    j.input("d", "Hauteur utile", section.d,
            prov.get("d", Provenance.user("saisie utilisateur")), display_unit="mm")
    j.input("A_s", "Section d'acier tendu mise en oeuvre", A_s.to("mm**2"),
            Provenance.user("choix de ferraillage de l'ingenieur"),
            clause=EC2("§9.2.1.1"), display_unit="mm²")
    j.input("phi_bar", "Diametre des barres tendues", detail.phi.to("mm"),
            Provenance.user("choix de ferraillage de l'ingenieur"),
            display_unit="mm")
    j.input("c_long", "Enrobage des armatures longitudinales",
            detail.cover.to("mm"), Provenance.user("choix de l'ingenieur"),
            clause=EC2("§4.4.1"), display_unit="mm")
    j.input("s_bar", "Espacement des barres tendues",
            detail.bar_spacing.to("mm"), Provenance.user("choix de ferraillage"),
            display_unit="mm")
    j.input("M_qp", "Moment sous combinaison quasi-permanente", M_qp,
            prov.get("M_qp", Provenance.user("combinaison EN 1990 §6.5.3")),
            clause=EC2("§7.3.1(5)"), display_unit="kN·m")
    j.input("M_car", "Moment sous combinaison caracteristique", M_char,
            prov.get("M_char", Provenance.user("combinaison EN 1990 §6.5.3")),
            clause=EC2("§7.2"), display_unit="kN·m")
    j.input("phi_fluage", "Coefficient de fluage phi(inf, t0)",
            Q_(phi_creep, "dimensionless"),
            prov.get("phi_creep", Provenance.user(
                "valeur fournie par l'ingenieur — §3.1.4 / Annexe B, non "
                "calculee par le moteur")),
            clause=EC2("§3.1.4"))
    # La classe d'exposition n'est pas une grandeur: elle n'entre pas au
    # journal comme une valeur. Elle est tracee la ou elle agit — dans le cas
    # demande a chaque parametre national ci-dessous, que le registre note.

    # --- national parameters ------------------------------------------------
    # §7.2(2): la borne depend de la classe d'exposition. L'ANB belge la fixe a
    # 0,5 en XD/XF/XS et 0,6 ailleurs; demander un scalaire ferait retomber sur
    # la mauvaise branche sans que rien ne le signale.
    k1_stress = float(params.get(
        f"{EC2_11}:k1_stress_limit", j,
        condition=exposure_class.stress_limit_condition,
    ).magnitude)
    k3_steel = float(params.get(f"{EC2_11}:k3_steel_stress", j).magnitude)
    w_max = params.get(
        f"{EC2_11}:w_max", j, condition=exposure_class.w_max_condition
    ).to("mm")
    k3_crack = float(params.get(f"{EC2_11}:k3_crack_spacing", j).magnitude)
    k4_crack = float(params.get(f"{EC2_11}:k4_crack_spacing", j).magnitude)

    # --- moduli -------------------------------------------------------------
    E_cm = concrete.Ecm.to("MPa")
    E_s = steel.Es.to("MPa")
    j.step("E_cm", "Module secant du beton", E_cm, EC2("§3.1.3, Tab. 3.1"),
           latex=r"E_{cm} = 22\left(\frac{f_{cm}}{10}\right)^{0{,}3}",
           numeric=f"beton {concrete.name}", depends_on=(), display_unit="MPa")

    E_c_eff = (E_cm / (1.0 + phi_creep)).to("MPa")
    j.step("E_c_eff", "Module effectif du beton (fluage)", E_c_eff,
           EC2("§7.4.3(5)", "(7.20)"),
           latex=r"E_{c,eff} = \frac{E_{cm}}{1 + \varphi(\infty, t_0)}",
           numeric=f"{fmt(E_cm, 'MPa', 0)} / (1 + {fmt(phi_creep)})",
           depends_on=("E_cm", "phi_fluage"), display_unit="MPa")

    alpha_e_short = float((E_s / E_cm).to("dimensionless").magnitude)
    alpha_e_long = float((E_s / E_c_eff).to("dimensionless").magnitude)
    j.step("alpha_e", "Coefficient d'equivalence a court terme",
           Q_(alpha_e_short, "dimensionless"), EC2("§7.3.4(2)", "(7.9)"),
           latex=r"\alpha_e = E_s / E_{cm}",
           numeric=f"{fmt(E_s, 'MPa', 0)} / {fmt(E_cm, 'MPa', 0)}",
           depends_on=("E_cm",))
    j.step("alpha_e_eff", "Coefficient d'equivalence a long terme",
           Q_(alpha_e_long, "dimensionless"), EC2("§7.4.3(5)"),
           latex=r"\alpha_{e,eff} = E_s / E_{c,eff}",
           numeric=f"{fmt(E_s, 'MPa', 0)} / {fmt(E_c_eff, 'MPa', 0)}",
           depends_on=("E_c_eff",))

    # --- §7.1(2): is the section cracked? -----------------------------------
    f_ct_eff = concrete.fctm.to("MPa")
    j.step("f_ct_eff", "Resistance moyenne en traction a la fissuration",
           f_ct_eff, EC2("§7.3.2(2)"),
           latex=r"f_{ct,eff} = f_{ctm}",
           numeric=f"beton {concrete.name}, fissuration au-dela de 28 jours",
           depends_on=(), display_unit="MPa")

    sigma_ct = _uncracked_tensile_stress(
        section=section, A_s=A_s, alpha_e=alpha_e_long, M=M_qp
    )
    is_cracked = sigma_ct > f_ct_eff
    j.step("sigma_ct",
           "Contrainte de traction sur section non fissuree — section "
           + ("FISSUREE" if is_cracked else "NON FISSUREE"),
           sigma_ct, EC2("§7.1(2)"),
           latex=r"\sigma_{ct} = \frac{M_{qp}\,(h - x_I)}{I_I}",
           numeric=(
               f"section homogeneisee non fissuree, alpha_e,eff = "
               f"{fmt(alpha_e_long, digits=2)} ; "
               f"{fmt(sigma_ct, 'MPa', 2)} "
               f"{'>' if is_cracked else '<='} f_ct,eff = "
               f"{fmt(f_ct_eff, 'MPa', 2)}"
           ),
           depends_on=("M_qp", "h", "alpha_e_eff", "f_ct_eff"),
           display_unit="MPa")

    # --- cracked-section analyses -------------------------------------------
    qp = _cracked_section(section=section, A_s=A_s, alpha_e=alpha_e_long, M=M_qp)
    char = _cracked_section(
        section=section, A_s=A_s, alpha_e=alpha_e_short, M=M_char
    )
    j.step("x_qp", "Axe neutre de la section fissuree (quasi-permanent)",
           qp.x, EC2("§7.1"),
           latex=r"\frac{b x^2}{2} = \alpha_{e,eff} A_s (d - x)",
           numeric=(
               f"b = {fmt(section.b, 'mm', 0)}, A_s = {fmt(A_s, 'mm**2', 0)}, "
               f"alpha_e,eff = {fmt(alpha_e_long, digits=2)}"
           ),
           depends_on=("b", "d", "A_s", "alpha_e_eff"), display_unit="mm")
    j.step("I_qp", "Inertie de la section fissuree (quasi-permanent)",
           qp.I, EC2("§7.1"),
           latex=r"I = \frac{b x^3}{3} + \alpha_{e,eff} A_s (d - x)^2",
           numeric=f"x = {fmt(qp.x, 'mm', 1)}",
           depends_on=("x_qp",), display_unit="mm⁴")
    j.step("sigma_s_qp", "Contrainte de l'acier sous combinaison quasi-permanente",
           qp.sigma_s, EC2("§7.3.4(2)"),
           latex=r"\sigma_s = \alpha_{e,eff}\,\frac{M_{qp}\,(d - x)}{I}",
           numeric=f"M_qp = {fmt(M_qp, 'kN*m', 2)}, I = {fmt(qp.I, 'mm**4', 0)}",
           depends_on=("M_qp", "I_qp", "x_qp"), display_unit="MPa")
    j.step("sigma_c_car", "Contrainte du beton sous combinaison caracteristique",
           char.sigma_c, EC2("§7.2(2)"),
           latex=r"\sigma_c = \frac{M_{car}\, x}{I}",
           numeric=(
               f"M_car = {fmt(M_char, 'kN*m', 2)}, alpha_e = "
               f"{fmt(alpha_e_short, digits=2)}"
           ),
           depends_on=("M_car", "alpha_e"), display_unit="MPa")
    j.step("sigma_s_car", "Contrainte de l'acier sous combinaison caracteristique",
           char.sigma_s, EC2("§7.2(5)"),
           latex=r"\sigma_s = \alpha_e\,\frac{M_{car}\,(d - x)}{I}",
           numeric=(
               f"M_car = {fmt(M_char, 'kN*m', 2)}, alpha_e = "
               f"{fmt(alpha_e_short, digits=2)}"
           ),
           depends_on=("M_car", "alpha_e"), display_unit="MPa")

    # --- §7.3.2(3): effective area in tension --------------------------------
    h_c_ef = min(
        (2.5 * (section.h - section.d)).to("mm"),
        ((section.h - qp.x) / 3.0).to("mm"),
        (section.h / 2.0).to("mm"),
    )
    A_c_eff = (section.b * h_c_ef).to("mm**2")
    j.step("h_c_ef", "Hauteur de la zone de beton tendu efficace", h_c_ef,
           EC2("§7.3.2(3)"),
           latex=r"h_{c,ef} = \min\left(2{,}5(h-d)\ ;\ \frac{h-x}{3}\ ;\ \frac{h}{2}\right)",
           numeric=(
               f"min(2,5 · ({fmt(section.h, 'mm', 0)} − {fmt(section.d, 'mm', 0)}) ; "
               f"({fmt(section.h, 'mm', 0)} − {fmt(qp.x, 'mm', 1)}) / 3 ; "
               f"{fmt(section.h, 'mm', 0)} / 2)"
           ),
           depends_on=("h", "d", "x_qp"), display_unit="mm")
    j.step("A_c_eff", "Aire de beton tendu efficace", A_c_eff,
           EC2("§7.3.2(3)"),
           latex=r"A_{c,eff} = b\, h_{c,ef}",
           numeric=f"{fmt(section.b, 'mm', 0)} · {fmt(h_c_ef, 'mm', 1)}",
           depends_on=("b", "h_c_ef"), display_unit="mm²")

    rho_p_eff = float((A_s / A_c_eff).to("dimensionless").magnitude)
    j.step("rho_p_eff", "Taux d'armature de la zone efficace",
           Q_(rho_p_eff, "dimensionless"), EC2("§7.3.4(2)", "(7.10)"),
           latex=r"\rho_{p,eff} = \frac{A_s}{A_{c,eff}}",
           numeric=f"{fmt(A_s, 'mm**2', 0)} / {fmt(A_c_eff, 'mm**2', 0)}",
           depends_on=("A_s", "A_c_eff"))

    # --- §7.3.4(2), equation (7.9) -------------------------------------------
    sigma_s = qp.sigma_s
    numerator = (
        sigma_s - _K_T_LONG_TERM * (f_ct_eff / rho_p_eff)
        * (1.0 + alpha_e_short * rho_p_eff)
    )
    eps_main = float((numerator / E_s).to("dimensionless").magnitude)
    eps_floor = 0.6 * float((sigma_s / E_s).to("dimensionless").magnitude)
    eps_floor_governs = eps_main < eps_floor
    eps_diff = max(eps_main, eps_floor)
    j.step("eps_diff", "Difference des deformations moyennes acier-beton",
           Q_(eps_diff, "dimensionless"), EC2("§7.3.4(2)", "(7.9)"),
           latex=(
               r"\varepsilon_{sm}-\varepsilon_{cm} = \max\left("
               r"\frac{\sigma_s - k_t \frac{f_{ct,eff}}{\rho_{p,eff}}"
               r"(1+\alpha_e \rho_{p,eff})}{E_s}\ ;\ "
               r"0{,}6\frac{\sigma_s}{E_s}\right)"
           ),
           numeric=(
               f"max({eps_main * 1000:.4f}‰ ; 0,6 · sigma_s/E_s = "
               f"{eps_floor * 1000:.4f}‰), k_t = {fmt(_K_T_LONG_TERM)} "
               "(charge de longue duree)"
           ),
           depends_on=("sigma_s_qp", "f_ct_eff", "rho_p_eff", "alpha_e"))

    # --- §7.3.4(3): maximum crack spacing -------------------------------------
    limit = detail.spacing_limit()
    wide_spacing = detail.bar_spacing > limit
    if wide_spacing:
        s_r_max = (_WIDE_SPACING_COEFF * (section.h - qp.x)).to("mm")
        j.step("s_r_max", "Espacement maximal des fissures — barres espacees",
               s_r_max, EC2("§7.3.4(3)", "(7.14)"),
               latex=r"s_{r,max} = 1{,}3\,(h - x)",
               numeric=(
                   f"espacement {fmt(detail.bar_spacing, 'mm', 0)} > "
                   f"5(c + phi/2) = {fmt(limit, 'mm', 0)} : la formule (7.11) "
                   f"ne s'applique pas. 1,3 · ({fmt(section.h, 'mm', 0)} − "
                   f"{fmt(qp.x, 'mm', 1)})"
               ),
               depends_on=("h", "x_qp", "s_bar", "c_long"), display_unit="mm")
    else:
        s_r_max = (
            k3_crack * detail.cover
            + detail.k1_bond * detail.k2_strain * k4_crack * detail.phi / rho_p_eff
        ).to("mm")
        j.step("s_r_max", "Espacement maximal des fissures", s_r_max,
               EC2("§7.3.4(3)", "(7.11)"),
               latex=r"s_{r,max} = k_3 c + k_1 k_2 k_4 \frac{\phi}{\rho_{p,eff}}",
               numeric=(
                   f"{fmt(k3_crack)} · {fmt(detail.cover, 'mm', 0)} + "
                   f"{fmt(detail.k1_bond)} · {fmt(detail.k2_strain)} · "
                   f"{fmt(k4_crack)} · {fmt(detail.phi, 'mm', 0)} / "
                   f"{fmt(rho_p_eff, digits=5)}"
               ),
               depends_on=(
                   "c_long", "phi_bar", "rho_p_eff",
                   f"{EC2_11}:k3_crack_spacing", f"{EC2_11}:k4_crack_spacing",
               ), display_unit="mm")

    # --- §7.3.4(1), equation (7.8) --------------------------------------------
    w_k = (s_r_max * eps_diff).to("mm")
    j.step("w_k", "Ouverture de fissure calculee", w_k,
           EC2("§7.3.4(1)", "(7.8)"),
           latex=r"w_k = s_{r,max}\,(\varepsilon_{sm} - \varepsilon_{cm})",
           numeric=f"{fmt(s_r_max, 'mm', 1)} · {eps_diff * 1000:.4f}‰",
           depends_on=("s_r_max", "eps_diff"), display_unit="mm")

    # --- §7.2 stress limits ---------------------------------------------------
    sigma_c_limit = (k1_stress * concrete.fck).to("MPa")
    j.step("sigma_c_lim", "Contrainte de compression admissible du beton",
           sigma_c_limit, EC2("§7.2(2)"),
           latex=r"\sigma_{c,lim} = k_1 f_{ck}",
           numeric=f"{fmt(k1_stress)} · {fmt(concrete.fck, 'MPa', 0)}",
           depends_on=(f"{EC2_11}:k1_stress_limit",), display_unit="MPa")
    sigma_s_limit = (k3_steel * steel.fyk).to("MPa")
    j.step("sigma_s_lim", "Contrainte de traction admissible de l'acier",
           sigma_s_limit, EC2("§7.2(5)"),
           latex=r"\sigma_{s,lim} = k_3 f_{yk}",
           numeric=f"{fmt(k3_steel)} · {fmt(steel.fyk, 'MPa', 0)}",
           depends_on=(f"{EC2_11}:k3_steel_stress",), display_unit="MPa")

    # --- checks ---------------------------------------------------------------
    report = VerificationReport(element=element)
    report.add(Check.from_ratio(
        "ELS — ouverture de fissure", w_k, w_max,
        EC2("§7.3.1(5)", "(7.8)"),
        detail=(
            None if w_k <= w_max else
            f"w_k = {fmt(w_k, 'mm', 3)} depasse w_max = {fmt(w_max, 'mm', 2)} "
            f"pour la classe d'exposition {exposure_class.value}."
        ),
        remedy=(
            "Reduire le diametre des barres a section constante (s_r,max "
            "decroit avec phi), rapprocher les barres, ou augmenter A_s."
        ),
    ))
    report.add(Check.from_ratio(
        "ELS — contrainte du beton (combinaison caracteristique)",
        char.sigma_c, sigma_c_limit, EC2("§7.2(2)"),
        detail=(
            None if char.sigma_c <= sigma_c_limit else
            "La contrainte de compression favorise la fissuration "
            "longitudinale dans l'enrobage."
        ),
        remedy="Augmenter la hauteur utile, la largeur, ou la classe de beton.",
    ))
    report.add(Check.from_ratio(
        "ELS — contrainte de l'acier (combinaison caracteristique)",
        char.sigma_s, sigma_s_limit, EC2("§7.2(5)"),
        detail=(
            None if char.sigma_s <= sigma_s_limit else
            "Une deformation inelastique de l'acier sous charges de service "
            "rendrait la fissuration irreversible."
        ),
        remedy="Augmenter la section d'acier mise en oeuvre.",
    ))

    return ServiceabilityDesign(
        element=element,
        exposure_class=exposure_class,
        is_cracked=is_cracked,
        quasi_permanent=qp,
        characteristic=char,
        alpha_e_short=alpha_e_short,
        h_c_ef=h_c_ef,
        A_c_eff=A_c_eff,
        rho_p_eff=rho_p_eff,
        eps_diff=eps_diff,
        eps_floor_governs=eps_floor_governs,
        s_r_max=s_r_max,
        wide_spacing=wide_spacing,
        w_k=w_k,
        w_max=w_max,
        sigma_c_limit=sigma_c_limit,
        sigma_s_limit=sigma_s_limit,
        report=report,
        journal=j,
        ndp_summary=params.summary(),
    )
