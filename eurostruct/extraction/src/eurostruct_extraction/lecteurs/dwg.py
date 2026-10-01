"""Le DWG : conservé, identifié, NON LU.

Lire un DWG nativement exige une licence ODA ou RealDWG. Ce produit n'en a
pas, et ne prétend pas en avoir (interdiction 7, tranchée : l'échange se fait
en DXF R2018, lu par ezdxf). Ce module fait donc trois choses, et pas une de
plus :

* il lit la **version** dans l'en-tête de six octets (``AC1032`` → AutoCAD
  2018) — c'est une signature documentée, pas une lecture du dessin ;
* il déclare le document ``non_lu``, avec le motif et le remède ;
* il prévoit le jour où une conversion sous licence sera configurée :
  :class:`ConvertisseurDWG` rend un DXF, qui suit alors le chemin du DXF, et
  la proposition dit quelle conversion a servi.
"""

from __future__ import annotations

from typing import Protocol

__all__ = ["ConvertisseurDWG", "MOTIF_DWG_NON_LU"]

MOTIF_DWG_NON_LU = (
    "DWG conserve et empreinte, non lu: la lecture native du DWG exige une "
    "licence ODA ou RealDWG, que ce service n'a pas. Exportez le plan en DXF "
    "(R2018 de preference) depuis votre logiciel de DAO et deposez ce DXF: "
    "il sera lu."
)


class ConvertisseurDWG(Protocol):
    """Une conversion DWG → DXF, fournie par un outil sous licence.

    Aucune implémentation n'est livrée. Celle qu'un déploiement brancherait
    doit rendre les octets d'un DXF ; ils sont vérifiés (signature) avant
    d'être lus, et une conversion qui rend autre chose fait échouer
    l'analyse plutôt que de la fausser.
    """

    nom: str

    def convertir(self, octets: bytes) -> bytes: ...
