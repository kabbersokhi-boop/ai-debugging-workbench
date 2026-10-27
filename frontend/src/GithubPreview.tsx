import { useEffect, useRef, useState } from "react";
import { api } from "./types";

type Preview = {
  repository: string;
  number: number;
  title: string;
  base_commit: string;
  head_commit: string;
  head_repository: string;
  changed_files: number;
  additions: number;
  deletions: number;
  observed_at: string;
  limitation: string;
  admission: string;
  execution_authorized: boolean;
};
export default function GithubPreview({ disabled }: { disabled: boolean }) {
  const [url, setUrl] = useState(""),
    [value, setValue] = useState<Preview | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const epoch = useRef(0);
  useEffect(
    () => () => {
      epoch.current++;
    },
    [],
  );
  useEffect(() => {
    if (disabled) {
      epoch.current++;
      setBusy(false);
      setValue(null);
      setError("");
    }
  }, [disabled]);
  async function preview() {
    const token = ++epoch.current;
    setBusy(true);
    setError("");
    setValue(null);
    try {
      const result = await api<Preview>("/repository-audits/github-preview", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      if (token === epoch.current) setValue(result);
    } catch (e) {
      if (token === epoch.current) setError(String(e));
    } finally {
      if (token === epoch.current) setBusy(false);
    }
  }
  return (
    <details className="github-preview">
      <summary>
        Start from a public GitHub pull request · metadata preview
      </summary>
      <p>
        Read-only preview of public PR metadata. No private access, source
        import, patch admission or execution. A PR link is not execution
        authorization.
      </p>
      <label>
        Public GitHub PR URL
        <input
          aria-label="Public GitHub PR URL"
          placeholder="https://github.com/owner/repository/pull/123"
          value={url}
          disabled={disabled}
          onChange={(e) => {
            epoch.current++;
            setBusy(false);
            setValue(null);
            setError("");
            setUrl(e.target.value);
          }}
        />
      </label>
      <button disabled={disabled || busy || !url} onClick={preview}>
        {busy ? "Reading public metadata…" : "Preview public PR"}
      </button>
      {error && (
        <p role="alert">
          Preview unavailable. {error} Continue with manual intake below; no
          source was admitted.
        </p>
      )}
      {value && (
        <section aria-label="GitHub PR preview">
          <h3>
            {value.repository} #{value.number}: {value.title}
          </h3>
          <span className="mode-badge">Preview only · not admitted</span>
          <dl className="audit-facts">
            <div>
              <dt>Observed base tip</dt>
              <dd>
                <code>{value.base_commit}</code>
              </dd>
            </div>
            <div>
              <dt>Observed head</dt>
              <dd>
                {value.head_repository}
                <br />
                <code>{value.head_commit}</code>
              </dd>
            </div>
            <div>
              <dt>Change metadata</dt>
              <dd>
                {value.changed_files} files · +{value.additions} / −
                {value.deletions}
              </dd>
            </div>
          </dl>
          <p>{value.limitation}</p>
          <p>
            Observed {new Date(value.observed_at).toLocaleString()}. Supply a
            deliberately chosen immutable base and production-only patch below.
            Admission recomputes source and candidate identities from bytes;
            preview metadata grants no approval.
          </p>
        </section>
      )}
    </details>
  );
}
