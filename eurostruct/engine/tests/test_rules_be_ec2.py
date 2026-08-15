"""Les six regles belges transcrites le 15/08, et le modele qui les porte.

Les tests T4 a T9 sont ceux specifies dans BE_EC2_NORMATIVE_STACK.md au moment
ou les formules ont ete etablies. Ils portent le nom annonce, et chaque regle
declare le nom du test qui l'exerce — un lien verifie ci-dessous, pour qu'une
regle ne puisse pas se dire testee sans l'etre.
"""

from __future__ import annotations

import math

import pytest

from eurostruct_engine.exceptions import OutOfValidationDomain, UnitError
from eurostruct_engine.ndp import rules_be_ec2 as R
from eurostruct_engine.ndp.model import ValidationStatus, ValueProvenance
from eurostruct_engine.ndp.rules import RuleKind, all_rules, check_registry
from eurostruct_engine.units import Q_


# ---------------------------------------------------------------------------
# Le modele lui-meme
# ---------------------------------------------------------------------------
def test_declarations_and_implementations_have_not_drifted() -> None:
    """Tout le dispositif « pas d'eval » repose sur cette correspondance.

    Les metadonnees d'une regle sont des donnees; sa mathematique est du Python
    ecrit a la main et enregistre sous un rule_id. Rien ne les tient ensemble
    sinon ce controle: une regle declaree sans mathematique, ou une
    mathematique sans regle, est une derive silencieuse.
    """
    check_registry()


def test_no_rule_is_executed_from_data() -> None:
    """Aucune expression n'est stockee sous forme de chaine a executer.

    Le controle est grossier — il cherche eval/exec/compile dans le module de
    regles — et c'est voulu: la propriete a garantir est architecturale, et
    elle doit rester vraie meme si personne ne relit le fichier.
    """
    import inspect

    from eurostruct_engine.ndp import rules

    for module in (rules, R):
        source = inspect.getsource(module)
        for interdit in ("eval(", "exec(", "compile("):
            assert interdit not in source, f"{module.__name__}: {interdit} interdit"


def test_a_formula_refuses_a_variable_with_the_wrong_unit() -> None:
    """Une formule ne recoit jamais silencieusement une mauvaise unite.

    Deux cas, et le second est le plus insidieux: un nombre nu passe la ou une
    contrainte est attendue « marche » dans la plupart des langages et produit
    un resultat plausible.
    """
    with pytest.raises(UnitError):
        R.NU_STRENGTH_REDUCTION.evaluate(f_ck=Q_(300, "mm"))     # longueur
    with pytest.raises(UnitError):
        R.NU_STRENGTH_REDUCTION.evaluate(f_ck=30)                # nombre nu


def test_a_rule_refuses_an_undeclared_variable() -> None:
    """Une variable non declaree ne peut pas etre utilisee en douce."""
    with pytest.raises(TypeError, match="inconnue"):
        R.S_T_MAX.evaluate(d=Q_(450, "mm"), b_w=Q_(300, "mm"))
    with pytest.raises(TypeError, match="manquante"):
        R.S_T_MAX.evaluate()


def test_every_rule_carries_its_full_provenance_chain() -> None:
    """base -> corrigendum -> A1 -> ANB -> regle -> test, sur chaque regle.

    C'est la chaine demandee, et elle doit etre lisible sans ouvrir le code:
    une regle qui ne citerait que l'Eurocode appliquerait une recommandation
    europeenne, une regle qui ne citerait que l'annexe ne pourrait pas montrer
    sa propre formule.
    """
    for rule in all_rules():
        chaine = rule.provenance_chain
        assert rule.expression_sources, f"{rule.rule_id}: sans source d'expression"
        assert rule.normative_authority.quote.strip(), (
            f"{rule.rule_id}: autorite sans citation"
        )
        assert rule.normative_authority.country_code == "BE"
        # L'autorite nationale est l'avant-derniere ligne, avant la regle.
        assert any("ANB" in ligne for ligne in chaine)
        assert chaine[-2] == f"regle moteur: {rule.rule_id}"
        assert chaine[-1].startswith("tests: ")


def test_a_rule_naming_a_test_is_a_rule_that_test_exercises() -> None:
    """Une regle ne peut pas se declarer testee sans l'etre.

    Le champ ``tests`` serait decoratif si rien ne verifiait que les noms
    qu'il porte existent vraiment dans ce fichier.
    """
    import inspect

    ici = inspect.getsource(__import__(__name__, fromlist=["_"]))
    for rule in all_rules():
        assert rule.tests, f"{rule.rule_id}: aucun test declare"
        for nom in rule.tests:
            assert f"def {nom}" in ici, (
                f"{rule.rule_id} declare le test '{nom}', qui n'existe pas"
            )


