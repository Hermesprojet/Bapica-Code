"""``parseDocument()`` : lire un document déposé, et dire ce qui a été lu.

LE STATUT DIT LA VÉRITÉ SUR LA LECTURE, page par page :

``analyse``   toutes les pages ont été lues (couche texte ou OCR) ;
``partiel``   certaines ne l'ont pas été — le compte rendu dit lesquelles et
              pourquoi (borne de pages, OCR indisponible ou en échec) ;
``non_lu``    rien n'a été lu : DWG sans conversion sous licence, ou PDF sans
              couche texte sur un serveur sans OCR ;
``echec``     la lecture a échoué (fichier corrompu, PDF protégé) ; une
              nouvelle analyse reste possible.

UN PDF D'UNE SEULE PAGE QUI PORTE DES TRAITS est aussi lu comme un dessin
(``geometrie/pdf_vectoriel.py``) : ses primitives passent dans la même chaîne
géométrique que celles d'un DXF. Un PDF de plusieurs pages, ou sans traits,
n'est lu que pour son texte, et le compte rendu dit pourquoi.

UN ÉCHEC N'EST PAS UNE EXCEPTION QUI REMONTE. Le document est déposé et
inscrit ; ce qui a échoué, c'est sa lecture, et cela se constate sur la ligne
du document plutôt que dans un journal que personne ne lit.
"""

from __future__ import annotations

from typing import Any

from .formats import FormatDetecte, FormatNonPrisEnCharge, detecter_format
from .geometrie.pdf_vectoriel import lire_geometrie_pdf
from .lecteurs.dwg import MOTIF_DWG_NON_LU, ConvertisseurDWG
from .lecteurs.dxf import lire_dxf
from .lecteurs.ocr import LecteurOcr, OcrTesseract
from .lecteurs.pdf import PAGES_MAX_OCR, PAGES_MAX_TEXTE, lire_pdf
from .modele import DocumentAnalyse

__all__ = ["OCR_PAR_DEFAUT", "parse_document"]

#: Le sentinel « OCR par défaut » : Tesseract s'il est disponible, sinon les
#: pages sans couche texte sont nommées « non lues ».
OCR_PAR_DEFAUT = "defaut"


def parse_document(
    octets: bytes,
    *,
    ocr: LecteurOcr | None | str = OCR_PAR_DEFAUT,
    convertisseur_dwg: ConvertisseurDWG | None = None,
    pages_max_texte: int = PAGES_MAX_TEXTE,
    pages_max_ocr: int = PAGES_MAX_OCR,
) -> DocumentAnalyse:
    """Lit les octets. Lève :class:`FormatNonPrisEnCharge` si le format n'est
    pas reçu ; toute autre défaillance devient une analyse ``echec``."""
    detecte = detecter_format(octets)
    lecteur_ocr: LecteurOcr | None = (OcrTesseract() if ocr == OCR_PAR_DEFAUT
                                      else ocr)  # type: ignore[assignment]
    try:
        if detecte.format == "pdf":
            return _analyser_pdf(octets, lecteur_ocr, pages_max_texte, pages_max_ocr)
        if detecte.format == "dxf":
            return _analyser_dxf(octets, "dxf", conversion=None)
        return _analyser_dwg(octets, detecte, convertisseur_dwg)
    except FormatNonPrisEnCharge:
        raise
    except Exception as cause:  # noqa: BLE001 — une lecture echouee se constate
        return DocumentAnalyse(
            format=detecte.format, statut="echec",
            detail=_motif_d_echec(cause), nombre_de_pages=None, couche_texte=None,
            version_dwg=detecte.version if detecte.format == "dwg" else None,
            compte_rendu={"error": type(cause).__name__}, octets=octets)


def _motif_d_echec(cause: BaseException) -> str:
    nom = type(cause).__name__
    if "Password" in nom or "Encrypt" in nom:
        return ("lecture impossible: le PDF est protege par un mot de passe. "
                "Deposez une version non protegee.")
    message = " ".join(str(cause).split())[:200]
    return f"lecture impossible ({nom}){': ' + message if message else ''}."


