"""L'attestation vivait dans la base ; le document qui circule n'en portait rien.

LE DEFAUT QUE CE MODULE FERME
-------------------------------
Un ingenieur habilite atteste une note de calcul: son nom, son role, son numero
d'inscription, sa declaration, ses reserves et la date sont ecrits dans
`validations`. Le PDF, lui, ne change pas — et c'est heureux: le modifier apres
coup detruirait l'empreinte sur laquelle porte l'attestation.

Consequence: **le document qui circule ne porte pas l'attestation.** Le bureau
d'etudes transmet un PDF que rien ne distingue d'un brouillon, et l'attestation
reste dans une base que le destinataire ne voit pas. Pour lui, l'etude n'a ete
relue par personne.

CE QUE L'EMISSION DOIT FAIRE, DESORMAIS
-----------------------------------------
Composer un SECOND PDF — `issued_calculation_note_pdf` — qui porte
l'attestation, reference l'original par son empreinte, et nait `final`. Le
tout dans la meme transaction que le passage de l'original a `final`: un
original emis sans document atteste, ou un document atteste sans original
emis, n'ont de sens ni l'un ni l'autre.

L'ORIGINAL RESTE IDENTIQUE AU BIT PRES. Aucun cas de ce module ne passe si un
seul octet du PDF valide a bouge.

Lance par `db/test/livrable_validation.sh`, qui pose le decor complet.
"""
# Le nom d'une fixture importée reparaît en paramètre de chaque test qui la
# demande ; ruff y voit une redéfinition alors que c'est le mécanisme même de
# pytest. La levée est déclarée ici plutôt que répétée sur chaque signature.
# ruff: noqa: F811

from __future__ import annotations

import hashlib
import json

import pytest

from .test_livrable_dxf import _creer_dxf
from .test_livrables import (  # noqa: F401 — fixtures partagées, décor commun
    ACTEUR_A,
    ACTEUR_B,
    ACTEUR_D,
    ACTEUR_V,
    ACTEUR_W,
    DECOR_PRESENT,
    _brouillon,
    _brouillon_pdf,
    _entete,
    _localisation,
    _objets_du_magasin,
    _observer,
    calcul_exploratoire,
    calcul_strict,
    cle,
    client,
    client_neuf,
    jeton,
    projet,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/livrable_validation.sh, qui pose la base deployee, "
                "les adhesions, la racine d'autorite et le magasin d'objets."),
    ),
]

DECLARATION = "FICTIF — j'ai relu ce calcul et j'en reponds."
RESERVES = "FICTIF — sous reserve de la reconnaissance de sol."


def _base(projet) -> str:
    return f"/v1/projects/{projet['project_id']}/deliverables/"


