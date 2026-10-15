import { useEffect, useRef } from "react";
import * as monaco from "monaco-editor/editor/editor.api.js";
import EditorWorker from "monaco-editor/editor/editor.worker.js?worker";

(self as unknown as { MonacoEnvironment: monaco.Environment }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

export default function CandidateDiff({ original, modified }: { original: string; modified: string }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const before = monaco.editor.createModel(original, "javascript");
    const after = monaco.editor.createModel(modified, "javascript");
    const editor = monaco.editor.createDiffEditor(container.current, {
      theme: "vs-dark", readOnly: true, originalEditable: false,
      minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 12,
      renderSideBySide: true, renderSideBySideInlineBreakpoint: 700,
      useInlineViewWhenSpaceIsLimited: true, automaticLayout: true, accessibilitySupport: "on",
    });
    editor.setModel({ original: before, modified: after });
    return () => {
      // Disconnect the widget before disposing models; async diff work may still be pending.
      editor.setModel(null);
      editor.dispose();
      before.dispose(); after.dispose();
    };
  }, [original, modified]);
  return <div ref={container} style={{height: 340, width: "100%"}} aria-label="Read-only candidate diff" />;
}
