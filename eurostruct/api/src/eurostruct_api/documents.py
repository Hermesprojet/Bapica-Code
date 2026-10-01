"""La lecture des plans, côté service : déposer, analyser, décider, reporter,
et contrôler la provenance d'une entrée avant le calcul.

LES CINQ GESTES DEMANDÉS, ET OÙ ILS VIVENT
-------------------------------------------
``uploadDocument()``            :func:`upload_document` — octets déposés,
                                relus, vérifiés, PUIS inscrits ;
``parseDocument()``             ``eurostruct_extraction.parse_document`` ;
``extractEngineeringData()``    ``eurostruct_extraction.extract_engineering_data`` ;
``createExtractionRecords()``   :func:`create_extraction_records` — un seul
                                appel de primitive, une seule transaction ;
``confirmExtraction()``         :func:`confirm_extraction` — le nom vient de
                                l'adhésion, la date du serveur.

CE QUE CE MODULE NE FAIT JAMAIS
--------------------------------
Il ne confirme rien, n'arrondit rien, ne convertit rien d'inexact. Le report
d'une longueur dans l'étude passe par un facteur DÉCIMAL EXACT (mm, cm, m) :
une unité qui n'en a pas — le pouce, le pied — n'est pas convertie ici, elle
se ressaisit (interdiction 9). Une charge n'est jamais reportée dans une
sollicitation ; la hauteur utile n'est jamais dérivée.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from eurostruct_engine.ec2.serviceability import ExposureClass
from eurostruct_engine.materials import CONCRETE_GRADES, STEEL_GRADES
from eurostruct_engine.schemas.common import ProvenanceDTO
from eurostruct_engine.schemas.documents import (
    SOURCES_DE_VALEUR,
    ChampPrerempli,
    ConflitDePreremplissage,
    DocumentDepose,
    Extraction,
    NonReportable,
    Preremplissage,
    StructureDuDocument,
    ValeurExtraite,
)
from eurostruct_engine.schemas.ec2_verification import Ec2BeamVerificationRequest
from eurostruct_engine.schemas.structure import ModeleStructurel, ResumeDeStructure
from eurostruct_extraction import (
    CATEGORIES,
    VERSION_EXTRACTEUR,
    DocumentAnalyse,
    ResultatExtraction,
    extract_engineering_data,
    parse_document,
)

from .stockage import (
    OctetsAlteres,
    Stockage,
    chemin_de_piece,
    empreinte,
)

__all__ = [
    "AVIS_PROPOSITIONS",
    "AVIS_STRUCTURE",
    "CHAMPS_REPORTABLES",
    "NATURES",
    "ProvenanceRefusee",
    "analyser",
    "confirm_extraction",
    "create_extraction_records",
    "en_document",
    "en_extraction",
    "en_structure",
    "preremplissage",
    "upload_document",
    "verifier_provenance",
]

#: CE QUE DIT LE MODELE STRUCTUREL, ET CE QU'IL NE DIT PAS.
AVIS_STRUCTURE: Final[str] = (
    "Ce modèle est une LECTURE de la géométrie du dessin : poteaux, poutres, "
    "travées et liaisons reconnus par leurs calques, leurs blocs et leurs "
    "formes. Ses longueurs sont dans l'unité du dessin; une portée y est une "
    "distance entre appuis, pas la portée utile. Aucune valeur n'entre dans "
    "un calcul sans avoir été confirmée depuis la revue."
)

#: LA PHRASE QUI ACCOMPAGNE TOUTE LISTE DE PROPOSITIONS.
AVIS_PROPOSITIONS: Final[str] = (
    "Les valeurs extraites des documents sont des PROPOSITIONS. Aucune n'entre "
    "dans un calcul avant d'avoir été confirmée ou corrigée par une personne "
    "nommée, et le serveur le vérifie au moment du calcul."
)

#: Les natures que ce lot reçoit, et leur libellé. La base refuse les autres.
NATURES: Final[dict[str, str]] = {
    "architect_drawing": "Plan d'architecte",
    "formwork_drawing": "Plan de coffrage",
    "cctp": "Cahier des charges (CCTP)",
    "other": "Autre pièce",
}

STATUTS_ANALYSE: Final[dict[str, str]] = {
    "en_attente": "En attente d'analyse",
    "analyse": "Analysé",
    "partiel": "Partiellement lu",
    "non_lu": "Conservé, non lu",
    "echec": "Lecture en échec",
}

#: LES ROLES QUI DEPOSENT ET DECIDENT — ceux qui lancent un calcul (0028).
#: Ce n'est qu'un precontrole, avant tout octet depose: la base rejoue la
#: question et c'est elle qui decide.
SAISIE: Final[frozenset[str]] = frozenset(
    {"owner", "admin", "engineer", "validating_engineer"})

#: Les facteurs EXACTS vers le millimetre. Rien d'autre n'est converti.
FACTEURS_MM: Final[dict[str, Decimal]] = {
    "mm": Decimal(1), "cm": Decimal(10), "m": Decimal(1000)}

#: LA GEOMETRIE D'ABORD. Quand plusieurs décisions donnent la MEME valeur à un
#: champ, la provenance retenue est celle de la source la plus directe: la
#: mesure sur le dessin, puis le texte du dessin, le texte d'un PDF, une
#: détection visuelle, l'OCR. Des valeurs DIFFERENTES restent un conflit que
#: l'ingénieur tranche — l'ordre ne choisit jamais à sa place.
PRIORITE_DES_SOURCES: Final[tuple[str, ...]] = (
    "geometry", "cad_text", "text", "vision", "ocr")

AVERTISSEMENT_PORTEE: Final[str] = (
    "Une portée lue sur un plan est souvent une portée entre axes ; la portée "
    "utile l_eff (EN 1992-1-1 §5.3.2.2) peut en différer. Vérifiez-la avant "
    "de la reporter."
)


@dataclass(frozen=True)
class ChampReportable:
    chemin: str
    libelle: str
    categories: frozenset[str]
    #: longueur_mm, entier, beton, acier, exposition
    nature: str
    avertissement: str | None = None


#: CHAQUE CHAMP DE L'ETUDE QU'UN DOCUMENT PEUT RENSEIGNER, et les categories
#: qui le peuvent. Les cles sont exactement `PROVENANCE_CHEMINS` du contrat —
#: un test le constate, pour que les deux listes ne divergent jamais.
CHAMPS_REPORTABLES: Final[dict[str, ChampReportable]] = {
    c.chemin: c for c in (
        ChampReportable("geometry.b", "Largeur b", frozenset({"beam_width"}), "longueur_mm"),
        ChampReportable("geometry.h", "Hauteur h", frozenset({"beam_depth"}), "longueur_mm"),
        ChampReportable("geometry.l_eff", "Portée utile l_eff",
                        frozenset({"beam_span"}), "longueur_mm", AVERTISSEMENT_PORTEE),
        ChampReportable("materials.concrete_grade", "Classe de béton",
                        frozenset({"concrete_class"}), "beton"),
        ChampReportable("materials.steel_grade", "Nuance d'acier",
                        frozenset({"steel_grade"}), "acier"),
        ChampReportable("exposure_class", "Classe d'exposition",
                        frozenset({"exposure_class"}), "exposition"),
        ChampReportable("cover", "Enrobage", frozenset({"concrete_cover"}), "longueur_mm"),
        ChampReportable("bars.count", "Nombre de barres", frozenset({"bar_count"}), "entier"),
        ChampReportable("bars.diameter", "Diamètre des barres",
                        frozenset({"bar_diameter"}), "longueur_mm"),
        ChampReportable("links.diameter", "Diamètre des cadres",
                        frozenset({"link_diameter"}), "longueur_mm"),
        ChampReportable("links.spacing", "Espacement des cadres",
                        frozenset({"link_spacing"}), "longueur_mm"),
    )
}

_CHAMP_DE_CATEGORIE: Final[dict[str, ChampReportable]] = {
    categorie: champ for champ in CHAMPS_REPORTABLES.values()
    for categorie in champ.categories}

_EXPOSITIONS: Final[frozenset[str]] = frozenset(e.value for e in ExposureClass)


class NonReportableErreur(ValueError):
    """La valeur décidée ne peut pas renseigner ce champ — et la raison."""


@dataclass(frozen=True)
class ProvenanceRefusee(Exception):
    """Au moins une provenance ne correspond pas à une décision enregistrée."""

    motifs: tuple[tuple[str, str], ...]


# ------------------------------------------------------------------ dépôt
def upload_document(ouvert: Any, jeton: str, projet: dict[str, Any], *,
                    octets: bytes, kind: str, filename: str, format_: str,
                    media_type: str, extension: str,
                    magasin: Stockage) -> tuple[str, bool]:
    """``uploadDocument()``: déposer, relire, vérifier, PUIS inscrire.

    L'ORDRE EST CELUI DES LIVRABLES, ET POUR LA MÊME RAISON: une ligne écrite
    avant le dépôt promettrait une pièce introuvable si l'écriture échouait;
    l'inverse ne laisse au pire qu'un objet que personne ne référence — et le
    rapprochement le nomme.
    """
    sha = empreinte(octets)
    chemin = chemin_de_piece(org_id=projet["organization_id"],
                             project_id=projet["project_id"], sha256=sha,
                             extension=extension)
    magasin.deposer(chemin, octets, media_type)
    relus = magasin.lire(chemin)
    if empreinte(relus) != sha or len(relus) != len(octets):
        raise OctetsAlteres(
            f"les octets relus depuis « {chemin} » ne portent pas l'empreinte "
            "deposee. Aucune ligne n'est enregistree."
        )
    return ouvert.atelier.inscrire_document(
        jeton, project_id=projet["project_id"], kind=kind, filename=filename,
        mime_type=media_type, format=format_, storage_backend=magasin.nom,
        storage_path=chemin, sha256=sha, size_bytes=len(octets))


# ---------------------------------------------------------------- analyse
def analyser(octets: bytes) -> tuple[DocumentAnalyse, ResultatExtraction]:
    """``parseDocument()`` puis ``extractEngineeringData()``.

    Un document non lu (DWG, PDF numérisé sans OCR) ou en échec ne propose
    rien : il n'y a rien à extraire de ce qui n'a pas été lu.
    """
    analyse = parse_document(octets)
    if analyse.statut in ("analyse", "partiel"):
        resultat = extract_engineering_data(analyse)
    else:
        resultat = ResultatExtraction(candidats=(), compte_rendu={})
    return analyse, resultat


def create_extraction_records(ouvert: Any, jeton: str, document_id: str,
                              analyse: DocumentAnalyse,
                              resultat: ResultatExtraction) -> int:
    """``createExtractionRecords()``: UN appel, UNE transaction.

    Toutes les propositions entrent au statut ``proposed`` — la primitive ne
    prend même pas le statut en paramètre.
    """
    compte_rendu = dict(analyse.compte_rendu)
    if resultat.compte_rendu:
        compte_rendu["extraction"] = resultat.compte_rendu
    if resultat.structure is not None:
        # LE MODELE EST FIGE AVEC LES PROPOSITIONS QU'IL A PRODUITES (0028:
        # le compte rendu ne change plus une fois des propositions inscrites).
        compte_rendu["structure"] = resultat.structure
    return ouvert.atelier.enregistrer_analyse(
        jeton, document_id=document_id, status=analyse.statut,
        detail=analyse.detail, page_count=analyse.nombre_de_pages,
        text_layer=analyse.couche_texte, report=compte_rendu,
        extractor_version=VERSION_EXTRACTEUR,
        extractions=[c.en_ligne() for c in resultat.candidats])


def enregistrer_echec(ouvert: Any, jeton: str, document_id: str, motif: str) -> None:
    """Une analyse que la base refuse d'enregistrer devient un ÉCHEC enregistré.

    Sans cela le document resterait « en attente » pour toujours, et l'écran
    ne saurait pas dire pourquoi.
    """
    ouvert.atelier.enregistrer_analyse(
        jeton, document_id=document_id, status="echec",
        detail=f"les propositions n'ont pas pu etre enregistrees: {motif}",
        page_count=None, text_layer=None, report={"error": "enregistrement"},
        extractor_version=VERSION_EXTRACTEUR, extractions=[])


# ------------------------------------------------------------------ revue
def confirm_extraction(ouvert: Any, jeton: str, *, project_id: str,
                       extraction_id: str, decision: str,
                       final_value: ValeurExtraite | None,
                       note: str | None) -> dict[str, Any]:
    """``confirmExtraction()``: confirmer, corriger ou rejeter."""
    return ouvert.atelier.decider_extraction(
        jeton, project_id=project_id, extraction_id=extraction_id,
        decision=decision,
        final_value=final_value.model_dump(mode="json") if final_value else None,
        note=note)


def _structure_de(ligne: dict[str, Any]) -> dict[str, Any] | None:
    rapport = ligne.get("analysis_report")
    structure = rapport.get("structure") if isinstance(rapport, dict) else None
    return structure if isinstance(structure, dict) else None


def en_document(ligne: dict[str, Any]) -> DocumentDepose:
    """Le document, SANS son modèle structurel (il se lit à part) : une liste
    de pièces ne transporte pas le plan de chacune."""
    analysee = (ligne["proposed_count"] + ligne["confirmed_count"]
                + ligne["corrected_count"] + ligne["rejected_count"]) > 0
    structure = _structure_de(ligne)
    rapport = ligne["analysis_report"]
    if structure is not None:
        rapport = {k: v for k, v in rapport.items() if k != "structure"}
    resume = None
    if structure is not None:
        unites = structure.get("units") or {}
        resume = ResumeDeStructure(
            schema_version=str(structure.get("schema")),
            drawing_units=unites.get("drawing"), unit_basis=str(unites.get("basis")),
            counts=dict(structure.get("counts") or {}))
    return DocumentDepose(
        **{k: ligne[k] for k in (
            "document_id", "kind", "filename", "format", "mime_type",
            "size_bytes", "sha256", "page_count", "text_layer",
            "analysis_status", "analysis_detail",
            "extractor_version", "analysed_at", "uploaded_by_me", "created_at",
            "proposed_count", "confirmed_count", "corrected_count",
            "rejected_count")},
        analysis_report=rapport,
        kind_label=NATURES.get(ligne["kind"], ligne["kind"]),
        analysis_status_label=STATUTS_ANALYSE.get(ligne["analysis_status"],
                                                  ligne["analysis_status"]),
        can_reanalyse=not analysee,
        has_structure=structure is not None, structure_summary=resume)


def en_structure(project_id: str, ligne: dict[str, Any]) -> StructureDuDocument | None:
    """Le modèle structurel enregistré avec l'analyse, ou ``None``."""
    structure = _structure_de(ligne)
    if structure is None:
        return None
    return StructureDuDocument(
        project_id=project_id, document_id=ligne["document_id"],
        filename=ligne["filename"], extractor_version=ligne["extractor_version"],
        structure=ModeleStructurel.model_validate(structure),
        notice=AVIS_STRUCTURE)


