"""La note de calcul d'une vérification COMPLÈTE — cinq chapitres.

CE QUE CE MODULE EST, ET CE QU'IL N'EST PAS
---------------------------------------------
Il compose la note d'une étude à cinq sections **depuis la ligne enregistrée**.
Il ne relance aucun module, ne recalcule aucun taux, et n'écrit aucun nombre
qu'un journal ne porte pas.

Il ne remplace PAS ``note.py``. La note de flexion simple garde son contrat et
ses octets : un client qui ne vérifie qu'une flexion n'a pas à recevoir cinq
chapitres dont quatre seraient vides. Les deux modules partagent le style, les
échappements et le format des grandeurs — pas leur structure.

POURQUOI LE RENDU NE CALCULE RIEN, JAMAIS
-------------------------------------------
Interdiction n° 1 : aucun résultat de calcul ne vient d'ailleurs que du moteur.
Un renderer qui recalculerait un taux de travail créerait une **seconde vérité**
— non éprouvée, non journalisée — et c'est celle-là que le lecteur croirait,
puisqu'elle est imprimée. Chaque valeur affichée ici est donc lue dans
``results.payload`` ou dans un journal gelé.

LE VOCABULAIRE DES QUATRE ÉTATS EST NORMATIF
----------------------------------------------
``passed``
    Vérifié.
``failed``
    NON VÉRIFIÉ — avec son taux et son remède.
``additional_analysis_required``
    La vérification a **tourné**, et sa conclusion est qu'une autre analyse
    reste due. Le seul cas est la dispense de flèche non acquise. Ce n'est
    **pas** une non-conformité, et l'écrire en rouge ferait refuser des poutres
    correctes. Elle est donc signalée à part, en orange.
``not_evaluated``
    N'a pas pu tourner. La note dit **pourquoi** et n'invente aucun résultat.

DÉTERMINISME
--------------
Aucune horloge. Le PDF ne porte aucune date de génération, si bien que deux
compositions du même dossier rendent les mêmes octets — ce que l'adressage par
contenu exige.
"""

from __future__ import annotations

from typing import Any

from .note import _STYLE, _e, _lignes, _quantite
from .pdf import Bloc, Champs, Paragraphe, Tableau, Titre, composer_pdf

__all__ = [
    "ETATS_LISIBLES",
    "MENTION_ANALYSE_REQUISE",
    "rendre_note_verification",
    "rendre_note_verification_pdf",
]

#: Ce que chaque état s'appelle sur la page. Les quatre sont distincts, et
#: aucun ne se laisse lire comme un autre.
ETATS_LISIBLES: dict[str, str] = {
    "passed": "Conforme",
    "failed": "NON CONFORME",
    "additional_analysis_required": "Analyse complémentaire requise",
    "not_evaluated": "Non évalué",
}

#: La classe CSS de chaque état. L'orange n'est ni le vert ni le rouge, et
#: c'est tout l'intérêt: une dispense non acquise n'est pas un échec.
_CLASSES: dict[str, str] = {
    "passed": "ok",
    "failed": "ko",
    "additional_analysis_required": "attente",
    "not_evaluated": "silence",
}

MENTION_ANALYSE_REQUISE = (
    "Dispense non acquise — calcul explicite de la flèche requis. "
    "Cela ne constitue pas, à lui seul, un échec de la poutre."
)

_VERDICTS = {
    "passed": "LES CINQ VÉRIFICATIONS SONT SATISFAITES",
    "failed": "UNE VÉRIFICATION AU MOINS N'EST PAS SATISFAITE",
    "incomplete": "L'ÉTUDE EST INCOMPLÈTE — une vérification n'a pas conclu",
}

_STYLE_EXTRA = """
.attente { color: #8a5a00; font-weight: 600; }
.silence { color: #555; font-style: italic; }
.ok { color: #14532d; }
.ko { color: #7f1d1d; font-weight: 700; }
.chapitre { border-top: 2px solid #333; margin-top: 1.6em; }
"""


