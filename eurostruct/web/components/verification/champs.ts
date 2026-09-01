/**
 * Les champs de l'étude, tels qu'on les SAISIT — et leur passage au contrat.
 *
 * POURQUOI DES CHAÎNES, ET PAS DES NOMBRES
 * ------------------------------------------
 * Un champ de saisie vide vaut `""`, jamais `0`. Les stocker en `number`
 * obligerait à choisir une valeur pour « rien », et « rien » deviendrait un
 * zéro que le serveur accepterait sans broncher : une portée nulle, un moment
 * nul, un enrobage nul. La conversion se fait donc au tout dernier moment, et
 * `champsIncomplets` dit AVANT l'envoi ce qui manque.
 *
 * CE FICHIER NE CALCULE RIEN. Pas une aire d'acier, pas un taux, pas une
 * borne. Il transporte ce que l'ingénieur a écrit, et rien d'autre : chaque
 * grandeur dérivée qu'on ajouterait ici serait une SECONDE SOURCE, et le jour
 * où elle diverge du moteur, l'écran affirmerait autre chose que la note.
 */
import type { Ec2BeamVerificationRequest } from "@/lib/verification";

/**
 * Les dix-sept entrées, en texte.
 *
 * Elles NE PORTENT NI pays, NI région, NI date normative : les trois sont
 * figés sur le projet et lus côté serveur. Le type généré de la requête ne les
 * accepte pas non plus — c'est le même refus, dit deux fois.
 */
export type ChampsEtude = {
  element: string;
  //: Section et portée
  b: string; h: string; d: string; l_eff: string;
  //: Matériaux et environnement
  beton: string; acier: string; exposition: string;
  //: Sollicitations
  M_Ed: string; V_Ed: string; M_char: string; M_qp: string;
  //: Ferraillage
  barres_nb: string; barres_diametre: string;
  cadres_branches: string; cadres_diametre: string; cadres_espacement: string;
  enrobage: string; cot_theta: string; ancrage: string; adherence: string;
  //: Service
  phi_creep: string; systeme: string; cloisons_fragiles: boolean;
  //: Mode
  strict: boolean;
};

/**
 * Un point de départ COURANT, à corriger — jamais une réponse.
 *
 * Aucune de ces valeurs n'est une recommandation : ce sont les dimensions
 * d'une poutre ordinaire, posées pour que l'écran ne s'ouvre pas sur vingt
 * champs vides. L'ingénieur les remplace toutes.
 *
 * DEUX CHAMPS N'ONT VOLONTAIREMENT PAS DE DÉFAUT UTILE. `phi_creep` dépend du
 * rayon moyen, de l'humidité et de l'âge au chargement ; `systeme` vaut de 0,4
 * à 1,5 selon la ligne du Tableau 7.4N. Un défaut y serait le plus cher des
 * mensonges — il passerait inaperçu.
 */
export const CHAMPS_INITIAUX: ChampsEtude = {
  element: "P1",
  b: "300", h: "600", d: "550", l_eff: "6000",
  beton: "C30/37", acier: "B500B", exposition: "XC3",
  M_Ed: "250", V_Ed: "300", M_char: "180", M_qp: "120",
  barres_nb: "4", barres_diametre: "20",
  cadres_branches: "2", cadres_diametre: "10", cadres_espacement: "150",
  enrobage: "40", cot_theta: "1.5", ancrage: "800", adherence: "good",
  phi_creep: "", systeme: "", cloisons_fragiles: false,
  strict: true,
};

/** Les cinq systèmes du Tableau 7.4N, et leur K. Aucun défaut. */
export const SYSTEMES: ReadonlyArray<readonly [string, string]> = [
  ["simply_supported", "Poutre isostatique (K = 1,0)"],
  ["end_span_continuous", "Travée de rive continue (K = 1,3)"],
  ["interior_span_continuous", "Travée intermédiaire (K = 1,5)"],
  ["flat_slab", "Plancher-dalle (K = 1,2)"],
  ["cantilever", "Console (K = 0,4)"],
];

/** Les classes d'exposition du Tableau 4.1. */
export const EXPOSITIONS = [
  "X0", "XC1", "XC2", "XC3", "XC4", "XD1", "XD2", "XD3",
  "XS1", "XS2", "XS3", "XF1", "XF2", "XF3", "XF4", "XA1", "XA2", "XA3",
] as const;

/** Les sept étapes, dans l'ordre où on les remplit. */
export const ETAPES = [
  { cle: "dossier", titre: "Le dossier" },
  { cle: "section", titre: "La section" },
  { cle: "materiaux", titre: "Les matériaux" },
  { cle: "sollicitations", titre: "Les sollicitations" },
  { cle: "ferraillage", titre: "Le ferraillage" },
  { cle: "service", titre: "Les conditions de service" },
  { cle: "mode", titre: "Le mode et le lancement" },
] as const;

export type CleEtape = (typeof ETAPES)[number]["cle"];

