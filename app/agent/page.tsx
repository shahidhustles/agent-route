"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { ArrowLeft, Send, Square } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { CodeArtifactPanel } from "@/components/code-artifact/panel";
import type { AgentRoutingData, AgentUIMessage } from "@/lib/agent/types";
import { ArtifactProvider, useArtifact } from "@/lib/agent/use-artifact";

import "./agent.css";

const transport = new DefaultChatTransport({ api: "/api/agent" });

export default function AgentPage() {
  return (
    <ArtifactProvider>
      <AgentWorkspace />
    </ArtifactProvider>
  );
}

function AgentWorkspace() {
  const { error, messages, sendMessage, status, stop } = useChat<AgentUIMessage>({
    transport,
  });
  const { artifact, setArtifact } = useArtifact();
  const [routing, setRouting] = useState<AgentRoutingData | null>(null);
  const [input, setInput] = useState("");

  useEffect(() => {
    let nextRouting: AgentRoutingData | null = null;
    let codeDelta: string | undefined;
    let documentId: string | undefined;
    let title: string | undefined;
    let kind: "code" | undefined;
    let finished = false;

    for (const message of messages) {
      for (const part of message.parts) {
        if (part.type === "data-routing") nextRouting = part.data;
        else if (part.type === "data-codeDelta") codeDelta = part.data;
        else if (part.type === "data-id") documentId = String(part.data);
        else if (part.type === "data-title") title = String(part.data);
        else if (part.type === "data-kind") kind = part.data;
        else if (part.type === "data-finish") finished = true;
      }
    }

    setRouting(nextRouting);
    setArtifact((current) => {
      let next = current;
      if (codeDelta !== undefined && codeDelta !== current.content) {
        next = { ...next, content: codeDelta, isVisible: true, status: "streaming" };
      }
      if (documentId !== undefined && documentId !== next.documentId) {
        next = { ...next, documentId };
      }
      if (title !== undefined && title !== next.title) {
        next = { ...next, title };
      }
      if (kind !== undefined && kind !== next.kind) {
        next = { ...next, kind };
      }
      if (finished && next.status !== "idle") {
        next = { ...next, status: "idle" };
      }
      return next;
    });
  }, [messages, setArtifact]);

  const busy = status === "submitted" || status === "streaming";

  const submit = () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setRouting(null);
    sendMessage({ text });
  };

  return (
    <main className="agent-shell">
      <header className="agent-topbar">
        <Link className="agent-back" href="/">
          <ArrowLeft aria-hidden size={16} />
          Model Router
        </Link>
        <span className="agent-title">Code artifact agent</span>
        <RoutingChip busy={busy} routing={routing} />
      </header>
      <div className="agent-main">
        <section className="agent-convo">
          <div className="agent-thread">
            {messages.length === 0 && !error ? (
              <p className="agent-hint">
                Ask for a Python snippet. The router picks between GLM-5.3 Flash
                and DeepSeek V4.1 Flash, then the code streams into the editor on
                the right. Run executes it with Pyodide in the browser.
              </p>
            ) : null}
            {messages.map((message) => (
              <article
                className={`agent-msg agent-${message.role}`}
                key={message.id}
              >
                <span className="agent-msg-role">
                  {message.role === "user" ? "You" : "Agent"}
                </span>
                <div className="agent-msg-body">
                  {message.parts
                    .filter(
                      (part) =>
                        part.type === "text" || part.type === "reasoning",
                    )
                    .map((part, index) =>
                      part.type === "reasoning" ? (
                        <p className="agent-msg-reasoning" key={index}>
                          {part.text}
                        </p>
                      ) : (
                        <p key={index}>{part.text}</p>
                      ),
                    )}
                </div>
              </article>
            ))}
            {busy ? (
              <div className="agent-shimmer" role="status">
                {routing?.status === "selected"
                  ? `${routing.model} is writing the snippet...`
                  : "Routing the task to the best model..."}
              </div>
            ) : null}
            {error ? <p className="agent-error">{error.message}</p> : null}
          </div>
          <form
            className="agent-composer"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <textarea
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
              placeholder="Describe the Python snippet you need..."
              rows={2}
              value={input}
            />
            {busy ? (
              <button
                className="btn btn-danger"
                onClick={() => stop()}
                type="button"
              >
                <Square aria-hidden size={14} />
                Stop
              </button>
            ) : (
              <button
                className="btn btn-primary"
                disabled={!input.trim()}
                type="submit"
              >
                <Send aria-hidden size={14} />
                Send
              </button>
            )}
          </form>
        </section>
        <section className="agent-stage">
          {artifact.isVisible ? (
            <CodeArtifactPanel />
          ) : (
            <div className="agent-empty">
              <h2>No artifact yet</h2>
              <p>
                The editor opens here once code streams in. Versions stay in
                this tab and Run never leaves the browser.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function RoutingChip({
  busy,
  routing,
}: {
  busy: boolean;
  routing: AgentRoutingData | null;
}) {
  if (busy && routing?.status !== "selected") {
    return (
      <span className="route-chip route-routing">
        <span className="dot dot-pulse" aria-hidden />
        Routing
      </span>
    );
  }
  if (!routing || routing.status !== "selected" || !routing.model) {
    return (
      <span className="route-chip route-idle">
        <span className="dot" aria-hidden />
        Auto routing
      </span>
    );
  }
  return (
    <span className="route-chip route-selected">
      <span className="dot" aria-hidden />
      {routing.model} · {(routing.confidence ?? 0).toFixed(2)}
    </span>
  );
}
