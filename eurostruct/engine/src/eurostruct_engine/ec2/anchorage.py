"""EN 1992-1-1 §8.4 and §8.7 — anchorage and lap lengths of ribbed bars.

Scope of this module (the *validated domain*):

* ribbed bars in tension or compression, ``phi <= 32 mm``;
* concrete up to C50/60;
* normal-weight concrete, no bundled bars, no bent-up bars in bundles;
* straight anchorage, or a shape from Figure 8.1 handled through ``alpha_1``.

The chain, and why each step is separate
----------------------------------------
1. ``f_bd`` — ultimate bond stress, §8.4.2 eq. (8.2). Depends on the concrete's
   *tensile* strength, so ``alpha_ct`` enters here, not ``alpha_cc``.
2. ``l_b,rqd`` — the length needed to develop the bar stress at that bond,
   §8.4.3 eq. (8.3). Depends on ``sigma_sd``, the stress the bar actually
   carries, not on ``f_yd``: a bar working at half its capacity needs half the
   length, and pretending otherwise wastes steel on every drawing.
3. ``l_bd`` — the design length, §8.4.4 eq. (8.4), obtained by applying five
   coefficients for bar shape, cover, transverse reinforcement, welded bars and
   transverse pressure.
4. ``l_0`` — the lap length, §8.7.3 eq. (8.10), which is ``l_bd`` with a sixth
   coefficient for the proportion of bars lapped at the same section.

The coefficients are inputs, not decisions the engine makes
-----------------------------------------------------------
``alpha_1`` to ``alpha_6`` of Table 8.2 depend on how the bar is actually
detailed: its shape, the cover to the bar in question, what transverse steel
crosses it and where. None of that can be read from a section's dimensions —
it is a drawing decision. The engine therefore takes them, checks each against
the range Table 8.2 allows, and enforces the product rule of §8.4.4(2):

    alpha_2 * alpha_3 * alpha_5 >= 0,7

A caller that supplies nothing gets 1,0 everywhere, which is the conservative
reading of the table for every coefficient.

alpha_ct, not alpha_cc
----------------------
Bond is governed by ``f_ctd = alpha_ct f_ctk,0.05 / gamma_C``. The Belgian
annex makes ``alpha_cc`` conditional (0,85 in bending, 1,0 otherwise) but
leaves ``alpha_ct`` a plain 1,0; reaching for the compression coefficient here
would be a different value for a different quantity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Mapping

from ..basis import DesignSituation
from ..exceptions import InconsistentInput, OutOfValidationDomain
from ..materials.concrete import Concrete
from ..materials.reinforcement import Reinforcement
from ..ndp.registry import ParameterSet
from ..traceability import EC2, Journal, Provenance
from ..units import Q_, Quantity, fmt, require_dimension
from ..version import ENGINE_VERSION

__all__ = [
    "BondCondition",
    "AnchorageCoefficients",
    "AnchorageDesign",
    "design_anchorage",
    "required_parameters",
    "EC2_11",
]

EC2_11: Final = "EN 1992-1-1"

_FCK_MAX_MPA = 50.0
#: §8.4.2(2): the formula for eta_2 applies to bars larger than 32 mm, which
#: this module has not been validated for.
_PHI_MAX_MM = 32.0

#: §8.4.2(2), eq. (8.2): f_bd = 2,25 eta_1 eta_2 f_ctd.
_BOND_FACTOR = 2.25

#: §8.4.4(2): the product of the three "confinement" coefficients has a floor.
_ALPHA_PRODUCT_MIN = 0.7

#: §8.4.4(1): floors on the design anchorage length, in tension and in
#: compression. Fixed in the Eurocode itself, not nationally determined.
_LB_MIN_TENSION_RQD = 0.3
_LB_MIN_COMPRESSION_RQD = 0.6
_LB_MIN_PHI_FACTOR = 10.0
_LB_MIN_ABSOLUTE_MM = 100.0

#: §8.7.3(1): the lap length has its own floor.
_L0_MIN_RQD = 0.3
_L0_MIN_PHI_FACTOR = 15.0
_L0_MIN_ABSOLUTE_MM = 200.0


class BondCondition(str):
    """§8.4.2(1): whether the bar sits in a zone of good bond.

    Not a judgement the engine can make — it depends on the bar's position
    during casting and on the depth of concrete beneath it. The detailer states
    it, and the note de calcul prints which was assumed.
    """

    GOOD = "good"
    POOR = "poor"

    @staticmethod
    def eta_1(condition: str) -> float:
        if condition == BondCondition.GOOD:
            return 1.0
        if condition == BondCondition.POOR:
            return 0.7
        raise InconsistentInput(
            f"condition d'adherence inconnue: '{condition}'. "
            f"Valeurs admises: '{BondCondition.GOOD}', '{BondCondition.POOR}'."
        )


@dataclass(frozen=True, slots=True)
class AnchorageCoefficients:
    """Table 8.2 coefficients, as detailed on the drawing.

    Defaults are 1,0 — the conservative reading of every row. Supplying a value
    below 1,0 is a claim about the detailing, and the caller answers for it.

    :param alpha_1: bar shape (§8.4.4, Fig. 8.1). 1,0 straight; 0,7 for a bend
        or hook **in tension** when the cover perpendicular to the bend is
        > 3 phi. Always 1,0 in compression.
    :param alpha_2: concrete cover.
    :param alpha_3: confinement by transverse reinforcement not welded to the
        main bars.
    :param alpha_4: confinement by welded transverse reinforcement.
    :param alpha_5: confinement by transverse pressure.
    :param alpha_6: proportion of bars lapped at the same section (§8.7.3,
        Table 8.3): 1,0 up to 25 %, 1,4 at 50 %, 1,5 above.
    """

    alpha_1: float = 1.0
    alpha_2: float = 1.0
    alpha_3: float = 1.0
    alpha_4: float = 1.0
    alpha_5: float = 1.0
    alpha_6: float = 1.0

    #: Table 8.2 / Table 8.3 admissible ranges, checked rather than assumed.
    _RANGES = {
        "alpha_1": (0.7, 1.0),
        "alpha_2": (0.7, 1.0),
        "alpha_3": (0.7, 1.0),
        "alpha_4": (0.7, 1.0),
        "alpha_5": (0.7, 1.0),
        "alpha_6": (1.0, 1.5),
    }

    def __post_init__(self) -> None:
        for name, (lo, hi) in self._RANGES.items():
            v = getattr(self, name)
            if not (lo <= v <= hi):
                raise InconsistentInput(
                    f"{name} = {v} est hors du domaine du Tableau 8.2/8.3 "
                    f"[{lo} ; {hi}]."
                )
        product = self.alpha_2 * self.alpha_3 * self.alpha_5
        if product < _ALPHA_PRODUCT_MIN:
            raise InconsistentInput(
                f"§8.4.4(2): le produit alpha_2 · alpha_3 · alpha_5 = "
                f"{product:.4f} est inferieur au plancher {_ALPHA_PRODUCT_MIN}. "
                "Les effets de confinement ne se cumulent pas indefiniment."
            )


@dataclass
class AnchorageDesign:
    """Result of an anchorage and lap calculation."""

    element: str
    #: Ultimate bond stress, §8.4.2 eq. (8.2).
    f_bd: Quantity
    #: Basic required anchorage length, §8.4.3 eq. (8.3).
    l_b_rqd: Quantity
    #: Design anchorage length, §8.4.4 eq. (8.4), floors applied.
    l_bd: Quantity
    #: The floor of §8.4.4(1), reported so the note can say when it governs.
    l_b_min: Quantity
    l_b_min_governs: bool
    #: Design lap length, §8.7.3 eq. (8.10), floors applied.
    l_0: Quantity
    l_0_min: Quantity
    #: Stress the bar actually carries at the section considered.
    sigma_sd: Quantity
    in_tension: bool
    bond_condition: str
    journal: Journal
    engine_version: str = ENGINE_VERSION
    ndp_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element,
            "engine_version": self.engine_version,
            "f_bd_MPa": float(self.f_bd.to("MPa").magnitude),
            "l_b_rqd_mm": float(self.l_b_rqd.to("mm").magnitude),
            "l_bd_mm": float(self.l_bd.to("mm").magnitude),
            "l_b_min_mm": float(self.l_b_min.to("mm").magnitude),
            "l_b_min_governs": self.l_b_min_governs,
            "l_0_mm": float(self.l_0.to("mm").magnitude),
            "l_0_min_mm": float(self.l_0_min.to("mm").magnitude),
            "sigma_sd_MPa": float(self.sigma_sd.to("MPa").magnitude),
            "in_tension": self.in_tension,
            "bond_condition": self.bond_condition,
            "journal": self.journal.to_dict(),
            "ndp": self.ndp_summary,
        }


def required_parameters(situation: DesignSituation) -> tuple[str, ...]:
    """National parameters this module needs, for preflight (TICKET 1.3)."""
    suffix = situation.partial_factor_suffix
    return (
        f"{EC2_11}:gamma_C_{suffix}",
        f"{EC2_11}:gamma_S_{suffix}",
        # Adherence: f_ctd = alpha_ct f_ctk,0.05 / gamma_C. C'est bien le
        # coefficient de TRACTION, pas celui de compression.
        f"{EC2_11}:alpha_ct",
    )


def design_anchorage(
    *,
    concrete: Concrete,
    steel: Reinforcement,
    phi: Quantity,
    params: ParameterSet,
    sigma_sd: Quantity | None = None,
    A_s_required: Quantity | None = None,
    A_s_provided: Quantity | None = None,
    in_tension: bool = True,
    bond_condition: str = BondCondition.GOOD,
    coefficients: AnchorageCoefficients | None = None,
    situation: DesignSituation = DesignSituation.PERSISTENT,
    element: str = "element",
    provenance: Mapping[str, Provenance] | None = None,
) -> AnchorageDesign:
    """Anchorage and lap lengths for one bar diameter.

    :param sigma_sd: stress the bar carries where the anchorage starts. When
        omitted it is taken as ``f_yd``, unless ``A_s_required`` and
        ``A_s_provided`` are supplied, in which case §8.4.3 allows
        ``sigma_sd = f_yd A_s,req / A_s,prov`` — the bar is not fully stressed
        when more steel was placed than the design needed.
    :param coefficients: Table 8.2 values from the drawing. Defaults to 1,0.
    :raises OutOfValidationDomain: outside the declared scope.
    """
    require_dimension(phi, "[length]", "phi")
    phi_mm = float(phi.to("mm").magnitude)
    if phi_mm <= 0:
        raise InconsistentInput("'phi' doit etre strictement positif")
    if phi_mm > _PHI_MAX_MM:
        raise OutOfValidationDomain(
            "large_diameter_bar",
            f"phi = {phi_mm:g} mm depasse 32 mm; §8.4.2(2) et §8.8 imposent "
            "des regles supplementaires que ce module ne traite pas.",
            clause="EN 1992-1-1 §8.8",
        )
    if concrete.fck.to("MPa").magnitude > _FCK_MAX_MPA:
        raise OutOfValidationDomain(
            "high_strength_concrete",
            f"ce module est valide jusqu'a C50/60; {concrete.name} le depasse.",
            clause="EN 1992-1-1 §3.1.2",
        )

    params.require(required_parameters(situation))
    coeff = coefficients or AnchorageCoefficients()
    if not in_tension and coeff.alpha_1 != 1.0:
        raise InconsistentInput(
            "§8.4.4, Tableau 8.2: alpha_1 vaut toujours 1,0 en compression. "
            "Une courbure n'ancre pas une barre comprimee."
        )

    j = Journal(f"Ancrage et recouvrement — {element}")
    prov = dict(provenance or {})

    j.input("phi", "Diametre de la barre", phi,
            prov.get("phi", Provenance.user("ferraillage")),
            clause=EC2("§8.4.2"), display_unit="mm")
    j.input("f_ck", f"Resistance caracteristique du beton ({concrete.name})",
            concrete.fck, Provenance.user(f"classe {concrete.name}"),
            clause=EC2("§3.1.2, Tab. 3.1"), display_unit="MPa")
    j.input("f_yk", f"Limite d'elasticite de l'acier ({steel.name})",
            steel.fyk, Provenance.user(f"nuance {steel.name}"),
            clause=EC2("§3.2.2"), display_unit="MPa")

    suffix = situation.partial_factor_suffix
    gamma_C = float(params.get(f"{EC2_11}:gamma_C_{suffix}", j).magnitude)
    gamma_S = float(params.get(f"{EC2_11}:gamma_S_{suffix}", j).magnitude)
    alpha_ct = float(params.get(f"{EC2_11}:alpha_ct", j).magnitude)

    # --- bond stress, §8.4.2 ----------------------------------------------
    fctd = concrete.fctd(alpha_ct, gamma_C).to("MPa")
    j.step("f_ctd", "Resistance de calcul du beton en traction", fctd,
           EC2("§3.1.6(2)P", "(3.16)"),
           latex=r"f_{ctd} = \alpha_{ct}\, f_{ctk;0{,}05} / \gamma_C",
           numeric=(f"{fmt(alpha_ct)} · {fmt(concrete.fctk_005, 'MPa', 3)} / "
                    f"{fmt(gamma_C)}"),
           depends_on=("f_ck", f"{EC2_11}:alpha_ct", f"{EC2_11}:gamma_C_{suffix}"),
           display_unit="MPa")

    eta_1 = BondCondition.eta_1(bond_condition)
    j.step("eta_1", "Coefficient de condition d'adherence",
           Q_(eta_1, "dimensionless"), EC2("§8.4.2(2)"),
           latex=r"\eta_1 = 1{,}0\ \text{(bonnes conditions)},\ 0{,}7\ \text{(autres)}",
           numeric=f"{fmt(eta_1)} — conditions declarees: « {bond_condition} »")

    # §8.4.2(2): eta_2 = 1,0 up to 32 mm, (132 - phi)/100 beyond. The module
    # refuses beyond 32 mm, so eta_2 is 1,0 here — stated rather than dropped.
    eta_2 = 1.0
    j.step("eta_2", "Coefficient de diametre", Q_(eta_2, "dimensionless"),
           EC2("§8.4.2(2)"),
           latex=r"\eta_2 = 1{,}0 \quad (\phi \le 32\ \mathrm{mm})",
           numeric=f"{fmt(eta_2)} (phi = {phi_mm:g} mm ≤ 32 mm)",
           depends_on=("phi",))

    f_bd = (_BOND_FACTOR * eta_1 * eta_2 * fctd).to("MPa")
    j.step("f_bd", "Contrainte ultime d'adherence", f_bd,
           EC2("§8.4.2(2)", "(8.2)"),
           latex=r"f_{bd} = 2{,}25\, \eta_1\, \eta_2\, f_{ctd}",
           numeric=f"2.25 · {fmt(eta_1)} · {fmt(eta_2)} · {fmt(fctd, 'MPa', 3)}",
           depends_on=("eta_1", "eta_2", "f_ctd"), display_unit="MPa")

    # --- bar stress, §8.4.3 ------------------------------------------------
    fyd = steel.fyd(gamma_S).to("MPa")
    if sigma_sd is not None:
        require_dimension(sigma_sd, "[pressure]", "sigma_sd")
        sigma = sigma_sd.to("MPa")
        sigma_note = "contrainte declaree par l'ingenieur"
    elif A_s_required is not None and A_s_provided is not None:
        require_dimension(A_s_required, "[length] ** 2", "A_s_required")
        require_dimension(A_s_provided, "[length] ** 2", "A_s_provided")
        if A_s_provided.magnitude <= 0:
            raise InconsistentInput("'A_s_provided' doit etre strictement positif")
        ratio = float((A_s_required / A_s_provided).to("dimensionless").magnitude)
        if ratio > 1.0:
            raise InconsistentInput(
                f"A_s,req ({fmt(A_s_required, 'mm**2', 1)}) depasse A_s,prov "
                f"({fmt(A_s_provided, 'mm**2', 1)}): la section n'est pas ferraillee."
            )
        sigma = (fyd * ratio).to("MPa")
        sigma_note = "reduite au prorata A_s,req / A_s,prov (§8.4.3)"
    else:
        sigma = fyd
        sigma_note = "barre supposee pleinement sollicitee, sigma_sd = f_yd"

    j.step("sigma_sd", "Contrainte dans la barre a l'origine de l'ancrage",
           sigma, EC2("§8.4.3(2)"),
           latex=r"\sigma_{sd}",
           numeric=f"{fmt(sigma, 'MPa', 2)} — {sigma_note}",
           depends_on=("f_yk", f"{EC2_11}:gamma_S_{suffix}"), display_unit="MPa")

    l_b_rqd = (phi / 4.0 * (sigma / f_bd)).to("mm")
    j.step("l_b_rqd", "Longueur d'ancrage de reference", l_b_rqd,
           EC2("§8.4.3(2)", "(8.3)"),
           latex=r"l_{b,rqd} = \frac{\phi}{4}\cdot\frac{\sigma_{sd}}{f_{bd}}",
           numeric=(f"{phi_mm:g} / 4 · {fmt(sigma, 'MPa', 2)} / "
                    f"{fmt(f_bd, 'MPa', 3)}"),
           depends_on=("phi", "sigma_sd", "f_bd"), display_unit="mm")

    # --- design anchorage length, §8.4.4 -----------------------------------
    alpha_product = (
        coeff.alpha_1 * coeff.alpha_2 * coeff.alpha_3 * coeff.alpha_4 * coeff.alpha_5
    )
    j.step("alpha_prod", "Produit des coefficients du Tableau 8.2",
           Q_(alpha_product, "dimensionless"), EC2("§8.4.4(1)", "(8.4)"),
           latex=r"\alpha_1\alpha_2\alpha_3\alpha_4\alpha_5",
           numeric=(f"{fmt(coeff.alpha_1)} · {fmt(coeff.alpha_2)} · "
                    f"{fmt(coeff.alpha_3)} · {fmt(coeff.alpha_4)} · "
                    f"{fmt(coeff.alpha_5)}"))

    rqd_floor = _LB_MIN_TENSION_RQD if in_tension else _LB_MIN_COMPRESSION_RQD
    l_b_min = max(
        (rqd_floor * l_b_rqd).to("mm"),
        Q_(_LB_MIN_PHI_FACTOR * phi_mm, "mm"),
        Q_(_LB_MIN_ABSOLUTE_MM, "mm"),
        key=lambda q: q.magnitude,
    )
    j.step("l_b_min", "Longueur d'ancrage minimale", l_b_min,
           EC2("§8.4.4(1)", "(8.6)/(8.7)"),
           latex=(r"l_{b,min} = \max\{0{,}3\, l_{b,rqd};\ 10\phi;\ 100\ \mathrm{mm}\}"
                  if in_tension else
                  r"l_{b,min} = \max\{0{,}6\, l_{b,rqd};\ 10\phi;\ 100\ \mathrm{mm}\}"),
           numeric=(f"max({rqd_floor} · {fmt(l_b_rqd, 'mm', 1)} ; "
                    f"10 · {phi_mm:g} ; 100 mm) — "
                    f"{'traction' if in_tension else 'compression'}"),
           depends_on=("l_b_rqd", "phi"), display_unit="mm")

    l_bd_unfloored = (alpha_product * l_b_rqd).to("mm")
    l_b_min_governs = l_b_min.magnitude > l_bd_unfloored.magnitude
    l_bd = max(l_bd_unfloored, l_b_min, key=lambda q: q.magnitude)
    j.step("l_bd", "Longueur d'ancrage de calcul", l_bd,
           EC2("§8.4.4(1)", "(8.4)"),
           latex=r"l_{bd} = \alpha_1\alpha_2\alpha_3\alpha_4\alpha_5\, l_{b,rqd} \ge l_{b,min}",
           numeric=(f"{fmt(alpha_product)} · {fmt(l_b_rqd, 'mm', 1)} = "
                    f"{fmt(l_bd_unfloored, 'mm', 1)}"
                    + (" → plancher l_b,min retenu" if l_b_min_governs else "")),
           depends_on=("alpha_prod", "l_b_rqd", "l_b_min"), display_unit="mm")

    # --- lap length, §8.7.3 ------------------------------------------------
    l_0_min = max(
        (_L0_MIN_RQD * coeff.alpha_6 * l_b_rqd).to("mm"),
        Q_(_L0_MIN_PHI_FACTOR * phi_mm, "mm"),
        Q_(_L0_MIN_ABSOLUTE_MM, "mm"),
        key=lambda q: q.magnitude,
    )
    j.step("alpha_6", "Coefficient de proportion de barres recouvertes",
           Q_(coeff.alpha_6, "dimensionless"), EC2("§8.7.3(1)", "Tab. 8.3"),
           latex=r"\alpha_6 = \sqrt{\rho_1/25} \quad (1{,}0 \le \alpha_6 \le 1{,}5)",
           numeric=f"{fmt(coeff.alpha_6)} (declare d'apres le plan de ferraillage)")
    j.step("l_0_min", "Longueur de recouvrement minimale", l_0_min,
           EC2("§8.7.3(1)", "(8.11)"),
           latex=r"l_{0,min} = \max\{0{,}3\,\alpha_6\, l_{b,rqd};\ 15\phi;\ 200\ \mathrm{mm}\}",
           numeric=(f"max(0.3 · {fmt(coeff.alpha_6)} · {fmt(l_b_rqd, 'mm', 1)} ; "
                    f"15 · {phi_mm:g} ; 200 mm)"),
           depends_on=("l_b_rqd", "phi", "alpha_6"), display_unit="mm")

    l_0_unfloored = (alpha_product * coeff.alpha_6 * l_b_rqd).to("mm")
    l_0 = max(l_0_unfloored, l_0_min, key=lambda q: q.magnitude)
    j.step("l_0", "Longueur de recouvrement de calcul", l_0,
           EC2("§8.7.3(1)", "(8.10)"),
           latex=(r"l_0 = \alpha_1\alpha_2\alpha_3\alpha_5\alpha_6\, l_{b,rqd} "
                  r"\ge l_{0,min}"),
           numeric=(f"{fmt(alpha_product)} · {fmt(coeff.alpha_6)} · "
                    f"{fmt(l_b_rqd, 'mm', 1)} = {fmt(l_0_unfloored, 'mm', 1)}"
                    + (" → plancher l_0,min retenu"
                       if l_0_min.magnitude > l_0_unfloored.magnitude else "")),
           depends_on=("alpha_prod", "alpha_6", "l_b_rqd", "l_0_min"),
           display_unit="mm")

    return AnchorageDesign(
        element=element,
        f_bd=f_bd,
        l_b_rqd=l_b_rqd,
        l_bd=l_bd,
        l_b_min=l_b_min,
        l_b_min_governs=l_b_min_governs,
        l_0=l_0,
        l_0_min=l_0_min,
        sigma_sd=sigma,
        in_tension=in_tension,
        bond_condition=bond_condition,
        journal=j,
        ndp_summary=params.summary(),
    )
