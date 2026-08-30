"""La note de calcul HTML, rendue **depuis les données gelées**.

CE QUE CE MODULE NE FAIT PAS
-----------------------------
Il ne calcule rien. Pas une formule, pas une somme, pas un arrondi, pas un
taux de travail. Chaque nombre affiché a été produit par le moteur, écrit dans
PostgreSQL au moment du calcul, et relu tel quel. Recalculer ne serait-ce
qu'une utilisation moyenne ici créerait une seconde vérité, non éprouvée, et
c'est celle-là que le lecteur croirait puisqu'elle est imprimée.

Il ne relance pas le moteur non plus. Une note produite six mois plus tard par
un moteur corrigé afficherait les nombres d'aujourd'hui sous la date d'hier.

CE QUE LE DOCUMENT NE CONTIENT PAS
------------------------------------
Aucun ``<script>``. Aucune ressource externe : ni feuille de style, ni image,
ni police distante. Le fichier s'ouvre hors ligne, dix ans plus tard, sans
qu'un serveur tiers décide de ce qu'on voit — et sans qu'une requête sortante
signale à quiconque qu'on relit ce dossier.

TOUT CE QUI VIENT D'UN HUMAIN EST ÉCHAPPÉ
-------------------------------------------
Nom de projet, référence, organisation, région, motifs de refus, descriptions
d'étapes : chacun traverse ``html.escape``. Une note est un document qu'on
s'envoie ; un nom de projet contenant ``<script>`` deviendrait exécutable chez
le destinataire.

CE QU'ELLE N'AFFIRME JAMAIS
----------------------------
« Final », « validé », « signable ». La mention obligatoire — ce document doit
être vérifié et signé par un ingénieur habilité — est présente sur toute note.
Le filigrane **PROJET — NON SIGNABLE** s'y ajoute quand des paramètres
nationaux non confirmés ont pu servir. Aucune ligne de validation nominative
n'existe encore : tant qu'elle n'existe pas, rien ici ne peut se dire final.
"""

from __future__ import annotations

from html import escape
from typing import Any

__all__ = ["MEDIA_TYPE", "rendre_note"]

#: `charset` DANS LE TYPE, PAS SEULEMENT DANS LE `<meta>`. Un navigateur qui
#: ouvre le fichier depuis le disque lit le `<meta>`; un client qui le reçoit
#: par HTTP lit l'en-tête. Les deux doivent dire UTF-8, sinon les accents des
#: descriptions d'étapes sortent faux dans l'un des deux cas.
MEDIA_TYPE = "text/html; charset=utf-8"

#: LA FEUILLE DE STYLE EST EMBARQUEE, ET MINIMALE.
#:
#: Aucune police distante: `system-ui` prend celle du lecteur. Une note ouverte
#: dans dix ans ne doit dependre d'aucun serveur — et une requete sortante
#: signalerait a un tiers qu'on relit ce dossier.
_STYLE = """
:root { color-scheme: light; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
       margin: 0; padding: 2rem; color: #1a1a1a; background: #fff;
       line-height: 1.5; }
main { max-width: 60rem; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
h2 { font-size: 1.1rem; margin: 2rem 0 .5rem; border-bottom: 1px solid #ddd;
     padding-bottom: .25rem; }
p.sous-titre { margin: 0 0 1.5rem; color: #555; }
table { border-collapse: collapse; width: 100%; margin: .5rem 0 1rem;
        font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid #eee;
         vertical-align: top; }
th { font-weight: 600; background: #f6f6f6; }
td.nombre, th.nombre { text-align: right; }
dl.champs { display: grid; grid-template-columns: max-content 1fr;
            gap: .3rem 1rem; margin: 0; }
dl.champs dt { font-weight: 600; color: #444; }
dl.champs dd { margin: 0; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
       font-size: .85em; overflow-wrap: anywhere; }
.mention { border: 2px solid #b00; color: #b00; font-weight: 700;
           padding: .75rem 1rem; margin: 1rem 0; letter-spacing: .04em; }
.notice { border-left: 4px solid #666; padding: .5rem 0 .5rem 1rem;
          color: #333; margin: 1.5rem 0; }
.refus { border: 1px solid #b00; padding: .75rem 1rem; margin: 1rem 0; }
.pass { color: #0a6; } .fail { color: #b00; font-weight: 600; }
footer { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #ddd;
         color: #666; font-size: .85rem; }
"""

