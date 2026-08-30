"""Provider PostgreSQL des confirmations et des décisions d'autorité.

Ce que ce module est
--------------------
La **frontière** entre le domaine — qui ne connaît aucune base — et
PostgreSQL, qui détient l'autorité. Il implémente
:class:`~eurostruct_engine.ndp.confirmation.ConfirmationProvider` pour la
lecture, et il porte en plus les trois primitives de décision du quatre-yeux.

Ce qu'il n'est pas
------------------
**Il n'authentifie personne.** Il exige qu'on lui *fournisse* un
authentificateur, et il refuse d'ouvrir la moindre requête privilégiée sans
lui. Tant qu'aucun vérificateur de jeton concret n'existe dans ce dépôt, le
statut du sous-système reste ``BLOCKED_BY_REAL_AUTH`` : ce module ne le lève
pas, il en rend l'absence *bloquante* au lieu de silencieuse.

Aucun pilote n'est importé ici
------------------------------
Ni ``psycopg``, ni ``psycopg2``, ni ``asyncpg``. La connexion est reçue et
doit satisfaire :class:`Connexion` — trois méthodes, celles de la DB-API. Deux
raisons, et la seconde compte autant que la première :

1. le moteur reste installable sans pilote, et ``engine/tests`` continue de
   prouver que le **domaine** ne dépend d'aucune base ;
2. le contrat SQL s'éprouve alors contre un **vrai** PostgreSQL, avec le
   pilote qu'on veut, sans que le paquet en impose un.

Ce que le contrat exige, et pourquoi chaque point y est
-------------------------------------------------------
``actor``, ``proposer`` et ``approver`` **n'apparaissent dans aucune
signature publique**. C'est la leçon de 6.3c : *un UUID reçu est une donnée,
jamais une preuve d'identité*. Les primitives SQL, elles non plus, ne
reçoivent pas d'acteur — elles le dérivent du contexte de session, que seul ce
module pose, et seulement après authentification.

``SET LOCAL`` et jamais ``SET``. Un ``SET`` de session survit à la connexion
rendue au pool : le locataire suivant hériterait de l'identité du précédent.
``SET LOCAL`` meurt avec la transaction — commit, rollback ou exception, sans
exception possible. C'est la seule différence entre « l'acteur est posé pour
cette unité de travail » et « l'acteur traîne ».
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, runtime_checkable

from .confirmation import (
    ConfirmationDomainError,
    NormativeRuleConfirmation,
    NormativeRuleConfirmationRevocation,
)
from .projection import (
    COLONNES_CONFIRMATION,
    COLONNES_REVOCATION,
    confirmation_depuis_ligne,
    revocation_depuis_ligne,
)

__all__ = [
    "Connexion",
    "Curseur",
    "Authentificateur",
    "ContexteAuthentifie",
    "AuthentificationRequise",
    "PostgresConfirmationProvider",
    "RefusSqlTraduits",
]


# ---------------------------------------------------------------------------
# CE QUE POSTGRESQL REFUSE EXPRÈS, ET CE QUI EST SIMPLEMENT CASSÉ
# ---------------------------------------------------------------------------
# Les deux arrivent ici sous la même forme — une exception du pilote — et il
# faut pourtant les séparer, parce qu'elles ne disent pas la même chose :
#
#   * « le proposant ne peut pas approuver sa propre décision » est une RÈGLE.
#     Elle s'adresse à l'ingénieur, elle doit remonter jusqu'à lui, et son
#     message a été écrit pour être lu ;
#   * « connection to server failed » est une PANNE. Elle ne s'adresse à
#     personne d'autre qu'à nous, et son message porte la chaîne de connexion.
#
# La couche HTTP ne peut pas trancher: elle voit deux exceptions de pilote.
# C'est ici, à la frontière du SQL, qu'on sait laquelle est laquelle — et
# PostgreSQL le dit lui-même, par son SQLSTATE.
#
# Avant ce tri, les routes attrapaient `Exception` et rendaient `str(cause)`
# en 422: la chaîne de connexion complète partait au client, sous un code qui
# se lit « votre demande est refusée ».

#: SQLSTATE que NOS PROPRES objets provoquent délibérément.
ETATS_DE_REFUS: frozenset[str] = frozenset({
    "P0001",   # raise_exception: un `raise exception` de nos fonctions
    "42501",   # insufficient_privilege: un refus de la frontière de rôles
})

#: Familles de SQLSTATE qui sont elles aussi nos règles — classe 23, violation
#: de contrainte d'intégrité: `check`, `unique`, clé étrangère.
FAMILLES_DE_REFUS: tuple[str, ...] = ("23",)


def _message_de_refus(cause: Exception, etat: str) -> str:
    """Le texte qu'on a le droit de faire sortir, et rien d'autre.

    ``str(cause)`` d'une erreur psycopg2 concatène le message, le ``DETAIL`` et
    parfois le ``CONTEXT`` : sur une violation de contrainte, le ``DETAIL``
    contient **la ligne fautive**, données comprises. On ne le recopie donc
    jamais.

    * ``P0001`` — le message est celui que nous avons écrit dans la fonction
      PL/pgSQL. Il est destiné à l'appelant, on le rend tel quel ;
    * classe 23 — on ne nomme que la **contrainte**, qui est un nom de règle
      que nous avons choisi (« decision_two_distinct_principals »). Ni la
      table, ni la ligne ;
    * ``42501`` — un texte fixe. Le message du serveur nomme l'objet et le
      rôle, ce qui décrit notre schéma à qui ne devrait pas le connaître.
    """
    diag = getattr(cause, "diag", None)
    if etat == "P0001":
        principal = getattr(diag, "message_primary", None)
        return principal or "la base a refuse cette operation."
    if etat.startswith(FAMILLES_DE_REFUS):
        contrainte = getattr(diag, "constraint_name", None)
        if contrainte:
            return (f"la regle « {contrainte} » refuse cette ecriture. Elle "
                    "est posee dans la base et s'applique quel que soit "
                    "l'appelant.")
        return "une regle d'integrite de la base refuse cette ecriture."
    return "cette operation n'est pas permise a l'identite presentee."


class RefusSqlTraduits:
    """Traduit les refus DÉLIBÉRÉS de PostgreSQL, laisse passer les pannes.

    Ce n'est pas un filet de sécurité : c'est un tri. Ce qui n'est pas reconnu
    comme une règle **remonte tel quel**, pour être traité comme le défaut que
    c'est — un 500 avec identifiant de corrélation, et rien dans le corps.
    """

    __slots__ = ()

    def __enter__(self) -> RefusSqlTraduits:
        return self

    def __exit__(self, _type, valeur, _trace) -> bool:
        if valeur is None or isinstance(valeur, ConfirmationDomainError):
            return False
        etat = getattr(valeur, "pgcode", None)
        if not isinstance(etat, str) or not etat:
            return False
        if etat in ETATS_DE_REFUS or etat.startswith(FAMILLES_DE_REFUS):
            raise ConfirmationDomainError(
                _message_de_refus(valeur, etat)) from valeur
        return False


# ---------------------------------------------------------------------------
# La forme minimale d'une connexion — DB-API, et rien de plus
# ---------------------------------------------------------------------------
@runtime_checkable
class Curseur(Protocol):
    def execute(self, requete: str, parametres: Any = ...) -> Any: ...
    def fetchall(self) -> list[Any]: ...
    def fetchone(self) -> Any: ...
    def close(self) -> None: ...

    #: Les noms de colonnes du dernier `select`. DÉCLARÉ parce que la lecture
    #: s'en sert pour nommer les champs: un curseur conforme qui ne le porte
    #: pas ferait échouer la projection, et l'exigence doit se lire ici plutôt
    #: que se découvrir à l'exécution.
    description: Any


@runtime_checkable
class Connexion(Protocol):
    def cursor(self) -> Curseur: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


# ---------------------------------------------------------------------------
# L'identité — produite par un authentificateur, jamais par l'appelant
# ---------------------------------------------------------------------------
class AuthentificationRequise(ConfirmationDomainError):
    """Aucun authentificateur, ou aucune identité : refus avant toute requête.

    Elle hérite de :class:`ConfirmationDomainError` pour qu'un appelant qui
    attrape déjà les erreurs du domaine ne laisse pas celle-ci filer.
    """


#: Jeton interne. Il n'a qu'un rôle : rendre :class:`ContexteAuthentifie`
#: **non constructible depuis l'extérieur du module**.
#:
#: PYTHON NE PERMET PAS D'INTERDIRE, IL PERMET DE RENDRE DÉLIBÉRÉ. Un appelant
#: déterminé peut importer ce symbole — il est là, sous les yeux. Ce qu'il ne
#: peut pas faire, c'est fabriquer un contexte *par accident*, ni en écrivant
#: du code qui a l'air normal. C'est exactement la distinction que 6.3c pose
#: entre une donnée et une preuve : le contournement doit être visible dans le
#: diff, et se lire comme ce qu'il est.
_JETON_INTERNE = object()


@dataclass(frozen=True, slots=True)
class ContexteAuthentifie:
    """Le résultat d'une authentification réussie. Jamais autre chose.

    ``actor_id`` est l'identité du principal, telle que l'authentificateur l'a
    établie. Elle n'est **pas** un paramètre d'API : elle sort d'ici, elle n'y
    entre pas.
    """

    actor_id: str
    emis_par: str
    _jeton: Any = field(repr=False, default=None)

    def __post_init__(self) -> None:
        if self._jeton is not _JETON_INTERNE:
            raise AuthentificationRequise(
                "ContexteAuthentifie ne se construit pas depuis l'exterieur. "
                "Un contexte fabrique par l'appelant serait exactement ce que "
                "6.3c refuse: une donnee presentee comme une preuve "
                "d'identite. Passez par un Authentificateur."
            )
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise AuthentificationRequise(
                "identite vide: un authentificateur qui ne nomme personne n'a "
                "pas authentifie."
            )


@runtime_checkable
class Authentificateur(Protocol):
    """Ce qui transforme une preuve externe en identité.

    Le provider ne sait pas ce qu'est un jeton, ni comment on le vérifie. Il
    sait seulement qu'il ne travaille pas sans réponse d'ici.
    """

    @property
    def identite_de_l_authentificateur(self) -> str:
        """Inscrit dans la trace: on doit savoir QUI a authentifié."""
        ...

    @property
    def est_fictif(self) -> bool:
        """Vrai pour un authentificateur de test. Un vrai répond ``False``."""
        ...

    def authentifier(self, preuve: Any) -> ContexteAuthentifie:
        """Rend un contexte, ou lève. Ne rend jamais ``None``."""
        ...


def creer_contexte(actor_id: str, emis_par: str) -> ContexteAuthentifie:
    """Réservé aux implémentations d':class:`Authentificateur`.

    C'est la seule fabrique de contexte. Elle est publique parce qu'un
    authentificateur vit forcément dans un autre module — et elle est nommée
    de façon à ce qu'un appel depuis un chemin applicatif saute aux yeux en
    relecture.
    """
    return ContexteAuthentifie(actor_id=actor_id, emis_par=emis_par,
                               _jeton=_JETON_INTERNE)


# ---------------------------------------------------------------------------
# Le provider
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class PostgresConfirmationProvider:
    """Lit les confirmations et porte les décisions, sous identité vérifiée.

    ``connexion`` doit satisfaire :class:`Connexion`. ``authentificateur``
    doit satisfaire :class:`Authentificateur` — **son absence est une erreur
    de construction**, pas un mode dégradé : un provider sans authentificateur
    ne peut rien faire d'utile, et le laisser exister inviterait à l'utiliser.
    """

    connexion: Connexion
    authentificateur: Authentificateur

    #: Nom du réglage de session que les primitives SQL lisent. Il est posé par
    #: `SET LOCAL`, donc lié à la transaction.
    REGLAGE_ACTEUR: str = "eurostruct.actor_id"

    #: Les rôles que les politiques de lecture couvrent en ``using (true)``.
    #: Voir :meth:`_exiger_un_role_qui_voit`: hors de cette liste, un SELECT
    #: rend zéro ligne **sans erreur**, et zéro ligne se lit « aucune
    #: confirmation ». La liste est ici, à côté du code qui s'en sert, plutôt
    #: que devinée à l'exécution: elle doit changer avec les migrations, et se
    #: relire dans le même diff qu'elles.
    ROLES_QUI_VOIENT: ClassVar[tuple[str, ...]] = (
        "normative_backend",
        "eurostruct_authority_backend",
        "normative_governance",
        "eurostruct_normative_writer",
    )

    def __post_init__(self) -> None:
        if self.authentificateur is None:
            raise AuthentificationRequise(
                "provider construit sans authentificateur. Le sous-systeme "
                "d'autorite reste BLOCKED_BY_REAL_AUTH: refus avant toute "
                "requete privilegiee."
            )
        if not isinstance(self.authentificateur, Authentificateur):
            raise AuthentificationRequise(
                "l'objet fourni comme authentificateur ne satisfait pas le "
                "protocole Authentificateur: il ne peut pas produire "
                "d'identite, et le provider refuse plutot que de deviner."
            )
        if not isinstance(self.connexion, Connexion):
            raise TypeError(
                "la connexion fournie ne satisfait pas le protocole Connexion "
                "(cursor/commit/rollback)."
            )

    # ------------------------------------------------------------------ trace
    @property
    def provider_identity(self) -> str:
        return (f"postgres://autorite?auth="
                f"{self.authentificateur.identite_de_l_authentificateur}")

    @property
    def is_fictional(self) -> bool:
        """FICTIF DES QUE L'AUTHENTIFICATEUR L'EST, et c'est le point.

        Un provider PostgreSQL branché sur un authentificateur de test n'est
        pas « presque réel » : les identités qu'il pose sont fabriquées.
        `assert_provider_is_usable_in_production` doit donc le refuser, et
        c'est ici que cela se décide — pas dans la conscience de l'appelant.
        """
        return bool(self.authentificateur.est_fictif)

    # ------------------------------------------------------- unité de travail
    def _unite(self, preuve: Any):
        """Ouvre une transaction, y pose l'identité, la referme quoi qu'il arrive.

        L'ORDRE EST LE CONTRAT : authentifier, PUIS ouvrir, PUIS `SET LOCAL`.
        Authentifier après avoir ouvert une transaction privilégiée
        laisserait une fenêtre où la connexion est engagée sans que personne
        ne soit nommé.
        """
        contexte = self.authentificateur.authentifier(preuve)
        if not isinstance(contexte, ContexteAuthentifie):
            raise AuthentificationRequise(
                "l'authentificateur n'a pas rendu un ContexteAuthentifie: "
                "une valeur quelconque ne vaut pas identite."
            )
        return _UniteDeTravail(self.connexion, contexte, self.REGLAGE_ACTEUR)

    # ----------------------------------------------------- lecture (Protocol)
    def _lire(self, requete: str, parametres: Any) -> list[dict[str, Any]]:
        """Une lecture, dans sa propre transaction, terminée par un rollback.

        PAS D'ACTEUR POSÉ, ET C'EST EXACT. Les politiques de lecture des
        confirmations sont ``using (true)`` pour les rôles de service : le
        référentiel normatif n'est pas une donnée de locataire, et une
        confirmation belge vaut pour toutes les études belges. Poser un acteur
        ici laisserait croire que la visibilité en dépend.

        ``rollback`` plutôt que ``commit`` : une lecture n'a rien à valider, et
        une transaction laissée ouverte tiendrait un instantané indéfiniment.

        AUCUN ``begin`` EXPLICITE ICI, ET LA PREMIÈRE RÉDACTION EN METTAIT UN.
        Le garde de rôle interroge la base *avant* la requête ; avec une
        connexion en ``autocommit=False``, ce premier ordre a déjà ouvert la
        transaction. Le ``begin`` qui suivait arrivait donc toujours en second,
        et PostgreSQL répondait ``WARNING: there is already a transaction in
        progress`` — à **chaque** lecture. Mesuré, pas supposé.

        L'écriture, elle, garde son ``begin`` explicite : ``SET LOCAL`` n'a
        aucune portée hors transaction, et une connexion reçue en autocommit
        poserait l'acteur pour la durée d'une seule instruction.

        Le garde partage désormais le curseur de la lecture, donc sa
        transaction : le rôle ne peut plus changer entre le contrôle et la
        requête qu'il autorise.
        """
        curseur = self.connexion.cursor()
        try:
            self._exiger_un_role_qui_voit(curseur)
            curseur.execute(requete, parametres)
            colonnes = [d[0] for d in curseur.description]
            return [dict(zip(colonnes, ligne, strict=True))
                    for ligne in curseur.fetchall()]
        finally:
            try:
                self.connexion.rollback()
            finally:
                curseur.close()

    def _exiger_un_role_qui_voit(self, curseur: Any = None) -> None:
        """Refuser de lire sous un rôle dont RLS masque tout.

        LA RAISON D'ÊTRE DE CETTE MÉTHODE. Sous ``row level security``, un rôle
        sans politique applicable ne reçoit pas d'erreur : il reçoit **zéro
        ligne**. « Je n'ai pas le droit de voir » et « il n'y en a aucune »
        deviennent le même octet, et c'est le second que lirait un décompte à
        quatre yeux — donc une règle réputée non confirmée alors qu'elle l'est,
        ou l'inverse le jour où une politique change.

        On demande donc à PostgreSQL, avant de conclure quoi que ce soit d'un
        ensemble vide, si le rôle courant est de ceux que les politiques
        ``using (true)`` couvrent.

        ``curseur`` est celui de la lecture quand elle en fournit un : le
        contrôle et la requête qu'il autorise partagent alors la même
        transaction. Sans argument — usage de diagnostic — la méthode ouvre et
        referme le sien.
        """
        propre = curseur is None
        curseur = self.connexion.cursor() if propre else curseur
        try:
            curseur.execute(
                "select bool_or(pg_has_role(current_user, r, 'usage')) "
                "from unnest(%s::text[]) r "
                "where exists (select 1 from pg_roles where rolname = r)",
                (list(self.ROLES_QUI_VOIENT),),
            )
            ligne = curseur.fetchone()
        finally:
            if propre:
                curseur.close()
        if not (ligne and ligne[0]):
            raise ConfirmationDomainError(
                "le role de cette connexion n'est couvert par aucune politique "
                f"de lecture des confirmations ({', '.join(self.ROLES_QUI_VOIENT)}). "
                "Lire quand meme rendrait zero ligne SANS ERREUR, et zero ligne "
                "se lit « aucune confirmation » — une REPONSE, et fausse. On "
                "refuse au lieu de repondre a la place de la base."
            )

    def confirmations_for(
        self, rule_id: str,
    ) -> tuple[NormativeRuleConfirmation, ...]:
        """Les confirmations portant *rule_id*, projetées et vérifiées.

        L'ordre est déterministe (``verified_at``, puis l'identifiant) : deux
        lectures de la même base doivent rendre la même séquence, sans quoi un
        diagnostic serait irreproductible.
        """
        colonnes = ", ".join(COLONNES_CONFIRMATION)
        lignes = self._lire(
            f"select {colonnes} from normative_rule_confirmations "
            "where rule_id = %s order by verified_at, id",
            (rule_id,),
        )
        return tuple(confirmation_depuis_ligne(ligne) for ligne in lignes)

    def revocations_for(
        self, rule_id: str,
    ) -> tuple[NormativeRuleConfirmationRevocation, ...]:
        """Les révocations visant les confirmations de *rule_id*.

        La table des révocations ne porte pas ``rule_id`` — une révocation vise
        une confirmation, pas une règle. La jointure est donc ce qui rattache
        les deux, et la faire ici plutôt que côté appelant évite qu'un appelant
        l'oublie et conclue « aucune révocation ».
        """
        colonnes = ", ".join(f"r.{c}" for c in COLONNES_REVOCATION)
        lignes = self._lire(
            f"select {colonnes} from normative_rule_confirmation_revocations r "
            "join normative_rule_confirmations c on c.id = r.confirmation_id "
            "where c.rule_id = %s order by r.revoked_at, r.id",
            (rule_id,),
        )
        return tuple(revocation_depuis_ligne(ligne) for ligne in lignes)

    # ------------------------------------------------- décisions (quatre-yeux)
    def proposer_decision(
        self, preuve: Any, *, subject_kind: str, subject_id: str,
        org_id: str | None, country_code: str, standard_family: str,
        part: str, edition: str, permission: str, reason: str,
    ) -> str:
        """Propose une décision **sous l'identité authentifiée**.

        Aucun paramètre ne nomme le proposant. ``subject_*``, la portée et le
        motif sont des DONNÉES — ce sur quoi la décision porte — et n'ont
        aucune valeur probante.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer(
                "select normative_decision_propose("
                "%s, %s, %s, %s::country_code, %s, %s, %s, "
                "%s::normative_permission, %s)",
                (subject_kind, subject_id, org_id, country_code,
                 standard_family, part, edition, permission, reason),
            )
            ligne = u.curseur.fetchone()
            return ligne[0] if ligne else ""

    def approuver_decision(self, preuve: Any, *, decision_id: str) -> None:
        """Approuve. L'approbateur est l'identité authentifiée, et elle seule.

        PostgreSQL refuse que ce soit le proposant — contrainte de table, pas
        vérification applicative.
        """
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer("select normative_decision_approve(%s::uuid)",
                       (decision_id,))

    def consommer_decision(self, preuve: Any, *, decision_id: str) -> Any:
        """Consomme une décision approuvée, une fois."""
        with RefusSqlTraduits(), self._unite(preuve) as u:
            u.executer("select normative_decision_consume(%s::uuid)",
                       (decision_id,))
            return u.curseur.fetchone()

    # ------------------------------------------------------------- diagnostic
    def acteur_courant(self) -> str:
        """Ce que la session voit MAINTENANT, hors transaction.

        Sert aux preuves de non-fuite: après un commit, un rollback ou une
        exception, cette valeur doit être vide.
        """
        curseur = self.connexion.cursor()
        try:
            curseur.execute(
                f"select coalesce(current_setting('{self.REGLAGE_ACTEUR}', "
                "true), '')")
            ligne = curseur.fetchone()
            return (ligne[0] if ligne else "") or ""
        finally:
            curseur.close()


