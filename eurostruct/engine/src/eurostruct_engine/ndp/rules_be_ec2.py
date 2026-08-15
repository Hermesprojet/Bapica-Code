"""Belgian EC2 rules, transcribed from the documents on 2026-08-15.

Every rule below carries its full chain:

    texte de base  →  corrigenda  →  amendement  →  annexe belge  →  regle  →  test

Nothing here was written from memory. Where a layer changed nothing, that is
recorded too — « AC:2010 ne modifie pas 9.5N » is a verified fact that cost
work to establish, and a reader must be able to tell a checked layer from an
unchecked one.

Two extractions needed the PDF's geometry because the text layer was not
enough, and both are noted on the rule concerned: the radical of 9.5N is drawn
as vectors rather than written as a character, and 6.6N extracts as "0,61-"
until the bracket glyph's position shows it is 0,6[1 − …].

Pagination
----------
``page_printed`` is the folio an engineer cites; ``page_pdf`` is the index a
script opens. They differ by the covers — for the ANB, ``folio = pdf − 2`` —
and confusing them already produced one wrong reference in the dataset.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from ..units import Q_, Quantity
from .model import ValidationStatus, ValueProvenance
from .rules import (
    OutsideValidityDomain,
    Branch,
    ConditionalRule,
    DomainBound,
    ExpressionSource,
    FormulaRule,
    InputSpec,
    NormativeAuthority,
    NormativeFunction,
    RuleKind,
    implementation,
    register,
)

__all__ = [
    "NU_STRENGTH_REDUCTION",
    "ALPHA_CW",
    "RHO_W_MIN",
    "S_L_MAX",
    "S_T_MAX",
    "COT_THETA_MAX",
]

# --- les trois documents de la pile, une fois -------------------------------
_BASE_DOC = "30be1270c64081f9c184af8eab380487e9fc43eb36410648c866840014a4e1c7"
_A1_DOC = "938d6d968a2beedbd0d1909e378782c5787f6b1dc7398829ca24afb822fb9735"
_ANB_DOC = "3a19536221aef69b16435b88bc05d7aee05cebe823e98cb292e49e48fe68dcdd"

_BASE = "NBN EN 1992-1-1:2005 (+AC:2010) — EN 1992-1-1:2004 (F)"
_CORR = "EN 1992-1-1:2004/AC:2008 (+AC:2010)"
_A1 = "NBN EN 1992-1-1/A1 (2015) = EN 1992-1-1:2004/A1:2014"


def _corrigenda_untouched(clause: str, label: str) -> ExpressionSource:
    """Layer record for an expression the corrigenda leave alone.

    Established by enumerating the 120 numbered modifications of pages 256-279
    and checking that none targets this clause. For §6.2.2 and §6.2.3 the
    clause IS in the list, and the entries had to be read in full to see that
    they change other paragraphs — the negative result is only as good as that
    reading, which is why the effect text says which paragraphs.
    """
    return ExpressionSource(
        reference=_CORR, layer="corrigendum", clause=clause,
        expression_label=label,
        effect="NON MODIFIEE — verifie sur les 120 modifications enumerees",
        page_pdf=256, doc_id_sha256=_BASE_DOC,
    )


def _a1_untouched(clause: str, label: str) -> ExpressionSource:
    """Layer record for an expression A1 leaves alone.

    A1 is nine pages and its table of contents enumerates seven modifications:
    avant-propos, §3.3.2, §3.3.4, §6.4.5, §11.6.4.2, §12.6.5.2, §H.1.2. The
    list is exhaustive by construction — an amendment states what it amends.
    """
    return ExpressionSource(
        reference=_A1, layer="amendement", clause=clause, expression_label=label,
        effect="NON MODIFIEE — les 7 modifications de l'A1 visent d'autres clauses",
        page_pdf=4, doc_id_sha256=_A1_DOC,
    )


# ---------------------------------------------------------------------------
# 1. nu_strength_reduction(f_ck) — Expression (6.6N)
# ---------------------------------------------------------------------------
NU_STRENGTH_REDUCTION = register(FormulaRule(
    rule_id="be.ec2.nu_strength_reduction",
    rule_type=RuleKind.FORMULA,
    description=(
        "Coefficient de reduction de la resistance du beton fissure a l'effort "
        "tranchant, nu = 0,6[1 - f_ck/250]"
    ),
    output_unit="dimensionless",
    inputs=(
        InputSpec("f_ck", "[pressure]",
                  "Resistance caracteristique en compression du beton", "MPa"),
    ),
    domain=(
        DomainBound(
            "f_ck", minimum=Q_(12.0, "MPa"), maximum=Q_(90.0, "MPa"),
            reason=(
                "Classes de resistance couvertes par l'EN 1992-1-1, Tableau 3.1 "
                "(C12/15 a C90/105)."
            ),
        ),
    ),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§6.2.2(6)",
            expression_label="(6.6N)",
            effect=(
                "TEXTE D'ORIGINE. « nu = 0,6[1 - f_ck/250] (f_ck en MPa) ». "
                "Reconstruite au caractere: le crochet ouvrant est a x=121,3, "
                "ENTRE le 0,6 (x=114,4) et le 1 (x=124,6) — c'est 0,6[1-...], "
                "et non 0,61 comme le rend l'extraction brute. Barre de "
                "fraction tracee x=138,5->156,5, 250 en dessous."
            ),
            page_pdf=102, doc_id_sha256=_BASE_DOC,
        ),
        _corrigenda_untouched("§6.2.2", "(6.6N)"),
        _a1_untouched("§6.2.2", "(6.6N)"),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§6.2.2(6)",
        quote="La valeur recommandee (formule 6.6N) est normative.",
        page_printed=15, page_pdf=17, doc_id_sha256=_ANB_DOC,
        effect="adopte l'expression telle quelle",
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.COMPOSED_NORMATIVE_RULE,
    tests=("test_T4_nu_decreases_with_concrete_strength",),
    notes=(
        "REMPLACE les deux scalaires nu1_coeff = 0,6 et nu1_fck_divisor = 250. "
        "Deux constantes independantes autorisaient des combinaisons qui "
        "n'existent dans aucun texte. "
        "QUESTION OUVERTE: l'ANB §6.2.3(3) NOTE 1 ecrit « Formule 6.6N-ANB », "
        "designation sans referent ni dans l'ANB ni dans la base; et l'EN "
        "§6.2.3(3) NOTE 2 offre une alternative (6.10.aN/bN) que l'ANB corrige "
        "sans supprimer. Aucune des deux ne change l'expression ci-dessus."
    ),
))


@implementation("be.ec2.nu_strength_reduction")
def _nu(f_ck: Quantity) -> Quantity:
    # « f_ck en MPa » est dans le texte: l'expression n'est pas homogene, le
    # 250 est un nombre de MPa. Convertir explicitement plutot que d'esperer
    # que l'appelant ait passe des MPa.
    fck = f_ck.to("MPa").magnitude
    return Q_(0.6 * (1.0 - fck / 250.0), "dimensionless")


# ---------------------------------------------------------------------------
# 2. alpha_cw(sigma_cp, f_cd) — Expressions (6.11.aN) a (6.11.cN)
# ---------------------------------------------------------------------------
_SELECTOR = register(FormulaRule(
    rule_id="be.ec2.sigma_cp_over_fcd",
    rule_type=RuleKind.FORMULA,
    description="Selecteur des branches de alpha_cw: sigma_cp / f_cd",
    output_unit="dimensionless",
    inputs=(
        InputSpec("sigma_cp", "[pressure]",
                  "Contrainte de compression moyenne due a l'effort normal", "MPa"),
        InputSpec("f_cd", "[pressure]", "Resistance de calcul en compression", "MPa"),
    ),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§6.2.3(3)",
            expression_label="(6.11.aN-cN)",
            effect="rapport servant de selecteur, lu dans les conditions imprimees",
            page_pdf=104, doc_id_sha256=_BASE_DOC,
        ),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§6.2.3(3)",
        quote="L'expression de alpha_cw recommandee (Formules 6.11aN a cN) est normative.",
        page_printed=15, page_pdf=17, doc_id_sha256=_ANB_DOC,
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.COMPOSED_NORMATIVE_RULE,
    tests=("test_T5_alpha_cw_branches_and_boundaries",),
))


@implementation("be.ec2.sigma_cp_over_fcd")
def _ratio(sigma_cp: Quantity, f_cd: Quantity) -> Quantity:
    return (sigma_cp / f_cd).to("dimensionless")


_ALPHA_CW_LINEAR = register(FormulaRule(
    rule_id="be.ec2.alpha_cw_linear",
    rule_type=RuleKind.FORMULA,
    description="Branche 6.11.aN: alpha_cw = 1 + sigma_cp/f_cd",
    output_unit="dimensionless",
    inputs=(InputSpec("x", "", "sigma_cp / f_cd"),),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§6.2.3(3)",
            expression_label="(6.11.aN)",
            effect="TEXTE D'ORIGINE: « (1 + sigma_cp/f_cd) »",
            page_pdf=104, doc_id_sha256=_BASE_DOC,
        ),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§6.2.3(3)", quote="(Formules 6.11aN a cN) est normative.",
        page_printed=15, page_pdf=17, doc_id_sha256=_ANB_DOC,
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.COMPOSED_NORMATIVE_RULE,
    tests=("test_T5_alpha_cw_branches_and_boundaries",),
))


@implementation("be.ec2.alpha_cw_linear")
def _acw_lin(x: Quantity) -> Quantity:
    return Q_(1.0 + float(x.magnitude), "dimensionless")


_ALPHA_CW_DECREASING = register(FormulaRule(
    rule_id="be.ec2.alpha_cw_decreasing",
    rule_type=RuleKind.FORMULA,
    description="Branche 6.11.cN: alpha_cw = 2,5 (1 - sigma_cp/f_cd)",
    output_unit="dimensionless",
    inputs=(InputSpec("x", "", "sigma_cp / f_cd"),),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§6.2.3(3)",
            expression_label="(6.11.cN)",
            effect="TEXTE D'ORIGINE: « 2,5 (1 - sigma_cp/f_cd) »",
            page_pdf=104, doc_id_sha256=_BASE_DOC,
        ),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§6.2.3(3)", quote="(Formules 6.11aN a cN) est normative.",
        page_printed=15, page_pdf=17, doc_id_sha256=_ANB_DOC,
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.COMPOSED_NORMATIVE_RULE,
    tests=("test_T5_alpha_cw_branches_and_boundaries",),
))


@implementation("be.ec2.alpha_cw_decreasing")
def _acw_dec(x: Quantity) -> Quantity:
    return Q_(2.5 * (1.0 - float(x.magnitude)), "dimensionless")


ALPHA_CW = register(ConditionalRule(
    rule_id="be.ec2.alpha_cw",
    rule_type=RuleKind.CONDITIONAL_RULE,
    description=(
        "Coefficient tenant compte de l'etat de contrainte dans la membrure "
        "comprimee. QUATRE branches, dont « 1 » n'est que le cas non precontraint."
    ),
    output_unit="dimensionless",
    inputs=(
        InputSpec("sigma_cp", "[pressure]",
                  "Contrainte de compression moyenne, comptee positive", "MPa"),
        InputSpec("f_cd", "[pressure]", "Resistance de calcul en compression", "MPa"),
    ),
    selector_rule_id="be.ec2.sigma_cp_over_fcd",
    branches=(
        Branch(lower=0.0, upper=0.0, value_scalar=1.0,
               description="structures non precontraintes (sigma_cp = 0)"),
        Branch(lower=0.0, upper=0.25, lower_inclusive=False,
               value_rule_id="be.ec2.alpha_cw_linear",
               description="0 < sigma_cp <= 0,25 f_cd — (6.11.aN)"),
        Branch(lower=0.25, upper=0.5, lower_inclusive=False, value_scalar=1.25,
               description="0,25 f_cd < sigma_cp <= 0,5 f_cd — (6.11.bN)"),
        Branch(lower=0.5, upper=1.0, lower_inclusive=False, upper_inclusive=False,
               value_rule_id="be.ec2.alpha_cw_decreasing",
               description="0,5 f_cd < sigma_cp < 1,0 f_cd — (6.11.cN)"),
    ),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§6.2.3(3)",
            expression_label="(6.11.aN) a (6.11.cN)",
            effect=(
                "TEXTE D'ORIGINE, quatre branches. Indices reconstruits ligne "
                "par ligne: « cpcdcpcd », « cdcpcd », « cpcdcdcpcd »."
            ),
            page_pdf=104, doc_id_sha256=_BASE_DOC,
        ),
        ExpressionSource(
            reference=_CORR, layer="corrigendum", clause="§6.2.3",
            expression_label="(6.11.aN-cN)",
            effect=(
                "NON MODIFIEES. §6.2.3 EST dans la liste (entree n° 27) mais "
                "aux paragraphes (1), (5), (6) et (8) — pas au (3). La chaine "
                "« 6.11 » apparait 0 fois dans les 24 pages de corrigenda."
            ),
            page_pdf=260, doc_id_sha256=_BASE_DOC,
        ),
        _a1_untouched("§6.2.3", "(6.11.aN-cN)"),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§6.2.3(3) NOTE 3",
        quote=(
            "L'expression de alpha_cw recommandee (Formules 6.11aN a cN) est "
            "normative."
        ),
        page_printed=15, page_pdf=17, doc_id_sha256=_ANB_DOC,
        effect="adopte les quatre branches telles quelles",
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.COMPOSED_NORMATIVE_RULE,
    tests=("test_T5_alpha_cw_branches_and_boundaries",),
    notes=(
        "REMPLACE le scalaire alpha_cw = 1,0, qui n'etait que la branche non "
        "precontrainte, presentee sans sa condition."
    ),
))


# ---------------------------------------------------------------------------
# 3. rho_w_min(f_ck, f_ywk) — Expression (9.5N) MODIFIEE par l'ANB
# ---------------------------------------------------------------------------
RHO_W_MIN = register(FormulaRule(
    rule_id="be.ec2.rho_w_min",
    rule_type=RuleKind.FORMULA,
    description=(
        "Taux minimal d'armatures d'effort tranchant, VERSION BELGE: "
        "rho_w,min = 0,08 sqrt(f_ck) / f_ywk"
    ),
    output_unit="dimensionless",
    inputs=(
        InputSpec("f_ck", "[pressure]",
                  "Resistance caracteristique du beton", "MPa"),
        InputSpec("f_ywk", "[pressure]",
                  "Limite d'elasticite caracteristique de l'acier des ETRIERS",
                  "MPa"),
    ),
    domain=(
        DomainBound("f_ck", minimum=Q_(12.0, "MPa"), maximum=Q_(90.0, "MPa"),
                    reason="Classes de l'EN 1992-1-1, Tableau 3.1."),
        DomainBound("f_ywk", minimum=Q_(1.0, "MPa"),
                    reason="Une limite d'elasticite nulle n'a pas de sens."),
    ),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§9.2.2(5)",
            expression_label="(9.5N)",
            effect=(
                "TEXTE D'ORIGINE: « rho_w,min = (0,08 sqrt(f_ck))/f_yk ». Le "
                "RADICAL est trace en vecteurs, pas ecrit en caracteres: "
                "quatre segments a x=130,3->150,4, dont la barre horizontale "
                "x=137,2->150,4 qui couvre exactement le f (x=137,6) et son "
                "indice ck. Le radical porte donc sur f_ck seul."
            ),
            page_pdf=179, doc_id_sha256=_BASE_DOC,
        ),
        ExpressionSource(
            reference=_CORR, layer="corrigendum", clause="§9.2.2",
            expression_label="(9.5N)",
            effect=(
                "NON MODIFIEE. §9.2.2 est ABSENT des 120 entrees (seuls "
                "§9.2.1.4 et §9.2.4 y figurent). « 9.5N »: 0 occurrence."
            ),
            page_pdf=256, doc_id_sha256=_BASE_DOC,
        ),
        _a1_untouched("§9.2.2", "(9.5N)"),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§9.2.2(5)",
        quote=(
            "La valeur de rho_w,min recommandee (Formule 9.5N) est normative. "
            "Dans la formule 9.5N, lire f_ywk a la place de f_yk, exprime en MPa."
        ),
        page_printed=20, page_pdf=22, doc_id_sha256=_ANB_DOC,
        effect=(
            "MODIFIE L'EXPRESSION: substitue f_ywk (acier des etriers) a f_yk "
            "(acier longitudinal). La regle applicable n'existe donc dans "
            "AUCUN des deux documents pris seul."
        ),
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.COMPOSED_NORMATIVE_RULE,
    tests=("test_T6_rho_w_min_uses_the_stirrup_steel",),
    notes=(
        "Corroboration independante de la substitution: l'ANB p.6 INTRODUIT "
        "les symboles f_ywk et f_ywd, « acier des etriers », avant de s'en "
        "servir. Ce n'est pas une coquille. "
        "Le scalaire rho_w_min_coeff = 0,08 stocke seul perdait integralement "
        "cette modification."
    ),
))


@implementation("be.ec2.rho_w_min")
def _rho_w_min(f_ck: Quantity, f_ywk: Quantity) -> Quantity:
    # « exprime en MPa » figure dans l'ANB: l'expression n'est pas homogene
    # (sqrt(MPa)/MPa n'est pas sans dimension), le resultat n'a de sens que si
    # les deux grandeurs sont en MPa. La conversion est explicite pour cette
    # raison, et le resultat est declare sans dimension a la main.
    return Q_(
        0.08 * math.sqrt(f_ck.to("MPa").magnitude) / f_ywk.to("MPa").magnitude,
        "dimensionless",
    )


# ---------------------------------------------------------------------------
# 4. s_l_max(d, alpha) — Expression (9.6N)
# ---------------------------------------------------------------------------
S_L_MAX = register(FormulaRule(
    rule_id="be.ec2.s_l_max",
    rule_type=RuleKind.FORMULA,
    description=(
        "Espacement longitudinal maximal entre cours d'armatures d'effort "
        "tranchant: s_l,max = 0,75 d (1 + cot alpha)"
    ),
    output_unit="mm",
    inputs=(
        InputSpec("d", "[length]", "Hauteur utile", "mm"),
        InputSpec("alpha", "",
                  "Inclinaison des armatures d'effort tranchant sur l'axe "
                  "longitudinal (90 deg pour des cadres droits)", "deg"),
    ),
    domain=(
        DomainBound("d", minimum=Q_(1.0, "mm"),
                    reason="Une hauteur utile nulle n'a pas de sens."),
        DomainBound(
            "alpha", minimum=Q_(45.0, "degree"), maximum=Q_(90.0, "degree"),
            reason=(
                "EN 1992-1-1 §9.2.2(1): l'angle entre armatures d'effort "
                "tranchant et axe longitudinal est compris entre 45 et 90 deg."
            ),
        ),
    ),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§9.2.2(6)",
            expression_label="(9.6N)",
            effect="TEXTE D'ORIGINE: « s_l,max = 0,75d (1 + cot alpha) »",
            page_pdf=179, doc_id_sha256=_BASE_DOC,
        ),
        ExpressionSource(
            reference=_CORR, layer="corrigendum", clause="§9.2.2",
            expression_label="(9.6N)",
            effect=(
                "NON MODIFIEE. §9.2.2 absent des 120 entrees. ATTENTION a "
                "l'homonymie: les 2 occurrences de « 9.6N » dans les "
                "corrigenda sont des « TABLEAU 9.6N », objet different de "
                "l'EXPRESSION (9.6N). Une recherche par chaine les melange."
            ),
            page_pdf=267, doc_id_sha256=_BASE_DOC,
        ),
        _a1_untouched("§9.2.2", "(9.6N)"),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§9.2.2(6)",
        quote="La valeur de s_l,max recommandee (Formule 9.6N) est normative.",
        page_printed=20, page_pdf=22, doc_id_sha256=_ANB_DOC,
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.COMPOSED_NORMATIVE_RULE,
    tests=("test_T7_s_l_max_vertical_stirrups_and_monotonicity",),
    notes=(
        "Le scalaire s_l_max_coeff = 0,75 seul ne disait pas quoi multiplier, "
        "et perdait le facteur (1 + cot alpha). Pour des cadres droits "
        "alpha = 90 deg, cot alpha = 0 et le facteur vaut 1 — c'est pourquoi "
        "le code precedent donnait le bon resultat dans ce seul cas."
    ),
))


@implementation("be.ec2.s_l_max")
def _s_l_max(d: Quantity, alpha: Quantity) -> Quantity:
    a = alpha.to("radian").magnitude if hasattr(alpha, "to") else float(alpha)
    return (0.75 * d * (1.0 + 1.0 / math.tan(a))).to("mm")


# ---------------------------------------------------------------------------
# 5. s_t_max(d) — Expression (9.8N)
# ---------------------------------------------------------------------------
S_T_MAX = register(FormulaRule(
    rule_id="be.ec2.s_t_max",
    rule_type=RuleKind.FORMULA,
    description=(
        "Espacement transversal maximal des brins verticaux: "
        "s_t,max = min(0,75 d ; 600 mm)"
    ),
    output_unit="mm",
    inputs=(InputSpec("d", "[length]", "Hauteur utile", "mm"),),
    domain=(
        DomainBound("d", minimum=Q_(1.0, "mm"),
                    reason="Une hauteur utile nulle n'a pas de sens."),
    ),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§9.2.2(8)",
            expression_label="(9.8N)",
            effect="TEXTE D'ORIGINE: « s_t,max = 0,75d <= 600 mm »",
            page_pdf=179, doc_id_sha256=_BASE_DOC,
        ),
        ExpressionSource(
            reference=_CORR, layer="corrigendum", clause="§9.2.2",
            expression_label="(9.8N)",
            effect="NON MODIFIEE. §9.2.2 absent; « 9.8N »: 0 occurrence.",
            page_pdf=256, doc_id_sha256=_BASE_DOC,
        ),
        _a1_untouched("§9.2.2", "(9.8N)"),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§9.2.2(8)",
        quote="La valeur de s_t,max recommandee (Formule 9.8N) est normative.",
        page_printed=21, page_pdf=23, doc_id_sha256=_ANB_DOC,
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.COMPOSED_NORMATIVE_RULE,
    tests=("test_T8_s_t_max_cap_governs_for_deep_beams",),
    notes=(
        "Le scalaire s_t_max_coeff = 0,75 perdait le PLAFOND de 600 mm — et "
        "n'etait de toute facon consomme par aucun module."
    ),
))


@implementation("be.ec2.s_t_max")
def _s_t_max(d: Quantity) -> Quantity:
    return min((0.75 * d).to("mm"), Q_(600.0, "mm"))


# ---------------------------------------------------------------------------
# 6. cot_theta_max — regle PROPRE a la Belgique, §6.2.3(2)
# ---------------------------------------------------------------------------
COT_THETA_MAX = register(NormativeFunction(
    rule_id="be.ec2.cot_theta_max",
    rule_type=RuleKind.FUNCTION,
    description=(
        "Borne superieure de cot(theta), REGLE BELGE PROPRE: "
        "cot(theta)_max = (2 + k1 sigma_cp b_w d s / (A_sw z f_ywd)) <= 3"
    ),
    output_unit="dimensionless",
    inputs=(
        InputSpec("k_1", "", "Coefficient k1 de §6.2.2(1), valeur belge 0,15"),
        InputSpec("sigma_cp", "[pressure]",
                  "Contrainte de compression moyenne", "MPa"),
        InputSpec("b_w", "[length]", "Largeur d'ame", "mm"),
        InputSpec("d", "[length]", "Hauteur utile", "mm"),
        InputSpec("s", "[length]", "Espacement des cadres", "mm"),
        InputSpec("A_sw", "[length] ** 2", "Section d'un cours d'armatures", "mm**2"),
        InputSpec("z", "[length]", "Bras de levier", "mm"),
        InputSpec("f_ywd", "[pressure]",
                  "Limite d'elasticite de calcul des etriers", "MPa"),
        InputSpec("f_cd", "[pressure]",
                  "Resistance de calcul du beton, pour le domaine", "MPa"),
    ),
    domain=(
        DomainBound(
            "sigma_cp", maximum_of="f_cd", maximum_factor=0.2,
            reason=(
                "L'ANB imprime « ou sigma_cp <= 0,2 f_cd » sous la formule. "
                "Au-dela, l'annexe ne dit rien."
            ),
        ),
    ),
    expression_sources=(
        ExpressionSource(
            reference=_BASE, layer="base", clause="§6.2.3(2)",
            expression_label="(6.7N)",
            effect=(
                "REMPLACEE. L'EN recommande « 1 <= cot(theta) <= 2,5 »; la "
                "Belgique substitue sa propre borne superieure. Le texte de "
                "base n'est donc PAS la source de cette regle — il est ce "
                "qu'elle ecarte."
            ),
            page_pdf=104, doc_id_sha256=_BASE_DOC,
        ),
    ),
    normative_authority=NormativeAuthority(
        country_code="BE", reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§6.2.3(2)",
        quote=(
            "Les valeurs limites de cot(theta) sont : 1,0 <= cot(theta) <= "
            "cot(theta)_max ; cot(theta)_max = (2 + k1.sigma_cp.bw.d.s / "
            "(Asw.z.fywd)) <= 3 ou sigma_cp <= 0,2 f_cd"
        ),
        page_printed=15, page_pdf=17, doc_id_sha256=_ANB_DOC,
        effect=(
            "ECRIT SA PROPRE FORMULE. L'ANB ne renvoie a rien: aucun "
            "corrigendum ni amendement du texte de base ne peut l'atteindre."
        ),
    ),
    validation_status=ValidationStatus.PENDING_VERIFICATION,
    value_provenance=ValueProvenance.NATIONAL_ANNEX,
    evaluation_order=(
        "POINT FIXE MONOTONE BORNE, itere par solve_cot_theta(). "
        "La formule depend de A_sw et s, qui sont des RESULTATS du "
        "dimensionnement qu'elle contraint: la dependance est reelle et elle "
        "est resolue numeriquement, pas evitee. "
        "Domaine initial = celui de la regle, 1,0 <= cot(theta) <= 3, et NON "
        "un intervalle raccourci: brider a 2 serait sur-conservatif des qu'il "
        "y a precontrainte, puisque la regle autorise jusqu'a 3. "
        "Iteration: cot_0 = 1,0 (le plus defavorable), puis "
        "cot_{n+1} = min(cot_theta_max(A_sw/s(cot_n)), 3). Monotone "
        "croissante — un cot plus grand demande moins d'armatures, ce qui "
        "releve la borne — et majoree par 3, donc convergente. "
        "Convergence: |cot_{n+1} - cot_n| <= 1e-9. Maximum 50 iterations. "
        "Chaque iteration est journalisee. Non-convergence = REFUS explicite, "
        "jamais une valeur approchee ni une boucle silencieuse."
    ),
    tests=("test_T9_cot_theta_max_is_two_without_prestress",),
    notes=(
        "CONSEQUENCE MAJEURE: pour une poutre NON precontrainte, sigma_cp = 0 "
        "donc cot(theta)_max = 2, et non 2,5. La regle belge est PLUS SEVERE "
        "que la recommandation europeenne dans le cas le plus courant. Un "
        "repli sur 2,5 produirait des armatures d'effort tranchant "
        "INSUFFISANTES, sans rien signaler."
    ),
))


@implementation("be.ec2.cot_theta_max")
def _cot_theta_max(
    k_1: Quantity, sigma_cp: Quantity, b_w: Quantity, d: Quantity, s: Quantity,
    A_sw: Quantity, z: Quantity, f_ywd: Quantity, f_cd: Quantity,
) -> Quantity:
    term = (
        float(k_1.magnitude) * sigma_cp * b_w * d * s / (A_sw * z * f_ywd)
    ).to("dimensionless")
    return Q_(min(2.0 + float(term.magnitude), 3.0), "dimensionless")


# ---------------------------------------------------------------------------
# Resolution du point fixe de cot(theta)
# ---------------------------------------------------------------------------
_TOLERANCE = 1e-12
_MAX_ITERATIONS = 200
_COT_CAP = 3.0


class Termination(str, Enum):
    """Pourquoi la resolution s'est arretee. Jamais implicite."""

    #: Residu |c - F(c)| <= tolerance, VERIFIE a la sortie sur la valeur retenue.
    CONVERGED = "converged"
    #: Le plafond normatif 3 est lui-meme le point fixe: F(3) = 3.
    UPPER_BOUND = "upper_bound"
    #: Budget d'iterations epuise sans residu acceptable. AUCUNE valeur rendue.
    MAX_ITERATIONS = "max_iterations"
    #: Entrees hors du domaine de la regle. AUCUNE valeur rendue.
    INVALID_DOMAIN = "invalid_domain"


