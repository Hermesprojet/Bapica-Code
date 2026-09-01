"""La verification complete d'une poutre: les cinq sections, une seule entree.

CE QUE CE MODULE FERME
-----------------------
Les cinq modules — flexion, tranchant, ancrage, ELS, dispense de fleche —
existaient, et le depot les assemblait DANS UN TEST. Chaque appel y recevait ses
propres arguments, ecrits a la main. Rien n'obligeait la geometrie de la flexion
a etre celle du tranchant, ni le ferraillage de l'ELS a etre celui du dessin:
l'assemblage tenait parce que les memes nombres avaient ete recopies cinq fois.

Ce module derive les cinq appels d'UNE entree gelee. Les valeurs partagees ne
sont pas recopiees, elles sont **derivees une fois**:

    A_s      <- nombre de barres x diametre
    A_sw     <- nombre de branches x diametre de cadre
    A_sl     <- la meme A_s (le terme V_Rd,c depend du ferraillage tendu)
    A_s,req  <- la flexion le CALCULE; la dispense de fleche le recoit d'elle
    entraxe  <- le MODELE GEOMETRIQUE PARTAGE, celui-la meme qui sera dessine

D'ou l'interdiction de saisir `A_s`, `A_sw` ou l'entraxe: deux sources pour un
meme fait finissent toujours par diverger, et le jour ou elles divergent le
produit dessine autre chose que ce qu'il a calcule.

LES QUATRE ISSUES, ET POURQUOI ELLES NE SE CONFONDENT PAS
----------------------------------------------------------
1. **Refus** — l'entree est incoherente, ou hors du domaine de validation. Rien
   n'est produit. Une exception, pas un resultat.
2. **Refus explicite** — un parametre national manque. En mode strict, c'est
   `preflight_beam` qui le dit AVANT le calcul, en une seule reponse pour les
   cinq modules: echouer cinq fois de suite n'apprend rien a personne.
3. **Rouge** — la verification a tourne et n'est pas satisfaite. Taux
   d'utilisation ET remede.
4. **`not_evaluated`** — la verification n'a pas pu tourner. Elle n'est JAMAIS
   « conforme », et l'etude entiere devient `incomplete`.

Une etude rouge ou incomplete se conserve pour diagnostic. Elle ne devient
jamais un livrable final: `may_be_finalised` ne vaut True que si les cinq
sections sont vertes.

CE QUE CE MODULE NE FAIT PAS
-----------------------------
Il ne calcule RIEN. Pas une formule, pas une comparaison normative — sauf une,
nommee et assumee: l'ancrage. `design_anchorage` produit une LONGUEUR REQUISE et
ne verifie rien; la verification est la comparaison de cette longueur a celle
que l'ingenieur declare disponible. Sans elle, l'ancrage serait le seul chapitre
de la note sans verdict.

AUCUN RESULTAT PRODUIT ICI N'EST UNE VERIFICATION REELLE tant que les
parametres nationaux ne sont pas releves et qu'un ingenieur habilite ne l'a pas
validee.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..drawing.modele import BarRow, BeamSectionSpec, construire_modele
from ..exceptions import (
    InconsistentInput,
    NationalAnnexIncomplete,
)
from ..materials import concrete as _concrete
from ..materials import reinforcement as _reinforcement
from ..materials.reinforcement import bars_area
from ..ndp.registry import ParameterSet, load_parameter_set
from ..units import Q_, Quantity, fmt
from ..version import ENGINE_VERSION
from .anchorage import AnchorageCoefficients, BondCondition, design_anchorage
from .anchorage import required_parameters as _anchorage_params
from .beam_flexure import RectangularSection, design_flexure
from .beam_flexure import required_parameters as _flexure_params
from .beam_shear import ShearLinks, ShearSection, design_shear
from .beam_shear import required_parameters as _shear_params
from .deflection import StructuralSystem, check_span_depth
from .deflection import required_parameters as _deflection_params
from .serviceability import (
    CrackControlDetail,
    ExposureClass,
    design_serviceability,
)
from .serviceability import required_parameters as _sls_params

__all__ = [
    "BeamGeometry",
    "BeamPreflight",
    "BeamVerification",
    "BeamVerificationInput",
    "BlockingParameter",
    "LongitudinalBars",
    "SectionOutcome",
    "TransverseLinks",
    "preflight_beam",
    "verify_beam",
]

#: L'ordre des cinq sections. Il est celui de la note de calcul, et il est
#: FIXE: un lecteur qui retrouve les chapitres dans un autre ordre d'une etude
#: a l'autre ne peut pas comparer deux dossiers.
SECTION_ORDER: tuple[tuple[str, str], ...] = (
    ("flexure", "Flexion simple a l'ELU"),
    ("shear", "Effort tranchant a l'ELU"),
    ("anchorage", "Ancrages et recouvrements"),
    ("serviceability", "Etats limites de service"),
    ("deflection", "Limitation des fleches"),
)

#: La base normative de chaque chapitre, citee dans la note.
SECTION_BASIS: dict[str, str] = {
    "flexure": "EN 1992-1-1 §6.1",
    "shear": "EN 1992-1-1 §6.2",
    "anchorage": "EN 1992-1-1 §8.4 et §8.7",
    "serviceability": "EN 1992-1-1 §7.2 et §7.3",
    "deflection": "EN 1992-1-1 §7.4.2",
}

#: LE VOCABULAIRE DE LA DISPENSE, MOT POUR MOT.
#:
#: Une dispense non acquise ne veut PAS dire que la poutre echoue: elle veut
#: dire qu'un calcul explicite de fleche reste necessaire. Confondre les deux
#: ferait refuser des poutres correctes. Le remede le dit donc en toutes
#: lettres, et l'interface reprend la meme phrase.
REMEDE_FLECHE = (
    "Dispense non acquise: un calcul explicite de la fleche est requis "
    "(EN 1992-1-1 §7.4.3). Ce n'est pas un echec de la poutre."
)

REMEDE_ANCRAGE = (
    "Longueur d'ancrage disponible insuffisante: allonger l'about, prevoir "
    "un crochet (alpha_1 = 0,7) ou augmenter le nombre de barres pour "
    "reduire sigma_sd."
)


# ---------------------------------------------------------------------------
# L'entree, gelee
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class BeamGeometry:
    """La section et la portee. Une seule fois, pour les cinq modules."""

    b: Quantity
    h: Quantity
    d: Quantity
    l_eff: Quantity


@dataclass(frozen=True, slots=True)
class LongitudinalBars:
    """Le lit tendu. `A_s` s'en DERIVE et ne se saisit jamais a cote."""

    count: int
    diameter: Quantity

    @property
    def area(self) -> Quantity:
        return bars_area(self.count, float(self.diameter.to("mm").magnitude))