_STATUT = {"pass": "vérifié", "fail": "NON VÉRIFIÉ",
           "not_applicable": "sans objet"}


def _e(valeur: Any) -> str:
    """Échappe pour du HTML. ``None`` devient un tiret, jamais « None ».

    « None » imprimé sur une note se lit comme une valeur, et l'ingénieur qui
    la relit ne sait pas si le champ était vide ou si le rendu a échoué.
    """
    if valeur is None or valeur == "":
        return "—"
    return escape(str(valeur), quote=True)


def _quantite(q: Any, decimales: int = 2) -> str:
    """``{"value": 1.0, "unit": "mm"}`` -> ``1,00 mm``. Sans jamais recalculer.

    LE FORMATAGE N'EST PAS UN CALCUL, et la distinction est réelle : on
    n'additionne rien, on ne convertit aucune unité — convertir serait
    recalculer, et l'unité affichée doit être celle que le moteur a écrite.
    Seule la virgule décimale est posée, parce que le document est en français.
    """
    if not isinstance(q, dict) or "value" not in q:
        return _e(q)
    try:
        nombre = f"{float(q['value']):.{decimales}f}".replace(".", ",")
    except (TypeError, ValueError):
        return _e(q.get("value"))
    unite = q.get("unit") or ""
    return f"{escape(nombre)}&nbsp;{escape(str(unite))}" if unite else escape(nombre)


def _lignes(paires: list[tuple[str, str]]) -> str:
    return "".join(f"<dt>{escape(cle)}</dt><dd>{valeur}</dd>"
                   for cle, valeur in paires)


