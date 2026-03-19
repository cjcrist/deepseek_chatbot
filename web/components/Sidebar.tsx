"use client";

import { useEffect, useState } from "react";
import type { ChatSummary, ExplanationLevel } from "@/lib/types";

interface SidebarProps {
  userId: string;
  chats: ChatSummary[];
  activeChatId: string | null;
  explanationLevel: ExplanationLevel;
  onExplanationLevelChange: (level: ExplanationLevel) => void;
  onUserSwitch: (userId: string) => void;
  onNewChat: () => void;
  onSelectChat: (chatId: string) => void;
  onArchiveChat: (chatId: string) => void | Promise<void>;
  onOpenArchive: () => void;
}

function PencilIcon() {
  return (
    <svg
      className="w-3 h-3 text-zinc-500"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
      />
    </svg>
  );
}

function ChatBubbleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
      />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg
      className="w-4 h-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 4v16m8-8H4"
      />
    </svg>
  );
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return date.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  if (diffDays < 7) {
    return date.toLocaleDateString(undefined, { weekday: "short" });
  }
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 13l4 4L19 7"
      />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg
      className="w-3.5 h-3.5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13 7l5 5m0 0l-5 5m5-5H6"
      />
    </svg>
  );
}

function ArchiveBoxIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"
      />
    </svg>
  );
}

const LEVEL_LABELS: Record<
  ExplanationLevel,
  { title: string; hint: string }
> = {
  beginner: {
    title: "Beginner",
    hint: "Simple words, like ~5th grade",
  },
  moderate: {
    title: "Moderate",
    hint: "Junior engineer depth",
  },
  expert: {
    title: "Expert",
    hint: "Senior engineer, concise",
  },
};