@dataclass(frozen=True, slots=True)
class TransverseLinks:
    """Les cadres. `A_sw` se derive des branches et du diametre."""

    legs: int
    diameter: Quantity
    spacing: Quantity

    @property
    def area(self) -> Quantity:
        return bars_area(self.legs, float(self.diameter.to("mm").magnitude))


@dataclass(frozen=True, slots=True)
class BeamVerificationInput:
    """Tout ce que les cinq verifications demandent, et rien de redondant."""

    element: str
    geometry: BeamGeometry
    concrete_grade: str
    steel_grade: str
    M_Ed: Quantity
    V_Ed: Quantity
    M_char: Quantity
    M_qp: Quantity
    phi_creep: float
    exposure_class: ExposureClass
    system: StructuralSystem
    bars: LongitudinalBars
    links: TransverseLinks
    cot_theta: float
    cover: Quantity
    anchorage_available: Quantity
    supports_brittle_partitions: bool = False
    bond_condition: str = BondCondition.GOOD
    anchorage_coefficients: AnchorageCoefficients | None = None
    b_eff_over_b_w: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """La forme gelee, telle qu'elle sera stockee et rehachee."""
        return {
            "element": self.element,
            "geometry": {
                "b": fmt(self.geometry.b), "h": fmt(self.geometry.h),
                "d": fmt(self.geometry.d), "l_eff": fmt(self.geometry.l_eff),
            },
            "concrete_grade": self.concrete_grade,
            "steel_grade": self.steel_grade,
            "M_Ed": fmt(self.M_Ed), "V_Ed": fmt(self.V_Ed),
            "M_char": fmt(self.M_char), "M_qp": fmt(self.M_qp),
            "phi_creep": self.phi_creep,
            "exposure_class": self.exposure_class.value,
            "system": self.system.value,
            "bars": {"count": self.bars.count,
                     "diameter": fmt(self.bars.diameter)},
            "links": {"legs": self.links.legs,
                      "diameter": fmt(self.links.diameter),
                      "spacing": fmt(self.links.spacing)},
            "cot_theta": self.cot_theta,
            "cover": fmt(self.cover),
            "anchorage_available": fmt(self.anchorage_available),
            "supports_brittle_partitions": self.supports_brittle_partitions,
            "bond_condition": str(self.bond_condition),
            "anchorage_coefficients": (
                None if self.anchorage_coefficients is None else {
                    "alpha_1": self.anchorage_coefficients.alpha_1,
                    "alpha_2": self.anchorage_coefficients.alpha_2,
                    "alpha_3": self.anchorage_coefficients.alpha_3,
                    "alpha_4": self.anchorage_coefficients.alpha_4,
                    "alpha_5": self.anchorage_coefficients.alpha_5,
                    "alpha_6": self.anchorage_coefficients.alpha_6,
                }),
            "b_eff_over_b_w": self.b_eff_over_b_w,
        }


