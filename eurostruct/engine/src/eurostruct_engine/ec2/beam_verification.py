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

LES CINQ ISSUES, ET POURQUOI ELLES NE SE CONFONDENT PAS
--------------------------------------------------------
1. **Refus** — l'entree est incoherente, ou hors du domaine de validation. Rien
   n'est produit. Une exception, pas un resultat. TOUTE incoherence de saisie
   passe par la, sans exception attrapee en cours de route.
2. **Refus explicite** — un parametre national manque. En mode strict, c'est
   `preflight_beam` qui le dit AVANT le calcul, en une seule reponse pour les
   cinq modules: echouer cinq fois de suite n'apprend rien a personne.
3. **`failed`** — la verification a tourne et n'est pas satisfaite. Taux
   d'utilisation ET remede.
4. **`additional_analysis_required`** — la verification a tourne, et sa
   conclusion est qu'une AUTRE analyse est due. Le seul cas aujourd'hui est la
   dispense de fleche non acquise: ce n'est ni un echec de la poutre, ni un
   silence. L'etude devient `incomplete`.
5. **`not_evaluated`** — la verification n'a pas pu tourner. Elle n'est JAMAIS
   « conforme ». Quand la cause est une dependance, la raison est un CODE:
   `prerequisite_failed:flexure`.

UNE ETUDE VERTE N'EST PAS UNE ETUDE FINALISABLE
------------------------------------------------
C'est le piege central de ce module. Une etude peut etre numeriquement verte
sur les cinq sections et rester EXPLORATOIRE — parce qu'elle a tourne hors mode
strict, ou parce que le preflight n'etait pas satisfait. `may_be_finalised`
exige donc QUATRE choses:

    cinq sections satisfaites
    ET mode strict
    ET preflight pret (confirmations reellement obtenues du provider)
    ET aucune analyse complementaire due

Le resultat porte lui-meme `strict_ndp`, le pays, la region, la date normative,
l'etat du preflight et l'empreinte de l'instantane normatif: sans eux, rien en
aval ne pourrait distinguer un vert exploratoire d'un vert signable.

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
    "MENTION_DISPENSE_NON_ACQUISE",
    "STATUT_ANALYSE_REQUISE",
    "STATUT_ECHOUE",
    "STATUT_NON_EVALUE",
    "STATUT_PASSE",
    "BeamGeometry",
    "BeamPreflight",
    "BeamVerification",
    "BeamVerificationInput",
    "LongitudinalBars",
    "ModuleBlocker",
    "SectionOutcome",
    "TransverseLinks",
    "preflight_beam",
    "required_parameters_for_beam",
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
#: LES QUATRE ETATS D'UNE SECTION, ET LE TROISIEME N'EST PAS UN ECHEC.
#:
#: `additional_analysis_required` existe parce que la dispense de fleche du
#: §7.4.2 ne se range dans aucune des trois autres cases. Le module a TOURNE —
#: ce n'est pas `not_evaluated`. Et il conclut que la dispense n'est pas
#: acquise, ce qui ne dit RIEN sur la conformite de la poutre: seulement qu'un
#: calcul explicite de fleche (§7.4.3) reste a faire. L'appeler `failed`
#: ferait refuser des poutres correctes.
STATUT_PASSE = "passed"
STATUT_ECHOUE = "failed"
STATUT_ANALYSE_REQUISE = "additional_analysis_required"
STATUT_NON_EVALUE = "not_evaluated"

#: La phrase exacte que l'interface et la note reprennent, mot pour mot.
MENTION_DISPENSE_NON_ACQUISE = (
    "Dispense non acquise — calcul explicite de la fleche requis. "
    "Cela ne constitue pas, a lui seul, un echec de la poutre."
)