@dataclass
class _UniteDeTravail:
    """Une transaction, une identité, et rien qui survive à sa fin."""

    connexion: Connexion
    contexte: ContexteAuthentifie
    reglage: str
    curseur: Any = None

    def __enter__(self) -> _UniteDeTravail:
        self.curseur = self.connexion.cursor()
        # LA TRANSACTION EST EXPLICITE. En autocommit, `SET LOCAL` n'a aucune
        # portée: il meurt à la fin de l'instruction, et l'acteur ne serait
        # pas posé quand la primitive le lit. Le rendre explicite ici évite de
        # dépendre du mode de la connexion reçue.
        self.curseur.execute("begin")
        # `set_config(..., true)` EST le `SET LOCAL`, en forme paramétrable.
        # Concaténer l'identité dans le texte SQL serait une injection de plus
        # dans un endroit où elle serait fatale.
        self.curseur.execute("select set_config(%s, %s, true)",
                             (self.reglage, self.contexte.actor_id))
        return self

    def executer(self, requete: str, parametres: Any = None) -> None:
        self.curseur.execute(requete, parametres)

    def __exit__(self, type_exc, valeur, trace) -> bool:
        try:
            if type_exc is None:
                self.connexion.commit()
            else:
                self.connexion.rollback()
        finally:
            try:
                self.curseur.close()
            except Exception:  # noqa: BLE001 — fermer ne doit jamais masquer
                pass
        # PAS DE `RESET` ICI, ET C'EST VOULU: `SET LOCAL` meurt avec la
        # transaction. Ajouter un reset explicite donnerait l'illusion que la
        # propriété vient du code applicatif, alors qu'elle vient de
        # PostgreSQL — et masquerait le jour où quelqu'un remplacerait
        # `set_config(..., true)` par `set_config(..., false)`.
        return False
