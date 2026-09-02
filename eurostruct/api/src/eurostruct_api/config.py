"""La configuration vient de l'environnement, et de nulle part ailleurs.

CE QUE CE MODULE REFUSE DE FAIRE
---------------------------------
Il ne devine pas. Une variable absente n'est pas remplacee par une valeur
« raisonnable » : elle rend la configuration invalide, et le refus nomme la
variable manquante. Deviner une URL de base, c'est ecrire dans une base que
personne n'a designee ; deviner un `issuer`, c'est accepter les jetons d'un
emetteur que personne n'a choisi.

CE QU'IL NE JOURNALISE JAMAIS
------------------------------
Aucune valeur de secret, aucune URL de connexion complete, aucun jeton.
:meth:`Reglages.diagnostic` ne rend que des booleens et des formes — « pose »
ou « absent » — parce qu'un diagnostic qui recopie un mot de passe pour dire
qu'il est present est une fuite deguisee en aide au debogage.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationInvalide(RuntimeError):
    """La configuration ne permet pas de servir. Refus, jamais repli."""


#: Algorithmes ASYMETRIQUES uniquement. `HS256` est exclu deliberement: avec un
#: secret partage, quiconque peut verifier peut aussi signer, et le JWKS public
#: de Supabase deviendrait une cle de forge. `none` n'est meme pas nommable.
ALGORITHMES_AUTORISES = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512")


@dataclass(frozen=True, slots=True)
class ReglagesAuth:
    """De quoi verifier un jeton, et rien de plus."""

    jwks_url: str
    issuer: str
    audience: str
    algorithmes: tuple[str, ...]
    #: Tolerance d'horloge, en secondes. Bornee: une tolerance large rend
    #: l'expiration decorative.
    tolerance_horloge_s: int = 60

    @property
    def configure(self) -> bool:
        return bool(self.jwks_url and self.issuer and self.audience)


@dataclass(frozen=True, slots=True)
class ReglagesBase:
    """De quoi ouvrir une connexion, sans jamais la recomposer en clair."""

    dsn: str

    @property
    def configure(self) -> bool:
        return bool(self.dsn)


#: Origines autorisees par defaut: le poste de developpement, et rien d'autre.
#: EN PRODUCTION, ELLES SE DECLARENT. Un `*` ici laisserait n'importe quelle
#: page du web appeler l'API avec les cookies du navigateur.
ORIGINES_LOCALES = ("http://localhost:3000", "http://127.0.0.1:3000")


@dataclass(frozen=True, slots=True)
class Reglages:
    auth: ReglagesAuth
    base: ReglagesBase
    #: D'ou l'interface a le droit d'appeler. Jamais `*`.
    origines: tuple[str, ...] = ORIGINES_LOCALES
    #: `true` en developpement local uniquement. N'assouplit AUCUNE
    #: verification: change seulement le detail rendu dans les refus 500.
    mode_debogage: bool = False

    def diagnostic(self) -> dict[str, object]:
        """Ce qu'on peut dire de la configuration sans rien en reveler."""
        return {
            "auth": {
                "jwks_url_pose": bool(self.auth.jwks_url),
                "issuer_pose": bool(self.auth.issuer),
                "audience_pose": bool(self.auth.audience),
                "algorithmes": list(self.auth.algorithmes),
                "configure": self.auth.configure,
            },
            "base": {"dsn_pose": bool(self.base.dsn),
                     "configure": self.base.configure},
        }


def _algorithmes(brut: str | None) -> tuple[str, ...]:
    if not brut:
        return ("RS256",)
    demandes = tuple(a.strip().upper() for a in brut.split(",") if a.strip())
    refuses = [a for a in demandes if a not in ALGORITHMES_AUTORISES]
    if refuses:
        raise ConfigurationInvalide(
            f"algorithme(s) refuse(s): {', '.join(refuses)}. Seuls les "
            f"algorithmes asymetriques sont acceptes ({', '.join(ALGORITHMES_AUTORISES)}). "
            "Un algorithme a secret partage ferait du JWKS public une cle de "
            "forge; « none » n'est pas une signature."
        )
    return demandes


def charger(env: dict[str, str] | None = None) -> Reglages:
    """Lit l'environnement. Ne leve que si une valeur POSEE est invalide.

    L'absence n'est pas une erreur ici — c'est `/ready` qui refuse de se
    declarer pret, et les routes protegees qui refusent de servir. Cette
    distinction permet de demarrer le processus, de le sonder, et de LIRE
    pourquoi il n'est pas pret, au lieu de mourir au boot sans rien dire.
    """
    e = os.environ if env is None else env
    return Reglages(
        auth=ReglagesAuth(
            jwks_url=e.get("EUROSTRUCT_SUPABASE_JWKS_URL", "").strip(),
            issuer=e.get("EUROSTRUCT_SUPABASE_ISSUER", "").strip(),
            audience=e.get("EUROSTRUCT_SUPABASE_AUDIENCE", "").strip(),
            algorithmes=_algorithmes(e.get("EUROSTRUCT_JWT_ALGORITHMS")),
            tolerance_horloge_s=_tolerance(e.get("EUROSTRUCT_JWT_LEEWAY_S")),
        ),
        base=ReglagesBase(dsn=e.get("EUROSTRUCT_DATABASE_URL", "").strip()),
        origines=_origines(e.get("EUROSTRUCT_CORS_ORIGINS")),
        mode_debogage=e.get("EUROSTRUCT_DEBUG", "").lower() in ("1", "true", "yes"),
    )


def _origines(brut: str | None) -> tuple[str, ...]:
    """Origines autorisees, explicites. `*` est REFUSE.

    Un joker laisserait n'importe quelle page du web appeler cette API depuis
    le navigateur d'un utilisateur connecte. C'est le genre de commodite qu'on
    ajoute « pour deboguer » et qu'on oublie de retirer.
    """
    if not brut:
        return ORIGINES_LOCALES
    demandees = tuple(o.strip() for o in brut.split(",") if o.strip())
    if "*" in demandees:
        raise ConfigurationInvalide(
            "EUROSTRUCT_CORS_ORIGINS ne peut pas valoir « * ». Declarez les "
            "origines une a une: un joker laisserait n'importe quelle page du "
            "web appeler cette API depuis le navigateur d'un utilisateur."
        )
    for o in demandees:
        if not o.startswith(("http://", "https://")):
            raise ConfigurationInvalide(
                f"origine invalide ({o!r}): une origine porte son schema, "
                "son hote et son port, sans chemin."
            )
    return demandees


def _tolerance(brut: str | None) -> int:
    if not brut:
        return 60
    try:
        v = int(brut)
    except ValueError as cause:
        raise ConfigurationInvalide(
            f"EUROSTRUCT_JWT_LEEWAY_S n'est pas un entier ({brut!r})."
        ) from cause
    if not 0 <= v <= 300:
        raise ConfigurationInvalide(
            f"EUROSTRUCT_JWT_LEEWAY_S={v} hors bornes [0, 300]. Une tolerance "
            "large rend l'expiration decorative."
        )
    return v