def test_nothing_is_confirmed_and_nothing_passes_strict_mode() -> None:
    """Aucune regle transcrite n'est validee: la relecture humaine reste due."""
    for rule in all_rules():
        assert rule.validation_status is ValidationStatus.PENDING_VERIFICATION
        assert not rule.usable_in_strict_mode


def test_a_composed_rule_does_not_claim_the_annex_printed_its_formula() -> None:
    """COMPOSED_NORMATIVE_RULE, et pourquoi NATIONAL_ANNEX serait un abus.

    Etiqueter 6.6N « national_annex » reviendrait a dire que l'annexe belge
    imprime « nu = 0,6[1 - f_ck/250] ». Elle ne l'imprime pas: elle ecrit
    « la valeur recommandee (formule 6.6N) est normative », et l'expression
    vit dans l'EN 1992-1-1:2004 p. 102.

    9.5N est le cas ou la distinction est indispensable: la base fournit la
    formule, l'annexe substitue f_ywk a f_yk, et la regle applicable n'existe
    dans AUCUN des deux documents pris seul. Elle est COMPOSEE.

    cot_theta_max fait exception dans l'autre sens: l'ANB imprime sa propre
    formule et ne renvoie a rien. Elle est donc bien `national_annex`.
    """
    composees = {
        r.rule_id for r in all_rules()
        if r.value_provenance is ValueProvenance.COMPOSED_NORMATIVE_RULE
    }
    propres = {
        r.rule_id for r in all_rules()
        if r.value_provenance is ValueProvenance.NATIONAL_ANNEX
    }
    assert propres == {"be.ec2.cot_theta_max"}
    assert "be.ec2.nu_strength_reduction" in composees
    assert "be.ec2.rho_w_min" in composees

    # Une regle composee reste NATIONALE: c'est bien la regle que le pays
    # applique, et elle doit pouvoir franchir le mode strict une fois validee.
    assert ValueProvenance.COMPOSED_NORMATIVE_RULE.is_national

    # Et elle porte les deux moities, l'une sans l'autre ne suffirait pas.
    for rid in composees:
        r = next(x for x in all_rules() if x.rule_id == rid)
        assert r.expression_sources and r.normative_authority.quote


# ---------------------------------------------------------------------------
# T4 — nu, Expression (6.6N)
# ---------------------------------------------------------------------------
def test_T4_nu_decreases_with_concrete_strength() -> None:
    """nu = 0,6[1 - f_ck/250], f_ck en MPa.

    Le point verifie a la main: le texte donne 0,6 MULTIPLIANT le crochet, ce
    que l'extraction brute rend « 0,61- ». Si le moteur avait lu 0,61, nu(30)
    vaudrait 0,61 - 30/250 = 0,49 et non 0,528. L'ecart est de 7 %, dans le
    sens qui SURESTIME la resistance de la bielle.
    """
    assert R.NU_STRENGTH_REDUCTION.evaluate(f_ck=Q_(30, "MPa")).magnitude == pytest.approx(0.528)
    assert R.NU_STRENGTH_REDUCTION.evaluate(f_ck=Q_(25, "MPa")).magnitude == pytest.approx(0.54)
    assert R.NU_STRENGTH_REDUCTION.evaluate(f_ck=Q_(50, "MPa")).magnitude == pytest.approx(0.48)

    # Decroissance stricte en f_ck.
    valeurs = [
        R.NU_STRENGTH_REDUCTION.evaluate(f_ck=Q_(f, "MPa")).magnitude
        for f in (12, 20, 30, 45, 60, 90)
    ]
    assert all(a > b for a, b in zip(valeurs, valeurs[1:]))

    # Hors des classes de l'EN: refus, pas d'extrapolation.
    with pytest.raises(OutOfValidationDomain):
        R.NU_STRENGTH_REDUCTION.evaluate(f_ck=Q_(120, "MPa"))


