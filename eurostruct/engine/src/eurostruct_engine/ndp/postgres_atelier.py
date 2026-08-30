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
