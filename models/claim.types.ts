export type ISODate = string;
export type ISODateTime = string;

export type ClaimStatus =
  | "new"
  | "pending_documents"
  | "investigating"
  | "coverage_review"
  | "reopened"
  | "paid"
  | "partially_paid"
  | "denied"
  | "closed_no_payment";

export type ClaimType =
  | "fire_damage"
  | "glass_breakage"
  | "smoke_damage"
  | "storm_damage"
  | "theft"
  | "water_damage";

export type ReportedBy = "broker" | "insured" | "spouse";
export type IntakeChannel = "broker_portal" | "email" | "mobile_app" | "phone";
export type CoverageDecision = "covered" | "not_covered" | "pending";
export type ResolutionOutcome = "closed_no_payment" | "denied" | "paid" | "partially_paid" | "pending";
export type PaymentMethod = "bank_transfer" | "check" | null;
export type PolicyProduct = "Condo Protect" | "Homeowners Basic" | "Homeowners Plus";
export type DocumentType =
  | "adjuster_report"
  | "claim_form"
  | "cleaning_estimate"
  | "contents_inventory"
  | "fire_report"
  | "photo_set"
  | "plumber_invoice"
  | "police_report"
  | "repair_quote"
  | "roofer_estimate"
  | "weather_report";

export interface CoverageLimits {
  dwelling_eur: number;
  contents_eur: number;
  water_damage_eur: number;
}

export interface Insured {
  full_name: string;
  email: string;
  phone: string;
  property_address: string;
}

export interface Policy {
  product: PolicyProduct;
  effective_date: ISODate;
  expiration_date: ISODate;
  deductible_eur: number;
  coverage_limits: CoverageLimits;
  endorsements: string[];
  exclusions: string[];
}

export interface ClaimIntake {
  reported_by: ReportedBy;
  channel: IntakeChannel;
  summary: string;
  cause_of_loss: string;
  initial_damage_estimate_eur: number | null;
  emergency_mitigation_completed: boolean | null;
  injuries_reported: boolean;
}

export interface ClaimDocument {
  doc_id: string;
  doc_type: DocumentType;
  title: string;
  created_at: ISODateTime;
  file_path: string | null;
}

export interface AdjusterNote {
  timestamp: ISODateTime;
  author: string;
  note: string;
}

export interface CoverageReview {
  reviewed_by: string;
  decision: CoverageDecision;
  reasoning: string | null;
  applied_deductible_eur: number;
  approved_repairs_eur: number;
  approved_contents_eur: number;
}

export interface Resolution {
  resolution_date: ISODate | null;
  outcome: ResolutionOutcome;
  gross_settlement_eur: number;
  deductible_eur: number;
  net_payment_eur: number;
  payment_method: PaymentMethod;
  customer_letter_summary: string | null;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  status: ClaimStatus;
  claim_type: ClaimType;
  loss_date: ISODate;
  reported_date: ISODate;
  insured: Insured;
  policy: Policy;
  claim_intake: ClaimIntake | null;
  documents: ClaimDocument[] | null;
  adjuster_notes: AdjusterNote[] | null;
  coverage_review: CoverageReview | null;
  resolution: Resolution | null;
  conversation_seed_questions: string[];
  data_path: string | null;
}

export type ClaimDataset = Claim[];
