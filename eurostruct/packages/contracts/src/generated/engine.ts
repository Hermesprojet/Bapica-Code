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

/** The decision was spent. Exactly once: a replay is refused. */
export interface AuthorityDecisionConsumed {
  consumed: boolean;
  decision_id: string;
}

/** A decision now exists, and it is PENDING. Nothing is confirmed yet. */
export interface AuthorityDecisionCreated {
  decision_id: string;
}

/** What the decision is about. Never who proposes it. */
export interface AuthorityDecisionRequest {
  /** ISO 3166-1 alpha-2 code of the national annex concerned. */
  country_code: string;
  /** Edition of the standard the decision is scoped to. */
  edition: string;
  /** Tenant scope, or null for a referential-wide decision. */
  org_id?: string | null;
  part: string;
  permission: string;
  /** Human-readable motive. A datum, never a proof. */
  reason: string;
  /** The dossier presented to both engineers. Required when subject_kind is 'ndp_parameter': without it the decision could be approved and consumed without producing any normative effect. */
  review_package?: AuthorityReviewPackage | null;
  standard_family: string;
  /** Identifier of the subject the decision bears on. */
  subject_id: string;
  /** Nature of the subject, e.g. 'ndp_parameter'. */
  subject_kind: string;
}

/** The dossier the two engineers are shown, frozen at proposal time. WHY IT TRAVELS WITH THE PROPOSAL AND NOT WITH THE APPROVAL. "B approved" means nothing unless the record says *what* B approved. The dossier is written once, at proposal, and PostgreSQL freezes it: A and B therefore approve byte-identical content, and the effect produced at consumption is that content and no other. NO DIGEST IS CARRIED HERE. The server recomputes every one of them from the payloads below. Accepting a digest would let a caller announce a fingerprint that does not summarise what is stored. */
export interface AuthorityReviewPackage {
  canonicalization_version: string;
  digest_algorithm: string;
  evidence_payload: string;
  implementation_payload: string;
  normative_spec_payload: string;
  /** Exact parameter identifier, e.g. 'EN 1992-1-1:alpha_cc'. */
  rule_id: string;
  stack_payload: string;
  /** What the reviewers declare they read and checked. */
  statement: string;
}

export interface BarRowDTO {
  count: number;
  /** Nominal bar diameter, mm */
  diameter: number;
  /** Developed length, mm */
  length?: number | null;
  mark: string;
}

/** Input of the DXF cross-section generator. Kept as the **drawing** contract: it knows a geometry and bars, and nothing about whether they were verified. :class:`Ec2BeamSectionRequest` is what a client should send; this one is what the renderer consumes once the check has passed. */
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