def _source(methode: str) -> tuple[str, str]:
    return SOURCES_DE_VALEUR.get(methode, ("text", methode))


def en_extraction(ligne: dict[str, Any]) -> Extraction:
    categorie = CATEGORIES.get(ligne["kind"])
    champ = _CHAMP_DE_CATEGORIE.get(ligne["kind"])
    return Extraction(
        extraction_id=ligne["extraction_id"], document_id=ligne["document_id"],
        document_filename=ligne["document_filename"], kind=ligne["kind"],
        kind_label=categorie.libelle if categorie else ligne["kind"],
        proposed_value=ValeurExtraite(**ligne["proposed_value"]),
        final_value=(ValeurExtraite(**ligne["final_value"])
                     if ligne["final_value"] else None),
        status=ligne["status"], page=ligne["page"], bbox=ligne["bbox"],
        position=ligne["position"], confidence=ligne["confidence"],
        method=ligne["method"], model_name=ligne["model_name"],
        raw_text=ligne["raw_text"], element_label=ligne["element_label"],
        basis=ligne["basis"], confirmed_by_name=ligne["confirmed_by_name"],
        confirmed_at=ligne["confirmed_at"], decision_note=ligne["decision_note"],
        created_at=ligne["created_at"],
        form_field=champ.chemin if champ else None,
        form_field_label=champ.libelle if champ else None,
        form_warning=champ.avertissement if champ else None,
        source_type=_source(ligne["method"])[0],  # type: ignore[arg-type]
        source_label=_source(ligne["method"])[1])


