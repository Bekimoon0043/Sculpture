// API client — the exact paths the backend serves (app/api/routes_geometry.py).
// All geometry traffic goes through the vite dev proxy (/api -> backend).

// PR-1 (ADR-059): fabrication.max_module_m may be a scalar (the Designer's
// deliberate CUBIC envelope) or the Design Spec's per-axis {x, y, z}.
export type FabricationValue =
  | number
  | string
  | { x: number; y: number; z: number };

export interface ParameterSpec {
  unit: string;
  default: number | string;
  min: number | null;
  max: number | null;
  type: "int" | "float" | "str";
  optional?: boolean;
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
  project_id: string | null;
  parent_design_id: string | null;
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

export interface AssemblyPreview {
  objectUrl: string;
  previewHash: string;
  buildMs: number;
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
  fabrication: Record<string, FabricationValue> | null,
  seed: number,
  gateProfileId?: string,
  intakeId?: string,
  projectId?: string,
  parentDesignId?: string
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
        intake_id: intakeId ?? null,
        project_id: projectId ?? null,
        parent_design_id: parentDesignId ?? null,
      }),
    })
  );
}

export async function postAssemblyPreview(
  elements: Array<Record<string, unknown>>,
  fabrication: Record<string, FabricationValue> | null,
  seed: number,
  signal?: AbortSignal
): Promise<AssemblyPreview> {
  const response = await fetch("/api/geometry/assembly/preview.glb", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ elements, fabrication, seed }),
    signal,
  });
  if (!response.ok) await parseOrThrow(response);
  const blob = await response.blob();
  return {
    objectUrl: URL.createObjectURL(blob),
    previewHash: response.headers.get("X-LuxuryForm-Preview-Hash") ?? "",
    buildMs: Number(response.headers.get("X-LuxuryForm-Build-Ms") ?? 0),
  };
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

export async function getDesignValidation(
  designId: string
): Promise<LatestValidationResponse | null> {
  const resp = await fetch(`/api/geometry/assembly/${designId}/validation`);
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
// Designer workspace API (Phase 14)
// ---------------------------------------------------------------------------

/** Pickable per-element scene — node names are element_ids. */
export function latestSceneGlbUrl(cacheBuster: number): string {
  return `/api/geometry/assembly/latest/scene.glb?ts=${cacheBuster}`;
}

export function designSceneGlbUrl(designId: string): (cacheBuster: number) => string {
  return (cacheBuster) =>
    `/api/geometry/assembly/${designId}/scene.glb?ts=${cacheBuster}`;
}

export interface DesignSummary {
  design_id: string;
  project_id: string | null;
  parent_design_id: string | null;
  created_at: string;
  spec_hash: string;
  seed: number;
  element_count: number;
  primitives: string[];
  element_ids: string[];
  total_mass_kg: number | null;
  overall_status: GateStatus | null;
  glb_url: string;
  scene_glb_url: string;
}

export async function listDesigns(
  limit = 50,
  projectId?: string | null,
  ungrouped = false
): Promise<{ count: number; designs: DesignSummary[] }> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (projectId) query.set("project_id", projectId);
  if (ungrouped) query.set("ungrouped", "true");
  return parseOrThrow(
    await fetch(`/api/geometry/assembly/designs?${query}`)
  );
}

export interface ProjectSummary {
  project_id: string;
  created_at: string;
  name: string;
  brief_text: string;
  status: "open" | "archived";
  variant_count: number;
}

export async function listProjects(): Promise<{
  count: number;
  projects: ProjectSummary[];
}> {
  return parseOrThrow(await fetch("/api/geometry/assembly/projects"));
}

export async function createProject(
  name: string,
  briefText = ""
): Promise<ProjectSummary> {
  return parseOrThrow(
    await fetch("/api/geometry/assembly/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, brief_text: briefText }),
    })
  );
}

export interface ManifestElement {
  element_id: string;
  primitive: string;
  material_id: string;
  parameters: Record<string, number | string>;
  placement_mm: { x: number; y: number; z: number };
  volume_mm3: number;
  mass_kg: number;
  bbox_mm: number[];
  bbox_min_mm: number[];
  bbox_max_mm: number[];
  centroid_mm: { x: number; y: number; z: number };
}

export interface DesignManifestResponse {
  created_at: string;
  design_id: string;
  project_id: string | null;
  parent_design_id: string | null;
  spec_hash: string;
  seed: number;
  manifest: {
    schema: string;
    elements: ManifestElement[];
    joints: Array<Record<string, unknown>>;
    total_mass_kg: number;
    [key: string]: unknown;
  };
  request: {
    elements: Array<Record<string, unknown>>;
    fabrication: Record<string, FabricationValue>;
    seed: number;
    gate_profile_id: string;
    intake_id: string | null;
    [key: string]: unknown;
  };
  artifacts: Record<string, string>;
}

export async function getDesignManifest(
  designId: string
): Promise<DesignManifestResponse> {
  return parseOrThrow(
    await fetch(`/api/geometry/assembly/${designId}/manifest`)
  );
}

// --- render jobs (Phase 9B worker) -----------------------------------------

export interface RenderJobView {
  name: string;
  path?: string;
  camera?: string;
  resolution?: number;
}

export interface RenderJob {
  id: string;
  design_id?: string;
  status: string;
  error?: string | null;
  views: RenderJobView[];
  total_s?: number;
}

export async function postRenderJob(designId: string): Promise<RenderJob> {
  return parseOrThrow(
    await fetch("/api/render/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ design_id: designId }),
    })
  );
}

/** Blocks server-side up to ~30 s while the job runs — poll, don't spam. */
export async function getRenderJob(jobId: string): Promise<RenderJob> {
  return parseOrThrow(await fetch(`/api/render/jobs/${jobId}`));
}

