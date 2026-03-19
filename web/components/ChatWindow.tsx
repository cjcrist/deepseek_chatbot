"use client";

import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble";
import MessageInput from "./MessageInput";
import type { ChatMessage, ExplanationLevel } from "@/lib/types";
import {
  ApiError,
  NetworkError,
  streamAssistantMessage,
  startChat,
} from "@/lib/api";

interface ChatWindowProps {
  userId: string;
  activeChatId: string | null;
  explanationLevel: ExplanationLevel;
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  onChatStarted: (chatId: string) => void;
}

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-5">
      <div className="w-7 h-7 rounded-full bg-emerald-700 flex items-center justify-center text-[11px] font-bold text-white shrink-0 mr-2.5 mt-0.5">
        AI
      </div>
      <div className="bg-zinc-800 rounded-2xl rounded-bl-sm px-4 py-3">
        <div className="flex gap-1.5 items-center h-4">
          <span
            className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce"
            style={{ animationDelay: "0ms" }}
          />
          <span
            className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce"
            style={{ animationDelay: "300ms" }}
          />
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6">
      <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/20 flex items-center justify-center mb-5">
        <svg
          className="w-8 h-8 text-indigo-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-zinc-300 mb-2">
        Start a conversation
      </h2>
      <p className="text-sm text-zinc-500 max-w-xs leading-relaxed">
        Type a message below to begin chatting with DeepSeek AI. Select an
        existing chat from the sidebar to continue a previous conversation.
      </p>
    </div>
  );
}

function errorMessage(err: unknown): string {
  if (err instanceof NetworkError) {
    return err.message;
  }
  if (err instanceof ApiError) {
    if (err.status === 403) return "This chat belongs to a different user.";
    if (err.status === 404) return "Chat not found.";
    if (err.status === 502)
      return "AI service is temporarily unavailable. Please try again.";
    if (err.status === 500 || err.status === 503 || err.status === 504) {
      return err.message;
    }
    return err.message.startsWith("HTTP ")
      ? `Request failed (${err.message}).`
      : err.message;
  }
  return "Something went wrong. Check your connection and try again.";
}

export default function ChatWindow({
  userId,
  activeChatId,
  explanationLevel,
  messages,
  onMessagesChange,
  onChatStarted,
}: ChatWindowProps) {
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  /** True until the first SSE chunk arrives (show typing dots meanwhile). */
  const [awaitingStream, setAwaitingStream] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending, awaitingStream]);

  const handleSubmit = async () => {
    const content = input.trim();
    if (!content || isSending) return;

    setError(null);
    setIsSending(true);
    setInput("");

    // Optimistic user message so the UI feels instant
    const optimisticMsg: ChatMessage = {
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    const withOptimistic = [...messages, optimisticMsg];
    onMessagesChange(withOptimistic);

    try {
      let chatId = activeChatId;

      if (!chatId) {
        const started = await startChat(userId);
        chatId = started.chat_id;
        onChatStarted(chatId);
      }

      setAwaitingStream(true);
      const assistantStarted = new Date().toISOString();
      let accumulated = "";

      try {
        for await (const ev of streamAssistantMessage(
          chatId,
          userId,
          content,
          { explanationLevel },
        )) {
          if (ev.type === "chunk") {
            setAwaitingStream(false);
            accumulated += ev.text;
            onMessagesChange([
              ...withOptimistic,
              {
                role: "assistant",
                content: accumulated,
                created_at: assistantStarted,
              },
            ]);
          } else if (ev.type === "done") {
            setAwaitingStream(false);
            onMessagesChange([...withOptimistic, ev.message]);
          } else if (ev.type === "error") {
            throw new ApiError(502, ev.detail);
          }
        }
      } finally {
        setAwaitingStream(false);
      }
    } catch (err) {
      // Roll back the optimistic message
      onMessagesChange(messages);
      setInput(content);
      setError(errorMessage(err));
    } finally {
      setIsSending(false);
    }
  };

  const isEmpty = messages.length === 0 && !isSending;

  return (
    <div className="flex flex-col flex-1 min-w-0 h-full bg-zinc-950">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <EmptyState />
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-6">
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}

            {isSending && awaitingStream && <TypingIndicator />}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Error banner — always visible regardless of empty state */}
      {error && (
        <div className="max-w-3xl w-full mx-auto px-4 pb-2">
          <div className="flex items-start gap-3 bg-red-950/50 border border-red-800/60 rounded-xl px-4 py-3 text-sm text-red-400">
            <svg
              className="w-4 h-4 shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
            <span className="flex-1">{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-400 transition-colors ml-1"
              aria-label="Dismiss error"
            >
              &#x2715;
            </button>
          </div>
        </div>
      )}

      {/* Input bar */}
      <div className="max-w-3xl w-full mx-auto">
        <MessageInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          disabled={isSending}
          placeholder={
            activeChatId
              ? "Continue the conversation... (Enter to send, Shift+Enter for newline)"
              : "Type a message to start a new chat..."
          }
        />
      </div>
    </div>
  );
}
