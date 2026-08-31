"""Le rapprochement base / magasin : ce qu'il voit, et ce qu'il ne touche pas.

CE MODULE N'A BESOIN NI DE POSTGRESQL NI DE RESEAU. Le rapprochement lui-meme
est une fonction pure — des lignes d'un cote, un magasin de l'autre — et c'est
volontaire : la partie qui decide des verdicts se teste sans decor, et la
partie qui parle a la base se reduit a une requete.

L'AUTRE MOITIE EST AILLEURS, ET CONTRE DU REEL. `db/test/stockage_s3.sh`
(etapes 8 et 9) enumere un vrai compartiment MinIO, rapproche la vraie base,
injecte un orphelin et constate qu'il est TOUJOURS LA apres. Et
`TestApresRedemarrage` verifie que PostgreSQL lui-meme refuse une ecriture
dans la transaction du rapprochement.

Ici on eprouve les verdicts; la-bas, l'innocuite.
"""
from __future__ import annotations

import hashlib

import pytest
from eurostruct_api.reconciliation import (
    ABSENT,
    DIVERGENT,
    INTACT,
    ORPHELIN,
    rapprocher,
)
from eurostruct_api.stockage import StockageLocal

ORG = "11111111-1111-1111-1111-111111111111"
PROJET = "22222222-2222-2222-2222-222222222222"


def _ligne(octets: bytes, *, identifiant: str = "d1",
           chemin: str | None = None, backend: str = "local",
           taille: int | None = None, sha: str | None = None) -> dict:
    empreinte = sha or hashlib.sha256(octets).hexdigest()
    return {
        "id": identifiant,
        "org_id": ORG,
        "project_id": PROJET,
        "storage_path": chemin or f"{ORG}/{PROJET}/{empreinte}.html",
        "sha256": empreinte,
        "size_bytes": taille if taille is not None else len(octets),
        "storage_backend": backend,
    }


@pytest.fixture()
def magasin(tmp_path) -> StockageLocal:
    return StockageLocal(tmp_path)


def _verdicts(rapport) -> dict[str, int]:
    return {v: rapport.compte(v)
            for v in (ABSENT, DIVERGENT, ORPHELIN, INTACT)}


# ===========================================================================
# 1 — LES QUATRE VERDICTS
# ===========================================================================
def test_une_ligne_et_son_objet_qui_s_accordent_sont_intacts(magasin):
    octets = b"<html>FICTIF note</html>"
    ligne = _ligne(octets)
    magasin.deposer(ligne["storage_path"], octets)

    rapport = rapprocher([ligne], magasin, empreintes=True)

    assert _verdicts(rapport) == {ABSENT: 0, DIVERGENT: 0, ORPHELIN: 0,
                                  INTACT: 1}
    assert rapport.sain


def test_une_ligne_sans_objet_est_le_verdict_grave(magasin):
    """C'EST LE SEUL VERDICT QUI DECRIT UNE PROMESSE ROMPUE.

    Une ligne existe, un dossier la cite, et le telechargement rendra 503.
    Les trois autres verdicts coutent de la place ou signalent une corruption;
    celui-ci veut dire qu'un document annonce est introuvable.
    """
    ligne = _ligne(b"<html>FICTIF disparu</html>")

    rapport = rapprocher([ligne], magasin)

    assert _verdicts(rapport)[ABSENT] == 1
    assert not rapport.sain
    (constat,) = [c for c in rapport.constats if c.verdict == ABSENT]
    assert constat.deliverable_id == "d1"
    assert "503" in constat.detail


def test_une_taille_qui_ne_correspond_pas_est_divergente(magasin):
    octets = b"<html>FICTIF</html>"
    ligne = _ligne(octets, taille=len(octets) + 100)
    magasin.deposer(ligne["storage_path"], octets)

    rapport = rapprocher([ligne], magasin)

    assert _verdicts(rapport)[DIVERGENT] == 1
    (constat,) = [c for c in rapport.constats if c.verdict == DIVERGENT]
    assert str(len(octets)) in constat.detail


def test_une_empreinte_qui_ne_correspond_pas_n_est_vue_qu_avec_l_option(
        magasin):
    """LA TAILLE NE SUFFIT PAS, ET C'EST TOUT L'INTERET DE L'OPTION.

    Deux contenus differents de meme longueur passent la comparaison de
    taille. Relire chaque objet coute cher sur un magasin de production, donc
    ce n'est pas le defaut — mais ne pas pouvoir le faire du tout laisserait
    une corruption silencieuse jusqu'au premier telechargement.
    """
    octets = b"<html>FICTIF A</html>"
    autres = b"<html>FICTIF B</html>"
    assert len(octets) == len(autres)

    ligne = _ligne(octets)
    magasin.deposer(ligne["storage_path"], autres)

    sans = rapprocher([ligne], magasin, empreintes=False)
    assert _verdicts(sans)[INTACT] == 1, "la taille seule ne voit rien"

    avec = rapprocher([ligne], magasin, empreintes=True)
    assert _verdicts(avec)[DIVERGENT] == 1


def test_un_objet_que_rien_ne_nomme_est_orphelin(magasin):
    magasin.deposer(f"{ORG}/{PROJET}/" + "a" * 64 + ".html", b"abandonne")

    rapport = rapprocher([], magasin)

    assert _verdicts(rapport)[ORPHELIN] == 1
    (constat,) = rapport.constats
    assert "n'est PAS supprime" in constat.detail


