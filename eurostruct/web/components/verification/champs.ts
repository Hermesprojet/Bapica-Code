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
import type { ChampPrerempli, ProvenanceDTO } from "@contracts/generated/engine";
import type { Ec2BeamVerificationRequest } from "@/lib/verification";

/**
 * Les entrées de l'étude, en texte — les dix-sept courantes et les avancées.
 *
 * Elles NE PORTENT NI pays, NI région, NI date normative : les trois sont
 * figés sur le projet et lus côté serveur. Le type généré de la requête ne les
 * accepte pas non plus — c'est le même refus, dit deux fois.
 *
 * LES ENTRÉES AVANCÉES SONT DES CHAMPS, PAS DES CASES CACHÉES. La classe
 * associée pour w_max, le rapport b_eff/b_w et les six coefficients d'ancrage
 * sont des entrées du contrat ; une étude qui les porte doit pouvoir être
 * relue, et sa variante les reprendre. Mesuré avant ce lot : une variante
 * d'une étude qui les portait les perdait en silence.
 */
export type ChampsEtude = {
  element: string;
  //: Section et portée
  b: string; h: string; d: string; l_eff: string;
  //: Rapport largeur efficace / largeur d'âme (section en T). Vide = rectangulaire.
  b_eff_sur_b_w: string;
  //: Matériaux et environnement
  beton: string; acier: string; exposition: string;
  //: Classe XC/XD/XS associée pour w_max, quand l'exposition est XF ou XA.
  w_max_associee: string;
  //: Sollicitations
  M_Ed: string; V_Ed: string; M_char: string; M_qp: string;
  //: Ferraillage
  barres_nb: string; barres_diametre: string;
  cadres_branches: string; cadres_diametre: string; cadres_espacement: string;
  enrobage: string; cot_theta: string; ancrage: string; adherence: string;
  //: Coefficients d'ancrage du Tableau 8.2 (et 8.3 pour α6): tous ou aucun.
  alpha_1: string; alpha_2: string; alpha_3: string;
  alpha_4: string; alpha_5: string; alpha_6: string;
  //: Service
  phi_creep: string; systeme: string; cloisons_fragiles: boolean;
  //: Mode
  strict: boolean;
};

/** Les champs-texte de la saisie : tous sauf les deux cases à cocher. */
export type ChampTexte = Exclude<keyof ChampsEtude, "cloisons_fragiles" | "strict">;

/**
 * LE CHEMIN DU CONTRAT ET LE CHAMP DE LA SAISIE, POUR LES ONZE ENTRÉES QU'UN
 * DOCUMENT PEUT RENSEIGNER — et pour elles seules.
 *
 * Les chemins sont ceux de `PROVENANCE_CHEMINS` côté serveur. `d` n'y figure
 * pas (grandeur dérivée), ni aucune sollicitation (une charge lue sur un plan
 * n'est pas un moment) : ces champs se saisissent, toujours.
 */
export const CHAMP_DE_CHEMIN: Readonly<Record<string, ChampTexte>> = {
  "geometry.b": "b",
  "geometry.h": "h",
  "geometry.l_eff": "l_eff",
  "materials.concrete_grade": "beton",
  "materials.steel_grade": "acier",
  "exposure_class": "exposition",
  "cover": "enrobage",
  "bars.count": "barres_nb",
  "bars.diameter": "barres_diametre",
  "links.diameter": "cadres_diametre",
  "links.spacing": "cadres_espacement",
};

/** L'unité dans laquelle chaque champ reçoit sa valeur. `null` : sans unité. */
const UNITE_DU_CHAMP: Readonly<Partial<Record<ChampTexte, string | null>>> = {
  b: "mm", h: "mm", l_eff: "mm", enrobage: "mm", barres_diametre: "mm",
  cadres_diametre: "mm", cadres_espacement: "mm",
  beton: null, acier: null, exposition: null, barres_nb: null,
};

