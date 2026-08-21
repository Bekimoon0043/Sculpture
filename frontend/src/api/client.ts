// API client — the exact paths the backend serves (app/api/routes_geometry.py).
// All geometry traffic goes through the vite dev proxy (/api -> backend).

export interface ParameterSpec {
  unit: string;
  default: number | string;
  min: number | null;
  max: number | null;
  type: "int" | "float" | "str";
  notes?: string;
}

export interface MaterialInfo {
  name: string;
  category: string;
  density_kg_per_m3: number;
  min_wall_mm: number;
}

export interface DefaultsResponse {
  parameters: Record<string, ParameterSpec>;
  materials: Record<string, MaterialInfo>;
}

export interface PrimitiveInfo {
  purpose: string;
  can_parent_stack: boolean;
  can_parent_insert: boolean;
  parameters: Record<string, ParameterSpec>;
}

export interface GateProfileInfo {
  name: string;
  signed_off: boolean;
  site_altitude_m: number;
  /** Thresholds still unsupplied — these produce `needs_input` rows. */
  unset_thresholds: string[];
}

export interface ExportFormatInfo {
  format: string;
  tier: string;
  purpose: string;
}

export interface AssemblyDefaultsResponse {
  schema: "assembly_defaults_v1";
  primitives: Record<string, PrimitiveInfo>;
  materials: Record<string, MaterialInfo>;
  joint_types: string[];
  gate_profiles: {
    version: number;
    default: string;
    profiles: Record<string, GateProfileInfo>;
  };
  export_formats: ExportFormatInfo[];
}

/**
 * Four statuses, never three. `needs_input` means the check could NOT be
 * evaluated — it is not a warning and it is never a pass.
 */
export type GateStatus = "pass" | "warn" | "fail" | "needs_input";

export interface CheckRow {
  check: string;
  value: unknown;
  passed: boolean;
  status?: GateStatus;
  on_violation?: "warn" | "fail";
  /** Provenance of `limit` — where the threshold came from (Rule 11). */
  basis?: string;
  units?: string | null;
  limit?: unknown;
  message?: string;
}

export interface Validation {
  watertight: boolean;
  winding_consistent: boolean;
  volume_mm3: number;
  surface_area_mm2: number;
  euler_number: number;
  bounds_mm: number[];
  degenerate_face_count: number;
  face_count: number;
  mass_kg: number;
  passed: boolean;
  rows?: CheckRow[];
  [key: string]: unknown;
}

export interface BuildResponse {
  spec_hash: string;
  seed: number;
  step_sha256: string;
  glb_sha256: string;
  glb_url: string;
  step_url: string;
  luxexchange_url?: string;
  build_ms: number;
  validation: Validation;
}

export interface ValidationGate {
  schema: string;
  gate_name: string;
  status: GateStatus;
  gate_profile_id?: string;
  gate_profiles_version?: number;
  profile_signed_off?: boolean;
  checks: CheckRow[];
  rows?: CheckRow[];
}

export interface AssemblyBuildResponse extends BuildResponse {
  design_id: string;
  overall_status: GateStatus;
  passed: boolean;
  gate_profile_id: string;
  exports_url: string;
  manifest: {
    schema: "assembly_manifest_v1";
    elements: Array<Record<string, unknown>>;
    joints: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  validation_gates: Record<string, ValidationGate>;
}

export interface LatestValidationResponse {
  created_at?: string;
  design_id: string;
  gate_name: string;
  /** True only on a clean pass. A warn is not a pass, nor is needs_input. */
  passed: boolean;
  overall_status?: GateStatus;
  blocking?: boolean;
  gate_statuses?: Record<string, GateStatus>;
  validation: Validation;
  gates?: Record<string, ValidationGate>;
}

export interface ExportEntry {
  format: string;
  status: "included" | "failed" | "unavailable" | "impossible" | null;
  path: string | null;
  sha256: string | null;
  bytes: number | null;
  error: string | null;
  /** "cad" | "mesh" | "render" | "none" | "package" — what the file is FOR. */
  tier?: string;
  purpose?: string;
  filename?: string;
  /** Present only when the file exists and can actually be fetched. */
  download_url?: string | null;
}

export interface ExportsResponse {
  design_id: string;
  package_built: boolean;
  package_bytes?: number | null;
  content_digest: string | null;
  exports: ExportEntry[];
  counts: Record<string, number>;
  luxexchange_url: string;
  catalog: ExportFormatInfo[];
  last_job: { status: string; halt_reason: string | null } | null;
}

/** URL for ONE exported file. Only valid once that format is `included`. */
export function exportFileUrl(designId: string, format: string): string {
  return `/api/geometry/assembly/${designId}/exports/${format}/download`;
}

export class ApiError extends Error {
  violations: string[] | null;
  constructor(message: string, violations: string[] | null = null) {
    super(message);
    this.violations = violations;
  }
}

async function parseOrThrow(resp: Response): Promise<any> {
  if (resp.ok) return resp.json();
  let detail: any = null;
  try {
    detail = (await resp.json()).detail;
  } catch {
    /* non-JSON error body */
  }
  if (resp.status === 422 && detail && Array.isArray(detail.violations)) {
    throw new ApiError("parameter constraints violated", detail.violations);
  }
  throw new ApiError(
    `HTTP ${resp.status}: ${typeof detail === "string" ? detail : resp.statusText}`
  );
}

export async function getDefaults(): Promise<DefaultsResponse> {
  return parseOrThrow(await fetch("/api/geometry/cascade/defaults"));
}

export async function postBuild(
  parameters: Record<string, number | string>,
  seed: number
): Promise<BuildResponse> {
  return parseOrThrow(
    await fetch("/api/geometry/cascade/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters, seed }),
    })
  );
}