@dataclass(frozen=True, slots=True)
class CotThetaIteration:
    """Une iteration, telle qu'elle sera imprimee dans la note de calcul."""

    index: int
    previous: float
    computed: float
    residual: float
    Asw_over_s: Quantity


@dataclass(frozen=True, slots=True)
class CotThetaSolution:
    """Resultat: converge, plafonne, ou REFUSE — jamais approche.

    ``cot_theta`` ne vaut ``None`` que pour les deux terminaisons d'echec: une
    valeur presente a donc toujours passe la verification de residu.
    """

    termination: Termination
    cot_theta: float | None
    residual: float | None
    iterations: tuple[CotThetaIteration, ...]
    #: Pente A de la demonstration ci-dessous, conservee pour l'audit.
    slope_A: float | None = None
    refusal: str | None = None

    @property
    def accepted(self) -> bool:
        return self.termination in (Termination.CONVERGED, Termination.UPPER_BOUND)

    @property
    def journal(self) -> tuple[str, ...]:
        lines = [
            f"iter {i.index}: c = {i.previous:.9f} -> F(c) = {i.computed:.9f}"
            f" | residu {i.residual:.3e}"
            f" | A_sw/s = {i.Asw_over_s.to('mm**2/m').magnitude:.2f} mm2/m"
            for i in self.iterations
        ]
        if self.accepted:
            lines.append(
                f"{self.termination.value.upper()} en {len(self.iterations)}"
                f" iteration(s): cot(theta) = {self.cot_theta:.9f},"
                f" residu final {self.residual:.3e} <= {_TOLERANCE:.0e}"
            )
        else:
            lines.append(f"REFUS [{self.termination.value}]: {self.refusal}")
        return tuple(lines)


