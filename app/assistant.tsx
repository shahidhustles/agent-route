"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useUser } from "@clerk/nextjs";
import { AssistantChatTransport, useChatRuntime } from "@assistant-ui/ai-sdk";
import type { ChatTransport, UIMessage } from "ai";
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  ActionBarPrimitive,
  AuiIf,
  useAui,
  useAuiState,
  useRemoteThreadListRuntime,
  type ToolCallMessagePartComponent,
} from "@assistant-ui/react";
import {
  useState,
  useRef,
  useEffect,
  useMemo,
  createContext,
  useContext,
  type ReactNode,
} from "react";
import {
  ArrowUp,
  Plus,
  Square,
  PanelLeft,
  X,
  Info,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Copy,
  FileText,
  Paperclip,
  ChevronRight,
  Library,
  Terminal,
  Search,
  Pencil,
  Brain,
} from "lucide-react";
import { parse } from "papaparse";
import { toast } from "sonner";
import { AccountFooter } from "@/components/account-footer";
import { RelayLogo } from "@/components/relay-logo";
import { ThreadListItems } from "@/components/assistant-ui/elements/thread-list.aui";
import { MarkdownText } from "@/components/assistant-ui/elements/markdown-text";
import {
  ToolGroupRoot,
  ToolGroupTrigger,
  ToolGroupContent,
} from "@/components/assistant-ui/elements/tool-group.aui";
import { ArtifactCard } from "@/components/assistant-ui/elements/artifact-card";
import {
  CanvasSplit,
  CanvasSplitThread,
  CanvasSplitDocument,
} from "@/components/assistant-ui/elements/canvas-split";
import { ArtifactView, ArtifactSkeleton } from "@/components/artifact-view";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AGENTS,
  AGENT_LABEL,
  MODEL_NAME,
  PREFERENCES,
  api,
  money,
  pct,
  type Agent,
  type Preference,
  type Recorded,
  type Artifact,
  type Status,
  type Run,
} from "@/lib/api";
import { chatMeta, type ChatMeta, type ArtifactSelection } from "@/lib/chat-meta";
import { useIsMobile } from "@/hooks/use-mobile";
import { csvSizeError } from "@/lib/route-state";
import { createThreadListAdapter, type Db } from "@/lib/persistence/conversations";
import { useSupabaseAdapters } from "@/lib/persistence/history";
import { saveRun, saveVerdict } from "@/lib/persistence/runs";
import { supabaseConfigured } from "@/lib/supabase/config";
import { useSupabase } from "@/lib/supabase/client";

type Options = {
  preference: Preference;
  agentMode: boolean;
  csv: { name: string; body: string } | null;
  override: { agent?: Agent; model?: string; rerun_of?: string } | null;
};
const initial: Options = { preference: "balanced", agentMode: false, csv: null, override: null };
const ChatContext = createContext<{
  options: Options;
  setOptions: React.Dispatch<React.SetStateAction<Options>>;
  openArtifact: (value: ArtifactSelection | null) => void;
  /** Stores a thumbs verdict with the run. Absent when history is not saved. */
  saveVerdict?: (runId: string, passed: boolean) => Promise<void>;
}>({ options: initial, setOptions: () => {}, openArtifact: () => {} });
const useChat = () => useContext(ChatContext);
const titleCase = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "Something went wrong. Try again.";

export function Assistant() {
  return supabaseConfigured() ? <SavedAssistant /> : <LocalAssistant footer={<AccountFooter />} />;
}

function useChatOptions(injected?: ChatTransport<UIMessage>) {
  const [options, setOptions] = useState(initial);
  const latest = useRef(options);
  latest.current = options;
  const transport = useMemo(
    () => injected ?? new AssistantChatTransport({ api: "/api/chat", body: () => latest.current }),
    [injected],
  );
  const onFinish = () => setOptions((o) => ({ ...o, override: null }));
  return { options, setOptions, transport, onFinish };
}

/** Chats live in memory and vanish on reload. Used when Supabase is not configured. */
function LocalAssistant({ footer }: { footer: ReactNode }) {
  const { options, setOptions, transport, onFinish } = useChatOptions();
  const runtime = useChatRuntime({ transport, onFinish });
  const [artifact, openArtifact] = useState<ArtifactSelection | null>(null);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatContext.Provider value={{ options, setOptions, openArtifact }}>
        <ChatShell artifact={artifact} footer={footer} />
      </ChatContext.Provider>
    </AssistantRuntimeProvider>
  );
}

