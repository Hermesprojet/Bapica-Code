"""L'identité d'EXÉCUTION : requête, référentiel appliqué, code qui a tourné.

CE QU'``inputs_hash`` DIT, ET CE QU'IL NE DIT PAS
--------------------------------------------------
``inputs_hash`` est l'empreinte de la **requête**, et rien d'autre. Il répond
à « est-ce la même demande ? ». Il ne répond pas à « obtiendra-t-on le même
résultat ? », et le commentaire de ``0001`` — « deux calculs de même hash
doivent produire le même resultat bit-a-bit » — n'est vrai que sous deux
conditions que l'empreinte ne porte pas :

* **le même code** — six commits successifs portent ``0.3.0`` ; la version ne
  désigne aucun build ;
* **le même référentiel** — une confirmation arrivée entre les deux calculs
  change la valeur d'un paramètre national, donc le résultat, pour une requête
  strictement identique.

Deux calculs de même ``inputs_hash`` et d'identités d'exécution différentes
peuvent légitimement différer. C'est précisément ce qu'il faut pouvoir dire.

CE QUE L'IDENTITÉ D'EXÉCUTION AJOUTE
--------------------------------------
Les trois ensemble : la requête canonique, l'instantané NDP **réellement
utilisé**, et le build. Deux exécutions de même identité doivent rendre le
même résultat ; deux résultats différents sous la même identité sont un
défaut, et celui-là mérite qu'on le cherche.

ELLE NE REMPLACE PAS ``inputs_hash``, ELLE LE SITUE. L'un sert à retrouver
« le même calcul » ; l'autre à affirmer « la même exécution ». Les fondre
ferait perdre la première question, qui est celle qu'un ingénieur pose.

LA CANONICALISATION EST CELLE DU DÉPÔT
----------------------------------------
``digest_of`` et ``CANONICALIZATION_VERSION`` viennent de ``canonical.py``,
comme les quatre empreintes du dossier de revue. Un second mécanisme —
``json.dumps`` avec ses propres options — dériverait au premier réglage
changé, et ce serait toujours le plus faible qui servirait ici.
"""

from __future__ import annotations

from typing import Any

from .canonical import CANONICALIZATION_VERSION, Digest, digest_of

__all__ = ["identite_execution"]


def identite_execution(
    *,
    request: Any,
    ndp_snapshot: Any,
    engine_name: str,
    engine_version: str,
    build_sha: str,
) -> Digest:
    """L'identité de cette exécution-là.

    Les paramètres sont **nommés obligatoirement** : un appel positionnel
    permettrait d'intervertir la requête et l'instantané, et le calcul
    réussirait en produisant une identité parfaitement stable et parfaitement
    fausse.

    :param request: la requête EXACTE reçue par le moteur, déjà projetée en
        types JSON. C'est la même valeur que celle enregistrée dans
        ``calculations.request`` : les deux doivent rester le même objet, sans
        quoi l'identité désignerait une exécution que la base ne conserve pas.
    :param ndp_snapshot: l'état du portillon normatif au moment du calcul.
        Il change quand une confirmation arrive ou est révoquée.
    :param build_sha: l'identité du build, injectée par l'environnement. Jamais
        déduite du dépôt courant — voir ``eurostruct_engine.build``.
    """
    if not build_sha:
        # UNE IDENTITE SANS BUILD N'EN EST PAS UNE. La construire quand meme
        # produirait une valeur qui a l'air d'une preuve; l'appelant doit
        # refuser d'enregistrer, et c'est a lui de le decider.
        raise ValueError(
            "identite d'execution sans identite de build: elle designerait "
            "un code qu'elle ne sait pas nommer."
        )
    return digest_of({
        "kind": "execution",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "engine_name": engine_name,
        "engine_version": engine_version,
        "build_sha": build_sha,
        "request": request,
        # `{}` PLUTOT QUE `null` QUAND L'INSTANTANE MANQUE. Un calcul refuse
        # n'en produit pas, et deux refus de meme requete sur le meme build
        # doivent porter la meme identite: laisser passer `None` la ferait
        # dependre de la representation du pilote.
        "ndp_snapshot": ndp_snapshot if ndp_snapshot is not None else {},
    })