export function renderViewUrl(jobId: string, viewName: string): string {
  return `/api/render/jobs/${jobId}/views/${viewName}`;
}

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
  /** PR-2 (ADR-061): the $5 binds per LOGICAL run, renamed from
   *  session_cap_usd by operator ruling 2026-08-28. */
  run_cap_usd: number;
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

// ---------------------------------------------------------------------------
// Brief intake API (Phase 12)
// ---------------------------------------------------------------------------

export interface SourcedField {
  value: unknown;
  source: "operator" | "parsed" | "default" | "unknown";
  quote?: string | null;
}

export interface IntakeWire {
  schema: string;
  [section: string]: Record<string, SourcedField> | string;
}

export interface IntakeReadiness {
  ready_for_council: boolean;
  missing_by_tier: Record<string, Array<{ field: string; why: string }>>;
  tier_labels: Record<string, string>;
  note: string;
}

export interface IntakeResponse {
  id: string;
  created_at: string;
  updated_at: string;
  status: "draft" | "confirmed";
  brief_text: string;
  council_session_id: string | null;
  intake: IntakeWire;
  readiness: IntakeReadiness;
  summary_block: string;
  /** Gate-profile thresholds this intake supplies, keyed by profile field. */
  site_overrides: Record<string, number>;
  parse?: {
    applied: number;
    kept_operator: number;
    dropped: number;
    provider: string;
    model: string;
    cost_usd: number;
  };
}

export async function createIntake(
  briefText: string,
  fields: Record<string, unknown> = {}
): Promise<IntakeResponse> {
  return parseOrThrow(
    await fetch("/api/intake", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief_text: briefText, fields }),
    })
  );
}

export async function getLatestIntake(): Promise<IntakeResponse | null> {
  const resp = await fetch("/api/intake/latest");
  if (resp.status === 404) return null;
  return parseOrThrow(resp);
}

export async function updateIntake(
  id: string,
  fields: Record<string, unknown>
): Promise<IntakeResponse> {
  return parseOrThrow(
    await fetch(`/api/intake/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields }),
    })
  );
}

export async function parseIntake(id: string): Promise<IntakeResponse> {
  return parseOrThrow(
    await fetch(`/api/intake/${id}/parse`, { method: "POST" })
  );
}

export async function confirmIntake(id: string): Promise<IntakeResponse> {
  return parseOrThrow(
    await fetch(`/api/intake/${id}/confirm`, { method: "POST" })
  );
}

// ---------------------------------------------------------------------------
// DesignDNA API (Phase 11)
// ---------------------------------------------------------------------------

export interface PrecedentTags {
  materials: string[];
  primitives: string[];
  height_m: number;
  footprint_m: number;
  total_mass_kg: number;
  has_water: boolean;
  gate_profile_id: string | null;
  overall_status: string;
  total_cost_usd: number | null;
}

export interface Precedent {
  id: string;
  created_at: string;
  design_id: string;
  status: "active" | "archived" | "deleted";
  accepted_by?: string;
  acceptance_note?: string;
  content_digest?: string;
  tags?: PrecedentTags;
  match_reasons?: string[];
  detail?: string;
}

export async function acceptDesign(req: {
  design_id: string;
  accepted_by: string;
  acceptance_note: string;
}): Promise<Precedent> {
  return parseOrThrow(
    await fetch("/api/dna/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    })
  );
}

export async function listPrecedents(
  includeArchived = false
): Promise<{ precedents: Precedent[]; count: number }> {
  return parseOrThrow(
    await fetch(`/api/dna?include_archived=${includeArchived}`)
  );
}

export async function searchPrecedents(
  criteria: Record<string, string | number | boolean>
): Promise<{ precedents: Precedent[]; count: number }> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(criteria)) {
    params.set(key, String(value));
  }
  return parseOrThrow(await fetch(`/api/dna/search?${params}`));
}

export async function archivePrecedent(id: string): Promise<Precedent> {
  return parseOrThrow(await fetch(`/api/dna/${id}/archive`, { method: "POST" }));
}

export async function deletePrecedent(id: string): Promise<Precedent> {
  return parseOrThrow(await fetch(`/api/dna/${id}`, { method: "DELETE" }));
}

// ---------------------------------------------------------------------------
// Operations API (Phase 13 slice A)
// ---------------------------------------------------------------------------

export interface OpsJob {
  id: string;
  ts: string;
  job_type: string;
  status: string;
  session_id: string;
  state: Record<string, unknown>;
  halt_reason: string | null;
  failure_class: string | null;
}

export interface OpsCosts {
  total_usd: number;
  call_count: number;
  by_purpose: Record<string, { cost_usd: number; calls: number; errors: number }>;
  by_provider: Record<string, { cost_usd: number; calls: number; errors: number }>;
  by_day: Record<string, number>;
  error_calls: { count: number; cost_usd: number };
  reconciliation: {
    checked_sessions: number;
    mismatches: Array<{
      session_id: string;
      calls_usd: number;
      ledger_usd: number | null;
      finding: string;
    }>;
    clean: boolean;
  };
  budget_events: Array<{
    ts: string;
    session_id: string;
    event_type: string;
    detail: string;
  }>;
}

export async function getOpsJobs(): Promise<{ jobs: OpsJob[]; count: number }> {
  return parseOrThrow(await fetch("/api/ops/jobs"));
}

export async function getOpsCosts(): Promise<OpsCosts> {
  return parseOrThrow(await fetch("/api/ops/costs"));
}

export async function getHealth(): Promise<boolean> {
  try {
    const resp = await fetch("/api/health");
    return resp.ok;
  } catch {
    return false;
  }
}