/** Waits for the Clerk session, because the first Supabase request has to carry its token. */
function SavedAssistant() {
  const { isLoaded, user } = useUser();
  const db = useSupabase();
  if (!isLoaded || !user || !db) return <div className="auth-screen" aria-busy="true" />;
  return <PersistedAssistant db={db} userId={user.id} footer={<AccountFooter />} />;
}

/** Chats, messages and finished runs saved to Supabase, so the sidebar list and old chats survive reload. */
export function PersistedAssistant({
  db,
  userId,
  footer,
  transport: injected,
}: {
  db: Db;
  userId: string;
  footer: ReactNode;
  transport?: ChatTransport<UIMessage>;
}) {
  const { options, setOptions, transport, onFinish } = useChatOptions(injected);
  const adapter = useMemo(
    () => ({
      ...createThreadListAdapter(db),
      unstable_useAdapters: function useAdapters() {
        return useSupabaseAdapters(db);
      },
    }),
    [db],
  );
  const runtime = useRemoteThreadListRuntime({
    runtimeHook: function RuntimeHook() {
      return useChatRuntime({ transport, onFinish });
    },
    adapter,
  });
  const [artifact, openArtifact] = useState<ArtifactSelection | null>(null);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatContext.Provider
        value={{
          options,
          setOptions,
          openArtifact,
          saveVerdict: (runId, passed) => saveVerdict(db, runId, passed),
        }}
      >
        <RunSaver db={db} userId={userId} />
        <ChatShell artifact={artifact} footer={footer} />
      </ChatContext.Provider>
    </AssistantRuntimeProvider>
  );
}

/** Writes an agent run's record and files when its reply finishes. Runs reopened from history are not rewritten. */
function RunSaver({ db, userId }: { db: Db; userId: string }) {
  const aui = useAui();
  const running = useAuiState((s) => s.thread.isRunning);
  const wasRunning = useRef(false);
  useEffect(() => {
    if (running) {
      wasRunning.current = true;
      return;
    }
    if (!wasRunning.current) return;
    wasRunning.current = false;
    const last = aui.thread.getState().messages.at(-1);
    const raw = last?.metadata.custom as { run?: Run } | undefined;
    if (!last || !raw?.run || raw.run.status === "running") return;
    const run = raw.run;
    void (async () => {
      const item = aui.threads.item("main");
      const conversationId =
        item.getState().remoteId ?? (await item.initialize().catch(() => null))?.remoteId ?? null;
      const { failed } = await saveRun(db, {
        run,
        userId,
        conversationId,
        messageId: last.id,
        backend: (path) => fetch(`/api/py/${path}`),
      });
      if (failed.length)
        toast.error(`The run was saved, but some files were not: ${failed.join("; ")}`);
    })().catch((e) => toast.error(errorText(e)));
  }, [running, aui, db, userId]);
  return null;
}

