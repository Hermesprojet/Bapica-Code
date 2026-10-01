"""Du modèle structurel aux propositions : méthode ``geometrie``.

CE QUI EST PROPOSÉ, ET RIEN DE PLUS
------------------------------------
| mesure                                   | catégorie                       |
|------------------------------------------|---------------------------------|
| étiquette d'un axe                       | ``grid_line``                   |
| entraxe de deux axes voisins             | ``grid_spacing``                |
| axes extrêmes d'une famille (≥ 3 axes)   | ``building_dimension``          |
| côtés / diamètre d'un poteau (regroupés) | ``column_width/depth/diameter`` |
| épaisseur d'un voile (regroupés)         | ``wall_thickness``              |
| largeur d'une bande, par repère          | ``beam_width``                  |
| entre-axes d'une travée                  | ``beam_span``                   |
| nu à nu d'une travée                     | ``beam_clear_span``             |
| porte-à-faux depuis le nu de l'appui     | ``cantilever_length``           |

Une hauteur de poutre, une épaisseur de dalle ou un niveau ne sont pas des
traits en plan : ils restent aux règles de texte.

LE TEXTE BRUT D'UNE PROPOSITION GÉOMÉTRIQUE EST SA DÉRIVATION. Aucun texte du
dessin n'écrit la portée ; la proposition écrit d'où elle la tire — repère,
appuis, nœuds de grille, longueur, unité — et la position porte les poignées,
les calques et les coordonnées.

LA CONFIANCE EST INDICATIVE, plafonnée à 0,90 comme la vision, et diminuée de
0,2 quand l'unité du dessin n'est pas connue.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Final

from ..modele import Candidat
from .modele import Appui, ModeleStructurel, Poteau, Poutre, RattachementCote, Travee, Voile
from .noyau import projeter, quantifier

__all__ = ["PLAFOND_GEOMETRIE", "propositions_du_modele"]

PLAFOND_GEOMETRIE: Final[float] = 0.90
PENALITE_SANS_UNITE: Final[float] = 0.2
INSTANCES_CITEES_MAX: Final[int] = 50


class _Fabrique:
    def __init__(self, modele: ModeleStructurel) -> None:
        self.m = modele
        self.u = modele.unites
        self.unite = modele.unites.unite
        self.libelle_unite = f" {self.unite}" if self.unite else " (unite non declaree)"
        self.candidats: list[Candidat] = []
        self.marques: dict[str, str] = {}
        for p in modele.poteaux:
            self.marques[p.id] = p.repere or "poteau"
        for v in modele.voiles:
            self.marques[v.id] = v.repere or "voile"
        for b in modele.poutres:
            self.marques[b.id] = "/".join(b.reperes) if b.reperes else "poutre"

    def q(self, valeur: float | None) -> int | float | None:
        if valeur is None:
            return None
        return quantifier(valeur, self.u.tolerances.quantum)

    def confiance(self, base: float) -> float:
        if self.u.base == "absente":
            base -= PENALITE_SANS_UNITE
        return round(min(max(base, 0.05), PLAFOND_GEOMETRIE), 3)

    def proposer(self, categorie: str, valeur: Any, texte: str, confiance: float,
                 position: dict[str, Any], fondement: dict[str, Any],
                 repere: str | None, *, longueur: bool = True) -> None:
        if valeur is None:
            return
        fond = dict(fondement)
        if longueur:
            fond.update(self.u.fondement())
            fond["quantum"] = self.u.tolerances.quantum
        self.candidats.append(Candidat(
            categorie=categorie, valeur=valeur, unite=self.unite if longueur else None,
            texte_brut=texte[:500], page=1, confiance=self.confiance(confiance),
            methode="geometrie",
            position={"source": "geometry", "space": "modelspace",
                      "drawing_units": self.unite, **position},
            repere=repere, fondement=fond))

    # -------------------------------------------------------------- libellés
    def marque(self, appui: Appui, portee: Poutre) -> str:
        """Le repère de l'appui ; pour une poutre porteuse, celui de SA travée
        sous le point d'appui (« B1 », non « B1/B2 »)."""
        if appui.genre == "poutre":
            porteuse = next((p for p in self.m.poutres if p.id == appui.element), None)
            if porteuse is not None:
                b = porteuse.bande
                t = projeter(portee.bande.point(appui.centre), b.origine, b.direction)
                for travee in porteuse.travees:
                    if (travee.repere and travee.debut and travee.fin
                            and min(travee.debut.centre, travee.fin.centre) <= t
                            <= max(travee.debut.centre, travee.fin.centre)):
                        return travee.repere
        return self.marques.get(appui.element, appui.genre)

    def appui(self, appui: Appui | None, portee: Poutre) -> str:
        if appui is None:
            return "extremite libre"
        marque = self.marque(appui, portee)
        return f"{marque} · {appui.noeud}" if appui.noeud else marque

    def appui_json(self, appui: Appui | None, portee: Poutre) -> dict[str, Any] | None:
        if appui is None:
            return None
        return {"support": appui.element, "kind": appui.genre,
                "mark": self.marque(appui, portee), "grid_node": appui.noeud,
                "centre": self.q(appui.centre),
            "faces": [self.q(appui.faces[0]), self.q(appui.faces[1])],
            "width": self.q(appui.largeur)}

    @staticmethod
    def notes(notes: list[RattachementCote] | tuple[RattachementCote, ...]) -> list[dict[str, Any]]:
        return [{"handle": n.poignee, "measures": n.mesure_de, "measured": n.mesure,
                 "displayed": n.affichee, "measure_agrees": n.concordante,
                 "forced_mismatch": n.discordante} for n in notes]

    @staticmethod
    def ajuster(base: float, notes: list[RattachementCote] | tuple[RattachementCote, ...]) -> float:
        if any(n.discordante for n in notes):
            return min(base, 0.4)
        if any(n.concordante for n in notes):
            return base + 0.05
        return base

    # -------------------------------------------------------------- grille
    def grille(self) -> None:
        g = self.m.grille
        r = self.m.rattachements
        for axe in g.axes:
            if not axe.etiquette:
                continue
            self.proposer(
                "grid_line", axe.etiquette,
                f"file {axe.etiquette} (calque {', '.join(axe.preuve.calques)} ; geometrie)",
                axe.confiance,
                {"element": {"type": "grid_axis", "id": axe.id},
                 "line": [[self.q(c) for c in p] for p in axe.extremites],
                 "evidence": axe.preuve.en_json()},
                {"rule": "axe_de_grille", "label_source": axe.etiquette_source,
                 "classified_by": axe.preuve.regle}, None, longueur=False)
        for famille in g.familles:
            axes = [g.axe(i) for i in famille.axes]
            for a, b in zip(axes, axes[1:], strict=False):
                brute = abs(b.decalage - a.decalage)
                notes = (r.par_entraxe.get((a.id, b.id), []) if r else [])
                repere = f"{a.etiquette}-{b.etiquette}" if a.etiquette and b.etiquette else None
                nom = repere or f"{a.id} - {b.id}"
                self.proposer(
                    "grid_spacing", self.q(brute),
                    f"entraxe {nom} : {self.q(brute)}{self.libelle_unite} (distance entre "
                    "deux axes paralleles ; geometrie)",
                    self.ajuster(min(a.confiance, b.confiance), notes),
                    {"element": {"type": "grid_spacing", "id": f"{a.id}..{b.id}"},
                     "axes": [a.id, b.id], "evidence": a.preuve.fusion(b.preuve).en_json()},
                    {"rule": "entraxe_droites_paralleles", "measured_raw": brute,
                     "dimensions": self.notes(notes)}, repere)
            if len(axes) >= 3 and axes[0].etiquette and axes[-1].etiquette:
                a, b = axes[0], axes[-1]
                brute = abs(b.decalage - a.decalage)
                notes = (r.par_extremes.get((a.id, b.id), []) if r else [])
                self.proposer(
                    "building_dimension", self.q(brute),
                    f"entre axes extremes {a.etiquette}-{b.etiquette} : {self.q(brute)}"
                    f"{self.libelle_unite} ({len(axes)} axes ; geometrie)",
                    self.ajuster(min(a.confiance, b.confiance) - 0.05, notes),
                    {"element": {"type": "grid_extent", "id": f"{a.id}..{b.id}"},
                     "axes": [ax.id for ax in axes]},
                    {"rule": "axes_extremes", "measured_raw": brute,
                     "dimensions": self.notes(notes)}, f"{a.etiquette}-{b.etiquette}")

    # -------------------------------------------------------------- poteaux
    def poteaux(self) -> None:
        groupes: dict[tuple[Any, ...], list[Poteau]] = defaultdict(list)
        for p in self.m.poteaux:
            if p.forme == "polygone":
                continue
            groupes[(p.repere, p.forme, self.q(p.largeur), self.q(p.profondeur),
                     self.q(p.diametre))].append(p)
        for (repere, forme, largeur, profondeur, diametre), membres in sorted(
                groupes.items(), key=lambda x: (x[0][0] or "~", str(x[0][2]), str(x[0][3]),
                                                str(x[0][4]))):
            noeuds = [p.noeud or p.id for p in membres]
            confiance = min(p.confiance for p in membres)
            instances = [{"id": p.id, "grid_node": p.noeud,
                          "centre": [self.q(p.centre[0]), self.q(p.centre[1])],
                          "handles": list(p.preuve.poignees[:5])}
                         for p in membres[:INSTANCES_CITEES_MAX]]
            position = {"element": {"type": "column_group", "id": membres[0].id},
                        "instances": instances, "count": len(membres)}
            nom = repere or "poteau"
            if forme == "cercle":
                self.proposer(
                    "column_diameter", diametre,
                    f"{nom} : diametre {diametre}{self.libelle_unite}, {len(membres)} poteau(x) "
                    f"({', '.join(noeuds[:12])}) ; geometrie", confiance, position,
                    {"rule": "poteau_circulaire", "instances": len(membres),
                     "classified_by": membres[0].preuve.regle}, repere)
                continue
            texte = (f"{nom} : {largeur} x {profondeur}{self.libelle_unite}, {len(membres)} "
                     f"poteau(x) ({', '.join(noeuds[:12])}) ; geometrie")
            fondement = {"rule": "poteau_rectangulaire", "instances": len(membres),
                         "classified_by": membres[0].preuve.regle,
                         "convention": "largeur selon l'axe x de la grille, profondeur selon y"}
            self.proposer("column_width", largeur, texte, confiance, position, fondement, repere)
            self.proposer("column_depth", profondeur, texte, confiance, position, fondement,
                          repere)

    # -------------------------------------------------------------- voiles
    def voiles(self) -> None:
        groupes: dict[tuple[Any, ...], list[Voile]] = defaultdict(list)
        for v in self.m.voiles:
            if v.epaisseur is not None:
                groupes[(v.repere, self.q(v.epaisseur))].append(v)
        for (repere, epaisseur), membres in sorted(groupes.items(),
                                                   key=lambda x: (x[0][0] or "~", str(x[0][1]))):
            self.proposer(
                "wall_thickness", epaisseur,
                f"{repere or 'voile'} : epaisseur {epaisseur}{self.libelle_unite}, "
                f"{len(membres)} voile(s) ; geometrie",
                min(v.confiance for v in membres),
                {"element": {"type": "wall_group", "id": membres[0].id},
                 "instances": [v.id for v in membres[:INSTANCES_CITEES_MAX]],
                 "count": len(membres)},
                {"rule": "epaisseur_de_voile", "instances": len(membres),
                 "classified_by": membres[0].preuve.regle}, repere)

    # -------------------------------------------------------------- poutres
    def poutres(self) -> None:
        r = self.m.rattachements
        for poutre in self.m.poutres:
            if not poutre.travees:
                # SANS APPUI, la bande reste dans le modèle et dans « unresolved »;
                # rien n'en est proposé, pas même sa largeur.
                continue
            self._largeurs(poutre, r)
            for travee in poutre.travees:
                if travee.genre == "travee":
                    self._travee(poutre, travee)
                else:
                    self._console(poutre, travee)

    def _largeurs(self, poutre: Poutre, r: Any) -> None:
        b = poutre.bande
        if b.largeur is None:
            return
        notes = r.par_largeur.get(poutre.id, []) if r else []
        reperes = sorted({t.repere for t in poutre.travees if t.repere})
        for repere in reperes or [None]:
            self.proposer(
                "beam_width", self.q(b.largeur),
                f"{repere or 'poutre'} : largeur {self.q(b.largeur)}{self.libelle_unite} "
                f"entre les deux faces ({b.dessin}, calque {', '.join(b.preuve.calques)} ; "
                "geometrie)",
                self.ajuster(poutre.confiance, notes),
                {"element": {"type": "beam", "id": poutre.id},
                 "axis": [[self.q(c) for c in b.point(b.debut)],
                          [self.q(c) for c in b.point(b.fin)]],
                 "evidence": b.preuve.en_json()},
                {"rule": "largeur_de_bande", "drawn_as": b.dessin, "measured_raw": b.largeur,
                 "classified_by": b.preuve.regle, "dimensions": self.notes(notes)}, repere)

    def _travee(self, poutre: Poutre, t: Travee) -> None:
        b = poutre.bande
        position = {
            "element": {"type": "span", "id": t.id}, "beam": poutre.id,
            "span": {"index": t.index, "count": t.nombre,
                     "from": self.appui_json(t.debut, poutre),
                     "to": self.appui_json(t.fin, poutre)},
            "axis": [[self.q(c) for c in b.point(t.debut.centre)],  # type: ignore[union-attr]
                     [self.q(c) for c in b.point(t.fin.centre)]],  # type: ignore[union-attr]
            "evidence": b.preuve.en_json()}
        fondement = {
            "rule": "entre_axes_des_appuis", "axis_length": self.q(t.entre_axes),
            "clear_length": self.q(t.nu_a_nu),
            "support_widths": [self.q(t.debut.largeur), self.q(t.fin.largeur)],  # type: ignore[union-attr]
            "supports": [self.appui_json(t.debut, poutre), self.appui_json(t.fin, poutre)],
            "mark_source": t.repere_source, "dimensions": self.notes(t.cotes),
            "measured_raw": t.entre_axes, "classified_by": b.preuve.regle}
        intitule = f"{t.repere or 'poutre'} — travee {t.index}/{t.nombre} : " \
                   f"{self.appui(t.debut, poutre)} -> {self.appui(t.fin, poutre)}"
        self.proposer(
            "beam_span", self.q(t.entre_axes),
            f"{intitule}, entre-axes {self.q(t.entre_axes)}{self.libelle_unite} (geometrie)",
            t.confiance, position, fondement, t.repere)
        self.proposer(
            "beam_clear_span", self.q(t.nu_a_nu),
            f"{intitule}, nu a nu {self.q(t.nu_a_nu)}{self.libelle_unite} (geometrie)",
            t.confiance - 0.05, position,
            {**fondement, "rule": "nu_a_nu_des_appuis", "measured_raw": t.nu_a_nu}, t.repere)

    def _console(self, poutre: Poutre, t: Travee) -> None:
        appui = t.debut or t.fin
        b = poutre.bande
        self.proposer(
            "cantilever_length", self.q(t.nu_a_nu),
            f"{t.repere or 'poutre'} — console depuis {self.appui(appui, poutre)} : "
            f"{self.q(t.nu_a_nu)}{self.libelle_unite} depuis le nu de l'appui "
            f"(entre-axes {self.q(t.entre_axes)}) (geometrie)",
            t.confiance,
            {"element": {"type": "cantilever", "id": t.id}, "beam": poutre.id,
             "support": self.appui_json(appui, poutre), "evidence": b.preuve.en_json()},
            {"rule": "porte_a_faux", "axis_length": self.q(t.entre_axes),
             "clear_length": self.q(t.nu_a_nu), "measured_raw": t.nu_a_nu,
             "mark_source": t.repere_source}, t.repere)


def propositions_du_modele(modele: ModeleStructurel) -> list[Candidat]:
    fabrique = _Fabrique(modele)
    fabrique.grille()
    fabrique.poteaux()
    fabrique.voiles()
    fabrique.poutres()
    return fabrique.candidats
