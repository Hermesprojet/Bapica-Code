"""Où vivent les octets d'un livrable, et comment on prouve qu'ils y sont.

LE PROBLÈME QUE CE MODULE RÉSOUT
---------------------------------
``deliverables.storage_path`` est une colonne ``not null`` depuis la première
migration, et personne n'y avait jamais écrit d'octets. Une ligne pouvait
nommer un chemin vide, le chemin d'un autre fichier, ou un chemin qui n'a
jamais existé — la table était exactement aussi convaincante dans les trois
cas. Un livrable dont on ne peut pas produire les octets n'est pas un livrable.

CE QU'UNE ABSTRACTION MINIMALE DOIT GARANTIR
----------------------------------------------
Deux gestes, et un invariant qui les relie :

``deposer`` puis ``lire`` rendent les **mêmes octets**.

Tout le reste — quel magasin, quel fournisseur, quelle région — est un détail
de déploiement. Ce qui n'est pas un détail, c'est que l'appelant **relise ce
qu'il vient d'écrire avant d'enregistrer quoi que ce soit**. Sans cette
relecture, on enregistre une promesse ; avec elle, on enregistre un fait.

CE MODULE NE SIMULE PAS SUPABASE
----------------------------------
Il n'y a pas d'adaptateur « Supabase » ici, pas même en attendant. Un
adaptateur qui écrirait dans ``/tmp`` sous le nom de Supabase ferait passer
pour éprouvé un chemin qui n'a jamais tourné, et c'est exactement la
compatibilité que le dépôt refuse d'affirmer (``SUPABASE_UNVERIFIED``). Quand
un magasin objet réel sera disponible, il implémentera ce protocole et sera
éprouvé pour lui-même.

EN PRODUCTION, L'ABSENCE DE MAGASIN EST UN REFUS
--------------------------------------------------
``stockage_configure()`` lève quand rien n'est configuré. Elle ne retombe
**pas** sur un répertoire temporaire : un conteneur redémarré perdrait les
octets, et les lignes en base continueraient de promettre des documents
introuvables. Un refus explicite au moment de créer le livrable est infiniment
préférable à un fichier manquant découvert dix ans plus tard.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Final, Protocol

__all__ = [
    "VARIABLE_RACINE",
    "ObjetIntrouvable",
    "OctetsAlteres",
    "Stockage",
    "StockageIndisponible",
    "StockageLocal",
    "chemin_de_livrable",
    "empreinte",
    "stockage_configure",
]

#: LA VARIABLE, ET UNE SEULE. Deux noms acceptés deviendraient deux façons de
#: configurer le même fait, dont une oubliée quelque part.
VARIABLE_RACINE: Final[str] = "EUROSTRUCT_STORAGE_DIR"

#: Un objet plus gros que cela n'est pas une note de calcul: c'est une erreur
#: de programmation ou une tentative de saturer le disque. La borne est haute
#: — une note très fournie tient dans quelques centaines de kilo-octets.
TAILLE_MAX: Final[int] = 32 * 1024 * 1024


class StockageIndisponible(RuntimeError):
    """Aucun magasin d'objets n'est configuré, ou il n'est pas utilisable.

    Distincte d'une erreur de domaine : elle ne dit pas que la demande est
    refusée, elle dit que le service ne peut pas la tenir. C'est un 503, pas un
    422.
    """


class ObjetIntrouvable(RuntimeError):
    """Le chemin enregistré ne désigne aucun octet."""


class OctetsAlteres(RuntimeError):
    """Les octets relus ne portent pas l'empreinte enregistrée.

    C'est le seul défaut qu'un magasin ne peut pas réparer lui-même, et le seul
    qu'il ne faut jamais servir : un document altéré qui s'affiche est pire
    qu'un document absent, parce qu'on le lit.
    """


class Stockage(Protocol):
    """Deux gestes, et l'invariant qui les relie."""

    #: Le nom enregistré dans ``deliverables.storage_backend``. Une ligne qui
    #: ne dit pas quel magasin détient ses octets ne permet pas de les
    #: retrouver.
    nom: str

    def deposer(self, chemin: str, octets: bytes) -> None: ...

    def lire(self, chemin: str) -> bytes: ...


def empreinte(octets: bytes) -> str:
    """Le sha256 hexadécimal minuscule des octets, tel qu'il part en base."""
    return hashlib.sha256(octets).hexdigest()


def chemin_de_livrable(*, org_id: str, project_id: str, sha256: str,
                       extension: str) -> str:
    """Le chemin d'un livrable, **dérivé de son contenu**.

    L'ADRESSAGE PAR CONTENU N'EST PAS UNE ÉLÉGANCE. La contrainte SQL
    ``storage_path_derives_from_sha`` exige que le chemin contienne
    l'empreinte : aucune ligne ne peut désigner un emplacement sans rapport
    avec le contenu qu'elle annonce. Deux dépôts des mêmes octets écrivent au
    même endroit, ce qui rend le second dépôt idempotent au lieu d'être une
    seconde copie qui pourrait diverger.

    LE CLOISONNEMENT EST DANS LE CHEMIN AUSSI. ``org/projet/`` en préfixe :
    une erreur de configuration qui exposerait le magasin exposerait au moins
    une arborescence où les organisations sont séparées, plutôt qu'un seul
    répertoire plat.

    AUCUN SEGMENT NE VIENT D'UN HUMAIN. Identifiants et empreinte sont
    contrôlés ci-dessous ; le nom de fichier choisi par l'utilisateur ne
    traverse jamais jusqu'ici. Un nom de projet contenant ``../`` n'a donc
    aucun chemin pour sortir de la racine.
    """
    for nom, valeur in (("org_id", org_id), ("project_id", project_id)):
        if not _identifiant_sur(valeur):
            raise StockageIndisponible(
                f"{nom} « {valeur} » n'a pas la forme d'un identifiant: "
                "aucun chemin de stockage n'est construit."
            )
    if not _empreinte_sure(sha256):
        raise StockageIndisponible(
            f"l'empreinte « {sha256} » n'est pas un sha256 hexadecimal "
            "minuscule: aucun chemin de stockage n'est construit."
        )
    suffixe = extension.lstrip(".")
    if not suffixe.isalnum():
        raise StockageIndisponible(
            f"l'extension « {extension} » n'est pas alphanumerique."
        )
    return f"{org_id}/{project_id}/{sha256}.{suffixe}"


