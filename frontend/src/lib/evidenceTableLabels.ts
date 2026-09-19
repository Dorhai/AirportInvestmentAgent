export const SCORE_TABLE_COLUMNS = [
  { key: "opportunity", label: "Opportunity", shortLabel: "Opp" },
  { key: "demand", label: "Demand growth", shortLabel: "Dem" },
  { key: "congestion", label: "Congestion", shortLabel: "Cong" },
  { key: "delay", label: "Delay pressure", shortLabel: "Del" },
  { key: "capacity", label: "Capacity pressure", shortLabel: "Cap" },
];

export const METRICS_INPUT_COLUMNS: {
  key: string;
  label: string;
  align: "left" | "right";
  className?: string;
}[] = [
  {
    key: "code",
    label: "Airport",
    align: "left",
    className: "w-16",
  },
  {
    key: "passengers",
    label: "Passengers",
    align: "right",
  },
  {
    key: "operations",
    label: "Operations / year",
    align: "right",
  },
  {
    key: "delay_pct",
    label: "Delayed flights %",
    align: "right",
  },
  {
    key: "avg_delay",
    label: "Avg delay (min)",
    align: "right",
  },
  {
    key: "long_haul",
    label: "Long-haul flights",
    align: "right",
  },
];