# ---------------------------------------------------------------------------
# Le resultat
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SectionOutcome:
    """Une des cinq sections, avec son verdict et de quoi le justifier."""

    key: str
    title: str
    basis: str
    #: `passed`, `failed` ou `not_evaluated`. JAMAIS autre chose.
    status: str
    #: `None` quand la section n'a pas tourne: un taux suppose un calcul.
    utilisation: float | None
    #: Ce qu'il faut faire quand c'est rouge.
    remedy: str | None = None
    #: Pourquoi la section n'a pas tourne.
    reason: str | None = None
    #: Le resultat du module, porteur du journal. La note s'en sert.
    design: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "title": self.title, "basis": self.basis,
            "status": self.status, "utilisation": self.utilisation,
            "remedy": self.remedy, "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class BeamVerification:
    """L'etude complete: cinq sections, un statut, une empreinte."""

    element: str
    inputs: BeamVerificationInput
    sections: tuple[SectionOutcome, ...]
    #: `passed`, `failed` ou `incomplete`.
    status: str
    inputs_hash: str
    bar_spacing: Quantity
    drawing_spec: BeamSectionSpec
    ndp_summary: dict[str, Any]
    engine_version: str = ENGINE_VERSION
    execution_identity: str | None = None

    @property
    def may_be_finalised(self) -> bool:
        """Seule une etude dont les CINQ sections sont vertes se finalise.

        Une section rouge est un defaut connu; une section non evaluee est un
        silence. Ni l'un ni l'autre ne devient un livrable final.
        """
        return self.status == "passed"

    @property
    def max_utilisation(self) -> float:
        taux = [s.utilisation for s in self.sections if s.utilisation is not None]
        return max(taux) if taux else 0.0

    def section(self, key: str) -> SectionOutcome:
        for s in self.sections:
            if s.key == key:
                return s
        raise KeyError(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element,
            "status": self.status,
            "inputs": self.inputs.to_dict(),
            "inputs_hash": self.inputs_hash,
            "sections": [s.to_dict() for s in self.sections],
            "bar_spacing": fmt(self.bar_spacing),
            "engine_version": self.engine_version,
            "execution_identity": self.execution_identity,
            "max_utilisation": self.max_utilisation,
            "may_be_finalised": self.may_be_finalised,
        }


