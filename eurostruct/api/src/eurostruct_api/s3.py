"""Un magasin objet S3-compatible, signé à la main, sans dépendance nouvelle.

POURQUOI PAS UN CLIENT TOUT FAIT
---------------------------------
``boto3`` pèse une trentaine de mégaoctets, tire ``botocore`` et sa base de
données de services, et apporte une couche de configuration — profils,
``~/.aws/credentials``, métadonnées d'instance — dont chaque entrée est une
façon supplémentaire pour ce service de trouver des identifiants **que
personne ne lui a déclarés**. Ce dépôt configure par l'environnement, et
refuse quand rien n'est déclaré ; un client qui va chercher ailleurs
contredirait cette règle en silence.

Ce qui est réellement nécessaire ici tient en quatre requêtes — ``PUT``,
``GET``, ``HEAD``, et la création de compartiment pour les harnais — et en une
signature dont l'algorithme est publié et **testable hors ligne** sur les
vecteurs d'AWS. C'est ce que fait ce module.

CE QU'IL PRÉTEND, ET CE QU'IL NE PRÉTEND PAS
----------------------------------------------
Il parle **le protocole S3 avec signature Version 4**. Il est éprouvé contre
un MinIO réel, localement et en intégration continue. Cela établit le
protocole, et **rien d'autre** :

* aucune preuve sur AWS S3 lui-même — le compte n'existe pas ici ;
* aucune preuve sur Supabase Storage — ``SUPABASE_UNVERIFIED`` reste vrai, et
  le nom « Supabase » n'apparaît nulle part dans ce module.

AUCUN SECRET NE SORT D'ICI
---------------------------
Les identifiants ne figurent dans aucun message, aucune exception, aucun
journal. Les messages nomment **la variable d'environnement** qui manque,
jamais sa valeur. L'en-tête ``Authorization`` est construit au moment de
l'envoi et n'est jamais conservé.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Final
from xml.etree import ElementTree

__all__ = [
    "ALGORITHME",
    "ClientS3",
    "ReglagesS3",
    "ReponseS3",
    "S3Refuse",
    "canoniser_requete",
    "chaine_a_signer",
    "cle_de_signature",
]

ALGORITHME: Final[str] = "AWS4-HMAC-SHA256"
SERVICE: Final[str] = "s3"

#: Le sha256 de la charge VIDE, qu'une requête sans corps doit annoncer.
#: Le calculer à chaque appel serait exact et inutile ; l'écrire en clair rend
#: la valeur reconnaissable dans un journal de mise au point.
SHA256_VIDE: Final[str] = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)


class S3Refuse(RuntimeError):
    """Le magasin objet a refusé, ou n'a pas répondu.

    ELLE NE PORTE JAMAIS D'IDENTIFIANT. Le code HTTP, la clé visée et le code
    d'erreur du fournisseur suffisent au diagnostic ; la signature et le secret
    qui l'a produite n'y ont rien à faire.
    """

    def __init__(self, message: str, *, statut: int | None = None,
                 code: str | None = None) -> None:
        super().__init__(message)
        self.statut = statut
        self.code = code


@dataclass(frozen=True)
class ReponseS3:
    """Ce qu'une requête rend : le statut, les en-têtes, et un flux."""

    statut: int
    entetes: dict[str, str]
    flux: Any

    def lire_tout(self) -> bytes:
        try:
            return self.flux.read()
        finally:
            self.flux.close()


@dataclass(frozen=True)
class ReglagesS3:
    """Tout ce qu'il faut pour joindre un compartiment, et rien de plus.

    ``endpoint`` EST OBLIGATOIRE, MÊME POUR AWS. Le déduire de la région
    ferait deviner une adresse : sur un fournisseur compatible, la déduction
    est fausse ; sur AWS, elle est juste mais non déclarée. On préfère une
    ligne de configuration à une devinette.

    ``chemin_style`` DÉFAUT VRAI. Les fournisseurs compatibles — MinIO en tête
    — servent ``endpoint/bucket/cle`` ; AWS accepte les deux et pousse le style
    virtuel, qui exige un certificat joker et une résolution DNS par
    compartiment. Le style chemin marche partout ; le style virtuel se demande.
    """

    endpoint: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    prefixe: str = ""
    chemin_style: bool = True
    verifier_tls: bool = True
    ca_bundle: str | None = None
    #: Chiffrement côté serveur, quand le fournisseur le propose: ``AES256``
    #: ou ``aws:kms``. Absent, aucun en-tête n'est envoyé — annoncer un
    #: chiffrement qu'on n'a pas demandé serait pire que de ne rien dire.
    chiffrement: str | None = None
    kms_key_id: str | None = None
    delai_s: float = 30.0


