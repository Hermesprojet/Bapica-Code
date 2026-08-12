"""Triage of deposited documents: what is each one, and can it be used?

Before extracting anything, a batch of PDFs has to be sorted. Three questions,
in order, and a document must pass all three:

1. **Is it machine-readable?** A scanned annex has no text layer and needs OCR.
2. **What is it, normatively?** A base Eurocode — even adopted as NF EN or
   registered as NBN EN — carries the Eurocode's *recommended* values. Only a
   National Annex fixes what a country adopted. This is interdiction 2, and it
   is where a filename lies most often: "NBN EN 1991-1-1" and
   "NBN EN 1991-1-1 ANB" are two different documents.
3. **Does it cover a standard the engine needs?** An annex to EN 1991-2 is a
   real annex and still unblocks nothing if the engine's pending parameters all
   belong to EN 1992-1-1.

The classification below is a *proposal*, derived from the document's own front
matter. It is offered to the depositing engineer, who declares the truth — the
same rule as everywhere else in this pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import pdfplumber

from .model import DocumentRole

__all__ = ["TriageResult", "triage_document", "triage_batch", "render_triage",
           "text_is_mis_decoded", "text_is_reversed"]

#: A National Annex names itself. These markers appear in the title block.
_ANNEX_MARKERS = re.compile(
    r"\bANB\b|\bNA\b(?!\w)|annexe\s+nationale|nationale\s+bijlage|"
    r"anexo\s+nacional|nationaler\s+anhang|national\s+annex",
    re.IGNORECASE,
)

#: National regulation outside the Eurocode system. It *can* fix requirements
#: (Belgian Arrete Royal on fire, Spanish Codigo Estructural, German MVV TB),
#: so it must not be lumped in with the base Eurocodes.
_REGULATION_MARKERS = re.compile(
    r"arrete\s+royal|koninklijk\s+besluit|moniteur\s+belge|"
    r"real\s+decreto|codigo\s+estructural|codigo\s+tecnico|\bCTE\b|\bNCSE\b|"
    r"\bMVV\s*TB\b|verwaltungsvorschrift|\bDIN\s*1054\b|\bDTU\b|"
    r"\bNBN\s*S\s*\d|normes?\s+de\s+base",
    re.IGNORECASE,
)

#: Guidance and articles, never a source of an enforceable value.
_SECONDARY_MARKERS = re.compile(
    r"\bCSTC\b|\bWTCB\b|\bJRC\b|\bCSTB\b|magazine|\bnotes?\s+d[eu]\s+information\b",
    re.IGNORECASE,
)

#: A draft or withdrawn edition. CEN prefixes drafts with "pr" (prEN, prNBN),
#: pre-standards with "ENV", and national bodies mirror that (oSIST prEN...).
#: Publishers' preview extracts ("iTeh STANDARD PREVIEW") are the same problem.
#:
#: This must be tested BEFORE the annex markers. A draft National Annex says
#: "annexe nationale" on its cover exactly like a published one, so without
#: this it came back usable_for_ndp with no blocker at all — the single worst
#: outcome this triage exists to prevent, since a draft carries values that
#: have no legal force and may still change.
#: ``DDENV`` has no word boundary before ENV, so ``\bENV\b`` missed it. A
#: DD ENV 1991-2-6 came through an IHS reseller whose banner replaced the
#: publisher's cover: the front matter carried no ENV at all, and the only
#: remaining signal was the filename — where the form is written solid.
_DRAFT_MARKERS = re.compile(
    r"\bpr[-\s]?EN\b|\bpr[-\s]?NBN\b|\bpr[-\s]?NF\b|\boSIST\b|\bENV\b|"
    r"\bDD[-\s]?ENV\b|"
    r"standard\s+preview|projet\s+de\s+norme|ontwerp[-\s]?norm|"
    r"norm[-\s]?entwurf|proyecto\s+de\s+norma|draft\s+standard|"
    r"final\s+draft|enquiry\s+draft",
    re.IGNORECASE,
)

#: A copy licensed to a named subscriber, which the publisher does not keep up
#: to date. BSI stamps its own words on it — "Licensed Copy: ... Uncontrolled
#: Copy, (c) BSI". Deposited as EN 1990, the file was one of these, licensed to
#: a university in 2003 and never revised since.
#:
#: It is not a draft and not a forgery; it is a copy whose publisher explicitly
#: disclaims currency. Confirming a national value from it would cite an
#: edition nobody can vouch is the one in force.
_UNCONTROLLED_COPY = re.compile(
    r"uncontrolled\s+cop(?:y|ies)|licensed\s+cop(?:y|ies)|"
    r"copie\s+non\s+control(?:e|é)e|single\s+user\s+licen[cs]e",
    re.IGNORECASE,
)

#: Teaching and commentary material. Never matched on the title alone: "Basis
#: of structural design" IS the subtitle of EN 1990, and a rule keyed to it
#: would reject the very standard it is meant to protect. These markers name
#: what a standard never contains — an author's email, a lecture handout, a
#: slide deck.
_TEACHING_MATERIAL = re.compile(
    r"for\s+dummies|slides?\s+available|lecture\s+notes?|"
    r"a\s+brief\s+guide|course\s+notes?|@[\w.]+\.ac\.[a-z]{2}|"
    r"designers'?\s+guide|worked\s+examples?\s+for\s+students",
    re.IGNORECASE,
)

#: A standard PUBLISHED and NOT YET IN FORCE. A third state, and the deposit
#: made it necessary: the second generation of Eurocodes is being issued
#: (EN 1990-1:2023, EN 1993-1-8:2024, EN 1993-2:2026) while the first stays
#: applicable. NBN prints the fact in capitals on the cover:
#:
#:     THIS STANDARD IS NOT YET APPLICABLE PENDING THE PUBLICATION OF ITS
#:     ACCOMPANYING NATIONAL ANNEX ... The applicable standard in Belgium
#:     remains the NBN EN 1993-2:2007.
#:
#: This is neither a draft nor a withdrawn edition. It is a real, published,
#: numbered standard that a reader would take for the current one — and it is
#: the most convincing impostor this triage has met, because everything about
#: it is genuine except its force.
_NOT_YET_APPLICABLE = re.compile(
    r"not\s+yet\s+applicable|does\s+not\s+yet\s+have\s+the\s+status|"
    r"pas\s+encore\s+d'?application|n'?est\s+pas\s+encore\s+applicable|"
    r"nog\s+niet\s+van\s+toepassing|second\s+generation\s+eurocodes",
    re.IGNORECASE,
)

#: A published standard names the pre-standard it supersedes, right on its
#: cover: "Remplace ENV 1993-1-2:1995". Matching the citation instead of the
#: document's own designation flagged 13 published Eurocodes as drafts — a
#: guard that rejects the documents we actually hold is worse than no guard.
_SUPERSEDES = re.compile(
    r"(?:remplace|replaces|supersedes|vervangt|ersetzt|sustituye|"
    r"annule\s+et\s+remplace|withdrawn)\s*(?::|)\s*$",
    re.IGNORECASE,
)


#: Download-bait pages that impersonate a standard. A deposited file claiming
#: to be "Eurocode 7 part 2" turned out to be an SEO scraper page: two pages of
#: "DOWNLOAD! DIRECT DOWNLOAD!", doubled glyphs ("EEuurrooccooddee") and
#: injected off-topic phrases. The triage classified it neatly as a base
#: Eurocode covering EN 1997-2 — harmless only because base Eurocodes are
#: refused anyway. The same page carrying "Annexe Nationale" would have come
#: back usable.
_NOT_A_STANDARD_MARKERS = re.compile(
    r"direct\s+download|download\s*!|free\s+pdf\s+download|"
    r"click\s+here\s+to\s+download|torrent",
    re.IGNORECASE,
)

#: How an official publication identifies itself. Every legitimate document in
#: the deposit carries one: an ICS code, a standards-body banner, or — for
#: national regulations — the official gazette it appeared in. A file bearing
#: none of these has no publication identity, and nothing that has no
#: publication identity can fix a normative value.
_PUBLICATION_HALLMARK = re.compile(
    r"\bICS[:\s]|\bcou\s*:|EUROPEAN\s+STANDARD|NORME\s+EUROP|EUROPÄISCHE\s+NORM|"
    r"Norme\s+belge|Belgische\s+norm|MONITEUR\s+BELGE|BELGISCH\s+STAATSBLAD|"
    r"\bNBN\b|\bAFNOR\b|\bDIN\b|\bUNE-?EN\b|\bAENOR\b|\bBOE\b|"
    r"journal\s+officiel|bundesanzeiger|"
    # Indice de classement francais: « P 18-711-1/NA ». C'est l'identifiant
    # officiel AFNOR, et il apparait meme sur les rendus d'editeurs tiers dont
    # la couverture ne porte pas la banniere AFNOR.
    r"indice\s+de\s+classement|\b[A-Z]\s?\d{2}-\d{3}",
    re.IGNORECASE,
)

#: Text that extracts but is systematically mis-decoded. A PDF whose font
#: carries a broken ToUnicode map yields characters from the Latin-1 supplement
#: instead of the real ones: « NF EN 1991-1-4/NA » comes out « ÒÚ ÛÒ ïççïóïóìñÒß ».
#:
#: More dangerous than a scan, because it looks like text. Measured over the
#: deposit: a mis-decoded annex reaches 96 % Latin-1 supplement and 0,2 % ASCII
#: letters, where every sound document sits between 0,5 % and 3,4 % / 14 % and
#: 81 %. The margin is wide enough that a single threshold separates them.
_MOJIBAKE_HIGH_RATIO = 0.5

#: Below this many characters the ratio means nothing — a cover page of three
#: accented words would trip it.
_MOJIBAKE_MIN_CHARS = 200


#: A standard put through machine translation. Deposited once: the French NA
#: to EN 1990 (NF P 06-100-2) arrived as a Google-translated English rendering,
#: stamped "© Machine Translated by Google" on its own cover.
#:
#: This is not the normative text in any language. AFNOR published it in
#: French; a translation engine produced this. Worse, the machine mangles the
#: very things that matter — the deposited file spells its own classification
#: index "P 0 6-100-2" and the standard it annexes "N F EN 1 990", with spaces
#: injected inside identifiers. A decimal comma has every chance of faring no
#: better.
_MACHINE_TRANSLATION_MARKERS = re.compile(
    r"machine\s+translated|traduit\s+automatiquement|"
    r"translated\s+by\s+google|automatische\s+ubersetzung|"
    r"traduccion\s+automatica|machinaal\s+vertaald",
    re.IGNORECASE,
)


def text_is_mis_decoded(text: str) -> bool:
    """Whether *text* is dominated by Latin-1 supplement characters.

    Detects the *shape* of the corruption rather than any particular encoding,
    so it holds whatever the publisher's font did wrong.
    """
    printable = [c for c in text if not c.isspace()]
    if len(printable) < _MOJIBAKE_MIN_CHARS:
        return False
    high = sum(1 for c in printable if 0x80 <= ord(c) <= 0xFF)
    return high / len(printable) > _MOJIBAKE_HIGH_RATIO


#: Words long enough that reading them backwards is not a coincidence, and
#: common enough to appear on any cover page. Kept short deliberately: the test
#: is "does reversing help", not "is this English".
_REVERSAL_PROBES = (
    "licensed", "uncontrolled", "copyright", "standard", "european",
    "eurocode", "national", "annex", "december", "january",
)


def text_is_reversed(text: str) -> bool:
    """Whether *text* reads backwards.

    Found on a deposited EN 1990 whose cover came out as ``desneciL :ypoC``
    and ``dellortnocnU`` — BSI's licence stamp, rendered right-to-left by the
    PDF's font.

    This is the trap that matters most, because it disables every other guard
    at once: a ``prEN`` cover rendered this way reads ``NErp`` and matches no
    draft marker, no publisher banner, no supersession verb. The document then
    looks merely *unidentified* rather than *a draft*, which is a far milder
    verdict than it deserves.

    Decided by comparing how many probe words appear forwards against how many
    appear only when the text is reversed. A document that genuinely mentions
    "desnecil" does not exist; one that scores on the reversal does.
    """
    low = text.lower()
    if len(low) < 200:
        return False
    backwards = low[::-1]
    forwards_hits = sum(1 for w in _REVERSAL_PROBES if w in low)
    reversed_hits = sum(1 for w in _REVERSAL_PROBES if w in backwards)
    return reversed_hits > forwards_hits


def _is_draft(front: str, filename: str) -> bool:
    """Whether the document *is* a draft, not merely whether it mentions one.

    A marker counts only when it designates this document. Anything introduced
    by a supersession verb refers to a superseded edition and is ignored.
    """
    hay = _searchable(front, filename)
    for m in _DRAFT_MARKERS.finditer(hay):
        if not _SUPERSEDES.search(hay[max(0, m.start() - 40) : m.start()]):
            return True
    return False

# Chaque composante de la partie accepte DEUX chiffres. Avec un seul, la
# regex ne pouvait pas atteindre la fin de « EN 1993-1-10 »: faute de
# frontiere de mot apres le premier « 1 » de « 10 », elle refluait sur
# « EN 1993-1 » — une partie qui n'existe pas. Un depot d'EN 1993-1-10 (celui
# auquel l'ANB acier renvoie en §3.2.3(3)) etait donc annonce sous un nom
# faux, puis ecarte comme hors perimetre.
_STANDARD_RE = re.compile(
    r"\bEN\s*(\d{4})(?:\s*[-–]\s*(\d{1,2}(?:\s*[-–]\s*\d{1,2})?))?\b", re.IGNORECASE
)


def _searchable(*parts: str) -> str:
    """Normalise a haystack before matching.

    Underscores are word characters in a regex, so ``\bANB\b`` does not match
    inside ``NBN_EN_1990__ANB``. Filenames use them constantly, and getting
    this wrong classified two genuine National Annexes as base Eurocodes.
    """
    return re.sub(r"[_\-]+", " ", " ".join(parts))


@dataclass(frozen=True, slots=True)
class TriageResult:
    """What a deposited file appears to be, and whether it can be used."""

    path: Path
    doc_id: str
    page_count: int
    text_chars: int
    proposed_role: DocumentRole
    proposed_standard: str | None
    #: Draft, pre-standard or publisher preview. Never usable, regardless of
    #: role: its values have no legal force and may still change.
    is_draft: bool
    #: Download-bait page dressed as a standard. Never usable.
    is_impersonation: bool
    #: Text extracts but is systematically mis-decoded. Never usable.
    is_mis_decoded: bool
    #: Put through a translation engine. Never the normative text.
    is_machine_translated: bool
    #: Carries an ICS code, a standards-body banner or an official gazette.
    #: A document without one cannot say under whose authority it speaks.
    #: True for scans, whose text layer is empty for an unrelated reason.
    has_publication_identity: bool
    front_matter: str
    blockers: tuple[str, ...]
    #: Text layer reads right-to-left. Disables every keyword guard at
    #: once, so it is reported before all of them.
    is_reversed: bool = False
    #: Published, numbered, and declaring itself not yet in force.
    is_not_yet_applicable: bool = False
    #: Publisher's own "Uncontrolled Copy" stamp: not maintained.
    is_uncontrolled_copy: bool = False
    #: Lecture deck, guide or commentary rather than the normative text.
    is_teaching_material: bool = False

    @property
    def machine_readable(self) -> bool:
        return self.text_chars > 0

    @property
    def usable_for_ndp(self) -> bool:
        """Can this document yield a *national* parameter at all?

        Four independent ways to fail, and a document must clear all of them.
        The role check alone is not enough: a draft annex, and an SEO page
        carrying the word "ANB", both classify as NATIONAL_ANNEX.
        """
        return (
            self.machine_readable
            and not self.is_draft
            and not self.is_impersonation
            and not self.is_mis_decoded
            and not self.is_reversed
            and not self.is_not_yet_applicable
            and not self.is_uncontrolled_copy
            and not self.is_teaching_material
            and not self.is_machine_translated
            and self.has_publication_identity
            and self.proposed_role.can_fix_national_parameters
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.path.name,
            "doc_id": self.doc_id,
            "page_count": self.page_count,
            "text_chars": self.text_chars,
            "machine_readable": self.machine_readable,
            "proposed_role": self.proposed_role.value,
            "proposed_standard": self.proposed_standard,
            "is_draft": self.is_draft,
            "is_impersonation": self.is_impersonation,
            "is_mis_decoded": self.is_mis_decoded,
            "is_machine_translated": self.is_machine_translated,
            "has_publication_identity": self.has_publication_identity,
            "usable_for_ndp": self.usable_for_ndp,
            "blockers": list(self.blockers),
        }


#: How a document declares, in its own title block, that it IS the National
#: Annex — as opposed to merely mentioning one. AFNOR prints the indice de
#: classement with the ``/NA`` suffix; the title says "Annexe nationale à la".
#: Neither appears on a guidance note that discusses an annex.
_SELF_DECLARED_ANNEX = re.compile(
    r"annexe\s+nationale\s+(?:a|à)\s+la\b|national\s+annex\s+to\b|"
    r"nationale\s+bijlage\s+bij\b|nationaler\s+anhang\s+zu\b|"
    r"anexo\s+nacional\s+a\b|"
    # Indice de classement portant le suffixe /NA: « P 06-100-1/NA ».
    r"\b[A-Z]\s?\d{2}-\d{3}(?:-\d+)?(?:/[A-Z]\d)?/NA\b",
    re.IGNORECASE,
)


#: How a document states, in its own words, that it IS a standard. A guidance
#: note never carries these: no "Dossier du CSTC" is an homologated standard,
#: and none bears an indice de classement.
_SELF_DECLARED_STANDARD = re.compile(
    r"norme\s+fran(?:c|ç)aise\s+homologu(?:e|é)e|norme\s+europ(?:e|é)enne|"
    r"belgische\s+norm|norme\s+belge|european\s+standard|"
    r"indice\s+de\s+classement",
    re.IGNORECASE,
)


def _classify(front: str, filename: str) -> DocumentRole:
    """Propose a role from the front matter.

    Order matters, and one ordering was wrong. ``_SECONDARY_MARKERS`` used to
    win outright, so a genuine AFNOR National Annex delivered through Reef4 —
    the CSTB's document platform — was classified as CSTB guidance. The
    DISTRIBUTOR's banner sits on page 1 above the publisher's own cover, and it
    was overriding the document's identity.

    That is the worst direction for this particular error: the earlier bugs
    admitted documents that should have been refused, which the downstream
    guards still caught. This one REFUSED a document that is exactly what the
    engine has been waiting for, and no downstream guard recovers from that —
    the file just looks unusable.

    So a document that declares itself the National Annex in its own title
    block keeps that role, whoever delivered the PDF.
    """
    hay = _searchable(front, filename)
    if _SELF_DECLARED_ANNEX.search(hay):
        return DocumentRole.NATIONAL_ANNEX
    # Le meme bandeau Reef4/CSTB coiffait aussi la NF EN 1990 elle-meme, qui
    # porte « Statut: Norme francaise homologuee ». Un document qui se declare
    # norme n'est pas une publication secondaire, quel qu'en soit le diffuseur.
    if _SECONDARY_MARKERS.search(hay) and not _SELF_DECLARED_STANDARD.search(hay):
        return DocumentRole.SECONDARY_PUBLICATION
    if _ANNEX_MARKERS.search(hay):
        return DocumentRole.NATIONAL_ANNEX
    if _REGULATION_MARKERS.search(hay):
        return DocumentRole.NATIONAL_REGULATION
    return DocumentRole.BASE_EUROCODE


def _standard_of(front: str, filename: str) -> str | None:
    """Best guess at which standard the document covers.

    Handles both ``EN 1992-1-1`` and a part-less ``EN 1990``. From a filename
    the separators have already been flattened, so ``EN_199111`` cannot be
    split reliably — that case falls back to the front matter, and failing that
    to ``None`` rather than to a wrong part number.
    """
    for hay in (front, _searchable(filename)):
        m = _STANDARD_RE.search(hay)
        if m:
            if m.group(2):
                part = re.sub(r"\s*[-–]\s*", "-", m.group(2)).strip()
                return f"EN {m.group(1)}-{part}"
            return f"EN {m.group(1)}"
    return None


def triage_document(path: Path, needed_standards: Sequence[str] = ()) -> TriageResult:
    """Classify one deposited file."""
    from .model import SourceDocument

    with pdfplumber.open(str(path)) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    # Unmappable watermark glyphs are not readable text; counting them would
    # make a scanned page look machine-readable.
    text = re.sub(r"\(cid:\d+\)", "", "".join(pages))
    front = " ".join((pages[0] if pages else "").split())[:400]

    role = _classify(front, path.name)
    standard = _standard_of(front, path.name)
    is_draft = _is_draft(front, path.name)
    is_mis_decoded = text_is_mis_decoded(text)
    is_not_yet_applicable = bool(_NOT_YET_APPLICABLE.search(front))
    is_reversed = text_is_reversed(text)
    # Cherche AUSSI a l'envers. Le cas qui a impose ce garde n'avait pas son
    # corps inverse — seul le FILIGRANE l'etait, et c'est lui qui porte la
    # mention disqualifiante. Un document dont le texte se lit normalement peut
    # donc cacher « Uncontrolled Copy » ecrit a rebours sur chaque page.
    _hay = _searchable(front, text[:4000])
    is_uncontrolled = bool(
        _UNCONTROLLED_COPY.search(_hay) or _UNCONTROLLED_COPY.search(_hay[::-1])
    )
    is_teaching = bool(_TEACHING_MATERIAL.search(_searchable(front, path.name)))
    is_machine_translated = bool(_MACHINE_TRANSLATION_MARKERS.search(text[:4000]))
    #: Only judged when there IS a text layer: a scan legitimately shows none.
    looks_official = not text.strip() or bool(_PUBLICATION_HALLMARK.search(front))

    is_impersonation = bool(
        _NOT_A_STANDARD_MARKERS.search(_searchable(front, path.name))
    )

    blockers: list[str] = []
    if is_not_yet_applicable:
        blockers.append(
            "PUBLIEE MAIS PAS ENCORE APPLICABLE: le document declare lui-meme "
            "qu'il n'est pas en vigueur, en attente de son annexe nationale et "
            "de la strategie de publication des Eurocodes de 2e generation. "
            "C'est le cas le plus trompeur rencontre: tout y est authentique "
            "— editeur, numero, mise en page — SAUF la force reglementaire. "
            "La norme applicable reste celle de 1re generation, que le "
            "document nomme d'ailleurs. Ne rien en extraire tant qu'elle n'est "
            "pas entree en vigueur."
        )
    if is_reversed:
        blockers.append(
            "TEXTE RENDU A L'ENVERS: la couche de texte se lit de droite a "
            "gauche (« desneciL :ypoC » pour « Licensed Copy »). C'est le pire "
            "cas, parce qu'il DESACTIVE TOUS LES AUTRES CONTROLES a la fois: "
            "une couverture « prEN » ressort « NErp » et ne declenche aucun "
            "marqueur de projet, aucune banniere d'editeur. Le document parait "
            "alors seulement non identifie, verdict bien plus doux qu'il ne le "
            "merite. Ne rien extraire de ce rendu."
        )
    if is_uncontrolled:
        blockers.append(
            "COPIE SOUS LICENCE NON MAINTENUE: le document porte la mention "
            "de l'editeur lui-meme (« Uncontrolled Copy », « Licensed Copy »). "
            "Ce n'est ni un projet ni un faux — c'est un exemplaire dont "
            "l'editeur declare qu'il ne le tient pas a jour. Confirmer une "
            "valeur nationale a partir de la reviendrait a citer une edition "
            "dont personne ne garantit qu'elle est celle en vigueur."
        )
    if is_teaching:
        blockers.append(
            "SUPPORT PEDAGOGIQUE OU COMMENTAIRE: diaporama de cours, guide ou "
            "recueil d'exemples, pas le texte normatif. Reconnu sur ce qu'une "
            "norme ne contient jamais — une adresse de courriel d'auteur, "
            "« slides available on the web ». Le titre seul ne suffirait pas: "
            "« Basis of structural design » EST le sous-titre de l'EN 1990."
        )
    if is_machine_translated:
        blockers.append(
            "TRADUCTION AUTOMATIQUE: ce document porte la marque d'un moteur "
            "de traduction. Ce n'est le texte normatif dans AUCUNE langue — "
            "l'organisme l'a publie dans la sienne, une machine a produit "
            "celui-ci. Elle abime justement ce qui compte: le fichier depose "
            "ecrit son propre indice « P 0 6-100-2 » et « N F EN 1 990 », avec "
            "des espaces inseres dans les identifiants. Obtenir la version "
            "publiee par l'organisme."
        )
    if is_mis_decoded:
        blockers.append(
            "TEXTE MAL DECODE: la police du PDF ne porte pas de table de "
            "correspondance Unicode valide, et l'extraction rend des "
            "caracteres faux (« NF EN 1991-1-4/NA » ressort « ÒÚ ÛÒ "
            "ïççïóïóìñÒß »). Plus dangereux qu'un scan, parce que ca ressemble "
            "a du texte. Obtenir une autre version du fichier; une ROC sur un "
            "rendu image donnerait un meilleur resultat que cette couche."
        )
    if is_impersonation:
        blockers.append(
            "CE N'EST PAS UNE NORME: la page porte des marqueurs de "
            "telechargement publicitaire. Un document normatif ne se presente "
            "jamais ainsi. Ne rien en extraire, quel que soit le titre annonce."
        )
    if not looks_official:
        blockers.append(
            "aucune identite de publication (ni code ICS, ni banniere "
            "d'organisme de normalisation, ni journal officiel): impossible "
            "d'etablir qui publie ce document ni sous quelle autorite"
        )
    if is_draft:
        blockers.append(
            "PROJET ou pre-norme (prEN / prNBN / ENV / apercu d'editeur): ce "
            "document n'a aucune force reglementaire et ses valeurs peuvent "
            "encore changer. Il ne peut fixer aucun parametre national, meme "
            "s'il porte « annexe nationale » sur sa couverture."
        )
    if not text.strip():
        blockers.append(
            "aucune couche de texte: document numerise, une ROC est necessaire "
            "avant tout depouillement automatique"
        )
    if role is DocumentRole.BASE_EUROCODE:
        blockers.append(
            "Eurocode de base (meme homologue NF ou enregistre NBN): il porte "
            "les valeurs RECOMMANDEES, pas les valeurs nationales. Il ne peut "
            "pas fixer un NDP"
        )
    if role is DocumentRole.SECONDARY_PUBLICATION:
        blockers.append(
            "publication secondaire (article, guide): utile au relecteur, "
            "jamais source d'une valeur opposable"
        )
    if needed_standards and standard and standard not in needed_standards:
        blockers.append(
            f"porte sur {standard}, hors des normes dont le moteur a besoin "
            f"({', '.join(needed_standards)})"
        )

    return TriageResult(
        path=path,
        doc_id=SourceDocument.digest(path),
        page_count=len(pages),
        text_chars=len(text),
        proposed_role=role,
        proposed_standard=standard,
        is_draft=is_draft,
        is_impersonation=is_impersonation,
        is_mis_decoded=is_mis_decoded,
        is_reversed=is_reversed,
        is_not_yet_applicable=is_not_yet_applicable,
        is_uncontrolled_copy=is_uncontrolled,
        is_teaching_material=is_teaching,
        is_machine_translated=is_machine_translated,
        has_publication_identity=looks_official,
        front_matter=front,
        blockers=tuple(blockers),
    )


def triage_batch(
    paths: Iterable[Path], needed_standards: Sequence[str] = ()
) -> list[TriageResult]:
    return sorted(
        (triage_document(p, needed_standards) for p in paths),
        key=lambda r: (not r.usable_for_ndp, r.path.name),
    )


def _already_held() -> dict[str, str]:
    """sha256 -> reference, for documents the catalogue already records.

    Deposits repeat. The same three EN 1994 annexes arrived three times over,
    byte for byte, because nothing in the triage said "you already have this".
    Re-sending a file costs the depositor real effort and buys nothing.
    """
    from .catalogue import load_catalogue

    held: dict[str, str] = {}
    for e in load_catalogue():
        if not e.acquired:
            continue
        if e.doc_id_sha256:
            held[e.doc_id_sha256] = e.reference
        for sha in e.alternate_copy_hashes:
            held[sha] = f"{e.reference} (copie alternative deja enregistree)"
    return held


def render_triage(results: Sequence[TriageResult]) -> str:
    usable = [r for r in results if r.usable_for_ndp]
    scanned = [r for r in results if not r.machine_readable]
    held = _already_held()
    repeats = [r for r in results if r.doc_id in held]

    lines = [
        "=== Triage des documents deposes ===",
        f"{len(results)} document(s): {len(usable)} exploitable(s) pour un "
        f"parametre national, {len(scanned)} numerise(s).",
        "",
    ]
    for r in results:
        mark = "OK    " if r.usable_for_ndp else "REJET "
        std = r.proposed_standard or "norme non identifiee"
        seen = "  [DEJA EN MAIN]" if r.doc_id in held else ""
        lines.append(
            f"[{mark}] {r.path.name[:44]:<46} {r.page_count:>3}p  "
            f"{r.proposed_role.value:<22} {std}{seen}"
        )
        for b in r.blockers:
            lines.append(f"           - {b}")
    lines.append("")

    # Plusieurs fichiers DISTINCTS pour une meme norme: editions concurrentes,
    # ou versions linguistiques. Le triage ne tranche pas — il ne peut pas lire
    # une date d'edition sans la deviner — mais il refuse de laisser le choix
    # se faire par hasard. C'est ainsi que la 1e ed. 2007 de l'ANB EN 1990 a
    # ete enregistree alors que la 2e ed. 2013, qui la remplace explicitement,
    # se trouvait dans le meme depot.
    rival: dict[str, list[TriageResult]] = {}
    for r in results:
        if r.proposed_role is DocumentRole.NATIONAL_ANNEX and r.proposed_standard:
            rival.setdefault(r.proposed_standard, []).append(r)
    contested = {
        std: rs for std, rs in rival.items() if len({x.doc_id for x in rs}) > 1
    }
    if contested:
        lines.append(
            f"{len(contested)} norme(s) avec PLUSIEURS FICHIERS DISTINCTS — "
            "verifier laquelle est l'edition en vigueur:"
        )
        for std, rs in sorted(contested.items()):
            lines.append(f"    {std}:")
            for r in sorted(rs, key=lambda x: x.path.name):
                lines.append(
                    f"      - {r.path.name} ({r.page_count}p, "
                    f"{r.text_chars} car.)"
                )
        lines.append(
            "    Editions concurrentes ou versions linguistiques: la date "
            "d'edition se lit sur la page de garde et se DECLARE. Une edition "
            "remplacee ne doit pas servir a un projet courant."
        )
        lines.append("")

    if repeats:
        lines.append(
            f"{len(repeats)} document(s) DEJA EN MAIN — meme empreinte qu'un "
            "fichier deja enregistre:"
        )
        for r in repeats:
            lines.append(f"    - {r.path.name} = {held[r.doc_id]}")
        lines.append(
            "    Les redeposer ne change rien. Si l'un est bloque sur une ROC, "
            "c'est une version AVEC couche de texte qu'il faut, pas le meme "
            "fichier a nouveau."
        )
        lines.append("")

    if scanned:
        lines.append(
            f"{len(scanned)} document(s) numerise(s) — a passer par une ROC "
            "avant depouillement:"
        )
        for r in scanned:
            lines.append(f"    - {r.path.name} ({r.page_count} pages)")
        lines.append("")

    if usable:
        lines.append("Annexes Nationales exploitables en l'etat:")
        for r in usable:
            lines.append(
                f"    - {r.path.name} — {r.proposed_standard or '?'} "
                f"({r.text_chars} caracteres)"
            )
    else:
        lines.append(
            "AUCUN de ces documents ne peut fixer un parametre national en "
            "l'etat. Le mode strict reste bloque."
        )
    lines.append("")
    lines.append(
        "Le role propose ci-dessus est une LECTURE de la page de garde. "
        "L'ingenieur qui depose declare le role reel: un nom de fichier "
        "portant « NBN » ne fait pas d'un document une ANB."
    )
    return "\n".join(lines)