# ---------------------------------------------------------------------------
# Le preflight: cinq modules, UNE reponse
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class BlockingParameter:
    """Un parametre qui empeche le calcul, et de quoi agir dessus."""

    module: str
    parameter: str
    clause: str
    annex: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "module": self.module, "parameter": self.parameter,
            "clause": self.clause, "annex": self.annex, "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class BeamPreflight:
    """Ce qui manque, pour les cinq modules a la fois."""

    country: str
    as_of: date
    blocking: tuple[BlockingParameter, ...]
    required: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.blocking

    def to_dict(self) -> dict[str, Any]:
        return {
            "country": self.country,
            "as_of": self.as_of.isoformat(),
            "ready": self.ready,
            "blocking": [b.to_dict() for b in self.blocking],
            "required": list(self.required),
        }


#: Les parametres que chaque module reclame. Ils viennent des modules
#: eux-memes: recopier une liste ici la ferait diverger au premier ajout.
def _required_by_module() -> dict[str, tuple[str, ...]]:
    from ..basis import DesignSituation

    persistent = DesignSituation.PERSISTENT
    return {
        "flexure": _flexure_params(persistent),
        "shear": _shear_params(persistent),
        "anchorage": _anchorage_params(persistent),
        "serviceability": _sls_params(),
        "deflection": _deflection_params(),
    }


def preflight_beam(*, country: str, as_of: date,
                   region: str | None = None) -> BeamPreflight:
    """Reunit en UNE reponse ce qui bloque les cinq modules.

    Le mode strict ne doit pas echouer cinq fois de suite: un ingenieur qui
    corrige un parametre pour se voir refuser sur le suivant, puis le suivant,
    ne sait jamais ou il en est. On demande donc a chaque module ce dont il a
    besoin, on interroge le registre une fois, et on rend la liste entiere.

    Aucune valeur n'est confirmee ici, et aucun ingenieur n'est sollicite.
    """
    params = load_parameter_set(country, strict=False, as_of=as_of)
    besoins = _required_by_module()
    bloquants: list[BlockingParameter] = []
    requis: set[str] = set()

    for module, cles in besoins.items():
        requis.update(cles)
        for cle in cles:
            souci = _diagnostiquer(params, cle)
            if souci is not None:
                clause, annexe, raison = souci
                bloquants.append(BlockingParameter(
                    module=module, parameter=cle, clause=clause,
                    annex=annexe, reason=raison))

    return BeamPreflight(
        country=country, as_of=as_of,
        blocking=tuple(sorted(bloquants, key=lambda b: (b.module, b.parameter))),
        required=tuple(sorted(requis)),
    )


def _diagnostiquer(params: ParameterSet, cle: str
                   ) -> tuple[str, str, str] | None:
    """Ce qui empeche `cle` de servir, ou `None` si rien ne l'empeche.

    LA RAISON EST LE SUJET, PAS LE SIMPLE FAIT DU BLOCAGE.

    « non representable » n'est pas « non confirme », et la nuance decide de ce
    qu'un ingenieur doit faire. Un parametre non confirme s'obtient en le
    faisant confirmer. Un parametre que le MODELE ne sait pas porter — une
    formule en l'enrobage, une borne calculee sur le ferraillage — ne s'obtient
    pas ainsi: il demande de changer le modele. Presenter le second comme le
    premier enverrait quelqu'un chercher une confirmation qui n'existe pas.
    """
    try:
        params.require((cle,))
    except NationalAnnexIncomplete as exc:
        detail = str(exc)
        raison = ("non representable: la valeur nationale est une formule "
                  "que le modele scalaire ne sait pas porter"
                  if "not_representable" in detail
                  else "absent ou non confirme dans l'annexe nationale")
        return (_clause_de(params, cle), _annexe_de(params, cle), raison)
    except KeyError:
        return ("inconnue", "inconnue", "parametre inconnu du registre")
    return None