# ------------------------------------------------------- report et contrôle
def _decimal(valeur: Any) -> Decimal:
    if isinstance(valeur, bool) or not isinstance(valeur, int | float):
        raise NonReportableErreur("la valeur retenue n'est pas un nombre")
    try:
        return Decimal(str(valeur))
    except InvalidOperation as cause:  # pragma: no cover — str(float) est lisible
        raise NonReportableErreur("la valeur retenue n'est pas un nombre") from cause


def _nombre(valeur: Decimal) -> int | float:
    return int(valeur) if valeur == valeur.to_integral_value() else float(valeur)


def valeur_du_champ(champ: ChampReportable,
                    retenue: dict[str, Any] | None) -> tuple[int | float | str, str | None]:
    """La valeur décidée, dans l'unité du champ — ou :class:`NonReportableErreur`."""
    if not retenue:
        raise NonReportableErreur("aucune valeur n'a ete retenue")
    valeur, unite = retenue.get("value"), retenue.get("unit")
    if champ.nature == "longueur_mm":
        nombre = _decimal(valeur)
        if unite is None:
            raise NonReportableErreur(
                "aucune unite n'est ecrite ni declaree: corrigez la valeur en "
                "precisant son unite avant de la reporter")
        facteur = FACTEURS_MM.get(unite)
        if facteur is None:
            raise NonReportableErreur(
                f"l'unite « {unite} » n'est pas une longueur metrique (mm, cm, m): "
                "saisissez la valeur convertie")
        if nombre <= 0:
            raise NonReportableErreur("une longueur nulle ou negative ne se reporte pas")
        return _nombre(nombre * facteur), "mm"
    if champ.nature == "entier":
        nombre = _decimal(valeur)
        if unite is not None:
            raise NonReportableErreur("un denombrement n'a pas d'unite")
        if nombre != nombre.to_integral_value() or nombre < 1:
            raise NonReportableErreur("un nombre de barres est un entier positif")
        return int(nombre), None
    if not isinstance(valeur, str):
        raise NonReportableErreur("la valeur retenue n'est pas une designation")
    texte = valeur.strip()
    admis = {"beton": CONCRETE_GRADES, "acier": STEEL_GRADES,
             "exposition": _EXPOSITIONS}[champ.nature]
    if texte not in admis:
        raise NonReportableErreur(
            f"« {texte} » n'est pas une valeur que le moteur sait verifier pour "
            f"« {champ.libelle} »")
    return texte, None


