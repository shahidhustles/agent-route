"use client";

import { Terminal, X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ConsoleOutput } from "@/lib/agent/types";

interface ConsoleProps {
  consoleOutputs: ConsoleOutput[];
  setConsoleOutputs: Dispatch<SetStateAction<ConsoleOutput[]>>;
}

export function CodeArtifactConsole({
  consoleOutputs,
  setConsoleOutputs,
}: ConsoleProps) {
  const consoleEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    consoleEndRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  if (consoleOutputs.length === 0) {
    return null;
  }

  return (
    <div className="console-frame">
      <div className="console-head">
        <span className="console-title">
          <Terminal aria-hidden size={14} />
          Console
        </span>
        <button
          aria-label="Clear console"
          className="btn-icon"
          onClick={() => setConsoleOutputs([])}
          type="button"
        >
          <X aria-hidden size={14} />
        </button>
      </div>
      <div className="console-body">
        {consoleOutputs.map((consoleOutput, index) => (
          <div
            className={`console-row console-${consoleOutput.status}`}
            key={consoleOutput.id}
          >
            <span className="console-index">[{index + 1}]</span>
            <div className="console-content">
              {consoleOutput.status === "in_progress" ||
              consoleOutput.status === "loading_packages" ? (
                <span className="console-pending">
                  {consoleOutput.status === "in_progress"
                    ? "Initializing Pyodide..."
                    : consoleOutput.contents.map((content) =>
                        content.type === "text" ? content.value : null
                      )}
                </span>
              ) : (
                consoleOutput.contents.map((content, contentIndex) =>
                  content.type === "image" ? (
                    <img
                      alt="Plot output from Python"
                      className="console-image"
                      key={`${consoleOutput.id}-${contentIndex}`}
                      src={content.value}
                    />
                  ) : (
                    <pre
                      className="console-text"
                      key={`${consoleOutput.id}-${contentIndex}`}
                    >
                      {content.value}
                    </pre>
                  )
                )
              )}
            </div>
          </div>
        ))}
        <div ref={consoleEndRef} />
      </div>
    </div>
  );
}