def _clause_de(params: ParameterSet, cle: str) -> str:
    """La clause qui porte ce parametre, telle que le registre la nomme."""
    try:
        entree = params.registry.lookup(cle)
    except Exception:
        return cle.split(":")[-1] if ":" in cle else cle
    return getattr(entree, "clause", None) or cle


def _annexe_de(params: ParameterSet, cle: str) -> str:
    standard = cle.split(":")[0] if ":" in cle else "EN 1992-1-1"
    try:
        annexe = params.registry.annex_for(standard, params.as_of)
    except Exception:
        return standard
    return getattr(annexe, "reference", None) or standard


# ---------------------------------------------------------------------------
# L'orchestrateur
# ---------------------------------------------------------------------------
def verify_beam(inputs: BeamVerificationInput, *, params: ParameterSet,
                execution_identity: str | None = None) -> BeamVerification:
    """Les cinq verifications, derivees d'une seule entree gelee.

    :raises InconsistentInput: l'entree se contredit.
    :raises OutOfValidationDomain: elle sort du domaine valide d'un module.
    """
    _exiger_coherence(inputs)

    beton = _concrete(inputs.concrete_grade)
    acier = _reinforcement(inputs.steel_grade)
    g = inputs.geometry
    section = RectangularSection(b=g.b, h=g.h, d=g.d)

    # Les majuscules sont celles de l'Eurocode. `a_s` serait conforme a PEP 8
    # et illisible pour qui relit une note de calcul: le symbole normatif prime.
    A_s = inputs.bars.area      # noqa: N806
    A_sw = inputs.links.area    # noqa: N806

    # LA GEOMETRIE PARTAGEE, CONSTRUITE UNE FOIS. Le dessin et l'ELS lisent le
    # meme objet: ils ne peuvent pas diverger.
    spec = _spec_de_dessin(inputs)
    modele = construire_modele(spec)
    entraxe = _entraxe_du_modele(modele)

    resultats: dict[str, SectionOutcome] = {}

    # --- 1. flexion ELU ----------------------------------------------------
    flexion = design_flexure(
        section=section, concrete=beton, steel=acier, M_Ed=inputs.M_Ed,
        params=params, element=inputs.element, A_s_provided=A_s)
    resultats["flexure"] = _depuis_rapport("flexure", flexion)

    # --- 2. effort tranchant ELU ------------------------------------------
    resultats["shear"] = _tente(
        "shear",
        lambda: design_shear(
            section=ShearSection(b_w=g.b, d=g.d, A_sl=A_s),
            concrete=beton, steel=acier, V_Ed=inputs.V_Ed, params=params,
            cot_theta=inputs.cot_theta,
            links=ShearLinks(A_sw=A_sw, s=inputs.links.spacing),
            element=inputs.element))

    # --- 3. ancrage et recouvrement ---------------------------------------
    resultats["anchorage"] = _tente(
        "anchorage", lambda: _verifier_ancrage(inputs, beton, acier, params,
                                               flexion))

    # --- 4. ELS: contraintes et fissuration -------------------------------
    resultats["serviceability"] = _tente(
        "serviceability",
        lambda: design_serviceability(
            section=section, concrete=beton, steel=acier, A_s=A_s,
            M_qp=inputs.M_qp, M_char=inputs.M_char,
            phi_creep=inputs.phi_creep,
            detail=CrackControlDetail(
                phi=inputs.bars.diameter, cover=inputs.cover,
                bar_spacing=entraxe),
            exposure_class=inputs.exposure_class, params=params,
            element=inputs.element))

    # --- 5. dispense du calcul de fleche ----------------------------------
    #: A_s,req VIENT DE LA FLEXION, il ne se saisit pas: c'est le rapport des
    #: deux aires qui porte le facteur de contrainte de §7.4.2(2).
    resultats["deflection"] = _tente(
        "deflection",
        lambda: check_span_depth(
            section=section, concrete=beton, steel=acier, l_eff=g.l_eff,
            system=inputs.system, A_s_required=flexion.As_required,
            A_s_provided=flexion.As_provided, params=params,
            b_eff_over_b_w=inputs.b_eff_over_b_w,
            supports_brittle_partitions=inputs.supports_brittle_partitions,
            element=inputs.element))

    sections = tuple(resultats[cle] for cle, _ in SECTION_ORDER)
    return BeamVerification(
        element=inputs.element,
        inputs=inputs,
        sections=sections,
        status=_statut_global(sections),
        inputs_hash=_empreinte(inputs),
        bar_spacing=entraxe,
        drawing_spec=spec,
        ndp_summary=params.summary(),
        execution_identity=execution_identity,
    )


