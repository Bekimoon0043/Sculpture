import type { ParameterSpec } from "../api/client";

export type ParameterGroup =
  | "Form"
  | "Water & services"
  | "Material"
  | "Construction"
  | "Advanced";

export interface PresentedParameter {
  name: string;
  spec: ParameterSpec;
  label: string;
  group: ParameterGroup;
  advanced: boolean;
}

const LABELS: Record<string, string> = {
  basin_diameter_mm: "Basin diameter",
  basin_height_mm: "Basin height",
  basin_wall_mm: "Basin wall",
  bore_mm: "Service bore",
  column_diameter_mm: "Column diameter",
  column_height_mm: "Column height",
  column_wall_mm: "Column wall",
  diameter_mm: "Diameter",
  dish_depth_mm: "Dish depth",
  dish_spacing_mm: "Tier spacing",
  floor_mm: "Floor thickness",
  height_mm: "Height",
  min_clearance_mm: "Insert clearance",
  nozzle_bore_mm: "Nozzle bore",
  taper_deg: "Taper",
  tier_count: "Number of tiers",
  top_diameter_mm: "Top diameter",
  wall_mm: "Wall thickness",
  material_id: "Material",
};

const FORM_WORDS = /diameter|height|width|depth|radius|taper|tier|spacing|profile|count/;
const WATER_WORDS = /water|flow|nozzle|bore|jet|fall|dish|clearance|service/;
const CONSTRUCTION_WORDS = /wall|floor|thickness|overlap|lift|mass|handling|tolerance/;

function fallbackLabel(name: string): string {
  const withoutUnit = name.replace(/_(mm|deg|kg|m3|pct|count)$/g, "");
  const words = withoutUnit.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function groupFor(name: string): ParameterGroup {
  if (name === "material_id") return "Material";
  if (CONSTRUCTION_WORDS.test(name)) return "Construction";
  if (WATER_WORDS.test(name)) return "Water & services";
  if (FORM_WORDS.test(name)) return "Form";
  return "Advanced";
}

export function presentParameters(
  params: Record<string, ParameterSpec>
): PresentedParameter[] {
  return Object.entries(params).map(([name, spec]) => {
    const group = groupFor(name);
    return {
      name,
      spec,
      label: LABELS[name] ?? fallbackLabel(name),
      group,
      advanced: group === "Construction" || group === "Advanced",
    };
  });
}