# ---------------------------------------------------------------------------
# T5 — alpha_cw, Expressions (6.11.aN) a (6.11.cN)
# ---------------------------------------------------------------------------
def test_T5_alpha_cw_branches_and_boundaries() -> None:
    """Quatre branches, et le cas non precontraint n'est que la premiere.

    Le scalaire 1,0 qui etait stocke etait cette branche-la, presentee sans sa
    condition — donc faux des qu'il y a precontrainte.
    """
    f_cd = Q_(20.0, "MPa")

    def a(sigma_mpa: float) -> float:
        return R.ALPHA_CW.evaluate(
            sigma_cp=Q_(sigma_mpa, "MPa"), f_cd=f_cd
        ).magnitude

    assert a(0.0) == pytest.approx(1.0)          # non precontraint
    assert a(2.0) == pytest.approx(1.1)          # 6.11.aN : 1 + 0,1
    assert a(5.0) == pytest.approx(1.25)         # borne 0,25 f_cd, incluse
    assert a(8.0) == pytest.approx(1.25)         # 6.11.bN
    assert a(10.0) == pytest.approx(1.25)        # borne 0,5 f_cd, incluse
    assert a(15.0) == pytest.approx(0.625)       # 6.11.cN : 2,5(1 - 0,75)

    # Continuite aux deux bornes: la valeur juste avant tend vers celle d'apres.
    assert a(5.0 - 1e-9) == pytest.approx(1.25, abs=1e-6)
    assert a(10.0 + 1e-9) == pytest.approx(1.25, abs=1e-6)

    # sigma_cp >= f_cd: aucune branche ne couvre, et rien n'est produit.
    with pytest.raises(OutOfValidationDomain):
        a(20.0)

    # Les intervalles declares sont des DONNEES: la note peut les imprimer.
    assert [b.description for b in R.ALPHA_CW.branches][0].startswith("structures non")
    assert R.ALPHA_CW.rule_type is RuleKind.CONDITIONAL_RULE


# ---------------------------------------------------------------------------
# T6 — rho_w_min, Expression (9.5N) MODIFIEE par l'ANB
# ---------------------------------------------------------------------------
def test_T6_rho_w_min_uses_the_stirrup_steel() -> None:
    """La substitution belge f_ywk <- f_yk, et le seul test qui la prouve.

    Un test ou f_ywk = f_yk ne prouverait RIEN: c'est exactement le cas ou la
    formule belge et la formule EN coincident. Il faut deux nuances d'acier
    differentes pour que la difference apparaisse.
    """
    f_ck = Q_(30.0, "MPa")
    attendu = 0.08 * math.sqrt(30.0) / 500.0
    assert R.RHO_W_MIN.evaluate(
        f_ck=f_ck, f_ywk=Q_(500.0, "MPa")
    ).magnitude == pytest.approx(attendu)

    # Etriers en acier different des barres longitudinales: la formule EN
    # (qui diviserait par f_yk = 500) et la belge (par f_ywk = 220) divergent.
    belge = R.RHO_W_MIN.evaluate(f_ck=f_ck, f_ywk=Q_(220.0, "MPa")).magnitude
    en_avec_fyk = 0.08 * math.sqrt(30.0) / 500.0
    assert belge != pytest.approx(en_avec_fyk)
    assert belge == pytest.approx(0.08 * math.sqrt(30.0) / 220.0)
    # Et l'ecart n'est pas marginal: plus du double.
    assert belge > 2 * en_avec_fyk

    # L'autorite dit qu'elle MODIFIE, pas qu'elle adopte.
    assert "MODIFIE" in R.RHO_W_MIN.normative_authority.effect


# ---------------------------------------------------------------------------
# T7 — s_l_max, Expression (9.6N)
# ---------------------------------------------------------------------------
def test_T7_s_l_max_vertical_stirrups_and_monotonicity() -> None:
    """0,75 d (1 + cot alpha), avec le cas des cadres droits explicite.

    alpha = 90 deg donne cot alpha = 0, donc 0,75 d — c'est pourquoi le code
    precedent, qui multipliait simplement par 0,75, donnait le bon resultat
    dans ce cas et seulement dans celui-la.
    """
    d = Q_(450.0, "mm")
    assert R.S_L_MAX.evaluate(d=d, alpha=Q_(90, "degree")).to("mm").magnitude == pytest.approx(337.5)
    # Armatures inclinees a 45 deg: cot = 1, le facteur double.
    assert R.S_L_MAX.evaluate(d=d, alpha=Q_(45, "degree")).to("mm").magnitude == pytest.approx(675.0)

    # Croissance stricte avec la hauteur utile.
    valeurs = [
        R.S_L_MAX.evaluate(d=Q_(x, "mm"), alpha=Q_(90, "degree")).to("mm").magnitude
        for x in (200, 400, 600, 900)
    ]
    assert all(a < b for a, b in zip(valeurs, valeurs[1:]))

    # Hors du domaine d'inclinaison de §9.2.2(1).
    with pytest.raises(OutOfValidationDomain):
        R.S_L_MAX.evaluate(d=d, alpha=Q_(30, "degree"))


