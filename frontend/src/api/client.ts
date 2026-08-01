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

export interface CheckRow {
  check: string;
  value: unknown;
  passed: boolean;
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
  build_ms: number;
  validation: Validation;
}

export interface LatestValidationResponse {
  created_at: string;
  design_id: string;
  gate_name: string;
  passed: boolean;
  validation: Validation;
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
