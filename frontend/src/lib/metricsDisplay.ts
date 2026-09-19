import type { components } from "@/types/api.generated";

type PresentInt = components["schemas"]["Present_int_"];
type PresentFloat = components["schemas"]["Present_float_"];
type Absent = components["schemas"]["Absent"];

type DatumInt = PresentInt | Absent;
type DatumFloat = PresentFloat | Absent;

export function fmtDatum(datum: DatumFloat, fractionDigits = 1): string {
  if (datum.kind === "absent") return "---";
  return datum.value.toFixed(fractionDigits);
}

export function fmtInt(datum: DatumInt): string {
  if (datum.kind === "absent") return "---";
  return datum.value.toLocaleString();
}
