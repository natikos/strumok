export interface FieldErrors {
  dayMeterValue?: string;
  nightMeterValue?: string;
  /** Whole-form failure (an API rejection), not tied to one input. */
  form?: string;
  /**
   * Tone for `form`: "error" (default) for something the resident should fix
   * or retry, "info" for a wait-and-see condition that isn't their fault
   * (e.g. the co-op hasn't set a rate yet).
   */
  formSeverity?: "error" | "info";
}
