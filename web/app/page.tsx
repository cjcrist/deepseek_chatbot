"use client";

import { useCallback, useEffect, useState } from "react";
import ArchivePanel from "@/components/ArchivePanel";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/ChatWindow";
import type {
  ChatMessage,
  ChatSummary,
  ExplanationLevel,
} from "@/lib/types";
import {
  archiveChat,
  getChatHistory,
  listChats,
  startChat,
} from "@/lib/api";

const DEFAULT_USER_ID = "user1";
const STORAGE_KEY = "chatbot_user_id";
const EXPLANATION_LEVEL_KEY = "chatbot_explanation_level";
const DEFAULT_EXPLANATION_LEVEL: ExplanationLevel = "moderate";

function readStoredUserId(): string {
  if (typeof window === "undefined") return DEFAULT_USER_ID;
  return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_USER_ID;
}

function readStoredExplanationLevel(): ExplanationLevel {
  if (typeof window === "undefined") return DEFAULT_EXPLANATION_LEVEL;
  const raw = localStorage.getItem(EXPLANATION_LEVEL_KEY);
  if (raw === "beginner" || raw === "moderate" || raw === "expert") {
    return raw;
  }
  return DEFAULT_EXPLANATION_LEVEL;
}

export default function Home() {
  const [userId, setUserId] = useState<string>(DEFAULT_USER_ID);
  const [explanationLevel, setExplanationLevel] =
    useState<ExplanationLevel>(DEFAULT_EXPLANATION_LEVEL);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [archiveOpen, setArchiveOpen] = useState(false);

  // Hydrate userId from localStorage on mount (avoids SSR mismatch)
  useEffect(() => {
    setUserId(readStoredUserId());
    setExplanationLevel(readStoredExplanationLevel());
  }, []);

  const handleExplanationLevelChange = (level: ExplanationLevel) => {
    localStorage.setItem(EXPLANATION_LEVEL_KEY, level);
    setExplanationLevel(level);
  };

  const loadChats = useCallback(async (uid: string) => {
    try {
      const res = await listChats(uid);
      setChats(res.chats);
    } catch {
      setChats([]);
    }
  }, []);

  useEffect(() => {
    if (userId) loadChats(userId);
  }, [userId, loadChats]);

  const handleUserSwitch = (newUserId: string) => {
    localStorage.setItem(STORAGE_KEY, newUserId);
    setUserId(newUserId);
    setActiveChatId(null);
    setMessages([]);
  };

  const handleNewChat = async () => {
    try {
      const res = await startChat(userId);
      setActiveChatId(res.chat_id);
      setMessages([]);
      await loadChats(userId);
    } catch (err) {
      console.error("Failed to start chat:", err);
    }
  };

  const handleSelectChat = async (chatId: string) => {
    setActiveChatId(chatId);
    try {
      const res = await getChatHistory(chatId, userId);
      setMessages(res.messages);
    } catch (err) {
      console.error("Failed to load chat history:", err);
      setMessages([]);
    }
  };

  // Called by ChatWindow after it auto-creates a chat on first message
  const handleChatStarted = async (chatId: string) => {
    setActiveChatId(chatId);
    await loadChats(userId);
  };

  const handleArchiveChat = async (chatId: string) => {
    try {
      await archiveChat(userId, chatId);
      if (activeChatId === chatId) {
        setActiveChatId(null);
        setMessages([]);
      }
      await loadChats(userId);
    } catch (err) {
      console.error("Archive failed:", err);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950">
      <Sidebar
        userId={userId}
        chats={chats}
        activeChatId={activeChatId}
        explanationLevel={explanationLevel}
        onExplanationLevelChange={handleExplanationLevelChange}
        onUserSwitch={handleUserSwitch}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onArchiveChat={handleArchiveChat}
        onOpenArchive={() => setArchiveOpen(true)}
      />
      <ArchivePanel
        isOpen={archiveOpen}
        onClose={() => setArchiveOpen(false)}
        userId={userId}
        onOpenChat={handleSelectChat}
        onChatsChanged={async () => {
          await loadChats(userId);
        }}
      />
      <ChatWindow
        userId={userId}
        activeChatId={activeChatId}
        explanationLevel={explanationLevel}
        messages={messages}
        onMessagesChange={setMessages}
        onChatStarted={handleChatStarted}
      />
    </div>
  );
}