@dataclass(frozen=True, slots=True)
class SectionOutcome:
    """Une des cinq sections, avec son verdict et de quoi le justifier."""

    key: str
    title: str
    basis: str
    #: L'un des quatre STATUT_* ci-dessus. JAMAIS autre chose.
    status: str
    #: `None` quand la section n'a pas tourne: un taux suppose un calcul.
    utilisation: float | None
    #: Ce qu'il faut faire quand c'est rouge, ou quelle analyse reste due.
    remedy: str | None = None
    #: Pourquoi la section n'a pas tourne. Code machine quand la cause est une
    #: dependance: `prerequisite_failed:<section>`.
    reason: str | None = None
    #: Le resultat du module, porteur du journal. La note s'en sert.
    design: Any = None

    @property
    def is_satisfied(self) -> bool:
        """Vrai UNIQUEMENT si la verification a tourne et est satisfaite.

        Ni un silence ni une analyse due ne comptent pour une satisfaction.
        """
        return self.status == STATUT_PASSE

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "title": self.title, "basis": self.basis,
            "status": self.status, "utilisation": self.utilisation,
            "remedy": self.remedy, "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class BeamVerification:
    """L'etude complete: cinq sections, un statut, un contexte normatif.

    LE CONTEXTE NORMATIF FAIT PARTIE DU RESULTAT, PAS DE SON DECOR.

    Une etude peut etre numeriquement verte et rester EXPLORATOIRE. Sans
    `strict_ndp`, `country`, `region`, `ndp_as_of` et l'etat du preflight
    portes par le resultat lui-meme, rien en aval — ni la base, ni la note, ni
    l'ecran — ne peut distinguer les deux. Ils sont donc ici, et
    `may_be_finalised` les lit.
    """

    element: str
    inputs: BeamVerificationInput
    sections: tuple[SectionOutcome, ...]
    #: `passed`, `failed` ou `incomplete`.
    status: str
    inputs_hash: str
    bar_spacing: Quantity
    drawing_spec: BeamSectionSpec
    ndp_summary: dict[str, Any]
    #: --- le contexte normatif, sans lequel un vert ne veut rien dire -------
    strict_ndp: bool = False
    country: str = ""
    region: str | None = None
    ndp_as_of: date | None = None
    preflight_ready: bool = False
    #: Empreinte de l'instantane normatif: pays, region, date, mode strict,
    #: annexes en vigueur et leurs editions, statut de chaque parametre.
    ndp_snapshot_id: str = ""
    engine_version: str = ENGINE_VERSION
    execution_identity: str | None = None

    @property
    def is_exploratory(self) -> bool:
        """Une etude est exploratoire des que le referentiel ne tient pas.

        C'est le cas des qu'on est hors mode strict, ou que le preflight n'est
        pas pret. Le vert numerique n'y change rien.
        """
        return not (self.strict_ndp and self.preflight_ready)

    @property
    def may_be_finalised(self) -> bool:
        """Les quatre conditions, et il en faut QUATRE.

        Une etude peut etre numeriquement verte tout en restant exploratoire:
        c'est le piege que cette propriete existe pour fermer. Il ne suffit
        donc pas que les cinq sections soient satisfaites — il faut aussi que
        le referentiel tienne (mode strict ET preflight pret, confirmations
        reellement obtenues), et qu'aucune analyse complementaire ne reste due.

        `additional_analysis_required` compte comme une analyse due: la
        dispense de fleche non acquise n'est pas un echec, mais elle n'autorise
        pas davantage a signer.
        """
        return (
            all(s.is_satisfied for s in self.sections)
            and self.strict_ndp
            and self.preflight_ready
            and not self.requires_additional_analysis
        )

    @property
    def requires_additional_analysis(self) -> bool:
        return any(s.status == STATUT_ANALYSE_REQUISE for s in self.sections)

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
            "is_exploratory": self.is_exploratory,
            "requires_additional_analysis": self.requires_additional_analysis,
            "strict_ndp": self.strict_ndp,
            "country": self.country,
            "region": self.region,
            "ndp_as_of": (self.ndp_as_of.isoformat()
                          if self.ndp_as_of is not None else None),
            "preflight_ready": self.preflight_ready,
            "ndp_snapshot_id": self.ndp_snapshot_id,
            "fingerprint": self.fingerprint,
        }

    @property
    def fingerprint(self) -> str:
        """L'empreinte de l'ETUDE: entree gelee ET contexte normatif.

        Deux etudes aux memes nombres mais sous un pays, une region, une date
        ou un mode strict differents ne sont pas la meme etude, et ne doivent
        pas partager une empreinte.
        """
        return hashlib.sha256(
            f"{self.inputs_hash}:{self.ndp_snapshot_id}".encode()
        ).hexdigest()


