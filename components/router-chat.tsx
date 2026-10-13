"use client";

import {
  ActionBarPrimitive,
  AssistantRuntimeProvider,
  AuiIf,
  BranchPickerPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadListPrimitive,
  ThreadPrimitive,
  useAssistantDataUI,
  useAui,
  useAuiState,
  type DataMessagePartProps,
} from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/ai-sdk";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  RefreshCw,
  Route,
  Square,
} from "lucide-react";
import { useState, type ComponentProps, type FC } from "react";

type RoutingData = {
  status: "routing" | "selected";
  model?: string;
  confidence?: number;
};

const suggestions = [
  "Compare two approaches to caching API responses",
  "Draft a concise approval note for a project delay",
  "Debug a TypeScript function that drops the last item",
];

export function RouterChat() {
  const runtime = useChatRuntime();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <RoutingDataRenderer />
      <main className="app-shell">
        <header className="topbar">
          <ThreadListPrimitive.New
            className="brand-home"
            aria-label="Start a new chat"
            title="Start a new chat"
          >
            <span className="brand-mark" aria-hidden="true">
              <Route size={18} strokeWidth={2} />
            </span>
            <span>
              <span className="brand-name">Model Router</span>
              <span className="brand-caption">Task-aware selection</span>
            </span>
          </ThreadListPrimitive.New>
          <a className="agent-link" href="/agent">
            Code artifact agent
          </a>
          <span className="live-badge">
            <span />
            Router online
          </span>
        </header>
        <ChatThread />
      </main>
    </AssistantRuntimeProvider>
  );
}

function RoutingDataRenderer() {
  useAssistantDataUI({ name: "routing", render: RoutingStatus });
  return null;
}

