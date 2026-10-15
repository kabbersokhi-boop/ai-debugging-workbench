import { DiffEditor, loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/editor/editor.api.js";
import EditorWorker from "monaco-editor/editor/editor.worker.js?worker";

(self as unknown as { MonacoEnvironment: monaco.Environment }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};
loader.config({ monaco });

export default function CandidateDiff({ original, modified }: { original: string; modified: string }) {
  return <DiffEditor height="340px" language="javascript" original={original} modified={modified}
    theme="vs-dark" options={{ readOnly: true, originalEditable: false, minimap: { enabled: false },
      scrollBeyondLastLine: false, fontSize: 12, renderSideBySide: true,
      automaticLayout: true, accessibilitySupport: "on" }}
    loading={<p>Loading local Monaco diff editor…</p>} />;
}
