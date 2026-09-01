"""Le document émis : l'attestation, sous une forme qui circule.

LE DÉFAUT QUE CE MODULE FERME
-------------------------------
Le nom du validateur, son rôle, son numéro d'inscription, sa déclaration, ses
réserves et la date vivaient dans ``validations`` — c'est-à-dire dans une base
que le destinataire du document ne voit pas. Le PDF qu'on lui transmettait ne
portait rien de tout cela, et rien ne l'y distinguait d'un brouillon.

Modifier le PDF original pour y ajouter l'attestation était exclu : son
empreinte est **ce sur quoi l'attestation porte**. La retoucher aurait détruit
le lien qu'elle établit. D'où un **second** document, qui référence le premier
par son SHA-256 et ne le remplace pas.

CE QU'IL PORTE, ET D'OÙ CELA VIENT
------------------------------------
Tout vient du serveur : la ligne de livrable gelée et la ligne de validation.
**Aucune de ces informations ne peut être dictée par un corps HTTP** — le nom
du validateur sort de son adhésion, pas de sa requête.

CE QU'IL N'EST PAS
--------------------
Une signature électronique qualifiée. Le document le dit en toutes lettres, en
tête et en pied : c'est une attestation métier authentifiée, et la nuance n'est
pas rhétorique — l'une engage un dispositif de certification, l'autre engage
une personne nommée.

DÉTERMINISME
--------------
Comme la note et le plan : aucune horloge n'entre ici. La date imprimée est
celle de la **signature**, lue en base. Deux compositions du même dossier
rendent les mêmes octets, ce que l'adressage par contenu exige.
"""
from __future__ import annotations

from typing import Any

from .pdf import Bloc, Champs, Paragraphe, Tableau, Titre, composer_pdf

__all__ = [
    "MENTION_DOCUMENT_EMIS",
    "MENTION_PAS_UNE_SIGNATURE_QUALIFIEE",
    "SIGNATURE_OUTIL",
    "ZONE_LOGO",
    "rendre_attestation_pdf",
]

#: Le titre du document, et ce qu'il annonce en une ligne.
MENTION_DOCUMENT_EMIS = "Document émis — attestation métier authentifiée"

#: LA LIMITE, DITE DEUX FOIS: en tête et en pied. Un lecteur pressé lit l'une
#: ou l'autre, jamais les deux, et il ne doit pas pouvoir manquer celle-là.
MENTION_PAS_UNE_SIGNATURE_QUALIFIEE = (
    "Ce document n'est PAS une signature électronique qualifiée au sens du "
    "règlement eIDAS. Il constate qu'un ingénieur habilité, nommé ci-dessus, "
    "a relu le calcul identifié et en répond. La vérification de son "
    "habilitation appartient au destinataire."
)

#: ZONE DE LOGO, VIDE PAR DÉFAUT ET DÉLIBÉRÉMENT.
#:
#: Un logo fictif intégré comme marque officielle serait pire qu'aucun logo:
#: il ferait passer un document de test pour la pièce d'un bureau réel. La
#: place est réservée; l'organisation la remplira quand elle fournira sa
#: propre identité visuelle.
ZONE_LOGO = ""

#: L'IDENTITÉ DE L'OUTIL, ET SEULEMENT DE L'OUTIL.
#:
#: Le document doit dire par quoi il a été composé — sans cela, un destinataire
#: reçoit un PDF anonyme et n'a aucun moyen de savoir à qui poser une question.
#: Mais cette ligne nomme le LOGICIEL, jamais un bureau d'études, jamais un
#: organisme de certification: le seul acteur qui engage sa responsabilité ici
#: est l'ingénieur nommé dans l'attestation, et rien ne doit venir partager
#: cette place avec lui. C'est pour la même raison qu'elle est en pied et non
#: en tête: l'outil n'est pas le sujet du document.
SIGNATURE_OUTIL = (
    "Composé par EUROSTRUCT — plateforme d'études structurelles assistées. "
    "Ce document est produit automatiquement à partir des données figées du "
    "calcul et de l'attestation enregistrée; EUROSTRUCT n'est ni auteur ni "
    "garant du contenu technique, qui relève de l'ingénieur nommé ci-dessus."
)


def _p(valeur: Any) -> str:
    """Une valeur absente s'écrit « — », jamais « None » ni une chaîne vide.

    Un champ vide se lit « on ne l'a pas rempli » ; un tiret se lit « il n'y en
    a pas ». Sur une attestation, la différence compte.
    """
    if valeur is None:
        return "—"
    texte = str(valeur).strip()
    return texte or "—"


