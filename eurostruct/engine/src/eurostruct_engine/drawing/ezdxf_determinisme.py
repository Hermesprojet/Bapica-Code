"""Rendre l'ordre de la section ``CLASSES`` d'``ezdxf`` deterministe.

LE DEFAUT, MESURE
------------------
Huit rendus du MEME dessin, dans huit processus distincts, donnaient DEUX
fichiers de taille identique (63 993 octets) et de contenu different. Le diff
faisait huit lignes, toutes dans la section ``CLASSES`` : les enregistrements
``LAYOUT`` et ``ACDBPLACEHOLDER`` echangeaient leur place.

LA CAUSE, EXACTEMENT
---------------------
Le document est en R2018. Dans ``ezdxf/sections/classes.py``,
``REQUIRED_CLASSES`` ne porte que deux entrees — ``DXF2000 -> REQ_R2000`` et
``DXF2004 -> REQ_R2004`` — si bien que toute version posterieure retombe sur
``REQ_R2004``, **qui ne cite ni ``LAYOUT`` ni ``ACDBPLACEHOLDER``** (alors que
``REQ_R2000`` cite les deux). Ces deux classes ne sont donc enregistrees que
par la boucle finale de ``add_required_classes`` ::

    dxf_types_in_use = self.doc.entitydb.dxf_types_in_use()
    ...
    for dxftype in dxf_types_in_use:
        self.add_class(dxftype)

et ``EntityDB.dxf_types_in_use`` rend un ``set[str]``. L'ordre d'iteration d'un
ensemble de chaines depend de ``PYTHONHASHSEED``, que CPython tire au hasard a
chaque demarrage.

CE QUE COUTAIT CE DESORDRE
---------------------------
Le chemin de stockage d'un livrable derive de son SHA-256, et la politique du
magasin (``docs/STOCKAGE.md`` §5) interdit toute suppression par le produit. Un
meme dessin se deposait donc sous deux chemins, **definitivement**, et deux
plans identiques portaient deux empreintes : le contraire de ce que
l'adressage par contenu existe pour donner.

POURQUOI CETTE FORME DE CORRECTIF, ET PAS UNE AUTRE
-----------------------------------------------------
``PYTHONHASHSEED`` FIXE AU DEPLOIEMENT N'EST PAS UN CORRECTIF. Il deplace la
garantie hors du code, dans une variable d'environnement qu'un operateur, un
conteneur ou un ordonnanceur peut ne pas poser — et le jour ou elle manque, le
produit redevient non deterministe sans que rien ne le dise.

UN NOUVEL EXPORTEUR DXF N'EN EST PAS UN NON PLUS. Reecrire ce qu'``ezdxf``
fait deja, pour un probleme d'ordre, echangerait un defaut connu contre une
surface entiere a maintenir.

ON ENVELOPPE DONC UNE SEULE METHODE, ET ON NE LA REIMPLEMENTE PAS.
``add_required_classes`` est appelee telle quelle ; on remet ensuite le
dictionnaire ``self.classes`` dans un ordre canonique. Le correctif ne depend
donc PAS de la facon dont ``ezdxf`` decide d'ajouter ses classes — il ne
depend que du fait que l'export suit l'ordre de ce dictionnaire, et c'est
exactement ce que le controle de signature verifie.

CE QUE CELA NE CHANGE PAS
--------------------------
Ni la geometrie, ni le cartouche, ni le contrat du livrable. La section
``CLASSES`` du format DXF n'impose aucun ordre : chaque enregistrement est
autonome et rien ne le reference par position. Un logiciel de CAO lit les deux
ordres de la meme facon — ce qu'``ezdxf`` lui-meme confirme, puisqu'il les
relit dans un dictionnaire.

SUR LA CONCURRENCE
-------------------
L'enveloppe ne touche que ``self``. Chaque ``Drawing`` porte sa propre
``ClassesSection`` : deux rendus simultanes ne partagent aucun etat, et aucun
drapeau global n'est pose puis retire. L'installation elle-meme est faite une
fois, au chargement du module, sous verrou et de facon idempotente.

VOIR AUSSI ``docs/TICKET_DXF_DETERMINISME.md``.
"""

