"""L'atelier, côté PostgreSQL : cinq primitives, une identité, zéro `org_id`.

CE QUE CE MODULE N'A PAS RÉÉCRIT, ET POURQUOI
----------------------------------------------
``_UniteDeTravail`` — authentifier, ouvrir la transaction, ``SET LOCAL
eurostruct.actor_id``, commit ou rollback, contexte parti avec la transaction —
vient de ``postgres_provider``. Le réimplémenter donnerait deux mécanismes
d'identité, dont un seul serait éprouvé par la campagne de mutations, et ce
serait toujours l'autre qui laisserait passer.

Même chose pour ``RefusSqlTraduits`` : un refus SQL doit devenir un refus du
domaine, sur le ``SQLSTATE`` que PostgreSQL pose lui-même, et non sur le texte
d'un message. Un second traducteur écrit ici dériverait au premier code
ajouté.

AUCUNE MÉTHODE NE PREND `org_id`
---------------------------------
L'organisation d'un projet se lit dans ``organization_members`` à partir de
l'acteur, à l'intérieur de la primitive. ``creer_projet`` accepte un
``organization_id`` **facultatif**, que la primitive confronte aux
appartenances avant d'en faire quoi que ce soit : c'est un choix parmi les
organisations de l'appelant, pas une affirmation qu'on croit.

L'ATOMICITÉ N'EST PAS ICI
--------------------------
``enregistrer_calcul`` fait **un** appel. Les quatre tables — ``calculations``,
``results``, ``verifications``, plus le modèle et la version de moteur qui
manquaient — sont écrites par la primitive, dans la transaction ouverte par
l'unité de travail. Enchaîner quatre ordres depuis Python laisserait, sur
incident réseau au troisième, un calcul « réussi » sans vérification : un
calcul dont personne ne sait s'il passe, et que l'historique présente comme
abouti.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .confirmation import ConfirmationDomainError
from .postgres_provider import (
    Authentificateur,
    AuthentificationRequise,
    Connexion,
    ContexteAuthentifie,
    RefusSqlTraduits,
    _UniteDeTravail,
)

__all__ = ["PostgresAtelier"]


def _texte(valeur: Any) -> str | None:
    """``None`` reste ``None``; tout le reste devient du texte comparable.

    psycopg2 rend les ``uuid`` et les ``timestamptz`` en objets Python. Les
    laisser traverser tels quels ferait dépendre la forme du fil du pilote
    installé, et un contrat de fil qui change avec le pilote n'en est pas un.
    """
    return None if valeur is None else str(valeur)


def _json_ou_none(valeur: Any) -> Any:
    """``jsonb`` déjà décodé, ou une chaîne à décoder. Jamais une supposition.

    psycopg2 décode ``jsonb`` tout seul ; un pilote qui rendrait la chaîne ne
    doit pas faire échouer la relecture pour autant.
    """
    if valeur is None:
        return None
    if isinstance(valeur, str | bytes | bytearray):
        return json.loads(valeur)
    return valeur


@dataclass
class PostgresAtelier:
    """Les cinq gestes du parcours de travail, sous identité vérifiée.

    Une instance par requête, comme le provider d'autorité : deux requêtes
    concurrentes qui partageraient une connexion partageraient aussi
    ``eurostruct.actor_id``, et l'une agirait sous l'identité de l'autre.
    """

    connexion: Connexion
    authentificateur: Authentificateur

    #: Le même réglage que le provider d'autorité, et volontairement le même:
    #: deux noms de contexte voudraient dire deux identités possibles dans une
    #: seule transaction.
    REGLAGE_ACTEUR = "eurostruct.actor_id"

    def __post_init__(self) -> None:
        if self.authentificateur is None:
            raise AuthentificationRequise(
                "atelier sans authentificateur: aucune operation n'est "
                "possible. Le produit ne simule pas une authentification "
                "qu'il n'a pas."
            )

    # ------------------------------------------------------- unité de travail
    def _unite(self, preuve: Any) -> _UniteDeTravail:
        """Authentifier, PUIS ouvrir, PUIS poser l'acteur. Dans cet ordre.

        Authentifier après avoir ouvert une transaction privilégiée laisserait
        une fenêtre où la connexion est engagée sans que personne ne soit
        nommé.
        """
        contexte = self.authentificateur.authentifier(preuve)
        if not isinstance(contexte, ContexteAuthentifie):
            raise AuthentificationRequise(
                "l'authentificateur n'a pas rendu un ContexteAuthentifie: "
                "une valeur quelconque ne vaut pas identite."
            )
        return _UniteDeTravail(self.connexion, contexte, self.REGLAGE_ACTEUR)

    @staticmethod
    def _lignes(unite: _UniteDeTravail) -> list[dict[str, Any]]:
        colonnes = [d[0] for d in unite.curseur.description]
        return [dict(zip(colonnes, ligne, strict=True))
                for ligne in unite.curseur.fetchall()]

    # ------------------------------------------------------------- projets
    def projets(self, preuve: Any) -> list[dict[str, Any]]:
        """Les projets des organisations de l'appelant.

        AUCUN FILTRE N'EST PASSÉ. « Mon organisation » est une question dont la
        réponse est en base ; la poser en paramètre laisserait l'écran demander
        celle d'un autre — RLS l'en empêcherait, mais la signature aurait déjà
        dit que la question se pose.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer("select * from project_workspace_list()")
            return [
                {
                    "project_id": _texte(ligne["project_id"]),
                    "organization_id": _texte(ligne["org_id"]),
                    "organization_name": ligne["org_name"],
                    "name": ligne["name"],
                    "reference": ligne["reference"],
                    "country": ligne["country"],
                    "region": ligne["region"],
                    "ndp_as_of": _texte(ligne["ndp_as_of"]),
                    "created_at": _texte(ligne["created_at"]),
                    "calculation_count": int(ligne["calculation_count"]),
                }
                for ligne in self._lignes(u)
            ]

    def creer_projet(self, preuve: Any, *, name: str, reference: str | None,
                     country: str, ndp_as_of: str, region: str | None = None,
                     organization_id: str | None = None) -> str:
        """Crée un projet, dans une organisation de l'appelant.

        ``organization_id`` est confronté aux appartenances par la primitive.
        Ce n'est pas une affirmation qu'on croit : c'est un choix parmi celles
        de l'appelant, et la base refuse tout autre.

        ``region`` SE FIGE AVEC LE PAYS ET LA DATE. Les trois ensemble
        désignent l'édition d'Annexe Nationale applicable ; aucun calcul du
        projet ne pourra en désigner d'autres.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select project_workspace_create("
                "%s, %s, %s::country_code, %s::date, %s::uuid, %s)",
                (name, reference, country, ndp_as_of, organization_id, region),
            )
            ligne = u.curseur.fetchone()
            if not ligne or not ligne[0]:
                raise ConfirmationDomainError(
                    "la creation n'a rendu aucun identifiant de projet. On "
                    "refuse plutot que d'annoncer un projet introuvable."
                )
            return str(ligne[0])

    # ------------------------------------------------------------- calculs
    def enregistrer_calcul(
        self, preuve: Any, *, project_id: str, status: str,
        inputs_hash: str, strict_ndp: bool, engine_version: str,
        request: Any, execution_identity: str, engine_build: str,
        ndp_snapshot: Any = None, progress_log: Any = None,
        refusal: Any = None, result: Any = None, journal: Any = None,
        verifications: Any = None,
    ) -> str:
        """Enregistre un calcul **entièrement ou pas du tout**.

        UN SEUL APPEL POUR QUATRE TABLES. La primitive écrit le calcul, son
        résultat, son journal et ses vérifications dans la transaction ouverte
        ici. Un enchaînement de quatre ordres depuis Python laisserait, sur
        incident au troisième, un calcul « réussi » sans vérification.

        UN REFUS EST ENREGISTRÉ COMME REFUS. ``status='refused'`` avec son
        motif : le mode strict qui refuse faute de paramètre confirmé n'est pas
        une panne, c'est une réponse du moteur, et l'historique doit la porter
        telle quelle.

        ``execution_identity`` ET ``engine_build`` SONT OBLIGATOIRES, et la
        primitive refuse sans eux. Un calcul conservé dix ans doit pouvoir
        désigner le code exact qui l'a produit ; ``0.3.0`` ne le désigne pas —
        six commits successifs la portent.
        """
        def _js(valeur: Any) -> str | None:
            if valeur is None:
                return None
            # `sort_keys` ET `separators`: deux enregistrements des mêmes
            # entrées doivent donner les mêmes octets, sans quoi comparer un
            # calcul rouvert à son original comparerait deux sérialisations.
            return json.dumps(valeur, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":"))

        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select project_calculation_record("
                "%s::uuid, %s::calculation_status, %s, %s, %s, "
                "%s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, "
                "%s::jsonb, %s::jsonb, %s::jsonb, %s, %s)",
                (project_id, status, inputs_hash, strict_ndp, engine_version,
                 _js(request), _js(ndp_snapshot), _js(progress_log),
                 _js(refusal), _js(result), _js(journal), _js(verifications),
                 execution_identity, engine_build),
            )
            ligne = u.curseur.fetchone()
            if not ligne or not ligne[0]:
                raise ConfirmationDomainError(
                    "l'enregistrement n'a rendu aucun identifiant de calcul. "
                    "Un calcul qu'on ne peut pas retrouver n'est pas un calcul "
                    "enregistre."
                )
            return str(ligne[0])

    def historique(self, preuve: Any, *, project_id: str) -> list[dict[str, Any]]:
        """L'historique d'un projet, du plus récent au plus ancien."""
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer("select * from project_calculation_list(%s::uuid)",
                       (project_id,))
            return [
                {
                    "calculation_id": _texte(ligne["calculation_id"]),
                    "status": ligne["status"],
                    "strict_ndp": bool(ligne["strict_ndp"]),
                    "engine_version": ligne["engine_version"],
                    "inputs_hash": ligne["inputs_hash"],
                    "element": ligne["element"],
                    "max_utilisation": (
                        None if ligne["max_utilisation"] is None
                        else float(ligne["max_utilisation"])),
                    "created_at": _texte(ligne["created_at"]),
                }
                for ligne in self._lignes(u)
            ]

    def rouvrir_calcul(self, preuve: Any, *, project_id: str,
                       calculation_id: str) -> dict[str, Any]:
        """Le calcul sauvegardé : les mêmes entrées, les mêmes résultats.

        UN ENSEMBLE VIDE N'EST PAS UN CALCUL VIDE. La primitive lève quand le
        projet n'est pas atteignable ; zéro ligne signifie « ce calcul n'existe
        pas dans ce projet ». Rendre ``{}`` ferait afficher un écran de calcul
        vide, rassurant et faux.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select * from project_calculation_read(%s::uuid, %s::uuid)",
                (project_id, calculation_id))
            lignes = self._lignes(u)
        if not lignes:
            raise ConfirmationDomainError(
                f"calcul {calculation_id}: introuvable dans ce projet. On "
                "refuse plutot que d'afficher un calcul vide."
            )
        ligne = lignes[0]
        return {
            "calculation_id": _texte(ligne["calculation_id"]),
            "project_id": project_id,
            "status": ligne["status"],
            "strict_ndp": bool(ligne["strict_ndp"]),
            "engine_version": ligne["engine_version"],
            "inputs_hash": ligne["inputs_hash"],
            "engine_build_sha": ligne["engine_build_sha"],
            "execution_identity": ligne["execution_identity"],
            "ndp_as_of": _texte(ligne["ndp_as_of"]),
            "request": _json_ou_none(ligne["request"]),
            "ndp_snapshot": _json_ou_none(ligne["ndp_snapshot"]),
            "refusal": _json_ou_none(ligne["refusal"]),
            "result": _json_ou_none(ligne["result"]),
            "journal": _json_ou_none(ligne["journal"]),
            "verifications": _json_ou_none(ligne["verifications"]) or [],
            "created_at": _texte(ligne["created_at"]),
        }

    # ---------------------------------------------------------- livrables
    #
    # LES SEPT GESTES DU PARCOURS DE RELECTURE. Ils rendent atteignable la
    # machine à états que 0005 et 0009 avaient construite sans porte : rien
    # ici ne décide qui peut valider, quel enchaînement d'états est permis, ni
    # ce qu'une signature fige. Tout cela est dans PostgreSQL, et ces méthodes
    # ne font que le demander. Réécrire un seul de ces contrôles ici donnerait
    # deux frontières, dont la plus faible finirait par décider.

    def creer_livrable(
        self, preuve: Any, *, project_id: str, calculation_id: str,
        kind: str, filename: str, media_type: str, storage_backend: str,
        storage_path: str, sha256: str, size_bytes: int,
        watermark: str | None = None, supersedes_id: str | None = None,
    ) -> str:
        """Enregistre un brouillon dont les octets sont **déjà déposés**.

        L'ORDRE N'EST PAS NÉGOCIABLE, ET IL EST CHEZ L'APPELANT : déposer les
        octets, les relire, vérifier leur empreinte, PUIS appeler ceci. Une
        ligne écrite avant le dépôt promettrait un document introuvable si
        l'écriture échouait ensuite ; l'inverse ne laisse au pire qu'un objet
        que personne ne référence.

        AUCUN CONTEXTE NORMATIF N'EST PASSÉ. Pays, région, date, version du
        moteur, build et identité d'exécution sont COPIÉS du calcul par la
        primitive. Les faire venir d'ici rouvrirait exactement la substitution
        que 0019 a fermée.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select project_deliverable_create("
                "%s::uuid, %s::uuid, %s::deliverable_kind, %s, %s, %s, %s, "
                "%s, %s::bigint, %s, %s::uuid)",
                (project_id, calculation_id, kind, filename, media_type,
                 storage_backend, storage_path, sha256, size_bytes,
                 watermark, supersedes_id),
            )
            ligne = u.curseur.fetchone()
            if not ligne or not ligne[0]:
                raise ConfirmationDomainError(
                    "la creation n'a rendu aucun identifiant de livrable. On "
                    "refuse plutot que d'annoncer un document introuvable."
                )
            return str(ligne[0])

    def livrables(self, preuve: Any, *, project_id: str) -> list[dict[str, Any]]:
        """Les livrables du projet, du plus récent au plus ancien."""
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer("select * from project_deliverable_list(%s::uuid)",
                       (project_id,))
            return [self._livrable_resume(ligne) for ligne in self._lignes(u)]

    @staticmethod
    def _livrable_resume(ligne: dict[str, Any]) -> dict[str, Any]:
        """Les champs communs à la liste et à la relecture.

        ``validated_at`` EST LU AVEC UN DÉFAUT, et c'est nécessaire : la liste
        rend cette colonne sous ce nom, la relecture la rend sous ``signed_at``
        — le nom qu'elle porte dans ``validations``. Les deux primitives sont
        justes ; c'est cette projection qui doit accepter les deux formes,
        plutôt que d'échouer sur un ``KeyError`` au premier appel de relecture.
        """
        return {
            "deliverable_id": _texte(ligne["deliverable_id"]),
            "calculation_id": _texte(ligne["calculation_id"]),
            "kind": ligne["kind"],
            "filename": ligne["filename"],
            "media_type": ligne["media_type"],
            "sha256": ligne["sha256"],
            "size_bytes": int(ligne["size_bytes"]),
            "state": ligne["state"],
            "revision": int(ligne["revision"]),
            "supersedes_id": _texte(ligne["supersedes_id"]),
            "watermark": ligne["watermark"],
            "last_reason": ligne["last_reason"],
            "engine_version": ligne["engine_version"],
            "engine_build_sha": ligne["engine_build_sha"],
            "execution_identity": ligne["execution_identity"],
            "validation_id": _texte(ligne["validation_id"]),
            "validator_name": ligne["validator_name"],
            "validated_at": _texte(ligne.get("validated_at")
                                   or ligne.get("signed_at")),
            "generated_at": _texte(ligne["generated_at"]),
        }

    def relire_livrable(self, preuve: Any, *, project_id: str,
                        deliverable_id: str) -> dict[str, Any]:
        """Un livrable, son contexte figé, son attestation et son histoire.

        L'HISTORIQUE VIENT DU MÊME APPEL. Deux appels séparés pourraient
        tomber de part et d'autre d'une transition et montrer un état qui ne
        correspond pas à son journal.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select * from project_deliverable_read(%s::uuid, %s::uuid)",
                (project_id, deliverable_id))
            lignes = self._lignes(u)
        if not lignes:
            raise ConfirmationDomainError(
                f"livrable {deliverable_id}: introuvable dans ce projet. On "
                "refuse plutot que d'afficher un document vide."
            )
        ligne = lignes[0]
        detail = self._livrable_resume(ligne)
        detail.update({
            "inputs_hash": ligne["inputs_hash"],
            "ndp_as_of": _texte(ligne["ndp_as_of"]),
            "validator_role": ligne["validator_role"],
            "professional_id": ligne["professional_id"],
            "statement": ligne["statement"],
            "reservations": ligne["reservations"],
            "validated_at": _texte(ligne["signed_at"]),
            "transitions": [
                {
                    "from_state": t.get("from_state"),
                    "to_state": t.get("to_state"),
                    "actor_id": t.get("actor_id"),
                    "reason": t.get("reason"),
                    "occurred_at": t.get("occurred_at"),
                }
                for t in (_json_ou_none(ligne["transitions"]) or [])
            ],
        })
        return detail

    def octets_du_livrable(self, preuve: Any, *, project_id: str,
                           deliverable_id: str) -> dict[str, Any]:
        """Où sont les octets, et ce qu'ils doivent peser.

        LE CHEMIN NE TRAVERSE PAS JUSQU'À L'ÉCRAN. Il sert au backend à aller
        chercher le fichier ; l'exposer donnerait au navigateur la carte du
        magasin, dont il n'a aucun usage légitime.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select * from project_deliverable_bytes(%s::uuid, %s::uuid)",
                (project_id, deliverable_id))
            lignes = self._lignes(u)
        if not lignes:
            raise ConfirmationDomainError(
                f"livrable {deliverable_id}: introuvable dans ce projet."
            )
        ligne = lignes[0]
        return {
            "storage_backend": ligne["storage_backend"],
            "storage_path": ligne["storage_path"],
            "sha256": ligne["sha256"],
            "size_bytes": int(ligne["size_bytes"]),
            "filename": ligne["filename"],
            "media_type": ligne["media_type"],
            "state": ligne["state"],
            "watermark": ligne["watermark"],
        }

    def transition_livrable(self, preuve: Any, *, project_id: str,
                            deliverable_id: str, to_state: str,
                            reason: str | None = None) -> str:
        """Soumettre à la relecture, ou revenir au brouillon avec un motif.

        ELLE NE CONDUIT QU'À ``draft`` OU ``review``, et la primitive le
        refuse autrement. ``validated`` exige une attestation nominative,
        ``final`` exige qu'elle existe déjà : les deux ont leur propre porte,
        avec leurs propres contrôles d'habilitation.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select project_deliverable_transition("
                "%s::uuid, %s::uuid, %s::deliverable_state, %s)",
                (project_id, deliverable_id, to_state, reason))
            ligne = u.curseur.fetchone()
            if not ligne or not ligne[0]:
                raise ConfirmationDomainError(
                    "la transition n'a rendu aucun etat."
                )
            return str(ligne[0])

    def attester_livrable(self, preuve: Any, *, project_id: str,
                          deliverable_id: str, statement: str,
                          reservations: str | None = None) -> str:
        """L'attestation métier, et le passage à ``validated``, en un seul acte.

        NI NOM, NI RÔLE, NI NUMÉRO D'INSCRIPTION NE SONT PASSÉS. Les trois
        sortent de ``organization_members`` sous l'identité du jeton. Les
        passer d'ici laisserait attester sous le nom de quelqu'un d'autre.

        UN SEUL APPEL POUR DEUX ÉCRITURES. La primitive insère la validation
        et fait basculer le livrable dans la même transaction : deux ordres
        depuis Python laisseraient, sur incident au second, une attestation
        orpheline — c'est-à-dire une signature qui ne porte sur rien.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select project_deliverable_validate("
                "%s::uuid, %s::uuid, %s, %s)",
                (project_id, deliverable_id, statement, reservations))
            ligne = u.curseur.fetchone()
            if not ligne or not ligne[0]:
                raise ConfirmationDomainError(
                    "l'attestation n'a rendu aucun identifiant."
                )
            return str(ligne[0])

    def emettre_livrable(self, preuve: Any, *, project_id: str,
                         deliverable_id: str) -> str:
        """L'émission. Séparée de l'attestation, et délibérément.

        Valider, c'est répondre du calcul ; émettre, c'est mettre le document
        en circulation. Les fondre ferait de toute relecture une publication.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select project_deliverable_finalize(%s::uuid, %s::uuid)",
                (project_id, deliverable_id))
            ligne = u.curseur.fetchone()
            if not ligne or not ligne[0]:
                raise ConfirmationDomainError(
                    "l'emission n'a rendu aucun etat."
                )
            return str(ligne[0])