/**
 * L'origine documentaire d'un champ : la provenance que le serveur a rendue,
 * et la valeur reportée. MODIFIER LE CHAMP LA RETIRE — la valeur redevient une
 * saisie, et n'est plus envoyée comme extraite d'un document.
 */
export type ProvenanceDeChamp = {
  chemin: string;
  provenance: ProvenanceDTO;
  valeur: string;
  avertissement?: string | null;
};
export type Provenances = Partial<Record<ChampTexte, ProvenanceDeChamp>>;

/**
 * Les valeurs DÉCIDÉES, reportées dans la saisie — sans aucune conversion.
 *
 * Le serveur les a déjà mises dans l'unité de chaque champ ; une unité
 * inattendue n'est donc PAS convertie ici : la valeur est écartée, et la
 * raison est rendue pour être affichée.
 */
export function reportDepuisPreremplissage(champs: ChampPrerempli[]): {
  valeurs: Partial<Record<ChampTexte, string>>;
  provenances: Provenances;
  ecartes: string[];
} {
  const valeurs: Partial<Record<ChampTexte, string>> = {};
  const provenances: Provenances = {};
  const ecartes: string[] = [];
  for (const c of champs) {
    const cle = CHAMP_DE_CHEMIN[c.path];
    if (!cle) {
      ecartes.push(`${c.label} : aucun champ de l'étude ne la reçoit`);
      continue;
    }
    const attendue = UNITE_DU_CHAMP[cle] ?? null;
    if ((c.unit ?? null) !== attendue) {
      ecartes.push(`${c.label} : rendue en « ${c.unit ?? "sans unité"} », le champ `
        + `attend « ${attendue ?? "sans unité"} » — saisissez-la`);
      continue;
    }
    const valeur = String(c.value);
    valeurs[cle] = valeur;
    provenances[cle] = {
      chemin: c.path, provenance: c.provenance, valeur, avertissement: c.warning,
    };
  }
  return { valeurs, provenances, ecartes };
}

/** Les six coefficients, dans l'ordre du Tableau 8.2. */
export const ALPHAS = [
  "alpha_1", "alpha_2", "alpha_3", "alpha_4", "alpha_5", "alpha_6",
] as const;

/**
 * Les classes que le Tableau 7.1N-ANB sait associer pour w_max : XC, XD, XS.
 * Ni XF ni XA — c'est précisément quand l'exposition est XF ou XA qu'on en
 * déclare une.
 */
export const CLASSES_W_MAX = [
  "XC1", "XC2", "XC3", "XC4", "XD1", "XD2", "XD3", "XS1", "XS2", "XS3",
] as const;

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
 * mensonges — il passerait inaperçu. Les entrées avancées sont vides : vides,
 * elles ne partent pas dans la requête, et le moteur dit ce qu'il retient.
 */
