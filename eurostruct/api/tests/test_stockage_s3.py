"""Les octets d'un livrable vivent dans un magasin objet réel, pas sur un disque.

CE QUE CE MODULE ÉPROUVE, ET CONTRE QUOI
------------------------------------------
Contre un **MinIO réel** — un serveur S3-compatible qui tourne dans un
conteneur, sur un **volume neuf**, joint par le réseau. Rien n'est simulé :
pas de faux client, pas de ``moto``, pas de répertoire déguisé en
compartiment. Ce qui est établi ici est établi sur le **protocole S3**, et sur
lui seul.

CE QUE CELA N'ÉTABLIT PAS, ET IL FAUT LE DIRE
-----------------------------------------------
Ni AWS S3, ni aucun fournisseur nommé n'a été joint depuis ce dépôt. Le mot
« Supabase » n'apparaît nulle part dans le chemin de code exercé, et
``SUPABASE_UNVERIFIED`` reste vrai : aucun staging réel n'a été éprouvé de
bout en bout. Un serveur qui parle le même protocole n'est pas une promesse de
compatibilité avec un service qu'on n'a pas essayé.

POURQUOI DEUX CLASSES, ET POURQUOI ELLES NE TOURNENT PAS ENSEMBLE
-------------------------------------------------------------------
``db/test/stockage_s3.sh`` lance ``TestAvantRedemarrage`` dans un processus, puis
``TestApresRedemarrage`` dans un **autre processus**, après avoir redémarré le
conteneur MinIO. Entre les deux, l'interpréteur est détruit : plus une
connexion, plus un cache, plus un objet en mémoire. C'est la seule forme
honnête de « les mêmes octets reviennent après redémarrage » — un second appel
dans le même processus prouverait surtout que la mémoire fonctionne.

Le passage de témoin se fait par un fichier d'état, dont le chemin arrive par
``EUROSTRUCT_S3_ETAT``. Il ne contient aucun secret : un identifiant de
livrable, un chemin d'objet, une empreinte et une taille.

AUCUN SKIP N'EST UTILISÉ POUR SÉPARER LES DEUX PHASES. Le harnais nomme la
classe qu'il exécute ; un ``skipif`` sur une variable de phase se confondrait
avec un cas qui s'esquive.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

import pytest

from .test_livrables import (  # noqa: F401 — fixtures partagées, décor commun
    ACTEUR_A,
    ACTEUR_B,
    ACTEUR_W,
    DSN,
    DSN_OBS,
    ORG_A,
    _brouillon,
    _entete,
    _observer,
    calcul_strict,
    cle,
    client,
    jeton,
    projet,
)

ETAT = os.environ.get("EUROSTRUCT_S3_ETAT", "")
#: LES OCTETS EXACTS QUE LA ROUTE A SERVIS, écrits pour le harnais. Il les
#: cherchera **verbatim** dans le volume de MinIO, hors de ce processus : c'est
#: ce qui transforme « notre client relit ce qu'il a écrit » en « ces octets-là
#: sont sur ce disque-là ».
DOCUMENT = os.environ.get("EUROSTRUCT_S3_DOCUMENT", "")
#: L'ETAT DU LIVRABLE PDF. Un second fichier plutot qu'une cle de plus dans le
#: premier: la phase de relecture doit pouvoir dire « le PDF n'a pas ete
#: depose » plutot que de lire `None` dans un etat par ailleurs complet.
ETAT_PDF = (ETAT + ".pdf.json") if ETAT else ""
BACKEND = (os.environ.get("EUROSTRUCT_STORAGE_BACKEND") or "").strip().lower()
BUCKET = os.environ.get("EUROSTRUCT_S3_BUCKET", "")
DISQUE_TEMOIN = os.environ.get("EUROSTRUCT_STORAGE_DIR", "")

#: LE DÉCOR DE CE MODULE EST PLUS EXIGEANT QUE CELUI DES AUTRES : il lui faut
#: un magasin objet **joignable**, déclaré comme backend actif. Sans lui, ces
#: cas ne mesureraient rien.
DECOR_PRESENT = bool(DSN and DSN_OBS and ETAT and DOCUMENT and BUCKET and ORG_A
                     and ACTEUR_A and ACTEUR_B and BACKEND == "s3")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/stockage_s3.sh, qui demarre un MinIO reel sur un "
                "volume neuf, cree le compartiment, pose la base deployee et "
                "fournit la configuration par l'environnement."),
    ),
]


# --------------------------------------------------------------------- outils
def _client_brut():
    """Un client S3 **indépendant de celui du produit**.

    IL EXISTE POUR REGARDER LE COMPARTIMENT DE L'EXTÉRIEUR. Vérifier le
    magasin par l'abstraction que le produit utilise ne prouve pas qu'un objet
    existe : cela prouve que l'abstraction est cohérente avec elle-même. Ce
    client-ci est construit à part, depuis l'environnement, et sert de témoin.
    """
    from eurostruct_api.s3 import ClientS3, ReglagesS3

    return ClientS3(ReglagesS3(
        endpoint=os.environ["EUROSTRUCT_S3_ENDPOINT"],
        region=os.environ["EUROSTRUCT_S3_REGION"],
        bucket=os.environ["EUROSTRUCT_S3_BUCKET"],
        access_key_id=os.environ["EUROSTRUCT_S3_ACCESS_KEY_ID"],
        secret_access_key=os.environ["EUROSTRUCT_S3_SECRET_ACCESS_KEY"],
        prefixe=os.environ.get("EUROSTRUCT_S3_PREFIX", ""),
    ))


def _lire_etat() -> dict:
    contenu = Path(ETAT).read_text(encoding="utf-8")
    assert contenu.strip(), (
        f"le fichier d'etat « {ETAT} » est vide: la phase de depot n'a rien "
        "transmis, et la phase de relecture ne sait pas quoi relire.")
    return json.loads(contenu)


def _localisation(deliverable_id: str) -> tuple[str, str, str, int]:
    """``(storage_backend, storage_path, sha256, size_bytes)``, lus en base."""
    lignes = _observer(
        "select storage_backend, storage_path, sha256, size_bytes "
        "  from deliverables where id = %s", (deliverable_id,))
    assert lignes, f"aucune ligne de livrable pour {deliverable_id}"
    return lignes[0]


def _fichiers_sur_disque() -> list[str]:
    """Ce que le disque local porte — il doit rester **vide**."""
    if not DISQUE_TEMOIN:
        return []
    racine = Path(DISQUE_TEMOIN)
    if not racine.is_dir():
        return []
    return sorted(str(p) for p in racine.rglob("*") if p.is_file())


# ===========================================================================
# PHASE 1 — LE DÉPÔT. Un processus, du calcul jusqu'aux octets dans MinIO.
# ===========================================================================
class TestAvantRedemarrage:
    """Ce qui se passe pendant que l'application tourne."""

    def test_le_magasin_configure_est_bien_le_magasin_objet(self):
        """PAS DE REPLI SILENCIEUX. Le backend déclaré est celui qui sert.

        Un produit qui retomberait sur le disque local parce que le magasin
        objet est mal configuré écrirait les livrables d'une production sur un
        disque éphémère, et personne ne l'apprendrait avant le premier
        redémarrage.
        """
        from eurostruct_api.stockage import StockageS3, stockage_configure

        magasin = stockage_configure()
        assert isinstance(magasin, StockageS3), type(magasin)
        assert magasin.nom == "s3"

    def test_le_brouillon_depose_ses_octets_dans_le_compartiment(
            self, client, jeton, projet, calcul_strict):
        """LE PARCOURS RÉEL : une route produit un livrable, MinIO le porte.

        LA VÉRIFICATION EST FAITE PAR UN CLIENT TÉMOIN, pas par le magasin du
        produit : c'est ce qui distingue « l'objet est dans le compartiment »
        de « notre code croit l'y avoir mis ».
        """
        avant = _fichiers_sur_disque()

        livrable = _brouillon(client, jeton, projet, calcul_strict)
        backend, chemin, sha, taille = _localisation(livrable["deliverable_id"])

        assert backend == "s3", (
            f"la ligne enregistre le magasin « {backend} »: elle ne permettrait "
            "pas de retrouver les octets.")
        assert sha in chemin, (
            "le chemin ne derive pas de l'empreinte: "
            f"« {chemin} » ne contient pas {sha}.")

        temoin = _client_brut().lire(chemin)
        assert hashlib.sha256(temoin).hexdigest() == sha
        assert len(temoin) == taille

        # LA ROUTE SERT EXACTEMENT CE QUE LE COMPARTIMENT DETIENT.
        r = client.get(
            f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{livrable['deliverable_id']}/download",
            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 200, r.text
        assert r.content == temoin

        # ET LE DISQUE LOCAL N'A RIEN RECU. Le harnais pointe
        # `EUROSTRUCT_STORAGE_DIR` sur un repertoire vide et jetable: si le
        # produit avait ecrit la, ne serait-ce qu'en copie de securite, un
        # fichier serait apparu.
        assert _fichiers_sur_disque() == avant, (
            "des octets sont apparus sur le disque local alors que le magasin "
            "declare est objet: un repli silencieux est un livrable perdu au "
            "prochain redemarrage.")

        # LES OCTETS SERVIS SONT DEPOSES POUR LE HARNAIS, qui les cherchera
        # VERBATIM dans le volume de MinIO — hors de ce processus, hors du
        # produit, et sans faire confiance a la moindre assertion d'ici.
        Path(DOCUMENT).write_bytes(r.content)
        Path(ETAT).write_text(json.dumps({
            "org_id": projet["organization_id"],
            "project_id": projet["project_id"],
            "deliverable_id": livrable["deliverable_id"],
            "filename": livrable["filename"],
            "storage_path": chemin,
            "sha256": sha,
            "size_bytes": taille,
        }, indent=2), encoding="utf-8")

    def test_un_pdf_traverse_le_magasin_objet_sans_perdre_un_octet(
            self, client, jeton, projet, calcul_strict):
        """UN CORPS BINAIRE N'EST PAS UN CORPS DE TEXTE, ET SigV4 LE SIGNE.

        Tout ce qui precede a depose du HTML. Un PDF est binaire: il porte des
        octets nuls, des sequences qui ne sont valides dans aucun encodage, et
        une table de references croisees dont chaque decalage est compte a
        l'octet. Le moindre reencodage en route — par notre client, par
        `urllib`, par le serveur — le casserait, et il le casserait
        SILENCIEUSEMENT: le fichier ferait toujours la bonne taille.

        L'empreinte le dirait, et c'est pourquoi on la verifie des deux cotes.
        """
        r = client.post(
            f"/v1/projects/{projet['project_id']}/deliverables",
            json={"calculation_id": calcul_strict, "format": "pdf"},
            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 201, r.text
        livrable = r.json()
        assert livrable["media_type"] == "application/pdf"

        backend, chemin, sha, taille = _localisation(livrable["deliverable_id"])
        assert backend == "s3", "le PDF n'est pas parti dans le magasin objet"
        assert chemin.endswith(".pdf")

        # LE TEMOIN LIT LE COMPARTIMENT, PAS LE PRODUIT.
        octets = _client_brut().lire(chemin)
        assert hashlib.sha256(octets).hexdigest() == sha
        assert len(octets) == taille
        assert octets.startswith(b"%PDF-")
        assert octets.rstrip().endswith(b"%%EOF"), (
            "la fin du fichier a ete perdue en route")

        # ET LA TAILLE ANNONCEE PAR LE SERVEUR S'ACCORDE — c'est `HEAD`, donc
        # une seconde source, distincte de la lecture.
        assert _client_brut().taille(chemin) == taille

        Path(ETAT_PDF).write_text(json.dumps({
            "org_id": projet["organization_id"],
            "project_id": projet["project_id"],
            "deliverable_id": livrable["deliverable_id"],
            "filename": livrable["filename"],
            "storage_path": chemin,
            "sha256": sha,
            "size_bytes": taille,
        }, indent=2), encoding="utf-8")

    def test_un_second_brouillon_identique_ne_duplique_pas_l_objet(
            self, client, jeton, projet, calcul_strict):
        """LA CLÉ DÉRIVE DU CONTENU : deux dépôts identiques, un seul objet.

        Ce n'est pas une optimisation. Deux copies d'un même document sous des
        clés différentes finissent par diverger — l'une réécrite, l'autre non
        — et plus rien ne dit laquelle fait foi. L'adressage par contenu rend
        la question impossible à poser.
        """
        premier = _brouillon(client, jeton, projet, calcul_strict)
        second = _brouillon(client, jeton, projet, calcul_strict)
        assert premier["deliverable_id"] != second["deliverable_id"]

        _, chemin_1, sha_1, _ = _localisation(premier["deliverable_id"])
        _, chemin_2, sha_2, _ = _localisation(second["deliverable_id"])
        assert sha_1 == sha_2, (
            "deux brouillons du meme calcul gele ne portent pas les memes "
            "octets: le document n'est pas reproductible.")
        assert chemin_1 == chemin_2
        assert _client_brut().lire(chemin_2) == _client_brut().lire(chemin_1)

    def test_un_objet_divergent_n_est_jamais_ecrase_en_silence(self):
        """LA CLÉ DÉRIVE DU CONTENU : deux contenus sous une clé se contredisent.

        Le second dépôt des **mêmes** octets est sans effet — c'est
        l'idempotence attendue. Le dépôt d'octets **différents** sous la même
        clé signale une corruption ou une collision, et l'écraser effacerait
        la seule trace du problème.
        """
        from eurostruct_api.stockage import OctetsAlteres, stockage_configure

        magasin = stockage_configure()
        octets = b"FICTIF - octets de collision, decor jetable"
        chemin = (f"{uuid.uuid4()}/{uuid.uuid4()}/"
                  f"{hashlib.sha256(octets).hexdigest()}.html")

        magasin.deposer(chemin, octets, "text/html; charset=utf-8")
        assert magasin.lire(chemin) == octets

        # MEMES OCTETS: sans effet, et surtout sans erreur.
        magasin.deposer(chemin, octets, "text/html; charset=utf-8")
        assert magasin.lire(chemin) == octets

        with pytest.raises(OctetsAlteres):
            magasin.deposer(chemin, octets + b" et un ajout", "text/html")
        assert magasin.lire(chemin) == octets, (
            "l'objet d'origine a ete modifie par une tentative refusee.")

    def test_un_objet_absent_du_compartiment_ne_devient_pas_un_document(self):
        """UN CHEMIN QUI NE DÉSIGNE RIEN EST UN REFUS, pas un corps vide."""
        from eurostruct_api.stockage import ObjetIntrouvable, stockage_configure

        magasin = stockage_configure()
        chemin = f"{uuid.uuid4()}/{uuid.uuid4()}/{'0' * 64}.html"
        with pytest.raises(ObjetIntrouvable):
            magasin.lire(chemin)


# ===========================================================================
# PHASE 2 — APRÈS. Nouveau processus, nouveau conteneur MinIO, rien en mémoire.
# ===========================================================================
class TestApresRedemarrage:
    """Ce qui reste quand tout ce qui tournait a été arrêté.

    CETTE CLASSE NE CRÉE RIEN. Elle ne calcule pas, ne produit pas de
    brouillon, ne pose pas de décor : elle ouvre le fichier d'état laissé par
    la phase précédente et exige que le passé soit encore là.
    """

    def test_les_memes_octets_reviennent_avec_la_meme_empreinte(
            self, client, jeton):
        etat = _lire_etat()
        r = client.get(
            f"/v1/projects/{etat['project_id']}/deliverables/"
            f"{etat['deliverable_id']}/download",
            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 200, r.text
        assert hashlib.sha256(r.content).hexdigest() == etat["sha256"], (
            "les octets servis apres redemarrage ne portent plus l'empreinte "
            "enregistree avant.")
        assert len(r.content) == etat["size_bytes"]

    def test_le_compartiment_detient_toujours_l_objet_lui_meme(self):
        """Le témoin regarde MinIO **après** le redémarrage du conteneur.

        LE VOLUME EST CE QUI PERSISTE, pas le processus. Si les octets ne
        vivaient que dans la mémoire du serveur, ce cas serait rouge — et
        c'est exactement ce qu'un magasin simulé aurait laissé passer.
        """
        etat = _lire_etat()
        octets = _client_brut().lire(etat["storage_path"])
        assert hashlib.sha256(octets).hexdigest() == etat["sha256"]
        assert len(octets) == etat["size_bytes"]

    def test_le_pdf_revient_octet_pour_octet_apres_redemarrage(
            self, client, jeton):
        """LE CAS BINAIRE DE LA RELECTURE.

        Le HTML survit deja au redemarrage. Un PDF met la question autrement:
        ses octets ne forment aucun texte valide, sa table de references
        croisees compte les decalages a l'octet, et un seul octet reecrit le
        rend illisible — sans changer sa taille.

        On verifie donc les MEMES octets par DEUX chemins: la route du produit,
        et le temoin qui lit le compartiment de l'exterieur.
        """
        contenu = Path(ETAT_PDF).read_text(encoding="utf-8")
        assert contenu.strip(), (
            f"le fichier d'etat PDF « {ETAT_PDF} » est vide: la phase de depot "
            "n'a pas depose de PDF, et il n'y a rien a relire.")
        etat = json.loads(contenu)

        r = client.get(
            f"/v1/projects/{etat['project_id']}/deliverables/"
            f"{etat['deliverable_id']}/download",
            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert hashlib.sha256(r.content).hexdigest() == etat["sha256"]
        assert len(r.content) == etat["size_bytes"]
        assert r.content.startswith(b"%PDF-")
        assert r.content.rstrip().endswith(b"%%EOF")

        # LE TEMOIN, SUR LE VOLUME REDEMARRE: memes octets, exactement.
        du_compartiment = _client_brut().lire(etat["storage_path"])
        assert du_compartiment == r.content, (
            "les octets servis par la route different de ceux du compartiment")

        # LE NOM PROPOSE AU TELECHARGEMENT PORTE ENCORE `.pdf`, sous les deux
        # formes de la RFC 6266.
        disposition = r.headers["content-disposition"]
        assert etat["filename"] in disposition
        assert ".pdf" in disposition

    def test_le_disque_local_n_a_jamais_rien_recu(self):
        """AUCUN REPLI, MÊME EN COPIE. Le témoin est un répertoire vide."""
        assert _fichiers_sur_disque() == [], (
            "le magasin declare est objet, et pourtant des fichiers sont "
            "apparus sur le disque local.")

    def test_l_entete_nomme_le_fichier_sous_les_deux_formes(
            self, client, jeton):
        """RFC 6266 : un repli ASCII **et** la forme étendue.

        Un nom accentué n'est pas représentable dans ``filename=`` ; sans
        ``filename*``, le navigateur enregistre un nom mutilé — ou pire, un
        nom tronqué à la première paire de guillemets.
        """
        etat = _lire_etat()
        r = client.get(
            f"/v1/projects/{etat['project_id']}/deliverables/"
            f"{etat['deliverable_id']}/download",
            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 200, r.text
        disposition = r.headers["content-disposition"]
        assert disposition.startswith("attachment; "), disposition
        assert 'filename="' in disposition, disposition
        assert "filename*=UTF-8''" in disposition, disposition
        assert disposition.isascii(), disposition

    def test_une_organisation_voisine_ne_telecharge_pas_un_objet_pourtant_la(
            self, client, jeton):
        """LE REFUS EST UNE AUTORISATION, PAS UNE ABSENCE.

        L'objet est dans le compartiment — le témoin vient de le lire — et le
        membre de l'organisation voisine reçoit néanmoins un refus. C'est la
        seule façon de distinguer « on ne vous le donne pas » de « il n'y est
        pas » : sans le témoin, le refus pourrait n'être qu'un magasin vide, et
        le cloisonnement resterait à prouver.

        LA FORME DU REFUS EST CELLE QUE LE DÉPÔT A DÉJÀ FIXÉE — 422, « projet
        introuvable ou hors de vos organisations » (``test_livrables.py``,
        ``test_une_organisation_voisine_ne_lit_ni_ne_telecharge``). Elle ne dit
        pas si le projet existe, ce qui est le point : un 404 et un 403
        distincts renseigneraient sur l'existence d'un dossier chez un
        concurrent.
        """
        etat = _lire_etat()
        temoin = _client_brut().lire(etat["storage_path"])
        assert hashlib.sha256(temoin).hexdigest() == etat["sha256"]

        r = client.get(
            f"/v1/projects/{etat['project_id']}/deliverables/"
            f"{etat['deliverable_id']}/download",
            headers=_entete(jeton(ACTEUR_B)))
        assert r.status_code == 422, (r.status_code, r.text)
        assert "introuvable" in r.text.lower(), r.text
        assert r.content != temoin, "les octets ont ete servis malgre le refus."
        assert etat["storage_path"] not in r.text, (
            "le refus divulgue le chemin de l'objet.")

    def test_aucun_refus_ne_laisse_filtrer_la_configuration_du_magasin(
            self, client, jeton):
        """NI CLÉ, NI SECRET, NI URL DE COMPARTIMENT DANS UNE RÉPONSE HTTP.

        Un message d'erreur voyage dans des journaux, des tickets et parfois
        des captures d'écran. Celui-ci nomme des variables, jamais leurs
        valeurs.
        """
        etat = _lire_etat()
        corps = []
        for acteur in (ACTEUR_B, ACTEUR_W):
            r = client.get(
                f"/v1/projects/{etat['project_id']}/deliverables/"
                f"{etat['deliverable_id']}/download",
                headers=_entete(jeton(acteur)))
            corps.append(r.text)
        r = client.get(
            f"/v1/projects/{etat['project_id']}/deliverables/"
            f"{uuid.uuid4()}/download",
            headers=_entete(jeton(ACTEUR_A)))
        corps.append(r.text)

        interdits = [os.environ["EUROSTRUCT_S3_SECRET_ACCESS_KEY"],
                     os.environ["EUROSTRUCT_S3_ACCESS_KEY_ID"],
                     os.environ["EUROSTRUCT_S3_ENDPOINT"]]
        for texte in corps:
            for secret in interdits:
                assert secret not in texte, (
                    "une reponse HTTP porte un element de configuration du "
                    "magasin.")

    def test_la_sonde_de_sante_ne_publie_pas_la_configuration_du_magasin(
            self, client):
        """``/health`` ET ``/ready`` SE LISENT DE L'EXTÉRIEUR, sans jeton.

        Tout ce qu'elles disent est public par construction. Une clé d'accès
        ou une adresse de compartiment y serait publiée à qui interroge le
        service.
        """
        interdits = [os.environ["EUROSTRUCT_S3_SECRET_ACCESS_KEY"],
                     os.environ["EUROSTRUCT_S3_ACCESS_KEY_ID"],
                     os.environ["EUROSTRUCT_S3_ENDPOINT"]]
        for route in ("/health", "/ready"):
            r = client.get(route)
            for secret in interdits:
                assert secret not in r.text, (
                    f"{route} publie un element de configuration du magasin.")

    def test_le_dossier_de_revue_se_construit_depuis_le_compartiment(
            self, client, jeton):
        """L'ARCHIVE PORTE LES OCTETS EXACTS, tirés du magasin objet."""
        import io
        import zipfile

        etat = _lire_etat()
        r = client.get(
            f"/v1/projects/{etat['project_id']}/deliverables/"
            f"{etat['deliverable_id']}/review-bundle",
            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 200, r.text

        with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
            manifeste = json.loads(archive.read("manifeste.json"))
            octets = archive.read(f"documents/{etat['filename']}")

        assert hashlib.sha256(octets).hexdigest() == etat["sha256"]
        # LES DEUX EMPREINTES DU MANIFESTE S'ACCORDENT: celle qu'a enregistree
        # la base, et celle des octets tires du compartiment.
        fichier = manifeste["files"][0]
        assert fichier["sha256_recorded"] == etat["sha256"]
        assert fichier["sha256_served"] == etat["sha256"]

    # =======================================================================
    # ETAPE 9 — L'ENUMERATION, CONTRE UN VRAI SERVEUR
    # =======================================================================
    def test_l_enumeration_voit_l_objet_et_retire_le_prefixe(self):
        """LE RAPPROCHEMENT NE PEUT PAS EXISTER SANS CETTE QUESTION.

        Le produit n'a jamais eu besoin d'enumerer: il connait le chemin d'un
        livrable avant de le lire, puisque ce chemin derive du contenu. Seul le
        rapprochement pose la question inverse — « qu'y a-t-il dans le
        compartiment que la base ne nomme pas ? ».

        LE PREFIXE DOIT ETRE RETIRE, et c'est le piege. `ListObjectsV2` rend
        des cles COMPLETES, prefixe declare compris; les comparer telles
        quelles a des `storage_path` declarerait tout le compartiment orphelin
        des qu'un prefixe est configure — c'est-a-dire dans la composition de
        production, ou il en existe un.
        """
        etat = _lire_etat()
        objets = dict(_client_brut().enumerer())

        assert etat["storage_path"] in objets, (
            "l'objet depose n'apparait pas dans l'enumeration. Cles vues: "
            f"{sorted(objets)[:5]}")
        assert objets[etat["storage_path"]] == etat["size_bytes"]

        prefixe = os.environ.get("EUROSTRUCT_S3_PREFIX", "").strip("/")
        if prefixe:
            assert not any(c.startswith(f"{prefixe}/") for c in objets), (
                "le prefixe declare n'a pas ete retire des chemins rendus")

        # L'ENUMERATION BORNEE PAR UN PREFIXE D'ORGANISATION NE DEBORDE PAS.
        sous = dict(_client_brut().enumerer(f"{etat['org_id']}/"))
        assert etat["storage_path"] in sous
        assert set(sous) <= set(objets)

    # =======================================================================
    # ETAPE 10 — LE RAPPROCHEMENT, ET SON INNOCUITE
    # =======================================================================
    def test_le_rapprochement_accorde_la_base_et_le_compartiment(self):
        """CE QUE `docs/STOCKAGE.md` §5 PROMETTAIT SANS L'OUTILLER."""
        from eurostruct_api.reconciliation import (
            ABSENT,
            DIVERGENT,
            INTACT,
            ORPHELIN,
            rapprocher,
        )
        from eurostruct_api.stockage import stockage_configure

        etat = _lire_etat()
        lignes = [
            {"id": i, "org_id": o, "project_id": p, "storage_path": c,
             "sha256": s, "size_bytes": t, "storage_backend": b}
            for (i, o, p, c, s, t, b) in _observer(
                "select id::text, org_id::text, project_id::text, "
                "       storage_path, sha256, size_bytes, storage_backend "
                "  from deliverables")
        ]
        assert lignes, "le decor est cense porter au moins un livrable"

        magasin = stockage_configure()
        rapport = rapprocher(lignes, magasin, empreintes=True)

        # AUCUNE PROMESSE ROMPUE, ET AUCUNE CORRUPTION. Ce sont les deux
        # verdicts qui decrivent un service en faute; ils doivent etre a zero.
        assert rapport.compte(ABSENT) == 0, [
            c for c in rapport.constats if c.verdict == ABSENT]
        assert rapport.compte(DIVERGENT) == 0, [
            c for c in rapport.constats if c.verdict == DIVERGENT]

        # LE LIVRABLE DE CE HARNAIS EST INTACT, nommement.
        intacts = {c.chemin for c in rapport.constats if c.verdict == INTACT}
        assert etat["storage_path"] in intacts

        # DES ORPHELINS, IL Y EN A DEJA — ET C'EST UNE MESURE, PAS UN DEFAUT.
        #
        # `test_un_objet_divergent_n_est_jamais_ecrase_en_silence` depose un
        # objet PAR LE CLIENT TEMOIN, sans qu'aucune ligne ne le reference:
        # c'est exactement ce qu'est un orphelin. Le premier rapprochement
        # jamais execute sur ce decor l'a trouve du premier coup, et ce cas ne
        # doit pas pretendre le contraire — un decor « propre » qu'on aurait
        # nettoye pour faire passer l'assertion ne prouverait plus rien.
        deja = rapport.compte(ORPHELIN)

        # ON EN INJECTE UN DE PLUS, dont on connait le chemin exact. Sans ce
        # second temps, un rapprochement qui ne verrait jamais RIEN serait
        # vert lui aussi.
        perdu = f"{etat['org_id']}/{etat['project_id']}/{'e' * 64}.html"
        _client_brut().deposer(perdu, b"FICTIF objet abandonne")

        apres = rapprocher(lignes, magasin, empreintes=True)
        assert apres.compte(ORPHELIN) == deja + 1
        assert perdu in {c.chemin for c in apres.constats
                         if c.verdict == ORPHELIN}
        assert not apres.sain

        # ET IL EST TOUJOURS LA. Le rapprochement CONSTATE; il ne reprend rien.
        # Le volume entier est detruit a la sortie du harnais — c'est la seule
        # suppression, et elle porte sur un objet dont il prouve la creation.
        assert _client_brut().taille(perdu) == len(b"FICTIF objet abandonne")

    def test_postgresql_refuse_lui_meme_toute_ecriture_du_rapprochement(self):
        """« NE VEUT PAS ECRIRE » ET « NE PEUT PAS ECRIRE » NE SE VALENT PAS.

        Le rapprochement ouvre sa transaction en lecture seule. Ce cas ne se
        contente pas de le lire dans le code: il prend la MEME connexion,
        preparee de la MEME facon, et demande a PostgreSQL d'ecrire. Le serveur
        doit refuser.

        Sans ce cas, la lecture seule ne serait qu'une intention d'auteur — et
        un defaut futur qui glisserait un `update` dans le rapprochement
        passerait toutes les autres assertions.
        """
        import psycopg2

        from eurostruct_api.reconciliation import _lignes_de_livrables

        connexion = psycopg2.connect(DSN_OBS)
        try:
            connexion.set_session(readonly=True)
            lignes = _lignes_de_livrables(connexion)
            assert lignes, "le decor est cense porter au moins un livrable"

            with connexion.cursor() as curseur, pytest.raises(Exception) as pris:  # noqa: PT011
                curseur.execute(
                    "update deliverables set filename = filename")
        finally:
            connexion.close()

        assert "read-only" in str(pris.value).lower(), (
            "PostgreSQL n'a pas refuse l'ecriture pour la raison attendue: "
            f"{pris.value}")
