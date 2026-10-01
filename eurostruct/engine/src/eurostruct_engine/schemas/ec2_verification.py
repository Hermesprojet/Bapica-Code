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

from typing import Any, Final

from pydantic import Field, model_validator

from .common import ProvenanceDTO, QuantityDTO, Strict

__all__ = [
    "PROVENANCE_CHEMINS",
    "AnchorageCoefficientsDTO",
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


class AnchorageCoefficientsDTO(Strict):
    """Les six coefficients du Tableau 8.2 — et 8.3 pour alpha_6 — déclarés.

    ILS SONT TOUS LES SIX, OU AUCUN. Une valeur inférieure à 1,0 est une
    affirmation sur le façonnage (crochet, enrobage, confinement) dont
    l'ingénieur répond ; le moteur refuse une valeur hors du domaine du
    tableau. Absents, le moteur retient 1,0 pour chacun — la lecture
    conservative de chaque ligne — et le dit dans son journal.
    """

    alpha_1: float = Field(description="Forme de la barre, §8.4.4, Fig. 8.1.")
    alpha_2: float = Field(description="Enrobage.")
    alpha_3: float = Field(description="Confinement par armatures transversales non soudées.")
    alpha_4: float = Field(description="Confinement par armatures transversales soudées.")
    alpha_5: float = Field(description="Confinement par pression transversale.")
    alpha_6: float = Field(
        description="Proportion de barres recouvertes dans la même section, "
                    "Tableau 8.3.")


#: LES ENTREES QU'UN DOCUMENT PEUT FOURNIR, ET ELLES SEULES.
#:
#: Ce sont les chemins du contrat qu'une valeur lue sur un plan ou un cahier
#: des charges, puis CONFIRMEE par une personne nommee, peut renseigner. Les
#: autres n'y figurent pas, et l'absence est voulue: ``geometry.d`` est une
#: grandeur DERIVEE (hauteur, enrobage, diametres) que le produit ne derive
#: jamais a la place de l'ingenieur; les sollicitations (``M_Ed``, ``V_Ed``…)
#: ne se lisent pas sur un plan — une charge n'est pas un moment.
PROVENANCE_CHEMINS: Final[tuple[str, ...]] = (
    "geometry.b", "geometry.h", "geometry.l_eff",
    "materials.concrete_grade", "materials.steel_grade",
    "exposure_class", "cover",
    "bars.count", "bars.diameter", "links.diameter", "links.spacing",
)


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
    w_max_associated_class: str | None = Field(
        default=None,
        examples=["XC4"],
        description="Classe XC/XD/XS que porte AUSSI l'élément, à déclarer "
                    "seulement quand exposure_class est XF ou XA. Le "
                    "Tableau 7.1N-ANB ne donne de ligne ni au gel/dégel ni à "
                    "l'attaque chimique : sans elle, l'ouverture de fissure "
                    "admissible est refusée, jamais rabattue sur 0,3 mm.")
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

    b_eff_over_b_w: float | None = Field(
        default=None,
        description="Rapport largeur efficace / largeur d'âme d'une section en "
                    "T (§5.3.2.1), pour la dispense de flèche. Absent : section "
                    "rectangulaire déclarée.")
    bond_condition: str = Field(default="good")
    anchorage_coefficients: AnchorageCoefficientsDTO | None = Field(
        default=None,
        description="Les six coefficients alpha du Tableau 8.2, déclarés. "
                    "Absents, le moteur retient 1,0 pour chacun.")

    #: LA FILIATION EST DECLAREE PAR L'INGENIEUR, ET VERIFIEE PAR LE SERVEUR.
    #:
    #: « Creer une variante » part d'une etude enregistree: les memes entrees
    #: preremplies, une section, une charge ou un ferraillage modifies, et un
    #: NOUVEAU calcul sous son propre identifiant. L'etude d'origine n'est ni
    #: modifiee ni remplacee — ses documents restent consultables — et le
    #: lien est ecrit ici, dans la requete gelee, pour que dix ans plus tard un
    #: lecteur sache de quelle etude celle-ci est partie.
    #:
    #: Ce n'est PAS une conclusion ni une preuve: c'est une donnee que seul
    #: l'appelant connait (de quoi il est parti). Le serveur verifie que
    #: l'origine existe dans le MEME projet et qu'elle est une etude complete;
    #: sinon il refuse sans rien ecrire.
    derived_from_calculation_id: str | None = Field(
        default=None,
        description="Identifiant de l'étude enregistrée dont celle-ci est une "
                    "variante. Elle doit appartenir au même projet et être "
                    "une étude complète à cinq chapitres ; sinon la requête "
                    "est refusée sans écriture. Absent pour une étude "
                    "initiale.")

    #: L'ORIGINE DOCUMENTAIRE D'UNE ENTREE, CHAMP PAR CHAMP — et rien d'autre.
    #:
    #: Une entree saisie n'a pas de provenance: la cle est absente. Une entree
    #: reportee depuis un document porte ici l'extraction CONFIRMEE dont elle
    #: vient. Ce que le client ecrit dans cette provenance n'est pas cru: le
    #: serveur relit l'extraction, verifie statut, categorie et valeur, refuse
    #: le calcul au moindre ecart, puis REECRIT la provenance depuis la base
    #: avant de geler la requete (interdiction 5).
    provenance: dict[str, ProvenanceDTO] = Field(
        default_factory=dict,
        description="Pour chaque entrée reportée depuis un document, "
                    "l'extraction confirmée dont elle provient, par chemin du "
                    "contrat (geometry.b, materials.concrete_grade…). Absente "
                    "pour une saisie.")

    @model_validator(mode="after")
    def _provenance_documentaire_confirmee(self) -> Ec2BeamVerificationRequest:
        """Interdiction 5, au premier mur: le contrat lui-même.

        Le second mur est la relecture de la décision en base (route), le
        troisième la contrainte qui interdit une confirmation non signée.
        """
        for chemin, origine in self.provenance.items():
            if chemin not in PROVENANCE_CHEMINS:
                raise ValueError(
                    f"provenance « {chemin} »: aucune entree reportable ne porte "
                    "ce chemin. La hauteur utile d se derive et les "
                    "sollicitations ne se lisent pas sur un plan: elles se "
                    "saisissent.")
            if origine.kind.value != "document_extraction":
                raise ValueError(
                    f"provenance « {chemin} »: seule une origine documentaire "
                    "se declare ici. Une saisie n'a pas de provenance.")
            if not origine.extraction_id or not origine.confirmed_by:
                raise ValueError(
                    f"la valeur « {chemin} » provient d'une extraction "
                    "documentaire qui ne nomme ni sa decision ni la personne "
                    "qui l'a confirmee. Toute cote extraite d'un plan doit etre "
                    "validee explicitement avant d'entrer dans le calcul.")
        return self


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

    #: LES QUATRE EMPREINTES, ET AUCUNE NE SE SUBSTITUE A UNE AUTRE.
    #:
    #:   engineering_inputs_hash   géométrie, sollicitations, ferraillage
    #:   ndp_snapshot_id           le référentiel exact, résolu
    #:   calculation_fingerprint   l'étude complète: technique + référentiel
    #:   execution_identity        l'étude complète + moteur et build
    #:
    #: La rédaction précédente appelait la première `inputs_hash` et la
    #: déposait dans la colonne SQL du même nom, laquelle promet la TOTALITÉ
    #: des entrées. Deux études identiques sous des annexes différentes la
    #: partageaient donc.
    engineering_inputs_hash: str
    ndp_snapshot_id: str
    calculation_fingerprint: str

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

    #: L'ETUDE DONT CELLE-CI EST UNE VARIANTE, telle que la requete gelee la
    #: nomme. Rendue a la creation ET a la relecture: le lien fait partie de
    #: l'etude, pas de l'ecran qui l'a lancee.
    derived_from_calculation_id: str | None = Field(
        default=None,
        description="Identifiant de l'étude d'origine quand celle-ci en est "
                    "une variante ; absent sinon. Lu dans la requête gelée, "
                    "jamais recomposé.")

    #: LA REQUETE GELEE, TELLE QUE RECUE ET ENREGISTREE — valeurs et unites
    #: exactes de l'ingenieur, sans la mise en forme du moteur. C'est d'elle
    #: qu'une variante repart: `inputs` porte les grandeurs formatees (« 300
    #: mm », trois decimales), pas la precision saisie. Rendue a la creation
    #: et a la relecture; absente seulement si la charge gelee n'est plus
    #: relisible dans la forme du contrat — et alors une variante ne peut pas
    #: etre fidele, et l'ecran le dit.
    request: Ec2BeamVerificationRequest | None = Field(
        default=None,
        description="La requête gelée avec l'étude, telle que reçue : c'est "
                    "d'elle qu'une variante fidèle repart, avec la précision "
                    "et les unités saisies.")