def _provenance(ligne: dict[str, Any]) -> ProvenanceDTO:
    """La provenance ÉCRITE PAR LE SERVEUR, depuis la décision enregistrée."""
    texte = ligne["raw_text"]
    texte = texte if len(texte) <= 160 else texte[:157] + "..."
    detail = f"« {texte} » — {ligne['document_filename']}, page {ligne['page']}"
    # LA SOURCE EST DITE quand ce n'est pas le texte d'un PDF: une valeur
    # mesuree sur le dessin ne se relit pas comme une valeur ecrite.
    if ligne.get("method") not in (None, "texte_natif"):
        detail += f" ({_source(ligne['method'])[1].lower()})"
    if ligne.get("element_label"):
        detail += f", repère {ligne['element_label']}"
    # UNE CORRECTION DIT CE QUI AVAIT ETE LU: la note doit permettre de
    # retrouver l'ecart entre le document et la valeur retenue.
    if ligne.get("status") == "corrected":
        lue = ligne.get("proposed_value") or {}
        unite = f" {lue['unit']}" if lue.get("unit") else ""
        detail += f"; valeur corrigée (lue : {lue.get('value')}{unite})"
    return ProvenanceDTO(
        kind="document_extraction", detail=detail,
        document_id=ligne["document_id"], page=ligne["page"],
        bbox=tuple(ligne["bbox"]) if ligne.get("bbox") else None,
        confirmed_by=ligne["confirmed_by_name"],
        confirmed_at=ligne["confirmed_at"],
        extraction_id=ligne["extraction_id"])


