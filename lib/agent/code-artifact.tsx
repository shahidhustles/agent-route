"use client";

import { Copy, Play, Redo2, Undo2 } from "lucide-react";

import { CodeArtifactConsole } from "@/components/code-artifact/console";
import { CodeEditor } from "@/components/code-artifact/editor";

import { Artifact } from "./create-artifact";
import type { ConsoleOutput, ConsoleOutputContent } from "./types";

const OUTPUT_HANDLERS = {
  basic: `
    # Basic output capture setup
  `,
  matplotlib: `
    import io
    import base64
    from matplotlib import pyplot as plt

    plt.clf()
    plt.close('all')

    plt.switch_backend('agg')

    def setup_matplotlib_output():
        def custom_show():
            if plt.gcf().get_size_inches().prod() * plt.gcf().dpi ** 2 > 25_000_000:
                print("Warning: Plot size too large, reducing quality")
                plt.gcf().set_dpi(100)

            png_buf = io.BytesIO()
            plt.savefig(png_buf, format='png')
            png_buf.seek(0)
            png_base64 = base64.b64encode(png_buf.read()).decode('utf-8')
            print(f'data:image/png;base64,{png_base64}')
            png_buf.close()

            plt.clf()
            plt.close('all')

        plt.show = custom_show
  `,
} as const;

function detectRequiredHandlers(code: string): string[] {
  const handlers: string[] = ["basic"];

  if (code.includes("matplotlib") || code.includes("plt.")) {
    handlers.push("matplotlib");
  }

  return handlers;
}

interface CodeMetadata {
  outputs: ConsoleOutput[];
}

export const codeArtifact = new Artifact<"code", CodeMetadata>({
  actions: [
    {
      description: "Execute Python code",
      icon: <Play aria-hidden className="artifact-icon" />,
      label: "Run",
      onClick: async ({ content, setMetadata }) => {
        const runId = crypto.randomUUID();
        const outputContent: ConsoleOutputContent[] = [];

        setMetadata((metadata) => ({
          ...metadata,
          outputs: [
            ...metadata.outputs,
            {
              id: runId,
              contents: [],
              status: "in_progress",
            },
          ],
        }));

        try {
          type PyodideInstance = {
            setStdout: (opts: { batched: (output: string) => void }) => void;
            loadPackagesFromImports: (
              code: string,
              opts?: { messageCallback?: (msg: string) => void }
            ) => Promise<void>;
            runPythonAsync: (code: string) => Promise<void>;
          };
          const g = globalThis as unknown as {
            loadPyodide?: (opts: {
              indexURL: string;
            }) => Promise<PyodideInstance>;
          };
          if (typeof g.loadPyodide !== "function") {
            await new Promise<void>((resolve, reject) => {
              const script = document.createElement("script");
              script.src =
                "https://cdn.jsdelivr.net/pyodide/v0.23.4/full/pyodide.js";
              script.onload = () => resolve();
              script.onerror = () =>
                reject(new Error("Failed to load Pyodide"));
              document.head.appendChild(script);
            });
          }
          const currentPyodideInstance = await g.loadPyodide!({
            indexURL: "https://cdn.jsdelivr.net/pyodide/v0.23.4/full/",
          });

          currentPyodideInstance.setStdout({
            batched: (output: string) => {
              outputContent.push({
                type: output.startsWith("data:image/png;base64")
                  ? "image"
                  : "text",
                value: output,
              });
            },
          });

          await currentPyodideInstance.loadPackagesFromImports(content, {
            messageCallback: (message: string) => {
              setMetadata((metadata) => ({
                ...metadata,
                outputs: [
                  ...metadata.outputs.filter((output) => output.id !== runId),
                  {
                    id: runId,
                    contents: [{ type: "text", value: message }],
                    status: "loading_packages",
                  },
                ],
              }));
            },
          });

          const requiredHandlers = detectRequiredHandlers(content);
          for (const handler of requiredHandlers) {
            if (handler in OUTPUT_HANDLERS) {
              await currentPyodideInstance.runPythonAsync(
                OUTPUT_HANDLERS[handler as keyof typeof OUTPUT_HANDLERS]
              );

              if (handler === "matplotlib") {
                await currentPyodideInstance.runPythonAsync(
                  "setup_matplotlib_output()"
                );
              }
            }
          }

          await currentPyodideInstance.runPythonAsync(content);

          setMetadata((metadata) => ({
            ...metadata,
            outputs: [
              ...metadata.outputs.filter((output) => output.id !== runId),
              {
                id: runId,
                contents: outputContent,
                status: "completed",
              },
            ],
          }));
        } catch (error: unknown) {
          const message =
            error instanceof Error ? error.message : "Execution failed";
          setMetadata((metadata) => ({
            ...metadata,
            outputs: [
              ...metadata.outputs.filter((output) => output.id !== runId),
              {
                id: runId,
                contents: [{ type: "text", value: message }],
                status: "failed",
              },
            ],
          }));
        }
      },
    },
    {
      description: "View previous version",
      icon: <Undo2 aria-hidden className="artifact-icon" />,
      isDisabled: ({ currentVersionIndex }) => currentVersionIndex === 0,
      onClick: ({ handleVersionChange }) => {
        handleVersionChange("prev");
      },
    },
    {
      description: "View next version",
      icon: <Redo2 aria-hidden className="artifact-icon" />,
      isDisabled: ({ isCurrentVersion }) => isCurrentVersion,
      onClick: ({ handleVersionChange }) => {
        handleVersionChange("next");
      },
    },
    {
      description: "Copy code to clipboard",
      icon: <Copy aria-hidden className="artifact-icon" />,
      isDisabled: ({ content }) => content.trim().length === 0,
      onClick: ({ content }) => {
        navigator.clipboard.writeText(content);
      },
    },
  ],
  content: ({
    metadata,
    setMetadata,
    content,
    onSaveContent,
    status,
    isCurrentVersion,
    currentVersionIndex,
  }) => {
    const hasConsole = Boolean(metadata?.outputs?.length);
    return (
      <div className="artifact-body">
        <div
          className={
            hasConsole ? "artifact-editor-area with-console" : "artifact-editor-area"
          }
        >
          <CodeEditor
            content={content}
            currentVersionIndex={currentVersionIndex}
            isCurrentVersion={isCurrentVersion}
            onSaveContent={onSaveContent}
            status={status}
          />
        </div>
        {hasConsole ? (
          <div className="artifact-console-area">
            <CodeArtifactConsole
              consoleOutputs={metadata.outputs}
              setConsoleOutputs={(updater) => {
                setMetadata((m) => ({
                  ...m,
                  outputs:
                    typeof updater === "function"
                      ? updater(m.outputs)
                      : updater,
                }));
              }}
            />
          </div>
        ) : null}
      </div>
    );
  },
  description:
    "Useful for Python code generation; Run executes in the browser via Pyodide.",
  initialize: ({ setMetadata }) => {
    setMetadata({
      outputs: [],
    });
  },
  kind: "code",
  onStreamPart: ({ streamPart, setArtifact }) => {
    if (streamPart.type === "data-codeDelta") {
      setArtifact((draftArtifact) => ({
        ...draftArtifact,
        content: streamPart.data,
        isVisible: true,
        status: "streaming",
      }));
    }
  },
});
