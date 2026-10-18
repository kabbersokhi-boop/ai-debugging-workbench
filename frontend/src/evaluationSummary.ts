type Observation = {
  name: string;
  status: string;
  expected: unknown;
  observed: unknown;
};
type EvidenceResult = {
  status: string;
  reason?: string;
  ordinary?: { outcome?: string } | null;
  independent?: { outcome?: string; checks?: Observation[] } | null;
};

export function evidenceSummary(
  taskId: string,
  result?: EvidenceResult | null,
) {
  if (!result) return "No completed check evidence is available.";
  const failed =
    result.independent?.checks?.filter((c) => c.status === "failed") ?? [];
  if (taskId === "boltons-addlist") {
    const empty = failed.find((c) => c.name.endsWith(":empty"));
    if (empty && typeof empty.observed === "object" && empty.observed) {
      const observed = empty.observed as Record<string, unknown>;
      if (
        typeof observed.length === "number" &&
        observed.length > 0 &&
        JSON.stringify(observed.keys) === "[]" &&
        JSON.stringify(observed.items) === "[]"
      ) {
        return `An empty addlist input produces inconsistent state: len() is ${observed.length}, while keys() and items() are empty.`;
      }
    }
  }
  if (result.status === "passed") {
    return "Ordinary checks and the frozen independent observations both passed. Coverage is finite.";
  }
  if (failed.length && taskId === "more-seekable") {
    return "The recorded peek, truth-test, and iteration sequence differs from the frozen contract for preserving unconsumed items.";
  }
  if (failed.length && taskId === "boltons-indexedset") {
    return "After removals, slicing differs from the expected visible contents. The saved observations show each removal history and slice.";
  }
  if (failed.length && taskId === "more-bucket") {
    return "The supplied false-valued validator does not produce the required key, value, or source-consumption behavior.";
  }
  if (failed.length && taskId === "boltons-addlist") {
    return "The addlist observations differ from the required values, item order, or length after one-shot inputs. Inspect the first differing case below.";
  }
  if (result.ordinary?.outcome === "failed") {
    return "Ordinary repository checks detected a failure. The saved transcript and independent observations explain the tested behavior.";
  }
  return (
    result.reason ??
    "Execution did not produce a complete passing result. Inspect its retained evidence."
  );
}
