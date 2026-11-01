import { lazy, Suspense, useState } from "react";
const Diff = lazy(() => import("./Diff"));

export default function DiffDisclosure({
  path,
  original,
  modified,
  language,
}: {
  path: string;
  original: string;
  modified: string;
  language: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <details onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>Compare {path}</summary>
      {open && (
        <Suspense fallback={<p>Opening diff…</p>}>
          <Diff original={original} modified={modified} language={language} />
        </Suspense>
      )}
    </details>
  );
}