def _repere(texte: str | None) -> str | None:
    return re.sub(r"[\s-]", "", texte).upper() if texte else None


def _cle_de_valeur(valeur: int | float | str) -> str:
    return valeur if isinstance(valeur, str) else str(Decimal(str(valeur)).normalize())


def preremplissage(project_id: str, lignes: list[dict[str, Any]],
                   element: str | None) -> Preremplissage:
    """Les valeurs DÉCIDÉES, dans l'unité de chaque champ, avec leur provenance.

    Un champ que deux décisions renseignent différemment n'est pas choisi
    ici : c'est un conflit, que l'ingénieur tranche depuis la revue. Une
    valeur d'un autre repère n'est pas proposée pour celui-ci. Les candidats
    sont rangés selon :data:`PRIORITE_DES_SOURCES` — la géométrie d'abord.
    """
    repere = _repere(element)
    par_chemin: dict[str, list[ChampPrerempli]] = {}
    sources: dict[str, str] = {}
    non_reportables: list[NonReportable] = []
    for ligne in lignes:
        if ligne["status"] not in ("confirmed", "corrected"):
            continue
        champ = _CHAMP_DE_CATEGORIE.get(ligne["kind"])
        if champ is None:
            continue
        sien = _repere(ligne.get("element_label"))
        if repere and sien and sien != repere:
            continue
        categorie = CATEGORIES.get(ligne["kind"])
        try:
            valeur, unite = valeur_du_champ(champ, ligne["final_value"])
        except NonReportableErreur as motif:
            non_reportables.append(NonReportable(
                extraction_id=ligne["extraction_id"], kind=ligne["kind"],
                kind_label=categorie.libelle if categorie else ligne["kind"],
                reason=str(motif)))
            continue
        sources[ligne["extraction_id"]] = _source(ligne.get("method", ""))[0]
        par_chemin.setdefault(champ.chemin, []).append(ChampPrerempli(
            path=champ.chemin, label=champ.libelle, value=valeur, unit=unite,
            extraction_id=ligne["extraction_id"], provenance=_provenance(ligne),
            source_value=ValeurExtraite(**ligne["final_value"]),
            element_label=ligne.get("element_label"),
            warning=champ.avertissement))

    champs: list[ChampPrerempli] = []
    conflits: list[ConflitDePreremplissage] = []
    rang = {source: i for i, source in enumerate(PRIORITE_DES_SOURCES)}
    for chemin, champ in CHAMPS_REPORTABLES.items():
        candidats = sorted(par_chemin.get(chemin, []),
                           key=lambda c: rang.get(sources[c.extraction_id], len(rang)))
        if not candidats:
            continue
        if repere:
            exacts = [c for c in candidats if _repere(c.element_label) == repere]
            candidats = exacts or candidats
        valeurs = {_cle_de_valeur(c.value) for c in candidats}
        if len(valeurs) == 1:
            champs.append(candidats[0])
        else:
            conflits.append(ConflitDePreremplissage(
                path=chemin, label=champ.libelle, candidates=candidats,
                reason=("plusieurs valeurs confirmees renseignent ce champ: "
                        "choisissez celle de l'element etudie depuis la revue")))
    return Preremplissage(project_id=project_id, element=element, fields=champs,
                          conflicts=conflits, not_reportable=non_reportables,
                          notice=AVIS_PROPOSITIONS)


