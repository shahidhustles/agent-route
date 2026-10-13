"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { codeArtifact } from "@/lib/agent/code-artifact";
import type { ArtifactActionContext } from "@/lib/agent/create-artifact";
import type { CodeDocumentVersion } from "@/lib/agent/types";
import { useArtifact, type CodeArtifactMetadata } from "@/lib/agent/use-artifact";

const CodeArtifactContent = codeArtifact.content;

export function CodeArtifactPanel() {
  const { artifact, setArtifact, metadata, setMetadata } = useArtifact();
  const [versions, setVersions] = useState<CodeDocumentVersion[]>([]);
  const [currentVersionIndex, setCurrentVersionIndex] = useState(0);
  const [isContentDirty, setIsContentDirty] = useState(false);
  const prevStatusRef = useRef(artifact.status);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const isCurrentVersion =
    versions.length === 0 ? true : currentVersionIndex === versions.length - 1;

  useEffect(() => {
    if (
      prevStatusRef.current === "streaming" &&
      artifact.status === "idle" &&
      artifact.content
    ) {
      setVersions((v) => {
        const last = v.at(-1);
        if (last?.content === artifact.content) {
          return v;
        }
        const next = [
          ...v,
          {
            content: artifact.content,
            createdAt: new Date(),
            id: crypto.randomUUID(),
          },
        ];
        setCurrentVersionIndex(next.length - 1);
        return next;
      });
    }
    prevStatusRef.current = artifact.status;
  }, [artifact.status, artifact.content]);

  useEffect(() => {
    if (versions.length === 0) {
      return;
    }
    setCurrentVersionIndex((idx) => {
      if (idx >= versions.length) {
        return versions.length - 1;
      }
      return idx;
    });
  }, [versions.length]);

  const getDocumentContentById = useCallback(
    (index: number) => versions[index]?.content ?? "",
    [versions]
  );

  const displayContent = isCurrentVersion
    ? artifact.content
    : getDocumentContentById(currentVersionIndex);

  const handleVersionChange = useCallback(
    (type: "next" | "prev" | "latest") => {
      if (type === "latest") {
        setCurrentVersionIndex(Math.max(0, versions.length - 1));
        return;
      }
      if (type === "prev") {
        if (currentVersionIndex > 0) {
          setCurrentVersionIndex((i) => i - 1);
        }
        return;
      }
      if (type === "next" && currentVersionIndex < versions.length - 1) {
        setCurrentVersionIndex((i) => i + 1);
      }
    },
    [currentVersionIndex, versions.length]
  );

  const commitContentVersion = useCallback(
    (updatedContent: string) => {
      setArtifact((a) => ({ ...a, content: updatedContent }));
      setIsContentDirty(false);
      setVersions((v) => {
        const last = v.at(-1);
        if (last?.content === updatedContent) {
          return v;
        }
        const next = [
          ...v,
          {
            content: updatedContent,
            createdAt: new Date(),
            id: crypto.randomUUID(),
          },
        ];
        setCurrentVersionIndex(next.length - 1);
        return next;
      });
    },
    [setArtifact]
  );

  const saveContent = useCallback(
    (updatedContent: string, isCurrentVersionFlag: boolean) => {
      if (!isCurrentVersionFlag) {
        return;
      }
      if (updatedContent === artifact.content) {
        return;
      }
      setIsContentDirty(true);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => commitContentVersion(updatedContent), 500);
    },
    [artifact.content, commitContentVersion]
  );

  const actionContext: ArtifactActionContext<CodeArtifactMetadata> = {
    artifactTitle: artifact.title || undefined,
    content: displayContent,
    currentVersionIndex,
    handleVersionChange,
    isCurrentVersion,
    metadata,
    setMetadata,
  };

  const latestVersion = versions.at(-1);

  if (!artifact.isVisible) {
    return null;
  }

  return (
    <section className="artifact-panel" data-testid="artifact">
      <header className="artifact-head">
        <div className="artifact-heading">
          <h2>{artifact.title || "Code artifact"}</h2>
          <p>
            {isContentDirty
              ? "Saving changes..."
              : latestVersion
                ? `${versions.length} version${versions.length === 1 ? "" : "s"} kept in this tab`
                : "Versions stay in this tab; nothing is stored."}
          </p>
        </div>
        <div className="artifact-actions">
          {codeArtifact.actions.map((action) => {
            const disabled = action.isDisabled?.(actionContext) ?? false;
            return (
              <button
                aria-label={action.description}
                className="btn-icon"
                disabled={disabled}
                key={action.description}
                onClick={() => {
                  action.onClick(actionContext);
                }}
                title={action.description}
                type="button"
              >
                {action.icon}
              </button>
            );
          })}
          <button
            className="btn"
            onClick={() => setArtifact((a) => ({ ...a, isVisible: false }))}
            type="button"
          >
            Close
          </button>
        </div>
      </header>
      <div className="artifact-stage">
        <CodeArtifactContent
          content={displayContent}
          currentVersionIndex={currentVersionIndex}
          isCurrentVersion={isCurrentVersion}
          metadata={metadata}
          onSaveContent={saveContent}
          setMetadata={setMetadata}
          status={artifact.status}
        />
      </div>
      {!isCurrentVersion && versions.length > 0 ? (
        <footer className="artifact-versions">
          <span>
            Version {currentVersionIndex + 1} of {versions.length}
          </span>
          <button
            className="btn"
            onClick={() => handleVersionChange("latest")}
            type="button"
          >
            Back to latest
          </button>
        </footer>
      ) : null}
    </section>
  );
}
