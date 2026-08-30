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
« Signable ». Un calcul enregistré est un calcul enregistré. La validation par
un ingénieur habilité est un **autre geste, dans une autre table** — celui que
portent ``AttestationDemande`` et le parcours de livrables plus bas — et ce
qu'elle enregistre est une attestation métier authentifiée, jamais une
signature électronique qualifiée.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import CountryCode, DesignSituationDTO, QuantityDTO, Strict
from .ec2_beam import MaterialsDTO, RectangularSectionDTO

__all__ = [
    "AttestationDemande",
    "CalculDeProjetRequest",
    "CalculEnregistre",
    "CalculResume",
    "HistoriqueCalculs",
    "ListeLivrables",
    "ListeProjets",
    "Livrable",
    "LivrableCreation",
    "LivrableDetail",
    "Projet",
    "ProjetCreation",
    "RetourAuBrouillon",
    "Transition",
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
    member_role: str = Field(
        description="Le rôle de l'appelant dans l'organisation de CE projet. "
                    "Dérivé de l'adhésion côté serveur. L'écran s'en sert pour "
                    "montrer ou expliquer une action; il ne décide de rien — "
                    "la frontière est dans PostgreSQL.")
    member_name: str | None = Field(
        default=None,
        description="Le nom de l'appelant tel que l'organisation l'enregistre. "
                    "C'est celui qui figurera sur une attestation: son absence "
                    "se constate ici plutôt qu'au moment de signer.")
    member_active: bool = Field(
        default=True,
        description="Faux quand l'accès à cette organisation a été révoqué. Le "
                    "projet reste lisible — la trace des signatures passées "
                    "doit le rester — et toute action est fermée.")


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


# =====================================================================
# LES LIVRABLES ET LEUR PARCOURS DE RELECTURE
#
# CE QU'AUCUN DE CES CORPS NE PORTE, ET POURQUOI CHAQUE ABSENCE COMPTE
# ---------------------------------------------------------------------
# Ni ``org_id``, ni identité du validateur, ni rôle, ni numéro d'inscription
# professionnelle, ni empreinte, ni version de moteur, ni identité
# d'exécution. Tout cela est **dérivé côté serveur** : l'organisation du
# projet, l'adhésion de l'appelant, et les colonnes gelées du calcul.
#
# Un corps qui accepterait ``validator_name`` laisserait signer sous le nom
# de quelqu'un d'autre ; un corps qui accepterait ``sha256`` laisserait
# enregistrer l'empreinte d'octets qu'on n'a pas produits. Ces champs ne sont
# pas « ignorés » : ``Strict`` les refuse par un 422, pour que le client sache
# que sa valeur n'a aucun effet plutôt que de le croire.
#
# CE QUE CES RÉPONSES NE DISENT JAMAIS
# --------------------------------------
# Qu'un document est « signé électroniquement ». Ce que le produit enregistre
# est une **attestation métier authentifiée** : un membre actif, nommé,
# porteur du rôle de validation, atteste avoir relu ce calcul-là. Le nom est
# le même ici, dans PostgreSQL et à l'écran.
# =====================================================================


class LivrableCreation(Strict):
    """Créer un brouillon **depuis un calcul déjà enregistré**.

    UN SEUL CHAMP, ET C'EST TOUT CE QUE LE CLIENT SAIT. Le contenu du document
    est produit sur le serveur à partir des données gelées du calcul ; sa
    nature, son nom, ses octets, leur empreinte, leur taille, le contexte
    normatif, la version du moteur, le build et l'identité d'exécution sont
    tous dérivés. Il n'y a donc rien d'autre à envoyer.

    ``kind`` N'EST PAS UN CHAMP NON PLUS. Le produit sait produire une note de
    calcul HTML autonome, et rien d'autre aujourd'hui. Offrir le choix entre
    huit natures de document dont sept n'existent pas ferait promettre à
    l'écran des livrables qu'aucune route ne produit.
    """

    calculation_id: str = Field(
        description="Le calcul enregistré dont ce livrable est tiré. Il doit "
                    "appartenir au projet du chemin, avoir abouti, et porter "
                    "une identité d'exécution vérifiable.")


class RetourAuBrouillon(Strict):
    """Renvoyer une pièce en relecture vers le brouillon, **avec un motif**.

    LE MOTIF EST OBLIGATOIRE, ET LA BASE LE REFUSE VIDE ELLE AUSSI. Celui qui
    reprend le document doit savoir ce qui lui est reproché ; un retour muet
    est une décision qu'on ne peut pas relire six mois plus tard.
    """

    reason: str = Field(
        min_length=1, max_length=4000,
        description="Ce qui est reproché à la pièce. Repris dans l'historique "
                    "des transitions et affiché à celui qui la reprend.")


class AttestationDemande(Strict):
    """Ce que le validateur écrit, et **rien d'autre**.

    NI NOM, NI RÔLE, NI NUMÉRO D'INSCRIPTION. Les trois sortent de
    ``organization_members`` sous l'identité du jeton. Les accepter ici
    donnerait l'illusion qu'ils comptent, alors que PostgreSQL les écrase de
    toute façon — et l'illusion est pire que l'absence, parce qu'un écran
    finirait par les afficher.

    NI IDENTIFIANT DE CALCUL, NI EMPREINTE. L'attestation porte sur le calcul
    du livrable et sur les octets réellement enregistrés ; les faire venir du
    corps laisserait attester un calcul et en signer un autre.
    """

    statement: str = Field(
        min_length=1, max_length=8000,
        description="Ce que le validateur atteste, dans ses termes. Repris "
                    "tel quel dans la ligne de validation, horodaté et figé.")
    reservations: str | None = Field(
        default=None, max_length=8000,
        description="Réserves émises par le validateur. Elles font partie de "
                    "l'attestation et sont conservées avec elle.")


class Transition(Strict):
    """Un pas dans le parcours de relecture, horodaté et attribué."""

    from_state: str | None = Field(
        default=None,
        description="L'état quitté. Absent pour la création du brouillon.")
    to_state: str
    actor_id: str | None = Field(
        default=None,
        description="Qui a provoqué la transition. Dérivé de la session, "
                    "jamais du corps de la requête.")
    reason: str | None = None
    occurred_at: str


class Livrable(Strict):
    """Un livrable, tel que la liste du projet le montre.

    ``state`` EST LA SEULE VÉRITÉ SUR L'ÉTAT. ``is_final`` en est dérivé en
    base et ne traverse pas jusqu'ici : deux champs pour un même fait finissent
    par se contredire, et c'est l'écran qui affiche le mauvais.
    """

    deliverable_id: str
    calculation_id: str
    kind: str
    filename: str
    media_type: str
    sha256: str = Field(
        description="Empreinte des octets réellement enregistrés. La route de "
                    "téléchargement la revérifie sur ce qu'elle sert.")
    size_bytes: int = Field(ge=0)
    state: str = Field(
        description="brouillon (draft), en relecture (review), validé "
                    "(validated), émis (final).")
    revision: int = Field(ge=1)
    supersedes_id: str | None = None
    watermark: str | None = Field(
        default=None,
        description="Le filigrane RÉELLEMENT apposé sur les octets. Il dit ce "
                    "qui est vrai du document pour toujours — « PROJET — NON "
                    "SIGNABLE » — et jamais son état de workflow, qui change.")
    last_reason: str | None = None
    engine_version: str
    engine_build_sha: str | None = None
    execution_identity: str | None = None
    validation_id: str | None = None
    validator_name: str | None = None
    validated_at: str | None = None
    generated_at: str


class LivrableDetail(Livrable):
    """Un livrable, son contexte figé, son attestation et son histoire.

    L'HISTORIQUE VIENT DU MÊME APPEL QUE L'ÉTAT. Deux appels séparés
    pourraient tomber de part et d'autre d'une transition et montrer un état
    qui ne correspond pas à son journal.
    """

    inputs_hash: str | None = None
    ndp_as_of: str | None = None
    validator_role: str | None = None
    professional_id: str | None = Field(
        default=None,
        description="Numéro d'inscription à l'ordre professionnel, figé au "
                    "moment de l'attestation depuis l'adhésion.")
    statement: str | None = None
    reservations: str | None = None
    transitions: list[Transition] = Field(default_factory=list)
    notice: str = Field(
        description="La mention obligatoire: ce document doit être vérifié et "
                    "signé par un ingénieur habilité.")
    mention: str | None = Field(
        default=None,
        description="« PROJET — NON SIGNABLE », quand des paramètres "
                    "nationaux non confirmés ont pu servir.")


class ListeLivrables(Strict):
    deliverables: list[Livrable] = Field(default_factory=list)