# ---------------------------------------------------------------------------
# Les pieces
# ---------------------------------------------------------------------------
def _exiger_coherence(inputs: BeamVerificationInput) -> None:
    """Ce qui se contredit est refuse AVANT tout calcul.

    Un refus n'est pas un resultat rouge: rien n'est produit, rien n'est
    conserve. Quatre sections vertes et une exception ne font pas une etude.
    """
    g = inputs.geometry
    if g.d.to("mm").magnitude >= g.h.to("mm").magnitude:
        raise InconsistentInput(
            "la hauteur utile d doit etre inferieure a la hauteur totale h")
    if inputs.M_char.to("kN*m").magnitude < inputs.M_qp.to("kN*m").magnitude:
        raise InconsistentInput(
            "M_char doit majorer M_qp: la combinaison caracteristique ne peut "
            "pas etre inferieure a la quasi-permanente")
    if inputs.bars.count < 2:
        raise InconsistentInput(
            "un lit tendu compte au moins deux barres: l'entraxe d'une barre "
            "unique n'est pas defini, et §7.3.4 en a besoin")
    if inputs.links.legs < 2:
        raise InconsistentInput("un cadre compte au moins deux branches")
    if inputs.anchorage_available.to("mm").magnitude <= 0:
        raise InconsistentInput(
            "la longueur d'ancrage disponible doit etre strictement positive")


def _spec_de_dessin(inputs: BeamVerificationInput) -> BeamSectionSpec:
    """La coupe, telle qu'elle sera dessinee — et telle qu'elle est calculee."""
    return BeamSectionSpec(
        b=float(inputs.geometry.b.to("mm").magnitude),
        h=float(inputs.geometry.h.to("mm").magnitude),
        cover=float(inputs.cover.to("mm").magnitude),
        link_diameter=float(inputs.links.diameter.to("mm").magnitude),
        bottom=(BarRow(count=inputs.bars.count,
                       diameter=float(inputs.bars.diameter.to("mm").magnitude),
                       mark="A1"),),
        link_spacing=float(inputs.links.spacing.to("mm").magnitude),
        element=inputs.element,
        concrete_grade=inputs.concrete_grade,
        steel_grade=inputs.steel_grade,
        exposure_class=inputs.exposure_class.value,
    )


def _entraxe_du_modele(modele) -> Quantity:
    """L'entraxe REEL des barres tendues, lu sur la geometrie dessinee.

    On ne le recalcule pas: on lit les abscisses que le modele a fixees, et
    dont le DXF sortira. Calcul et dessin ne peuvent donc pas diverger — c'est
    la meme source.
    """
    barres = modele.barres
    if not barres:
        raise InconsistentInput("le modele geometrique ne porte aucune barre")
    y_min = min(b.y for b in barres)
    lit = sorted((b for b in barres if abs(b.y - y_min) < 1e-6),
                 key=lambda b: b.x)
    if len(lit) < 2:
        raise InconsistentInput(
            "le lit tendu compte moins de deux barres: l'entraxe n'est pas "
            "defini")
    return Q_(lit[1].x - lit[0].x, "mm")