const RoutingStatus: FC<DataMessagePartProps<RoutingData>> = ({ data }) => {
  const [open, setOpen] = useState(false);

  if (data.status === "routing") {
    return (
      <div className="routing-shimmer" role="status">
        Routing your task to the best model in the registry.
      </div>
    );
  }

  const confidence = Math.round((data.confidence ?? 0) * 100);
  return (
    <div className="routing-result">
      <button
        type="button"
        className="model-chip"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Route size={14} strokeWidth={2} />
        <span>{data.model}</span>
        <span className="confidence">{confidence}%</span>
        <ChevronDown size={14} className={open ? "chevron-open" : ""} />
      </button>
      {open && (
        <div className="model-popover" role="status">
          <p>Router recommendation</p>
          <dl>
            <div>
              <dt>Model</dt>
              <dd>{data.model}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{confidence}%</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
};

const ChatThread: FC = () => {
  const isEmpty = useAuiState((state) => state.thread.messages.length === 0);

  return (
    <ThreadPrimitive.Root className="thread-root">
      {isEmpty ? (
        <EmptyState />
      ) : (
        <ThreadPrimitive.Viewport className="thread-viewport">
          <ThreadPrimitive.Messages>
            {({ message }) => (message.role === "user" ? <UserMessage /> : <AssistantMessage />)}
          </ThreadPrimitive.Messages>
          <ThreadPrimitive.ViewportFooter className="thread-footer">
            <ThreadPrimitive.ScrollToBottom asChild>
              <button className="scroll-button" aria-label="Scroll to bottom">
                <ArrowDown size={17} />
              </button>
            </ThreadPrimitive.ScrollToBottom>
            <Composer />
            <p className="disclaimer">
              Responses may contain mistakes. Check important information.
            </p>
          </ThreadPrimitive.ViewportFooter>
        </ThreadPrimitive.Viewport>
      )}
    </ThreadPrimitive.Root>
  );
};

const EmptyState: FC = () => (
  <section className="empty-state">
    <div className="empty-content">
      <div className="empty-icon">
        <Route size={24} strokeWidth={1.8} />
      </div>
      <h1>What should we route?</h1>
      <p>Describe the task. The router will choose the strongest model before the answer begins.</p>
      <Composer />
      <SuggestionList />
    </div>
  </section>
);

const SuggestionList: FC = () => {
  const aui = useAui();
  return (
    <div className="suggestions" aria-label="Suggested prompts">
      {suggestions.map((suggestion) => (
        <button
          type="button"
          key={suggestion}
          onClick={() =>
            aui.thread.append({ role: "user", content: [{ type: "text", text: suggestion }] })
          }
        >
          {suggestion}
          <ArrowUp size={14} />
        </button>
      ))}
    </div>
  );
};

const Composer: FC = () => (
  <ComposerPrimitive.Root className="composer-root">
    <ComposerPrimitive.Input
      autoFocus
      rows={1}
      placeholder="Message the router"
      aria-label="Message the router"
      className="composer-input"
    />
    <div className="composer-actions">
      <div className="composer-hint">
        <Route size={15} />
        Auto route
      </div>
      <AuiIf condition={(state) => state.thread.isRunning}>
        <ComposerPrimitive.Cancel className="send-button" aria-label="Stop response">
          <Square size={13} fill="currentColor" />
        </ComposerPrimitive.Cancel>
      </AuiIf>
      <AuiIf condition={(state) => !state.thread.isRunning}>
        <ComposerPrimitive.Send className="send-button" aria-label="Send message">
          <ArrowUp size={19} strokeWidth={2.2} />
        </ComposerPrimitive.Send>
      </AuiIf>
    </div>
  </ComposerPrimitive.Root>
);

const UserMessage: FC = () => (
  <MessagePrimitive.Root className="message user-message">
    <div className="user-bubble">
      <MessagePrimitive.Parts />
    </div>
    <ActionBarPrimitive.Root autohide="always" className="message-actions">
      <ActionBarPrimitive.Copy asChild>
        <IconButton label="Copy">
          <Copy size={16} />
        </IconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Edit asChild>
        <button className="text-action">Edit</button>
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  </MessagePrimitive.Root>
);

const AssistantMessage: FC = () => (
  <MessagePrimitive.Root className="message assistant-message">
    <div className="assistant-body">
      <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
      <MessagePrimitive.Error>
        <ErrorPrimitive.Root className="error-box">
          <ErrorPrimitive.Message />
        </ErrorPrimitive.Root>
      </MessagePrimitive.Error>
    </div>
    <div className="assistant-controls">
      <ActionBarPrimitive.Root hideWhenRunning className="message-actions assistant-actions">
        <ActionBarPrimitive.Copy asChild>
          <IconButton label="Copy">
            <AuiIf condition={(state) => state.message.isCopied}>
              <Check size={16} />
            </AuiIf>
            <AuiIf condition={(state) => !state.message.isCopied}>
              <Copy size={16} />
            </AuiIf>
          </IconButton>
        </ActionBarPrimitive.Copy>
        <ActionBarPrimitive.Reload asChild>
          <IconButton label="Try again">
            <RefreshCw size={16} />
          </IconButton>
        </ActionBarPrimitive.Reload>
      </ActionBarPrimitive.Root>
      <BranchPicker />
    </div>
  </MessagePrimitive.Root>
);

const MarkdownText: FC = () => <MarkdownTextPrimitive />;

const BranchPicker: FC = () => (
  <BranchPickerPrimitive.Root hideWhenSingleBranch className="branch-picker">
    <BranchPickerPrimitive.Previous asChild>
      <IconButton label="Previous response">
        <ChevronLeft size={16} />
      </IconButton>
    </BranchPickerPrimitive.Previous>
    <span>
      <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
    </span>
    <BranchPickerPrimitive.Next asChild>
      <IconButton label="Next response">
        <ChevronRight size={16} />
      </IconButton>
    </BranchPickerPrimitive.Next>
  </BranchPickerPrimitive.Root>
);

function IconButton({ label, ...props }: ComponentProps<"button"> & { label: string }) {
  return (
    <button type="button" className="icon-button" aria-label={label} title={label} {...props} />
  );
}