/** Un nombre, ou `null` si la saisie n'en est pas un. Jamais `0` par défaut. */
function nombre(texte: string): number | null {
  const net = texte.trim().replace(",", ".");
  if (net === "") return null;
  const n = Number(net);
  return Number.isFinite(n) ? n : null;
}

/**
 * Ce qui manque, étape par étape — AVANT tout envoi.
 *
 * L'ÉCRAN NE VALIDE AUCUNE RÈGLE D'INGÉNIERIE ICI, et c'est délibéré. Il ne
 * demande pas si `d < h`, si `M_char ≥ M_qp` ou si `cot θ` est dans les
 * bornes : ces questions ont des réponses NATIONALES, et les trancher dans le
 * navigateur ferait un second juge dont personne ne relit les règles. Le
 * serveur refuse, avec sa clause et son annexe.
 *
 * Ce qu'il vérifie, c'est qu'une valeur A ÉTÉ SAISIE et qu'elle est un nombre.
 * Envoyer `""` obtiendrait un 422 de forme, illisible pour l'ingénieur.
 */
export function champsManquants(c: ChampsEtude): Record<CleEtape, string[]> {
  const requis = (etiquette: string, valeur: string): string | null =>
    nombre(valeur) === null ? etiquette : null;
  const texte = (etiquette: string, valeur: string): string | null =>
    valeur.trim() === "" ? etiquette : null;

  const garder = (...v: (string | null)[]) => v.filter((x): x is string => !!x);

  return {
    dossier: garder(texte("le repère de l'élément", c.element)),
    section: garder(
      requis("la largeur b", c.b), requis("la hauteur h", c.h),
      requis("la hauteur utile d", c.d), requis("la portée utile", c.l_eff)),
    materiaux: garder(
      texte("la classe de béton", c.beton), texte("la nuance d'acier", c.acier),
      texte("la classe d'exposition", c.exposition)),
    sollicitations: garder(
      requis("M_Ed", c.M_Ed), requis("V_Ed", c.V_Ed),
      requis("M sous combinaison caractéristique", c.M_char),
      requis("M sous combinaison quasi-permanente", c.M_qp)),
    ferraillage: garder(
      requis("le nombre de barres", c.barres_nb),
      requis("le diamètre des barres", c.barres_diametre),
      requis("le nombre de branches", c.cadres_branches),
      requis("le diamètre des cadres", c.cadres_diametre),
      requis("l'espacement des cadres", c.cadres_espacement),
      requis("l'enrobage", c.enrobage),
      requis("cot θ", c.cot_theta),
      requis("la longueur d'ancrage disponible", c.ancrage)),
    service: garder(
      requis("le coefficient de fluage φ(∞,t₀)", c.phi_creep),
      texte("le système structural (Tableau 7.4N)", c.systeme)),
    //: Le mode est un booléen: il ne peut pas manquer.
    mode: [],
  };
}

/** Vrai quand toutes les étapes sont remplies. */
export function etudeComplete(c: ChampsEtude): boolean {
  return Object.values(champsManquants(c)).every((m) => m.length === 0);
}

/**
 * Le corps que le serveur attend, composé au tout dernier moment.
 *
 * IL NE PORTE AUCUNE GRANDEUR DÉRIVÉE. `A_s` se déduit des barres, `A_sw` des
 * branches, l'entraxe du modèle géométrique : les envoyer donnerait deux
 * sources pour un même fait. Le type généré ne les accepte pas.
 *
 * Appeler cette fonction sur des champs incomplets produirait `NaN` : c'est à
 * l'appelant de vérifier `etudeComplete` d'abord, et l'écran le fait en
 * désactivant le bouton avec le motif écrit à côté.
 */
export function enRequete(c: ChampsEtude): Ec2BeamVerificationRequest {
  const mm = (v: string) => ({ value: Number(v.trim().replace(",", ".")), unit: "mm" });
  const val = (v: string) => Number(v.trim().replace(",", "."));
  return {
    element: c.element.trim(),
    strict_ndp: c.strict,
    geometry: { b: mm(c.b), h: mm(c.h), d: mm(c.d), l_eff: mm(c.l_eff) },
    materials: { concrete_grade: c.beton.trim(), steel_grade: c.acier.trim() },
    M_Ed: { value: val(c.M_Ed), unit: "kN*m" },
    V_Ed: { value: val(c.V_Ed), unit: "kN" },
    M_char: { value: val(c.M_char), unit: "kN*m" },
    M_qp: { value: val(c.M_qp), unit: "kN*m" },
    phi_creep: val(c.phi_creep),
    exposure_class: c.exposition.trim(),
    structural_system: c.systeme.trim(),
    supports_brittle_partitions: c.cloisons_fragiles,
    bars: {
      count: val(c.barres_nb),
      diameter: mm(c.barres_diametre),
    },
    links: {
      legs: val(c.cadres_branches),
      diameter: mm(c.cadres_diametre),
      spacing: mm(c.cadres_espacement),
    },
    cot_theta: val(c.cot_theta),
    cover: mm(c.enrobage),
    anchorage_available: mm(c.ancrage),
    bond_condition: c.adherence,
  };
}