function ChatShell({
  artifact,
  footer,
}: {
  artifact: ArtifactSelection | null;
  footer: ReactNode;
}) {
  const aui = useAui();
  const mobile = useIsMobile();
  const { openArtifact, setOptions } = useChat();
  const [sidebar, setSidebar] = useState(false);
  const [library, setLibrary] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [offline, setOffline] = useState(false);
  const hasChats = useAuiState((s) => s.threads.threadIds.length > 0);
  const threadId = useAuiState((s) => s.threads.mainThreadId);
  const running = useAuiState((s) => s.thread.isRunning);
  const firstText = useAuiState(
    (s) =>
      s.thread.messages.find((m) => m.role === "user")?.content.find((p) => p.type === "text")
        ?.text,
  );
  useEffect(() => {
    const item = aui.threads.item("main");
    // A reopened chat keeps its stored title instead of being renamed again.
    if (firstText && !item.getState().title) item.rename(firstText.slice(0, 60));
  }, [firstText, threadId, aui]);
  useEffect(() => {
    openArtifact(null);
    setSidebar(false);
  }, [threadId, openArtifact]);
  // A link ending in ?artifact=<run id> reopens that run's preview, so a finished file can be shared or reloaded.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("artifact");
    if (!id) return;
    api<Run>(`runs/${encodeURIComponent(id)}`)
      .then((run) => {
        if (run.artifact)
          openArtifact({
            artifact: run.artifact,
            title: AGENT_LABEL[run.agent],
            docxHref: `/api/py/runs/${run.id}/docx`,
            runId: run.id,
          });
      })
      .catch((e) => toast.error(errorText(e)));
  }, [openArtifact]);
  useEffect(() => {
    const refresh = () =>
      api<Status>("status").then(
        (s) => {
          setStatus(s);
          setOffline(false);
        },
        () => setOffline(true),
      );
    void refresh();
    const timer = setInterval(refresh, 8000);
    return () => clearInterval(timer);
  }, []);
  const newChat = () => {
    if (running) aui.thread.cancelRun();
    aui.threads.switchToNewThread();
    openArtifact(null);
    setOptions((o) => ({ ...o, csv: null, override: null }));
    setSidebar(false);
  };
  return (
    <div className="chat-app">
      {sidebar && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside className={`chat-sidebar ${sidebar ? "is-open" : ""}`} aria-label="Navigation">
        <div className="sidebar-brand">
          <RelayLogo />
          <span>Relay</span>
          <button
            className="icon-button mobile-only"
            aria-label="Close navigation"
            onClick={() => setSidebar(false)}
          >
            <X size={18} />
          </button>
        </div>
        <button className="nav-button" onClick={newChat}>
          <Pencil size={17} />
          New chat
        </button>
        <button
          className="nav-button"
          onClick={() => {
            setLibrary(true);
            setSidebar(false);
          }}
        >
          <Library size={17} />
          Recorded artifacts
        </button>
        <div className="sidebar-chats">
          <p className="section-label">Chats</p>
          {hasChats ? <ThreadListItems /> : <p className="section-label">No chats yet</p>}
        </div>
        {footer}
      </aside>
      <main className="chat-main">
        <header className="chat-header">
          <button
            className="icon-button mobile-only"
            aria-label="Open navigation"
            onClick={() => setSidebar(true)}
          >
            <PanelLeft size={20} />
          </button>
          <span>
            Relay <span className="header-subtitle">Chat</span>
          </span>
          <button
            className="icon-button ml-auto"
            aria-label="New chat"
            title="New chat"
            onClick={newChat}
          >
            <Pencil size={18} />
          </button>
        </header>
        {(offline || status?.stopped) && (
          <div className="connection-notice" role="status">
            {offline
              ? "The backend is unavailable. Reconnecting…"
              : `Live calls are stopped: ${status?.stopped}`}
          </div>
        )}
        <CanvasSplit className="chat-split">
          <CanvasSplitThread>
            <ChatThread />
          </CanvasSplitThread>
          {artifact && !mobile && <ArtifactPanel artifact={artifact} />}
        </CanvasSplit>
      </main>
      {artifact && mobile && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) openArtifact(null);
          }}
        >
          <DialogContent className="artifact-sheet" showCloseButton={false}>
            <DialogTitle className="sr-only">{artifact.title} artifact</DialogTitle>
            <DialogDescription className="sr-only">Generated artifact preview</DialogDescription>
            <ArtifactPanel artifact={artifact} />
          </DialogContent>
        </Dialog>
      )}
      <RecordedLibrary open={library} onOpenChange={setLibrary} />
    </div>
  );
}

function ArtifactPanel({ artifact }: { artifact: ArtifactSelection }) {
  const { openArtifact } = useChat();
  return (
    <CanvasSplitDocument className="artifact-panel" role="region" aria-label="Artifact preview">
      <header className="artifact-header">
        <FileText size={18} />
        <span>{artifact.title}</span>
        <button
          className="icon-button ml-auto"
          aria-label="Close artifact"
          onClick={() => openArtifact(null)}
        >
          <X size={18} />
        </button>
      </header>
      <div className="artifact-content">
        <ArtifactView
          key={artifact.docxHref}
          artifact={artifact.artifact}
          docxHref={artifact.docxHref}
          runId={artifact.runId}
        />
      </div>
    </CanvasSplitDocument>
  );
}

