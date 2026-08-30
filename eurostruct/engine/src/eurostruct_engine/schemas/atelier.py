"""Les formes de fil de l'atelier : projets, calculs enregistrés, historique.

CE QU'AUCUN DE CES CORPS NE PORTE
----------------------------------
Ni ``org_id``, ni ``actor_id``, ni ``created_by``. L'organisation d'un projet
se lit dans ``organization_members`` à partir de l'identité du jeton ; un champ
qui l'accepterait rendrait le cloisonnement décoratif — il suffirait de mentir
dans le corps. C'est la même règle que sur le chemin d'autorité, et pour la
même raison.

``ProjetCreation`` fait une exception nommée, et elle est bornée :
``organization_id`` est **facultatif**, et la base le confronte aux
appartenances avant d'en faire quoi que ce soit. Il sert au seul cas où
l'ingénieur appartient à plusieurs bureaux : deviner à sa place vaudrait mieux
que de refuser, sauf que « deviner » voudrait dire créer le projet dans la
mauvaise organisation, où il resterait visible par les mauvaises personnes.

CE QU'AUCUNE DE CES RÉPONSES NE DIT
------------------------------------
« Final », « signable », « validé ». Un calcul enregistré est un calcul
enregistré. La validation nominative par un ingénieur habilité est un autre
geste, dans une autre table, et il n'existe pas encore.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import CountryCode, DesignSituationDTO, QuantityDTO, Strict
from .ec2_beam import MaterialsDTO, RectangularSectionDTO

__all__ = [
    "CalculDeProjetRequest",
    "CalculEnregistre",
    "CalculResume",
    "HistoriqueCalculs",
    "ListeProjets",
    "Projet",
    "ProjetCreation",
]


class Projet(Strict):
    """Un projet, tel que l'atelier le montre.

    ``organization_name`` accompagne ``organization_id`` : un identifiant seul
    obligerait l'écran à un second appel pour afficher « Bureau A », et c'est
    ce genre de second appel qui finit par ne jamais être fait.
    """

    project_id: str
    organization_id: str
    organization_name: str
    name: str
    reference: str | None = None
    country: CountryCode
    region: str | None = Field(
        default=None,
        description="Région sous-nationale quand elle change les paramètres "
                    "(Wallonie / Vlaanderen / Bruxelles, Land, Comunidad "
                    "autónoma). Figée à la création, comme le pays et la date.")
    ndp_as_of: str = Field(
        description="Date de référence du projet (ISO 8601). Elle résout "
                    "l'édition d'Annexe Nationale en vigueur, norme par "
                    "norme. Ce n'est pas la date du calcul.")
    created_at: str
    calculation_count: int = Field(
        ge=0, description="Combien de calculs sont enregistrés sur ce projet.")


class ListeProjets(Strict):
    """Les projets des organisations de l'appelant, et rien d'autre."""

    projects: list[Projet]


class ProjetCreation(Strict):
    """Ce qu'un ingénieur saisit pour ouvrir un projet.

    ``ndp_as_of`` N'EST PAS DÉCORATIVE. Elle résout l'édition d'Annexe
    Nationale en vigueur, norme par norme, et se fige à la création : sans
    elle, le référentiel dépendrait de la date à laquelle le calcul est
    lancé — c'est-à-dire du hasard.
    """

    name: str = Field(min_length=1, max_length=200)
    reference: str | None = Field(default=None, max_length=100)
    country: CountryCode
    region: str | None = Field(
        default=None, max_length=100,
        description="Région sous-nationale, quand elle change les paramètres "
                    "nationaux. Elle se fige à la création avec le pays et la "
                    "date: un calcul ne pourra plus en désigner une autre.")
    ndp_as_of: str = Field(
        description="Date de référence, ISO 8601 (AAAA-MM-JJ). Elle résout "
                    "l'édition d'Annexe Nationale en vigueur et se fige à la "
                    "création du projet.")
    organization_id: str | None = Field(
        default=None,
        description="Facultatif, et jamais cru sur parole: la base le "
                    "confronte aux appartenances. Nécessaire uniquement quand "
                    "l'appelant appartient à plusieurs organisations.")


class CalculResume(Strict):
    """Une ligne d'historique. Assez pour choisir, pas assez pour conclure.

    ``max_utilisation`` est ``None`` quand le calcul n'a produit aucune
    vérification — un refus, notamment. Le rendre à ``0.0`` ferait lire
    « largement vérifié » là où rien n'a été vérifié.
    """

    calculation_id: str
    status: str = Field(
        description="'succeeded' ou 'refused'. Un refus reste un refus dans "
                    "l'historique: il n'est ni omis, ni dégradé en échec "
                    "technique.")
    strict_ndp: bool
    engine_version: str
    inputs_hash: str
    element: str | None = None
    max_utilisation: float | None = None
    created_at: str


class HistoriqueCalculs(Strict):
    """L'historique d'un projet, du plus récent au plus ancien."""

    project_id: str
    calculations: list[CalculResume]


class CalculEnregistre(Strict):
    """Un calcul rouvert : les MÊMES entrées, les MÊMES résultats.

    ``request`` est la requête exacte reçue par le moteur, pas une
    reconstruction. ``inputs_hash`` en est l'empreinte, et permet à l'écran de
    dire « ce sont bien ces entrées-là » sans faire confiance au transport.

    ``ndp_snapshot`` est l'état du portillon normatif **au moment du calcul**. Il
    change quand une confirmation arrive ou est révoquée ; le relire
    aujourd'hui donnerait l'état d'aujourd'hui pour un calcul d'hier.
    """

    calculation_id: str
    project_id: str
    status: str
    strict_ndp: bool
    engine_version: str
    engine_build_sha: str | None = Field(
        default=None,
        description="Le build EXACT qui a produit ce calcul. La version seule "
                    "ne désigne aucun code: plusieurs commits successifs la "
                    "partagent.")
    execution_identity: str | None = Field(
        default=None,
        description="Empreinte canonique de (requête, instantané NDP, moteur, "
                    "build). Deux exécutions de même identité doivent rendre "
                    "le même résultat. Distincte d'`inputs_hash`, qui "
                    "n'empreinte que la requête.")
    ndp_as_of: str | None = Field(
        default=None,
        description="La date de référence effectivement appliquée, reprise du "
                    "projet.")
    inputs_hash: str = Field(
        description="Empreinte de la REQUÊTE, et rien d'autre. Elle répond à "
                    "« est-ce la même demande ? », pas à « obtiendra-t-on le "
                    "même résultat ? » — cela dépend aussi du code et du "
                    "référentiel, que porte `execution_identity`.")
    request: dict[str, Any]
    ndp_snapshot: dict[str, Any] | None = None
    refusal: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    journal: Any | None = None
    verifications: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    notice: str = Field(
        description="La mention obligatoire: ce document doit être vérifié et "
                    "signé par un ingénieur habilité. Elle accompagne un "
                    "calcul relu comme elle accompagne un calcul neuf.")
    mention: str | None = Field(
        default=None,
        description="« PROJET — NON SIGNABLE ». Présente uniquement quand des "
                    "paramètres nationaux non confirmés ont pu servir. Bien "
                    "plus forte que `notice`: celle-ci dit « pas encore "
                    "signé », celle-là « pas signable du tout ».")


class CalculDeProjetRequest(Strict):
    """Un calcul de flexion **sur un projet**. Il ne nomme aucun référentiel.

    CE QU'IL NE PORTE PAS, ET POURQUOI CHAQUE ABSENCE COMPTE
    ---------------------------------------------------------
    ``project_id``
        Il est dans le chemin. Le laisser aussi dans le corps donnerait deux
        sources pour une même question, et la note pourrait nommer un dossier
        autre que celui où elle est rangée.

    ``country``, ``region``, ``as_of``
        Ils décident **quelle édition d'Annexe Nationale s'applique**, donc
        quelles valeurs entrent dans les formules. Ils sont figés sur le
        projet à sa création. Les accepter ici laissait — mesuré — un calcul
        français aboutir sur un projet belge, avec une ligne enregistrée qui
        se contredisait : ``request.country = FR`` et
        ``calculations.ndp_as_of`` repris du projet.

    ``Strict`` INTERDIT LES CHAMPS SUPPLÉMENTAIRES, si bien qu'un client qui
    envoie encore l'un des quatre reçoit un **422** — une réponse — plutôt
    qu'un champ silencieusement ignoré. Écraser aurait marché tant qu'une
    seule route existe ; refuser dit au client que son champ n'a pas d'effet.

    CE QU'IL PORTE, ET QUI EST BIEN À LUI
    --------------------------------------
    La géométrie, les matériaux, la situation de projet, le moment, le
    ferraillage éventuellement retenu, la provenance des entrées, et
    ``strict_ndp``. Tout cela change d'un calcul à l'autre par nature.
    """

    element: str = Field(
        default="poutre", max_length=100,
        description="Repère de l'élément, tel qu'il apparaîtra sur la note.")
    strict_ndp: bool = Field(
        default=True,
        description="Quand vrai, un paramètre national non confirmé provoque "
                    "un refus. Exigé pour tout livrable destiné à être signé.")

    section: RectangularSectionDTO
    materials: MaterialsDTO
    situation: DesignSituationDTO = DesignSituationDTO.PERSISTENT

    M_Ed: QuantityDTO = Field(
        description="Moment de calcul issu de la combinaison EN 1990 "
                    "déterminante. Le moteur ne construit pas les "
                    "combinaisons.")
    A_s_provided: QuantityDTO | None = Field(
        default=None,
        description="Aire des barres réellement disposées. Omise, la "
                    "vérification porte sur l'aire strictement requise.")