def _etude_de(calcul: dict[str, Any]) -> dict[str, Any]:
    """L'étude telle qu'elle a été écrite. Aucune reconstruction."""
    return ((calcul.get("result") or {}).get("result") or {})


def _journaux_de(calcul: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Les cinq journaux, indexés par clé de section."""
    brut = (calcul.get("journal") or {}).get("sections") or []
    return {j.get("key"): (j.get("journal") or {}) for j in brut if j.get("key")}


def est_note_de_verification(calcul: dict[str, Any]) -> bool:
    """Cette ligne porte-t-elle une étude à cinq sections ?

    Le test est la PRÉSENCE des sections, pas un drapeau posé à côté: un
    drapeau peut mentir sur ce que la ligne contient, la structure non.
    """
    return bool(_etude_de(calcul).get("sections"))


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def rendre_note_verification(projet: dict[str, Any], calcul: dict[str, Any],
                             notice: str, mention: str | None) -> str:
    """La note complète, autonome, à partir du projet et du calcul relus."""
    etude = _etude_de(calcul)
    journaux = _journaux_de(calcul)
    entrees = etude.get("inputs") or {}
    ndp = calcul.get("ndp_snapshot") or {}
    sections = etude.get("sections") or []

    titre = (f"Note de calcul — {projet.get('name', '')} — "
             f"{etude.get('element', '')}")

    parties: list[str] = [
        "<!-- Document autonome: aucun script, aucune ressource externe. -->",
        f"<title>{_e(titre)}</title>",
        f"<style>{_STYLE}{_STYLE_EXTRA}</style>",
        "<main>",
        f"<h1>{_e(titre)}</h1>",
        ('<p class="sous-titre">Vérification complète d\'une poutre en béton '
         'armé — flexion, effort tranchant, ancrages, états limites de '
         'service et limitation des flèches. EN 1992-1-1 et son Annexe '
         'Nationale.</p>'),
    ]

    # LE FILIGRANE EN TETE. Un lecteur qui parcourt la premiere page doit
    # savoir avant de lire les nombres qu'ils ne sont pas signables.
    if mention:
        parties.append(f'<p class="mention">{_e(mention)}</p>')

    # --- 1. LE DOSSIER ----------------------------------------------------
    parties += [
        "<h2>Dossier</h2>", '<dl class="champs">',
        _lignes([
            ("Organisation", _e(projet.get("organization_name"))),
            ("Projet", _e(projet.get("name"))),
            ("Référence", _e(projet.get("reference"))),
            ("Élément", _e(etude.get("element"))),
            ("Calcul", f"<code>{_e(calcul.get('calculation_id'))}</code>"),
        ]),
        "</dl>",
    ]

    # --- 2. LA SYNTHESE, AVANT LE DETAIL ----------------------------------
    #
    # Un ingenieur qui ouvre la note veut d'abord savoir ou il en est. Le
    # detail vient ensuite, chapitre par chapitre.
    parties += [
        "<h2>Synthèse</h2>",
        ('<table><thead><tr><th>Chapitre</th><th>État</th>'
         '<th class="nombre">Utilisation</th></tr></thead><tbody>'),
    ]
    for s in sections:
        etat = s.get("status", "")
        taux = s.get("utilisation")
        parties.append(
            f'<tr><td>{_e(s.get("title"))}</td>'
            f'<td class="{_CLASSES.get(etat, "silence")}">'
            f'{_e(ETATS_LISIBLES.get(etat, etat))}</td>'
            f'<td class="nombre">'
            f'{"—" if taux is None else f"{taux:.3f}"}</td></tr>')
    parties.append("</tbody></table>")

    statut = etude.get("status", "")
    classe = "ok" if statut == "passed" else (
        "ko" if statut == "failed" else "attente")
    parties.append(
        f'<p class="{classe}"><strong>Verdict global&nbsp;: '
        f'{_e(_VERDICTS.get(statut, statut))}.</strong></p>')

    if etude.get("requires_additional_analysis"):
        parties.append(
            f'<p class="attente">{_e(MENTION_ANALYSE_REQUISE)}</p>')

    # --- 3. LES ENTREES ---------------------------------------------------
    geo = entrees.get("geometry") or {}
    barres = entrees.get("bars") or {}
    cadres = entrees.get("links") or {}
    parties += [
        "<h2>Hypothèses et données d'entrée</h2>", '<dl class="champs">',
        _lignes([
            ("Largeur b", _e(geo.get("b"))),
            ("Hauteur h", _e(geo.get("h"))),
            ("Hauteur utile d", _e(geo.get("d"))),
            ("Portée utile l<sub>eff</sub>", _e(geo.get("l_eff"))),
            ("Béton", _e(entrees.get("concrete_grade"))),
            ("Acier", _e(entrees.get("steel_grade"))),
            ("Moment M<sub>Ed</sub>", _e(entrees.get("M_Ed"))),
            ("Effort tranchant V<sub>Ed</sub>", _e(entrees.get("V_Ed"))),
            ("Moment M<sub>car</sub>", _e(entrees.get("M_char"))),
            ("Moment M<sub>qp</sub>", _e(entrees.get("M_qp"))),
            ("Coefficient de fluage φ", _e(entrees.get("phi_creep"))),
            ("Classe d'exposition", _e(entrees.get("exposure_class"))),
            ("Système structural", _e(entrees.get("system"))),
            ("Barres longitudinales",
             f'{_e(barres.get("count"))} × {_e(barres.get("diameter"))}'),
            ("Cadres",
             (f'{_e(cadres.get("legs"))} branches × '
              f'{_e(cadres.get("diameter"))}, '
              f'e = {_e(cadres.get("spacing"))}')),
            ("cot θ retenu", _e(entrees.get("cot_theta"))),
            ("Enrobage", _e(entrees.get("cover"))),
            ("Longueur d'ancrage disponible",
             _e(entrees.get("anchorage_available"))),
            ("Entraxe des barres (dérivé du modèle)",
             _e(etude.get("bar_spacing"))),
            ("Mode strict",
             "oui" if etude.get("strict_ndp") else "non (exploratoire)"),
        ]),
        "</dl>",
    ]

    # --- 4. LES CINQ CHAPITRES -------------------------------------------
    for index, s in enumerate(sections, start=1):
        parties += _chapitre_html(index, s, journaux.get(s.get("key")) or {})

    # --- 5. LE REFERENTIEL APPLIQUE ---------------------------------------
    parties += [
        "<h2>Référentiel national appliqué</h2>", '<dl class="champs">',
        _lignes([
            ("Pays", _e(ndp.get("country") or etude.get("country"))),
            ("Région", _e(ndp.get("region") or etude.get("region"))),
            ("Date de référence",
             _e(ndp.get("as_of") or etude.get("ndp_as_of"))),
            ("Mode strict", "oui" if ndp.get("strict") else "non"),
            ("Préflight satisfait",
             "oui" if etude.get("preflight_ready") else "non"),
        ]),
        "</dl>",
    ]
    annexes = ndp.get("annexes") or []
    if annexes:
        parties += [
            ("<table><thead><tr><th>Annexe</th><th>Édition</th>"
             "</tr></thead><tbody>")]
        for a in annexes:
            parties.append(f'<tr><td>{_e(a.get("reference"))}</td>'
                           f'<td>{_e(a.get("edition"))}</td></tr>')
        parties.append("</tbody></table>")

    non_releves = ndp.get("unverified") or []
    if non_releves:
        parties += [
            "<h3>Paramètres nationaux non relevés</h3>",
            ("<p>Ces valeurs n'ont pas été relevées dans l'Annexe Nationale "
             "publiée. Une note qui les emploie ne peut pas être émise en "
             "l'état.</p>"),
            "<ul>"] + [f"<li><code>{_e(k)}</code></li>" for k in non_releves] + [
            "</ul>"]

    # --- 6. TRACABILITE ---------------------------------------------------
    parties += [
        "<h2>Traçabilité</h2>", '<dl class="champs">',
        _lignes([
            ("Version du moteur", _e(etude.get("engine_version"))),
            ("Build du moteur", _e(calcul.get("engine_build_sha"))),
            # L'IDENTITE VIENT DE LA BASE, pas du payload: c'est la colonne qui
            # fait foi, et une note qui citerait l'autre ne se rattacherait a
            # aucune ligne.
            ("Identité d'exécution",
             f'<code>{_e(calcul.get("execution_identity"))}</code>'),
            ("Empreinte des entrées techniques",
             f'<code>{_e(etude.get("engineering_inputs_hash"))}</code>'),
            ("Empreinte du référentiel",
             f'<code>{_e(etude.get("ndp_snapshot_id"))}</code>'),
            ("Empreinte de l'étude complète",
             f'<code>{_e(etude.get("calculation_fingerprint"))}</code>'),
        ]),
        "</dl>",
    ]

    # --- 7. PORTEE ET LIMITES ---------------------------------------------
    parties += [
        "<h2>Portée et limites du domaine</h2>",
        ("<p>Cette note couvre une poutre de section rectangulaire en béton "
         "armé, sous les cinq vérifications énumérées et sous elles seules. "
         "Elle ne traite ni la torsion, ni le poinçonnement, ni le flambement, "
         "ni les situations accidentelles ou sismiques.</p>"),
        f'<p class="notice">{_e(notice)}</p>',
    ]
    if mention:
        parties.append(f'<p class="mention">{_e(mention)}</p>')
    parties.append("</main>")
    return "\n".join(parties)


def _chapitre_html(index: int, section: dict[str, Any],
                   journal: dict[str, Any]) -> list[str]:
    """Un chapitre: son verdict, son journal, et rien d'autre."""
    etat = section.get("status", "")
    taux = section.get("utilisation")
    parties = [
        f'<h2 class="chapitre">{index}. {_e(section.get("title"))}</h2>',
        f'<p>Base normative&nbsp;: {_e(section.get("basis"))}</p>',
        f'<p class="{_CLASSES.get(etat, "silence")}"><strong>'
        f'{_e(ETATS_LISIBLES.get(etat, etat))}'
        + ("" if taux is None else f" — utilisation {taux:.3f}")
        + "</strong></p>",
    ]

    # UNE SECTION NON EVALUEE DIT POURQUOI, ET N'INVENTE AUCUN RESULTAT.
    if etat == "not_evaluated":
        parties.append(
            "<p class=\"silence\">Cette vérification n'a pas pu être "
            f"exécutée&nbsp;: {_e(section.get('reason'))}. Aucun résultat "
            "n'est produit, et l'absence de résultat ne vaut pas "
            "conformité.</p>")
        return parties

    if etat == "additional_analysis_required":
        parties.append(f'<p class="attente">{_e(section.get("remedy"))}</p>')
    elif etat == "failed" and section.get("remedy"):
        parties.append(f'<p class="ko">Action&nbsp;: '
                       f'{_e(section.get("remedy"))}</p>')

    etapes = journal.get("steps") or []
    if etapes:
        parties += [
            ("<table><thead><tr><th>Symbole</th><th>Description</th>"
             "<th>Application numérique</th><th class=\"nombre\">Valeur</th>"
             "<th>Clause</th></tr></thead><tbody>"),
        ]
        for e in etapes:
            clause = e.get("clause") or {}
            cite = clause.get("cite") if isinstance(clause, dict) else clause
            parties.append(
                f"<tr><td><code>{_e(e.get('symbol'))}</code></td>"
                f"<td>{_e(e.get('description'))}</td>"
                f"<td><code>{_e(e.get('numeric'))}</code></td>"
                f"<td class=\"nombre\">{_e(e.get('formatted'))}</td>"
                f"<td>{_e(cite)}</td></tr>")
        parties.append("</tbody></table>")
        clauses = journal.get("clauses") or []
        if clauses:
            parties.append("<p>Clauses citées&nbsp;: "
                           + ", ".join(_e(c) for c in clauses) + "</p>")
    return parties


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def _p(valeur: Any) -> str:
    if valeur is None:
        return "—"
    texte = str(valeur).strip()
    return texte or "—"


def rendre_note_verification_pdf(projet: dict[str, Any],
                                 calcul: dict[str, Any],
                                 notice: str, mention: str | None) -> bytes:
    """La note complète en PDF. **Aucune date, donc des octets stables.**"""
    etude = _etude_de(calcul)
    journaux = _journaux_de(calcul)
    entrees = etude.get("inputs") or {}
    ndp = calcul.get("ndp_snapshot") or {}
    sections = etude.get("sections") or []

    titre = (f"Note de calcul — {projet.get('name', '')} — "
             f"{etude.get('element', '')}")

    blocs: list[Bloc] = [Titre(titre, 1)]
    if mention:
        blocs.append(Paragraphe(mention, gras=True, encadre=True))

    blocs += [
        Titre("Dossier"),
        Champs([
            ("Organisation", _p(projet.get("organization_name"))),
            ("Projet", _p(projet.get("name"))),
            ("Référence", _p(projet.get("reference"))),
            ("Élément", _p(etude.get("element"))),
            ("Calcul", _p(calcul.get("calculation_id"))),
        ]),
        Titre("Synthèse"),
        Tableau(
            ["Chapitre", "État", "Utilisation"],
            [[_p(s.get("title")),
              _p(ETATS_LISIBLES.get(s.get("status"), s.get("status"))),
              "—" if s.get("utilisation") is None
              else f"{s['utilisation']:.3f}"]
             for s in sections],
            droite={2}),
        Paragraphe(
            "Verdict global : "
            + _VERDICTS.get(etude.get("status", ""), _p(etude.get("status"))),
            gras=True),
    ]
    if etude.get("requires_additional_analysis"):
        blocs.append(Paragraphe(MENTION_ANALYSE_REQUISE, encadre=True))

    geo = entrees.get("geometry") or {}
    barres = entrees.get("bars") or {}
    cadres = entrees.get("links") or {}
    blocs += [
        Titre("Hypothèses et données d'entrée"),
        Champs([
            ("Largeur b", _p(geo.get("b"))),
            ("Hauteur h", _p(geo.get("h"))),
            ("Hauteur utile d", _p(geo.get("d"))),
            ("Portée utile", _p(geo.get("l_eff"))),
            ("Béton", _p(entrees.get("concrete_grade"))),
            ("Acier", _p(entrees.get("steel_grade"))),
            ("M_Ed", _p(entrees.get("M_Ed"))),
            ("V_Ed", _p(entrees.get("V_Ed"))),
            ("M_car", _p(entrees.get("M_char"))),
            ("M_qp", _p(entrees.get("M_qp"))),
            ("Coefficient de fluage", _p(entrees.get("phi_creep"))),
            ("Classe d'exposition", _p(entrees.get("exposure_class"))),
            ("Système structural", _p(entrees.get("system"))),
            ("Barres longitudinales",
             f'{_p(barres.get("count"))} x {_p(barres.get("diameter"))}'),
            ("Cadres",
             (f'{_p(cadres.get("legs"))} branches x '
              f'{_p(cadres.get("diameter"))}, '
              f'e = {_p(cadres.get("spacing"))}')),
            ("cot theta retenu", _p(entrees.get("cot_theta"))),
            ("Enrobage", _p(entrees.get("cover"))),
            ("Ancrage disponible", _p(entrees.get("anchorage_available"))),
            ("Entraxe (dérivé du modèle)", _p(etude.get("bar_spacing"))),
            ("Mode strict",
             "oui" if etude.get("strict_ndp") else "non (exploratoire)"),
        ]),
    ]

    for index, s in enumerate(sections, start=1):
        blocs += _chapitre_pdf(index, s, journaux.get(s.get("key")) or {})

    blocs += [
        Titre("Référentiel national appliqué"),
        Champs([
            ("Pays", _p(ndp.get("country") or etude.get("country"))),
            ("Région", _p(ndp.get("region") or etude.get("region"))),
            ("Date de référence",
             _p(ndp.get("as_of") or etude.get("ndp_as_of"))),
            ("Mode strict", "oui" if ndp.get("strict") else "non"),
            ("Préflight satisfait",
             "oui" if etude.get("preflight_ready") else "non"),
        ]),
    ]
    annexes = ndp.get("annexes") or []
    if annexes:
        blocs.append(Tableau(
            ["Annexe", "Édition"],
            [[_p(a.get("reference")), _p(a.get("edition"))] for a in annexes]))
    non_releves = ndp.get("unverified") or []
    if non_releves:
        blocs += [
            Titre("Paramètres nationaux non relevés"),
            Paragraphe("Ces valeurs n'ont pas été relevées dans l'Annexe "
                       "Nationale publiée. Une note qui les emploie ne peut "
                       "pas être émise en l'état."),
            Paragraphe(", ".join(_p(k) for k in non_releves)),
        ]

    blocs += [
        Titre("Traçabilité"),
        Champs([
            ("Version du moteur", _p(etude.get("engine_version"))),
            ("Build du moteur", _p(calcul.get("engine_build_sha"))),
            ("Identité d'exécution", _p(calcul.get("execution_identity"))),
            ("Empreinte des entrées techniques",
             _p(etude.get("engineering_inputs_hash"))),
            ("Empreinte du référentiel", _p(etude.get("ndp_snapshot_id"))),
            ("Empreinte de l'étude complète",
             _p(etude.get("calculation_fingerprint"))),
        ]),
        Titre("Portée et limites du domaine"),
        Paragraphe(
            "Cette note couvre une poutre de section rectangulaire en béton "
            "armé, sous les cinq vérifications énumérées et sous elles "
            "seules. Elle ne traite ni la torsion, ni le poinçonnement, ni le "
            "flambement, ni les situations accidentelles ou sismiques."),
        Paragraphe(notice, gras=True),
    ]
    if mention:
        blocs.append(Paragraphe(mention, gras=True, encadre=True))

    return composer_pdf(titre, blocs)


def _chapitre_pdf(index: int, section: dict[str, Any],
                  journal: dict[str, Any]) -> list[Bloc]:
    etat = section.get("status", "")
    taux = section.get("utilisation")
    entete = _p(ETATS_LISIBLES.get(etat, etat))
    if taux is not None:
        entete += f" — utilisation {taux:.3f}"

    blocs: list[Bloc] = [
        Titre(f"{index}. {_p(section.get('title'))}"),
        Paragraphe(f"Base normative : {_p(section.get('basis'))}"),
        Paragraphe(entete, gras=True),
    ]

    if etat == "not_evaluated":
        blocs.append(Paragraphe(
            "Cette vérification n'a pas pu être exécutée : "
            f"{_p(section.get('reason'))}. Aucun résultat n'est produit, et "
            "l'absence de résultat ne vaut pas conformité."))
        return blocs

    if etat == "additional_analysis_required":
        blocs.append(Paragraphe(_p(section.get("remedy")), encadre=True))
    elif etat == "failed" and section.get("remedy"):
        blocs.append(Paragraphe(f"Action : {_p(section.get('remedy'))}"))

    etapes = journal.get("steps") or []
    if etapes:
        lignes = []
        for e in etapes:
            clause = e.get("clause") or {}
            cite = clause.get("cite") if isinstance(clause, dict) else clause
            lignes.append([_p(e.get("symbol")), _p(e.get("description")),
                           _p(e.get("numeric")), _p(e.get("formatted")),
                           _p(cite)])
        blocs.append(Tableau(
            ["Symbole", "Description", "Application numérique", "Valeur",
             "Clause"], lignes, droite={3}))
        clauses = journal.get("clauses") or []
        if clauses:
            blocs.append(Paragraphe(
                "Clauses citées : " + ", ".join(_p(c) for c in clauses)))
    return blocs


# `_quantite` est importé pour rester disponible aux futures rubriques qui
# formatteraient une grandeur structurée; l'étude, elle, stocke déjà ses
# grandeurs formatées par le moteur.
_ = _quantite