function ChatThread() {
  const empty = useAuiState((s) => s.thread.messages.length === 0);
  return (
    <ThreadPrimitive.Root className={`chat-thread ${empty ? "is-empty" : ""}`}>
      <ThreadPrimitive.Viewport className="chat-viewport" autoScroll>
        <div className="chat-column">
          {empty && (
            <div className="chat-welcome">
              <h1>What can I help with?</h1>
            </div>
          )}
          <div className="chat-messages">
            <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
          </div>
          <ThreadPrimitive.ViewportFooter className="chat-footer">
            <ChatComposer />
            <p className="composer-note">
              {empty
                ? "Ask a question, or turn on Agent to create something."
                : "AI can make mistakes. Check important details."}
            </p>
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}
function AgentSteps({
  running,
  count,
  children,
}: {
  running: boolean;
  count: number;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <ToolGroupRoot variant="ghost" open={running || expanded} onOpenChange={setExpanded}>
      <ToolGroupTrigger count={count} active={running} />
      <ToolGroupContent>
        <div className="agent-steps">{children}</div>
      </ToolGroupContent>
    </ToolGroupRoot>
  );
}
function UserMessage() {
  return (
    <MessagePrimitive.Root className="user-message">
      <MessagePrimitive.Parts />
    </MessagePrimitive.Root>
  );
}
function AssistantMessage() {
  const raw = useAuiState((s) => s.message.metadata.custom);
  const result = chatMeta.safeParse(raw);
  const meta = result.success ? result.data : {};
  const running = useAuiState((s) => s.message.status?.type === "running");
  const content = useAuiState((s) => s.message.content);
  const { openArtifact } = useChat();
  const opened = useRef<string | null>(null);
  useEffect(() => {
    if (meta.run?.artifact && opened.current !== meta.run.id) {
      opened.current = meta.run.id;
      openArtifact({
        artifact: meta.run.artifact,
        title: AGENT_LABEL[meta.run.agent],
        docxHref: `/api/py/runs/${meta.run.id}/docx`,
        runId: meta.run.id,
      });
    }
  }, [meta.run, openArtifact]);
  const tools = content.filter((p) => p.type === "tool-call");
  return (
    <MessagePrimitive.Root className={`assistant-message ${meta.failed ? "message-error" : ""}`}>
      {running && content.length === 0 && (
        <div role="status" className="thinking-state">
          <span className="thinking-dot" />
          <span className="shimmer">Thinking</span>
        </div>
      )}
      <MessagePrimitive.GroupedParts
        groupBy={(part) => (part.type === "tool-call" ? ["group-tools"] : [])}
      >
        {({ part, children }) => {
          if (part.type === "group-tools")
            return (
              <AgentSteps count={tools.length} running={running}>
                {children}
              </AgentSteps>
            );
          if (part.type === "text") return <MarkdownText />;
          if (part.type === "tool-call") return <AgentStep {...part} />;
          return null;
        }}
      </MessagePrimitive.GroupedParts>
      {meta.run?.artifact && (
        <button
          className="artifact-card-button"
          aria-label={`Open ${AGENT_LABEL[meta.run.agent]} artifact`}
          onClick={() => {
            if (meta.run?.artifact)
              openArtifact({
                artifact: meta.run.artifact,
                title: AGENT_LABEL[meta.run.agent],
                docxHref: `/api/py/runs/${meta.run.id}/docx`,
                runId: meta.run.id,
              });
          }}
        >
          <ArtifactCard title={AGENT_LABEL[meta.run.agent]} meta="Click to open preview" />
        </button>
      )}
      {!running && <ReplyActions meta={meta} />}
      <AuiIf condition={(s) => s.message.status?.type === "incomplete"}>
        <p className="text-sm text-muted-foreground mt-3">
          Response stopped. You can send another message or retry.
        </p>
      </AuiIf>
    </MessagePrimitive.Root>
  );
}
const AgentStep: ToolCallMessagePartComponent = ({ toolName, args, status }) => {
  const active = status.type === "running";
  const text = typeof args.text === "string" ? args.text : toolName;
  if (toolName === "text")
    return (
      <div className="agent-note">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
      </div>
    );
  const label = titleCase(toolName);
  const Icon = /shell|bash/.test(toolName)
    ? Terminal
    : /grep|read|glob/.test(toolName)
      ? Search
      : /write|edit/.test(toolName)
        ? Pencil
        : Brain;
  return (
    <div className="agent-step" data-running={active}>
      <Icon size={15} />
      <div>
        <span className={active ? "shimmer" : ""}>{label}</span>
        <p>{text}</p>
      </div>
    </div>
  );
};

function StopButton() {
  const aui = useAui();
  const raw = useAuiState((s) => s.thread.messages.at(-1)?.metadata.custom);
  const stop = async () => {
    const parsed = chatMeta.safeParse(raw);
    if (parsed.success && parsed.data.runId) {
      try {
        await api(`runs/${parsed.data.runId}/cancel`, {});
        return;
      } catch (e) {
        toast.error(errorText(e));
        return;
      }
    }
    aui.thread.cancelRun();
  };
  return (
    <button
      type="button"
      className="send-button ml-auto"
      aria-label="Stop response"
      onClick={() => void stop()}
    >
      <Square size={14} fill="currentColor" />
    </button>
  );
}
function ChatComposer() {
  const { options, setOptions } = useChat();
  const running = useAuiState((s) => s.thread.isRunning);
  const fileInput = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const attach = async (file?: File) => {
    if (!file) return;
    const size = csvSizeError(file);
    if (size) {
      setError(size);
      return;
    }
    try {
      const body = await file.text();
      const parsed = parse(body, { header: true, skipEmptyLines: true });
      if (
        !file.name.toLowerCase().endsWith(".csv") ||
        parsed.errors.length ||
        !parsed.meta.fields?.length ||
        !parsed.data.length
      )
        throw new Error(
          parsed.errors[0]?.message ?? "Attach a CSV with a header and at least one data row.",
        );
      setOptions((o) => ({ ...o, csv: { name: file.name, body }, agentMode: true }));
      setError(null);
      toast.success(`${file.name} attached`);
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <div>
      {error && (
        <p role="alert" className="upload-error">
          {error}
          <button aria-label="Dismiss upload error" onClick={() => setError(null)}>
            <X size={14} />
          </button>
        </p>
      )}
      <ComposerPrimitive.Root className="chat-composer">
        {options.csv && (
          <div className="attached-csv">
            <Paperclip size={16} />
            <span>{options.csv.name}</span>
            <button
              className="icon-button"
              aria-label="Remove CSV"
              onClick={() => setOptions((o) => ({ ...o, csv: null }))}
            >
              <X size={14} />
            </button>
          </div>
        )}
        <ComposerPrimitive.Input
          rows={1}
          autoFocus
          placeholder="Message Relay"
          aria-label="Message Relay"
          className="chat-input"
        />
        <div className="composer-controls">
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            tabIndex={-1}
            aria-label="Attach CSV"
            onChange={(e) => {
              void attach(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            className="icon-button"
            aria-label="Attach CSV file"
            title="Attach CSV"
            disabled={running}
            onClick={() => fileInput.current?.click()}
          >
            <Plus size={21} />
          </button>
          <button
            type="button"
            role="switch"
            aria-checked={options.agentMode}
            aria-label="Agent mode"
            className={`agent-toggle ${options.agentMode ? "active" : ""}`}
            disabled={running}
            onClick={() => setOptions((o) => ({ ...o, agentMode: !o.agentMode, override: null }))}
          >
            <span className="toggle-track">
              <span />
            </span>
            Agent
          </button>
          <select
            aria-label="Routing mode"
            className="mode-select"
            value={options.preference}
            disabled={running}
            onChange={(e) => {
              const pref = PREFERENCES.find((p) => p === e.target.value);
              if (pref) setOptions((o) => ({ ...o, preference: pref }));
            }}
          >
            {PREFERENCES.map((p) => (
              <option key={p} value={p}>
                {titleCase(p)}
              </option>
            ))}
          </select>
          {running ? (
            <StopButton />
          ) : (
            <ComposerPrimitive.Send className="send-button ml-auto" aria-label="Send message">
              <ArrowUp size={20} />
            </ComposerPrimitive.Send>
          )}
        </div>
      </ComposerPrimitive.Root>
    </div>
  );
}

function ReplyActions({ meta }: { meta: ChatMeta }) {
  const { setOptions, openArtifact, saveVerdict } = useChat();
  const aui = useAui();
  const [marked, setMarked] = useState(meta.run?.marked ?? null);
  const [marking, setMarking] = useState(false);
  const rerun = (agent?: Agent, model?: string) => {
    openArtifact(null);
    setOptions((o) => ({
      ...o,
      agentMode: !!meta.agentMode,
      preference: meta.preference ?? o.preference,
      csv: meta.run ? null : o.csv,
      override: { agent, model, rerun_of: meta.run?.id },
    }));
    // Let the transport's body callback observe the new rerun selection.
    setTimeout(() => {
      aui.message.reload();
    }, 0);
  };
  const mark = async (passed: boolean) => {
    if (!meta.run) return;
    setMarking(true);
    try {
      await api(`runs/${meta.run.id}/mark`, { passed });
      await saveVerdict?.(meta.run.id, passed).catch((e) => toast.error(errorText(e)));
      setMarked(passed);
      toast.success(passed ? "Marked as passed" : "Marked as failed");
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setMarking(false);
    }
  };
  return (
    <div className="reply-actions">
      <ActionBarPrimitive.Root className="contents">
        <ActionBarPrimitive.Copy className="icon-button" aria-label="Copy reply">
          <Copy size={15} />
        </ActionBarPrimitive.Copy>
      </ActionBarPrimitive.Root>
      {meta.run?.result?.appended && (
        <>
          <button
            className="icon-button"
            aria-label="Mark passed"
            aria-pressed={marked === true}
            disabled={marking}
            onClick={() => void mark(true)}
          >
            <ThumbsUp size={15} />
          </button>
          <button
            className="icon-button"
            aria-label="Mark failed"
            aria-pressed={marked === false}
            disabled={marking}
            onClick={() => void mark(false)}
          >
            <ThumbsDown size={15} />
          </button>
        </>
      )}
      <button className="icon-button" aria-label="Rerun reply" onClick={() => rerun()}>
        <RotateCcw size={15} />
      </button>
      <RoutingInfo meta={meta} rerun={rerun} />
    </div>
  );
}
function RoutingInfo({
  meta,
  rerun,
}: {
  meta: ChatMeta;
  rerun: (agent?: Agent, model?: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = meta.route?.decisions[meta.preference ?? "balanced"];
  const [agent, setAgent] = useState<Agent>(meta.run?.agent ?? selected?.agent ?? "code");
  const [model, setModel] = useState(
    meta.run?.model ?? meta.answer?.model ?? selected?.model ?? "",
  );
  const [past, setPast] = useState<Run[]>([]);
  useEffect(() => {
    if (open) api<Run[]>("runs").then(setPast, () => {});
  }, [open]);
  const usage = meta.run?.result ?? meta.answer;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button className="icon-button" aria-label="Reply information">
          <Info size={16} />
        </button>
      </DialogTrigger>
      <DialogContent className="routing-dialog">
        <DialogTitle>Reply information</DialogTitle>
        <DialogDescription>How this reply was routed and what it used.</DialogDescription>
        <div className="info-summary">
          <span>{MODEL_NAME[meta.run?.model ?? meta.answer?.model ?? ""] ?? "Router"}</span>
          <span>
            {usage
              ? `${money(usage.cost_usd)} · ${usage.wall_s.toFixed(1)} s`
              : "No usage recorded"}
          </span>
        </div>
        {meta.route && (
          <>
            <section>
              <h3>Agent vote</h3>
              <div className="vote-list">
                {meta.route.agents.map((v) => (
                  <div key={v.agent}>
                    <span>{AGENT_LABEL[v.agent]}</span>
                    <span>{pct(v.share)}</span>
                  </div>
                ))}
              </div>
              {selected?.runner_up.agent && (
                <p className="info-muted">
                  Agent runner-up: {AGENT_LABEL[selected.runner_up.agent.agent]} ·{" "}
                  {pct(selected.runner_up.agent.share)}
                </p>
              )}
              {selected?.runner_up.model && (
                <p className="info-muted">
                  Model runner-up:{" "}
                  {MODEL_NAME[selected.runner_up.model.model] ?? selected.runner_up.model.model}
                </p>
              )}
            </section>
            <section>
              <h3>Mode picks</h3>
              <div className="mode-picks">
                {PREFERENCES.map((p) => (
                  <div key={p}>
                    <span>{titleCase(p)}</span>
                    <strong>{MODEL_NAME[meta.route?.decisions[p].model ?? ""]}</strong>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <h3>Model estimates</h3>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Pass</th>
                      <th>Cost</th>
                      <th>Time</th>
                      <th>Past runs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected?.estimates.map((e) => (
                      <tr key={e.model}>
                        <td>{MODEL_NAME[e.model]}</td>
                        <td>{pct(e.p_pass)}</td>
                        <td>{money(e.cost_usd)}</td>
                        <td>{e.wall_s.toFixed(1)} s</td>
                        <td>{e.runs_seen}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="info-muted">{selected?.reasoning}</p>
            </section>
          </>
        )}
        {meta.routing && (
          <section>
            <h3>Model routing</h3>
            <p>{MODEL_NAME[meta.routing.model] ?? meta.routing.model}</p>
            {meta.routing.router && (
              <>
                <p className="info-muted">
                  Confidence {pct(meta.routing.router.confidence)} · Router{" "}
                  {meta.routing.router.routing_ms.toFixed(0)} ms
                </p>
                {Object.entries(meta.routing.router.probabilities).map(([key, value]) => (
                  <p className="info-muted" key={key}>
                    {key}: {pct(value)}
                  </p>
                ))}
              </>
            )}
            {meta.routing.routerError && (
              <p className="info-muted">The router was unavailable. Used the fallback model.</p>
            )}
          </section>
        )}
        {meta.run && (
          <section>
            <h3>Past runs</h3>
            {past
              .filter((r) => r.text === meta.run?.text)
              .map((r) => (
                <p className="info-muted" key={r.id}>
                  {AGENT_LABEL[r.agent]} · {MODEL_NAME[r.model]} · {r.status} ·{" "}
                  {r.result ? money(r.result.cost_usd) : "Running"}
                </p>
              ))}
          </section>
        )}
        <section>
          <h3>Try another selection</h3>
          <div className="rerun-controls">
            {meta.agentMode && (
              <label>
                Change agent
                <select
                  aria-label="Change agent"
                  value={agent}
                  onChange={(e) => {
                    const a = AGENTS.find((a) => a === e.target.value);
                    if (a) setAgent(a);
                  }}
                >
                  {AGENTS.map((a) => (
                    <option key={a} value={a}>
                      {AGENT_LABEL[a]}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Change model
              <select
                aria-label="Change model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                <option value="">Router choice</option>
                {Object.entries(MODEL_NAME).map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Button
            onClick={() => {
              setOpen(false);
              rerun(meta.agentMode ? agent : undefined, model || undefined);
            }}
          >
            Rerun reply
          </Button>
        </section>
      </DialogContent>
    </Dialog>
  );
}

function RecordedLibrary({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [index, setIndex] = useState<Recorded[]>([]);
  const [loading, setLoading] = useState<Agent | null>(null);
  const { openArtifact } = useChat();
  useEffect(() => {
    if (open) api<Recorded[]>("recorded").then(setIndex, (e) => toast.error(errorText(e)));
  }, [open]);
  const show = async (agent: Agent) => {
    const row =
      index.find((r) => r.agent === agent && r.passed && r.model.startsWith("deepseek/")) ??
      index.find((r) => r.agent === agent && r.passed);
    if (!row) return;
    setLoading(agent);
    const path = `recorded/${row.model.split("/").pop()}/${agent}/${row.task_id}`;
    try {
      const artifact = await api<Artifact>(path);
      openArtifact({ artifact, title: AGENT_LABEL[agent], docxHref: `/api/py/${path}/docx` });
      onOpenChange(false);
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setLoading(null);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Recorded artifacts</DialogTitle>
        <DialogDescription>
          Explore finished work. Opening a preview makes no paid calls.
        </DialogDescription>
        <div className="recorded-list">
          {AGENTS.map((a) => (
            <button disabled={!index.length || !!loading} key={a} onClick={() => void show(a)}>
              <FileText size={18} />
              <span>{AGENT_LABEL[a]}</span>
              {loading === a ? (
                <span className="shimmer">Opening</span>
              ) : (
                <ChevronRight size={16} />
              )}
            </button>
          ))}
        </div>
        {!index.length && <ArtifactSkeleton />}
      </DialogContent>
    </Dialog>
  );
}