def _tente(cle: str, appel) -> SectionOutcome:
    """Execute une section, ou dit honnetement pourquoi elle n'a pas tourne.

    `NationalAnnexIncomplete` ne devient PAS une exception ici: en mode
    exploratoire, une annexe incomplete doit laisser voir les autres sections.
    Elle devient `not_evaluated`, ce qui rend l'etude `incomplete` et interdit
    sa finalisation. Le refus explicite du mode strict, lui, appartient a
    `preflight_beam`, qui parle AVANT le calcul.

    `OutOfValidationDomain` remonte: sortir du domaine valide n'est pas une
    lacune du referentiel, c'est un choix d'entree que le produit refuse.

    `InconsistentInput` DEVIENT AUSSI `not_evaluated`, ET L'ARGUMENT EST LE
    SUIVANT: la coherence de l'ENTREE est etablie par `_exiger_coherence`,
    avant qu'aucun module ne tourne. Passe ce point, une incoherence signalee
    par un module ne porte donc plus sur ce que l'ingenieur a saisi, mais sur
    une grandeur DERIVEE — donc sur la consequence d'une verification amont non
    satisfaite.

    Le cas reel: sous-ferraillee, la poutre fait dire a `check_span_depth`
    « la dispense du §7.4.2 n'a pas de sens avant que la resistance soit
    acquise ». L'argument du module est juste. Mais laisser remonter cette
    exception ferait REFUSER l'etude entiere, et l'ingenieur ne verrait jamais
    la flexion rouge — c'est-a-dire precisement le defaut qu'il doit corriger,
    et dont la correction fera disparaitre le silence de la dispense.
    """
    titre = dict(SECTION_ORDER)[cle]
    try:
        return _depuis_rapport(cle, appel())
    except (NationalAnnexIncomplete, InconsistentInput) as exc:
        return SectionOutcome(
            key=cle, title=titre, basis=SECTION_BASIS[cle],
            status="not_evaluated", utilisation=None,
            reason=str(exc).strip().splitlines()[0])


def _depuis_rapport(cle: str, design: Any) -> SectionOutcome:
    """Traduit le rapport d'un module en verdict de section."""
    titre = dict(SECTION_ORDER)[cle]
    rapport = design.report
    gouvernante = rapport.governing
    passe = rapport.passed
    remede = None if passe else _remede(cle, gouvernante)
    return SectionOutcome(
        key=cle, title=titre, basis=SECTION_BASIS[cle],
        status="passed" if passe else "failed",
        utilisation=rapport.max_utilisation,
        remedy=remede, design=design)


def _remede(cle: str, gouvernante) -> str:
    """Ce qu'il faut faire. Un rouge sans remede n'aide personne."""
    if cle == "deflection":
        return REMEDE_FLECHE
    if cle == "anchorage":
        return REMEDE_ANCRAGE
    propre = getattr(gouvernante, "remedy", None)
    if propre:
        return propre
    return ("Verification non satisfaite: revoir le ferraillage ou la "
            "geometrie de la section.")


@dataclass(frozen=True, slots=True)
class AnchorageVerification:
    """`AnchorageDesign` plus le verdict qu'il ne rend pas lui-meme.

    On NE GREFFE PAS `report` sur `AnchorageDesign` par `setattr`: ce serait
    modifier depuis l'exterieur la forme d'un objet qu'un autre module possede,
    et le premier `slots=True` ajoute la-bas ferait tomber l'orchestrateur sans
    que rien ne relie la panne a sa cause. Le porteur est donc explicite, et il
    expose ce que la note attend: un journal et un rapport.
    """

    design: Any
    report: Any

    @property
    def journal(self):
        return self.design.journal

    @property
    def utilisation(self) -> float:
        return self.report.max_utilisation


