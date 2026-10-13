"use client";

import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { ConsoleOutput, UIArtifact } from "./types";

export interface CodeArtifactMetadata {
  outputs: ConsoleOutput[];
}

export const initialArtifactData: UIArtifact = {
  boundingBox: {
    height: 400,
    left: 0,
    top: 0,
    width: 400,
  },
  content: "",
  documentId: "init",
  isVisible: false,
  kind: "code",
  status: "idle",
  title: "",
};

interface ArtifactContextValue {
  artifact: UIArtifact;
  setArtifact: React.Dispatch<React.SetStateAction<UIArtifact>>;
  metadata: CodeArtifactMetadata;
  setMetadata: React.Dispatch<React.SetStateAction<CodeArtifactMetadata>>;
}

const ArtifactContext = createContext<ArtifactContextValue | null>(null);

export function ArtifactProvider({ children }: { children: ReactNode }) {
  const [artifact, setArtifact] = useState<UIArtifact>(initialArtifactData);
  const [metadata, setMetadata] = useState<CodeArtifactMetadata>({
    outputs: [],
  });

  const value = useMemo(
    () => ({ artifact, metadata, setArtifact, setMetadata }),
    [artifact, metadata],
  );

  return (
    <ArtifactContext.Provider value={value}>
      {children}
    </ArtifactContext.Provider>
  );
}

export function useArtifact() {
  const ctx = useContext(ArtifactContext);
  if (!ctx) {
    throw new Error("useArtifact must be used within ArtifactProvider");
  }
  return ctx;
}
