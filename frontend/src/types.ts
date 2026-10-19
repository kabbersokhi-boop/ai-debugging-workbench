export type RunStatus =
  | "queued"
  | "running"
  | "reproduced"
  | "not_reproduced"
  | "error"
  | "cancelled"
  | "interrupted";
export type Bug = {
  id: string;
  title: string;
  summary: string;
  severity: string;
  report: string;
  steps: string[];
  expected: string;
  repository: string;
};
export type RunEvent = {
  sequence: number;
  kind: string;
  title: string;
  detail: string;
  created_at: string;
  data: Record<string, unknown>;
};
export type Check = {
  name: string;
  expected_cents: number;
  observed_cents: number;
  passed: boolean;
};
export type Observation = {
  quantity: number;
  unit_price_cents: number;
  line_total_cents: number;
  subtotal_cents: number;
  shipping_cents: number;
  total_cents: number;
};
export type Result = {
  status: string;
  checks: Check[];
  baseline: Observation;
  observed: Observation;
  artifacts: { name: string; label: string; media_type: string }[];
  fixture_sha256: string;
  browser_version: string;
  duration_ms: number;
};
export type RunSummary = {
  id: string;
  bug_id: string;
  status: RunStatus;
  created_at: string;
  updated_at: string;
};
export type Run = RunSummary & {
  error: string | null;
  result: Result | null;
  events: RunEvent[];
};
export const active = (status?: RunStatus) =>
  status === "queued" || status === "running";
export const money = (cents: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    cents / 100,
  );
export const statusLabel = (status?: RunStatus) =>
  status
    ? {
        queued: "Queued",
        running: "Reproducing",
        reproduced: "Defect reproduced",
        not_reproduced: "Not reproduced",
        error: "Execution error",
        cancelled: "Cancelled",
        interrupted: "Interrupted",
      }[status]
    : "Ready to reproduce";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : typeof body?.detail?.reason === "string"
          ? `${body.detail.status ? body.detail.status.replaceAll("_", " ") + ": " : ""}${body.detail.reason}`
          : Array.isArray(body?.detail)
            ? body.detail.slice(0, 3).map((e: {loc?: string[]; msg?: string}) => `${e.loc?.slice(1).join(".") ?? "Input"}: ${e.msg ?? "invalid"}`).join("; ")
            : `Request failed (${response.status}). Please retry.`,
    );
  }
  return response.json() as Promise<T>;
}