# ---------------------------------------------------------------------------
# T8 — s_t_max, Expression (9.8N)
# ---------------------------------------------------------------------------
def test_T8_s_t_max_cap_governs_for_deep_beams() -> None:
    """min(0,75 d ; 600 mm) — et un cas ou le PLAFOND gouverne.

    Sans ce second cas, le plafond ne serait jamais exerce et le scalaire 0,75
    tout seul passerait le test. C'est precisement ce que le modele scalaire
    perdait.
    """
    assert R.S_T_MAX.evaluate(d=Q_(450.0, "mm")).to("mm").magnitude == pytest.approx(337.5)
    # 0,75 x 1200 = 900 > 600: le plafond gouverne.
    assert R.S_T_MAX.evaluate(d=Q_(1200.0, "mm")).to("mm").magnitude == pytest.approx(600.0)
    # Juste au-dessus du basculement, a d = 800 mm.
    assert R.S_T_MAX.evaluate(d=Q_(800.0, "mm")).to("mm").magnitude == pytest.approx(600.0)
    assert R.S_T_MAX.evaluate(d=Q_(799.0, "mm")).to("mm").magnitude == pytest.approx(599.25)


# ---------------------------------------------------------------------------
# T9 — cot_theta_max, regle belge propre
# ---------------------------------------------------------------------------
def _cot(sigma_mpa: float, **kw: object) -> float:
    args = dict(
        k_1=Q_(0.15, ""), sigma_cp=Q_(sigma_mpa, "MPa"), b_w=Q_(300.0, "mm"),
        d=Q_(450.0, "mm"), s=Q_(200.0, "mm"), A_sw=Q_(101.0, "mm**2"),
        z=Q_(405.0, "mm"), f_ywd=Q_(435.0, "MPa"), f_cd=Q_(20.0, "MPa"),
    )
    args.update(kw)
    return R.COT_THETA_MAX.evaluate(**args).magnitude


def test_T9_cot_theta_max_is_two_without_prestress() -> None:
    """Le resultat qui rendait un repli sur l'Eurocode NON CONSERVATIF.

    L'EN recommande 1 <= cot(theta) <= 2,5. La Belgique remplace la borne
    superieure par une formule dont le terme constant vaut 2. Pour une poutre
    NON precontrainte, sigma_cp = 0, donc cot(theta)_max = 2 — pas 2,5.

    Un moteur qui, faute de mieux, aurait retenu 2,5 aurait produit des
    armatures d'effort tranchant INSUFFISANTES, sans rien signaler.
    """
    assert _cot(0.0) == pytest.approx(2.0)
    assert _cot(0.0) < 2.5

    # Precontrainte: la borne monte, strictement.
    assert _cot(0.5) > 2.0
    assert _cot(1.0) > _cot(0.5)
    # A la limite du domaine pour f_cd = 20 MPa, elle vaut 2,910: le plafond
    # de 3 n'est PAS encore atteint avec ce ferraillage. L'attente initiale de
    # ce test disait 3,0 — c'etait l'attente qui etait fausse, pas la formule.
    assert _cot(4.0) == pytest.approx(2.9104358711733243)

    # Le plafond de 3 gouverne pour un beton plus resistant, qui autorise une
    # precontrainte plus forte: f_cd = 30 MPa permet sigma_cp jusqu'a 6 MPa.
    assert _cot(6.0, f_cd=Q_(30.0, "MPa")) == pytest.approx(3.0)

    # Domaine: sigma_cp <= 0,2 f_cd = 4 MPa. Au-dela, refus.
    with pytest.raises(OutOfValidationDomain, match="0.2"):
        _cot(5.0)