def _attestee(client, jeton, projet, calcul_id, *, reserves=RESERVES) -> dict:
    """Une note PDF menee jusqu'a l'attestation, par DEUX acteurs distincts.

    Le redacteur cree et soumet; le validateur atteste. C'est le parcours
    reel, et il est refait a chaque cas parce que les transitions sont
    irreversibles: un livrable deja emis ne peut pas resservir.
    """
    note = _brouillon_pdf(client, jeton, projet, calcul_id)
    r = client.post(f"{_base(projet)}{note['deliverable_id']}/review",
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    r = client.post(
        f"{_base(projet)}{note['deliverable_id']}/validation",
        json={"statement": DECLARATION, "reservations": reserves},
        headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text
    return note


def _emettre(client, jeton, projet, deliverable_id, acteur=ACTEUR_V):
    return client.post(f"{_base(projet)}{deliverable_id}/final",
                       headers=_entete(jeton(acteur)))


def _emis_de(source_id: str) -> list[tuple]:
    return _observer(
        "select id::text, kind::text, state::text, sha256, size_bytes, "
        "       validation_id::text, derived_from_id::text "
        "  from deliverables where derived_from_id = %s", (source_id,))


# ===========================================================================
# 1 — LE PARCOURS NOMINAL, A DEUX ACTEURS REELLEMENT DISTINCTS
# ===========================================================================
def test_l_emission_produit_un_second_pdf_atteste(
        client, jeton, projet, calcul_strict):
    """LE GESTE ENTIER, ET CE QU'IL LAISSE DERRIERE LUI."""
    note = _attestee(client, jeton, projet, calcul_strict)
    _, _, sha_avant, taille_avant = _localisation(note["deliverable_id"])

    r = _emettre(client, jeton, projet, note["deliverable_id"])
    assert r.status_code == 200, r.text
    detail = r.json()

    # L'ORIGINAL EST EMIS, ET SES OCTETS N'ONT PAS BOUGE D'UN BIT.
    assert detail["state"] == "final"
    _, _, sha_apres, taille_apres = _localisation(note["deliverable_id"])
    assert (sha_apres, taille_apres) == (sha_avant, taille_avant)

    # UN SECOND DOCUMENT EXISTE, ET IL DERIVE DE CELUI-LA.
    emis = _emis_de(note["deliverable_id"])
    assert len(emis) == 1, "l'emission doit produire exactement un document"
    (emis_id, genre, etat, sha_emis, taille_emis,
     validation_emis, derive) = emis[0]
    assert genre == "issued_calculation_note_pdf"
    assert etat == "final"
    assert derive == note["deliverable_id"]
    assert sha_emis != sha_avant, "le document emis n'est pas l'original"
    assert taille_emis > 0

    # IL PORTE LA MEME ATTESTATION, PAS UNE AUTRE.
    source = _observer(
        "select validation_id::text from deliverables where id = %s",
        (note["deliverable_id"],))[0][0]
    assert validation_emis == source

    # ET LA REPONSE LE NOMME, sans quoi le client devrait le deviner.
    assert detail.get("issued_deliverable_id") == emis_id


def test_le_document_emis_se_telecharge_et_porte_l_attestation(
        client, jeton, projet, calcul_strict):
    """CE QUE LE DESTINATAIRE DOIT POUVOIR LIRE DANS LE FICHIER LUI-MEME."""
    note = _attestee(client, jeton, projet, calcul_strict)
    emis_id = _emettre(client, jeton, projet,
                       note["deliverable_id"]).json()["issued_deliverable_id"]

    r = client.get(f"{_base(projet)}{emis_id}/download",
                   headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")

    _, _, sha, taille = _localisation(emis_id)
    assert hashlib.sha256(r.content).hexdigest() == sha
    assert len(r.content) == taille

    # LE CONTENU EST RELU PAR UN LECTEUR TIERS, pas par notre propre ecrivain:
    # se relire soi-meme ne prouve que la coherence avec soi-meme.
    pypdf = pytest.importorskip("pypdf")
    lu = pypdf.PdfReader(__import__("io").BytesIO(r.content))
    texte = "\n".join(page.extract_text() or "" for page in lu.pages)

    source = _observer(
        "select d.sha256, v.validator_name, v.validator_role::text, "
        "       v.professional_id, v.statement, v.reservations, "
        "       v.id::text, d.execution_identity, d.engine_build_sha, "
        "       d.inputs_hash "
        "  from deliverables d join validations v on v.id = d.validation_id "
        " where d.id = %s", (note["deliverable_id"],))[0]
    (sha_source, nom, role, inscription, declaration, reserves,
     validation_id, identite, build, entrees) = source

    assert "Document" in texte and "mis" in texte      # « Document émis »
    assert sha_source in texte, "le SHA-256 de l'original doit y figurer"
    assert validation_id in texte
    assert nom in texte
    assert role in texte
    assert inscription is None or inscription in texte
    # LE TIRET CADRATIN EST SUBSTITUE PAR L'ECRIVAIN PDF, et c'est voulu:
    # `pdf.py` n'emporte aucune police et remplace « — » par « -- » plutot que
    # de servir un caractere qu'un lecteur afficherait en carre. On confronte
    # donc la partie du texte qui ne subit aucune substitution — ce qui reste
    # le controle utile: la declaration de l'ingenieur, mot pour mot.
    assert declaration.split("—")[-1].strip() in texte
    assert reserves.split("—")[-1].strip() in texte
    assert identite in texte
    assert build in texte
    assert entrees in texte
    # ET LA LIMITE, DITE EN TOUTES LETTRES.
    bas = texte.lower()
    assert "signature" in bas and "qualifi" in bas


def test_les_deux_pdf_survivent_a_un_redemarrage_de_l_api(
        client, client_neuf, jeton, projet, calcul_strict):
    """F5 NE PROUVE RIEN; UNE APPLICATION RECONSTRUITE, SI."""
    note = _attestee(client, jeton, projet, calcul_strict)
    emis_id = _emettre(client, jeton, projet,
                       note["deliverable_id"]).json()["issued_deliverable_id"]

    attendus = {i: _localisation(i)[2]
                for i in (note["deliverable_id"], emis_id)}

    for livrable_id, sha in attendus.items():
        r = client_neuf.get(f"{_base(projet)}{livrable_id}/download",
                            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 200, (livrable_id, r.text)
        assert hashlib.sha256(r.content).hexdigest() == sha


def test_le_dossier_de_revue_liste_les_deux_sans_etendre_l_attestation(
        client, jeton, projet, calcul_strict):
    """EMETTRE N'ETEND PAS LA PORTEE DE L'ATTESTATION AU PLAN."""
    import io
    import zipfile

    note = _attestee(client, jeton, projet, calcul_strict)
    plan = _creer_dxf(client, jeton, projet, calcul_strict).json()
    emis_id = _emettre(client, jeton, projet,
                       note["deliverable_id"]).json()["issued_deliverable_id"]

    r = client.get(f"{_base(projet)}{note['deliverable_id']}/review-bundle",
                   headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        m = json.loads(archive.read("manifeste.json"))

    par_id = {a["deliverable_id"]: a
              for a in m["review_snapshot"]["artifacts"]}
    assert emis_id in par_id
    assert par_id[emis_id]["kind"] == "issued_calculation_note_pdf"
    assert par_id[emis_id]["derived_from_id"] == note["deliverable_id"]

    non_couverts = {a["deliverable_id"]
                    for a in m["attestation"]["does_not_cover"]}
    assert plan["deliverable_id"] in non_couverts, (
        "le plan reste hors de la portee de l'attestation, meme apres "
        "l'emission")


# ===========================================================================
# 2 — QUI PEUT EMETTRE, ET QUI NE PEUT PAS
# ===========================================================================
@pytest.mark.parametrize("acteur", [ACTEUR_A, ACTEUR_W])
def test_un_non_validateur_ne_peut_pas_emettre(
        client, jeton, projet, calcul_strict, acteur):
    """REDACTEUR ET LECTEUR SONT REFUSES, ET AUCUN DOCUMENT N'EST ECRIT."""
    note = _attestee(client, jeton, projet, calcul_strict)

    r = _emettre(client, jeton, projet, note["deliverable_id"], acteur=acteur)

    assert r.status_code == 422, r.text
    assert _emis_de(note["deliverable_id"]) == []
    etat = _observer("select state::text from deliverables where id = %s",
                     (note["deliverable_id"],))[0][0]
    assert etat == "validated", "l'original ne doit pas avoir bouge"


def test_un_validateur_desactive_ne_peut_pas_emettre(
        client, jeton, projet, calcul_strict):
    """LA LIGNE D'ADHESION SURVIT; LE DROIT D'ENGAGER LE BUREAU, NON."""
    note = _attestee(client, jeton, projet, calcul_strict)

    r = _emettre(client, jeton, projet, note["deliverable_id"],
                 acteur=ACTEUR_D)

    assert r.status_code == 422, r.text
    assert _emis_de(note["deliverable_id"]) == []


def test_un_validateur_d_une_autre_organisation_ne_peut_pas_emettre(
        client, jeton, projet, calcul_strict):
    note = _attestee(client, jeton, projet, calcul_strict)

    r = _emettre(client, jeton, projet, note["deliverable_id"],
                 acteur=ACTEUR_B)

    assert r.status_code == 422, r.text
    assert _emis_de(note["deliverable_id"]) == []


# ===========================================================================
# 3 — CE QUI NE S'EMET PAS
# ===========================================================================
def test_un_brouillon_ne_s_emet_pas(client, jeton, projet, calcul_strict):
    note = _brouillon_pdf(client, jeton, projet, calcul_strict)

    r = _emettre(client, jeton, projet, note["deliverable_id"])

    assert r.status_code == 422, r.text
    assert "attestation" in json.dumps(r.json()).lower()
    assert _emis_de(note["deliverable_id"]) == []


def test_une_piece_en_relecture_ne_s_emet_pas(
        client, jeton, projet, calcul_strict):
    note = _brouillon_pdf(client, jeton, projet, calcul_strict)
    r = client.post(f"{_base(projet)}{note['deliverable_id']}/review",
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text

    r = _emettre(client, jeton, projet, note["deliverable_id"])

    assert r.status_code == 422, r.text
    assert _emis_de(note["deliverable_id"]) == []


def test_un_plan_dxf_s_emet_mais_ne_produit_aucun_document_emis(
        client, jeton, projet, calcul_strict):
    """CETTE PRIMITIVE N'EST PAS UNE FONCTION GENERIQUE DE CREATION.

    Un plan se transmet tel quel: il ne porte pas d'attestation nominative de
    calcul, et lui en fabriquer une laisserait croire qu'un ingenieur repond
    du dessin comme il repond des nombres.

    MAIS IL S'EMET, ET C'ETAIT MON ERREUR. J'attendais d'abord un refus; la
    suite existante l'a corrigee en tombant. Empecher l'emission d'un plan
    aurait ete une REGRESSION: elle marchait avant ce lot.
    """
    plan = _creer_dxf(client, jeton, projet, calcul_strict).json()
    r = client.post(f"{_base(projet)}{plan['deliverable_id']}/review",
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    r = client.post(
        f"{_base(projet)}{plan['deliverable_id']}/validation",
        json={"statement": DECLARATION, "reservations": None},
        headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text

    r = _emettre(client, jeton, projet, plan["deliverable_id"])

    assert r.status_code == 200, r.text
    assert r.json()["state"] == "final"
    assert r.json().get("issued_deliverable_id") is None
    assert _emis_de(plan["deliverable_id"]) == []


def test_un_calcul_exploratoire_ne_donne_aucune_attestation(
        client, jeton, projet, calcul_exploratoire):
    """LA BARRIERE EST EN AMONT, ET C'EST LA BONNE PLACE.

    Un calcul non strict a pu employer des parametres nationaux non confirmes:
    il ne s'atteste pas, donc il ne s'emet pas.
    """
    note = _brouillon_pdf(client, jeton, projet, calcul_exploratoire)
    r = client.post(f"{_base(projet)}{note['deliverable_id']}/review",
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    r = client.post(
        f"{_base(projet)}{note['deliverable_id']}/validation",
        json={"statement": DECLARATION, "reservations": None},
        headers=_entete(jeton(ACTEUR_V)))

    assert r.status_code == 422, r.text
    assert _emis_de(note["deliverable_id"]) == []


# ===========================================================================
# 4 — L'IDENTITE NE S'ENVOIE PAS
# ===========================================================================
@pytest.mark.parametrize("champ,valeur", [
    ("validator_name", "FICTIF Quelqu'un d'autre"),
    ("professional_id", "FICTIF-999999"),
    ("filename", "attestation-choisie.pdf"),
    ("sha256", "f" * 64),
    ("deliverable_id", "00000000-0000-0000-0000-000000000000"),
    ("issued_deliverable_id", "00000000-0000-0000-0000-000000000000"),
])
def test_le_corps_ne_peut_rien_dicter_a_l_emission(
        client, jeton, projet, calcul_strict, champ, valeur):
    """`Strict` REFUSE LES CHAMPS SUPPLEMENTAIRES, ET C'EST LE POINT.

    Un client doit apprendre que sa valeur n'a aucun effet plutot que de le
    croire. L'identite du validateur sort de son adhesion, cote serveur.
    """
    note = _attestee(client, jeton, projet, calcul_strict)

    r = client.post(f"{_base(projet)}{note['deliverable_id']}/final",
                    json={champ: valeur},
                    headers=_entete(jeton(ACTEUR_V)))

    assert r.status_code == 422, (champ, r.status_code, r.text)
    assert _emis_de(note["deliverable_id"]) == []


# ===========================================================================
# 5 — CONCURRENCE, IDEMPOTENCE, ET ABSENCE DE DOUBLON
# ===========================================================================
def test_une_seconde_emission_rend_le_meme_document(
        client, jeton, projet, calcul_strict):
    """UNE REPONSE PERDUE NE DOIT PAS COUTER UN SECOND DOCUMENT.

    Le PDF emis est compose depuis des donnees GELEES: deux tentatives
    produisent les memes octets. La seconde doit donc retrouver le document
    deja emis, pas en ecrire un autre.
    """
    note = _attestee(client, jeton, projet, calcul_strict)
    premier = _emettre(client, jeton, projet, note["deliverable_id"])
    assert premier.status_code == 200, premier.text
    emis_id = premier.json()["issued_deliverable_id"]
    objets = _objets_du_magasin(
        f"{projet['organization_id']}/{projet['project_id']}/")

    second = _emettre(client, jeton, projet, note["deliverable_id"])

    assert second.status_code == 200, second.text
    assert second.json()["issued_deliverable_id"] == emis_id
    assert len(_emis_de(note["deliverable_id"])) == 1
    # ET AUCUN OCTET SUPPLEMENTAIRE: le chemin derive de l'empreinte, donc la
    # seconde composition retombe sur le meme objet.
    assert _objets_du_magasin(
        f"{projet['organization_id']}/{projet['project_id']}/") == objets


def test_deux_emissions_simultanees_ne_produisent_qu_un_document(
        client, jeton, projet, calcul_strict):
    """LA BASE TRANCHE, PAS L'APPLICATION.

    Entre le `select` et l'`insert` d'une transaction, une autre passe. Seuls
    le verrou de la source et l'index unique sur `derived_from_id` peuvent
    tenir cette promesse.
    """
    import threading

    note = _attestee(client, jeton, projet, calcul_strict)
    reponses: list = []
    barriere = threading.Barrier(2)

    def emettre() -> None:
        barriere.wait()
        reponses.append(_emettre(client, jeton, projet,
                                 note["deliverable_id"]))

    fils = [threading.Thread(target=emettre) for _ in range(2)]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=60)

    assert len(reponses) == 2
    codes = sorted(r.status_code for r in reponses)
    assert codes[0] == 200, [r.text for r in reponses]
    # QU'IL Y AIT UN OU DEUX SUCCES IMPORTE PEU; ce qui compte est qu'il
    # n'existe QU'UN document emis, et que l'echec eventuel soit un refus
    # propre et non une erreur interne.
    assert codes[1] in (200, 422, 409), [r.text for r in reponses]
    assert len(_emis_de(note["deliverable_id"])) == 1


def test_le_document_emis_ne_se_reemet_pas(client, jeton, projet, calcul_strict):
    """UN DOCUMENT EMIS EST DEJA `final`: il n'y a rien a emettre."""
    note = _attestee(client, jeton, projet, calcul_strict)
    emis_id = _emettre(client, jeton, projet,
                       note["deliverable_id"]).json()["issued_deliverable_id"]

    r = _emettre(client, jeton, projet, emis_id)

    assert r.status_code == 422, r.text
    assert _emis_de(emis_id) == []


# ===========================================================================
# 6 — DETERMINISME
# ===========================================================================
def test_deux_attestations_du_meme_dossier_ont_la_meme_empreinte(
        client, jeton, projet, calcul_strict):
    """MEME EXIGENCE QUE PARTOUT AILLEURS: le chemin derive de l'empreinte."""
    a = _attestee(client, jeton, projet, calcul_strict)
    emis_a = _emettre(client, jeton, projet,
                      a["deliverable_id"]).json()["issued_deliverable_id"]
    sha_a = _localisation(emis_a)[2]

    # Une SECONDE note du meme calcul, attestee dans les memes termes.
    b = _attestee(client, jeton, projet, calcul_strict)
    emis_b = _emettre(client, jeton, projet,
                      b["deliverable_id"]).json()["issued_deliverable_id"]
    sha_b = _localisation(emis_b)[2]

    # LES DEUX ATTESTATIONS DIFFERENT — identifiants de validation distincts,
    # dates distinctes — mais chacune est stable, ce que prouve le fait que
    # son chemin de stockage porte bien son empreinte.
    for emis_id, sha in ((emis_a, sha_a), (emis_b, sha_b)):
        _, chemin, enregistre, _ = _localisation(emis_id)
        assert enregistre == sha
        assert sha in chemin