def _valeur_envoyee(corps: Ec2BeamVerificationRequest, chemin: str) -> Any:
    valeur: Any = corps
    for morceau in chemin.split("."):
        valeur = getattr(valeur, morceau)
    return valeur


def _egale(champ: ChampReportable, envoyee: Any, attendue: int | float | str) -> bool:
    """ÉGALITÉ EXACTE, sans tolérance (interdiction 9)."""
    if champ.nature == "longueur_mm":
        facteur = FACTEURS_MM.get(getattr(envoyee, "unit", ""))
        if facteur is None:
            return False
        return Decimal(str(envoyee.value)) * facteur == Decimal(str(attendue))
    if champ.nature == "entier":
        return isinstance(envoyee, int) and envoyee == attendue
    return isinstance(envoyee, str) and envoyee.strip() == attendue


def verifier_provenance(corps: Ec2BeamVerificationRequest,
                        lues: dict[str, dict[str, Any]]) -> dict[str, ProvenanceDTO]:
    """Le contrôle de provenance d'un calcul, AVANT le moteur.

    ``lues`` sont les extractions relues SOUS L'IDENTITÉ DE L'APPELANT dans CE
    projet. Rend la provenance réécrite depuis la base, ou lève
    :class:`ProvenanceRefusee` avec un motif par champ — rien n'est alors ni
    calculé ni enregistré.
    """
    motifs: list[tuple[str, str]] = []
    reecrites: dict[str, ProvenanceDTO] = {}
    for chemin, origine in corps.provenance.items():
        champ = CHAMPS_REPORTABLES[chemin]
        ligne = lues.get(origine.extraction_id or "")
        if ligne is None:
            motifs.append((chemin, (f"l'extraction {origine.extraction_id} est "
                                    "introuvable dans ce projet")))
            continue
        if ligne["status"] not in ("confirmed", "corrected"):
            motifs.append((chemin, (f"l'extraction est « {ligne['status']} »: seule "
                                    "une valeur confirmee ou corrigee entre dans un "
                                    "calcul")))
            continue
        if ligne["kind"] not in champ.categories:
            motifs.append((chemin, (f"une extraction « {ligne['kind']} » ne renseigne "
                                    f"pas « {champ.libelle} »")))
            continue
        try:
            attendue, _ = valeur_du_champ(champ, ligne["final_value"])
        except NonReportableErreur as motif:
            motifs.append((chemin, str(motif)))
            continue
        envoyee = _valeur_envoyee(corps, chemin)
        if not _egale(champ, envoyee, attendue):
            motifs.append((chemin, (
                "la valeur envoyee n'est pas la valeur decidee "
                f"({attendue}{' mm' if champ.nature == 'longueur_mm' else ''}). Une "
                "valeur modifiee apres report redevient une saisie et ne porte "
                "plus de provenance")))
            continue
        reecrites[chemin] = _provenance(ligne)
    if motifs:
        raise ProvenanceRefusee(tuple(motifs))
    return reecrites