def _identifiant_sur(valeur: str) -> bool:
    return bool(valeur) and all(c.isalnum() or c == "-" for c in valeur)


def _empreinte_sure(valeur: str) -> bool:
    return (len(valeur) == 64
            and all(c in "0123456789abcdef" for c in valeur))


class StockageLocal:
    """Le système de fichiers, sous une racine déclarée.

    IL EST RÉEL, PAS SIMULÉ. C'est le magasin qu'un déploiement mono-machine
    ou un poste de développement utilise vraiment, et c'est celui que les
    tests exercent. Sa limite est connue et nommée : il ne survit pas à un
    conteneur éphémère et ne se réplique pas. Ce n'est pas une raison de le
    remplacer par un simulacre ; c'est une raison de le déclarer.
    """

    nom = "local"

    def __init__(self, racine: Path | str) -> None:
        self.racine = Path(racine).resolve()

    def _absolu(self, chemin: str) -> Path:
        """Résout un chemin relatif SOUS la racine, ou refuse.

        LE CONTRÔLE EST FAIT MÊME SUR UN CHEMIN VENU DE NOTRE PROPRE BASE.
        ``storage_path`` est écrit par nous, donc sûr — jusqu'au jour où une
        migration, un import ou une restauration y met autre chose. Un
        ``../../etc/passwd`` servi par une route de téléchargement est le
        défaut le plus banal qui soit, et il ne coûte rien de le fermer.
        """
        if not chemin or chemin.startswith("/") or "\\" in chemin:
            raise ObjetIntrouvable(
                f"chemin de stockage invalide: « {chemin} »"
            )
        cible = (self.racine / chemin).resolve()
        if cible != self.racine and self.racine not in cible.parents:
            raise ObjetIntrouvable(
                "le chemin de stockage sort de la racine declaree: "
                f"« {chemin} »"
            )
        return cible

    def deposer(self, chemin: str, octets: bytes) -> None:
        """Écrit les octets, **atomiquement**.

        L'ÉCRITURE PASSE PAR UN FICHIER TEMPORAIRE PUIS UN ``rename``. Une
        écriture directe interrompue — conteneur tué, disque plein — laisserait
        un fichier tronqué à l'emplacement définitif, portant le nom d'une
        empreinte qu'il ne vérifie plus. ``rename`` sur le même système de
        fichiers est atomique : le fichier est absent, ou complet.
        """
        if len(octets) > TAILLE_MAX:
            raise StockageIndisponible(
                f"objet de {len(octets)} octets: au-dela de la borne de "
                f"{TAILLE_MAX} octets."
            )
        cible = self._absolu(chemin)
        cible.parent.mkdir(parents=True, exist_ok=True)
        provisoire = cible.with_name(f".{cible.name}.{os.getpid()}.partiel")
        try:
            provisoire.write_bytes(octets)
            provisoire.replace(cible)
        except OSError as cause:
            provisoire.unlink(missing_ok=True)
            raise StockageIndisponible(
                f"depot impossible sous « {self.racine} »: {cause.strerror}"
            ) from cause

    def lire(self, chemin: str) -> bytes:
        cible = self._absolu(chemin)
        try:
            return cible.read_bytes()
        except FileNotFoundError as cause:
            raise ObjetIntrouvable(
                f"aucun octet a l'emplacement « {chemin} »"
            ) from cause
        except OSError as cause:
            raise StockageIndisponible(
                f"lecture impossible sous « {self.racine} »: {cause.strerror}"
            ) from cause


def stockage_configure() -> Stockage:
    """Le magasin déclaré, ou un refus qui dit comment le déclarer.

    ELLE NE RETOMBE SUR RIEN. Un répertoire temporaire choisi d'office
    laisserait le produit créer des livrables qui disparaissent au prochain
    redémarrage, en laissant derrière eux des lignes qui promettent des
    documents introuvables. Le refus est la seule réponse qui ne ment pas.

    :raises StockageIndisponible: rien n'est déclaré, ou la racine déclarée
        n'est pas un répertoire utilisable en écriture.
    """
    brut = (os.environ.get(VARIABLE_RACINE) or "").strip()
    if not brut:
        raise StockageIndisponible(
            f"aucun magasin d'objets n'est declare ({VARIABLE_RACINE}). Un "
            "livrable est un fichier: sans magasin, la ligne enregistree "
            "promettrait un document introuvable. Declarer un repertoire "
            "persistant — dev.sh, l'image Docker et la CI le font — ou "
            "brancher un magasin objet."
        )
    racine = Path(brut)
    if not racine.is_dir():
        raise StockageIndisponible(
            f"{VARIABLE_RACINE} designe « {brut} », qui n'est pas un "
            "repertoire existant."
        )
    if not os.access(racine, os.W_OK | os.X_OK):
        raise StockageIndisponible(
            f"{VARIABLE_RACINE} designe « {brut} », sur lequel le service n'a "
            "pas le droit d'ecrire."
        )
    return StockageLocal(racine)