def test_T9_cot_theta_max_declares_how_the_circularity_is_broken() -> None:
    """La dependance circulaire doit etre NOMMEE, pas laissee implicite.

    La formule depend de A_sw et s, qui sont des resultats du dimensionnement
    qu'elle contraint. Le modele refuse de construire une NormativeFunction
    qui ne dit pas comment l'appelant doit sequencer cela.
    """
    ordre = R.COT_THETA_MAX.evaluation_order
    # Une iteration numerique CONTROLEE est autorisee; ce qui ne l'est pas,
    # c'est une boucle silencieuse ou non bornee. L'ordre doit donc annoncer
    # ses quatre garanties: bornes, convergence, plafond d'iterations, refus.
    assert "POINT FIXE" in ordre
    assert "1e-9" in ordre and "50 iterations" in ordre
    assert "REFUS" in ordre
    # Et il ne doit PAS brider le domaine initial: brider a 2 serait
    # sur-conservatif des qu'il y a precontrainte.
    assert "1,0 <= cot(theta) <= 3" in ordre

    from eurostruct_engine.ndp.rules import NormativeFunction

    with pytest.raises(ValueError, match="ordre d'evaluation"):
        NormativeFunction(
            rule_id="essai", rule_type=RuleKind.FUNCTION, description="essai",
            output_unit="dimensionless",
            normative_authority=R.COT_THETA_MAX.normative_authority,
            expression_sources=R.COT_THETA_MAX.expression_sources,
            validation_status=ValidationStatus.PENDING_VERIFICATION,
            value_provenance=ValueProvenance.NATIONAL_ANNEX,
        )


# ---------------------------------------------------------------------------
# Le solveur de cot(theta): convergence demontree, et verifiee quand meme
# ---------------------------------------------------------------------------
def _solve(sigma_mpa: float, **kw):
    from eurostruct_engine.ndp.rules_be_ec2 import solve_cot_theta_for_design

    args = dict(
        V_Ed=Q_(250.0, "kN"), k_1=Q_(0.15, ""), sigma_cp=Q_(sigma_mpa, "MPa"),
        b_w=Q_(300.0, "mm"), d=Q_(450.0, "mm"), z=Q_(405.0, "mm"),
        f_ywd=Q_(435.0, "MPa"), f_cd=Q_(20.0, "MPa"), s=Q_(200.0, "mm"),
    )
    args.update(kw)
    return solve_cot_theta_for_design(**args)


@pytest.mark.parametrize("sigma_mpa,f_cd_mpa", [
    (0.0, 20.0), (0.5, 20.0), (1.0, 20.0), (2.0, 20.0), (3.0, 20.0),
    (4.0, 20.0), (5.0, 30.0), (6.0, 30.0), (9.0, 50.0), (10.0, 50.0),
])
@pytest.mark.parametrize("f_ywd_mpa", [300.0, 435.0, 500.0])
@pytest.mark.parametrize("geometry", [
    {"b_w": Q_(200.0, "mm"), "d": Q_(300.0, "mm"), "z": Q_(270.0, "mm")},
    {"b_w": Q_(300.0, "mm"), "d": Q_(450.0, "mm"), "z": Q_(405.0, "mm")},
    {"b_w": Q_(500.0, "mm"), "d": Q_(900.0, "mm"), "z": Q_(810.0, "mm")},
])
@pytest.mark.parametrize("s_mm", [100.0, 300.0])
def test_the_solver_agrees_with_an_independent_closed_form(
    sigma_mpa, f_cd_mpa, f_ywd_mpa, geometry, s_mm
) -> None:
    """180 combinaisons, confrontees a une methode INDEPENDANTE.

    L'iteration part de cot = 1 et applique F. L'oracle resout l'equation de
    point fixe algebriquement. Les deux n'ont en commun que la formule de
    l'ANB: si l'une se trompe, elles divergent.

    C'est la discipline des cas de reference du moteur — bissection contre
    forme fermee — appliquee ici.

    La demonstration montre aussi que s, z, f_ywd et A_sw se SIMPLIFIENT: ces
    trois axes de parametrage ne doivent donc rien changer au resultat, et
    c'est verifie plutot que suppose.
    """
    from eurostruct_engine.ndp.rules_be_ec2 import Termination, fixed_point_closed_form

    sol = _solve(sigma_mpa, f_cd=Q_(f_cd_mpa, "MPa"),
                 f_ywd=Q_(f_ywd_mpa, "MPa"), s=Q_(s_mm, "mm"), **geometry)
    if sol.termination is Termination.INVALID_DOMAIN:
        # sigma_cp > 0,2 f_cd: refus attendu, aucune valeur.
        assert sol.cot_theta is None
        assert sigma_mpa > 0.2 * f_cd_mpa
        return

    assert sol.accepted, sol.refusal
    assert sol.cot_theta == pytest.approx(fixed_point_closed_form(sol.slope_A), abs=1e-9)
    # Le residu de sortie a ete verifie sur la valeur retenue.
    assert sol.residual is not None and sol.residual <= 1e-12
    assert 1.0 <= sol.cot_theta <= 3.0


