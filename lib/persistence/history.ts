"use client";

import type {
  GenericThreadHistoryAdapter,
  MessageFormatAdapter,
  MessageFormatItem,
  RuntimeAdapters,
  ThreadHistoryAdapter,
} from "@assistant-ui/react";
import { useAui } from "@assistant-ui/react";
import { useEffect, useMemo, useRef } from "react";

import { loadMessages, removeMessages, saveMessage, type Db } from "./conversations";

type ThreadItem = {
  getState(): { remoteId?: string | undefined };
  initialize(): Promise<{ remoteId: string }>;
};
/** Reads and writes one thread's messages. `getItem` returns the thread this adapter belongs to. */
export function createHistoryAdapter(db: Db, getItem: () => ThreadItem): ThreadHistoryAdapter {
  return {
    // The AI SDK runtime always goes through withFormat; these two only satisfy the interface.
    load: async () => ({ messages: [] }),
    append: async () => {},
    withFormat: <T, S extends Record<string, unknown>>(
      formatAdapter: MessageFormatAdapter<T, S>,
    ): GenericThreadHistoryAdapter<T> => {
      let pinned: ThreadItem | undefined;
      const item = () => (pinned ??= getItem());
      const store = async (entry: MessageFormatItem<T>) => {
        const { remoteId } = await item().initialize();
        await saveMessage(db, remoteId, {
          id: formatAdapter.getId(entry.message),
          parent_id: entry.parentId,
          format: formatAdapter.format,
          content: formatAdapter.encode(entry),
        });
      };
      return {
        pin: () => void item(),
        async load() {
          const remoteId = item().getState().remoteId;
          if (!remoteId) return { messages: [] };
          const rows = await loadMessages(db, remoteId);
          return { messages: rows.map((row) => formatAdapter.decode(row as never)) };
        },
        append: store,
        update: store,
        async delete(entries: MessageFormatItem<T>[]) {
          const remoteId = item().getState().remoteId;
          if (!remoteId) return;
          await removeMessages(
            db,
            remoteId,
            entries.map((entry) => formatAdapter.getId(entry.message)),
          );
        },
      };
    },
  };
}

/** The `unstable_useAdapters` hook of the thread list adapter: per-thread history stored in Supabase. */
export function useSupabaseAdapters(db: Db): RuntimeAdapters {
  const aui = useAui();
  const auiRef = useRef(aui);
  useEffect(() => {
    auiRef.current = aui;
  });
  return useMemo(
    () => ({
      history: createHistoryAdapter(db, () => auiRef.current.threadListItem as ThreadItem),
    }),
    [db],
  );
}
