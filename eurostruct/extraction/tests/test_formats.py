"""Le format se constate sur les octets — ni sur l'extension, ni sur l'en-tête HTTP."""

from __future__ import annotations

import io
import zipfile

import pytest

from eurostruct_extraction import FormatNonPrisEnCharge, detecter_format
from fabrique import dxf_de_plan, entete_dwg, pdf_de_texte


def test_un_pdf_se_reconnait_a_sa_signature():
    detecte = detecter_format(pdf_de_texte([[(40, 40, 10, "FICTIF")]]))
    assert (detecte.format, detecte.type_media, detecte.extension) == (
        "pdf", "application/pdf", "pdf")


def test_un_dxf_ascii_et_un_dxf_binaire_sont_des_dxf():
    assert detecter_format(dxf_de_plan()).version == "ascii"
    assert detecter_format(dxf_de_plan(binaire=True)).version == "binaire"
    assert detecter_format(dxf_de_plan()).type_media == "image/vnd.dxf"


@pytest.mark.parametrize(("signature", "libelle"), [
    ("AC1032", "AutoCAD 2018"), ("AC1027", "AutoCAD 2013"), ("AC1015", "AutoCAD 2000"),
])
def test_un_dwg_dit_sa_version_et_rien_de_plus(signature, libelle):
    detecte = detecter_format(entete_dwg(signature))
    assert (detecte.format, detecte.version, detecte.libelle_version) == (
        "dwg", signature, libelle)


def test_une_version_dwg_inconnue_est_dite_inconnue():
    assert detecter_format(entete_dwg("AC1099")).libelle_version == "version DWG inconnue"


@pytest.mark.parametrize("octets", [
    b"",
    b"\x89PNG\r\n\x1a\n" + bytes(64),
    b"plan.pdf: ceci n'est pas un PDF",
    b"0\nSECTIONNEMENT\n",
])
def test_ce_qui_n_est_ni_pdf_ni_dxf_ni_dwg_est_refuse(octets):
    with pytest.raises(FormatNonPrisEnCharge):
        detecter_format(octets)


def test_une_archive_renommee_en_pdf_reste_une_archive():
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("plan.pdf", "FICTIF")
    with pytest.raises(FormatNonPrisEnCharge):
        detecter_format(tampon.getvalue())