def test_the_solver_names_why_it_stopped() -> None:
    """Quatre terminaisons, et deux d'entre elles ne rendent aucune valeur."""
    from eurostruct_engine.ndp.rules_be_ec2 import Termination

    # Sans precontrainte: convergence en 2 iterations, cot = 2 exactement.
    sans = _solve(0.0)
    assert sans.termination is Termination.CONVERGED
    assert sans.cot_theta == pytest.approx(2.0)
    assert sans.slope_A == pytest.approx(0.0)

    # Precontrainte forte: le plafond normatif EST le point fixe.
    plafond = _solve(6.0, f_cd=Q_(30.0, "MPa"))
    assert plafond.termination is Termination.UPPER_BOUND
    assert plafond.cot_theta == pytest.approx(3.0)

    # Hors domaine: sigma_cp > 0,2 f_cd.
    hors = _solve(5.0)
    assert hors.termination is Termination.INVALID_DOMAIN
    assert hors.cot_theta is None and hors.refusal

    # Effort nul: SANS OBJET, et non « domaine invalide ». Il n'y a pas
    # d'erreur — il n'y a simplement aucune armature d'effort tranchant a
    # dimensionner, donc aucun cot(theta) a resoudre. Classer cela en refus
    # aurait fait passer une absence de travail pour une anomalie.
    nul = _solve(0.0, V_Ed=Q_(0.0, "kN"))
    assert nul.termination is Termination.NOT_APPLICABLE
    assert nul.cot_theta is None
    assert not nul.accepted

    # sigma_cp < 0: traction. EN §6.2.3(3) p.104 definit sigma_cp « mesuree
    # positivement »; aucune branche ne couvre une traction.
    traction = _solve(-1.0)
    assert traction.termination is Termination.INVALID_DOMAIN
    assert "positivement" in traction.refusal


def test_the_solver_journals_every_iteration() -> None:
    """Chaque iteration porte precedent, calcule et residu — auditable."""
    sol = _solve(2.0)
    assert len(sol.iterations) >= 2
    for it in sol.iterations:
        assert it.residual == pytest.approx(abs(it.computed - it.previous))
    # Suite croissante, comme la demonstration l'annonce.
    valeurs = [it.previous for it in sol.iterations]
    assert all(a <= b for a, b in zip(valeurs, valeurs[1:]))
    # Residus decroissants: convergence lineaire de rapport A.
    residus = [it.residual for it in sol.iterations]
    assert all(a >= b for a, b in zip(residus, residus[1:]))
    assert sol.journal[-1].startswith("CONVERGED")


# ---------------------------------------------------------------------------
# La substitution elle-meme, et ses conditions de validite
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("c", [1.0, 1.5, 2.0, 2.7, 3.0])
@pytest.mark.parametrize("s_mm", [75.0, 100.0, 200.0, 350.0])
@pytest.mark.parametrize("z_mm", [270.0, 380.0, 405.0, 500.0, 810.0])
def test_the_substitution_holds_for_required_reinforcement(c, s_mm, z_mm) -> None:
    """L'expression ANB NON SIMPLIFIEE contre l'expression simplifiee.

    C'est la verification qui avait ete faite HORS DEPOT avant d'ecrire le
    code, sur 81 combinaisons. Une verification externe non persistee ne fait
    pas partie de la preuve reproductible: la voici, elargie a 100 cas.

    Cote gauche: la formule de l'ANB telle qu'elle est imprimee, evaluee avec
    A_sw calcule par l'equilibre (6.8). Cote droit: 2 + A c. Les deux doivent
    coincider EXACTEMENT — a l'arrondi flottant pres — puisque s, z, f_ywd et
    A_sw se simplifient algebriquement.

    Le parametrage sur s et z est le test de l'invariance annoncee: si la
    simplification etait fausse, ces axes feraient bouger le resultat.
    """
    from eurostruct_engine.ndp.rules_be_ec2 import COT_THETA_MAX

    V_Ed, k_1 = Q_(250.0, "kN"), Q_(0.15, "")
    sigma_cp, b_w, d = Q_(2.0, "MPa"), Q_(300.0, "mm"), Q_(450.0, "mm")
    f_ywd, f_cd = Q_(435.0, "MPa"), Q_(20.0, "MPa")
    s, z = Q_(s_mm, "mm"), Q_(z_mm, "mm")

    # (6.8): l'armature REQUISE a cet angle — la precondition de la substitution.
    A_sw = (V_Ed / (z * f_ywd * c) * s).to("mm**2")

    non_simplifiee = float(COT_THETA_MAX.evaluate(
        k_1=k_1, sigma_cp=sigma_cp, b_w=b_w, d=d, s=s,
        A_sw=A_sw, z=z, f_ywd=f_ywd, f_cd=f_cd,
    ).magnitude)

    A = float((k_1 * sigma_cp * b_w * d / V_Ed).to("dimensionless").magnitude)
    simplifiee = min(2.0 + A * c, 3.0)

    assert non_simplifiee == pytest.approx(simplifiee, rel=1e-12), (
        f"c={c} s={s_mm} z={z_mm}: {non_simplifiee!r} != {simplifiee!r}"
    )


