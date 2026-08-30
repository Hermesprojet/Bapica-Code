"""L'empreinte d'implémentation : elle désigne du CODE, pas une phrase.

CE QUE CE MODULE REMPLACE, ET POURQUOI
---------------------------------------
``implementation_payload`` était construit à partir d'``implementation_note``,
une chaîne fournie par le client, et l'interface y déposait une phrase
générique. Deux conséquences, mesurées :

* deux rédactions du même paramètre produisaient deux empreintes. L'empreinte
  ne désignait donc pas l'implémentation, mais la façon dont quelqu'un l'avait
  décrite : deux ingénieurs écrivant la même chose autrement signaient deux
  sujets ;
* le code qui lit et applique le paramètre pouvait changer entièrement — une
  formule corrigée, un facteur déplacé — sans qu'aucune confirmation cesse
  d'être valable. C'est exactement ce que cette empreinte existe pour empêcher.

CE QU'ELLE RÉSUME MAINTENANT
-----------------------------
Le **chemin de code déclaré** qui lit et applique la règle, symbole par
symbole, et la version du moteur. Rien d'autre. Aucun texte, d'aucun client.

POURQUOI UNE CARTE DÉCLARÉE PLUTÔT QU'UNE DÉCOUVERTE
-----------------------------------------------------
On pourrait chercher automatiquement « qui lit ce paramètre » — par analyse
statique, par instrumentation. Une découverte se trompe en silence : un chemin
manqué produit une empreinte qui couvre moins que ce qu'elle prétend couvrir,
et personne ne le voit. Une carte NOMMÉE se trompe bruyamment : une règle
absente n'a pas d'empreinte du tout, et ne peut pas être confirmée.

C'est le même choix qu'à ``normative_authority_manifest()`` en base : ce qui
est déclaré peut être relu ; ce qui est découvert doit être cru.

CE QUE CETTE EMPREINTE FAIT QUAND LE CODE CHANGE
-------------------------------------------------
Elle change. Une confirmation antérieure **reste dans l'historique** — elle est
authentique, elle a eu lieu, et l'audit la voit — mais elle n'ouvre plus le
mode strict : elle atteste d'un code qui n'est plus celui qui tourne. La
passerelle recalcule l'empreinte de son côté et refuse l'écart en le nommant.

Cela veut dire qu'un correctif dans ``design_flexure`` invalide les huit
confirmations belges, et **c'est voulu**. Un paramètre national confirmé pour
un code, puis appliqué par un autre, est une confirmation qui ne dit plus ce
qu'elle croyait dire.

CE QUI RESTE HUMAIN
--------------------
La déclaration et les citations. Elles portent la PREUVE : ce qu'une personne
a lu, à quelle page, et ce qu'elle certifie. Elles peuvent tout changer de la
preuve, et rien de la spécification ni de l'empreinte d'implémentation.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
from functools import lru_cache

from .canonical import CANONICALIZATION_VERSION, Digest, digest_of
from .confirmation import ConfirmationDomainError

__all__ = [
    "CHEMIN_DE_CODE",
    "empreinte_implementation",
    "regles_avec_implementation",
]

#: Les huit paramètres nationaux que le calcul EC2 en flexion exige.
#:
#: ILS PARTAGENT LE MÊME CHEMIN, et ce n'est pas un raccourci : ils sont lus
#: par le même accesseur, filtrés par le même portillon, et appliqués par la
#: même fonction. Les déclarer séparément avec un chemin identique dirait la
#: vérité de façon plus verbeuse, pas de façon plus juste.
_EC2_FLEXION = (
    # LE CHEMIN DE LECTURE. `ParameterSet.get` est ce qui va chercher la
    # valeur; `usable_in_strict_mode` est le portillon qui décide si elle a le
    # droit de servir en mode strict.
    "eurostruct_engine.ndp.registry:ParameterSet.get",
    "eurostruct_engine.ndp.model:NationalParameter.usable_in_strict_mode",
    # LE CHEMIN D'APPLICATION. C'est là que le nombre entre dans une formule.
    "eurostruct_engine.ec2.beam_flexure:design_flexure",
)

_EC2_11 = "EN 1992-1-1"

#: rule_id -> les symboles qui le LISENT et l'APPLIQUENT.
#:
#: UNE RÈGLE ABSENTE N'A PAS D'EMPREINTE, donc ne peut pas être confirmée.
#: C'est le comportement fail-closed voulu : ajouter une règle au registre sans
#: dire quel code l'applique laisserait signer une attestation qui ne couvre
#: rien.
CHEMIN_DE_CODE: dict[str, tuple[str, ...]] = {
    f"{_EC2_11}:{nom}": _EC2_FLEXION
    for nom in (
        "gamma_C_persistent", "gamma_S_persistent",
        "gamma_C_accidental", "gamma_S_accidental",
        "alpha_cc",
        "k1_redistribution", "k2_redistribution",
        "As_min_coeff", "As_min_floor", "As_max_ratio",
    )
}


def regles_avec_implementation() -> tuple[str, ...]:
    """Les règles dont le chemin de code est déclaré. Pour les diagnostics."""
    return tuple(sorted(CHEMIN_DE_CODE))


def _resoudre(symbole: str):
    """``"module:Qualname"`` -> l'objet, ou un refus qui nomme ce qui manque."""
    module_nom, _, qualname = symbole.partition(":")
    if not module_nom or not qualname:
        raise ConfirmationDomainError(
            f"symbole {symbole!r} mal forme: attendu « module:Qualname »."
        )
    try:
        objet = importlib.import_module(module_nom)
    except ImportError as cause:
        raise ConfirmationDomainError(
            f"le chemin de code declare cite le module {module_nom!r}, "
            "introuvable. L'empreinte d'implementation ne peut pas etre "
            "calculee, et on ne la devine pas."
        ) from cause
    for morceau in qualname.split("."):
        try:
            objet = inspect.getattr_static(objet, morceau)
        except AttributeError as cause:
            raise ConfirmationDomainError(
                f"le chemin de code declare cite {symbole!r}, et "
                f"{morceau!r} n'existe pas. Un chemin qui ne resout plus "
                "designe un code qui a bouge sans que la carte suive."
            ) from cause
    return objet