def cle_de_signature(secret: str, date: str, region: str,
                     service: str = SERVICE) -> bytes:
    """La clé dérivée de SigV4 : quatre HMAC en chaîne.

    Chaque étage restreint la clé — à la date, puis à la région, puis au
    service — pour qu'une signature interceptée ne serve ni un autre jour, ni
    ailleurs, ni pour autre chose.
    """
    def _h(cle: bytes, message: str) -> bytes:
        return hmac.new(cle, message.encode("utf-8"), hashlib.sha256).digest()

    return _h(_h(_h(_h(("AWS4" + secret).encode("utf-8"), date), region),
                 service), "aws4_request")


def _encoder_segment(segment: str) -> str:
    """Encode un segment de chemin comme S3 l'attend pour la canonisation."""
    return urllib.parse.quote(segment, safe="-_.~")


def canoniser_requete(methode: str, chemin: str, requete: dict[str, str],
                      entetes: dict[str, str], empreinte_charge: str) -> str:
    """La requête canonique, dans l'ordre exact que la signature suppose.

    LES DÉTAILS SONT LA SPÉCIFICATION, PAS DU STYLE : chemin encodé segment par
    segment, paramètres triés et encodés, en-têtes en minuscules triés, valeurs
    dont les blancs de bord sont retirés, et une ligne vide avant la liste des
    en-têtes signés. Une virgule de travers rend une signature invalide, et le
    fournisseur répond alors « SignatureDoesNotMatch » sans dire où.
    """
    chemin_canon = "/" + "/".join(
        _encoder_segment(s) for s in chemin.lstrip("/").split("/")
    ) if chemin.strip("/") else "/"

    requete_canon = "&".join(
        f"{urllib.parse.quote(c, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
        for c, v in sorted(requete.items())
    )

    minuscules = {c.lower(): " ".join(str(v).split())
                  for c, v in entetes.items()}
    entetes_canon = "".join(f"{c}:{minuscules[c]}\n"
                            for c in sorted(minuscules))
    signes = ";".join(sorted(minuscules))

    return (f"{methode}\n{chemin_canon}\n{requete_canon}\n"
            f"{entetes_canon}\n{signes}\n{empreinte_charge}")


def chaine_a_signer(horodatage: str, portee: str, canonique: str) -> str:
    return "\n".join([
        ALGORITHME, horodatage, portee,
        hashlib.sha256(canonique.encode("utf-8")).hexdigest(),
    ])