from __future__ import annotations

import inspect
import io
import threading
from collections import OrderedDict
from typing import Any

import ezdxf
from ezdxf.lldxf.const import DXF2000
from ezdxf.lldxf.tagwriter import TagWriter
from ezdxf.sections.classes import ClassesSection

__all__ = [
    "VERSIONS_EPROUVEES",
    "EzdxfIncompatible",
    "appliquer",
    "verifier_signature",
]

#: Les versions d'``ezdxf`` sur lesquelles ce correctif a ete EPROUVE.
#:
#: Elle sert au MESSAGE d'un refus, pas a le declencher : refuser sur le seul
#: numero ferait echouer le produit a la premiere montee de version corrective,
#: alors que la structure enveloppee n'a pas bouge. C'est la signature qui
#: decide, et elle est verifiee ci-dessous.
VERSIONS_EPROUVEES: tuple[str, ...] = ("1.4.4",)

#: Le marqueur d'installation. Il porte le nom du module pour qu'un lecteur qui
#: le trouve sur la classe sache d'ou il vient.
_MARQUEUR = "_eurostruct_classes_deterministes"

_VERROU = threading.Lock()


class EzdxfIncompatible(RuntimeError):  # noqa: N818 — voir ci-dessous
    """``ezdxf`` n'a plus la forme que ce correctif a ete eprouve a corriger.

    LE NOM NE PORTE PAS « Error », ET C'EST DELIBERE. Le depot nomme ses refus
    par ce qu'ils CONSTATENT — ``ReinforcementNotVerified``,
    ``NationalAnnexIncomplete``, ``CaractereNonRepresentable`` — et non par le
    fait qu'ils sont des exceptions, que la clause ``except`` dit deja.

    ON LEVE PLUTOT QUE DE CONTINUER. Appliquer une enveloppe a une methode qui
    a change de role produirait un fichier dont personne ne sait plus ce qu'il
    garantit — et le defaut d'origine, lui, est silencieux : il ne se voit
    qu'en comparant des empreintes de deux executions.
    """


def _ordonner(classes: Any) -> OrderedDict:
    """L'ordre canonique : par cle ``(name, cpp_class_name)``.

    LES DEUX MEMBRES DE LA CLE SERVENT. ``ezdxf`` documente que plusieurs
    classes peuvent porter le meme ``name`` avec des ``cpp_class_name``
    differents ; trier sur le seul nom laisserait leur ordre relatif indecis.
    """
    return OrderedDict(sorted(classes.items()))