def rendre_attestation_pdf(projet: dict[str, Any],
                           source: dict[str, Any]) -> bytes:
    """Le PDF du document émis, composé depuis les données **gelées**.

    :param projet: la ligne de projet, telle que le serveur la relit.
    :param source: le livrable original relu — ses colonnes gelées **et** son
        attestation, telles que ``project_deliverable_read`` les rend.
    """
    reference = _p(projet.get("reference") or projet.get("name"))

    blocs: list[Bloc] = [
        Titre(MENTION_DOCUMENT_EMIS, 1),
        # LA LIMITE EN TETE, encadrée, avant tout le reste. Un lecteur qui ne
        # lirait que le premier paragraphe doit lire celui-là.
        Paragraphe(MENTION_PAS_UNE_SIGNATURE_QUALIFIEE, gras=True,
                   encadre=True),

        Titre("Dossier"),
        Champs([
            ("Organisation", _p(projet.get("organization_name"))),
            ("Projet", _p(projet.get("name"))),
            ("Référence du projet", reference),
            ("Pays", _p(projet.get("country"))),
            ("Région", _p(projet.get("region"))),
            ("Calcul", _p(source.get("calculation_id"))),
            ("Élément", _p(source.get("filename"))),
        ]),

        Titre("Le document attesté"),
        Paragraphe(
            "L'attestation ci-dessous porte sur les octets dont l'empreinte "
            "est reproduite ici, et sur eux seuls. Un fichier dont "
            "l'empreinte diffère n'est pas le document attesté."),
        Champs([
            ("Nom du fichier", _p(source.get("filename"))),
            ("Type", _p(source.get("media_type"))),
            ("Taille", f"{source.get('size_bytes', 0)} octets"),
            ("SHA-256 de l'original", _p(source.get("sha256"))),
            ("Identifiant du livrable", _p(source.get("deliverable_id"))),
            ("Indice", _p(source.get("revision"))),
        ]),

        Titre("L'attestation"),
        Champs([
            ("Identifiant de validation", _p(source.get("validation_id"))),
            ("Validateur", _p(source.get("validator_name"))),
            ("Rôle", _p(source.get("validator_role"))),
            ("Identifiant professionnel", _p(source.get("professional_id"))),
            ("Date et heure de validation", _p(source.get("validated_at"))),
        ]),
        Paragraphe("Déclaration :", gras=True),
        Paragraphe(_p(source.get("statement"))),
        Paragraphe("Réserves :", gras=True),
        # LES RESERVES ABSENTES SE DISENT, ELLES NE SE TAISENT PAS. Un lecteur
        # qui ne trouve pas la rubrique ne sait pas si elle a été omise.
        Paragraphe(_p(source.get("reservations"))
                   if source.get("reservations")
                   else "Aucune réserve n'a été formulée."),

        Titre("Ce qui a produit le calcul"),
        Paragraphe(
            "Ces valeurs sont figées avec le calcul. Elles permettent de "
            "rejouer la vérification et de constater qu'aucune n'a bougé "
            "depuis l'attestation."),
        Tableau(
            entetes=["Élément", "Valeur"],
            lignes=[
                ["Version du moteur", _p(source.get("engine_version"))],
                ["Build du moteur", _p(source.get("engine_build_sha"))],
                ["Identité d'exécution", _p(source.get("execution_identity"))],
                ["Empreinte des entrées", _p(source.get("inputs_hash"))],
                ["Date de référence normative", _p(source.get("ndp_as_of"))],
            ],
        ),

        Titre("Portée et limites"),
        Paragraphe(
            "Cette attestation couvre le document identifié ci-dessus, et lui "
            "seul. Les autres pièces du même calcul — plan de ferraillage, "
            "note au format HTML — ne sont pas couvertes par elle : le "
            "dossier de revue les énumère séparément."),
        Paragraphe(MENTION_PAS_UNE_SIGNATURE_QUALIFIEE, encadre=True),

        # L'OUTIL SIGNE EN DERNIER, ET EN PETIT. Voir SIGNATURE_OUTIL: il
        # nomme le logiciel pour qu'un destinataire sache d'où vient le
        # fichier, et décline toute part dans le contenu technique.
        Paragraphe(SIGNATURE_OUTIL),
    ]

    if ZONE_LOGO:
        blocs.insert(0, Paragraphe(ZONE_LOGO))

    return composer_pdf(
        f"{MENTION_DOCUMENT_EMIS} — {reference}", blocs)
