/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by engine/scripts/export_contracts.py from the Pydantic models in
 * engine/src/eurostruct_engine/schemas/. Edit those, then re-run:
 *
 *     cd engine && python scripts/export_contracts.py
 *
 * CI fails if this file is out of date with the models.
 *
 * Every physical value crosses the wire as a QuantityDTO carrying its unit.
 * There are no bare numbers for dimensional quantities, by design.
 */

/* eslint-disable */

export interface BarRowDTO {
  count: number;
  /** Nominal bar diameter, mm */
  diameter: number;
  /** Developed length, mm */
  length?: number | null;
  mark: string;
}

/** Input of the DXF cross-section generator. */
export interface BeamSectionDrawingRequest {
  /** Width, mm */
  b: number;
  bottom?: BarRowDTO[];
  concrete_grade?: string;
  /** Nominal cover c_nom, mm */
  cover: number;
  date?: string;
  element?: string;
  exposure_class?: string;
  /** Overall depth, mm */
  h: number;
  index?: string;
  /** Link diameter, mm */
  link_diameter: number;
  link_mark?: string;
  link_spacing?: number | null;
  plot_scale?: number;
  project?: string;
  steel_grade?: string;
  top?: BarRowDTO[];
}

/** One traceable line of the calculation — see section 8.1. */
export interface CalcStepDTO {
  clause?: ClauseDTO | null;
  depends_on?: string[];
  description: string;
  formatted: string;
  latex?: string | null;
  numeric?: string | null;
  provenance?: ProvenanceDTO | null;
  symbol: string;
  unit: string;
  value: number;
}

export interface CheckDTO {
  acting: string;
  clause: ClauseDTO;
  detail?: string | null;
  name: string;
  remedy?: string | null;
  resisting: string;
  status: CheckStatusDTO;
  /** E_d / R_d. Always reported, never just 'OK'. */
  utilisation: number;
}

export type CheckStatusDTO =
  | "pass"
  | "fail"
  | "not_applicable";

export interface ClauseDTO {
  cite: string;
  clause: string;
  equation?: string | null;
  national_note?: string | null;
  standard: string;
}

export type DesignSituationDTO =
  | "persistent"
  | "transient"
  | "accidental"
  | "seismic";

/** Input of the ULS bending verification of a rectangular section. */
export interface Ec2BeamFlexureRequest {
  /** Area of the bars actually detailed. When omitted, the ULS check is made against the exact required area and its utilisation is 1,000. */
  A_s_provided?: QuantityDTO | null;
  /** Design moment from the governing EN 1990 combination. The engine does not build combinations. */
  M_Ed: QuantityDTO;
  country: "BE" | "FR" | "ES" | "DE";
  /** Element mark shown in the note. */
  element?: string;
  materials: MaterialsDTO;
  project_id: string;
  /** Origin of each input, keyed by symbol (b, h, d, M_Ed). Values extracted from a document must carry confirmed_by/confirmed_at. */
  provenance?: Record<string, ProvenanceDTO>;
  /** Sub-national region where it changes the parameters (Wallonie / Vlaanderen / Bruxelles, Land, Comunidad autonoma). */
  region?: string | null;
  section: RectangularSectionDTO;
  situation?: DesignSituationDTO;
  /** When true, an unverified National Annex parameter causes a refusal. Required for any deliverable intended to be signed; set false only for exploratory work. */
  strict_ndp?: boolean;
}

/** Output of a successful verification. A refusal is *not* represented here: it is returned as :class:`~eurostruct_engine.schemas.common.EngineErrorDTO` with HTTP 422, so a caller cannot mistake a refusal for a result. */
export interface Ec2BeamFlexureResponse {
  element: string;
  /** Stamped into the note de calcul and every drawing. */
  engine_version: string;
  journal: JournalDTO;
  ndp: NdpSummaryDTO;
  result: Ec2BeamFlexureResult;
  verification: VerificationReportDTO;
}

/** Numeric outcome. Every field is also reachable through the journal. */
export interface Ec2BeamFlexureResult {
  /** §9.2.1.1(3) */
  As_max: QuantityDTO;
  /** §9.2.1.1(1), eq. (9.1N) */
  As_min: QuantityDTO;
  As_provided: QuantityDTO;
  /** max(As_strength, As_min) */
  As_required: QuantityDTO;
  /** Area required by strength alone */
  As_strength: QuantityDTO;
  M_Rd: QuantityDTO;
  eps_s: number;
  mu: number;
  utilisation: number;
  /** Neutral axis depth */
  x: QuantityDTO;
  xi: number;
  xi_lim: number;
  /** Lever arm */
  z: QuantityDTO;
}

/** A refusal. The API returns this with HTTP 422, never a partial result. */
export interface EngineErrorDTO {
  clause?: string | null;
  detail: string;
  /** Machine-readable class of refusal. */
  error: "out_of_validation_domain" | "unverified_national_parameter" | "inconsistent_input" | "unit_error";
  what: string;
}

export interface JournalDTO {
  clauses: string[];
  steps: CalcStepDTO[];
  title: string;
}

export interface MaterialsDTO {
  /** EN 1992-1-1 Table 3.1 designation. */
  concrete_grade: string;
  /** Reinforcement designation. */
  steel_grade: string;
}

export interface NdpEntryDTO {
  clause: string;
  en_recommended?: number | null;
  source: string;
  status: NdpStatusDTO;
  unit: string;
  value: number;
}

export type NdpStatusDTO =
  | "en_recommended"
  | "na_confirmed"
  | "na_pending_verification";

/** Printed verbatim in the 'referentiel applique' section of the note. */
export interface NdpSummaryDTO {
  country: string;
  description: string;
  parameters: Record<string, NdpEntryDTO>;
  published_at: string;
  region: string | null;
  strict: boolean;
  /** Parameters not yet confirmed against the published National Annex. */
  unverified: string[];
  version: string;
}

/** Where a value came from. ``document_extraction`` values must already have been confirmed by a human before the orchestrator submits them: ``confirmed_by`` and ``confirmed_at`` are how the engine's output can state that the gate was passed. */
export interface ProvenanceDTO {
  /** [x0, y0, x1, y1] in PDF points, so the UI can highlight the source. */
  bbox?: [number, number, number, number] | null;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  detail: string;
  document_id?: string | null;
  kind: ProvenanceKindDTO;
  ndp_key?: string | null;
  page?: number | null;
}

export type ProvenanceKindDTO =
  | "user_input"
  | "document_extraction"
  | "national_annex"
  | "standard_constant"
  | "derived";

/** A physical quantity with an explicit unit. */
export interface QuantityDTO {
  /** Pint-parsable unit, e.g. 'mm', 'kN*m', 'MPa', 'dimensionless'. */
  unit: string;
  value: number;
}

/** One line of the nomenclature — section 7.2. */
export interface RebarScheduleRowDTO {
  comment?: string;
  count: number;
  diameter_mm: number;
  mark: string;
  mass_kg: number | null;
  /** Shape code per EN ISO 3766 */
  shape_code: string;
  total_length_mm: number | null;
  unit_length_mm: number | null;
}

export interface RectangularSectionDTO {
  /** Width */
  b: QuantityDTO;
  /** Effective depth to the tension reinforcement */
  d: QuantityDTO;
  /** Overall depth */
  h: QuantityDTO;
}

export interface VerificationReportDTO {
  checks: CheckDTO[];
  element: string;
  max_utilisation: number;
  passed: boolean;
}