def verifier_signature(classes_section: Any) -> None:
    """Refuse si ``ezdxf`` n'a plus la forme attendue.

    QUATRE FAITS SONT EXIGES, et chacun est ce dont l'enveloppe depend :

    1. ``add_required_classes`` existe et est une fonction ;
    2. sa signature est bien ``(self, dxfversion)`` — un parametre de plus
       signifierait un role different ;
    3. une section fraiche expose ``classes`` sous la forme d'un dictionnaire,
       seul objet qu'on sache reordonner ;
    4. **l'export suit l'ordre de ce dictionnaire.** C'est le fait porteur : le
       reordonner ne servirait a rien si l'export triait de son cote.

    Le quatrieme se verifie en EXPORTANT reellement, pas en lisant le code :
    une lecture de source se laisse tromper par une indirection, une vraie
    sortie non.
    """
    version = getattr(ezdxf, "__version__", "inconnue")
    eprouvees = ", ".join(VERSIONS_EPROUVEES)

    def refuser(quoi: str) -> None:
        raise EzdxfIncompatible(
            f"ezdxf {version} n'a pas la forme que le correctif de determinisme "
            f"a ete eprouve a corriger (versions eprouvees : {eprouvees}). "
            f"{quoi} Le correctif n'est PAS applique: un DXF produit "
            "maintenant pourrait porter deux empreintes pour un meme dessin, "
            "et se deposer deux fois dans un magasin qui ne supprime jamais. "
            "Voir docs/TICKET_DXF_DETERMINISME.md."
        )

    methode = getattr(classes_section, "add_required_classes", None)
    if methode is None or not inspect.isfunction(methode):
        refuser("`ClassesSection.add_required_classes` est absente ou n'est "
                "plus une fonction.")

    parametres = list(inspect.signature(methode).parameters)
    if parametres != ["self", "dxfversion"]:
        refuser("`ClassesSection.add_required_classes` prend desormais "
                f"{parametres!r} et non ['self', 'dxfversion'].")

    try:
        temoin = classes_section()
    except Exception as cause:  # pragma: no cover - depend d'ezdxf
        refuser(f"`ClassesSection()` ne se construit plus seule ({cause}).")
        raise  # pragma: no cover - refuser leve deja

    if not isinstance(getattr(temoin, "classes", None), dict):
        refuser("`ClassesSection.classes` n'est plus un dictionnaire.")

    # --- 4. L'EXPORT SUIT-IL L'ORDRE DU DICTIONNAIRE ? -------------------
    #
    # On peuple la section par le chemin normal, on la reordonne A L'ENVERS de
    # l'ordre canonique, et on exporte : si la sortie suit, l'ordre du
    # dictionnaire commande bien. Un export qui trierait de lui-meme rendrait
    # la sortie canonique malgre l'inversion, et le controle le verrait.
    temoin.add_required_classes(DXF2000)
    if len(temoin.classes) < 2:
        refuser("`add_required_classes` n'ajoute plus aucune classe.")
    a_l_envers = OrderedDict(sorted(temoin.classes.items(), reverse=True))
    temoin.classes = a_l_envers

    tampon = io.StringIO()
    temoin.export_dxf(TagWriter(tampon, dxfversion=DXF2000))
    emis = [ligne for ligne in tampon.getvalue().splitlines()]
    #: Le nom de la classe est la valeur du groupe 1, juste apres « CLASS ».
    noms: list[str] = []
    for i, ligne in enumerate(emis):
        if ligne.strip() == "CLASS" and i + 2 < len(emis) \
                and emis[i + 1].strip() == "1":
            noms.append(emis[i + 2])
    attendus = [cle[0] for cle in a_l_envers]
    if noms != attendus:
        refuser("l'export de la section CLASSES ne suit plus l'ordre du "
                f"dictionnaire (attendu {attendus[:3]}…, obtenu {noms[:3]}…).")


def appliquer() -> None:
    """Installe l'enveloppe, une seule fois, apres verification.

    IDEMPOTENTE ET SOUS VERROU. Deux imports concurrents — deux fils qui
    chargent le module de dessin en meme temps — ne doivent pas envelopper
    deux fois : la seconde enveloppe appellerait la premiere, ce qui reste
    correct mais rend la pile illisible le jour ou l'on diagnostique.
    """
    with _VERROU:
        if getattr(ClassesSection, _MARQUEUR, False):
            return
        verifier_signature(ClassesSection)

        originale = ClassesSection.add_required_classes

        def add_required_classes(self: Any, dxfversion: str) -> None:
            """``ezdxf`` ajoute ses classes, puis on fige leur ordre.

            L'ORIGINALE EST APPELEE TELLE QUELLE. On ne decide pas QUELLES
            classes sont necessaires — c'est le travail d'``ezdxf``, et il
            change avec le format. On decide seulement de l'ordre dans lequel
            elles seront ecrites, qui n'a aucune signification pour le format
            et toute son importance pour l'adressage par contenu.
            """
            originale(self, dxfversion)
            self.classes = _ordonner(self.classes)

        add_required_classes.__wrapped__ = originale  # type: ignore[attr-defined]
        ClassesSection.add_required_classes = add_required_classes  # type: ignore[method-assign]
        setattr(ClassesSection, _MARQUEUR, True)