export default function Sidebar({
  userId,
  chats,
  activeChatId,
  explanationLevel,
  onExplanationLevelChange,
  onUserSwitch,
  onNewChat,
  onSelectChat,
  onArchiveChat,
  onOpenArchive,
}: SidebarProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(userId);
  const [chatIdInput, setChatIdInput] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    setInputValue(userId);
  }, [userId]);

  const commitSwitch = () => {
    const trimmed = inputValue.trim();
    if (trimmed && trimmed !== userId) {
      onUserSwitch(trimmed);
    } else {
      setInputValue(userId);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") commitSwitch();
    if (e.key === "Escape") {
      setInputValue(userId);
      setIsEditing(false);
    }
  };

  const copyChatId = async (id: string) => {
    try {
      await navigator.clipboard.writeText(id);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((cur) => (cur === id ? null : cur)), 2000);
    } catch {
      setChatIdInput(id);
    }
  };

  return (
    <aside className="flex flex-col w-64 shrink-0 bg-zinc-900 border-r border-zinc-800 h-full">
      {/* Branding */}
      <div className="px-4 pt-5 pb-3 border-b border-zinc-800">
        <div className="flex items-center gap-2 mb-4">
          <ChatBubbleIcon className="w-5 h-5 text-indigo-400" />
          <h1 className="text-sm font-semibold text-zinc-200 tracking-wide">
            DeepSeek Chat
          </h1>
        </div>

        {/* User switcher */}
        <div>
          <p className="text-xs text-zinc-500 mb-1.5 uppercase tracking-wider">
            Active user
          </p>
          {isEditing ? (
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={commitSwitch}
              autoFocus
              className="w-full bg-zinc-800 border border-indigo-500 rounded-lg px-3 py-1.5 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="Enter user ID"
            />
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              className="w-full flex items-center gap-2.5 bg-zinc-800 hover:bg-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 transition-colors group"
              title="Click to switch user"
            >
              <span className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
                {userId.charAt(0).toUpperCase()}
              </span>
              <span className="flex-1 truncate text-left">{userId}</span>
              <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                <PencilIcon />
              </span>
            </button>
          )}
        </div>

        {/* Explanation depth */}
        <div className="mt-4">
          <label
            htmlFor="explanation-level"
            className="text-xs text-zinc-500 mb-1.5 uppercase tracking-wider block"
          >
            Explanation level
          </label>
          <select
            id="explanation-level"
            value={explanationLevel}
            onChange={(e) =>
              onExplanationLevelChange(e.target.value as ExplanationLevel)
            }
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            title={LEVEL_LABELS[explanationLevel].hint}
          >
            {(Object.keys(LEVEL_LABELS) as ExplanationLevel[]).map((key) => (
              <option key={key} value={key}>
                {LEVEL_LABELS[key].title} — {LEVEL_LABELS[key].hint}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* New Chat + Archive */}
      <div className="px-3 py-3 border-b border-zinc-800 space-y-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white rounded-lg px-3 py-2 text-sm font-medium transition-colors"
        >
          <PlusIcon />
          New Chat
        </button>
        <button
          type="button"
          onClick={onOpenArchive}
          className="w-full flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 rounded-lg px-3 py-2 text-xs font-medium transition-colors"
        >
          <ArchiveBoxIcon className="w-4 h-4" />
          Archived chats
        </button>
      </div>

      {/* Recall by Chat ID */}
      <div className="px-3 py-3 border-b border-zinc-800">
        <p className="text-xs text-zinc-500 mb-1.5 uppercase tracking-wider">
          Recall by chat ID
        </p>
        <div className="flex gap-1.5">
          <input
            type="text"
            value={chatIdInput}
            onChange={(e) => setChatIdInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                const id = chatIdInput.trim();
                if (id) {
                  onSelectChat(id);
                  setChatIdInput("");
                }
              }
            }}
            placeholder="Paste a chat ID…"
            className="flex-1 min-w-0 bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 font-mono break-all"
          />
          <button
            onClick={() => {
              const id = chatIdInput.trim();
              if (id) {
                onSelectChat(id);
                setChatIdInput("");
              }
            }}
            disabled={!chatIdInput.trim()}
            className="flex items-center justify-center w-8 h-8 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-zinc-300 transition-colors shrink-0"
            aria-label="Load chat"
            title="Load this chat"
          >
            <ArrowRightIcon />
          </button>
        </div>
      </div>

      {/* Chat history list */}
      <div className="flex-1 overflow-y-auto py-2 px-2">
        {chats.length === 0 ? (
          <p className="text-xs text-zinc-600 text-center mt-6 px-3 leading-relaxed">
            No chats yet.
            <br />
            Click &ldquo;New Chat&rdquo; to begin.
          </p>
        ) : (
          <ul className="space-y-1">
            {chats.map((chat) => {
              const isActive = chat.chat_id === activeChatId;
              return (
                <li key={chat.chat_id}>
                  <div
                    className={`flex items-stretch gap-1 rounded-lg border transition-colors ${
                      isActive
                        ? "bg-zinc-700/80 border-zinc-600"
                        : "bg-zinc-800/40 border-transparent hover:border-zinc-700"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectChat(chat.chat_id)}
                      className={`shrink-0 flex items-start pt-2.5 pl-2.5 pb-2 ${
                        isActive ? "text-indigo-400" : "text-zinc-600"
                      } hover:text-indigo-400 transition-colors`}
                      title="Open this chat"
                      aria-label="Open this chat"
                    >
                      <ChatBubbleIcon className="w-3.5 h-3.5" />
                    </button>
                    <div className="flex-1 min-w-0 py-2 pr-1 flex flex-col gap-1">
                      <button
                        type="button"
                        onClick={() => setChatIdInput(chat.chat_id)}
                        className={`w-full text-left font-mono text-[10px] leading-snug break-all rounded px-1 -mx-1 py-0.5 transition-colors ${
                          isActive
                            ? "text-zinc-100 hover:bg-zinc-600/50"
                            : "text-zinc-400 hover:text-indigo-300 hover:bg-zinc-800/80"
                        }`}
                        title="Put this ID in the recall field above"
                      >
                        {chat.chat_id}
                      </button>
                      <span className="text-zinc-600 text-[11px]">
                        {formatDate(chat.updated_at)}
                      </span>
                    </div>
                    <div className="shrink-0 flex flex-col border-l border-zinc-700/50">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          void onArchiveChat(chat.chat_id);
                        }}
                        className="w-9 h-9 flex items-center justify-center text-zinc-500 hover:text-amber-400 hover:bg-zinc-700/50 transition-colors rounded-tr-lg"
                        title="Archive chat"
                        aria-label="Archive chat"
                      >
                        <ArchiveBoxIcon className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => void copyChatId(chat.chat_id)}
                        className="w-9 h-9 flex items-center justify-center rounded-br-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-700/60 transition-colors border-t border-zinc-700/50"
                        title="Copy chat ID"
                        aria-label="Copy chat ID"
                      >
                        {copiedId === chat.chat_id ? (
                          <CheckIcon className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <CopyIcon className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-zinc-800">
        <p className="text-[11px] text-zinc-600 text-center">
          Powered by DeepInfra
        </p>
      </div>
    </aside>
  );
}
