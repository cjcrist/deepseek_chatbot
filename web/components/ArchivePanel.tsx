"use client";

import { useCallback, useEffect, useState } from "react";
import type { ArchivedChatsResponse } from "@/lib/types";
import {
  deleteChatPermanently,
  listArchivedChats,
  restoreChat,
} from "@/lib/api";

interface ArchivePanelProps {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
  onOpenChat: (chatId: string) => void | Promise<void>;
  onChatsChanged: () => void | Promise<void>;
}

export default function ArchivePanel({
  isOpen,
  onClose,
  userId,
  onOpenChat,
  onChatsChanged,
}: ArchivePanelProps) {
  const [data, setData] = useState<ArchivedChatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listArchivedChats(userId);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load archive");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (isOpen) void load();
  }, [isOpen, load]);

  if (!isOpen) return null;

  const totalArchived =
    data?.buckets.reduce((n, b) => n + b.chats.length, 0) ?? 0;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="archive-panel-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="w-full max-w-md h-full bg-zinc-900 border-l border-zinc-800 shadow-xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <h2
            id="archive-panel-title"
            className="text-sm font-semibold text-zinc-100"
          >
            Archived chats
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 text-lg leading-none px-2 py-1 rounded-lg hover:bg-zinc-800"
            aria-label="Close archive panel"
          >
            ×
          </button>
        </div>

        <p className="px-4 py-2 text-[11px] text-zinc-500 leading-relaxed border-b border-zinc-800">
          Chats stay here for up to{" "}
          <span className="text-zinc-400 font-medium">
            {data?.retention_days ?? 30} days
          </span>{" "}
          after archiving, then are removed from the database. You can restore
          to the sidebar, open to read, or delete now.
        </p>

        <div className="flex-1 overflow-y-auto px-3 py-2">
          {loading && (
            <p className="text-xs text-zinc-500 text-center py-8">Loading…</p>
          )}
          {error && (
            <p className="text-xs text-red-400 text-center py-4">{error}</p>
          )}
          {!loading && !error && totalArchived === 0 && (
            <p className="text-xs text-zinc-600 text-center py-8 px-2">
              No archived chats. Use the archive button on a chat in the
              sidebar to hide it from the main list.
            </p>
          )}
          {data?.buckets.map((bucket) =>
            bucket.chats.length === 0 ? null : (
              <section key={bucket.bucket_id} className="mb-4">
                <h3 className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2 px-1">
                  {bucket.title}
                </h3>
                <ul className="space-y-2">
                  {bucket.chats.map((chat) => (
                    <li
                      key={chat.chat_id}
                      className="rounded-lg border border-zinc-800 bg-zinc-800/40 p-2.5"
                    >
                      <p className="font-mono text-[10px] text-zinc-300 break-all leading-snug mb-1">
                        {chat.chat_id}
                      </p>
                      <p className="text-[10px] text-zinc-600 mb-2">
                        Archived{" "}
                        {new Date(chat.archived_at).toLocaleString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        <button
                          type="button"
                          className="text-[10px] px-2 py-1 rounded-md bg-zinc-700 hover:bg-zinc-600 text-zinc-200"
                          onClick={async () => {
                            await onOpenChat(chat.chat_id);
                            onClose();
                          }}
                        >
                          Open
                        </button>
                        <button
                          type="button"
                          className="text-[10px] px-2 py-1 rounded-md bg-indigo-700/80 hover:bg-indigo-600 text-white"
                          onClick={async () => {
                            await restoreChat(userId, chat.chat_id);
                            await onChatsChanged();
                            await load();
                          }}
                        >
                          Restore
                        </button>
                        <button
                          type="button"
                          className="text-[10px] px-2 py-1 rounded-md bg-red-950/80 hover:bg-red-900/80 text-red-300"
                          onClick={async () => {
                            if (
                              !confirm(
                                "Permanently delete this chat and all messages?",
                              )
                            ) {
                              return;
                            }
                            await deleteChatPermanently(userId, chat.chat_id);
                            await onChatsChanged();
                            await load();
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ),
          )}
        </div>
      </div>
    </div>
  );
}
