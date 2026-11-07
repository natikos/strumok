import { z } from "zod";

// An unsent reading survives a reload: residents read the meter in the garden,
// often without signal, and a service-worker update can reload the page.
const draftSchema = z.object({
  period: z.string(),
  day: z.number().nullable(),
  night: z.number().nullable(),
});

export type ReadingDraft = z.infer<typeof draftSchema>;

function key(householdId: number): string {
  return `strumok:reading-draft:${householdId}`;
}

/** The saved draft for this household and period; anything older is discarded. */
export function loadReadingDraft(householdId: number, period: string): ReadingDraft | null {
  try {
    const raw = localStorage.getItem(key(householdId));
    if (raw === null) {
      return null;
    }

    const parsed = draftSchema.safeParse(JSON.parse(raw));
    if (parsed.success && parsed.data.period === period) {
      return parsed.data;
    }

    localStorage.removeItem(key(householdId));
  } catch {
    // Storage can be blocked or the JSON corrupt: start without a draft.
  }

  return null;
}

export function saveReadingDraft(householdId: number, draft: ReadingDraft): void {
  try {
    if (draft.day === null && draft.night === null) {
      localStorage.removeItem(key(householdId));
      return;
    }

    localStorage.setItem(key(householdId), JSON.stringify(draft));
  } catch {
    // The values still live in memory; only surviving a reload is lost.
  }
}

export function clearReadingDraft(householdId: number): void {
  try {
    localStorage.removeItem(key(householdId));
  } catch {
    // Nothing to clear without storage.
  }
}
