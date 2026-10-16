import { money, type Run } from "./types";

export function captureDescription(run: Run, name: string): string {
  const baseline = name === "before.png";
  const observed = baseline ? run.result?.baseline : run.result?.observed;
  const label = baseline
    ? "baseline"
    : run.status === "reproduced"
      ? "defect"
      : "after state";
  if (!observed)
    return `Actual Playwright ${label}; observation is incomplete.`;
  return `Actual Playwright ${label}: quantity ${observed.quantity}, line amount ${money(observed.line_total_cents)}, subtotal ${money(observed.subtotal_cents)}, shipping ${money(observed.shipping_cents)}, total ${money(observed.total_cents)}.${run.status === "not_reproduced" ? " The reported defect was not observed." : ""}`;
}

export function pricingNote(run: Run | null): string {
  if (!run?.result)
    return "Expected values come from a fixed pricing contract, outside the storefront implementation.";
  if (run.bug_id !== "cart-quantity") return "Versioned scenario contract. Compare the captured action and named checks; reproduction is separate from repair verification.";
  return run.status === "not_reproduced"
    ? "Baseline and after-action pricing checks passed. The reported defect was not observed; this does not establish a verified repair."
    : "Baseline contract passed. These checks establish the defect; they do not verify a repair.";
}
