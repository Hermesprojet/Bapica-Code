"""EN 1992-1-1 — ULS bending of a rectangular section, singly reinforced.

Scope of this module (the *validated domain*; anything else raises
:class:`~eurostruct_engine.exceptions.OutOfValidationDomain`):

* rectangular cross-section, constant width;
* simple bending (no axial force) about a principal axis;
* tension reinforcement only, concentrated at one effective depth ``d``;
* concrete up to C50/60;
* no moment redistribution (``delta = 1,0``);
* rectangular stress block of §3.1.7(3);
* bilinear steel diagram with horizontal top branch (§3.2.7(2), option a),
  so the steel stress is capped at ``fyd``.

Mechanical model
----------------
Equilibrium of the section at ULS, with the rectangular stress block:

    Compression   Fc = eta * fcd * lambda * x * b
    Tension       Fs = As * sigma_s
    Lever arm     z  = d - lambda * x / 2

Writing ``xi = x/d`` and the dimensionless moment
``mu = MEd / (b d^2 eta fcd)``, moment equilibrium about the tension
reinforcement gives

    mu = lambda * xi * (1 - lambda * xi / 2)

whose relevant root is

    xi = (1 - sqrt(1 - 2 mu)) / lambda

This is an exact inversion, not a table lookup or a fit, which is what makes
the result reproducible bit-for-bit.

Every value produced here is recorded in a
:class:`~eurostruct_engine.traceability.Journal` with its clause, so the note
de calcul can be assembled without the engine ever handing a bare number to a
text generator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Final, Mapping

from ..basis import DesignSituation
from ..exceptions import InconsistentInput, OutOfValidationDomain
from ..materials.concrete import Concrete
from ..materials.reinforcement import Reinforcement
from ..ndp.registry import ParameterSet
from ..traceability import EC2, Journal, Provenance
from ..units import Q_, Quantity, fmt, require_dimension
from ..verification import Check, VerificationReport
from ..version import ENGINE_VERSION

__all__ = [
    "RectangularSection",
    "FlexureDesign",
    "FlexureResistance",
    "design_flexure",
    "moment_resistance",
    "required_parameters",
    "EC2_11",
]

#: The standard this module draws its national parameters from. Keys are
#: ``"EN 1992-1-1:alpha_cc"`` and so on, so a parameter of another part can
#: never be picked up by accident.
EC2_11: Final = "EN 1992-1-1"

#: Highest concrete grade this module has been validated for.
_FCK_MAX_MPA = 50.0


def required_parameters(situation: DesignSituation) -> tuple[str, ...]:
    """National parameters this module needs, for preflight (TICKET 1.3).

    Declared rather than discovered: the preflight can then report every
    blocker in one pass, before any calculation starts.
    """
    suffix = situation.partial_factor_suffix
    return (
        f"{EC2_11}:gamma_C_{suffix}",
        f"{EC2_11}:gamma_S_{suffix}",
        f"{EC2_11}:alpha_cc",
        f"{EC2_11}:k1_redistribution",
        f"{EC2_11}:k2_redistribution",
        f"{EC2_11}:As_min_coeff",
        f"{EC2_11}:As_min_floor",
        f"{EC2_11}:As_max_ratio",
    )


@dataclass(frozen=True, slots=True)
class RectangularSection:
    """A rectangular concrete cross-section.

    :param b: width.
    :param h: overall depth.
    :param d: effective depth to the centroid of the tension reinforcement.
    """

    b: Quantity
    h: Quantity
    d: Quantity

    def __post_init__(self) -> None:
        for name, v in (("b", self.b), ("h", self.h), ("d", self.d)):
            require_dimension(v, "[length]", name)
            if v.magnitude <= 0:
                raise InconsistentInput(f"'{name}' doit etre strictement positif")
        if self.d >= self.h:
            raise InconsistentInput(
                f"la hauteur utile d = {fmt(self.d)} doit etre inferieure a la "
                f"hauteur totale h = {fmt(self.h)} (enrobage et armatures)."
            )

    @property
    def Ac(self) -> Quantity:
        """Gross concrete area."""
        return self.b * self.h


@dataclass(frozen=True, slots=True)
class FlexureResistance:
    """Moment resistance of a section with a known reinforcement area."""

    M_Rd: Quantity
    x: Quantity
    z: Quantity
    xi: float
    eps_s: float
    steel_yields: bool


@dataclass
class FlexureDesign:
    """Result of designing the tension reinforcement for a given moment."""

    element: str
    #: Area required by strength alone.
    As_strength: Quantity
    #: Minimum area from detailing rules, §9.2.1.1(1).
    As_min: Quantity
    #: Maximum permitted area, §9.2.1.1(3).
    As_max: Quantity
    #: What must actually be provided: ``max(As_strength, As_min)``.
    As_required: Quantity
    #: The area actually detailed (real bars). Equal to ``As_required`` when the
    #: caller did not supply one.
    As_provided: Quantity
    x: Quantity
    z: Quantity
    mu: float
    xi: float
    xi_lim: float
    eps_s: float
    resistance: FlexureResistance
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
            "As_strength_mm2": float(self.As_strength.to("mm**2").magnitude),
            "As_min_mm2": float(self.As_min.to("mm**2").magnitude),
            "As_max_mm2": float(self.As_max.to("mm**2").magnitude),
            "As_required_mm2": float(self.As_required.to("mm**2").magnitude),
            "As_provided_mm2": float(self.As_provided.to("mm**2").magnitude),
            "x_mm": float(self.x.to("mm").magnitude),
            "z_mm": float(self.z.to("mm").magnitude),
            "mu": self.mu,
            "xi": self.xi,
            "xi_lim": self.xi_lim,
            "eps_s": self.eps_s,
            "M_Rd_kNm": float(self.resistance.M_Rd.to("kN*m").magnitude),
            "utilisation": self.utilisation,
            "verification": self.report.to_dict(),
            "journal": self.journal.to_dict(),
            "ndp": self.ndp_summary,
        }


# ---------------------------------------------------------------------------
# Resistance of a section with known reinforcement
# ---------------------------------------------------------------------------
def moment_resistance(
    *,
    section: RectangularSection,
    concrete: Concrete,
    steel: Reinforcement,
    A_s: Quantity,
    fcd: Quantity,
    fyd: Quantity,
    eps_yd: float,
    journal: Journal | None = None,
    prefix: str = "",
) -> FlexureResistance:
    """Moment resistance ``M_Rd`` of a singly reinforced rectangular section.

    Neutral axis from horizontal equilibrium, assuming the steel yields:

        As * fyd = eta * fcd * lambda * x * b   =>   x = As fyd / (eta fcd lambda b)

    :raises OutOfValidationDomain: if the steel does not reach yield, because
        the closed-form expression above no longer holds and the section would
        fail in a brittle manner.
    """
    lam = concrete.lambda_
    eta = concrete.eta
    b, d = section.b, section.d

    x = (A_s * fyd / (eta * fcd * lam * b)).to("mm")
    xi = float((x / d).to("dimensionless").magnitude)
    eps_s = concrete.eps_cu3 * (1.0 - xi) / xi if xi > 0 else math.inf
    steel_yields = eps_s >= eps_yd
    z = (d - lam * x / 2.0).to("mm")
    M_Rd = (A_s * fyd * z).to("kN*m")

    if journal is not None:
        p = prefix
        journal.step(
            f"{p}x",
            "Hauteur de l'axe neutre — equilibre des efforts horizontaux",
            x,
            EC2("§6.1", "(3.19)-(3.21)"),
            latex=r"x = \frac{A_s f_{yd}}{\eta \, f_{cd} \, \lambda \, b}",
            numeric=(
                f"({fmt(A_s, 'mm**2', 1)} · {fmt(fyd, 'MPa', 1)}) / "
                f"({fmt(eta)} · {fmt(fcd, 'MPa', 2)} · {fmt(lam)} · {fmt(b, 'mm', 0)})"
            ),
            depends_on=(),
            display_unit="mm",
        )
        journal.step(
            f"{p}z",
            "Bras de levier des efforts internes",
            z,
            EC2("§6.1"),
            latex=r"z = d - \frac{\lambda x}{2}",
            numeric=f"{fmt(d, 'mm', 0)} − {fmt(lam)} · {fmt(x, 'mm', 1)} / 2",
            depends_on=(f"{p}x",),
            display_unit="mm",
        )
        journal.step(
            f"{p}eps_s",
            "Deformation de l'acier tendu (compatibilite des deformations)",
            Q_(eps_s, "dimensionless"),
            EC2("§6.1(2)P"),
            latex=r"\varepsilon_s = \varepsilon_{cu3}\,\frac{d-x}{x}",
            numeric=(
                f"{fmt(concrete.eps_cu3 * 1000, digits=2)}‰ · "
                f"({fmt(d, 'mm', 0)} − {fmt(x, 'mm', 1)}) / {fmt(x, 'mm', 1)}"
            ),
            depends_on=(f"{p}x",),
        )
        journal.step(
            f"{p}M_Rd",
            "Moment resistant de calcul",
            M_Rd,
            EC2("§6.1"),
            latex=r"M_{Rd} = A_s f_{yd} z",
            numeric=(
                f"{fmt(A_s, 'mm**2', 1)} · {fmt(fyd, 'MPa', 1)} · {fmt(z, 'mm', 1)}"
            ),
            depends_on=(f"{p}z",),
            display_unit="kN·m",
        )

    if not steel_yields:
        raise OutOfValidationDomain(
            "steel_not_yielding",
            f"la deformation de l'acier eps_s = {eps_s * 1000:.2f}‰ est "
            f"inferieure a la deformation d'ecoulement eps_yd = {eps_yd * 1000:.2f}‰. "
            "La section est sur-armee et romprait de maniere fragile. Le present "
            "module ne couvre que les sections sous-armees. Augmenter la hauteur "
            "utile, la largeur ou la classe de beton, ou prevoir des armatures "
            "comprimees (module non disponible dans cette version).",
            clause="EN 1992-1-1 §6.1(2)P",
        )

    return FlexureResistance(
        M_Rd=M_Rd, x=x, z=z, xi=xi, eps_s=eps_s, steel_yields=steel_yields
    )


# ---------------------------------------------------------------------------
# Design
# ---------------------------------------------------------------------------
def design_flexure(
    *,
    section: RectangularSection,
    concrete: Concrete,
    steel: Reinforcement,
    M_Ed: Quantity,
    params: ParameterSet,
    situation: DesignSituation = DesignSituation.PERSISTENT,
    element: str = "poutre",
    provenance: Mapping[str, Provenance] | None = None,
    A_s_provided: Quantity | None = None,
) -> FlexureDesign:
    """Design the tension reinforcement of a rectangular section in bending.

    :param section: geometry.
    :param concrete: concrete grade.
    :param steel: reinforcement grade.
    :param M_Ed: design bending moment at ULS, positive, from the governing
        EN 1990 combination. This module does not build combinations.
    :param params: the project's National Annex parameter set. In strict mode
        an unverified parameter raises rather than being used.
    :param situation: selects the partial factor set.
    :param provenance: per-symbol origin of the geometric and load inputs, so
        the note de calcul can state where each came from. Symbols: ``b``,
        ``h``, ``d``, ``M_Ed``.
    :param A_s_provided: the area of the bars actually detailed. Supply it once
        the bar arrangement is chosen: the ULS check is then a genuine
        comparison against the built section. When omitted, the check is made
        against ``As_required``, where ``M_Rd`` equals ``M_Ed`` by construction
        and the utilisation is 1,000 whenever strength governs.
    :raises OutOfValidationDomain: outside the scope listed in the module
        docstring — the engine refuses rather than approximating.
    """
    require_dimension(M_Ed, "[length] ** 2 * [mass] / [time] ** 2", "M_Ed")
    if M_Ed.magnitude < 0:
        raise InconsistentInput(
            "M_Ed doit etre positif; orienter la section pour que la fibre "
            "tendue corresponde a la hauteur utile d."
        )

    fck_mpa = concrete.fck.to("MPa").magnitude
    if fck_mpa > _FCK_MAX_MPA:
        raise OutOfValidationDomain(
            "high_strength_concrete",
            f"beton {concrete.name} (fck = {fck_mpa:g} MPa) au-dela de C50/60. "
            "Les coefficients lambda, eta et le parametre k2 de l'AN doivent "
            "etre re-exprimes pour les betons a hautes performances; ce module "
            "n'a pas ete valide dans ce domaine.",
            clause="EN 1992-1-1 §3.1.7(3)",
        )

    # Preflight before anything else (TICKET 1.3): report every blocking
    # national parameter in one pass rather than failing on the first lookup.
    params.require(required_parameters(situation))

    prov = dict(provenance or {})
    j = Journal(title=f"{element} — flexion simple a l'ELU (EN 1992-1-1)")

    # --- inputs ------------------------------------------------------------
    j.input(
        "b", "Largeur de la section", section.b,
        prov.get("b", Provenance.user("saisie utilisateur")), display_unit="mm",
    )
    j.input(
        "h", "Hauteur totale de la section", section.h,
        prov.get("h", Provenance.user("saisie utilisateur")), display_unit="mm",
    )
    j.input(
        "d", "Hauteur utile", section.d,
        prov.get("d", Provenance.user("saisie utilisateur")), display_unit="mm",
    )
    j.input(
        "f_ck", f"Resistance caracteristique du beton ({concrete.name})",
        concrete.fck, Provenance.user(f"classe {concrete.name}"),
        clause=EC2("§3.1.2, Tab. 3.1"), display_unit="MPa",
    )
    j.input(
        "f_yk", f"Limite d'elasticite de l'acier ({steel.name})",
        steel.fyk, Provenance.user(f"nuance {steel.name}"),
        clause=EC2("§3.2.2"), display_unit="MPa",
    )
    j.input(
        "M_Ed", "Moment flechissant de calcul a l'ELU", M_Ed,
        prov.get("M_Ed", Provenance.user("combinaison EN 1990 retenue")),
        clause=EC2("§6.1"), display_unit="kN·m",
    )

    # --- nationally determined parameters ----------------------------------
    suffix = situation.partial_factor_suffix
    gamma_C = float(params.get(f"{EC2_11}:gamma_C_{suffix}", j).magnitude)
    gamma_S = float(params.get(f"{EC2_11}:gamma_S_{suffix}", j).magnitude)
    # §3.1.6(1)P: la flexion simple releve du cas « effort normal et flexion ».
    # L'Annexe belge y met 0,85 et 1,0 partout ailleurs; le module doit dire
    # lequel il applique, il n'a pas le droit de se voir servir un defaut.
    alpha_cc = float(
        params.get(f"{EC2_11}:alpha_cc", j, condition="axial_and_bending").magnitude
    )
    k1 = float(params.get(f"{EC2_11}:k1_redistribution", j).magnitude)
    k2 = float(params.get(f"{EC2_11}:k2_redistribution", j).magnitude)
    as_min_coeff = float(params.get(f"{EC2_11}:As_min_coeff", j).magnitude)
    as_min_floor = float(params.get(f"{EC2_11}:As_min_floor", j).magnitude)
    as_max_ratio = float(params.get(f"{EC2_11}:As_max_ratio", j).magnitude)

    # --- design strengths --------------------------------------------------
    fcd = concrete.fcd(alpha_cc, gamma_C).to("MPa")
    j.step(
        "f_cd", "Resistance de calcul du beton en compression", fcd,
        EC2("§3.1.6(1)P", "(3.15)"),
        latex=r"f_{cd} = \alpha_{cc}\, f_{ck} / \gamma_C",
        numeric=f"{fmt(alpha_cc)} · {fmt(concrete.fck, 'MPa', 0)} / {fmt(gamma_C)}",
        depends_on=("f_ck", f"{EC2_11}:alpha_cc", f"{EC2_11}:gamma_C_{suffix}"),
        display_unit="MPa",
    )

    fyd = steel.fyd(gamma_S).to("MPa")
    j.step(
        "f_yd", "Resistance de calcul de l'acier", fyd,
        EC2("§3.2.7(2)", "(3.14)"),
        latex=r"f_{yd} = f_{yk} / \gamma_S",
        numeric=f"{fmt(steel.fyk, 'MPa', 0)} / {fmt(gamma_S)}",
        depends_on=("f_yk", f"{EC2_11}:gamma_S_{suffix}"),
        display_unit="MPa",
    )

    eps_yd = steel.eps_yd(gamma_S)
    j.step(
        "eps_yd", "Deformation d'ecoulement de calcul de l'acier",
        Q_(eps_yd, "dimensionless"), EC2("§3.2.7(2)"),
        latex=r"\varepsilon_{yd} = f_{yd} / E_s",
        numeric=f"{fmt(fyd, 'MPa', 1)} / {fmt(steel.Es, 'MPa', 0)}",
        depends_on=("f_yd",),
    )

    lam, eta = concrete.lambda_, concrete.eta
    j.step(
        "lambda", "Coefficient de hauteur du diagramme rectangulaire",
        Q_(lam, "dimensionless"), EC2("§3.1.7(3)", "(3.19)"),
        latex=r"\lambda = 0{,}8 \quad (f_{ck} \le 50\ \mathrm{MPa})",
        numeric=f"{fmt(lam)}", depends_on=("f_ck",),
    )
    j.step(
        "eta", "Coefficient de resistance effective du diagramme rectangulaire",
        Q_(eta, "dimensionless"), EC2("§3.1.7(3)", "(3.21)"),
        latex=r"\eta = 1{,}0 \quad (f_{ck} \le 50\ \mathrm{MPa})",
        numeric=f"{fmt(eta)}", depends_on=("f_ck",),
    )

    # --- dimensionless moment ---------------------------------------------
    mu_q = (M_Ed / (section.b * section.d**2 * eta * fcd)).to("dimensionless")
    mu = float(mu_q.magnitude)
    j.step(
        "mu", "Moment reduit", mu_q, EC2("§6.1"),
        latex=r"\mu = \frac{M_{Ed}}{b\, d^{2}\, \eta\, f_{cd}}",
        numeric=(
            f"{fmt(M_Ed, 'kN*m', 2)} / ({fmt(section.b, 'mm', 0)} · "
            f"{fmt(section.d, 'mm', 0)}² · {fmt(eta)} · {fmt(fcd, 'MPa', 2)})"
        ),
        depends_on=("M_Ed", "b", "d", "eta", "f_cd"),
    )

    # --- ductility limit on the neutral axis -------------------------------
    xi_lim = (1.0 - k1) / k2
    j.step(
        "xi_lim", "Limite de l'axe neutre pour la ductilite (sans redistribution)",
        Q_(xi_lim, "dimensionless"), EC2("§5.5(4)", "(5.10a)"),
        latex=r"\left(\frac{x_u}{d}\right)_{lim} = \frac{\delta - k_1}{k_2},\ \delta = 1{,}0",
        numeric=f"(1 − {fmt(k1)}) / {fmt(k2)}",
        depends_on=(f"{EC2_11}:k1_redistribution", f"{EC2_11}:k2_redistribution"),
    )
    mu_lim = lam * xi_lim * (1.0 - lam * xi_lim / 2.0)
    j.step(
        "mu_lim", "Moment reduit limite correspondant",
        Q_(mu_lim, "dimensionless"), EC2("§5.5(4)"),
        latex=r"\mu_{lim} = \lambda\,\xi_{lim}\left(1 - \frac{\lambda \xi_{lim}}{2}\right)",
        numeric=f"{fmt(lam)} · {fmt(xi_lim, digits=4)} · (1 − {fmt(lam)} · {fmt(xi_lim, digits=4)} / 2)",
        depends_on=("lambda", "xi_lim"),
    )

    if mu > mu_lim:
        raise OutOfValidationDomain(
            "compression_reinforcement_required",
            f"moment reduit mu = {mu:.4f} superieur a la limite de ductilite "
            f"mu_lim = {mu_lim:.4f}. La section exigerait des armatures "
            "comprimees, cas non couvert par cette version du moteur. "
            f"Pistes de redimensionnement: augmenter d (actuellement "
            f"{fmt(section.d, 'mm', 0)}), augmenter b (actuellement "
            f"{fmt(section.b, 'mm', 0)}), ou monter en classe de beton.",
            clause="EN 1992-1-1 §5.5(4)",
        )

    # --- neutral axis, lever arm, required area ----------------------------
    xi = (1.0 - math.sqrt(1.0 - 2.0 * mu)) / lam
    j.step(
        "xi", "Hauteur relative de l'axe neutre", Q_(xi, "dimensionless"),
        EC2("§3.1.7(3)"),
        latex=r"\xi = \frac{x}{d} = \frac{1 - \sqrt{1 - 2\mu}}{\lambda}",
        numeric=f"(1 − √(1 − 2 · {fmt(mu, digits=4)})) / {fmt(lam)}",
        depends_on=("mu", "lambda"),
    )
    x = (xi * section.d).to("mm")
    j.step(
        "x", "Hauteur de l'axe neutre", x, EC2("§3.1.7(3)"),
        latex=r"x = \xi\, d",
        numeric=f"{fmt(xi, digits=4)} · {fmt(section.d, 'mm', 0)}",
        depends_on=("xi", "d"), display_unit="mm",
    )
    z = (section.d * (1.0 - lam * xi / 2.0)).to("mm")
    j.step(
        "z", "Bras de levier des efforts internes", z, EC2("§6.1"),
        latex=r"z = d\left(1 - \frac{\lambda \xi}{2}\right)",
        numeric=f"{fmt(section.d, 'mm', 0)} · (1 − {fmt(lam)} · {fmt(xi, digits=4)} / 2)",
        depends_on=("d", "xi", "lambda"), display_unit="mm",
    )

    As_strength = (M_Ed / (fyd * z)).to("mm**2")
    j.step(
        "A_s_calc", "Section d'acier requise par la resistance", As_strength,
        EC2("§6.1"),
        latex=r"A_{s} = \frac{M_{Ed}}{f_{yd}\, z}",
        numeric=f"{fmt(M_Ed, 'kN*m', 2)} / ({fmt(fyd, 'MPa', 1)} · {fmt(z, 'mm', 1)})",
        depends_on=("M_Ed", "f_yd", "z"), display_unit="mm²",
    )

    eps_s = concrete.eps_cu3 * (1.0 - xi) / xi
    j.step(
        "eps_s", "Deformation de l'acier tendu", Q_(eps_s, "dimensionless"),
        EC2("§6.1(2)P"),
        latex=r"\varepsilon_s = \varepsilon_{cu3}\,\frac{1-\xi}{\xi}",
        numeric=f"{fmt(concrete.eps_cu3 * 1000, digits=2)}‰ · (1 − {fmt(xi, digits=4)}) / {fmt(xi, digits=4)}",
        depends_on=("xi",),
    )

    # --- detailing limits --------------------------------------------------
    fctm = concrete.fctm.to("MPa")
    j.step(
        "f_ctm", "Resistance moyenne du beton en traction", fctm,
        EC2("§3.1.2, Tab. 3.1"),
        latex=r"f_{ctm} = 0{,}30\, f_{ck}^{2/3}",
        numeric=f"0.30 · {fmt(concrete.fck, 'MPa', 0)}^(2/3)",
        depends_on=("f_ck",), display_unit="MPa",
    )
    As_min_a = (as_min_coeff * fctm / steel.fyk * section.b * section.d).to("mm**2")
    As_min_b = (as_min_floor * section.b * section.d).to("mm**2")
    As_min = max(As_min_a, As_min_b)
    j.step(
        "A_s_min", "Section minimale d'armature tendue", As_min,
        EC2("§9.2.1.1(1)", "(9.1N)"),
        latex=(
            r"A_{s,min} = \max\left(0{,}26\,\frac{f_{ctm}}{f_{yk}} b_t d\ ;\ "
            r"0{,}0013\, b_t d\right)"
        ),
        numeric=(
            f"max({fmt(as_min_coeff)} · {fmt(fctm, 'MPa', 2)} / {fmt(steel.fyk, 'MPa', 0)}"
            f" · {fmt(section.b, 'mm', 0)} · {fmt(section.d, 'mm', 0)} = "
            f"{fmt(As_min_a, 'mm**2', 1)} ; {fmt(as_min_floor, digits=4)} · "
            f"{fmt(section.b, 'mm', 0)} · {fmt(section.d, 'mm', 0)} = "
            f"{fmt(As_min_b, 'mm**2', 1)})"
        ),
        depends_on=("f_ctm", "f_yk", "b", "d", f"{EC2_11}:As_min_coeff", f"{EC2_11}:As_min_floor"),
        display_unit="mm²",
    )

    As_max = (as_max_ratio * section.Ac).to("mm**2")
    j.step(
        "A_s_max", "Section maximale d'armature (hors recouvrements)", As_max,
        EC2("§9.2.1.1(3)"),
        latex=r"A_{s,max} = 0{,}04\, A_c",
        numeric=f"{fmt(as_max_ratio)} · {fmt(section.b, 'mm', 0)} · {fmt(section.h, 'mm', 0)}",
        depends_on=("b", "h", f"{EC2_11}:As_max_ratio"), display_unit="mm²",
    )

    As_required = max(As_strength, As_min)
    j.step(
        "A_s_req", "Section d'acier a mettre en oeuvre", As_required,
        EC2("§6.1 et §9.2.1.1(1)"),
        latex=r"A_{s,req} = \max(A_s\ ;\ A_{s,min})",
        numeric=f"max({fmt(As_strength, 'mm**2', 1)} ; {fmt(As_min, 'mm**2', 1)})",
        depends_on=("A_s_calc", "A_s_min"), display_unit="mm²",
    )

    # --- resistance of the section as actually detailed ---------------------
    if A_s_provided is not None:
        require_dimension(A_s_provided, "[length] ** 2", "A_s_provided")
        As_actual = A_s_provided.to("mm**2")
        j.input(
            "A_s_prov", "Section d'acier effectivement mise en oeuvre", As_actual,
            Provenance.user("choix de ferraillage de l'ingenieur"),
            clause=EC2("§9.2.1.1"), display_unit="mm²",
        )
    else:
        As_actual = As_required

    resistance = moment_resistance(
        section=section, concrete=concrete, steel=steel, A_s=As_actual,
        fcd=fcd, fyd=fyd, eps_yd=eps_yd, journal=j, prefix="chk_",
    )

    # --- checks ------------------------------------------------------------
    report = VerificationReport(element=element)
    report.add(
        Check.from_ratio(
            "ELU — flexion simple", M_Ed, resistance.M_Rd, EC2("§6.1"),
            detail=(
                "Le moment resistant est insuffisant."
                if M_Ed > resistance.M_Rd else None
            ),
            remedy="Augmenter d, b, la classe de beton ou la section d'acier.",
        )
    )
    report.add(
        Check.from_ratio(
            "Ductilite — position de l'axe neutre",
            Q_(xi, "dimensionless"), Q_(xi_lim, "dimensionless"),
            EC2("§5.5(4)", "(5.10a)"),
            detail=(
                f"x/d = {xi:.3f} depasse la limite {xi_lim:.3f}: rupture fragile."
                if xi > xi_lim else None
            ),
            remedy="Augmenter la hauteur utile ou la classe de beton.",
        )
    )
    report.add(
        Check.from_ratio(
            "Section minimale d'armature", As_min, As_actual,
            EC2("§9.2.1.1(1)", "(9.1N)"),
            detail=(
                "La section mise en oeuvre est inferieure au minimum normatif."
                if As_min > As_actual else None
            ),
            remedy="Augmenter la section d'acier mise en oeuvre.",
        )
    )
    report.add(
        Check.from_ratio(
            "Section maximale d'armature", As_actual, As_max,
            EC2("§9.2.1.1(3)"),
            detail=(
                "La section d'acier depasse 4 % de la section de beton."
                if As_actual > As_max else None
            ),
            remedy="Augmenter les dimensions de la section de beton.",
        )
    )

    return FlexureDesign(
        element=element,
        As_strength=As_strength,
        As_min=As_min,
        As_max=As_max,
        As_required=As_required,
        As_provided=As_actual,
        x=x, z=z, mu=mu, xi=xi, xi_lim=xi_lim, eps_s=eps_s,
        resistance=resistance,
        report=report,
        journal=j,
        ndp_summary=params.summary(),
    )
