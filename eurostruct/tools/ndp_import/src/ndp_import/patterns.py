"""Where to look, in a National Annex, for each parameter.

Anchoring strategy, in order of reliability:

1. **Clause reference** — ``3.1.6(1)P`` reads the same in Brussels, Paris,
   Madrid and Berlin. It is the only anchor that survives translation, and it
   is what a National Annex is organised around.
2. **Symbol** — ``αcc``, ``γC``. Robust, but PDF text extraction mangles Greek
   letters often enough that it cannot be relied on alone.
3. **Wording** — last resort, per language, because it is the most brittle.

Everything here produces *candidates*. A pattern that matches the wrong clause
costs a reviewer thirty seconds; a pattern that silently invents a value would
cost far more, which is why no pattern ever supplies a default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

__all__ = ["ParameterPattern", "PATTERNS", "patterns_for", "parse_number", "NUMBER_RE"]

#: A number as written in a European standard: decimal comma or point.
#: ``1,0`` · ``0,0013`` · ``250`` · ``2,5``
NUMBER_RE: Final = re.compile(r"(?<![\w.,])([-+]?\d{1,6}(?:[.,]\d{1,6})?)(?![\w])")


def parse_number(token: str) -> float | None:
    """``"1,0"`` -> ``1.0``. Returns ``None`` rather than guessing.

    The decimal comma is the norm in the four target countries; a value read as
    ``1.0`` when the document says ``1,0`` would be the same number, but a
    thousands separator misread as a decimal would not, so anything ambiguous
    is refused.
    """
    t = token.strip()
    if t.count(",") > 1 or t.count(".") > 1:
        return None
    if "," in t and "." in t:            # e.g. "1.234,5" — ambiguous here
        return None
    try:
        return float(t.replace(",", "."))
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class ParameterPattern:
    """How to find one nationally determined parameter in a document."""

    parameter_name: str
    #: Clause references, without the section sign. Most reliable anchor.
    clause_refs: tuple[str, ...]
    #: Symbol spellings, including the ASCII fallbacks PDF extraction produces.
    symbols: tuple[str, ...] = ()
    unit: str = "dimensionless"
    #: Plausible range. A candidate outside it is still recorded — the reviewer
    #: decides — but its confidence drops, so it sinks in the queue.
    plausible: tuple[float, float] | None = None
    description: str = ""

    def clause_regex(self) -> re.Pattern[str]:
        alts = "|".join(re.escape(c) for c in self.clause_refs)
        return re.compile(rf"(?:§\s*)?({alts})")

    def symbol_regex(self) -> re.Pattern[str] | None:
        if not self.symbols:
            return None
        alts = "|".join(re.escape(s) for s in self.symbols)
        return re.compile(rf"({alts})", re.IGNORECASE)


#: EN 1992-1-1. Clause references are those of the base Eurocode, which the
#: National Annex quotes when it fixes the value.
PATTERNS: Final[tuple[ParameterPattern, ...]] = (
    ParameterPattern(
        "alpha_cc", ("3.1.6(1)P", "3.1.6(1)"),
        ("αcc", "acc", "alpha cc", "alphacc", "α cc"),
        plausible=(0.8, 1.0),
        description="Coefficient de longue duree, resistance en compression",
    ),
    ParameterPattern(
        "alpha_ct", ("3.1.6(2)P", "3.1.6(2)"),
        ("αct", "act", "alpha ct", "alphact"),
        plausible=(0.8, 1.0),
        description="Coefficient de longue duree, resistance en traction",
    ),
    ParameterPattern(
        "gamma_C_persistent", ("2.4.2.4(1)", "Tableau 2.1N", "Table 2.1N", "Tabelle 2.1N", "Tabla 2.1N"),
        ("γC", "gamma C", "gammaC", "γc"),
        plausible=(1.2, 1.6),
        description="Coefficient partiel du beton, situations durables/transitoires",
    ),
    ParameterPattern(
        "gamma_S_persistent", ("2.4.2.4(1)", "Tableau 2.1N", "Table 2.1N", "Tabelle 2.1N", "Tabla 2.1N"),
        ("γS", "gamma S", "gammaS", "γs"),
        plausible=(1.0, 1.3),
        description="Coefficient partiel de l'acier, situations durables/transitoires",
    ),
    ParameterPattern(
        "gamma_C_accidental", ("2.4.2.4(1)", "Tableau 2.1N", "Table 2.1N"),
        ("γC", "gamma C"),
        plausible=(1.0, 1.5),
        description="Coefficient partiel du beton, situations accidentelles",
    ),
    ParameterPattern(
        "gamma_S_accidental", ("2.4.2.4(1)", "Tableau 2.1N", "Table 2.1N"),
        ("γS", "gamma S"),
        plausible=(1.0, 1.2),
        description="Coefficient partiel de l'acier, situations accidentelles",
    ),
    ParameterPattern(
        "k1_redistribution", ("5.5(4)",), ("k1", "k 1"),
        plausible=(0.3, 0.6),
        description="Coefficient k1 bornant xu/d",
    ),
    ParameterPattern(
        "k2_redistribution", ("5.5(4)",), ("k2", "k 2"),
        plausible=(0.8, 1.6),
        description="Coefficient k2 bornant xu/d",
    ),
    ParameterPattern(
        "As_min_coeff", ("9.2.1.1(1)", "9.1N"), ("As,min", "As min"),
        plausible=(0.2, 0.35),
        description="Coefficient de As,min = 0,26 fctm/fyk bt d",
    ),
    ParameterPattern(
        "As_min_floor", ("9.2.1.1(1)", "9.1N"), ("As,min", "As min"),
        plausible=(0.0005, 0.005),
        description="Plancher de As,min = 0,0013 bt d",
    ),
    ParameterPattern(
        "As_max_ratio", ("9.2.1.1(3)",), ("As,max", "As max"),
        plausible=(0.02, 0.08),
        description="As,max = 0,04 Ac",
    ),
    ParameterPattern(
        "C_Rd_c_coeff", ("6.2.2(1)",), ("CRd,c", "CRdc", "C Rd,c"),
        plausible=(0.10, 0.25),
        description="Coefficient de C_Rd,c = 0,18/gamma_C",
    ),
    ParameterPattern(
        "v_min_coeff", ("6.2.2(1)", "6.3N"), ("vmin", "v min", "νmin"),
        plausible=(0.02, 0.06),
        description="Coefficient de v_min",
    ),
    ParameterPattern(
        "k1_shear", ("6.2.2(1)",), ("k1", "k 1"),
        plausible=(0.05, 0.3),
        description="Coefficient k1 de la contribution de l'effort normal",
    ),
    ParameterPattern(
        "nu1_coeff", ("6.2.2(6)", "6.6N"), ("ν", "nu", "ν1", "nu1"),
        plausible=(0.4, 0.8),
        description="Coefficient nu de la resistance du beton fissure",
    ),
    ParameterPattern(
        "nu1_fck_divisor", ("6.2.2(6)", "6.6N"), ("ν", "nu"),
        unit="MPa", plausible=(200.0, 300.0),
        description="Diviseur de fck dans nu = 0,6 [1 - fck/250]",
    ),
    ParameterPattern(
        "alpha_cw", ("6.2.3(3)",), ("αcw", "alpha cw", "acw"),
        plausible=(1.0, 1.25),
        description="Coefficient alpha_cw",
    ),
    ParameterPattern(
        "cot_theta_min", ("6.2.3(2)", "6.7N"), ("cotθ", "cot θ", "cot theta"),
        plausible=(0.5, 1.5),
        description="Borne inferieure de cot(theta)",
    ),
    ParameterPattern(
        "cot_theta_max", ("6.2.3(2)", "6.7N"), ("cotθ", "cot θ", "cot theta"),
        plausible=(1.5, 3.0),
        description="Borne superieure de cot(theta)",
    ),
    ParameterPattern(
        "rho_w_min_coeff", ("9.2.2(5)", "9.5N"), ("ρw,min", "rho w min", "ρw"),
        plausible=(0.04, 0.15),
        description="Coefficient de rho_w,min",
    ),
    ParameterPattern(
        "s_l_max_coeff", ("9.2.2(6)", "9.6N"), ("sl,max", "sl max"),
        plausible=(0.5, 1.0),
        description="Coefficient de s_l,max",
    ),
    ParameterPattern(
        "s_t_max_coeff", ("9.2.2(8)", "9.8N"), ("st,max", "st max"),
        plausible=(0.5, 1.0),
        description="Coefficient de s_t,max",
    ),

    # -----------------------------------------------------------------------
    # EN 1993-1-1 — acier, regles generales
    #
    # NBN EN 1993-1-1 ANB renvoie a la valeur recommandee pour la plupart de
    # ces parametres sans l'imprimer. Les motifs existent quand meme: sans
    # eux, un depouillement ne les chercherait pas, et l'absence passerait
    # pour un silence de l'annexe.
    # -----------------------------------------------------------------------
    ParameterPattern(
        "gamma_M0", ("6.1(1)", "6.1(1)B"), ("γM0", "gamma M0", "gammaM0", "γ M0"),
        plausible=(1.0, 1.2),
        description="Coefficient partiel de resistance des sections",
    ),
    ParameterPattern(
        "gamma_M1", ("6.1(1)", "6.1(1)B"), ("γM1", "gamma M1", "gammaM1", "γ M1"),
        plausible=(1.0, 1.2),
        description="Coefficient partiel de resistance aux instabilites",
    ),
    ParameterPattern(
        "gamma_M2", ("6.1(1)", "6.1(1)B"), ("γM2", "gamma M2", "gammaM2", "γ M2"),
        plausible=(1.1, 1.5),
        description="Coefficient partiel de resistance a la rupture des sections tendues",
    ),
    ParameterPattern(
        "alpha_cr_min_plastique", ("5.2.1(3)",), ("αcr", "alpha cr", "α cr"),
        plausible=(3.0, 20.0),
        description="Borne inferieure de alpha_cr pour l'analyse plastique",
    ),
    ParameterPattern(
        "k_imperfection_element", ("5.3.4(3)",), ("k =", "facteur k"),
        plausible=(0.1, 1.0),
        description="Facteur k des imperfections d'elements",
    ),
    ParameterPattern(
        "lambda_LT_0", ("6.3.2.3(1)",), ("λLT,0", "lambda LT,0", "λ LT,0"),
        plausible=(0.1, 0.6),
        description="Elancement de palier du deversement (profils lamines)",
    ),
    ParameterPattern(
        "beta_deversement", ("6.3.2.3(1)",), ("β", "beta"),
        plausible=(0.5, 1.0),
        description="Facteur beta des courbes de deversement",
    ),
    ParameterPattern(
        "alpha_LT", ("6.3.2.2(2)",), ("αLT", "alpha LT", "α LT"),
        plausible=(0.1, 1.0),
        description="Facteur d'imperfection pour le deversement",
    ),
    ParameterPattern(
        "lambda_c_0", ("6.3.2.4(1)", "6.3.2.4(1)B"), ("λc,0", "lambda c,0", "λ c,0"),
        plausible=(0.1, 1.0),
        description="Elancement limite, methode simplifiee des poutres maintenues",
    ),
    ParameterPattern(
        "k_fl", ("6.3.2.4(2)", "6.3.2.4(2)B"), ("kfl", "k fl"),
        plausible=(1.0, 1.5),
        description="Facteur k_fl, methode simplifiee des poutres maintenues",
    ),
    ParameterPattern(
        "temperature_service_min", ("3.2.3(1)",),
        ("température de service", "temperature de service"),
        plausible=(-60.0, 20.0), unit="degC",
        description="Temperature minimale de service pour la tenacite a la rupture",
    ),

    # -----------------------------------------------------------------------
    # EN 1993-1-2 — acier, calcul au feu
    # -----------------------------------------------------------------------
    ParameterPattern(
        "gamma_M_fi", ("2.3(1)", "2.3(2)"),
        ("γM,fi", "gamma M,fi", "γ M,fi", "gammaM,fi"),
        plausible=(0.9, 1.3),
        description="Coefficient partiel des materiaux en situation d'incendie",
    ),
    ParameterPattern(
        "theta_crit_classe_4", ("4.2.3.6(1)",), ("θcrit", "theta crit", "θ crit"),
        plausible=(300.0, 700.0), unit="degC",
        description="Temperature critique des sections de Classe 4",
    ),
    ParameterPattern(
        "theta_crit_poutre_isostatique", ("4.2.4(2)",),
        ("θcrit", "theta crit", "θ crit"),
        plausible=(400.0, 700.0), unit="degC",
        description="Temperature critique des poutres isostatiques et tirants",
    ),
    ParameterPattern(
        "theta_crit_poutre_hyperstatique", ("4.2.4(2)",),
        ("θcrit", "theta crit", "θ crit"),
        plausible=(400.0, 700.0), unit="degC",
        description="Temperature critique des poutres hyperstatiques",
    ),
    ParameterPattern(
        "theta_crit_comprime", ("4.2.4(2)",), ("θcrit", "theta crit", "θ crit"),
        plausible=(400.0, 700.0), unit="degC",
        description="Temperature critique des elements comprimes et flechis-comprimes",
    ),
)


def patterns_for(names: tuple[str, ...] | None = None) -> tuple[ParameterPattern, ...]:
    """The patterns for *names*, or all of them.

    :raises KeyError: for a name with no pattern — better a loud gap than a
        parameter silently never searched for.
    """
    if names is None:
        return PATTERNS
    index = {p.parameter_name: p for p in PATTERNS}
    missing = [n for n in names if n not in index]
    if missing:
        raise KeyError(
            "aucun motif de recherche pour: " + ", ".join(sorted(missing))
            + ". Ajouter le motif dans patterns.py avant de depouiller ce "
            "document, sinon ces parametres ne seront jamais cherches."
        )
    return tuple(index[n] for n in names)