# ---------------------------------------------------------------------------
# Le preflight: cinq modules, UNE reponse — et il est STRICT par defaut
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ModuleBlocker:
    """Un parametre qui empeche le calcul, rattache au module qui le reclame.

    IL NE DUPLIQUE PAS `ndp.registry.BlockingParameter`, IL L'HABILLE.

    Le registre sait deja POURQUOI un parametre bloque, et il le dit par un
    code: `annex_missing`, `missing`, `deprecated`, `not_representable`,
    `pending_verification`. Ce qu'il ignore, c'est QUI le reclame — un meme
    `gamma_C` sert quatre modules sur cinq. Cette classe ajoute cette seule
    information et recopie le reste tel quel.

    Une premiere redaction devinait la raison en cherchant « not_representable »
    dans le TEXTE d'une exception. Un code de raison typé existait a cote; s'en
    remettre a une sous-chaine aurait fait dependre le produit du libelle d'un
    message d'erreur.
    """

    module: str
    parameter: str
    clause: str
    annex: str
    reason: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "module": self.module, "parameter": self.parameter,
            "clause": self.clause, "annex": self.annex,
            "reason": self.reason, "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class BeamPreflight:
    """Ce qui manque, pour les cinq modules a la fois."""

    country: str
    region: str | None
    as_of: date
    strict: bool
    blocking: tuple[ModuleBlocker, ...]
    required: tuple[str, ...] = ()
    #: Qui a repondu sur les confirmations, ou `None` si personne n'a ete
    #: interroge. Un preflight strict SANS provider n'est pas un preflight
    #: strict satisfait: c'est un preflight strict qui bloque.
    provider_identity: str | None = None
    provider_is_fictional: bool | None = None

    @property
    def ready(self) -> bool:
        return not self.blocking

    def to_dict(self) -> dict[str, Any]:
        return {
            "country": self.country,
            "region": self.region,
            "as_of": self.as_of.isoformat(),
            "strict": self.strict,
            "ready": self.ready,
            "blocking": [b.to_dict() for b in self.blocking],
            "required": list(self.required),
            "provider_identity": self.provider_identity,
            "provider_is_fictional": self.provider_is_fictional,
        }


#: Les parametres que chaque module reclame. Ils viennent des modules
#: eux-memes: recopier une liste ici la ferait diverger au premier ajout.
#:
#: LE PAYS CHANGE LA REPONSE, ET L'OUBLIER REND LE PREFLIGHT FAUX.
#:
#: `beam_shear.required_parameters` prend un `country_code`: un pays dont les
#: regles TYPEES sont transcrites — `be.ec2.cot_theta_max` et les six autres —
#: n'exige plus les scalaires qu'elles remplacent. Ces scalaires sont
#: `deprecated` ou `not_representable`, donc bloquants dans TOUS les modes.
#:
#: Mesure du 01/09: en omettant le pays, le preflight belge rendait sept
#: bloquants que le calcul ne reclame pas — il refusait un travail que le
#: moteur execute sans broncher. Un preflight plus severe que le calcul est
#: aussi faux qu'un preflight plus permissif: il fait renoncer pour rien.
def _required_by_module(country_code: str | None = None
                        ) -> dict[str, tuple[str, ...]]:
    from ..basis import DesignSituation

    persistent = DesignSituation.PERSISTENT
    return {
        "flexure": _flexure_params(persistent),
        "shear": _shear_params(persistent, country_code),
        "anchorage": _anchorage_params(persistent),
        "serviceability": _sls_params(),
        "deflection": _deflection_params(),
    }


