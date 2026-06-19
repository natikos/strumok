# Dashboard design context

This file documents the UI/UX decisions made for the main dashboard page. Claude Code should follow these when implementing or modifying the dashboard.

---

## App purpose

Neighborhood shared electricity meter tracker. Users submit their monthly meter reading so the shared bill can be split. **The primary action is submitting a reading** — everything else on the dashboard is secondary.

**Users are older people.** Design accordingly: large text, large tap targets, plain language, no ambiguity.

---

## Layout structure

### Page order (top to bottom)

1. **Submit reading card** — always first, always visible without scrolling
2. **Last month usage + vs previous month** — two small stat cards side by side
3. **Meter readings card** — current Day and Night totals in a single unified card
4. **Usage trend** — line chart, last 6 months
5. **Next deadline** — shown only after submission

### Web layout

- Sidebar navigation (Home, History, Settings — 3 items only)
- Top bar with app name + user avatar
- Main content area with the order above
- Submit card uses `border: 2px solid #378ADD` to draw the eye immediately
- Subgreeting line below the welcome message explains why they're here: e.g. "July reading is due — please submit your meter reading below."

### Mobile layout (PWA)

- Top bar only (no sidebar), bottom navigation with 3 tabs
- Same card order as web, full-width cards
- Bottom nav: Home / History / Settings

---

## Submit card

### Default state (reading due)

- `border: 2px solid #378ADD` — blue accent border
- Header: "Submit [Month] reading" + "Due now" amber badge
- Previous readings shown inline below the header: "Previous: Day 1,433 · Night 258" — helps users sanity-check new numbers
- Two large inputs side by side: Day and Night
  - `font-size: 22px` (web) / `18px` (mobile)
  - `inputmode="numeric"` — triggers number pad on mobile
  - Placeholder shows example: "e.g. 1 450"
- Submit button: full width, `background: #378ADD`, `font-size: 17px`
- Hint text below button: "Enter the numbers shown on your electricity meter, then press Submit"

### Overdue state (deadline missed)

- `border: 2px solid #E24B4A` — red accent border
- Red alert banner at top with triangle icon: "July deadline passed" + plain explanation
- Estimated charge shown prominently in a red-tinted box:
  - Label: "Your estimated charge"
  - Value: calculated kWh (avg × 1.3), large text
  - Sub-text: "Average 156 kWh × 1.3 — still submit to correct next month"
- **Overdue calculation rule: average of user's last 3 months × 1.30**
- Form stays open — user can still submit a late reading
- Button label changes to "Submit late reading"
- Hint: "This will not change your July charge but will correct August"
- Avatar dot and bolt icon in topbar also turn red

### Submitted state (reading recorded)

- Form is **completely replaced** — never disabled/greyed out
- `border: 2px solid #639922` — green accent border
- Green confirmation banner with large checkmark icon:
  - "July reading submitted"
  - "Thank you, [Name]. Your reading has been recorded."
- Submitted values shown below: Day and Night readings user entered
- Usage computed immediately and shown as a pill: "Used this month: 18 kWh"
- Next deadline card appears below stats: "August — due in 31 days"

---

## Meter readings card

Day and Night values are **always in a single unified card** — never split into two separate cards.

```
Meter readings
☀ Day        1,433
☾ Night        258
```

- Section label at top: "Meter readings" (uppercase, muted)
- Each row: icon + label on left, value right-aligned
- Value font-size: 22px (web) / 16–17px (mobile)
- Rows separated by a 0.5px border

---

## Stat cards

Two small cards side by side below the submit card:

- "Used last month — [Month]": total kWh with Day/Night breakdown as sub-text
- "vs last month": delta in kWh, green if lower (`color: var(--color-text-success)`), red if higher

---

## Trend chart

- Line chart, not bar chart
- Last 6 months of total usage
- Area fill below the line (low opacity)
- Current month: larger dot with ring + callout bubble showing the value
- Trend label: "Decreasing" / "Increasing" in green/red next to the chart title
- X-axis: month abbreviations, current month in blue

---

## Design principles for older users

- Minimum font size: 13px for any label, 16px+ for values, 22px+ for primary numbers
- Tap targets: minimum 44px height on all interactive elements
- Full-width primary buttons — never small or inline
- Plain language: "Submit reading" not "Log entry", "Used this month" not "Delta kWh"
- Personal name in confirmation messages ("Thank you, Наталія")
- Never disable a form without replacing it with a clear explanation
- `inputmode="numeric"` on all meter reading inputs
- Maximum 3 navigation items — no nested menus
- "Due now" / "Due" badge disappears after submission — clear before/after state
- Show previous readings inside the submit form for reference

---

## Color usage

| Meaning               | Color                                   |
| --------------------- | --------------------------------------- |
| Primary action / info | `#378ADD` (blue)                        |
| Due / warning         | `var(--color-background-warning)` amber |
| Overdue / error       | `#E24B4A` red                           |
| Submitted / success   | `#639922` green                         |
| Lower usage (good)    | `var(--color-text-success)`             |
| Higher usage (bad)    | `var(--color-text-danger)`              |

Card accent border is always `2px solid [color]` — this is intentional (thicker than default 0.5px) to draw attention to the primary card.
