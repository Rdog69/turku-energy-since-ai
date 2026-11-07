// Shape of src/data/payload.js, written by frontend/scripts/build_data.py.
// Times on the quarter grid are indices (15 min each) from `t0`; publication times (`*_fu`, `cutoff`) are minutes from `t0`.

export type AlertKind = "spike_high" | "spike_low" | "dir_up" | "changed" | "conflict" | "review";

export interface Alert {
  kind: AlertKind;
  a: number; // first step (0-based) of the window
  b: number; // last step (inclusive)
  value: number;
  rise?: number | null;
  level: "high" | "medium" | "info";
}

export type FcKey =
  | "p10" | "p50" | "p90" | "pu" | "pd" | "pn" | "hi" | "lo"
  | "fr_p50" | "fr_pu" | "fr_pd" | "ou_p50" | "ou_pu" | "ou_pd";

export interface Period {
  label: { en: string; fi: string };
  t0: number; // epoch ms of grid index 0
  nq: number;
  origins: number[]; // grid index of each forecast hour's first quarter
  spot: (number | null)[];
  spot_fu: (number | null)[];
  imb: (number | null)[];
  imb_fu: (number | null)[];
  dir: (number | null)[];
  dir_fu: (number | null)[];
  cutoff: number[];
  fc: Record<FcKey, number[]>; // [origin * 40 + step]
  drivers: number[]; // [origin * 40 + step] -> index into driver_combos
  driver_combos: string[];
  alerts: Alert[][];
}

export interface Payload {
  generated: string;
  model: string;
  periods: Record<string, Period>;
}

declare const payload: Payload;
export default payload;