def required_parameters_for_beam(country_code: str | None = None
                                 ) -> tuple[str, ...]:
    """L'UNION des parametres que les cinq modules reclament, triee."""
    union: set[str] = set()
    for cles in _required_by_module(country_code).values():
        union.update(cles)
    return tuple(sorted(union))


def preflight_beam(*, country: str, as_of: date, region: str | None = None,
                   strict: bool = True,
                   provider: Any = None) -> BeamPreflight:
    """Reunit en UNE reponse ce qui bloque les cinq modules.

    Le mode strict ne doit pas echouer cinq fois de suite: un ingenieur qui
    corrige un parametre pour se voir refuser sur le suivant, puis le suivant,
    ne sait jamais ou il en est.

    `strict` VAUT VRAI PAR DEFAUT, ET C'EST LE SUJET.

    Une premiere redaction chargeait le jeu avec `strict=False` en dur. Elle ne
    signalait donc AUCUNE valeur `pending_verification` — un preflight qui se
    declare pret sur un referentiel dont rien n'est releve. Un preflight
    permissif par defaut est pire que pas de preflight: il rassure.

    `region` EST TRANSMISE. Elle ne l'etait pas: le jeu revenait sans elle, et
    une region qui modifie un parametre etait ignoree en silence.

    LES CONFIRMATIONS VIENNENT DU VRAI PROVIDER, quand il y en a un. Sans
    provider, ou avec des confirmations insuffisantes, les valeurs en attente
    RESTENT bloquantes: c'est le fait produit sur le referentiel livre.

    `not_representable` bloque MEME EN MODE NON STRICT: une formule que le
    modele scalaire ne sait pas porter ne devient pas portable parce qu'on a
    baisse les exigences.

    Aucune valeur n'est confirmee ici, et aucun ingenieur n'est sollicite.
    """
    jeu = load_parameter_set(country, region=region, strict=strict, as_of=as_of)
    pays = jeu.registry.country_code
    cles = required_parameters_for_beam(pays)

    identite = None
    fictif = None
    if provider is not None:
        identite = getattr(provider, "provider_identity", None)
        fictif = getattr(provider, "is_fictional", None)
        if strict:
            # LE PONT EXISTANT, PAS UN NOUVEAU. `confirmer_depuis_le_provider`
            # confronte chaque parametre aux attestations qui le visent et rend
            # un jeu ou SEULS les parametres confirmes sont utilisables.
            from ..ndp.passerelle import confirmer_depuis_le_provider

            jeu, _ = confirmer_depuis_le_provider(jeu, cles, provider=provider)

    rapport = jeu.preflight(cles)

    # QUI RECLAME QUOI. Un meme parametre sert plusieurs modules; il apparait
    # alors une fois par module, parce que c'est module par module qu'on
    # decide d'un contournement.
    par_module = _required_by_module(pays)
    bloquants: list[ModuleBlocker] = []
    for bp in rapport.blocking:
        for module, demandes in par_module.items():
            if bp.key in demandes:
                bloquants.append(ModuleBlocker(
                    module=module,
                    parameter=bp.key,
                    # `clause` du registre est une CHAINE, pas un `Clause`.
                    # Appeler `.cite()` dessus levait un AttributeError — la
                    # premiere execution du preflight l'a dit.
                    clause=bp.clause or bp.parameter_name,
                    annex=bp.national_annex_reference or bp.standard,
                    reason=bp.reason,
                    detail=bp.detail,
                ))

    return BeamPreflight(
        country=pays,
        region=region,
        as_of=as_of,
        strict=strict,
        blocking=tuple(sorted(bloquants, key=lambda b: (b.module, b.parameter))),
        required=cles,
        provider_identity=identite,
        provider_is_fictional=fictif,
    )

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
    #:
    #: LA DEPENDANCE EST DECLAREE, PAS DEDUITE D'UNE EXCEPTION. `check_span_depth`
    #: refuse — a juste titre — une section sous-ferraillee: « la dispense n'a
    #: pas de sens avant que la resistance soit acquise ». On ne l'APPELLE donc
    #: pas dans ce cas, au lieu d'attraper son refus et d'en deviner la cause.
    manque = _prerequis_de_la_fleche(resultats["flexure"], flexion)
    if manque is not None:
        resultats["deflection"] = _section_non_evaluee("deflection", manque)
    else:
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
    prevol = params.preflight(
        required_parameters_for_beam(params.registry.country_code))
    return BeamVerification(
        element=inputs.element,
        inputs=inputs,
        sections=sections,
        status=_statut_global(sections),
        inputs_hash=_empreinte(inputs),
        bar_spacing=entraxe,
        drawing_spec=spec,
        ndp_summary=params.summary(),
        strict_ndp=params.strict,
        country=params.registry.country_code,
        region=params.region,
        ndp_as_of=params.as_of,
        preflight_ready=prevol.ok,
        ndp_snapshot_id=_empreinte_normative(params),
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

    # --- les grandeurs strictement positives -------------------------------
    for nom, q, unite in (
        ("b", g.b, "mm"), ("h", g.h, "mm"), ("d", g.d, "mm"),
        ("l_eff", g.l_eff, "mm"),
        ("le diametre des barres", inputs.bars.diameter, "mm"),
        ("le diametre des cadres", inputs.links.diameter, "mm"),
        ("l'espacement des cadres", inputs.links.spacing, "mm"),
        ("l'enrobage", inputs.cover, "mm"),
        ("la longueur d'ancrage disponible", inputs.anchorage_available, "mm"),
    ):
        if q.to(unite).magnitude <= 0:
            raise InconsistentInput(f"{nom} doit etre strictement positif")

    # --- les sollicitations, qui peuvent etre nulles mais jamais negatives --
    for nom, q, unite in (
        ("M_Ed", inputs.M_Ed, "kN*m"), ("V_Ed", inputs.V_Ed, "kN"),
        ("M_char", inputs.M_char, "kN*m"), ("M_qp", inputs.M_qp, "kN*m"),
    ):
        if q.to(unite).magnitude < 0:
            raise InconsistentInput(f"{nom} ne peut pas etre negatif")

    if inputs.phi_creep < 0:
        raise InconsistentInput(
            "le coefficient de fluage phi ne peut pas etre negatif")

    if inputs.cot_theta <= 0:
        raise InconsistentInput("cot(theta) doit etre strictement positif")

    # --- ce qui se contredit -----------------------------------------------
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

    # --- l'enrobage doit laisser de la place aux barres ---------------------
    # Deux fois (enrobage + cadre + demi-barre) doit tenir dans la largeur,
    # sinon la coupe n'existe pas: le modele geometrique placerait les barres
    # a l'exterieur du beton sans se plaindre, et le dessin serait faux.
    largeur = g.b.to("mm").magnitude
    emprise = 2.0 * (inputs.cover.to("mm").magnitude
                     + inputs.links.diameter.to("mm").magnitude
                     + inputs.bars.diameter.to("mm").magnitude / 2.0)
    if emprise >= largeur:
        raise InconsistentInput(
            f"enrobage geometriquement impossible: l'emprise des cadres et des "
            f"barres ({emprise:g} mm) atteint ou depasse la largeur "
            f"({largeur:g} mm)")


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

    `InconsistentInput` N'EST PAS CAPTUREE, ET C'EST UNE CORRECTION.

    Une redaction precedente l'attrapait ici et la transformait en
    `not_evaluated`. C'etait trop large: elle aurait avale une VRAIE entree
    invalide qu'`_exiger_coherence` n'aurait pas anticipee — un moment negatif,
    un fluage negatif, ou n'importe quel controle qu'un module ajouterait plus
    tard. L'etude aurait alors ete conservee comme « incomplete » au lieu
    d'etre refusee, et une saisie fausse serait devenue un dossier.

    La seule dependance legitime — la dispense de fleche qui n'a pas de sens
    sous une flexion non satisfaite — est desormais DECLAREE en amont: on
    n'appelle pas le module, au lieu d'attraper son refus et d'en deviner la
    cause dans un texte.
    """
    titre = dict(SECTION_ORDER)[cle]
    try:
        return _depuis_rapport(cle, appel())
    except NationalAnnexIncomplete as exc:
        return SectionOutcome(
            key=cle, title=titre, basis=SECTION_BASIS[cle],
            status=STATUT_NON_EVALUE, utilisation=None,
            reason=str(exc).strip().splitlines()[0])


def _section_non_evaluee(cle: str, raison: str) -> SectionOutcome:
    """Une section qu'on n'a pas appelee, et qui dit pourquoi par un CODE."""
    return SectionOutcome(
        key=cle, title=dict(SECTION_ORDER)[cle], basis=SECTION_BASIS[cle],
        status=STATUT_NON_EVALUE, utilisation=None, reason=raison)


def _prerequis_de_la_fleche(flexion: SectionOutcome, design) -> str | None:
    """Le prerequis de §7.4.2, ou `None` s'il est tenu.

    LA RAISON EST UN CODE MACHINE, PAS UNE PHRASE. `prerequisite_failed:flexure`
    se teste, se traduit et se stocke; un message d'erreur recopie ne fait
    aucune des trois.
    """
    if flexion.status != STATUT_PASSE:
        return "prerequisite_failed:flexure"
    if (design.As_provided.to("mm**2").magnitude
            < design.As_required.to("mm**2").magnitude):
        return "prerequisite_failed:flexure"
    return None


def _depuis_rapport(cle: str, design: Any) -> SectionOutcome:
    """Traduit le rapport d'un module en verdict de section.

    LA DISPENSE DE FLECHE A SON PROPRE ETAT, ET CE N'EST PAS UN ECHEC.

    `check_span_depth` a bien TOURNE quand il conclut que la dispense n'est pas
    acquise: ce n'est donc pas `not_evaluated`. Et il ne dit rien sur la
    conformite de la poutre — seulement qu'un calcul explicite de fleche reste
    a faire: ce n'est donc pas `failed` non plus. Ranger ce cas dans l'une des
    deux cases ferait refuser des poutres correctes.
    """
    titre = dict(SECTION_ORDER)[cle]
    rapport = design.report
    gouvernante = rapport.governing
    passe = rapport.passed

    if cle == "deflection" and not passe:
        return SectionOutcome(
            key=cle, title=titre, basis=SECTION_BASIS[cle],
            status=STATUT_ANALYSE_REQUISE,
            utilisation=rapport.max_utilisation,
            remedy=MENTION_DISPENSE_NON_ACQUISE, design=design)

    remede = None if passe else _remede(cle, gouvernante)
    return SectionOutcome(
        key=cle, title=titre, basis=SECTION_BASIS[cle],
        status=STATUT_PASSE if passe else STATUT_ECHOUE,
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

    `additional_analysis_required` REJOINT `incomplete`, PAS `failed`. Une
    dispense de fleche non acquise laisse l'etude inachevee — il manque un
    calcul — sans rien dire de la conformite de la poutre.
    """
    if any(s.status == STATUT_ECHOUE for s in sections):
        return "failed"
    if any(s.status in (STATUT_NON_EVALUE, STATUT_ANALYSE_REQUISE)
           for s in sections):
        return "incomplete"
    return "passed"


def _empreinte(inputs: BeamVerificationInput) -> str:
    """L'empreinte de l'entree gelee. Deux etudes identiques la partagent."""
    charge = json.dumps(inputs.to_dict(), sort_keys=True,
                        ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(charge.encode("utf-8")).hexdigest()


def _empreinte_normative(params: ParameterSet) -> str:
    """L'empreinte de l'INSTANTANE normatif.

    `summary()` porte deja le pays, la region, la date de reference, le mode
    strict, les annexes en vigueur avec leurs editions et le statut de chaque
    parametre. Le hacher revient donc a dater le referentiel employe: deux
    etudes menees sous des annexes differentes, ou sous la meme annexe a des
    dates ou des regions differentes, ne partagent pas cette empreinte.
    """
    charge = json.dumps(params.summary(), sort_keys=True,
                        ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(charge.encode("utf-8")).hexdigest()