def test_the_substitution_must_not_be_used_for_a_given_reinforcement() -> None:
    """Armature IMPOSEE: A_sw/s est une donnee, pas une consequence de cot.

    Le solveur porte cette precondition dans son nom. La verifier ici, c'est
    montrer que l'oublier CHANGE le resultat: avec un ferraillage impose plus
    faible que le requis, la borne de l'ANB est differente de celle que la
    forme simplifiee donnerait.
    """
    from eurostruct_engine.ndp.rules_be_ec2 import COT_THETA_MAX

    V_Ed, c = Q_(250.0, "kN"), 2.0
    k_1, sigma_cp = Q_(0.15, ""), Q_(2.0, "MPa")
    b_w, d, z = Q_(300.0, "mm"), Q_(450.0, "mm"), Q_(405.0, "mm")
    f_ywd, f_cd, s = Q_(435.0, "MPa"), Q_(20.0, "MPa"), Q_(200.0, "mm")

    requise = (V_Ed / (z * f_ywd * c) * s).to("mm**2")
    imposee = requise * 0.6          # l'ingenieur a mis moins que le requis

    borne_requise = float(COT_THETA_MAX.evaluate(
        k_1=k_1, sigma_cp=sigma_cp, b_w=b_w, d=d, s=s,
        A_sw=requise, z=z, f_ywd=f_ywd, f_cd=f_cd).magnitude)
    borne_imposee = float(COT_THETA_MAX.evaluate(
        k_1=k_1, sigma_cp=sigma_cp, b_w=b_w, d=d, s=s,
        A_sw=imposee, z=z, f_ywd=f_ywd, f_cd=f_cd).magnitude)

    assert borne_imposee != pytest.approx(borne_requise)
    # Moins d'armature -> borne PLUS HAUTE (le terme est en 1/A_sw).
    assert borne_imposee > borne_requise


def test_the_slope_A_is_dimensionless_in_the_engine_units() -> None:
    """[] . [pression] . [longueur]^2 / [force] doit etre sans dimension."""
    A = (Q_(0.15, "") * Q_(2.0, "MPa") * Q_(300.0, "mm") * Q_(450.0, "mm")
         / Q_(250.0, "kN")).to_base_units()
    assert A.dimensionless
    assert float(A.to("dimensionless").magnitude) == pytest.approx(0.162)


@pytest.mark.parametrize("A_cible,attendu", [
    (0.0, "converged"),
    (1.0 / 3.0 - 1e-6, "converged"),
    (1.0 / 3.0, "upper_bound"),
    (1.0 / 3.0 + 1e-6, "upper_bound"),
    (0.9, "upper_bound"),
])
def test_termination_is_classified_on_A_not_on_proximity_to_three(
    A_cible, attendu
) -> None:
    """A = 1/3 exactement: la suite approche 3 SANS activer le min.

    Classer sur la proximite numerique de 3 aurait rendu « converged » alors
    que la solution mathematique EST la borne. Le classement se fait donc sur
    A, ou le seuil est exact.
    """
    from eurostruct_engine.ndp.rules_be_ec2 import fixed_point_closed_form

    # A = k1 sigma_cp b_w d / V_Ed: on regle sigma_cp pour viser A.
    V_Ed, k_1 = Q_(250.0, "kN"), Q_(0.15, "")
    b_w, d = Q_(300.0, "mm"), Q_(450.0, "mm")
    facteur = float((k_1 * b_w * d / V_Ed).to("1/MPa").magnitude)
    sigma = A_cible / facteur
    # f_cd assez grand pour que sigma_cp <= 0,2 f_cd reste satisfait.
    sol = _solve(sigma, f_cd=Q_(max(20.0, sigma / 0.2 + 1.0), "MPa"))

    assert sol.termination.value == attendu, sol.journal[-1]
    assert sol.cot_theta == pytest.approx(fixed_point_closed_form(sol.slope_A),
                                          abs=1e-9)
    if attendu == "upper_bound":
        assert sol.cot_theta == pytest.approx(3.0)


