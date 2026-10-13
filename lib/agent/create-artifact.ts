import type { DataUIPart } from "ai";
import type { ComponentType, Dispatch, SetStateAction } from "react";

import type { AgentDataParts, UIArtifact } from "./types";

export interface ArtifactActionContext<M = unknown> {
  content: string;
  artifactTitle?: string;
  handleVersionChange: (type: "next" | "prev" | "latest") => void;
  currentVersionIndex: number;
  isCurrentVersion: boolean;
  metadata: M;
  setMetadata: Dispatch<SetStateAction<M>>;
}

export interface ArtifactAction<M = unknown> {
  icon: React.ReactNode;
  label?: string;
  description: string;
  onClick: (context: ArtifactActionContext<M>) => void | Promise<void>;
  isDisabled?: (context: ArtifactActionContext<M>) => boolean;
}

export interface ArtifactContentProps<M = unknown> {
  content: string;
  isCurrentVersion: boolean;
  currentVersionIndex: number;
  status: "streaming" | "idle";
  onSaveContent: (updatedContent: string, isCurrentVersionFlag: boolean) => void;
  metadata: M;
  setMetadata: Dispatch<SetStateAction<M>>;
}

interface InitializeParameters<M = unknown> {
  documentId: string;
  setMetadata: Dispatch<SetStateAction<M>>;
}

export interface ArtifactConfig<T extends string, M = unknown> {
  kind: T;
  description: string;
  content: ComponentType<ArtifactContentProps<M>>;
  actions: ArtifactAction<M>[];
  initialize?: (parameters: InitializeParameters<M>) => void;
  onStreamPart: (args: {
    setMetadata: Dispatch<SetStateAction<M>>;
    setArtifact: Dispatch<SetStateAction<UIArtifact>>;
    streamPart: DataUIPart<AgentDataParts>;
  }) => void;
}

export class Artifact<T extends string, M = unknown> {
  readonly kind: T;
  readonly description: string;
  readonly content: ComponentType<ArtifactContentProps<M>>;
  readonly actions: ArtifactAction<M>[];
  readonly initialize?: (parameters: InitializeParameters<M>) => void;
  readonly onStreamPart: (args: {
    setMetadata: Dispatch<SetStateAction<M>>;
    setArtifact: Dispatch<SetStateAction<UIArtifact>>;
    streamPart: DataUIPart<AgentDataParts>;
  }) => void;

  constructor(config: ArtifactConfig<T, M>) {
    this.kind = config.kind;
    this.description = config.description;
    this.content = config.content;
    this.actions = config.actions || [];
    this.initialize = config.initialize;
    this.onStreamPart = config.onStreamPart;
  }
}
