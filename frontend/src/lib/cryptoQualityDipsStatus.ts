export const CRYPTO_QUALITY_DIPS_SCHEMA_VERSION = "E72_CRYPTO_QUALITY_DIPS_PUBLIC_V1" as const;

export type CryptoQualityDipsSeverity = "INFO" | "WARNING" | "CRITICAL";
export type CryptoQualityDipsDisplayState = "NO_EVIDENCE" | "COLLECTING" | "RESEARCH_GATES_MET" | "REVIEW_REQUIRED" | "UNAVAILABLE";

export type CryptoQualityDipsViewModel = {
  schemaVersion: typeof CRYPTO_QUALITY_DIPS_SCHEMA_VERSION;
  displayState: CryptoQualityDipsDisplayState;
  severity: CryptoQualityDipsSeverity;
  status: string;
  operatorAttentionRequired: boolean;
  chainState: string;
  recoveryStatus: string;
  readiness: { gatesMet: boolean; totalObservations: number; validObservations: number; validFraction: number; distinctObservationDays: number };
  authorityLocked: true;
};

export type CryptoQualityDipsConsumerResult =
  | { ok: true; value: CryptoQualityDipsViewModel }
  | { ok: false; value: CryptoQualityDipsViewModel; reason: string };

const FAIL_CLOSED: CryptoQualityDipsViewModel = {
  schemaVersion: CRYPTO_QUALITY_DIPS_SCHEMA_VERSION,
  displayState: "UNAVAILABLE",
  severity: "CRITICAL",
  status: "PUBLIC_STATUS_UNAVAILABLE",
  operatorAttentionRequired: true,
  chainState: "UNKNOWN",
  recoveryStatus: "UNKNOWN",
  readiness: { gatesMet: false, totalObservations: 0, validObservations: 0, validFraction: 0, distinctObservationDays: 0 },
  authorityLocked: true,
};

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function finiteNonNegative(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}
function severity(value: unknown): value is CryptoQualityDipsSeverity {
  return value === "INFO" || value === "WARNING" || value === "CRITICAL";
}
function displayState(status: string, level: CryptoQualityDipsSeverity): CryptoQualityDipsDisplayState {
  if (level === "CRITICAL" || status === "INTEGRITY_REVIEW_REQUIRED" || status === "LEGACY_REVIEW_REQUIRED") return "REVIEW_REQUIRED";
  if (status === "NO_EVIDENCE_YET") return "NO_EVIDENCE";
  if (status === "RESEARCH_GATES_MET") return "RESEARCH_GATES_MET";
  return "COLLECTING";
}

export function consumeCryptoQualityDipsStatus(payload: unknown): CryptoQualityDipsConsumerResult {
  if (!record(payload)) return { ok: false, value: FAIL_CLOSED, reason: "MALFORMED_PAYLOAD" };
  if (payload.schema_version !== CRYPTO_QUALITY_DIPS_SCHEMA_VERSION) return { ok: false, value: FAIL_CLOSED, reason: "UNSUPPORTED_SCHEMA_VERSION" };
  if (payload.surface !== "CRYPTO_QUALITY_DIPS_RESEARCH" || payload.read_only !== true) return { ok: false, value: FAIL_CLOSED, reason: "INVALID_PUBLIC_BOUNDARY" };

  const operator = payload.operator, readiness = payload.readiness, authority = payload.authority;
  if (!record(operator) || !record(readiness) || !record(authority)) return { ok: false, value: FAIL_CLOSED, reason: "MISSING_REQUIRED_SECTION" };

  const requiredAuthority = ["scoring_active","paper_entry_authority","execution_authority","live_capital_allowed","repair_action_available","mutation_action_available"];
  if (requiredAuthority.some((key) => authority[key] !== false)) return { ok: false, value: FAIL_CLOSED, reason: "AUTHORITY_BOUNDARY_VIOLATION" };

  if (
    typeof operator.status !== "string" || !severity(operator.severity) ||
    typeof operator.operator_attention_required !== "boolean" || typeof operator.chain_state !== "string" ||
    typeof operator.recovery_status !== "string" || typeof readiness.gates_met !== "boolean" ||
    !finiteNonNegative(readiness.total_observations) || !finiteNonNegative(readiness.valid_observations) ||
    !finiteNonNegative(readiness.valid_fraction) || readiness.valid_fraction > 1 ||
    !finiteNonNegative(readiness.distinct_observation_days)
  ) return { ok: false, value: FAIL_CLOSED, reason: "MALFORMED_REQUIRED_FIELD" };

  return { ok: true, value: {
    schemaVersion: CRYPTO_QUALITY_DIPS_SCHEMA_VERSION,
    displayState: displayState(operator.status, operator.severity),
    severity: operator.severity,
    status: operator.status,
    operatorAttentionRequired: operator.operator_attention_required,
    chainState: operator.chain_state,
    recoveryStatus: operator.recovery_status,
    readiness: {
      gatesMet: readiness.gates_met,
      totalObservations: readiness.total_observations,
      validObservations: readiness.valid_observations,
      validFraction: readiness.valid_fraction,
      distinctObservationDays: readiness.distinct_observation_days,
    },
    authorityLocked: true,
  }};
}