export async function getLatestValidation(): Promise<LatestValidationResponse | null> {
  const resp = await fetch("/api/geometry/cascade/latest/validation");
  if (resp.status === 404) return null;
  return parseOrThrow(resp);
}

export function latestGlbUrl(cacheBuster: number): string {
  return `/api/geometry/cascade/latest.glb?ts=${cacheBuster}`;
}

export async function getAssemblyDefaults(): Promise<AssemblyDefaultsResponse> {
  return parseOrThrow(await fetch("/api/geometry/assembly/defaults"));
}

export async function postAssemblyBuild(
  elements: Array<Record<string, unknown>>,
  fabrication: Record<string, number | string> | null,
  seed: number,
  gateProfileId?: string
): Promise<AssemblyBuildResponse> {
  return parseOrThrow(
    await fetch("/api/geometry/assembly/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        elements,
        fabrication,
        seed,
        gate_profile_id: gateProfileId ?? null,
      }),
    })
  );
}

/** Build the export package. POST — this is the only call that writes. */
export async function postAssemblyExports(
  designId: string
): Promise<ExportsResponse & { content_digest: string }> {
  return parseOrThrow(
    await fetch(`/api/geometry/assembly/${designId}/exports`, { method: "POST" })
  );
}

/** Read export status. Never writes — safe to poll. */
export async function getAssemblyExports(
  designId?: string
): Promise<ExportsResponse | null> {
  const path = designId
    ? `/api/geometry/assembly/${designId}/exports`
    : "/api/geometry/assembly/latest/exports";
  const resp = await fetch(path);
  if (resp.status === 404) return null;
  return parseOrThrow(resp);
}

export async function getLatestAssemblyValidation(): Promise<LatestValidationResponse | null> {
  const resp = await fetch("/api/geometry/assembly/latest/validation");
  if (resp.status === 404) return null;
  return parseOrThrow(resp);
}

export function latestAssemblyGlbUrl(cacheBuster: number): string {
  return `/api/geometry/assembly/latest.glb?ts=${cacheBuster}`;
}

export const latestAssemblyStepUrl = "/api/geometry/assembly/latest.step";
export const latestAssemblyLuxexchangeUrl =
  "/api/geometry/assembly/latest/luxexchange.zip";

// ---------------------------------------------------------------------------
// Council transcript API (Phase 3, build step 3)
// ---------------------------------------------------------------------------

export interface CouncilSessionSummary {
  id: string;
  created_at: string;
  brief_text: string;
  status: string;
  total_cost_usd: number;
  pricing_version: string;
  arbiter_confidence: number | null;
  degraded: number;
  corrected: number;
  synthetic: boolean;
}

export interface CouncilCall {
  id: string;
  ts: string;
  role: string;
  side: string;
  provider: string;
  model: string;
  prompt: string;
  response: string;
  tokens_in: number;
  tokens_out: number;
  cached_input_tokens: number;
  cache_write_input_tokens: number;
  latency_ms: number;
  cost_usd: number;
  pricing_version: string;
  status: string;
  error: string | null;
}

export interface CouncilSpec {
  id: string;
  provider: string;
  alternative_no: number;
  spec_json: string;
  spec_hash: string;
  seed: number;
  schema_valid: number;
}

export interface CouncilPayloadRow {
  id: string;
  provider: string;
  side: string;
  payload_json: string;
}

export interface ArbiterDecision {
  id: string;
  chosen_spec_ids_json: string;
  confidence: number;
  rationale: string;
  disagreement_register_json: string;
  binding: number;
}

export interface CostRollup {
  total_cost_usd: number;
  by_role: Record<string, number>;
  by_provider: Record<string, number>;
  cache_savings_usd: number;
  session_cap_usd: number;
  day_cap_usd: number;
  call_count: number;
  pricing_version: string;
}

export interface GeneratedProgram {
  id: string;
  spec_id: string;
  attempt_no: number;
  provider: string;
  model: string;
  status: string;
  rejection_reason: string | null;
  error_digest: string | null;
  program_hash: string;
  artifacts_json: string | null;
  validation_json: string | null;
}

export interface CouncilSessionDetail {
  session: CouncilSessionSummary & {
    started_at: string;
    ended_at: string | null;
  };
  calls: CouncilCall[];
  specs: CouncilSpec[];
  programs?: GeneratedProgram[];
  engineering_reviews: CouncilPayloadRow[];
  defect_lists: CouncilPayloadRow[];
  arbiter_decision: ArbiterDecision | null;
  cost_rollup: CostRollup;
}

export async function getCouncilSessions(): Promise<{
  count: number;
  sessions: CouncilSessionSummary[];
}> {
  return parseOrThrow(await fetch("/api/council/sessions"));
}

export async function getCouncilSession(
  id: string
): Promise<CouncilSessionDetail> {
  return parseOrThrow(await fetch(`/api/council/sessions/${id}`));
}

export async function loadDemoSession(): Promise<{
  session_id: string;
  created: boolean;
  synthetic: boolean;
  note: string;
}> {
  return parseOrThrow(
    await fetch("/api/council/demo-session", { method: "POST" })
  );
}