class ClientS3:
    """Quatre requêtes, et la signature qui les autorise."""

    def __init__(self, reglages: ReglagesS3) -> None:
        self.r = reglages
        self._contexte = self._construire_contexte_tls()

    # ------------------------------------------------------------------ TLS
    def _construire_contexte_tls(self) -> ssl.SSLContext | None:
        """Le contexte TLS, ou ``None`` pour un endpoint en clair.

        ``verifier_tls=False`` EXISTE ET SE DÉCLARE. Un magasin de recette
        derrière un certificat auto-signé est un cas réel ; le silence sur ce
        point pousserait à désactiver la vérification ailleurs, plus
        largement. Ce qui n'existe pas, c'est un repli automatique : la valeur
        par défaut vérifie, et ne se désactive que sur demande explicite.
        """
        if not self.r.endpoint.lower().startswith("https://"):
            return None
        contexte = ssl.create_default_context(cafile=self.r.ca_bundle)
        if not self.r.verifier_tls:
            contexte.check_hostname = False
            contexte.verify_mode = ssl.CERT_NONE
        return contexte

    # ---------------------------------------------------------------- clés
    def cle_objet(self, chemin: str) -> str:
        """La clé d'objet complète : le préfixe déclaré, puis le chemin."""
        prefixe = self.r.prefixe.strip("/")
        chemin = chemin.strip("/")
        return f"{prefixe}/{chemin}" if prefixe else chemin

    def _url_et_chemin(self, cle: str) -> tuple[str, str, str]:
        """(url, hôte, chemin canonique) pour une clé — ou pour le bucket."""
        base = self.r.endpoint.rstrip("/")
        analyse = urllib.parse.urlsplit(base)
        hote = analyse.netloc
        if self.r.chemin_style:
            chemin = f"/{self.r.bucket}" + (f"/{cle}" if cle else "")
        else:
            hote = f"{self.r.bucket}.{hote}"
            chemin = f"/{cle}" if cle else "/"
            base = urllib.parse.urlunsplit(
                (analyse.scheme, hote, "", "", ""))
        segments = "/".join(urllib.parse.quote(s, safe="-_.~")
                            for s in chemin.lstrip("/").split("/")) \
            if chemin.strip("/") else ""
        url = f"{base.rstrip('/')}/{segments}" if segments else base
        return url, hote, chemin

    # ------------------------------------------------------------- requête
    def _envoyer(self, methode: str, cle: str, *, corps: bytes | None = None,
                 entetes_sup: dict[str, str] | None = None,
                 flux: bool = False,
                 requete: dict[str, str] | None = None) -> ReponseS3:
        # LES PARAMETRES DE REQUETE SONT SIGNES, PAS SEULEMENT ENVOYES. Ils
        # entrent dans la requete canonique; les oublier de la signature donne
        # « SignatureDoesNotMatch » sans indiquer lequel manque.
        requete = requete or {}
        url, hote, chemin = self._url_et_chemin(cle)
        if requete:
            url = f"{url}?" + "&".join(
                f"{urllib.parse.quote(c, safe='-_.~')}="
                f"{urllib.parse.quote(v, safe='-_.~')}"
                for c, v in sorted(requete.items()))
        maintenant = _dt.datetime.now(_dt.UTC)
        horodatage = maintenant.strftime("%Y%m%dT%H%M%SZ")
        date = maintenant.strftime("%Y%m%d")
        portee = f"{date}/{self.r.region}/{SERVICE}/aws4_request"

        charge = corps if corps is not None else b""
        empreinte_charge = (hashlib.sha256(charge).hexdigest()
                            if corps is not None else SHA256_VIDE)

        entetes: dict[str, str] = {
            "host": hote,
            "x-amz-content-sha256": empreinte_charge,
            "x-amz-date": horodatage,
        }
        if corps is not None:
            entetes["content-length"] = str(len(charge))
        entetes.update({c.lower(): v for c, v in (entetes_sup or {}).items()})

        canonique = canoniser_requete(methode, chemin, requete, entetes,
                                      empreinte_charge)
        signature = hmac.new(
            cle_de_signature(self.r.secret_access_key, date, self.r.region),
            chaine_a_signer(horodatage, portee, canonique).encode("utf-8"),
            hashlib.sha256).hexdigest()
        signes = ";".join(sorted(c.lower() for c in entetes))

        # L'EN-TETE D'AUTORISATION EST CONSTRUIT ICI ET NULLE PART AILLEURS. Il
        # n'est ni conserve, ni journalise, ni rendu par une exception.
        entetes["authorization"] = (
            f"{ALGORITHME} Credential={self.r.access_key_id}/{portee}, "
            f"SignedHeaders={signes}, Signature={signature}"
        )

        demande = urllib.request.Request(url, data=corps, method=methode,
                                         headers=entetes)
        try:
            reponse = urllib.request.urlopen(
                demande, timeout=self.r.delai_s, context=self._contexte)
        except urllib.error.HTTPError as erreur:
            detail = ""
            try:
                detail = (erreur.read() or b"").decode("utf-8", "replace")[:400]
            except Exception:  # noqa: BLE001 — le diagnostic ne doit pas lever
                detail = ""
            code = _code_derreur(detail)
            raise S3Refuse(
                f"le magasin objet a refuse « {methode} {cle or '(bucket)'} »: "
                f"HTTP {erreur.code}"
                + (f", code « {code} »" if code else ""),
                statut=erreur.code, code=code) from erreur
        except urllib.error.URLError as erreur:
            # LA CAUSE EST RENDUE, PAS L'URL COMPLETE: un endpoint peut porter
            # un identifiant dans son nom d'hote sur certains fournisseurs.
            raise S3Refuse(
                f"le magasin objet est injoignable ({erreur.reason})."
            ) from erreur
        except TimeoutError as erreur:
            raise S3Refuse(
                f"le magasin objet n'a pas repondu en {self.r.delai_s} s."
            ) from erreur

        entetes_reponse = {c.lower(): v for c, v in reponse.headers.items()}
        if flux:
            return ReponseS3(reponse.status, entetes_reponse, reponse)
        try:
            return ReponseS3(reponse.status, entetes_reponse,
                             _FluxMemoire(reponse.read()))
        finally:
            reponse.close()

    # ------------------------------------------------------------ opérations
    def deposer(self, chemin: str, octets: bytes,
                media_type: str = "application/octet-stream") -> None:
        entetes = {"content-type": media_type}
        if self.r.chiffrement:
            entetes["x-amz-server-side-encryption"] = self.r.chiffrement
            if self.r.kms_key_id:
                entetes["x-amz-server-side-encryption-aws-kms-key-id"] = \
                    self.r.kms_key_id
        self._envoyer("PUT", self.cle_objet(chemin), corps=octets,
                      entetes_sup=entetes)

    def lire(self, chemin: str) -> bytes:
        return self._envoyer("GET", self.cle_objet(chemin)).lire_tout()

    def lire_en_flux(self, chemin: str, taille_bloc: int = 65536
                     ) -> Iterator[bytes]:
        """Rend les octets par blocs, sans jamais tenir l'objet en mémoire."""
        reponse = self._envoyer("GET", self.cle_objet(chemin), flux=True)
        try:
            while True:
                bloc = reponse.flux.read(taille_bloc)
                if not bloc:
                    return
                yield bloc
        finally:
            reponse.flux.close()

    def taille(self, chemin: str) -> int | None:
        """La taille de l'objet, ou ``None`` s'il n'existe pas.

        UN ABSENT N'EST PAS UNE PANNE. C'est le cas nominal d'un premier dépôt,
        et le distinguer d'un refus de droit est exactement ce qui permet de
        dire « la clé est libre » plutôt que « le magasin a refusé ».
        """
        try:
            reponse = self._envoyer("HEAD", self.cle_objet(chemin))
        except S3Refuse as refus:
            if refus.statut == 404:
                return None
            raise
        return int(reponse.entetes.get("content-length", "0"))

    def enumerer(self, prefixe: str = "") -> list[tuple[str, int]]:
        """Les objets sous ``prefixe`` : ``(chemin, taille)``, paginés.

        POURQUOI CETTE METHODE EXISTE, ET POURQUOI ELLE ARRIVE SI TARD. Le
        produit n'en a jamais eu besoin : il connaît le chemin d'un livrable
        avant de le lire, puisque ce chemin est dérivé du contenu. Seul le
        **rapprochement** a besoin de la question inverse — « qu'y a-t-il dans
        le compartiment que la base ne nomme pas ? » — et c'est exactement la
        question à laquelle on ne pouvait pas répondre.

        LE CHEMIN RENDU EST RELATIF AU PREFIXE DECLARE, pas la clé brute. Un
        appelant qui comparerait des clés brutes à des ``storage_path``
        déclarerait orphelin tout le compartiment dès qu'un préfixe est
        configuré.

        ``ListObjectsV2`` PAGINE, ET ON SUIT LA PAGINATION. Un magasin de
        production dépasse mille objets ; s'arrêter à la première page
        présenterait les suivants comme absents — le pire des verdicts, parce
        qu'il accuse un magasin sain.
        """
        base = self.r.prefixe.strip("/")
        complet = f"{base}/{prefixe.lstrip('/')}" if base else prefixe.lstrip("/")

        objets: list[tuple[str, int]] = []
        jeton_suite: str | None = None
        while True:
            requete = {"list-type": "2", "max-keys": "1000"}
            if complet:
                requete["prefix"] = complet
            if jeton_suite:
                requete["continuation-token"] = jeton_suite

            reponse = self._envoyer("GET", "", requete=requete)
            racine = ElementTree.fromstring(reponse.lire_tout())
            espace = ""
            if racine.tag.startswith("{"):
                espace = racine.tag[:racine.tag.index("}") + 1]

            for contenu in racine.findall(f"{espace}Contents"):
                cle = (contenu.findtext(f"{espace}Key") or "")
                taille = int(contenu.findtext(f"{espace}Size") or "0")
                if base:
                    if not cle.startswith(f"{base}/"):
                        continue
                    cle = cle[len(base) + 1:]
                if cle:
                    objets.append((cle, taille))

            tronquee = (racine.findtext(f"{espace}IsTruncated") or "").lower()
            jeton_suite = racine.findtext(f"{espace}NextContinuationToken")
            if tronquee != "true" or not jeton_suite:
                break
        return objets

    def creer_compartiment(self) -> None:
        """Crée le compartiment s'il n'existe pas. Réservé aux harnais.

        LE PRODUIT NE L'APPELLE PAS. Un service qui créerait son propre
        compartiment au démarrage masquerait une erreur de configuration —
        écrire dans un compartiment nouvellement créé au lieu de refuser parce
        que celui qu'on a nommé n'existe pas.
        """
        try:
            self._envoyer("PUT", "")
        except S3Refuse as refus:
            if refus.code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                return
            raise


class _FluxMemoire:
    """Un flux minimal sur des octets déjà lus."""

    __slots__ = ("_i", "_o")

    def __init__(self, octets: bytes) -> None:
        self._o = octets
        self._i = 0

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            morceau, self._i = self._o[self._i:], len(self._o)
            return morceau
        morceau = self._o[self._i:self._i + n]
        self._i += len(morceau)
        return morceau

    def close(self) -> None:
        return None


def _code_derreur(corps: str) -> str | None:
    """Le ``<Code>`` d'une erreur S3, sans analyseur XML.

    UNE EXTRACTION MINIMALE SUFFIT ET NE PEUT PAS LEVER. Monter un analyseur
    XML pour lire une balise ferait dépendre le diagnostic de la bonne formation
    d'un document que le fournisseur produit au moment où quelque chose va mal.
    """
    debut = corps.find("<Code>")
    if debut < 0:
        return None
    fin = corps.find("</Code>", debut)
    return corps[debut + 6:fin] if fin > debut else None
