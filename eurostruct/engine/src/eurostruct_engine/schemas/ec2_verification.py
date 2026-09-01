"""Le contrat HTTP de la vérification complète d'une poutre.

CE QUE LE CORPS PORTE, ET CE QU'IL NE PORTERA JAMAIS
------------------------------------------------------
La règle tient en une phrase : **le corps porte ce que l'ingénieur SAIT,
jamais ce que le serveur CALCULE ni ce que le projet FIXE.**

Trois familles de champs sont donc absentes, et chaque absence ferme un défaut
précis.

``status``, ``may_be_finalised``, ``preflight_ready``, ``is_exploratory``
    Ce sont des **conclusions**. Les accepter du corps laisserait un client
    décider de sa propre conformité — et une étude exploratoire se déclarer
    signable.

``inputs_hash``, ``ndp_snapshot_id``, ``fingerprint``, ``provider_identity``
    Ce sont des **preuves**. Une empreinte fournie par celui qu'elle engage ne
    prouve rien. L'identité du provider vient du composition root authentifié,
    jamais du corps : la laisser passer reviendrait à choisir qui atteste.

``A_s``, ``A_sw``, ``bar_spacing``
    Ce sont des grandeurs **dérivées**. `A_s` se déduit des barres, `A_sw` des
    branches, l'entraxe du modèle géométrique partagé. Deux sources pour un
    même fait divergent un jour — et ce jour-là, le produit dessine autre chose
    que ce qu'il a calculé.

``country``, ``region``, ``ndp_as_of``
    Ils décident **quelle édition d'Annexe Nationale s'applique**. Ils sont
    figés sur le projet. Mesuré sur la route de flexion avant correction : un
    corps annonçant ``country=FR`` sur un projet belge obtenait un 201, et la
    ligne enregistrée se contredisait elle-même.

``Strict`` REFUSE au lieu d'ignorer, et la nuance compte : un champ
silencieusement écarté laisse le client croire qu'il a eu un effet. Un 422 lui
dit que non.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import QuantityDTO, Strict

__all__ = [
    "BeamGeometryDTO",
    "Ec2BeamVerificationRequest",
    "Ec2BeamVerificationResponse",
    "LongitudinalBarsDTO",
    "PreflightBlockerDTO",
    "SectionOutcomeDTO",
    "TransverseLinksDTO",
    "VerificationMaterialsDTO",
]


class BeamGeometryDTO(Strict):
    """La section et la portée, une seule fois pour les cinq modules."""

    b: QuantityDTO
    h: QuantityDTO
    d: QuantityDTO
    l_eff: QuantityDTO = Field(
        description="Portée utile, §5.3.2.2. Elle sert à la dispense du "
                    "calcul de flèche.")


class VerificationMaterialsDTO(Strict):
    concrete_grade: str = Field(examples=["C30/37"])
    steel_grade: str = Field(examples=["B500B"])


class LongitudinalBarsDTO(Strict):
    """Le lit tendu. ``A_s`` s'en DÉRIVE et ne se saisit jamais à côté."""

    count: int = Field(ge=1, le=40)
    diameter: QuantityDTO


class TransverseLinksDTO(Strict):
    """Les cadres. ``A_sw`` se dérive des branches et du diamètre."""

    legs: int = Field(ge=1, le=12)
    diameter: QuantityDTO
    spacing: QuantityDTO


class Ec2BeamVerificationRequest(Strict):
    """Une vérification complète **sur un projet**.

    Elle ne nomme aucun référentiel : voir le docstring du module.
    """

    element: str = Field(default="poutre", max_length=100)
    strict_ndp: bool = Field(
        default=True,
        description="Quand vrai, un paramètre national non confirmé bloque "
                    "AVANT le calcul, et rien n'est enregistré.")

    geometry: BeamGeometryDTO
    materials: VerificationMaterialsDTO

    M_Ed: QuantityDTO
    V_Ed: QuantityDTO
    M_char: QuantityDTO = Field(
        description="Moment sous combinaison caractéristique. Il majore "
                    "M_qp par nature.")
    M_qp: QuantityDTO = Field(
        description="Moment sous combinaison quasi-permanente.")

    phi_creep: float = Field(
        description="Coefficient de fluage φ(∞,t0), §3.1.4. Fourni par "
                    "l'ingénieur, jamais deviné : il dépend du rayon moyen, "
                    "de l'humidité et de l'âge au chargement.")
    exposure_class: str = Field(examples=["XC3"])
    structural_system: str = Field(
        examples=["simply_supported"],
        description="Ligne du Tableau 7.4N. Aucun défaut.")
    supports_brittle_partitions: bool = Field(
        default=False,
        description="Aucune géométrie ne le révèle : c'est une donnée.")

    bars: LongitudinalBarsDTO
    links: TransverseLinksDTO

    cot_theta: float = Field(
        description="Inclinaison des bielles retenue par l'ingénieur. Une "
                    "borne nationale peut la refuser, et c'est un refus juste.")
    cover: QuantityDTO
    anchorage_available: QuantityDTO = Field(
        description="Longueur d'ancrage réellement disponible. L'ingénieur "
                    "seul connaît l'about dont il dispose ; sans elle, "
                    "l'ancrage serait le seul chapitre sans verdict.")

    b_eff_over_b_w: float | None = None
    bond_condition: str = Field(default="good")


class SectionOutcomeDTO(Strict):
    """Le verdict d'un des cinq chapitres."""

    key: str
    title: str
    basis: str
    status: str = Field(
        description="passed | failed | additional_analysis_required | "
                    "not_evaluated. Une section non évaluée n'est JAMAIS "
                    "conforme.")
    utilisation: float | None = Field(
        default=None,
        description="Absent quand la section n'a pas tourné : un taux "
                    "suppose un calcul.")
    remedy: str | None = None
    reason: str | None = Field(
        default=None,
        description="Code machine quand la cause est une dépendance, "
                    "p. ex. « prerequisite_failed:flexure ».")


class PreflightBlockerDTO(Strict):
    """Un paramètre qui empêche le calcul, et le module qui le réclame."""

    module: str
    parameter: str
    clause: str
    annex: str
    reason: str
    detail: str


class Ec2BeamVerificationResponse(Strict):
    """L'étude enregistrée, telle que le serveur la rend et la relit."""

    calculation_id: str
    element: str
    status: str = Field(description="passed | failed | incomplete")
    sections: tuple[SectionOutcomeDTO, ...]

    #: --- le contexte normatif, sans lequel un vert ne veut rien dire -------
    strict_ndp: bool
    country: str
    region: str | None
    ndp_as_of: str
    preflight_ready: bool
    is_exploratory: bool
    may_be_finalised: bool
    requires_additional_analysis: bool

    inputs_hash: str
    ndp_snapshot_id: str
    fingerprint: str

    engine_version: str
    engine_build_sha: str
    execution_identity: str
    max_utilisation: float
    bar_spacing: QuantityDTO

    #: LA MENTION EST DANS LA RÉPONSE, pas seulement dans l'interface: une note
    #: produite par un autre client doit la porter aussi.
    mention: str | None = None
    notice: str
    inputs: dict[str, Any] = Field(default_factory=dict)
