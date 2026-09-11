export interface FieldErrors {
  dayMeterValue?: string;
  nightMeterValue?: string;
  /** Whole-form failure (an API rejection), not tied to one input. */
  form?: string;
}