def _verifier_ancrage(inputs: BeamVerificationInput, beton, acier,
                      params: ParameterSet, flexion) -> AnchorageVerification:
    """L'ancrage, avec le verdict que `design_anchorage` ne rend pas.

    LE SEUL ENDROIT DE CE MODULE QUI COMPARE DEUX GRANDEURS, et il est assume:
    `design_anchorage` produit `l_bd`, la longueur REQUISE. Aucune formule
    n'est reimplementee — on confronte cette longueur a celle que l'ingenieur
    declare disponible, parce que lui seul connait l'about dont il dispose.
    """
    from ..traceability import EC2
    from ..verification import Check, VerificationReport

    # LA REDUCTION DE §8.4.3 NE S'APPLIQUE QUE SI LA SECTION EST FERRAILLEE.
    #
    # `sigma_sd = f_yd · A_req/A_prov` dit « la barre n'est pas pleinement
    # sollicitee parce qu'on en a mis plus que necessaire ». Sous-ferraillee,
    # le rapport depasse 1 et la phrase n'a plus de sens: `design_anchorage`
    # refuse, a juste titre.
    #
    # Mesure du 01/09: en transmettant le couple sans condition, une poutre
    # sous-ferraillee faisait REFUSER l'etude entiere au lieu d'afficher une
    # flexion rouge — le defaut le plus utile a voir devenait le plus
    # invisible. On omet donc le couple dans ce cas: `sigma_sd` retombe sur
    # `f_yd`, la barre pleinement sollicitee, ce qui allonge l'ancrage requis.
    # C'est le sens conservatif, et c'est le seul defendable ici.
    sous_ferraille = (flexion.As_provided.to("mm**2").magnitude
                      < flexion.As_required.to("mm**2").magnitude)
    reduction = {} if sous_ferraille else {
        "A_s_required": flexion.As_required,
        "A_s_provided": flexion.As_provided,
    }
    design = design_anchorage(
        concrete=beton, steel=acier, phi=inputs.bars.diameter, params=params,
        bond_condition=inputs.bond_condition,
        coefficients=inputs.anchorage_coefficients,
        element=inputs.element, **reduction)

    rapport = VerificationReport(element=inputs.element)
    rapport.add(Check.from_ratio(
        name="Longueur d'ancrage",
        acting=design.l_bd,
        resisting=inputs.anchorage_available,
        clause=EC2("§8.4.4"),
        detail="l_bd requise confrontee a la longueur declaree disponible.",
        remedy=REMEDE_ANCRAGE,
    ))
    return AnchorageVerification(design=design, report=rapport)


def _statut_global(sections: tuple[SectionOutcome, ...]) -> str:
    """`failed` prime sur `incomplete`, qui prime sur `passed`.

    L'ORDRE N'EST PAS ARBITRAIRE, et j'ai commence par le poser a l'envers.

    Un rouge est un defaut CERTAIN et ACTIONNABLE; un silence est une
    incertitude. Quand les deux coexistent, ils ne sont d'ailleurs presque
    jamais independants: c'est le rouge qui produit le silence — une poutre
    sous-ferraillee fait taire la dispense de fleche, parce que la dispense n'a
    pas de sens avant que la resistance soit acquise. Titrer « incomplete »
    mettrait la consequence devant la cause et cacherait la seule chose que
    l'ingenieur peut corriger.

    Aucun des deux ne se finalise: `may_be_finalised` exige les CINQ vertes.
    """
    if any(s.status == "failed" for s in sections):
        return "failed"
    if any(s.status == "not_evaluated" for s in sections):
        return "incomplete"
    return "passed"


def _empreinte(inputs: BeamVerificationInput) -> str:
    """L'empreinte de l'entree gelee. Deux etudes identiques la partagent."""
    charge = json.dumps(inputs.to_dict(), sort_keys=True,
                        ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(charge.encode("utf-8")).hexdigest()
