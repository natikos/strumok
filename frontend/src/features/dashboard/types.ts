export interface FieldErrors {
  dayMeterValue?: string;
  nightMeterValue?: string;
  /** Whole-form failure (an API rejection), not tied to one input. */
  form?: string;
  /** Whole-form notice that isn't the resident's fault (e.g. no rate configured yet). */
  info?: string;
}
