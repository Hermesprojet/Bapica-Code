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
from collections.abc import Iterator
from pathlib import Path
from typing import Final, Protocol
from urllib.parse import quote

from .s3 import ClientS3, ReglagesS3, S3Refuse

__all__ = [
    "VARIABLE_BACKEND",
    "VARIABLE_RACINE",
    "ObjetIntrouvable",
    "OctetsAlteres",
    "Stockage",
    "StockageIndisponible",
    "StockageLocal",
    "StockageS3",
    "chemin_de_livrable",
    "disposition_de_fichier",
    "empreinte",
    "stockage_configure",
]

#: LE BACKEND DECLARE. `local` ou `s3`, et rien d'autre — une valeur inconnue
#: est refusee plutot que ramenee au defaut: retomber sur le disque local parce
#: qu'on a mal orthographie « s3 » ecrirait les livrables d'une production sur
#: un disque ephemere, sans un mot.
VARIABLE_BACKEND: Final[str] = "EUROSTRUCT_STORAGE_BACKEND"

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

    def deposer(self, chemin: str, octets: bytes,
                media_type: str = "application/octet-stream") -> None: ...

    def lire(self, chemin: str) -> bytes: ...

    #: LE FLUX EXISTE POUR NE PAS TENIR UN OBJET ENTIER EN MEMOIRE. Une note
    #: de calcul pese quelques dizaines de kilo-octets; un futur dossier de
    #: revue avec ses pieces jointes ne fera pas cette promesse. La route de
    #: telechargement consomme ce flux, et verifie l'empreinte AU FIL de sa
    #: lecture.
    def lire_en_flux(self, chemin: str,
                     taille_bloc: int = 65536) -> Iterator[bytes]: ...


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

    def deposer(self, chemin: str, octets: bytes,
                media_type: str = "application/octet-stream") -> None:
        """Écrit les octets, **atomiquement**.

        ``media_type`` EST ACCEPTE ET IGNORE. Un système de fichiers n'a pas de
        notion de type de contenu ; l'accepter garde la même signature pour les
        deux magasins, et le type reste porté par la ligne en base.

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

    def lire_en_flux(self, chemin: str,
                     taille_bloc: int = 65536) -> Iterator[bytes]:
        cible = self._absolu(chemin)
        try:
            fichier = cible.open("rb")
        except FileNotFoundError as cause:
            raise ObjetIntrouvable(
                f"aucun octet a l'emplacement « {chemin} »"
            ) from cause
        with fichier:
            while True:
                bloc = fichier.read(taille_bloc)
                if not bloc:
                    return
                yield bloc

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


class StockageS3:
    """Un compartiment S3-compatible, prive, adresse par contenu.

    IL EST REEL, ET EPROUVE CONTRE UN MinIO REEL — localement et en
    integration continue. Cela etablit LE PROTOCOLE, et rien d'autre : ni AWS
    S3, ni aucun fournisseur particulier n'a ete joint depuis ce depot. Le mot
    « Supabase » n'apparait pas ici, et ``SUPABASE_UNVERIFIED`` reste vrai.

    LE COMPARTIMENT N'EST PAS CREE PAR LE PRODUIT. Un service qui creerait le
    sien au demarrage masquerait une erreur de configuration : il ecrirait dans
    un compartiment neuf au lieu de refuser parce que celui qu'on a nomme
    n'existe pas — et les livrables partiraient dans le vide, sans un mot.
    """

    nom = "s3"

    def __init__(self, client: ClientS3) -> None:
        self.client = client

    def deposer(self, chemin: str, octets: bytes,
                media_type: str = "application/octet-stream") -> None:
        """Depose, sans jamais ecraser en silence un objet divergent.

        LA CLE DERIVE DU CONTENU: deux depots des memes octets visent la meme
        clé, et le second est sans effet. Un objet DEJA PRESENT sous cette clé
        avec une AUTRE taille est donc une contradiction — la clé ne designe
        plus son contenu — et l'ecraser effacerait la seule trace du probleme.
        """
        if len(octets) > TAILLE_MAX:
            raise StockageIndisponible(
                f"objet de {len(octets)} octets: au-dela de la borne de "
                f"{TAILLE_MAX} octets."
            )
        try:
            existante = self.client.taille(chemin)
        except S3Refuse as cause:
            raise StockageIndisponible(str(cause)) from cause

        if existante is not None:
            if existante == len(octets):
                # MEME CLE, MEME TAILLE: la clé derive du contenu, l'objet est
                # deja la. Le re-deposer serait un aller-retour pour rien; la
                # relecture de l'appelant verifiera l'empreinte de toute facon.
                return
            raise OctetsAlteres(
                f"un objet de {existante} octets occupe deja la cle « {chemin} » "
                f"alors que le document en pese {len(octets)}. La cle derive de "
                "l'empreinte du contenu: cette divergence signale une "
                "corruption ou une collision, et l'ecraser en effacerait la "
                "seule trace."
            )

        try:
            self.client.deposer(chemin, octets, media_type)
        except S3Refuse as cause:
            raise StockageIndisponible(str(cause)) from cause

    def lire(self, chemin: str) -> bytes:
        try:
            return self.client.lire(chemin)
        except S3Refuse as cause:
            if cause.statut == 404:
                raise ObjetIntrouvable(
                    f"aucun octet a l'emplacement « {chemin} »"
                ) from cause
            raise StockageIndisponible(str(cause)) from cause

    def lire_en_flux(self, chemin: str,
                     taille_bloc: int = 65536) -> Iterator[bytes]:
        try:
            yield from self.client.lire_en_flux(chemin, taille_bloc)
        except S3Refuse as cause:
            if cause.statut == 404:
                raise ObjetIntrouvable(
                    f"aucun octet a l'emplacement « {chemin} »"
                ) from cause
            raise StockageIndisponible(str(cause)) from cause


def disposition_de_fichier(nom: str) -> str:
    """L'en-tete ``Content-Disposition``, sur les DEUX formes exigees.

    UN NOM ACCENTUE CASSE LA FORME SIMPLE. ``filename="note-Liège.html"`` n'est
    pas representable en ISO-8859-1 pour tous les caracteres, et un octet non
    ASCII dans un en-tete HTTP est au mieux ignore, au pire tronque. La RFC
    6266 repond par deux parametres:

    * ``filename`` — un repli ASCII, que les clients anciens comprennent;
    * ``filename*`` — la forme RFC 5987, ``UTF-8''`` suivie du nom encode.

    LES GUILLEMETS ET LES RETOURS A LA LIGNE SONT RETIRES DU REPLI, pas
    echappes: un nom de fichier qui contiendrait ``"`` refermerait le parametre
    et permettrait d'en injecter un autre. Le nom exact reste disponible dans
    ``filename*``, ou l'encodage pour-cent le rend inoffensif.
    """
    ascii_sur = "".join(
        c if (c.isalnum() or c in "-_. ") else "-"
        for c in nom.encode("ascii", "replace").decode("ascii")
    ).strip() or "document"
    return (f'attachment; filename="{ascii_sur}"; '
            f"filename*=UTF-8''{quote(nom, safe='')}")


def stockage_configure() -> Stockage:
    """Le magasin déclaré, ou un refus qui dit comment le déclarer.

    ELLE NE RETOMBE SUR RIEN. Un répertoire temporaire choisi d'office
    laisserait le produit créer des livrables qui disparaissent au prochain
    redémarrage, en laissant derrière eux des lignes qui promettent des
    documents introuvables. Le refus est la seule réponse qui ne ment pas.

    :raises StockageIndisponible: rien n'est déclaré, ou la configuration du
        magasin déclaré est incomplète ou inutilisable.
    """
    backend = (os.environ.get(VARIABLE_BACKEND) or "").strip().lower()
    if backend == "s3":
        return _stockage_s3()
    if backend not in ("", "local"):
        # AUCUN REPLI SUR UNE VALEUR INCONNUE. « s4 », « S3 » mal recopie, un
        # espace de trop: ramener cela au disque local ecrirait les livrables
        # d'une production sur un disque ephemere, sans un mot.
        raise StockageIndisponible(
            f"{VARIABLE_BACKEND} vaut « {backend} », qui n'est pas un magasin "
            "connu. Les deux valeurs acceptees sont « local » et « s3 »."
        )
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


#: LES SIX VARIABLES SANS LESQUELLES UN MAGASIN S3 N'EXISTE PAS.
#:
#: Aucune n'a de valeur par defaut, et c'est le point: deviner une region, un
#: compartiment ou un endpoint ferait ecrire des livrables quelque part plutot
#: que de refuser.
_S3_REQUISES: Final[tuple[str, ...]] = (
    "EUROSTRUCT_S3_ENDPOINT",
    "EUROSTRUCT_S3_REGION",
    "EUROSTRUCT_S3_BUCKET",
    "EUROSTRUCT_S3_ACCESS_KEY_ID",
    "EUROSTRUCT_S3_SECRET_ACCESS_KEY",
)


def _booleen(nom: str, defaut: bool) -> bool:
    brut = (os.environ.get(nom) or "").strip().lower()
    if not brut:
        return defaut
    if brut in ("1", "true", "oui", "yes", "on"):
        return True
    if brut in ("0", "false", "non", "no", "off"):
        return False
    raise StockageIndisponible(
        f"{nom} vaut « {brut} », qui n'est ni vrai ni faux. Une valeur "
        "ambigue sur un reglage de securite ne se devine pas."
    )


def _stockage_s3() -> Stockage:
    """Le magasin objet declare, ou un refus qui NOMME ce qui manque.

    LE REFUS NE PORTE AUCUN SECRET. Il nomme les VARIABLES absentes, jamais
    leurs valeurs — un message d'erreur voyage dans des journaux, des tickets
    et parfois des captures d'ecran.

    IL NE RETOMBE PAS SUR LE DISQUE LOCAL. Un magasin objet mal configure en
    production doit refuser: ecrire sur un disque de conteneur ferait
    disparaitre les livrables au prochain redemarrage, en laissant en base des
    lignes qui promettent des documents introuvables.
    """
    manquantes = [v for v in _S3_REQUISES if not (os.environ.get(v) or "").strip()]
    if manquantes:
        raise StockageIndisponible(
            f"{VARIABLE_BACKEND}=s3, mais la configuration est incomplete: "
            + ", ".join(manquantes)
            + ". Aucune de ces valeurs ne se devine, et aucun repli sur le "
              "disque local n'est fait."
        )

    ca = (os.environ.get("EUROSTRUCT_S3_CA_BUNDLE") or "").strip() or None
    if ca and not os.path.isfile(ca):
        raise StockageIndisponible(
            f"EUROSTRUCT_S3_CA_BUNDLE designe « {ca} », qui n'est pas un "
            "fichier lisible."
        )

    reglages = ReglagesS3(
        endpoint=os.environ["EUROSTRUCT_S3_ENDPOINT"].strip(),
        region=os.environ["EUROSTRUCT_S3_REGION"].strip(),
        bucket=os.environ["EUROSTRUCT_S3_BUCKET"].strip(),
        access_key_id=os.environ["EUROSTRUCT_S3_ACCESS_KEY_ID"].strip(),
        secret_access_key=os.environ["EUROSTRUCT_S3_SECRET_ACCESS_KEY"],
        prefixe=(os.environ.get("EUROSTRUCT_S3_PREFIX") or "").strip(),
        chemin_style=_booleen("EUROSTRUCT_S3_PATH_STYLE", True),
        verifier_tls=_booleen("EUROSTRUCT_S3_VERIFY_TLS", True),
        ca_bundle=ca,
        chiffrement=(os.environ.get("EUROSTRUCT_S3_SSE") or "").strip() or None,
        kms_key_id=(os.environ.get("EUROSTRUCT_S3_SSE_KMS_KEY_ID")
                    or "").strip() or None,
    )
    return StockageS3(ClientS3(reglages))