def rendre_note(projet: dict[str, Any], calcul: dict[str, Any],
                notice: str, mention: str | None) -> str:
    """Le document complet, autonome, à partir du projet et du calcul relus.

    :param projet: la ligne de projet, telle que ``project_workspace_list``
        la rend. Elle porte l'organisation, la référence et le contexte
        normatif figé.
    :param calcul: le calcul relu, tel que ``project_calculation_read`` le
        rend. Tout ce qui est affiché vient de là.
    :param notice: la mention obligatoire, prise sur la réponse — jamais
        recopiée ici. Une seconde rédaction divergerait de celle que porte le
        DXF, et le document affirmerait autre chose que le livrable.
    :param mention: « PROJET — NON SIGNABLE », ou ``None`` en mode strict.
    """
    paquet = calcul.get("result") or {}
    resultat = paquet.get("result") or {}
    rapport = paquet.get("verification") or {}
    journal = calcul.get("journal") or {}
    requete = calcul.get("request") or {}
    ndp = calcul.get("ndp_snapshot") or {}

    titre = (f"Note de calcul — {projet.get('name', '')} — "
             f"{requete.get('element', '')}")

    parties: list[str] = [
        "<!-- Document autonome: aucun script, aucune ressource externe. -->",
        f"<title>{_e(titre)}</title>",
        f"<style>{_STYLE}</style>",
        "<main>",
        f"<h1>{_e(titre)}</h1>",
        ("<p class=\"sous-titre\">Vérification ELU en flexion simple, "
         "section rectangulaire — EN 1992-1-1 et son Annexe Nationale.</p>"),
    ]

    # LE FILIGRANE EN TETE, PAS EN PIED. Un lecteur qui parcourt la premiere
    # page doit savoir avant de lire les nombres qu'ils ne sont pas signables.
    if mention:
        parties.append(f'<p class="mention">{_e(mention)}</p>')

    # --- 1. LE DOSSIER ----------------------------------------------------
    parties += [
        "<h2>Dossier</h2>",
        "<dl class=\"champs\">",
        _lignes([
            ("Organisation", _e(projet.get("organization_name"))),
            ("Projet", _e(projet.get("name"))),
            ("Référence", _e(projet.get("reference"))),
            ("Pays", _e(projet.get("country"))),
            ("Région", _e(projet.get("region"))),
            ("Date de référence normative", _e(projet.get("ndp_as_of"))),
            ("Élément", _e(requete.get("element"))),
            ("Calcul", f"<code>{_e(calcul.get('calculation_id'))}</code>"),
            ("Enregistré le", _e(calcul.get("created_at"))),
        ]),
        "</dl>",
    ]

    # --- 2. LES ENTREES ---------------------------------------------------
    section = requete.get("section") or {}
    materiaux = requete.get("materials") or {}
    parties += [
        "<h2>Entrées</h2>",
        "<dl class=\"champs\">",
        _lignes([
            ("Largeur b", _quantite(section.get("b"), 0)),
            ("Hauteur h", _quantite(section.get("h"), 0)),
            ("Hauteur utile d", _quantite(section.get("d"), 0)),
            ("Moment M<sub>Ed</sub>", _quantite(requete.get("M_Ed"), 2)),
            ("Béton", _e(materiaux.get("concrete_grade"))),
            ("Acier", _e(materiaux.get("steel_grade"))),
            ("Situation de projet", _e(requete.get("situation"))),
            ("Mode strict",
             "oui" if calcul.get("strict_ndp") else "non (exploratoire)"),
        ]),
        "</dl>",
    ]

    # --- 3. LE REFUS, LE CAS ECHEANT --------------------------------------
    refus = calcul.get("refusal")
    if refus:
        parties += [
            "<h2>Refus du moteur</h2>",
            "<div class=\"refus\">",
            f"<p><strong>{_e(refus.get('error'))}</strong></p>",
            f"<p>{_e(refus.get('detail'))}</p>",
            ("<p>Un refus n'est pas une panne&nbsp;: le moteur a refusé de "
             "conclure, et cette note le dit sans nuance. Aucun résultat "
             "n'est produit.</p>"),
            "</div>",
        ]

    # --- 4. LES RESULTATS -------------------------------------------------
    if resultat:
        parties += [
            "<h2>Résultats</h2>",
            ("<table><thead><tr><th>Grandeur</th>"
             "<th class=\"nombre\">Valeur</th></tr></thead><tbody>"),
        ]
        for cle, libelle, dec in (
            ("As_strength", "A<sub>s</sub> requise par la résistance", 0),
            ("As_min", "A<sub>s,min</sub> — §9.2.1.1(1)", 0),
            ("As_max", "A<sub>s,max</sub> — §9.2.1.1(3)", 0),
            ("As_required", "A<sub>s</sub> requise", 0),
            ("As_provided", "A<sub>s</sub> disposée", 0),
            ("x", "Axe neutre x", 1),
            ("z", "Bras de levier z", 1),
            ("M_Rd", "M<sub>Rd</sub>", 2),
        ):
            if cle in resultat:
                parties.append(f"<tr><td>{libelle}</td>"
                               f"<td class=\"nombre\">"
                               f"{_quantite(resultat[cle], dec)}</td></tr>")
        for cle, libelle in (("mu", "μ"), ("xi", "ξ"), ("xi_lim", "ξ<sub>lim</sub>"),
                             ("eps_s", "ε<sub>s</sub>"),
                             ("utilisation", "Taux de travail")):
            if cle in resultat:
                # LE NOMBRE EST CELUI QUI EST ENREGISTRE. On pose la virgule
                # decimale, on ne touche a rien d'autre — l'interdiction n° 9
                # vaut aussi pour l'affichage.
                brut = resultat[cle]
                texte = (f"{float(brut):.3f}".replace(".", ",")
                         if isinstance(brut, int | float) else _e(brut))
                parties.append(f"<tr><td>{libelle}</td>"
                               f"<td class=\"nombre\">{escape(texte)}</td></tr>")
        parties.append("</tbody></table>")

    # --- 5. LES VERIFICATIONS ---------------------------------------------
    controles = rapport.get("checks") or []
    if controles:
        parties += [
            "<h2>Vérifications</h2>",
            ("<table><thead><tr><th>Contrôle</th><th>État</th>"
             "<th class=\"nombre\">Taux de travail</th><th>Sollicitant</th>"
             "<th>Résistant</th><th>Clause</th></tr></thead><tbody>"),
        ]
        for c in controles:
            statut = str(c.get("status", ""))
            classe = "pass" if statut == "pass" else (
                "fail" if statut == "fail" else "")
            taux = c.get("utilisation")
            # AUCUN ARRONDI QUI FLATTE. `0,999` reste `0,999`; on n'affiche pas
            # « 1,0 » pour un controle qui passe de justesse, ni l'inverse.
            taux_txt = (f"{float(taux) * 100:.1f}".replace(".", ",") + "&nbsp;%"
                        if isinstance(taux, int | float) else "—")
            clause = c.get("clause") or {}
            cite = clause.get("cite") if isinstance(clause, dict) else clause
            parties.append(
                f"<tr><td>{_e(c.get('name'))}</td>"
                f"<td class=\"{classe}\">{_e(_STATUT.get(statut, statut))}</td>"
                f"<td class=\"nombre\">{taux_txt}</td>"
                f"<td>{_e(c.get('acting'))}</td>"
                f"<td>{_e(c.get('resisting'))}</td>"
                f"<td>{_e(cite)}</td></tr>")
        parties.append("</tbody></table>")
        if isinstance(rapport.get("max_utilisation"), int | float):
            maxi = f"{float(rapport['max_utilisation']) * 100:.1f}".replace(".", ",")
            parties.append(f"<p>Taux de travail maximal&nbsp;: "
                           f"<strong>{escape(maxi)}&nbsp;%</strong></p>")

    # --- 6. LE JOURNAL ----------------------------------------------------
    etapes = journal.get("steps") or []
    if etapes:
        parties += [
            f"<h2>Journal de calcul — {_e(journal.get('title'))}</h2>",
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

    # --- 7. LE REFERENTIEL APPLIQUE ---------------------------------------
    parties += ["<h2>Référentiel national appliqué</h2>", "<dl class=\"champs\">"]
    parties.append(_lignes([
        ("Pays", _e(ndp.get("country") or projet.get("country"))),
        ("Région", _e(ndp.get("region") or projet.get("region"))),
        ("Date de référence", _e(ndp.get("as_of") or calcul.get("ndp_as_of"))),
        ("Mode strict", "oui" if ndp.get("strict") else "non"),
    ]))
    parties.append("</dl>")
    annexes = ndp.get("annexes") or []
    if annexes:
        parties += [
            ("<table><thead><tr><th>Annexe</th><th>Édition</th>"
             "<th>En vigueur depuis</th><th>Source</th>"
             "</tr></thead><tbody>")]
        for a in annexes:
            parties.append(
                f"<tr><td>{_e(a.get('reference'))}</td>"
                f"<td>{_e(a.get('edition'))}</td>"
                f"<td>{_e(a.get('effective_from'))}</td>"
                f"<td>{_e(a.get('source_official'))}</td></tr>")
        parties.append("</tbody></table>")
    non_verifies = ndp.get("unverified") or []
    if non_verifies:
        parties.append(
            ("<p><strong>Paramètres nationaux non confirmés utilisés"
             "&nbsp;:</strong> ") + ", ".join(f"<code>{_e(p)}</code>"
                                     for p in non_verifies) + "</p>")

    # --- 8. LA TRACABILITE ------------------------------------------------
    # C'EST LA SECTION QUI REND CETTE NOTE VERIFIABLE. Sans elle, le document
    # affirme des nombres sans dire quel code les a produits ni sous quel
    # referentiel — et « 0.3.0 » ne designe aucun code: plusieurs commits la
    # partagent.
    parties += [
        "<h2>Traçabilité</h2>",
        "<dl class=\"champs\">",
        _lignes([
            ("Moteur", _e(calcul.get("engine_version"))),
            ("Build (SHA exact)",
             f"<code>{_e(calcul.get('engine_build_sha'))}</code>"),
            ("Empreinte des entrées",
             f"<code>{_e(calcul.get('inputs_hash'))}</code>"),
            ("Identité d'exécution",
             f"<code>{_e(calcul.get('execution_identity'))}</code>"),
            ("État", _e(calcul.get("status"))),
        ]),
        "</dl>",
        ("<p>L'empreinte des entrées désigne la <em>requête</em>. L'identité "
         "d'exécution désigne la requête, le référentiel réellement appliqué "
         "et le build&nbsp;: deux calculs de même identité doivent rendre le "
         "même résultat.</p>"),
    ]

    # --- 9. CE QUI RESTE A FAIRE, ET QUI N'EST PAS FAIT -------------------
    parties += [
        f"<div class=\"notice\">{_e(notice)}</div>",
        "<footer>",
        ("<p>Ce document n'est pas un livrable final. Aucune validation "
         "nominative n'y figure&nbsp;: tant qu'un ingénieur habilité ne l'a "
         "pas signée, aucune mention de ce document ne peut se lire comme un "
         "engagement.</p>"),
        ("<p>Document autonome&nbsp;: aucun script, aucune ressource externe, "
         "aucune police distante. Il s'ouvre hors ligne.</p>"),
        "</footer>",
        "</main>",
    ]
    return "\n".join(parties)