@pytest.mark.parametrize("champ,valeur", [
    ("V_Ed", Q_(float("nan"), "kN")),
    ("V_Ed", Q_(float("inf"), "kN")),
    ("sigma_cp", Q_(float("nan"), "MPa")),
    ("b_w", Q_(float("inf"), "mm")),
])
def test_non_finite_inputs_never_yield_a_value(champ, valeur) -> None:
    """NaN et infinis: aucune valeur acceptee, quelle que soit la sortie.

    Le solveur peut les refuser au domaine ou epuiser son budget; ce qui est
    interdit, c'est qu'il rende un cot(theta). Un NaN qui traverse une
    comparaison la rend fausse en silence — c'est la facon la plus discrete
    de produire un resultat faux.
    """
    sol = _solve(2.0, **{champ: valeur})
    if sol.accepted:
        assert math.isfinite(sol.cot_theta), sol.journal[-1]
        assert 1.0 <= sol.cot_theta <= 3.0
    else:
        assert sol.cot_theta is None


def test_the_solver_refuses_inconsistent_units() -> None:
    """Une longueur passee pour une contrainte est refusee, pas convertie."""
    with pytest.raises((UnitError, OutOfValidationDomain)):
        _solve(2.0, sigma_cp=Q_(300.0, "mm"))
    with pytest.raises((UnitError, OutOfValidationDomain)):
        _solve(2.0, b_w=Q_(300.0, "MPa"))


@pytest.mark.parametrize("V_kN", [80.0, 150.0, 250.0, 600.0])
@pytest.mark.parametrize("k1", [0.10, 0.15, 0.20])
@pytest.mark.parametrize("b_mm,d_mm", [(200.0, 300.0), (300.0, 450.0), (500.0, 900.0)])
def test_A_is_driven_by_V_Ed_k1_and_geometry(V_kN, k1, b_mm, d_mm) -> None:
    """Les quatre grandeurs qui determinent REELLEMENT A.

    s, z et f_ywd n'y figurent pas — ils se simplifient. Ceux-la, si.
    """
    from eurostruct_engine.ndp.rules_be_ec2 import fixed_point_closed_form

    sol = _solve(2.0, V_Ed=Q_(V_kN, "kN"), k_1=Q_(k1, ""),
                 b_w=Q_(b_mm, "mm"), d=Q_(d_mm, "mm"))
    attendu_A = k1 * 2.0 * b_mm * d_mm / (V_kN * 1000.0)
    assert sol.slope_A == pytest.approx(attendu_A, rel=1e-12)
    assert sol.accepted
    assert sol.cot_theta == pytest.approx(fixed_point_closed_form(sol.slope_A),
                                          abs=1e-9)


def test_the_iteration_budget_is_derived_not_chosen() -> None:
    """26 iterations suffisent sur A <= 1/3; le budget les majore de peu.

    Un premier jet portait 200, ce qui remplacait une borne calculable par une
    constante confortable.
    """
    import math as _m

    from eurostruct_engine.ndp.rules_be_ec2 import _MAX_ITERATIONS, _TOLERANCE

    theorique = _m.ceil(_m.log(2.0 / _TOLERANCE) / _m.log(3.0))
    assert theorique == 26
    assert _MAX_ITERATIONS >= theorique
    assert _MAX_ITERATIONS <= 4 * theorique, (
        "budget trop large: une constante ne doit pas remplacer une borne"
    )
    # Et le pire cas mesure reste sous la borne theorique.
    pire = _solve(4.0)          # A = 0,324
    assert len(pire.iterations) <= theorique


def test_the_report_shows_raw_values_and_the_actual_tolerance() -> None:
    """Lever l'ambiguite d'affichage signalee sur le tableau precedent.

    L'ecart apparent au neuvieme chiffre venait du formatage, pas du calcul.
    La solution porte donc les valeurs BRUTES et l'ecart, pour qu'aucune
    lecture ne depende d'un arrondi d'impression.
    """
    sol = _solve(4.0)
    assert sol.cot_theta is not None and sol.closed_form is not None
    assert sol.difference_to_closed_form == pytest.approx(
        abs(sol.cot_theta - sol.closed_form)
    )
    assert sol.difference_to_closed_form < 1e-9
    assert sol.tolerance == 1e-12
    dernier = sol.journal[-1]
    for attendu in ("iteration =", "forme fermee =", "ecart =", "residu",
                    "tolerance ="):
        assert attendu in dernier