# ===========================================================================
# 2 — LES DEUX PIEGES QUI FERAIENT MENTIR LE RAPPORT
# ===========================================================================
def test_les_lignes_d_un_autre_magasin_sont_ecartees_pas_declarees_absentes(
        magasin):
    """UN DEPLOIEMENT QUI A MIGRE GARDE DES LIGNES `local` ET DES LIGNES `s3`.

    Les chercher toutes dans le magasin configure les dirait absentes en
    masse — et noierait la seule qui l'est vraiment.
    """
    ailleurs = _ligne(b"<html>FICTIF s3</html>", identifiant="d-s3",
                      backend="s3")

    rapport = rapprocher([ailleurs], magasin)

    assert _verdicts(rapport) == {ABSENT: 0, DIVERGENT: 0, ORPHELIN: 0,
                                  INTACT: 0}
    assert rapport.sain


def test_deux_lignes_partageant_un_objet_ne_le_rendent_pas_orphelin(magasin):
    """L'ADRESSAGE PAR CONTENU REND CE CAS NORMAL, PAS EXCEPTIONNEL.

    Deux revisions au contenu identique ecrivent au meme endroit. Un
    rapprochement qui apparierait une cle a une seule ligne declarerait la
    seconde absente, ou l'objet orphelin apres suppression de la premiere.
    """
    octets = b"<html>FICTIF partage</html>"
    une = _ligne(octets, identifiant="d1")
    deux = _ligne(octets, identifiant="d2")
    assert une["storage_path"] == deux["storage_path"]
    magasin.deposer(une["storage_path"], octets)

    rapport = rapprocher([une, deux], magasin, empreintes=True)

    assert _verdicts(rapport) == {ABSENT: 0, DIVERGENT: 0, ORPHELIN: 0,
                                  INTACT: 1}


# ===========================================================================
# 3 — L'ENUMERATION DU MAGASIN LOCAL
# ===========================================================================
def test_un_depot_en_cours_n_est_pas_un_orphelin(magasin, tmp_path):
    """`deposer` ECRIT UN PROVISOIRE PUIS RENOMME.

    Un rapprochement lance pendant que le service travaille peut apercevoir ce
    provisoire. Le compter ferait accuser un magasin parfaitement sain.
    """
    dossier = tmp_path / ORG / PROJET
    dossier.mkdir(parents=True)
    (dossier / ".abcdef.html.4242.partiel").write_bytes(b"en cours")

    assert magasin.enumerer() == []
    assert rapprocher([], magasin).sain


def test_l_enumeration_rend_des_chemins_relatifs_a_la_racine(magasin):
    octets = b"x"
    chemin = f"{ORG}/{PROJET}/" + "b" * 64 + ".html"
    magasin.deposer(chemin, octets)

    assert magasin.enumerer() == [(chemin, 1)]
    assert magasin.taille(chemin) == 1
    assert magasin.taille("nulle/part.html") is None


# ===========================================================================
# 4 — L'OUTIL N'A AUCUN MOYEN D'ECRIRE
# ===========================================================================
class _MagasinSansEcriture:
    """Un magasin qui ne SAIT PAS deposer: la methode n'existe pas.

    SI `rapprocher` TENTAIT D'ECRIRE, CE CAS LEVERAIT `AttributeError`. C'est
    une garantie plus forte qu'un espion qui compterait les appels: il n'y a
    rien a appeler.
    """

    nom = "local"

    def __init__(self, objets: dict[str, bytes]) -> None:
        self._o = objets

    def enumerer(self, prefixe: str = "") -> list[tuple[str, int]]:
        return [(c, len(v)) for c, v in self._o.items()
                if c.startswith(prefixe)]

    def lire(self, chemin: str) -> bytes:
        return self._o[chemin]

    def taille(self, chemin: str) -> int | None:
        octets = self._o.get(chemin)
        return None if octets is None else len(octets)


def test_le_rapprochement_n_appelle_aucun_geste_d_ecriture():
    octets = b"<html>FICTIF</html>"
    ligne = _ligne(octets)
    orphelin = f"{ORG}/{PROJET}/" + "c" * 64 + ".html"
    magasin = _MagasinSansEcriture({ligne["storage_path"]: octets,
                                    orphelin: b"perdu"})

    rapport = rapprocher([ligne], magasin, empreintes=True)

    assert _verdicts(rapport) == {ABSENT: 0, DIVERGENT: 0, ORPHELIN: 1,
                                  INTACT: 1}


def test_le_magasin_est_intact_apres_un_rapprochement(magasin, tmp_path):
    """LA MESURE PORTE SUR LE DISQUE, PAS SUR L'INTENTION.

    On photographie chemins, tailles et empreintes avant, on rapproche avec
    toutes les options, on rephotographie. Le moindre octet ecrit, deplace ou
    supprime ferait diverger les deux photos.
    """
    octets = b"<html>FICTIF</html>"
    ligne = _ligne(octets)
    magasin.deposer(ligne["storage_path"], octets)
    magasin.deposer(f"{ORG}/{PROJET}/" + "d" * 64 + ".html", b"orphelin")
    manquante = _ligne(b"<html>FICTIF absent</html>", identifiant="d9")

    def photo() -> set[tuple[str, int, str]]:
        return {(str(c.relative_to(tmp_path)), c.stat().st_size,
                 hashlib.sha256(c.read_bytes()).hexdigest())
                for c in tmp_path.rglob("*") if c.is_file()}

    avant = photo()
    rapport = rapprocher([ligne, manquante], magasin, empreintes=True)
    assert not rapport.sain, "le decor porte volontairement des ecarts"

    assert photo() == avant
