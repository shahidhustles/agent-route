import type { UIMessage } from "ai";

/**
 * Custom UI data streamed alongside assistant messages.
 * SDK prefixes keys with `data-` at runtime (e.g. codeDelta -> data-codeDelta).
 */
export type AgentCodeDataParts = {
  codeDelta: string;
  id: string;
  title: string;
  kind: "code";
  clear: null;
  finish: null;
};

export type AgentRoutingData = {
  status: "routing" | "selected";
  model?: string;
  confidence?: number;
};

export type AgentDataParts = AgentCodeDataParts & {
  routing: AgentRoutingData;
};

export type AgentUIMessage = UIMessage<never, AgentDataParts>;

export type CodeArtifactKind = "code";

export interface UIArtifact {
  title: string;
  documentId: string;
  kind: CodeArtifactKind;
  content: string;
  isVisible: boolean;
  status: "streaming" | "idle";
  boundingBox: {
    top: number;
    left: number;
    width: number;
    height: number;
  };
}

export interface CodeDocumentVersion {
  id: string;
  content: string;
  createdAt: Date;
}

export interface ConsoleOutputContent {
  type: "text" | "image";
  value: string;
}

export interface ConsoleOutput {
  id: string;
  status: "in_progress" | "loading_packages" | "completed" | "failed";
  contents: ConsoleOutputContent[];
}