def fixed_point_closed_form(A: float) -> float:
    """Point fixe exact de ``F(c) = min(3 ; 2 + A c)``, demontre ci-dessous.

    Sert d'ORACLE INDEPENDANT dans les tests. Deux methodes distinctes qui
    s'accordent valent mieux qu'une methode qu'on croit juste: c'est la
    discipline des cas de reference du moteur, etablis par bissection quand la
    forme fermee existe, et inversement.
    """
    if A >= 1.0 / 3.0:
        return _COT_CAP
    return 2.0 / (1.0 - A)


def solve_cot_theta(
    *,
    V_Ed: Quantity,
    k_1: Quantity,
    sigma_cp: Quantity,
    b_w: Quantity,
    d: Quantity,
    z: Quantity,
    f_ywd: Quantity,
    f_cd: Quantity,
    s: Quantity,
    cot_theta_min: float = 1.0,
) -> CotThetaSolution:
    """Resoudre cot(theta) sous la borne belge de §6.2.3(2).

    Demonstration de la convergence
    --------------------------------
    Elle n'est pas invoquee, elle se calcule. En reportant
    ``A_sw/s = V_Ed/(z f_ywd c)`` dans la borne de l'ANB::

        cot_max = 2 + k1 sigma_cp b_w d s / (A_sw z f_ywd)
                = 2 + k1 sigma_cp b_w d s / ((V_Ed s/(z f_ywd c)) z f_ywd)
                = 2 + (k1 sigma_cp b_w d / V_Ed) . c

    ``s``, ``z`` et ``f_ywd`` se simplifient TOUS LES TROIS, et ``A_sw`` avec
    eux. L'application d'iteration est donc affine::

        F(c) = min(3 ; 2 + A c),   A = k1 sigma_cp b_w d / V_Ed >= 0

    F est croissante (A >= 0) et majoree par 3. Partant de
    ``c_0 = cot_theta_min`` avec ``F(c_0) >= 2 > c_0``, la suite est croissante
    et bornee: elle converge. Son point fixe vaut ``2/(1-A)`` si ``A < 1/3``,
    et ``3`` sinon — le plafond normatif devenant lui-meme point fixe des que
    ``2 + 3A >= 3``.

    Sans precontrainte ``A = 0``: F est constante egale a 2, atteinte des la
    premiere iteration, quel que soit le ferraillage.

    Ce que le solveur fait quand meme
    ----------------------------------
    La demonstration ne dispense pas de VERIFIER. Le residu
    ``|c - F(c)| <= tolerance`` est controle a la sortie SUR LA VALEUR
    RETENUE, independamment de ce que la boucle croit avoir fait; une
    terminaison qui ne le passe pas ne rend aucune valeur. La convergence est
    lineaire de rapport A et ralentit quand A approche 1/3, d'ou un budget de
    200 iterations.
    """
    if V_Ed.magnitude <= 0:
        return CotThetaSolution(
            Termination.INVALID_DOMAIN, None, None, (),
            refusal="V_Ed doit etre strictement positif pour dimensionner.",
        )

    A = float((k_1 * sigma_cp * b_w * d / V_Ed).to("dimensionless").magnitude)

    def F(c: float) -> tuple[float, Quantity]:
        asw_over_s = (V_Ed / (z * f_ywd * c)).to("mm**2/m")
        value = COT_THETA_MAX.evaluate(
            k_1=k_1, sigma_cp=sigma_cp, b_w=b_w, d=d, s=s,
            A_sw=(asw_over_s * s).to("mm**2"), z=z, f_ywd=f_ywd, f_cd=f_cd,
        )
        return float(value.magnitude), asw_over_s

    steps: list[CotThetaIteration] = []
    c = float(cot_theta_min)
    try:
        for index in range(1, _MAX_ITERATIONS + 1):
            nxt, asw_over_s = F(c)
            residual = abs(nxt - c)
            steps.append(CotThetaIteration(index, c, nxt, residual, asw_over_s))
            if residual <= _TOLERANCE:
                check, _ = F(nxt)
                final_residual = abs(nxt - check)
                if final_residual > _TOLERANCE:
                    return CotThetaSolution(
                        Termination.MAX_ITERATIONS, None, final_residual,
                        tuple(steps), slope_A=A,
                        refusal=(
                            f"residu de sortie {final_residual:.3e} > tolerance"
                            f" {_TOLERANCE:.0e} alors que la boucle s'estimait"
                            " convergee. Aucune valeur n'est retenue."
                        ),
                    )
                termination = (
                    Termination.UPPER_BOUND
                    if nxt >= _COT_CAP - _TOLERANCE
                    else Termination.CONVERGED
                )
                return CotThetaSolution(
                    termination, nxt, final_residual, tuple(steps), slope_A=A
                )
            c = nxt
    except OutsideValidityDomain as exc:
        return CotThetaSolution(
            Termination.INVALID_DOMAIN, None, None, tuple(steps), slope_A=A,
            refusal=str(exc),
        )

    return CotThetaSolution(
        Termination.MAX_ITERATIONS, None, steps[-1].residual, tuple(steps),
        slope_A=A,
        refusal=(
            f"cot(theta) n'a pas converge en {_MAX_ITERATIONS} iterations"
            f" (residu {steps[-1].residual:.3e} > {_TOLERANCE:.0e}). Aucune"
            " valeur n'est retenue: une valeur approchee serait un resultat que"
            " le moteur ne peut pas justifier. Le journal est joint pour que"
            " l'ingenieur tranche."
        ),
    )