def _source_du_symbole(symbole: str) -> str:
    """Le TEXTE SOURCE du symbole désigné.

    ``getattr_static`` rend l'objet du dictionnaire de classe, si bien qu'une
    ``property`` arrive telle quelle : on prend son accesseur, qui est le code
    réellement exécuté. Une méthode statique ou de classe arrive enveloppée,
    et ``__func__`` la déballe.

    ON NE NORMALISE PAS LA SOURCE. Ni indentation, ni commentaires retirés :
    l'empreinte doit bouger dès que le fichier bouge sur ce symbole. Une
    normalisation choisirait quels changements « ne comptent pas », et ce choix
    n'appartient pas à ce module.
    """
    cible = symbole.rsplit(":", 1)[-1]
    objet = _resoudre(symbole)
    if isinstance(objet, property):
        objet = objet.fget
    objet = getattr(objet, "__func__", objet)
    try:
        return inspect.getsource(objet)
    except (OSError, TypeError) as cause:
        raise ConfirmationDomainError(
            f"la source de {cible!r} n'est pas lisible ({type(cause).__name__}). "
            "Sans elle, l'empreinte d'implementation ne resumerait rien; on "
            "refuse plutot que d'en fabriquer une."
        ) from cause


@lru_cache(maxsize=256)
def empreinte_implementation(rule_id: str) -> Digest:
    """L'empreinte du code qui lit et applique ``rule_id``.

    UN SEUL PARAMÈTRE, ET C'EST LA GARANTIE. Il n'y a aucune façon de faire
    entrer un texte ici : ce qui est haché sort du dépôt et de la version du
    moteur, pas d'une requête.

    :raises ConfirmationDomainError: aucun chemin de code n'est déclaré pour
        cette règle, ou l'un des symboles déclarés ne résout plus.
    """
    from ..version import ENGINE_NAME, ENGINE_VERSION

    chemin = CHEMIN_DE_CODE.get(rule_id)
    if not chemin:
        raise ConfirmationDomainError(
            f"aucun chemin de code n'est declare pour {rule_id!r}. Une regle "
            "dont on ne sait pas nommer le code qui l'applique ne peut pas "
            "etre confirmee: l'attestation ne couvrirait rien. Declarer le "
            "chemin dans ndp/implementation.py, ou retirer la regle."
        )
    return digest_of({
        "kind": "implementation",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": rule_id,
        "engine_name": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        # ORDRE DÉCLARÉ, PAS TRIÉ. Le chemin dit « on lit, on filtre, on
        # applique »: le réordonner effacerait cette lecture, et la
        # canonicalisation trierait de toute façon les clés, pas cette liste.
        "code_path": [
            {"symbol": s,
             "source_sha256": hashlib.sha256(
                 _source_du_symbole(s).encode("utf-8")).hexdigest()}
            for s in chemin
        ],
    })
