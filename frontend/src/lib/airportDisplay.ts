/** Human-readable airport label from backend catalog name + IATA code. */
export function formatAirportLabel(
  code: string,
  name?: string | null,
): string {
  const trimmed = name?.trim();
  if (trimmed) {
    return `${trimmed} (${code})`;
  }
  return code;
}
