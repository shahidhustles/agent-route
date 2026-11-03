import type { SupabaseClient } from "@supabase/supabase-js";
import { createAssistantStream } from "assistant-stream";

/** The slice of the Supabase client the persistence layer uses, so tests can pass a fake. */
export type Db = Pick<SupabaseClient, "from" | "storage">;

type Failure = { message: string } | null;
const check = (what: string, error: Failure) => {
  if (error) throw new Error(`${what} failed: ${error.message}`);
};

/** A message as stored: the AI SDK message without its id, plus its place in the branch tree. */
export type StoredMessage = {
  id: string;
  parent_id: string | null;
  format: string;
  content: Record<string, unknown>;
};

type ConversationRow = { id: string; title: string | null; status: "regular" | "archived" };

export async function loadMessages(db: Db, conversationId: string): Promise<StoredMessage[]> {
  const { data, error } = await db
    .from("messages")
    .select("id, parent_id, format, message")
    .eq("conversation_id", conversationId)
    .order("created_at", { ascending: true })
    .order("id", { ascending: true });
  check("Loading messages", error);
  return (data ?? []).map((row) => ({
    id: row.id,
    parent_id: row.parent_id,
    format: row.format,
    content: row.message,
  }));
}

export async function saveMessage(db: Db, conversationId: string, message: StoredMessage) {
  const { error } = await db.from("messages").upsert(
    {
      conversation_id: conversationId,
      id: message.id,
      parent_id: message.parent_id,
      format: message.format,
      message: message.content,
    },
    { onConflict: "conversation_id,id" },
  );
  check("Saving a message", error);
}

/** Deletes messages and hands their children to the nearest surviving ancestor, like assistant-ui's local store. */
export async function removeMessages(db: Db, conversationId: string, ids: string[]) {
  const { data, error } = await db
    .from("messages")
    .select("id, parent_id")
    .eq("conversation_id", conversationId);
  check("Reading messages", error);
  const parents = new Map(
    (data ?? []).map((row) => [row.id as string, row.parent_id as string | null]),
  );
  const gone = new Set(ids);
  const survivor = (start: string | null) => {
    let parent = start;
    const seen = new Set<string>();
    while (parent !== null && gone.has(parent) && !seen.has(parent)) {
      seen.add(parent);
      parent = parents.get(parent) ?? null;
    }
    return parent !== null && gone.has(parent) ? null : parent;
  };
  for (const [id, parent] of parents) {
    if (gone.has(id) || parent === null || !gone.has(parent)) continue;
    const moved = await db
      .from("messages")
      .update({ parent_id: survivor(parent) })
      .eq("conversation_id", conversationId)
      .eq("id", id);
    check("Re-parenting a message", moved.error);
  }
  const removed = await db
    .from("messages")
    .delete()
    .eq("conversation_id", conversationId)
    .in("id", ids);
  check("Deleting messages", removed.error);
}

const metadata = (row: ConversationRow) => ({
  remoteId: row.id,
  externalId: undefined,
  status: row.status,
  title: row.title ?? undefined,
});

/** The conversation half of assistant-ui's RemoteThreadListAdapter. The history half is in history.ts. */
export function createThreadListAdapter(db: Db) {
  const update = async (id: string, patch: Partial<Pick<ConversationRow, "title" | "status">>) => {
    const { error } = await db.from("conversations").update(patch).eq("id", id);
    check("Updating the chat", error);
  };
  return {
    async list() {
      const { data, error } = await db
        .from("conversations")
        .select("id, title, status")
        .order("updated_at", { ascending: false })
        .limit(200);
      check("Listing chats", error);
      return { threads: (data ?? []).map(metadata) };
    },
    async initialize(_threadId: string) {
      const id = crypto.randomUUID();
      const { error } = await db.from("conversations").insert({ id });
      check("Creating the chat", error);
      return { remoteId: id, externalId: undefined };
    },
    rename: (id: string, title: string) => update(id, { title }),
    archive: (id: string) => update(id, { status: "archived" }),
    unarchive: (id: string) => update(id, { status: "regular" }),
    async delete(id: string) {
      const { error } = await db.from("conversations").delete().eq("id", id);
      check("Deleting the chat", error);
    },
    async fetch(id: string) {
      const { data, error } = await db
        .from("conversations")
        .select("id, title, status")
        .eq("id", id)
        .single();
      check("Reading the chat", error);
      return metadata(data as ConversationRow);
    },
    // The first message already becomes the title, and a title model call would spend credit.
    async generateTitle() {
      return createAssistantStream(() => {});
    },
  };
}