def _analyser_pdf(octets: bytes, ocr: LecteurOcr | None, pages_max_texte: int,
                  pages_max_ocr: int) -> DocumentAnalyse:
    lecture = lire_pdf(octets, ocr=ocr, pages_max_texte=pages_max_texte,
                       pages_max_ocr=pages_max_ocr)
    if lecture.nombre_de_pages == 0:
        return DocumentAnalyse(format="pdf", statut="echec",
                               detail="le PDF ne contient aucune page.",
                               nombre_de_pages=0, couche_texte=False, octets=octets)

    lues = [p for p in lecture.pages if p.methode in ("texte_natif", "ocr")]
    natives = sum(1 for p in lues if p.methode == "texte_natif")
    par_ocr = sum(1 for p in lues if p.methode == "ocr")
    non_lues = lecture.non_lues

    if not lues:
        statut = "non_lu"
    elif non_lues:
        statut = "partiel"
    else:
        statut = "analyse"

    morceaux = []
    if natives:
        morceaux.append(f"{natives} page(s) lue(s) par leur couche texte")
    if par_ocr:
        morceaux.append(f"{par_ocr} page(s) lue(s) par OCR")
    if non_lues:
        motifs = sorted({n["motif"] for n in non_lues})
        morceaux.append(f"{len(non_lues)} page(s) non lue(s): " + "; ".join(motifs))
    raison_ocr = ocr.indisponible() if ocr is not None else "OCR non active"
    compte_rendu: dict[str, Any] = {
        "pages": [{"page": p.numero, "method": p.methode, "words": len(p.mots),
                   "width": round(p.largeur, 2), "height": round(p.hauteur, 2)}
                  for p in lecture.pages],
        "not_read": non_lues,
        "ocr": {"engine": getattr(ocr, "nom", None), "available": raison_ocr is None,
                "reason_unavailable": raison_ocr},
        "limits": {"text_pages_max": pages_max_texte, "ocr_pages_max": pages_max_ocr},
    }
    detail = ", ".join(morceaux)
    primitives = None
    try:
        geometrie = lire_geometrie_pdf(octets)
    except Exception as cause:  # noqa: BLE001 — le texte reste lu
        detail += "; geometrie illisible, seuls les textes sont lus"
        compte_rendu["geometry_error"] = type(cause).__name__
    else:
        primitives = geometrie.primitives
        compte_rendu["geometry_read"] = (
            {"read": False, "reason": geometrie.motif} if primitives is None
            else {"read": True, **geometrie.compte_rendu})
        if primitives is not None:
            echelle = geometrie.compte_rendu["scale"]
            detail += (f"; geometrie: {len(primitives.segments)} trait(s), "
                       f"{len(primitives.cercles)} bulle(s) d'axe, "
                       f"{geometrie.compte_rendu['dimensions_rebuilt']} cote(s) reconstituee(s); "
                       + (f"echelle {echelle['scale']} ecrite et confirmee par "
                          f"{echelle['concordant']} cote(s) sur {echelle['dimensions']} "
                          f"(lues en {echelle['dimension_unit']})" if echelle["established"]
                          else "echelle non etablie, longueurs en points sans unite"))
    return DocumentAnalyse(
        format="pdf", statut=statut, detail=detail + ".",
        nombre_de_pages=lecture.nombre_de_pages, couche_texte=lecture.couche_texte,
        pages=tuple(lecture.pages), compte_rendu=compte_rendu, octets=octets,
        primitives_dxf=primitives)


def _analyser_dxf(octets: bytes, fmt: str, *,
                  conversion: dict[str, Any] | None) -> DocumentAnalyse:
    lecture = lire_dxf(octets)
    textes = sum(1 for e in lecture.entites if e.type in ("TEXT", "MTEXT", "ATTRIB"))
    cotes = sum(1 for e in lecture.entites if e.type == "DIMENSION")
    detail = (f"espace objet lu: {textes} texte(s), {cotes} cote(s); unite du dessin "
              f"{lecture.unites or 'non declaree ($INSUNITS=' + str(lecture.insunits) + ')'}")
    if lecture.tronquee:
        detail += "; lecture arretee a la borne d'entites"
    compte_rendu: dict[str, Any] = {
        "dxf_version": lecture.version, "insunits": lecture.insunits,
        "drawing_units": lecture.unites, "entities_read": len(lecture.entites),
        "texts": textes, "dimensions": cotes, "truncated": lecture.tronquee,
        "repairs": lecture.erreurs_corrigees,
        "dimension_types": dict(sorted(lecture.cotes_par_type.items())),
    }
    primitives = lecture.primitives
    if primitives is not None:
        detail += (f"; geometrie: {len(primitives.segments)} trait(s), "
                   f"{len(primitives.contours)} contour(s), {len(primitives.cercles)} cercle(s), "
                   f"{len(primitives.insertions)} bloc(s) explose(s)")
        compte_rendu["geometry_read"] = {
            "segments": len(primitives.segments), "outlines": len(primitives.contours),
            "circles": len(primitives.cercles), "inserts": len(primitives.insertions),
            "truncated": primitives.tronquee}
    if lecture.erreur_geometrie:
        detail += "; geometrie illisible, seuls les textes sont lus"
        compte_rendu["geometry_error"] = lecture.erreur_geometrie
    if conversion is not None:
        compte_rendu["conversion"] = conversion
    partiel = lecture.tronquee or bool(primitives is not None and primitives.tronquee)
    return DocumentAnalyse(
        format=fmt, statut="partiel" if partiel else "analyse",
        detail=detail + ".", nombre_de_pages=1, couche_texte=True,
        entites_dxf=tuple(lecture.entites), unites_dxf=lecture.unites,
        compte_rendu=compte_rendu, octets=octets, primitives_dxf=primitives)


def _analyser_dwg(octets: bytes, detecte: FormatDetecte,
                  convertisseur: ConvertisseurDWG | None) -> DocumentAnalyse:
    version = {"dwg_version": detecte.version, "dwg_release": detecte.libelle_version}
    if convertisseur is None:
        return DocumentAnalyse(
            format="dwg", statut="non_lu",
            detail=f"{MOTIF_DWG_NON_LU} (version {detecte.libelle_version}).",
            nombre_de_pages=None, couche_texte=None, version_dwg=detecte.version,
            compte_rendu=dict(version, remedy="exporter en DXF R2018"), octets=octets)
    dxf = convertisseur.convertir(octets)
    if detecter_format(dxf).format != "dxf":
        raise FormatNonPrisEnCharge(
            f"la conversion « {convertisseur.nom} » n'a pas rendu un DXF.")
    analyse = _analyser_dxf(dxf, "dwg",
                            conversion=dict(version, converter=convertisseur.nom))
    return DocumentAnalyse(
        format="dwg", statut=analyse.statut,
        detail=f"converti par {convertisseur.nom}; {analyse.detail}",
        nombre_de_pages=analyse.nombre_de_pages, couche_texte=analyse.couche_texte,
        entites_dxf=analyse.entites_dxf, unites_dxf=analyse.unites_dxf,
        version_dwg=detecte.version, compte_rendu=analyse.compte_rendu, octets=octets,
        primitives_dxf=analyse.primitives_dxf)
