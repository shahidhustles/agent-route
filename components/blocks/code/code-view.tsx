"use client";

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { basicSetup } from "codemirror";
import { useEffect, useRef } from "react";

// Read-only variant of the ai-components agent-code-artifact editor (CodeMirror, Python mode). The block's
// in-browser console is left out: the agent already ran this code in its sandbox, and the app never runs it.
export function CodeView({ content }: { content: string }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current) return;
    const view = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: content,
        extensions: [basicSetup, python(), EditorState.readOnly.of(true), EditorView.editable.of(false)],
      }),
    });
    return () => view.destroy();
  }, [content]);
  return <div className="max-h-[560px] overflow-auto rounded-lg border bg-background" ref={host} />;
}
