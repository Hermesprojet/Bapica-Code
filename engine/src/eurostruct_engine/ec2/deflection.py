"""EN 1992-1-1 §7.4.2 — span/depth ratio exempting from a deflection calculation.

What this module answers, and what it does NOT
-----------------------------------------------
§7.4.2 is titled *cas de dispense du calcul*. Passing it means the deflection
need not be computed. **Failing it does not mean the member deflects too much**
— it means the exemption does not apply and §7.4.3 has to be run. That
distinction is carried into the wording of the check and into
:attr:`SpanDepthCheck.verdict`, because reporting a failed exemption the way a
failed strength check is reported would tell an engineer their beam is
inadequate when nothing of the sort has been established.

This module does **not** compute deflections. §7.4.3 needs the loading history,
the cracked and uncracked curvatures, the shrinkage curvature and a creep
coefficient, and it integrates over the span. None of that is here, and the
refusal message says so rather than letting the exemption stand in for it.

Nor does it hold deflection **limits**. §7.4.1(3) recommends span/250 for
appearance and span/500 for damage to adjacent parts, but NBN EN 1992-1-1 ANB
§7.4.1(3) adds: « La norme NBN B 03-003 donne des indications quant aux limites
de flèches en fonction de la destination de l'élément. » That document is not
in hand, so Belgian deflection limits are unknown to this engine and no default
is substituted for them.

Scope of this module (the *validated domain*):

* rectangular cross-section — a flanged section is admitted only through the
  explicit ``flanged`` factor of §7.4.2(2), supplied by the caller;
* concrete up to C50/60;
* reinforced concrete, no prestress;
* the reinforcement ratios are those at the section §7.4.2 designates: midspan
  for a span, at the support for a cantilever. Which one was supplied is the
  caller's statement, journalised as such.
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
    "StructuralSystem",
    "SpanDepthCheck",
    "check_span_depth",
    "required_parameters",
]

_FCK_MAX_MPA = 50.0

#: §7.4.2(2): a flanged section with b_eff/b_w > 3 takes 0,8.
_FLANGE_THRESHOLD: Final = 3.0
_FLANGE_FACTOR: Final = 0.8

#: §7.4.2(2): beams and slabs over 7 m supporting partitions liable to be
#: damaged take 7/l_eff. Flat slabs take 8,5/l_eff beyond 8,5 m.
_LONG_SPAN_M: Final = 7.0
_LONG_SPAN_FLAT_SLAB_M: Final = 8.5

#: §7.4.2(2): the stress-level factor is capped at 1,5.
_STRESS_FACTOR_CAP: Final = 1.5


class StructuralSystem(str, Enum):
    """Rows of Table 7.4N.

    An input, not something the section can reveal: whether a beam is an end
    span or an interior span is a property of the frame around it. Between a
    cantilever (K = 0,4) and an interior span (K = 1,5) there is a factor of
    nearly four, so a default here would be the most expensive kind of guess.
    """

    SIMPLY_SUPPORTED = "simply_supported"
    END_SPAN_CONTINUOUS = "end_span_continuous"
    INTERIOR_SPAN_CONTINUOUS = "interior_span_continuous"
    FLAT_SLAB = "flat_slab"
    CANTILEVER = "cantilever"

    @property
    def label(self) -> str:
        return {
            StructuralSystem.SIMPLY_SUPPORTED: "poutre ou dalle isostatique",
            StructuralSystem.END_SPAN_CONTINUOUS: "travee de rive continue",
            StructuralSystem.INTERIOR_SPAN_CONTINUOUS: "travee intermediaire",
            StructuralSystem.FLAT_SLAB: "plancher-dalle",
            StructuralSystem.CANTILEVER: "console",
        }[self]

    @property
    def long_span_threshold_m(self) -> float:
        """Above which §7.4.2(2) applies the partition-damage reduction."""
        if self is StructuralSystem.FLAT_SLAB:
            return _LONG_SPAN_FLAT_SLAB_M
        return _LONG_SPAN_M


def required_parameters() -> tuple[str, ...]:
    return (f"{EC2_11}:K_span_depth",)


@dataclass
class SpanDepthCheck:
    """Result of the §7.4.2 exemption test."""

    element: str
    system: StructuralSystem
    K: float
    #: Reference ratio rho_0 = 1e-3 sqrt(f_ck).
    rho_0: float
    rho: float
    rho_comp: float
    #: Basic ratio from (7.16a) or (7.16b), before the §7.4.2(2) factors.
    basic_ratio: float
    #: Whether (7.16b) — the compression-reinforcement branch — was used.
    heavily_reinforced: bool
    stress_factor: float
    flange_factor: float
    long_span_factor: float
    limit_ratio: float
    actual_ratio: float
    l_eff: Quantity
    report: VerificationReport
    journal: Journal
    engine_version: str = ENGINE_VERSION
    ndp_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def exempt(self) -> bool:
        """Whether the deflection calculation may be skipped."""
        return self.actual_ratio <= self.limit_ratio

    @property
    def utilisation(self) -> float:
        return self.report.max_utilisation

    @property
    def verdict(self) -> str:
        """What the outcome means, in words a note can print.

        Written out because "échec" alone would be read as "the beam deflects
        too much", which §7.4.2 never establishes.
        """
        if self.exempt:
            return (
                f"Rapport l/d = {self.actual_ratio:.2f} <= limite "
                f"{self.limit_ratio:.2f} (§7.4.2): le calcul de la fleche N'EST "
                "PAS REQUIS. La fleche n'a pas ete calculee et n'avait pas a "
                "l'etre."
            )
        return (
            f"Rapport l/d = {self.actual_ratio:.2f} > limite "
            f"{self.limit_ratio:.2f} (§7.4.2): la DISPENSE NE S'APPLIQUE PAS. "
            "Cela n'etablit PAS que la fleche est excessive — seulement que le "
            "critere forfaitaire ne permet pas de s'en dispenser. Il faut "
            "calculer la fleche selon le §7.4.3, ce que ce module ne fait pas."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element,
            "engine_version": self.engine_version,
            "system": self.system.value,
            "K": self.K,
            "rho_0": self.rho_0,
            "rho": self.rho,
            "rho_comp": self.rho_comp,
            "basic_ratio": self.basic_ratio,
            "heavily_reinforced": self.heavily_reinforced,
            "stress_factor": self.stress_factor,
            "flange_factor": self.flange_factor,
            "long_span_factor": self.long_span_factor,
            "limit_ratio": self.limit_ratio,
            "actual_ratio": self.actual_ratio,
            "l_eff_mm": float(self.l_eff.to("mm").magnitude),
            "exempt": self.exempt,
            "verdict": self.verdict,
            "utilisation": self.utilisation,
            "verification": self.report.to_dict(),
            "journal": self.journal.to_dict(),
            "ndp": self.ndp_summary,
        }


def check_span_depth(
    *,
    section: RectangularSection,
    concrete: Concrete,
    steel: Reinforcement,
    l_eff: Quantity,
    system: StructuralSystem,
    A_s_required: Quantity,
    A_s_provided: Quantity,
    params: ParameterSet,
    A_s_comp: Quantity | None = None,
    b_eff_over_b_w: float | None = None,
    supports_brittle_partitions: bool = False,
    element: str = "poutre",
    provenance: Mapping[str, Provenance] | None = None,
) -> SpanDepthCheck:
    """Test whether §7.4.2 exempts this member from a deflection calculation.

    :param l_eff: effective span, §5.3.2.2.
    :param system: row of Table 7.4N. No default — see
        :class:`StructuralSystem`.
    :param A_s_required: tension steel required by the ULS calculation at the
        section §7.4.2 designates.
    :param A_s_provided: tension steel actually detailed there. The ratio of the
        two is what the §7.4.2(2) stress factor rests on.
    :param A_s_comp: compression reinforcement, if any. Only enters (7.16b).
    :param b_eff_over_b_w: flange ratio. Above 3,0 the limit takes 0,8.
        ``None`` means a rectangular section, stated rather than assumed.
    :param supports_brittle_partitions: whether the member carries partitions
        liable to be damaged by excessive deflection — an input, because no
        geometry reveals it.
    """
    require_dimension(l_eff, "[length]", "l_eff")
    for name, A in (("A_s_required", A_s_required), ("A_s_provided", A_s_provided)):
        require_dimension(A, "[length] ** 2", name)
        if A.magnitude <= 0:
            raise InconsistentInput(f"'{name}' doit etre strictement positif")
    if l_eff.magnitude <= 0:
        raise InconsistentInput("la portee utile doit etre strictement positive")
    if A_s_provided < A_s_required:
        raise InconsistentInput(
            f"A_s,prov = {fmt(A_s_provided, 'mm**2', 0)} est inferieure a "
            f"A_s,req = {fmt(A_s_required, 'mm**2', 0)}. La section mise en "
            "oeuvre ne couvre pas l'ELU: la dispense du §7.4.2 n'a pas de sens "
            "avant que la resistance soit acquise."
        )
    if b_eff_over_b_w is not None and b_eff_over_b_w < 1.0:
        raise InconsistentInput(
            "b_eff/b_w ne peut pas etre inferieur a 1,0"
        )

    fck_mpa = concrete.fck.to("MPa").magnitude
    if fck_mpa > _FCK_MAX_MPA:
        raise OutOfValidationDomain(
            "high_strength_concrete",
            f"beton {concrete.name} (fck = {fck_mpa:g} MPa) au-dela de C50/60. "
            "Les expressions (7.16a) et (7.16b) n'ont pas ete validees dans ce "
            "domaine par ce moteur.",
            clause="EN 1992-1-1 §7.4.2(2)",
        )

    params.require(required_parameters())

    prov = dict(provenance or {})
    j = Journal(
        title=(
            f"{element} — dispense du calcul de la fleche, rapport portee/"
            f"hauteur (EN 1992-1-1 §7.4.2) — {system.label}"
        )
    )

    A_comp = A_s_comp if A_s_comp is not None else Q_(0.0, "mm**2")
    require_dimension(A_comp, "[length] ** 2", "A_s_comp")

    # --- inputs -------------------------------------------------------------
    j.input("b", "Largeur de la section", section.b,
            prov.get("b", Provenance.user("saisie utilisateur")), display_unit="mm")
    j.input("d", "Hauteur utile", section.d,
            prov.get("d", Provenance.user("saisie utilisateur")), display_unit="mm")
    j.input("l_eff", "Portee utile", l_eff.to("mm"),
            prov.get("l_eff", Provenance.user("portee utile §5.3.2.2")),
            clause=EC2("§5.3.2.2"), display_unit="mm")
    j.input("A_s_req", "Section d'acier tendu requise par l'ELU",
            A_s_required.to("mm**2"),
            Provenance.user("resultat du calcul de flexion"),
            clause=EC2("§6.1"), display_unit="mm²")
    j.input("A_s_prov", "Section d'acier tendu mise en oeuvre",
            A_s_provided.to("mm**2"),
            Provenance.user("choix de ferraillage de l'ingenieur"),
            display_unit="mm²")
    if A_comp.magnitude > 0:
        j.input("A_s_comp", "Section d'acier comprime", A_comp.to("mm**2"),
                Provenance.user("choix de ferraillage de l'ingenieur"),
                display_unit="mm²")
    j.input("f_ck", f"Resistance caracteristique du beton ({concrete.name})",
            concrete.fck, Provenance.user(f"classe {concrete.name}"),
            clause=EC2("§3.1.2, Tab. 3.1"), display_unit="MPa")

    # --- national parameter --------------------------------------------------
    # Tab. 7.4N depend du systeme structural. Aucun scalaire ne convient: de la
    # console a la travee intermediaire, K va de 0,4 a 1,5.
    K = float(params.get(
        f"{EC2_11}:K_span_depth", j, condition=system.value
    ).magnitude)

    # --- reinforcement ratios -------------------------------------------------
    bd = (section.b * section.d).to("mm**2")
    rho = float((A_s_provided / bd).to("dimensionless").magnitude)
    rho_comp = float((A_comp / bd).to("dimensionless").magnitude)
    rho_0 = 1e-3 * math.sqrt(fck_mpa)

    j.step("rho_0", "Taux d'armature de reference",
           Q_(rho_0, "dimensionless"), EC2("§7.4.2(2)"),
           latex=r"\rho_0 = 10^{-3}\sqrt{f_{ck}}",
           numeric=f"1e-3 · √{fck_mpa:g}", depends_on=("f_ck",))
    j.step("rho", "Taux d'armature tendue mise en oeuvre",
           Q_(rho, "dimensionless"), EC2("§7.4.2(2)"),
           latex=r"\rho = \frac{A_{s,prov}}{b\,d}",
           numeric=(
               f"{fmt(A_s_provided, 'mm**2', 0)} / "
               f"({fmt(section.b, 'mm', 0)} · {fmt(section.d, 'mm', 0)})"
           ),
           depends_on=("A_s_prov", "b", "d"))

    # --- basic ratio, (7.16a) or (7.16b) --------------------------------------
    sq = math.sqrt(fck_mpa)
    heavily = rho > rho_0
    if not heavily:
        basic = K * (
            11.0
            + 1.5 * sq * rho_0 / rho
            + 3.2 * sq * (rho_0 / rho - 1.0) ** 1.5
        )
        j.step("l_sur_d_base", "Rapport portee/hauteur de base — faiblement arme",
               Q_(basic, "dimensionless"), EC2("§7.4.2(2)", "(7.16a)"),
               latex=(
                   r"\frac{l}{d} = K\left[11 + 1{,}5\sqrt{f_{ck}}\frac{\rho_0}{\rho}"
                   r" + 3{,}2\sqrt{f_{ck}}\left(\frac{\rho_0}{\rho}-1\right)^{3/2}"
                   r"\right]"
               ),
               numeric=(
                   f"{fmt(K)} · [11 + 1,5·√{fck_mpa:g}·{rho_0/rho:.4f} + "
                   f"3,2·√{fck_mpa:g}·({rho_0/rho:.4f}−1)^1,5]"
               ),
               depends_on=("rho", "rho_0", f"{EC2_11}:K_span_depth"))
    else:
        # (7.16b): rho' n'apparait qu'ici, et rho - rho' au denominateur.
        denom = rho - rho_comp
        if denom <= 0.0:
            raise InconsistentInput(
                f"rho' = {rho_comp:.5f} n'est pas inferieur a rho = {rho:.5f}. "
                "La formule (7.16b) divise par (rho − rho'): plus d'acier "
                "comprime que d'acier tendu sort du domaine de cette expression."
            )
        basic = K * (
            11.0
            + 1.5 * sq * rho_0 / denom
            + sq * math.sqrt(rho_comp / rho_0) / 12.0
        )
        j.step("l_sur_d_base", "Rapport portee/hauteur de base — fortement arme",
               Q_(basic, "dimensionless"), EC2("§7.4.2(2)", "(7.16b)"),
               latex=(
                   r"\frac{l}{d} = K\left[11 + 1{,}5\sqrt{f_{ck}}"
                   r"\frac{\rho_0}{\rho-\rho'} + \frac{1}{12}\sqrt{f_{ck}}"
                   r"\sqrt{\frac{\rho'}{\rho_0}}\right]"
               ),
               numeric=(
                   f"{fmt(K)} · [11 + 1,5·√{fck_mpa:g}·{rho_0/denom:.4f} + "
                   f"√{fck_mpa:g}·√({rho_comp:.5f}/{rho_0:.5f})/12]"
               ),
               depends_on=("rho", "rho_0", f"{EC2_11}:K_span_depth"))

    # --- §7.4.2(2) modifying factors ------------------------------------------
    # Facteur de contrainte: 310/sigma_s, approche par 500/(f_yk A_req/A_prov).
    # Le §7.4.2(2) le plafonne a 1,5.
    ratio_areas = float((A_s_provided / A_s_required).to("dimensionless").magnitude)
    fyk_mpa = steel.fyk.to("MPa").magnitude
    stress_factor = min(500.0 / (fyk_mpa / ratio_areas), _STRESS_FACTOR_CAP)
    j.step("facteur_contrainte", "Facteur de niveau de contrainte de l'acier",
           Q_(stress_factor, "dimensionless"), EC2("§7.4.2(2)"),
           latex=r"\frac{310}{\sigma_s} \approx \frac{500}{f_{yk}\,A_{s,req}/A_{s,prov}} \le 1{,}5",
           numeric=(
               f"min(500 / ({fyk_mpa:g} · {1.0/ratio_areas:.4f}) ; "
               f"{_STRESS_FACTOR_CAP}) — A_prov/A_req = {ratio_areas:.4f}"
           ),
           depends_on=("A_s_req", "A_s_prov"))

    flange_factor = 1.0
    if b_eff_over_b_w is not None and b_eff_over_b_w > _FLANGE_THRESHOLD:
        flange_factor = _FLANGE_FACTOR
    j.step("facteur_table", "Facteur de section en T",
           Q_(flange_factor, "dimensionless"), EC2("§7.4.2(2)"),
           latex=r"0{,}8 \text{ si } b_{eff}/b_w > 3",
           numeric=(
               "section rectangulaire declaree" if b_eff_over_b_w is None
               else f"b_eff/b_w = {b_eff_over_b_w:g}"
           ),
           depends_on=())

    l_eff_m = float(l_eff.to("m").magnitude)
    threshold = system.long_span_threshold_m
    long_span_factor = 1.0
    if supports_brittle_partitions and l_eff_m > threshold:
        long_span_factor = threshold / l_eff_m
    j.step("facteur_portee", "Facteur de grande portee (cloisons fragiles)",
           Q_(long_span_factor, "dimensionless"), EC2("§7.4.2(2)"),
           latex=rf"\frac{{{threshold:g}}}{{l_{{eff}}}} \text{{ si }} l_{{eff}} > {threshold:g}\,\mathrm{{m}}",
           numeric=(
               f"cloisons fragiles: {'oui' if supports_brittle_partitions else 'NON declarees'} ; "
               f"l_eff = {l_eff_m:.3f} m, seuil {threshold:g} m"
           ),
           depends_on=("l_eff",))

    limit = basic * stress_factor * flange_factor * long_span_factor
    j.step("l_sur_d_limite", "Rapport portee/hauteur limite",
           Q_(limit, "dimensionless"), EC2("§7.4.2(2)"),
           latex=r"\left(\frac{l}{d}\right)_{lim} = \frac{l}{d}\Big|_{base} \cdot f_\sigma \cdot f_T \cdot f_l",
           numeric=(
               f"{basic:.4f} · {stress_factor:.4f} · {flange_factor:.4f} · "
               f"{long_span_factor:.4f}"
           ),
           depends_on=("l_sur_d_base", "facteur_contrainte", "facteur_table",
                       "facteur_portee"))

    actual = float((l_eff / section.d).to("dimensionless").magnitude)
    j.step("l_sur_d_reel", "Rapport portee/hauteur reel",
           Q_(actual, "dimensionless"), EC2("§7.4.2(1)"),
           latex=r"\frac{l_{eff}}{d}",
           numeric=f"{fmt(l_eff, 'mm', 0)} / {fmt(section.d, 'mm', 0)}",
           depends_on=("l_eff", "d"))

    # --- the check ------------------------------------------------------------
    report = VerificationReport(element=element)
    exempt = actual <= limit
    report.add(Check.from_ratio(
        "ELS — dispense du calcul de la fleche (rapport l/d)",
        Q_(actual, "dimensionless"), Q_(limit, "dimensionless"),
        EC2("§7.4.2(2)", "(7.16a)-(7.16b)"),
        detail=(
            None if exempt else
            "Le critere forfaitaire ne dispense pas du calcul. Ce n'est PAS "
            "une insuffisance demontree de la poutre: la fleche reelle n'a pas "
            "ete calculee."
        ),
        remedy=(
            "Calculer la fleche selon le §7.4.3 — module non disponible dans "
            "cette version — ou augmenter la hauteur utile, la section d'acier "
            "tendu, ou la classe de beton."
        ),
    ))

    return SpanDepthCheck(
        element=element,
        system=system,
        K=K,
        rho_0=rho_0,
        rho=rho,
        rho_comp=rho_comp,
        basic_ratio=basic,
        heavily_reinforced=heavily,
        stress_factor=stress_factor,
        flange_factor=flange_factor,
        long_span_factor=long_span_factor,
        limit_ratio=limit,
        actual_ratio=actual,
        l_eff=l_eff.to("mm"),
        report=report,
        journal=j,
        ndp_summary=params.summary(),
    )