export const CHAMPS_INITIAUX: ChampsEtude = {
  element: "P1",
  b: "300", h: "600", d: "550", l_eff: "6000", b_eff_sur_b_w: "",
  beton: "C30/37", acier: "B500B", exposition: "XC3", w_max_associee: "",
  M_Ed: "250", V_Ed: "300", M_char: "180", M_qp: "120",
  barres_nb: "4", barres_diametre: "20",
  cadres_branches: "2", cadres_diametre: "10", cadres_espacement: "150",
  enrobage: "40", cot_theta: "1.5", ancrage: "800", adherence: "good",
  alpha_1: "", alpha_2: "", alpha_3: "", alpha_4: "", alpha_5: "", alpha_6: "",
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
 *
 * LES ENTRÉES AVANCÉES SONT FACULTATIVES, MAIS PAS À MOITIÉ. Un rapport
 * b_eff/b_w saisi doit être un nombre ; les six coefficients d'ancrage se
 * donnent tous, ou aucun — trois sur six enverraient au moteur une déclaration
 * qu'il n'a pas le droit de compléter.
 */
export function champsManquants(c: ChampsEtude): Record<CleEtape, string[]> {
  const requis = (etiquette: string, valeur: string): string | null =>
    nombre(valeur) === null ? etiquette : null;
  const texte = (etiquette: string, valeur: string): string | null =>
    valeur.trim() === "" ? etiquette : null;
  const facultatif = (etiquette: string, valeur: string): string | null =>
    valeur.trim() !== "" && nombre(valeur) === null ? etiquette : null;

  const garder = (...v: (string | null)[]) => v.filter((x): x is string => !!x);

  const alphasRemplis = ALPHAS.filter((a) => c[a].trim() !== "");
  const alphasFaux = ALPHAS.filter((a) => c[a].trim() !== "" && nombre(c[a]) === null);

  return {
    dossier: garder(texte("le repère de l'élément", c.element)),
    section: garder(
      requis("la largeur b", c.b), requis("la hauteur h", c.h),
      requis("la hauteur utile d", c.d), requis("la portée utile", c.l_eff),
      facultatif("le rapport b_eff/b_w (un nombre, ou vide)", c.b_eff_sur_b_w)),
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
      requis("la longueur d'ancrage disponible", c.ancrage),
      alphasRemplis.length > 0 && alphasRemplis.length < ALPHAS.length
        ? "les six coefficients d'ancrage α1 à α6 (tous, ou aucun)" : null,
      ...alphasFaux.map((a) => `le coefficient ${a.replace("alpha_", "α")} (un nombre)`)),
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
 * LES ENTRÉES AVANCÉES NE PARTENT QUE SI ELLES SONT SAISIES. Vides, la clé
 * est absente du corps : le corps d'une étude courante reste celui d'hier,
 * octet pour octet, et le moteur retient ce qu'il déclare retenir.
 *
 * Appeler cette fonction sur des champs incomplets produirait `NaN` : c'est à
 * l'appelant de vérifier `etudeComplete` d'abord, et l'écran le fait en
 * désactivant le bouton avec le motif écrit à côté.
 */
export function enRequete(
  c: ChampsEtude, origine: string | null = null, provenances: Provenances = {},
): Ec2BeamVerificationRequest {
  const mm = (v: string) => ({ value: Number(v.trim().replace(",", ".")), unit: "mm" });
  const val = (v: string) => Number(v.trim().replace(",", "."));
  const alphas = ALPHAS.every((a) => c[a].trim() !== "");
  //: L'ORIGINE DOCUMENTAIRE, CHAMP PAR CHAMP — seulement pour une valeur
  //: restee celle qui a ete reportee. Le serveur relira chaque decision et
  //: refusera tout ecart; l'ecran ne la renvoie donc que quand elle tient.
  const provenance = Object.fromEntries(
    (Object.entries(provenances) as [ChampTexte, ProvenanceDeChamp | undefined][])
      .filter(([cle, p]) => p && c[cle].trim() === p.valeur)
      .map(([, p]) => [p!.chemin, p!.provenance]));
  return {
    //: LA FILIATION D'UNE VARIANTE, quand il y en a une. La clé n'est posée
    //: que dans ce cas: le corps d'une étude initiale reste celui d'hier,
    //: octet pour octet.
    ...(origine ? { derived_from_calculation_id: origine } : {}),
    //: MEME REGLE POUR LA PROVENANCE: absente d'une etude saisie.
    ...(Object.keys(provenance).length ? { provenance } : {}),
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
    ...(c.w_max_associee.trim()
      ? { w_max_associated_class: c.w_max_associee.trim() } : {}),
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
    ...(c.b_eff_sur_b_w.trim() ? { b_eff_over_b_w: val(c.b_eff_sur_b_w) } : {}),
    bond_condition: c.adherence,
    ...(alphas ? {
      anchorage_coefficients: {
        alpha_1: val(c.alpha_1), alpha_2: val(c.alpha_2), alpha_3: val(c.alpha_3),
        alpha_4: val(c.alpha_4), alpha_5: val(c.alpha_5), alpha_6: val(c.alpha_6),
      },
    } : {}),
  };
}

/**
 * Une entrée de l'étude d'origine que le formulaire n'a PAS pu reprendre.
 *
 * `champ` désigne le champ resté vide, pour que le blocage se lève dès qu'on
 * le saisit ; `"*"` désigne une impossibilité globale, que seul le détachement
 * de la variante peut lever.
 */
export type NonRepris = { champ: keyof ChampsEtude | "*"; motif: string };

export type ChampsDeVariante = {
  champs: ChampsEtude; nonRepris: NonRepris[];
  //: L'ORIGINE DOCUMENTAIRE DE L'ETUDE D'ORIGINE, reprise avec ses valeurs:
  //: une variante sans modification renvoie les memes decisions, que le
  //: serveur reverifiera.
  provenances: Provenances;
};

/** Les unités que chaque champ attend. Aucune conversion n'est faite ici. */
const MM = ["mm"];
const KNM = ["kN*m", "kN·m"];
const KN = ["kN"];

/**
 * Les champs d'une VARIANTE : la requête gelée d'une étude, remise en saisie.
 *
 * ELLE REPART DE LA REQUÊTE, PAS DES GRANDEURS FORMATÉES. `inputs` porte ce
 * que le moteur a reçu, mis en forme à trois décimales avec ses unités ;
 * la requête gelée porte ce que l'ingénieur a SAISI, valeur et unité exactes.
 * Une variante sans modification doit rendre la même empreinte d'entrées
 * d'ingénierie que son origine, et seule la requête le garantit.
 *
 * AUCUNE CONVERSION D'UNITÉ. Une grandeur gelée en millimètres redevient le
 * nombre saisi dans le champ en millimètres ; une grandeur dans une autre
 * unité n'est PAS convertie : le champ reste vide, l'entrée est nommée dans
 * `nonRepris`, et le lancement est bloqué tant que le champ n'est pas saisi
 * à la main. Un facteur appliqué ici serait une règle de calcul dans le
 * navigateur.
 *
 * TOUT CE QUE LA REQUÊTE PORTE A UN CHAMP. Les entrées avancées comprises :
 * rien n'est perdu en silence, et ce que l'écran ne saurait pas reprendre
 * bloque au lieu d'avertir.
 */
export function champsDepuisRequete(
  requete: Ec2BeamVerificationRequest | null | undefined, strict: boolean,
): ChampsDeVariante {
  const nonRepris: NonRepris[] = [];
  if (!requete) {
    return {
      champs: { ...CHAMPS_INITIAUX, strict },
      provenances: {},
      nonRepris: [{
        champ: "*",
        motif: "la requête gelée de l'étude d'origine n'est pas relisible dans "
          + "la forme du contrat : aucune entrée n'a pu être reprise",
      }],
    };
  }
  const grandeur = (
    champ: keyof ChampsEtude, q: { value: number; unit: string } | null | undefined,
    unites: string[],
  ): string => {
    if (!q || typeof q.value !== "number" || !Number.isFinite(q.value)) {
      nonRepris.push({ champ, motif: `${champ} : absent de la requête gelée` });
      return "";
    }
    if (!unites.includes(q.unit)) {
      nonRepris.push({
        champ,
        motif: `${champ} : « ${q.value} ${q.unit} » n'est pas en ${unites[0]} — `
          + "saisissez la valeur convertie",
      });
      return "";
    }
    return String(q.value);
  };
  const nombreDe = (champ: keyof ChampsEtude, v: number | null | undefined): string => {
    if (typeof v !== "number" || !Number.isFinite(v)) {
      nonRepris.push({ champ, motif: `${champ} : absent de la requête gelée` });
      return "";
    }
    return String(v);
  };
  const texteDe = (champ: keyof ChampsEtude, v: string | null | undefined): string => {
    if (typeof v !== "string" || v.trim() === "") {
      nonRepris.push({ champ, motif: `${champ} : absent de la requête gelée` });
      return "";
    }
    return v;
  };
  const facultatifNombre = (v: number | null | undefined): string =>
    typeof v === "number" && Number.isFinite(v) ? String(v) : "";

  const alphas = requete.anchorage_coefficients;
  const champs: ChampsEtude = {
    element: texteDe("element", requete.element ?? "poutre"),
    b: grandeur("b", requete.geometry?.b, MM),
    h: grandeur("h", requete.geometry?.h, MM),
    d: grandeur("d", requete.geometry?.d, MM),
    l_eff: grandeur("l_eff", requete.geometry?.l_eff, MM),
    b_eff_sur_b_w: facultatifNombre(requete.b_eff_over_b_w),
    beton: texteDe("beton", requete.materials?.concrete_grade),
    acier: texteDe("acier", requete.materials?.steel_grade),
    exposition: texteDe("exposition", requete.exposure_class),
    w_max_associee: requete.w_max_associated_class ?? "",
    M_Ed: grandeur("M_Ed", requete.M_Ed, KNM),
    V_Ed: grandeur("V_Ed", requete.V_Ed, KN),
    M_char: grandeur("M_char", requete.M_char, KNM),
    M_qp: grandeur("M_qp", requete.M_qp, KNM),
    barres_nb: nombreDe("barres_nb", requete.bars?.count),
    barres_diametre: grandeur("barres_diametre", requete.bars?.diameter, MM),
    cadres_branches: nombreDe("cadres_branches", requete.links?.legs),
    cadres_diametre: grandeur("cadres_diametre", requete.links?.diameter, MM),
    cadres_espacement: grandeur("cadres_espacement", requete.links?.spacing, MM),
    enrobage: grandeur("enrobage", requete.cover, MM),
    cot_theta: nombreDe("cot_theta", requete.cot_theta),
    ancrage: grandeur("ancrage", requete.anchorage_available, MM),
    adherence: "good",
    alpha_1: alphas ? nombreDe("alpha_1", alphas.alpha_1) : "",
    alpha_2: alphas ? nombreDe("alpha_2", alphas.alpha_2) : "",
    alpha_3: alphas ? nombreDe("alpha_3", alphas.alpha_3) : "",
    alpha_4: alphas ? nombreDe("alpha_4", alphas.alpha_4) : "",
    alpha_5: alphas ? nombreDe("alpha_5", alphas.alpha_5) : "",
    alpha_6: alphas ? nombreDe("alpha_6", alphas.alpha_6) : "",
    phi_creep: nombreDe("phi_creep", requete.phi_creep),
    systeme: texteDe("systeme", requete.structural_system),
    cloisons_fragiles: requete.supports_brittle_partitions === true,
    strict,
  };
  //: LES CONDITIONS D'ADHÉRENCE: deux valeurs possibles, et rien d'autre. Une
  //: troisième ne se reprend pas — elle se ressaisit.
  const adherence = requete.bond_condition ?? "good";
  if (adherence === "good" || adherence === "poor") champs.adherence = adherence;
  else nonRepris.push({ champ: "adherence",
                        motif: `adherence : « ${adherence} » n'est ni « good » ni « poor »` });
  //: LA PROVENANCE GELEE, reprise pour les champs repris tels quels.
  const provenances: Provenances = {};
  for (const [chemin, p] of Object.entries(requete.provenance ?? {})) {
    const cle = CHAMP_DE_CHEMIN[chemin];
    if (cle && p && champs[cle].trim() !== "") {
      provenances[cle] = { chemin, provenance: p, valeur: champs[cle].trim() };
    }
  }
  return { champs, nonRepris, provenances };
}