/** One reason a calculation cannot proceed — TICKET 1.3. */
export interface BlockingParameterDTO {
  clause?: string | null;
  detail: string;
  key: string;
  national_annex_reference?: string | null;
  parameter_name: string;
  /** Machine-readable cause, for CI. */
  reason: "annex_missing" | "missing" | "pending_verification" | "deprecated";
  standard: string;
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
  /** Project reference date (ISO 8601) used to select the edition of the National Annex in force. Pin it on a real project so the calculation stays reproducible after a newer edition is published. Defaults to today. */
  as_of?: string | null;
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

/** Verify the chosen bars, **then** draw them — never the reverse. WHY THE CALCULATION TRAVELS WITH THE DRAWING REQUEST ----------------------------------------------------- Measured on 30/08: the interface sent a hard-coded 300 x 500 to the drawing endpoint whatever section had just been calculated. The engineer received a plan of a beam that was never verified, carrying the mandatory notice and their own element mark. Nothing could catch it, because the drawing endpoint had no way to know what had been calculated: it was handed a geometry and drew it, correctly. Sending the **verified request itself** removes the gap by construction — the drawn section and the checked section are the same object, and no caller can hold two of them. ``A_s_provided`` is deliberately absent: it is **computed here** from the bars, so that no client has to, and so that none can claim an area its bars do not have. */
export interface Ec2BeamSectionRequest {
  calculation: Ec2BeamFlexureRequest;
  date?: string;
  exposure_class?: string;
  index?: string;
  plot_scale?: number;
  reinforcement: ReinforcementChoiceDTO;
}

/** A refusal. The API returns this with HTTP 422, never a partial result. */
export interface EngineErrorDTO {
  clause?: string | null;
  detail: string;
  /** Machine-readable class of refusal. */
  error: "out_of_validation_domain" | "national_annex_incomplete" | "unverified_national_parameter" | "deprecated_national_parameter" | "inconsistent_input" | "unit_error" | "reinforcement_not_verified";
  preflight?: PreflightReportDTO | null;
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

/** One published National Annex document, at one edition. */
export interface NationalAnnexDTO {
  country_code: string;
  edition: string;
  effective_from: string;
  effective_to?: string | null;
  reference: string;
  source_official: string;
  source_url_or_doc_id?: string | null;
  standard: string;
}

/** One national parameter, at one version. Carries its own provenance so the note de calcul can print the annex reference, the edition and who checked it, next to the value. */
export interface NdpEntryDTO {
  clause: string;
  country_code: string;
  description: string;
  edition: string;
  effective_from: string;
  effective_to?: string | null;
  en_recommended?: number | null;
  key: string;
  national_annex_reference: string;
  notes?: string | null;
  parameter_name: string;
  parameter_value: number | null;
  part: string;
  /** sha256 of the deposited document the value was read from. */
  source_doc_id?: string | null;
  source_official: string;
  /** Page of that document, as printed. */
  source_page?: number | null;
  source_type: SourceTypeDTO;
  source_url_or_doc_id?: string | null;
  standard: string;
  standard_family: string;
  unit: string;
  validation_status: ValidationStatusDTO;
  variants?: ParameterVariantDTO[];
  verified_at?: string | null;
  verified_by?: string | null;
}

/** Printed verbatim in the 'referentiel applique' section of the note. */
export interface NdpSummaryDTO {
  annexes: NationalAnnexDTO[];
  /** Project reference date used to select the edition in force. */
  as_of: string;
  country: string;
  country_name: string;
  parameters: Record<string, NdpEntryDTO>;
  region?: string | null;
  regulatory_framework: RegulatoryFrameworkDTO;
  strict: boolean;
  /** Parameters not yet confirmed against the published National Annex. */
  unverified: string[];
}

/** One branch of a parameter the National Annex makes conditional. Belgium's alpha_cc is 0,85 for axial force and bending, 1,0 otherwise. The frontend must never collapse this to one number for display without saying which case it shows. */
export interface ParameterVariantDTO {
  /** Which verification this branch applies to, matched exactly. */
  condition: string;
  /** What the annex says about this branch. */
  description: string;
  value: number;
}

/** Result of checking every required national parameter before running. Returned in full on refusal, so the user fixes the whole list in one pass. */
export interface PreflightReportDTO {
  as_of: string;
  blocking: BlockingParameterDTO[];
  country_code: string;
  ok: boolean;
  required: string[];
  strict: boolean;
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

/** What is legally binding in the country — not always the Eurocode. Interdiction 4: a Spanish project must state that the Código Estructural, the CTE and NCSE-02 are the enforceable reference. */
export interface RegulatoryFrameworkDTO {
  binding_reference: string;
  eurocode_status: string;
  notes?: string[];
  verification_regime: string;
}

/** The bars the engineer chose. Never deduced from the calculation. ``As_required`` says how much steel is needed; it says nothing about how many bars, of which diameter, arranged how. That choice is the engineer's, and this is where it enters — separately from the geometry, which comes from the calculation that was verified. */
export interface ReinforcementChoiceDTO {
  bottom: BarRowDTO[];
  /** Nominal cover c_nom, mm */
  cover: number;
  /** Link diameter, mm */
  link_diameter: number;
  link_mark?: string;
  link_spacing?: number | null;
  top?: BarRowDTO[];
}

export type SourceTypeDTO =
  | "national_annex"
  | "en_recommended"
  | "national_regulation";

/** How far a national value has been verified — see TICKET 1.1. */
export type ValidationStatusDTO =
  | "confirmed"
  | "pending_verification"
  | "deprecated"
  | "not_representable";

export interface VerificationReportDTO {
  checks: CheckDTO[];
  element: string;
  max_utilisation: number;
  passed: boolean;
}
